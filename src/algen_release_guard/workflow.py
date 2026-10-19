"""Runtime workflow hooks for `release-readiness`, shared by the CLI and Algen Studio."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any

from algen_agent_runtime.policies.engine import CompositePolicyEngine
from algen_agent_runtime.tools.contracts import ToolContext
from algen_agent_runtime.tools.executor import ToolExecutor
from algen_agent_runtime.tools.registry import ToolRegistry
from algen_agent_runtime.types.contracts import RunStatus
from algen_agent_runtime.workflows import (
    WorkflowHookContext,
    WorkflowHookRegistry,
    WorkflowNodeStatus,
)

from . import __version__
from .contracts import Assessment, Evidence, Explanation, ReleasePolicy, Target, timestamp
from .github import GitHubReader, evidence_tool
from .policy import assess
from .report import markdown

WORKFLOW = "release-readiness"
MAX_POLICY_BYTES = 64000
LIMITATIONS = [
    "Snapshot only; re-run immediately before a human merge or deployment decision.",
    "Local policy is not a complete evaluation of GitHub branch rules, CODEOWNERS, or merge queues.",
    "No source-code audit, security certification, production telemetry, or deployment validation.",
    "Model prose is advisory and can be wrong; deterministic findings are authoritative.",
]


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def parse_policy(raw: str) -> ReleasePolicy:
    if len(raw.encode()) > MAX_POLICY_BYTES:
        raise ValueError("policy_too_large")
    return ReleasePolicy.model_validate_json(raw)


def parse_allowlist(raw: str) -> frozenset[str]:
    allowed = frozenset(s.strip() for s in raw.split(",") if s.strip())
    if not allowed:
        raise ValueError("RELEASE_GUARD_REPOSITORIES must contain an explicit owner/repo allowlist")
    return allowed


def validate_explanation(raw: str, assessment: Assessment) -> Explanation:
    if len(raw.encode()) > 20000:
        raise ValueError("explanation_too_large")
    explanation = Explanation.model_validate_json(raw)
    expected = {f.id: set(f.evidence_ids) for f in assessment.findings}
    ids = [f.finding_id for f in explanation.findings]
    if len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ValueError("explanation_finding_mismatch")
    for item in explanation.findings:
        if set(item.evidence_ids) != expected[item.finding_id]:
            raise ValueError("explanation_evidence_mismatch")
    return explanation


@dataclass
class ReleaseGuardHooks:
    """Runtime's hook loader uses `.hooks` and calls `aclose()` when the workflow ends."""

    hooks: WorkflowHookRegistry
    reader: GitHubReader

    async def aclose(self) -> None:
        await self.reader.aclose()


def build_hooks(
    *,
    policy: ReleasePolicy,
    allowed_repositories: frozenset[str],
    reader: GitHubReader,
    runtime: Any = None,
) -> ReleaseGuardHooks:
    registry = ToolRegistry()
    registry.register(evidence_tool(reader, allowed_repositories))
    executor = ToolExecutor(registry, CompositePolicyEngine())
    hooks = WorkflowHookRegistry()

    async def collect_evidence(context: WorkflowHookContext) -> dict[str, Any]:
        state = context.state
        inputs = state.values["inputs"]
        target = Target(repository=inputs["repository"], pull_request=inputs["pull_request"])
        result = await executor.execute(
            "github.release_evidence",
            target.model_dump(),
            ToolContext(
                run_id=state.id,
                step_id=context.node.id,
                tenant_id=state.tenant_id,
                user_id=state.user_id,
                permissions=frozenset({"github:read"}),
                idempotency_key=f"{state.id}:{context.node.id}",
            ),
        )
        return Evidence.model_validate(result.value).model_dump(mode="json")

    def assess_evidence(context: WorkflowHookContext) -> dict[str, Any]:
        return assess(
            Evidence.model_validate(context.state.values["evidence"]), policy
        ).model_dump()

    def explanation_input(context: WorkflowHookContext) -> str:
        # Only deterministic finding text and source labels cross the model boundary.
        return Assessment.model_validate(context.state.values["assessment"]).model_dump_json()

    def explanation_validator(value: Any, context: WorkflowHookContext) -> str | None:
        assessment = Assessment.model_validate(context.state.values["assessment"])
        try:
            validate_explanation(json.dumps(value), assessment)
        except ValueError:
            # Never echo model output or validation detail into run errors.
            return "explanation_invalid"
        return None

    async def build_report(context: WorkflowHookContext) -> dict[str, Any]:
        state = context.state
        evidence = Evidence.model_validate(state.values["evidence"])
        assessment = Assessment.model_validate(state.values["assessment"])
        explain = state.nodes["explain"]
        explanation = None
        if explain.status == WorkflowNodeStatus.COMPLETED:
            explanation = state.values["explanation"]
            model = {"status": "completed", **await _model_details(state, explain.run_ids)}
        elif explain.status == WorkflowNodeStatus.SKIPPED:
            model = {"status": "not_requested"}
        else:
            # Do not erase the deterministic report or echo provider diagnostics.
            model = {"status": "failed", "error": "explanation_unavailable_or_invalid"}
        # A long model call must not leave a passing report with expired evidence.
        final_assessment = assess(evidence, policy)
        if final_assessment != assessment:
            assessment = final_assessment
            explanation = None
            model = {"status": "discarded", "error": "evidence_expired_during_explanation"}
        report = {
            "schema_version": "release-guard-report/v1",
            "agent_version": __version__,
            "runtime_version": version("algen-agent-runtime"),
            "workflow": f"{state.manifest_name}@{state.manifest_version}",
            "run_id": state.id,
            "generated_at": timestamp(),
            "assessment": assessment.model_dump(),
            "policy": policy.model_dump(),
            "policy_sha256": digest(policy.model_dump()),
            "evidence": evidence.model_dump(mode="json"),
            "evidence_sha256": digest(evidence.model_dump(mode="json")),
            "explanation": explanation,
            "model": model,
            "github_requests": reader.requests,
            "limitations": LIMITATIONS,
        }
        return {**report, "markdown": markdown(report)}

    async def _model_details(state: Any, run_ids: list[str]) -> dict[str, Any]:
        details: dict[str, Any] = {
            "run_id": run_ids[-1] if run_ids else None,
            "billing_note": "Runtime cost estimates are not billed charges; use token counts and the provider billing dashboard.",
        }
        if runtime is not None and run_ids:
            try:
                result = await runtime.wait(run_ids[-1], state.tenant_id)
                if result.status == RunStatus.COMPLETED:
                    details["execution"] = result.execution_summary.model_dump(mode="json")
            except Exception:
                # Usage is informative; a host that runs agents elsewhere may not expose it.
                pass
        return details

    hooks.register_handler("release_guard.collect_evidence", collect_evidence)
    hooks.register_handler("release_guard.assess", assess_evidence)
    hooks.register_builder("release_guard.explanation_input", explanation_input)
    hooks.register_schema("release_guard.explanation_schema", Explanation.model_json_schema())
    hooks.register_validator("release_guard.explanation_validator", explanation_validator)
    hooks.register_handler("release_guard.report", build_report)
    return ReleaseGuardHooks(hooks, reader)


def create_workflow_hooks(
    *,
    container: Any,
    environment: dict[str, str],
    **_: Any,
) -> ReleaseGuardHooks:
    """Studio/Runtime hook provider; operator settings come only from the environment."""
    return build_hooks(
        policy=parse_policy(environment.get("RELEASE_GUARD_POLICY", "")),
        allowed_repositories=parse_allowlist(environment.get("RELEASE_GUARD_REPOSITORIES", "")),
        reader=GitHubReader(environment.get("GITHUB_TOKEN") or None),
        runtime=container.runtime,
    )
