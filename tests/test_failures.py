import asyncio
import os

import httpx
import pytest
from test_github import api_fixture

from algen_release_guard.cli import atomic_write
from algen_release_guard.github import GitHubError, GitHubReader
from algen_release_guard.report import markdown
from algen_release_guard.service import run_assessment


async def test_transient_http_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, json={"ok": True})

    reader = GitHubReader(None, transport=httpx.MockTransport(handler))
    try:
        assert (await reader.get("/repos/example/project/pulls/7"))[0] == {"ok": True}
        assert reader.requests == 2
    finally:
        await reader.aclose()


async def test_bad_json():
    reader = GitHubReader(
        None, transport=httpx.MockTransport(lambda _: httpx.Response(200, text="not json"))
    )
    try:
        with pytest.raises(GitHubError, match="invalid_json"):
            await reader.get("/repos/example/project/pulls/7")
    finally:
        await reader.aclose()


async def test_cancellation_propagates_and_closes(monkeypatch, evidence, policy):
    reader = GitHubReader(None)

    async def cancel(*args):
        raise asyncio.CancelledError

    monkeypatch.setattr(reader, "collect", cancel)
    with pytest.raises(asyncio.CancelledError):
        await run_assessment(
            evidence.target,
            policy,
            frozenset({"example/project"}),
            github_token=None,
            openai_key=None,
            evidence_only=True,
            reader=reader,
        )
    assert reader.client.is_closed


def test_private_atomic_report(tmp_path):
    path = tmp_path / "report.json"
    atomic_write(path, "one")
    atomic_write(path, "two")
    assert path.read_text() == "two"
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.iterdir()) == [path]


async def test_report_escapes_model_markup(evidence, policy):
    transport, _ = api_fixture(evidence)
    report = await run_assessment(
        evidence.target,
        policy,
        frozenset({"example/project"}),
        github_token=None,
        openai_key=None,
        evidence_only=True,
        reader=GitHubReader(None, transport=transport),
    )
    report["explanation"] = {
        "findings": [
            {
                "finding_id": "x",
                "explanation": "<script>bad</script> [steal](https://evil.invalid)",
                "next_step": "none",
            }
        ]
    }
    rendered = markdown(report)
    assert "<script>" not in rendered and "[steal](" not in rendered
