from datetime import UTC, date, datetime

from cre_foundry.entity_resolution import resolve_event
from cre_foundry.models import Business, EvidenceEvent


def event(address: str, name: str | None = None) -> EvidenceEvent:
    return EvidenceEvent(
        event_id="evt:x", source_id="s", source_record_id="r",
        observed_at=datetime.now(UTC), event_date=date(2026, 8, 1),
        event_type="building_permit", account_name=name, address=address, city="Brampton"
    )


def test_exact_address_match():
    businesses = [Business(business_id="b1", name="Northstar Logistics", address="8100 Dixie Road", city="Brampton", industry="Logistics")]
    result = resolve_event(event("8100 Dixie Rd", "Northstar Logistics Inc"), businesses)
    assert result.business_id == "b1"
    assert not result.abstained


def test_shared_address_abstains_when_ambiguous():
    businesses = [
        Business(business_id="b1", name="Twin Creek Distribution", address="5000 Steeles Avenue East", city="Brampton", industry="Distribution"),
        Business(business_id="b2", name="Twin Creek Storage", address="5000 Steeles Avenue East", city="Brampton", industry="Storage"),
    ]
    result = resolve_event(event("5000 Steeles Ave East", "Twin Creek"), businesses)
    assert result.abstained
    assert result.business_id is None
