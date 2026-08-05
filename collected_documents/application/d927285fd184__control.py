from __future__ import annotations

import json
import os
import socket
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from cre_foundry.scheduling import (
    CadenceDecision,
    calculate_cadence,
)
from cre_foundry.source_contracts import (
    BulkFileSourceConfig,
    SourceConfig,
)


class SourceLockedError(RuntimeError):
    """Raised when a source already has a live lock."""


SchemaState = Literal[
    "baseline",
    "unchanged",
    "changed",
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ControlDatabase:
    """Persistent operational state for source pipelines."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_registry (
                    source_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    access_state TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    base_cadence_minutes INTEGER NOT NULL,
                    minimum_cadence_minutes INTEGER NOT NULL,
                    maximum_cadence_minutes INTEGER NOT NULL,
                    critical_source INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_runs (
                    run_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'running',
                            'succeeded',
                            'failed'
                        )
                    ),
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    as_of_timestamp TEXT NOT NULL,
                    records_observed INTEGER,
                    bytes_written INTEGER,
                    schema_changed INTEGER,
                    manifest_path TEXT,
                    metadata_json TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    host_name TEXT NOT NULL,
                    process_id INTEGER NOT NULL,
                    FOREIGN KEY (source_id)
                        REFERENCES source_registry(source_id)
                );

                CREATE INDEX IF NOT EXISTS
                    idx_source_runs_source_started
                ON source_runs (
                    source_id,
                    started_at DESC
                );

                CREATE TABLE IF NOT EXISTS source_locks (
                    source_id TEXT PRIMARY KEY,
                    owner_token TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (source_id)
                        REFERENCES source_registry(source_id)
                );

                CREATE TABLE IF NOT EXISTS source_health (
                    source_id TEXT PRIMARY KEY,
                    last_attempt_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    last_change_at TEXT,
                    consecutive_successes INTEGER NOT NULL,
                    consecutive_failures INTEGER NOT NULL,
                    consecutive_no_change INTEGER NOT NULL,
                    current_cadence_minutes INTEGER NOT NULL,
                    next_due_at TEXT,
                    health_status TEXT NOT NULL,
                    last_error_type TEXT,
                    last_error_message TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_id)
                        REFERENCES source_registry(source_id)
                );

                CREATE TABLE IF NOT EXISTS
                    source_schema_versions (
                        source_id TEXT NOT NULL,
                        layer_key TEXT NOT NULL,
                        schema_fingerprint TEXT NOT NULL,
                        first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL,
                        is_current INTEGER NOT NULL,
                        metadata_json TEXT NOT NULL,
                        PRIMARY KEY (
                            source_id,
                            layer_key,
                            schema_fingerprint
                        ),
                        FOREIGN KEY (source_id)
                            REFERENCES source_registry(source_id)
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_schema_current
                ON source_schema_versions (
                    source_id,
                    layer_key,
                    is_current
                );
                """
            )

    def register_source(
        self,
        config: SourceConfig | BulkFileSourceConfig,
    ) -> None:
        now = iso_timestamp(utc_now())

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_registry (
                    source_id,
                    name,
                    access_state,
                    enabled,
                    base_cadence_minutes,
                    minimum_cadence_minutes,
                    maximum_cadence_minutes,
                    critical_source,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    name = excluded.name,
                    access_state = excluded.access_state,
                    enabled = excluded.enabled,
                    base_cadence_minutes =
                        excluded.base_cadence_minutes,
                    minimum_cadence_minutes =
                        excluded.minimum_cadence_minutes,
                    maximum_cadence_minutes =
                        excluded.maximum_cadence_minutes,
                    critical_source =
                        excluded.critical_source,
                    updated_at = excluded.updated_at
                """,
                (
                    config.source_id,
                    config.name,
                    config.access_state,
                    int(config.enabled),
                    config.base_cadence_minutes,
                    config.minimum_cadence_minutes,
                    config.maximum_cadence_minutes,
                    int(config.critical_source),
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                INSERT INTO source_health (
                    source_id,
                    consecutive_successes,
                    consecutive_failures,
                    consecutive_no_change,
                    current_cadence_minutes,
                    health_status,
                    updated_at
                )
                VALUES (?, 0, 0, 0, ?, 'healthy', ?)
                ON CONFLICT(source_id) DO NOTHING
                """,
                (
                    config.source_id,
                    config.base_cadence_minutes,
                    now,
                ),
            )

    @contextmanager
    def source_lock(
        self,
        source_id: str,
        *,
        ttl_minutes: int = 30,
    ) -> Iterator[str]:
        now = utc_now()
        owner_token = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:10]}"

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                DELETE FROM source_locks
                WHERE expires_at <= ?
                """,
                (iso_timestamp(now),),
            )

            existing = connection.execute(
                """
                SELECT owner_token, expires_at
                FROM source_locks
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()

            if existing is not None:
                connection.rollback()
                raise SourceLockedError(
                    f"Source {source_id} is locked "
                    f"by {existing['owner_token']} "
                    f"until {existing['expires_at']}."
                )

            connection.execute(
                """
                INSERT INTO source_locks (
                    source_id,
                    owner_token,
                    acquired_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    source_id,
                    owner_token,
                    iso_timestamp(now),
                    iso_timestamp(now + timedelta(minutes=ttl_minutes)),
                ),
            )

            connection.commit()

        try:
            yield owner_token
        finally:
            with self.connect() as connection:
                connection.execute(
                    """
                    DELETE FROM source_locks
                    WHERE source_id = ?
                      AND owner_token = ?
                    """,
                    (
                        source_id,
                        owner_token,
                    ),
                )

    def start_run(
        self,
        *,
        source_id: str,
        run_type: str,
        as_of_timestamp: datetime,
    ) -> str:
        started_at = utc_now()
        run_id = f"RUN-{started_at:%Y%m%dT%H%M%SZ}-{uuid4().hex[:10]}"

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_runs (
                    run_id,
                    source_id,
                    run_type,
                    status,
                    started_at,
                    as_of_timestamp,
                    host_name,
                    process_id
                )
                VALUES (?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    run_type,
                    iso_timestamp(started_at),
                    iso_timestamp(as_of_timestamp),
                    socket.gethostname(),
                    os.getpid(),
                ),
            )

        return run_id

    def complete_run(
        self,
        *,
        run_id: str,
        records_observed: int,
        schema_changed: bool,
        metadata: dict[str, Any],
        bytes_written: int = 0,
        manifest_path: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE source_runs
                SET status = 'succeeded',
                    completed_at = ?,
                    records_observed = ?,
                    bytes_written = ?,
                    schema_changed = ?,
                    manifest_path = ?,
                    metadata_json = ?
                WHERE run_id = ?
                """,
                (
                    iso_timestamp(utc_now()),
                    records_observed,
                    bytes_written,
                    int(schema_changed),
                    manifest_path,
                    json.dumps(
                        metadata,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    run_id,
                ),
            )

    def fail_run(
        self,
        *,
        run_id: str,
        error: Exception,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE source_runs
                SET status = 'failed',
                    completed_at = ?,
                    error_type = ?,
                    error_message = ?
                WHERE run_id = ?
                """,
                (
                    iso_timestamp(utc_now()),
                    type(error).__name__,
                    str(error),
                    run_id,
                ),
            )

    def record_schema(
        self,
        *,
        source_id: str,
        layer_key: str,
        fingerprint: str,
        metadata: dict[str, Any],
        observed_at: datetime,
    ) -> SchemaState:
        observed = iso_timestamp(observed_at)
        serialized = json.dumps(
            metadata,
            sort_keys=True,
            separators=(",", ":"),
        )

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            current = connection.execute(
                """
                SELECT schema_fingerprint
                FROM source_schema_versions
                WHERE source_id = ?
                  AND layer_key = ?
                  AND is_current = 1
                """,
                (
                    source_id,
                    layer_key,
                ),
            ).fetchone()

            if current is None:
                state: SchemaState = "baseline"

            elif current["schema_fingerprint"] == fingerprint:
                connection.execute(
                    """
                    UPDATE source_schema_versions
                    SET last_seen_at = ?,
                        metadata_json = ?
                    WHERE source_id = ?
                      AND layer_key = ?
                      AND schema_fingerprint = ?
                    """,
                    (
                        observed,
                        serialized,
                        source_id,
                        layer_key,
                        fingerprint,
                    ),
                )
                connection.commit()
                return "unchanged"

            else:
                state = "changed"
                connection.execute(
                    """
                    UPDATE source_schema_versions
                    SET is_current = 0
                    WHERE source_id = ?
                      AND layer_key = ?
                      AND is_current = 1
                    """,
                    (
                        source_id,
                        layer_key,
                    ),
                )

            connection.execute(
                """
                INSERT INTO source_schema_versions (
                    source_id,
                    layer_key,
                    schema_fingerprint,
                    first_seen_at,
                    last_seen_at,
                    is_current,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    source_id,
                    layer_key,
                    fingerprint,
                    observed,
                    observed,
                    serialized,
                ),
            )

            connection.commit()
            return state

    def update_health(
        self,
        *,
        source_id: str,
        success: bool,
        changed: bool,
        error: Exception | None = None,
        now: datetime | None = None,
    ) -> CadenceDecision:
        observed_at = now or utc_now()

        with self.connect() as connection:
            registry = connection.execute(
                """
                SELECT
                    base_cadence_minutes,
                    minimum_cadence_minutes,
                    maximum_cadence_minutes
                FROM source_registry
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()

            health = connection.execute(
                """
                SELECT *
                FROM source_health
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()

            if registry is None or health is None:
                raise RuntimeError(f"Source {source_id} is not registered.")

            decision = calculate_cadence(
                now=observed_at,
                success=success,
                changed=changed,
                base_minutes=registry["base_cadence_minutes"],
                minimum_minutes=registry["minimum_cadence_minutes"],
                maximum_minutes=registry["maximum_cadence_minutes"],
                current_minutes=health["current_cadence_minutes"],
                no_change_streak=health["consecutive_no_change"],
                failure_streak=health["consecutive_failures"],
            )

            consecutive_successes = health["consecutive_successes"] + 1 if success else 0

            last_success_at = iso_timestamp(observed_at) if success else health["last_success_at"]

            last_failure_at = (
                iso_timestamp(observed_at) if not success else health["last_failure_at"]
            )

            last_change_at = (
                iso_timestamp(observed_at) if success and changed else health["last_change_at"]
            )

            connection.execute(
                """
                UPDATE source_health
                SET last_attempt_at = ?,
                    last_success_at = ?,
                    last_failure_at = ?,
                    last_change_at = ?,
                    consecutive_successes = ?,
                    consecutive_failures = ?,
                    consecutive_no_change = ?,
                    current_cadence_minutes = ?,
                    next_due_at = ?,
                    health_status = ?,
                    last_error_type = ?,
                    last_error_message = ?,
                    updated_at = ?
                WHERE source_id = ?
                """,
                (
                    iso_timestamp(observed_at),
                    last_success_at,
                    last_failure_at,
                    last_change_at,
                    consecutive_successes,
                    decision.consecutive_failures,
                    decision.consecutive_no_change,
                    decision.cadence_minutes,
                    iso_timestamp(decision.next_due_at),
                    decision.health_status,
                    (type(error).__name__ if error is not None else None),
                    (str(error) if error is not None else None),
                    iso_timestamp(observed_at),
                    source_id,
                ),
            )

        return decision

    def source_status(
        self,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    registry.source_id,
                    registry.name,
                    registry.access_state,
                    registry.enabled,
                    health.health_status,
                    health.last_attempt_at,
                    health.last_success_at,
                    health.last_failure_at,
                    health.consecutive_failures,
                    health.consecutive_no_change,
                    health.current_cadence_minutes,
                    health.next_due_at
                FROM source_registry AS registry
                JOIN source_health AS health
                  ON health.source_id =
                     registry.source_id
                ORDER BY registry.source_id
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def recent_runs(
        self,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    run_id,
                    source_id,
                    run_type,
                    status,
                    started_at,
                    completed_at,
                    records_observed,
                    schema_changed,
                    error_type
                FROM source_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]
