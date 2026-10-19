from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

from .contracts import Target
from .service import run_assessment, runtime_settings
from .workflow import MAX_POLICY_BYTES, parse_allowlist, parse_policy


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".release-guard-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess an allowlisted GitHub PR with the Algen Runtime release-readiness workflow"
    )
    parser.add_argument("--repository")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    parser.add_argument(
        "--evidence-only",
        action="store_true",
        help="Skip OpenAI; collect real GitHub evidence and apply policy",
    )
    parser.add_argument("--validate-config", action="store_true")
    args = parser.parse_args(argv)
    try:
        runtime_settings()
        if args.validate_config:
            print(
                f"Runtime configuration valid: algen-agent-runtime=={version('algen-agent-runtime')}"
            )
            return 0
        if not args.repository or not args.pr or not args.policy:
            parser.error("--repository, --pr and --policy are required")
        load_dotenv(args.env_file, override=False)
        if args.policy.stat().st_size > MAX_POLICY_BYTES:
            raise ValueError("policy_file_too_large")
        policy = parse_policy(args.policy.read_text())
        allowed = parse_allowlist(os.getenv("RELEASE_GUARD_REPOSITORIES", ""))
        report = asyncio.run(
            run_assessment(
                Target(repository=args.repository, pull_request=args.pr),
                policy,
                allowed,
                github_token=os.getenv("GITHUB_TOKEN") or None,
                openai_key=os.getenv("OPENAI_API_KEY") or None,
                evidence_only=args.evidence_only,
            )
        )
        rendered = report.pop("markdown")
        stem = args.output_dir / report["run_id"]
        atomic_write(stem.with_suffix(".json"), json.dumps(report, indent=2) + "\n")
        atomic_write(stem.with_suffix(".md"), rendered)
        print(
            json.dumps(
                {
                    "verdict": report["assessment"]["verdict"],
                    "model": report["model"]["status"],
                    "report": str(stem.with_suffix(".json")),
                }
            )
        )
        if report["assessment"]["verdict"] == "INCOMPLETE" or report["model"]["status"] in {
            "failed",
            "discarded",
        }:
            return 3
        return 0 if report["assessment"]["verdict"] == "PASS" else 2
    except KeyboardInterrupt:
        print("Interrupted; no passing assessment was produced.", file=sys.stderr)
        return 130
    except Exception as exc:
        # Validation errors can echo input; emit only the class, never values or tokens.
        print(
            f"Assessment failed ({type(exc).__name__}); check configuration, access, and service availability.",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
