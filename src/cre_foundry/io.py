from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from cre_foundry.models import Business, EvidenceEvent


def load_businesses(path: Path) -> list[Business]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [Business(**row) for row in csv.DictReader(handle)]


def load_events(path: Path) -> list[EvidenceEvent]:
    rows: list[EvidenceEvent] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            amount = row.get("amount", "").strip()
            rows.append(
                EvidenceEvent(
                    event_id=row["event_id"],
                    source_id=row["source_id"],
                    source_record_id=row["source_record_id"],
                    observed_at=datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")),
                    event_date=row["event_date"],
                    event_type=row["event_type"],
                    account_name=row.get("account_name") or None,
                    address=row.get("address") or None,
                    city=row.get("city") or None,
                    amount=float(amount) if amount else None,
                    description=row.get("description", ""),
                    attribution=row.get("attribution", ""),
                )
            )
    return rows
