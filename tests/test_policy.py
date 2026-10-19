from datetime import datetime, timedelta

import pytest

from algen_release_guard.contracts import RequiredCheck
from algen_release_guard.policy import assess


def test_clean_snapshot(evidence, policy):
    assert assess(evidence, policy).verdict == "PASS"


@pytest.mark.parametrize(
    "field,value,verdict",
    [
        ("draft", True, "BLOCKED"),
        ("merged", True, "BLOCKED"),
        ("pr_state", "closed", "BLOCKED"),
        ("mergeable", None, "INCOMPLETE"),
        ("mergeable", False, "BLOCKED"),
        ("mergeable_state", "blocked", "BLOCKED"),
        ("mergeable_state", "behind", "BLOCKED"),
        ("stable", False, "INCOMPLETE"),
        ("errors", ["truncated"], "INCOMPLETE"),
        ("checks", [], "BLOCKED"),
        ("reviews", [], "BLOCKED"),
        ("files", [], "INCOMPLETE"),
        ("collected_at", "invalid", "INCOMPLETE"),
    ],
)
def test_fail_closed(evidence, policy, field, value, verdict):
    assert assess(evidence.model_copy(update={field: value}), policy).verdict == verdict


@pytest.mark.parametrize(
    "conclusion", ["failure", "cancelled", "timed_out", "skipped", "neutral", None]
)
def test_required_checks_must_succeed(evidence, policy, conclusion):
    evidence.checks[0].conclusion = conclusion
    assert assess(evidence, policy).verdict == "BLOCKED"


@pytest.mark.parametrize(
    "field,value", [("app_id", 99), ("sha", "c" * 40), ("state", "in_progress")]
)
def test_check_identity_and_state(evidence, policy, field, value):
    setattr(evidence.checks[0], field, value)
    assert assess(evidence, policy).verdict == "BLOCKED"


def test_require_trusted_app(evidence, policy):
    policy.required_checks = [RequiredCheck(name="tests")]
    assert assess(evidence, policy).verdict == "INCOMPLETE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("commit_id", "c" * 40),
        ("user", "author"),
        ("association", "CONTRIBUTOR"),
        ("state", "DISMISSED"),
        ("state", "CHANGES_REQUESTED"),
    ],
)
def test_reviews(evidence, policy, field, value):
    setattr(evidence.reviews[0], field, value)
    assert assess(evidence, policy).verdict == "BLOCKED"


def test_later_comment_does_not_dismiss_requested_changes(evidence, policy):
    evidence.reviews[0].state = "CHANGES_REQUESTED"
    evidence.reviews.append(evidence.reviews[0].model_copy(update={"id": 2, "state": "COMMENTED"}))
    assert "changes_requested" in {f.id for f in assess(evidence, policy).findings}


def test_duplicate_reviews_do_not_count_twice(evidence, policy):
    policy.minimum_approvals = 2
    evidence.reviews.append(evidence.reviews[0].model_copy(update={"id": 2}))
    assert assess(evidence, policy).verdict == "BLOCKED"


def test_stale_and_future_snapshot(evidence, policy):
    for delta in (-1, 301):
        now = datetime.fromisoformat(evidence.collected_at) + timedelta(seconds=delta)
        assert assess(evidence, policy, now=now).verdict == "INCOMPLETE"


def test_size_limit(evidence, policy):
    evidence.files[0].changes = 99999
    assert assess(evidence, policy).verdict == "BLOCKED"
