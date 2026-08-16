from __future__ import annotations

from datetime import date

from cre_foundry.models import EvidenceEvent, Signal


def _recency(event_date: date, as_of: date) -> tuple[int, float]:
    days = max(0, (as_of - event_date).days)
    # Smooth, legible decay: 1.0 today, 0.5 at ~90 days, ~0.2 at one year.
    score = 1.0 / (1.0 + days / 90.0)
    return days, score


def _magnitude(event: EvidenceEvent) -> float:
    if event.event_type == "building_permit":
        if event.amount is None:
            return 0.45
        # Piecewise scale avoids pretending the relationship is linear.
        if event.amount >= 5_000_000:
            return 1.0
        if event.amount >= 1_000_000:
            return 0.85
        if event.amount >= 250_000:
            return 0.65
        return 0.4
    if event.event_type == "expansion":
        return 0.8
    if event.event_type == "business_record":
        return 0.35
    return 0.25


def build_signal(
    *,
    business_id: str,
    event: EvidenceEvent,
    entity_confidence: float,
    as_of: date,
    corroboration_count: int = 1,
) -> Signal:
    days, _ = _recency(event.event_date, as_of)
    corroboration = min(1.0, 0.35 + 0.2 * max(0, corroboration_count - 1))
    summary = f"{event.event_type.replace('_', ' ')} on {event.event_date.isoformat()}"
    if event.amount:
        summary += f" (${event.amount:,.0f})"
    if event.description:
        summary += f": {event.description}"
    return Signal(
        signal_id=f"sig:{event.event_id}",
        business_id=business_id,
        event_id=event.event_id,
        signal_type=event.event_type,
        event_date=event.event_date,
        recency_days=days,
        magnitude=_magnitude(event),
        corroboration=corroboration,
        entity_confidence=entity_confidence,
        evidence_summary=summary,
    )


def recency_score(signal: Signal) -> float:
    return 1.0 / (1.0 + signal.recency_days / 90.0)
