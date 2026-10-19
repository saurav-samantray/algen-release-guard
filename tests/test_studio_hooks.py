"""The hook provider loaded the way Studio loads it: Runtime's allowlisted loader and env only."""

import json

import httpx
import pytest
from algen_agent_runtime.orchestration.container import build_container
from algen_agent_runtime.workflows import (
    MultiAgentWorkflowExecutor,
    WorkflowHookLoader,
    WorkflowStatus,
)
from test_github import api_fixture

from algen_release_guard.service import runtime_settings
from algen_release_guard.workflow import WORKFLOW


def studio_environment(policy, **overrides):
    return {
        "RELEASE_GUARD_POLICY": policy.model_dump_json(),
        "RELEASE_GUARD_REPOSITORIES": "example/project",
        "GITHUB_TOKEN": "",
        **overrides,
    }


async def load(environment, container):
    settings = runtime_settings()
    return settings.workflows[WORKFLOW], await WorkflowHookLoader(
        allowed_modules=["algen_release_guard"]
    ).aload(
        settings.workflows[WORKFLOW].hook_provider,
        container=container,
        manifest=settings.workflows[WORKFLOW],
        environment=environment,
        tenant_id="studio-project",
        user_id="studio-workflow",
        project_id="studio-project",
    )


async def test_studio_loaded_workflow_runs_evidence_only(monkeypatch, evidence, policy):
    github, calls = api_fixture(evidence)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: original(*a, **{**kw, "transport": github})
    )
    container = build_container(runtime_settings(), environment={})
    try:
        manifest, loaded = await load(studio_environment(policy), container)
        try:
            state = await MultiAgentWorkflowExecutor(container.runtime, loaded.hooks).run(
                manifest,
                {
                    "inputs": {
                        "repository": "example/project",
                        "pull_request": 7,
                        "evidence_only": True,
                    }
                },
                tenant_id="studio-project",
                user_id="studio-workflow",
            )
        finally:
            await loaded.aclose()
    finally:
        await container.aclose()
    assert state.status == WorkflowStatus.COMPLETED, state.error
    report = state.values["report"]
    assert report["assessment"]["verdict"] == "PASS"
    assert report["model"] == {"status": "not_requested"}
    assert report["markdown"].startswith("# Algen Release Guard")
    assert len(calls) == 6
    json.dumps(report)


@pytest.mark.parametrize(
    "overrides",
    [
        {"RELEASE_GUARD_REPOSITORIES": ""},
        {"RELEASE_GUARD_POLICY": ""},
        {"RELEASE_GUARD_POLICY": '{"required_checks": []}'},
    ],
)
async def test_missing_operator_settings_fail_closed(policy, overrides):
    container = build_container(runtime_settings(), environment={})
    try:
        with pytest.raises(Exception, match="RELEASE_GUARD_REPOSITORIES|validation|policy|JSON"):
            await load(studio_environment(policy, **overrides), container)
    finally:
        await container.aclose()


async def test_studio_input_schema_rejects_unlisted_fields(policy):
    container = build_container(runtime_settings(), environment={})
    try:
        manifest, loaded = await load(studio_environment(policy), container)
        try:
            state = await MultiAgentWorkflowExecutor(container.runtime, loaded.hooks).run(
                manifest,
                {"inputs": {"repository": "example/project", "pull_request": 7, "policy": {}}},
                tenant_id="studio-project",
                user_id="studio-workflow",
            )
        finally:
            await loaded.aclose()
    finally:
        await container.aclose()
    # Callers cannot weaken the operator policy through run inputs.
    assert state.status == WorkflowStatus.FAILED
    assert "evidence" not in state.values
