from datetime import date

from cre_foundry.models import Business, Signal
from cre_foundry.scoring import score_accounts


def make_signal(business_id: str, recency: int, magnitude: float) -> Signal:
    return Signal(
        signal_id=f"s:{business_id}:{recency}", business_id=business_id, event_id="e",
        signal_type="building_permit", event_date=date(2026, 8, 1), recency_days=recency,
        magnitude=magnitude, corroboration=0.55, entity_confidence=0.95,
        evidence_summary="fixture"
    )


def test_more_recent_signal_ranks_higher_other_things_equal():
    businesses = [
        Business(business_id="a", name="A", address="1 A Rd", city="Brampton", industry="X"),
        Business(business_id="b", name="B", address="2 B Rd", city="Brampton", industry="X"),
    ]
    rows = score_accounts(businesses, [make_signal("a", 5, 0.7), make_signal("b", 200, 0.7)])
    assert rows[0].business.business_id == "a"
