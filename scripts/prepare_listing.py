"""Prepare and validate a local marketplace manifest. Never uploads or publishes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "publisher",
        "maintainer",
        "email",
        "license",
        "repository",
        "source-commit",
        "artifact-url",
        "security-url",
        "support-url",
    ):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    for url in (args.repository, args.artifact_url, args.security_url, args.support_url):
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.password or parsed.username:
            parser.error("All publication URLs must be credential-free HTTPS URLs")
    archive = ROOT / "dist/algen-release-guard-0.2.0.algen"
    data = archive.read_bytes()
    manifest = {
        "schema_version": "algen-marketplace-manifest/v1",
        "package_id": args.publisher + "/algen-release-guard",
        "version": "0.2.0",
        "display_name": "Algen Release Guard",
        "summary": "Read-only GitHub PR readiness checks with deterministic blockers and evidence-linked OpenAI explanations.",
        "description": "Algen Runtime workflow (release-readiness) on algen-agent-runtime 0.1.0a5 or later 0.1.x, runnable from the CLI or imported into Algen Studio. Reads allowlisted GitHub PR metadata and current-commit checks/reviews. Does not merge, publish or deploy. OpenAI receives generic findings only. Model/API charges are paid by the operator. Studio import and local hook execution are tested; hosted Studio execution is not certified. PASS means local policy passed for a timestamped snapshot, not deployment approval.",
        "license": args.license,
        "taxonomy": {
            "categories": ["engineering/developer-tools"],
            "tags": ["github", "release-readiness", "read-only", "algen-runtime"],
        },
        "framework": {"name": "algen", "version": "0.1.0a5"},
        "io_contract": {
            "inputs": [{"name": "request", "media_type": "application/json", "required": True}],
            "outputs": [{"name": "report", "media_type": "application/json", "required": True}],
            "streaming": False,
        },
        "pricing": {"model": "free"},
        "deployment": {
            "execution": "customer_managed",
            "isolation": "process",
            "minimum_memory_mb": 512,
            "gpu_required": False,
        },
        "delivery": {
            "type": "algen_package",
            "format": "algen-package/v1",
            "entrypoint": "algen_release_guard.cli:main",
            "artifact": {
                "url": args.artifact_url,
                "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "media_type": "application/vnd.algen.package+zip",
            },
        },
        "capabilities": [
            {
                "kind": "workflow",
                "name": "pr_readiness",
                "description": "Collect evidence, evaluate explicit local policy, explain findings and save a report.",
            }
        ],
        # Empty compatibility range: no hosted Studio version is certified yet.
        "compatibility": {
            "studio": ">=0.0.0 <0.0.0",
            "runtimes": [
                "python/3.12",
                "algen-agent-runtime/0.1.0a5",
                "algen-agent-runtime/0.1.0a7",
            ],
        },
        "evidence": {"review_status": "not_reviewed"},
        "ownership": {
            "publisher_id": args.publisher,
            "maintainers": [{"name": args.maintainer, "contact": args.email}],
            "source_repository": args.repository,
            "support_url": args.support_url,
        },
        "provenance": {
            "origin": "generated",
            "generated_at": datetime.now(UTC).isoformat(),
            "source_commit": args.source_commit,
        },
        "security": {
            "data_classes": ["user_content", "personal_data", "credentials"],
            "data_handling": {
                "purposes": ["Assess GitHub PR readiness", "Generate an advisory explanation"],
                "retention": "indefinite",
                "training_use": "none",
                "third_party_sharing": True,
                "recipients": [
                    "GitHub: repository requests and GitHub credential",
                    "OpenAI: generic findings and OpenAI credential",
                ],
            },
            "permissions": {
                "filesystem": "read_write",
                "environment": ["OPENAI_API_KEY", "GITHUB_TOKEN", "RELEASE_GUARD_REPOSITORIES"],
                "tools": ["github.release_evidence"],
            },
            "network": {"outbound": ["api.github.com", "api.openai.com"]},
            "secrets": [
                {
                    "name": "OPENAI_API_KEY",
                    "purpose": "Advisory explanation through OpenAI",
                    "required": True,
                    "scope": "Operator-owned OpenAI project",
                },
                {
                    "name": "GITHUB_TOKEN",
                    "purpose": "Read selected repositories",
                    "required": False,
                    "scope": "Metadata, Pull requests, Checks, Contents and Commit statuses read only",
                },
            ],
            "reporting_url": args.security_url,
        },
        "links": {"documentation": args.repository},
    }
    jsonschema.Draft202012Validator(
        json.loads((ROOT / "docs/marketplace-manifest.schema.json").read_text()),
        format_checker=jsonschema.FormatChecker(),
    ).validate(manifest)
    output = ROOT / "dist/marketplace-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Prepared {output}; not published. Verify URL reachability, category, license, source commit and AgentStripes receipt before submission."
    )


if __name__ == "__main__":
    main()
