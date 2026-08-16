from __future__ import annotations

from rapidfuzz.fuzz import ratio

from cre_foundry.models import Business, EvidenceEvent, MatchResult
from cre_foundry.normalization import normalize_address, normalize_name


def resolve_event(
    event: EvidenceEvent,
    businesses: list[Business],
    *,
    accept_threshold: float = 0.88,
    ambiguity_margin: float = 0.06,
) -> MatchResult:
    """Resolve one event conservatively; abstain when the top two candidates are too close."""
    candidates: list[tuple[float, Business, str]] = []
    event_address = normalize_address(event.address or "")
    event_name = normalize_name(event.account_name or "")

    for business in businesses:
        if event.city and business.city.casefold() != event.city.casefold():
            continue
        address = normalize_address(business.address)
        name = normalize_name(business.name)

        if event_address and address == event_address:
            score, method = 0.98, "exact_address"
            if event_name:
                score = min(1.0, score + 0.02 * (ratio(event_name, name) / 100.0))
        else:
            address_score = ratio(event_address, address) / 100.0 if event_address else 0.0
            name_score = ratio(event_name, name) / 100.0 if event_name else 0.0
            score = 0.65 * address_score + 0.35 * name_score
            method = "fuzzy_address_name"
        candidates.append((score, business, method))

    if not candidates:
        return MatchResult(
            business_id=None,
            confidence=0,
            method="none",
            abstained=True,
            reason="no candidates in city",
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    top_score, top_business, top_method = candidates[0]
    runner_score = candidates[1][0] if len(candidates) > 1 else 0.0

    if top_score < accept_threshold:
        return MatchResult(
            business_id=None,
            confidence=top_score,
            method=top_method,
            abstained=True,
            reason="below confidence threshold",
        )
    if top_score - runner_score < ambiguity_margin:
        return MatchResult(
            business_id=None,
            confidence=top_score,
            method=top_method,
            abstained=True,
            reason="ambiguous candidates",
        )
    return MatchResult(
        business_id=top_business.business_id,
        confidence=round(top_score, 4),
        method=top_method,
    )
