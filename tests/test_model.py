import json

import httpx
import pytest
from test_github import api_fixture

from algen_release_guard.github import GitHubReader
from algen_release_guard.policy import assess
from algen_release_guard.service import run_assessment, runtime_settings
from algen_release_guard.workflow import WORKFLOW, validate_explanation


def response(assessment):
    return {
        "findings": [
            {
                "finding_id": f.id,
                "explanation": f.message,
                "next_step": "Review the linked evidence before deciding.",
                "evidence_ids": f.evidence_ids,
            }
            for f in assessment.findings
        ]
    }


def openai_route(monkeypatch, evidence, content):
    """Route OpenAI through a mock; GitHub keeps the recorded fixture."""
    github, _ = api_fixture(evidence)
    calls = []

    def handler(request):
        if request.url.host != "api.openai.com":
            return github.handler(request)
        calls.append(request)
        if isinstance(content, int):
            return httpx.Response(
                content, json={"error": {"message": "private provider diagnostic"}}
            )
        return httpx.Response(
            200,
            json={
                "id": "test",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: original(*a, **{**kw, "transport": httpx.MockTransport(handler)}),
    )
    return calls


async def run(evidence, policy):
    return await run_assessment(
        evidence.target,
        policy,
        frozenset({"example/project"}),
        github_token=None,
        openai_key="unit-test-credential",
        reader=GitHubReader(None),
    )


def test_config_declares_studio_workflow():
    settings = runtime_settings()
    assert settings.agents[0].enabled_tools == frozenset()
    workflow = settings.workflows[WORKFLOW]
    assert workflow.hook_provider == "algen_release_guard.workflow:create_workflow_hooks"
    assert [node.id for node in workflow.nodes] == [
        "collect",
        "assess",
        "explain",
        "explained",
        "report",
    ]


@pytest.mark.parametrize(
    "mutation", ["verdict", "invented_id", "invented_source", "missing_finding", "duplicate"]
)
def test_reject_invalid_model_output(evidence, policy, mutation):
    assessment = assess(evidence, policy)
    value = response(assessment)
    if mutation == "verdict":
        value["verdict"] = "PASS"
    elif mutation == "invented_id":
        value["findings"][0]["finding_id"] = "invented"
    elif mutation == "invented_source":
        value["findings"][0]["evidence_ids"] = ["invented"]
    elif mutation == "missing_finding":
        value["findings"] = []
    else:
        value["findings"].append(value["findings"][0])
    with pytest.raises(ValueError):
        validate_explanation(json.dumps(value), assessment)


async def test_openai_wire_contract_through_workflow(monkeypatch, evidence, policy):
    calls = openai_route(monkeypatch, evidence, json.dumps(response(assess(evidence, policy))))
    report = await run(evidence, policy)
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    assert body["model"] == "gpt-4.1-mini-2025-04-14"
    assert body["response_format"]["type"] == "json_schema"
    assert "example/project" not in calls[0].content.decode()
    assert report["model"]["status"] == "completed"
    assert report["model"]["execution"]["model_calls"] == 1
    assert report["explanation"]["findings"][0]["finding_id"] == "policy_passed"
    assert report["workflow"] == "release-readiness@0.2.0"


@pytest.mark.parametrize("content", ["not json", json.dumps({"findings": []}), 500])
async def test_model_failure_preserves_deterministic_evidence(
    monkeypatch, evidence, policy, content
):
    openai_route(monkeypatch, evidence, content)
    report = await run(evidence, policy)
    assert report["assessment"]["verdict"] == "PASS"
    assert report["model"] == {"status": "failed", "error": "explanation_unavailable_or_invalid"}
    assert report["explanation"] is None
    assert "private provider diagnostic" not in json.dumps(report)
