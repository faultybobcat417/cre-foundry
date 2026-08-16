from __future__ import annotations

from collections import defaultdict

from cre_foundry.models import Business, RankedAccount, Signal
from cre_foundry.signals import recency_score

WEIGHTS = {
    "recency": 0.30,
    "magnitude": 0.25,
    "corroboration": 0.20,
    "entity_confidence": 0.15,
    "signal_diversity": 0.10,
}


def score_accounts(businesses: list[Business], signals: list[Signal]) -> list[RankedAccount]:
    grouped: dict[str, list[Signal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.business_id].append(signal)

    ranked: list[RankedAccount] = []
    for business in businesses:
        account_signals = grouped.get(business.business_id, [])
        if not account_signals:
            continue

        recency = max(recency_score(s) for s in account_signals)
        magnitude = max(s.magnitude for s in account_signals)
        corroboration = max(s.corroboration for s in account_signals)
        entity_confidence = min(s.entity_confidence for s in account_signals)
        diversity = min(1.0, len({s.signal_type for s in account_signals}) / 3.0)

        components = {
            "recency": recency,
            "magnitude": magnitude,
            "corroboration": corroboration,
            "entity_confidence": entity_confidence,
            "signal_diversity": diversity,
        }
        score = 100.0 * sum(WEIGHTS[key] * value for key, value in components.items())
        confidence = min(1.0, entity_confidence * (0.85 + 0.05 * len(account_signals)))

        rationale = [
            min(account_signals, key=lambda s: s.recency_days).evidence_summary,
            f"{len(account_signals)} evidence event(s), "
            f"{len({s.signal_type for s in account_signals})} signal type(s)",
        ]
        ranked.append(
            RankedAccount(
                business=business,
                priority_score=round(score, 1),
                confidence=round(confidence, 2),
                component_scores={k: round(v, 3) for k, v in components.items()},
                signals=sorted(account_signals, key=lambda s: s.event_date, reverse=True),
                rationale=rationale,
            )
        )

    return sorted(ranked, key=lambda row: (-row.priority_score, row.business.name))
