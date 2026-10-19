from __future__ import annotations

from datetime import UTC, datetime

from .contracts import Assessment, Evidence, Finding, ReleasePolicy


def assess(evidence: Evidence, policy: ReleasePolicy, *, now: datetime | None = None) -> Assessment:
    findings = []

    def add(code: str, message: str, source: str, severity: str = "blocker") -> None:
        findings.append(Finding(id=code, severity=severity, message=message, evidence_ids=[source]))

    try:
        age = (
            (now or datetime.now(UTC)) - datetime.fromisoformat(evidence.collected_at)
        ).total_seconds()
    except (ValueError, TypeError):
        age = -1
    if age < 0 or age > policy.max_evidence_age_seconds:
        add(
            "stale_evidence",
            "Evidence timestamp is invalid or outside the policy freshness window.",
            "pr",
            "unknown",
        )
    for error in evidence.errors:
        add(error, "A required evidence source could not be collected completely.", "pr", "unknown")
    if not evidence.stable:
        add(
            "pr_changed",
            "PR state, head, or base changed during collection. Collect a new snapshot.",
            "pr",
            "unknown",
        )
    if evidence.pr_state != "open" or evidence.merged:
        add("not_open", "The PR is not an open, unmerged candidate.", "pr")
    if evidence.draft:
        add("draft", "The PR is still a draft.", "pr")
    if evidence.mergeable is None or evidence.mergeable_state in {"unknown", "unchecked"}:
        add("mergeability_unknown", "GitHub has not established mergeability.", "pr", "unknown")
    elif evidence.mergeable is not True or evidence.mergeable_state != "clean":
        add(
            "mergeability_blocked",
            "GitHub does not report a clean, mergeable PR. Branch rules may block it.",
            "pr",
        )
    for index, required in enumerate(policy.required_checks):
        matches = [
            c
            for c in evidence.checks
            if c.name == required.name
            and c.kind == required.kind
            and (required.app_id is None or c.app_id == required.app_id)
        ]
        if required.kind == "check" and required.app_id is None:
            add(
                f"check_{index}_untrusted",
                "Required check policy needs a trusted GitHub App ID.",
                "checks",
                "unknown",
            )
        if not matches:
            add(
                f"check_{index}_missing",
                "A required check is missing for the selected commit.",
                "checks",
            )
        elif any(
            c.sha != evidence.head_sha or c.state != "completed" or c.conclusion != "success"
            for c in matches
        ):
            add(
                f"check_{index}_not_passed",
                "A required check is pending, failed, skipped, or belongs to another commit.",
                "checks",
            )
    if any(
        c.state != "completed" or c.conclusion not in {"success", "neutral", "skipped"}
        for c in evidence.checks
    ):
        add(
            "observed_checks_not_passed",
            "At least one observed check or commit status is pending or unsuccessful.",
            "checks",
        )
    latest = {}
    for review in sorted(evidence.reviews, key=lambda r: r.id):
        if review.state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[review.user.lower()] = review
    if any(r.state == "CHANGES_REQUESTED" for r in latest.values()):
        add("changes_requested", "An outstanding review requests changes.", "reviews")
    approvals = [
        r
        for r in latest.values()
        if r.state == "APPROVED"
        and r.commit_id == evidence.head_sha
        and r.user.lower() != evidence.author.lower()
        and r.association in {"OWNER", "MEMBER", "COLLABORATOR"}
    ]
    if len(approvals) < policy.minimum_approvals:
        add(
            "insufficient_approvals",
            "Not enough trusted reviewers approved the current head commit.",
            "reviews",
        )
    if not evidence.files:
        add("no_changed_files", "No changed-file evidence is available.", "files", "unknown")
    if (
        len(evidence.files) > policy.max_changed_files
        or sum(f.changes for f in evidence.files) > policy.max_changed_lines
    ):
        add("change_size", "Change size exceeds the operator's review policy.", "files")
    verdict = (
        "INCOMPLETE"
        if any(f.severity == "unknown" for f in findings)
        else "BLOCKED"
        if findings
        else "PASS"
    )
    if not findings:
        add(
            "policy_passed",
            "All configured checks, review, mergeability, freshness, and size rules passed for this snapshot.",
            "pr",
            "info",
        )
    return Assessment(verdict=verdict, findings=findings)
