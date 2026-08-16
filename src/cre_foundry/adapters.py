from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any

import httpx

from cre_foundry.models import EvidenceEvent

BRAMPTON_PERMITS_URL = (
    "https://maps1.brampton.ca/arcgis/rest/services/"
    "BuildingPermit/Building_Permits/FeatureServer/0/query"
)
BRAMPTON_ATTRIBUTION = "City of Brampton Open Data"


def stable_event_id(source_id: str, source_record_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{source_record_id}".encode()).hexdigest()[:16]
    return f"evt:{digest}"


def _date_from_epoch_ms(value: Any) -> date:
    if value is None:
        return datetime.now(UTC).date()
    return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC).date()


def fetch_brampton_permits(limit: int = 25, timeout: float = 30.0) -> list[EvidenceEvent]:
    """Fetch a bounded public sample; live network access is optional, never required for demo."""
    params = {
        "where": "SUBDESC IN ('F1: Industrial','F2: Industrial','F3: Industrial')",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": max(1, min(limit, 250)),
    }
    response = httpx.get(BRAMPTON_PERMITS_URL, params=params, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(f"ArcGIS source error: {body['error']}")

    events: list[EvidenceEvent] = []
    for idx, feature in enumerate(body.get("features", [])):
        attrs = feature.get("attributes", {})
        record_id = str(
            attrs.get("OBJECTID")
            or attrs.get("PERMITNUM")
            or attrs.get("PERMITNO")
            or idx
        )
        address = (
            attrs.get("ADDRESS")
            or attrs.get("LOCATION")
            or attrs.get("PROPADDRESS")
            or ""
        )
        raw_date = attrs.get("ISSUEDATE") or attrs.get("ISSUE_DATE") or attrs.get("ISSUED")
        amount = attrs.get("CONSTCOST") or attrs.get("VALUE") or attrs.get("COST")
        try:
            amount_value = float(amount) if amount not in (None, "") else None
        except (TypeError, ValueError):
            amount_value = None
        events.append(
            EvidenceEvent(
                event_id=stable_event_id("brampton_building_permits", record_id),
                source_id="brampton_building_permits",
                source_record_id=record_id,
                observed_at=datetime.now(UTC),
                event_date=_date_from_epoch_ms(raw_date),
                event_type="building_permit",
                account_name=None,
                address=str(address),
                city="Brampton",
                amount=amount_value,
                description=str(attrs.get("DESCRIPTION") or attrs.get("WORKDESC") or ""),
                attribution=BRAMPTON_ATTRIBUTION,
            )
        )
    return events
