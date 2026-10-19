from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml
from algen_agent_runtime.config.settings import AppSettings
from algen_agent_runtime.orchestration.container import build_container
from algen_agent_runtime.workflows import MultiAgentWorkflowExecutor, WorkflowStatus

from .contracts import ReleasePolicy, Target
from .github import GitHubReader
from .workflow import WORKFLOW, build_hooks

# Source checkouts (editable installs, Studio managed builds) read the project's config;
# wheels carry the same file, force-included by pyproject.toml.
SOURCE_CONFIG = Path(__file__).resolve().parents[2] / "config" / "agent.yaml"


class WorkflowFailedError(Exception):
    """The workflow did not complete; carries a status only, never node diagnostics."""


def runtime_settings() -> AppSettings:
    path = SOURCE_CONFIG
    raw = (
        path.read_text()
        if path.is_file()
        else files("algen_release_guard").joinpath("config/agent.yaml").read_text()
    )
    data = yaml.safe_load(raw)
    data.pop("extensions", None)  # Studio-only export declarations
    # Deliberately exclude ambient Runtime overrides from this fixed application contract.
    return AppSettings.model_validate(data)


async def run_assessment(
    target: Target,
    policy: ReleasePolicy,
    allowed_repositories: frozenset[str],
    *,
    github_token: str | None,
    openai_key: str | None,
    evidence_only: bool = False,
    reader: GitHubReader | None = None,
) -> dict:
    """Run the `release-readiness` workflow locally, exactly as Studio runs it."""
    if not evidence_only and not openai_key:
        raise ValueError(
            "OPENAI_API_KEY is required; use --evidence-only for a deterministic assessment"
        )
    reader = reader or GitHubReader(github_token)
    try:
        settings = runtime_settings()
        container = build_container(
            settings, environment={"OPENAI_API_KEY": openai_key} if openai_key else {}
        )
    except BaseException:
        await reader.aclose()
        raise
    hooks = build_hooks(
        policy=policy,
        allowed_repositories=allowed_repositories,
        reader=reader,
        runtime=container.runtime,
    )
    try:
        state = await MultiAgentWorkflowExecutor(container.runtime, hooks.hooks).run(
            settings.workflows[WORKFLOW],
            {"inputs": {**target.model_dump(), "evidence_only": evidence_only}},
            tenant_id="local",
            user_id="operator",
        )
        if state.status != WorkflowStatus.COMPLETED:
            raise WorkflowFailedError(f"workflow_{state.status.value}")
        return state.values["report"]
    finally:
        await hooks.aclose()
        await container.aclose()
