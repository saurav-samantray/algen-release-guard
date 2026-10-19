from __future__ import annotations

from types import SimpleNamespace

import pytest

from algen_release_guard import service
from algen_release_guard.contracts import (
    Check,
    Evidence,
    FileChange,
    ReleasePolicy,
    RequiredCheck,
    Review,
    Target,
    timestamp,
)


@pytest.fixture(autouse=True)
def no_trace_export(monkeypatch):
    """Tests never send spans to Traccia; the shipped config is checked separately."""
    settings = service.AppSettings

    def validate(data):
        data["telemetry"]["traccia"]["enabled"] = False
        return settings.model_validate(data)

    monkeypatch.setattr(service, "AppSettings", SimpleNamespace(model_validate=validate))


@pytest.fixture
def evidence():
    return Evidence(
        target=Target(repository="example/project", pull_request=7),
        collected_at=timestamp(),
        head_sha="a" * 40,
        base_sha="b" * 40,
        pr_state="open",
        draft=False,
        merged=False,
        mergeable=True,
        mergeable_state="clean",
        author="author",
        stable=True,
        checks=[
            Check(
                id=1,
                name="tests",
                kind="check",
                app_id=15368,
                state="completed",
                conclusion="success",
                sha="a" * 40,
            )
        ],
        reviews=[
            Review(
                id=1, user="maintainer", state="APPROVED", commit_id="a" * 40, association="MEMBER"
            )
        ],
        files=[FileChange(filename="app.py", changes=10)],
        errors=[],
        sources={
            "pr": "https://github.com/example/project/pull/7",
            "checks": "https://github.com/example/project/pull/7/checks",
            "reviews": "https://github.com/example/project/pull/7#pullrequestreview",
            "files": "https://github.com/example/project/pull/7/files",
        },
    )


@pytest.fixture
def policy():
    return ReleasePolicy(required_checks=[RequiredCheck(name="tests", app_id=15368)])
