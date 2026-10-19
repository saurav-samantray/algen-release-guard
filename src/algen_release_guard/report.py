from __future__ import annotations

import re


def text(value: object) -> str:
    # Plain-text presentation: do not let repository/model content become active Markdown/HTML.
    return re.sub(r"([\\`*_{}\[\]()#+.!|<>~-])", r"\\\1", str(value)).replace("\n", " ")


def markdown(report: dict) -> str:
    evidence, assessment = report["evidence"], report["assessment"]
    lines = [
        "# Algen Release Guard",
        "",
        f"**Verdict: {assessment['verdict']}**",
        "",
        text(assessment["scope"]),
        "",
        f"Repository: {text(evidence['target']['repository'])}",
        f"PR: {evidence['target']['pull_request']}",
        f"Head: `{evidence['head_sha']}`",
        f"Base: `{evidence['base_sha']}`",
        f"Collected: {text(evidence['collected_at'])}",
        "",
        "## Deterministic findings",
        "",
    ]
    for finding in assessment["findings"]:
        lines.append(f"- **{finding['severity']}**: {text(finding['message'])}")
        for source in finding["evidence_ids"]:
            lines.append(f"  Evidence: [{source}]({evidence['sources'][source]})")
    lines.extend(["", "## AI explanation (advisory)", ""])
    if report["explanation"]:
        for item in report["explanation"]["findings"]:
            lines.extend(
                [
                    f"- {text(item['finding_id'])}: {text(item['explanation'])}",
                    f"  Suggested next step: {text(item['next_step'])}",
                ]
            )
    else:
        lines.append("Unavailable or not requested. No AI explanation is implied.")
    lines.extend(["", "## Limits", "", *[f"- {text(x)}" for x in report["limitations"]], ""])
    return "\n".join(lines)
