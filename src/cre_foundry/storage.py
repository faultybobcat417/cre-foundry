from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cre_foundry.models import EvidenceEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_events (
  event_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  event_date TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_source_record
  ON evidence_events(source_id, source_record_id);
"""


class EvidenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    def put(self, event: EvidenceEvent) -> None:
        payload = event.model_dump(mode="json")
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_events
                (event_id, source_id, source_record_id, observed_at, event_date, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.source_id,
                    event.source_record_id,
                    event.observed_at.isoformat(),
                    event.event_date.isoformat(),
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def count(self) -> int:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM evidence_events").fetchone()
            return int(row[0]) if row else 0
