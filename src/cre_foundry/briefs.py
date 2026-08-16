from __future__ import annotations

from cre_foundry.models import RankedAccount


def render_markdown(account: RankedAccount, rank: int) -> str:
    lines = [
        f"# {rank}. {account.business.name}",
        "",
        f"**Priority:** {account.priority_score:.1f}/100  ",
        f"**Confidence:** {account.confidence:.2f}  ",
        f"**Location:** {account.business.address}, {account.business.city}  ",
        f"**Industry:** {account.business.industry}",
        "",
        "## Why now",
        "",
    ]
    lines.extend(f"- {item}" for item in account.rationale)
    lines.extend(["", "## Evidence", ""])
    for signal in account.signals:
        lines.append(
            f"- **{signal.signal_type.replace('_', ' ').title()}** — {signal.evidence_summary} "
            f"(entity confidence {signal.entity_confidence:.2f})"
        )
    lines.extend(["", "## Score components", ""])
    lines.extend(f"- `{key}`: {value:.3f}" for key, value in account.component_scores.items())
    lines.extend(
        [
            "",
            "> Decision-support heuristic only. Review evidence before contacting an account.",
            "",
        ]
    )
    return "\n".join(lines)
