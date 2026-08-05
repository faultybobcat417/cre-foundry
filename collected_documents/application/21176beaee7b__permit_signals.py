from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PermitSignalClassification:
    event_type: str
    signal_strength: str
    lifecycle_stage: str
    is_revision: bool
    signal_candidate: bool
    outreach_eligible: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _is_revision(
    permit_number: str | None,
    work_description: str | None,
) -> bool:
    number = permit_number or ""
    work = _normalize(work_description)

    return (
        "revision" in work
        or re.search(
            r"-p\d{2}-\d{2}$",
            number,
            flags=re.IGNORECASE,
        )
        is not None
    )


def classify_event_type(
    permit_number: str | None,
    work_description: str | None,
) -> str:
    work = _normalize(work_description)

    if _is_revision(
        permit_number,
        work_description,
    ):
        return "revision"

    if any(
        phrase in work
        for phrase in (
            "new building",
            "new industrial",
            "new construction",
            "construct new",
        )
    ):
        return "new_construction"

    if "addition" in work:
        return "building_addition"

    if "change of use" in work:
        return "change_of_use"

    if any(
        phrase in work
        for phrase in (
            "interior/unit finish",
            "interior unit finish",
            "unit finish",
            "tenant finish",
            "tenant improvement",
            "tenant alteration",
            "interior finish",
        )
    ):
        return "tenant_fitout"

    if any(
        phrase in work
        for phrase in (
            "alteration",
            "renovation",
        )
    ):
        return "alteration"

    if "demolition" in work:
        return "demolition"

    if any(
        phrase in work
        for phrase in (
            "sprinkler",
            "fire alarm",
            "hvac",
            "plumbing",
        )
    ):
        return "building_system"

    return "other"


def classify_lifecycle_stage(
    status: str | None,
) -> str:
    normalized = _normalize(status)

    stages = {
        "applied": "application",
        "zoning certified": "zoning_certified",
        "ready to issue": "ready_to_issue",
        "issued": "issued",
        "occupancy granted": "occupancy_granted",
        "closed": "closed",
        "cancelled": "cancelled",
        "revoked": "revoked",
        "deemed abandoned": "deemed_abandoned",
    }

    return stages.get(
        normalized,
        "unknown",
    )


def classify_permit_signal(
    *,
    permit_number: str | None,
    work_description: str | None,
    status: str | None,
) -> PermitSignalClassification:
    event_type = classify_event_type(
        permit_number,
        work_description,
    )

    lifecycle_stage = classify_lifecycle_stage(status)

    strength_by_event = {
        "new_construction": "high",
        "building_addition": "high",
        "change_of_use": "high",
        "tenant_fitout": "high",
        "alteration": "medium",
        "building_system": "medium",
        "demolition": "review",
        "revision": "review",
        "other": "review",
    }

    signal_strength = strength_by_event[event_type]

    active_stages = {
        "application",
        "zoning_certified",
        "ready_to_issue",
        "issued",
    }

    signal_candidate = (
        lifecycle_stage in active_stages
        and signal_strength in {"high", "medium"}
        and event_type != "revision"
    )

    return PermitSignalClassification(
        event_type=event_type,
        signal_strength=signal_strength,
        lifecycle_stage=lifecycle_stage,
        is_revision=(event_type == "revision"),
        signal_candidate=signal_candidate,
        outreach_eligible=False,
    )
