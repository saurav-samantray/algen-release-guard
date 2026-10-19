from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Target(Contract):
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}$")
    pull_request: int = Field(ge=1, le=2147483647)


class RequiredCheck(Contract):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["check", "status"] = "check"
    # Prevent a different GitHub App from impersonating a required check name.
    app_id: int | None = Field(default=None, ge=1)


class ReleasePolicy(Contract):
    required_checks: list[RequiredCheck] = Field(min_length=1, max_length=30)
    minimum_approvals: int = Field(default=1, ge=1, le=10)
    max_changed_files: int = Field(default=200, ge=1, le=1000)
    max_changed_lines: int = Field(default=3000, ge=1, le=100000)
    max_evidence_age_seconds: int = Field(default=300, ge=30, le=900)


class Check(Contract):
    id: int
    name: str = Field(max_length=200)
    kind: Literal["check", "status"]
    app_id: int | None
    state: str = Field(max_length=50)
    conclusion: str | None = Field(max_length=50)
    sha: str


class Review(Contract):
    id: int
    user: str
    state: str
    commit_id: str
    association: str


class FileChange(Contract):
    filename: str = Field(max_length=1024)
    changes: int = Field(ge=0)


class Evidence(Contract):
    target: Target
    collected_at: str
    head_sha: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    base_sha: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    pr_state: str
    draft: bool
    merged: bool
    mergeable: bool | None
    mergeable_state: str
    author: str
    stable: bool
    checks: list[Check]
    reviews: list[Review]
    files: list[FileChange]
    errors: list[str]
    sources: dict[str, str]


class Finding(Contract):
    id: str
    severity: Literal["blocker", "unknown", "info"]
    message: str
    evidence_ids: list[str]


class Assessment(Contract):
    verdict: Literal["PASS", "BLOCKED", "INCOMPLETE"]
    scope: str = "Selected PR readiness under the supplied local policy; not deployment approval."
    findings: list[Finding]


class ExplanationItem(Contract):
    finding_id: str
    explanation: str = Field(min_length=1, max_length=1000)
    next_step: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=40)


class Explanation(Contract):
    findings: list[ExplanationItem] = Field(min_length=1, max_length=80)


def timestamp() -> str:
    from datetime import UTC

    return datetime.now(UTC).isoformat()
