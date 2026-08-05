from __future__ import annotations

import pytest

from cre_foundry.permit_signals import (
    classify_permit_signal,
)


@pytest.mark.parametrize(
    (
        "permit_number",
        "work_description",
        "expected_event",
        "expected_strength",
    ),
    [
        (
            "26-124048-000-00",
            "Interior/Unit Finish",
            "tenant_fitout",
            "high",
        ),
        (
            "26-119005-000-00",
            "Addition - Complete",
            "building_addition",
            "high",
        ),
        (
            "26-121053-000-00",
            "Alteration (Renovation)",
            "alteration",
            "medium",
        ),
        (
            "26-100000-000-00",
            "Change of Use",
            "change_of_use",
            "high",
        ),
        (
            "26-100001-000-00",
            "New Industrial Building",
            "new_construction",
            "high",
        ),
        (
            "26-100002-000-00",
            "HVAC Only",
            "building_system",
            "medium",
        ),
        (
            "26-100003-000-00",
            "Demolition",
            "demolition",
            "review",
        ),
        (
            "26-040037-P01-01",
            "Revision",
            "revision",
            "review",
        ),
        (
            "26-100004-000-00",
            None,
            "other",
            "review",
        ),
    ],
)
def test_classifies_permit_work(
    permit_number: str,
    work_description: str | None,
    expected_event: str,
    expected_strength: str,
) -> None:
    result = classify_permit_signal(
        permit_number=permit_number,
        work_description=work_description,
        status="Applied",
    )

    assert result.event_type == expected_event
    assert result.signal_strength == expected_strength
    assert result.outreach_eligible is False


@pytest.mark.parametrize(
    (
        "status",
        "expected_stage",
        "expected_candidate",
    ),
    [
        ("Applied", "application", True),
        (
            "Zoning Certified",
            "zoning_certified",
            True,
        ),
        (
            "Ready to Issue",
            "ready_to_issue",
            True,
        ),
        ("Issued", "issued", True),
        (
            "Occupancy Granted",
            "occupancy_granted",
            False,
        ),
        ("Closed", "closed", False),
        ("Cancelled", "cancelled", False),
        ("Revoked", "revoked", False),
        (
            "Deemed Abandoned",
            "deemed_abandoned",
            False,
        ),
        (None, "unknown", False),
    ],
)
def test_classifies_lifecycle(
    status: str | None,
    expected_stage: str,
    expected_candidate: bool,
) -> None:
    result = classify_permit_signal(
        permit_number="26-124048-000-00",
        work_description=("Interior/Unit Finish"),
        status=status,
    )

    assert result.lifecycle_stage == expected_stage
    assert result.signal_candidate is expected_candidate


def test_revision_is_never_candidate() -> None:
    result = classify_permit_signal(
        permit_number="26-040037-P01-01",
        work_description="Revision",
        status="Applied",
    )

    assert result.is_revision is True
    assert result.signal_candidate is False
    assert result.outreach_eligible is False
