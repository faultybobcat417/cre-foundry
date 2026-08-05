from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path

ALLOWED_EVENT_TYPES = {
    "task_started",
    "evidence_added",
    "task_passed",
    "task_failed",
    "task_reset",
}


@dataclass(frozen=True)
class VerificationTaskState:
    task_status: str = "not_started"
    verification_result: str = "unknown"
    gate_cleared: bool = False
    evidence_count_total: int = 0
    evidence_count_since_reset: int = 0
    latest_event_id: str | None = None
    latest_event_at: str | None = None


def control_database_path(
    project_root: Path,
) -> Path:
    return project_root / "data" / "control" / "operations.sqlite3"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_timestamp(
    value: datetime,
) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _scalar_int(
    connection: Any,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def _connect_control(
    project_root: Path,
) -> sqlite3.Connection:
    path = control_database_path(project_root)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def initialize_verification_ledger(
    project_root: Path,
) -> dict[str, Any]:
    connection = _connect_control(project_root)

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                verification_events (
                    event_sequence
                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id
                        TEXT NOT NULL UNIQUE,
                    verification_task_id
                        TEXT NOT NULL,
                    opportunity_evidence_id
                        TEXT NOT NULL,
                    permit_source_record_id
                        TEXT NOT NULL,
                    permit_number
                        TEXT NOT NULL,
                    gate_id
                        TEXT NOT NULL,
                    event_type
                        TEXT NOT NULL,
                    verification_result
                        TEXT,
                    evidence_source_type
                        TEXT,
                    evidence_reference
                        TEXT,
                    reviewer
                        TEXT,
                    notes
                        TEXT,
                    occurred_at
                        TEXT NOT NULL,
                    recorded_at
                        TEXT NOT NULL,
                    previous_event_id
                        TEXT,
                    previous_chain_hash
                        TEXT NOT NULL,
                    chain_hash
                        TEXT NOT NULL UNIQUE,
                    payload_json
                        TEXT NOT NULL,
                    CHECK (
                        event_type IN (
                            'task_started',
                            'evidence_added',
                            'task_passed',
                            'task_failed',
                            'task_reset'
                        )
                    )
                );

            CREATE INDEX IF NOT EXISTS
                idx_verification_events_task
            ON
                verification_events (
                    verification_task_id,
                    event_sequence
                );

            CREATE INDEX IF NOT EXISTS
                idx_verification_events_opportunity
            ON
                verification_events (
                    opportunity_evidence_id,
                    event_sequence
                );

            CREATE TRIGGER IF NOT EXISTS
                verification_events_block_update
            BEFORE UPDATE ON
                verification_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'verification_events is append-only'
                );
            END;

            CREATE TRIGGER IF NOT EXISTS
                verification_events_block_delete
            BEFORE DELETE ON
                verification_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'verification_events is append-only'
                );
            END;
            """
        )

        connection.commit()

        event_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM verification_events
            """,
        )

    finally:
        connection.close()

    return {
        "ledger_path": str(control_database_path(project_root).relative_to(project_root)),
        "event_count": event_count,
        "append_only": True,
    }


def reduce_task_events(
    events: list[dict[str, Any]],
) -> VerificationTaskState:
    state = VerificationTaskState()

    for event in events:
        event_type = str(event["event_type"])

        if event_type == "task_started":
            if state.task_status != "not_started":
                raise ValueError("task_started requires a not_started task.")

            state = VerificationTaskState(
                task_status="in_progress",
                verification_result="unknown",
                gate_cleared=False,
                evidence_count_total=(state.evidence_count_total),
                evidence_count_since_reset=(state.evidence_count_since_reset),
                latest_event_id=str(event["event_id"]),
                latest_event_at=str(event["occurred_at"]),
            )

        elif event_type == "evidence_added":
            if state.task_status == "completed":
                raise ValueError("Evidence cannot be added to a completed task.")

            state = VerificationTaskState(
                task_status="in_progress",
                verification_result="unknown",
                gate_cleared=False,
                evidence_count_total=(state.evidence_count_total + 1),
                evidence_count_since_reset=(state.evidence_count_since_reset + 1),
                latest_event_id=str(event["event_id"]),
                latest_event_at=str(event["occurred_at"]),
            )

        elif event_type in {
            "task_passed",
            "task_failed",
        }:
            if state.task_status != "in_progress":
                raise ValueError(f"{event_type} requires an in_progress task.")

            if state.evidence_count_since_reset < 1:
                raise ValueError(f"{event_type} requires at least one evidence event.")

            passed = event_type == "task_passed"

            state = VerificationTaskState(
                task_status="completed",
                verification_result=("pass" if passed else "fail"),
                gate_cleared=passed,
                evidence_count_total=(state.evidence_count_total),
                evidence_count_since_reset=(state.evidence_count_since_reset),
                latest_event_id=str(event["event_id"]),
                latest_event_at=str(event["occurred_at"]),
            )

        elif event_type == "task_reset":
            if state.task_status != "completed":
                raise ValueError("task_reset requires a completed task.")

            state = VerificationTaskState(
                task_status="not_started",
                verification_result="unknown",
                gate_cleared=False,
                evidence_count_total=(state.evidence_count_total),
                evidence_count_since_reset=0,
                latest_event_id=str(event["event_id"]),
                latest_event_at=str(event["occurred_at"]),
            )

        else:
            raise ValueError(f"Unsupported event type: {event_type}")

    return state


def _task_definition(
    project_root: Path,
    verification_task_id: str,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(
        str(warehouse),
        read_only=True,
    )

    try:
        row = connection.execute(
            """
            SELECT
                verification_task_id,
                opportunity_evidence_id,
                permit_source_record_id,
                permit_number,
                gate_id
            FROM
                silver.brampton_permit_verification_tasks
            WHERE
                verification_task_id = ?
            """,
            [verification_task_id],
        ).fetchone()

    finally:
        connection.close()

    if row is None:
        raise ValueError(f"Unknown verification task ID: {verification_task_id}")

    return {
        "verification_task_id": str(row[0]),
        "opportunity_evidence_id": str(row[1]),
        "permit_source_record_id": str(row[2]),
        "permit_number": str(row[3]),
        "gate_id": str(row[4]),
    }


def _canonical_event_payload(
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _chain_hash(
    previous_chain_hash: str,
    payload_json: str,
) -> str:
    return hashlib.sha256((previous_chain_hash + "\n" + payload_json).encode("utf-8")).hexdigest()


def record_verification_event(
    project_root: Path,
    *,
    verification_task_id: str,
    event_type: str,
    reviewer: str | None = None,
    evidence_source_type: str | None = None,
    evidence_reference: str | None = None,
    notes: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")

    reviewer_value = reviewer.strip() if reviewer else None

    evidence_source_value = evidence_source_type.strip() if evidence_source_type else None

    evidence_reference_value = evidence_reference.strip() if evidence_reference else None

    notes_value = notes.strip() if notes else None

    if event_type == "evidence_added":
        if not reviewer_value:
            raise ValueError("evidence_added requires a reviewer.")

        if not evidence_source_value:
            raise ValueError("evidence_added requires an evidence source type.")

        if not evidence_reference_value:
            raise ValueError("evidence_added requires an evidence reference.")

    if (
        event_type
        in {
            "task_started",
            "task_passed",
            "task_failed",
            "task_reset",
        }
        and not reviewer_value
    ):
        raise ValueError(f"{event_type} requires a reviewer.")

    if event_type == "task_reset" and not notes_value:
        raise ValueError("task_reset requires review notes.")

    initialize_verification_ledger(project_root)

    task = _task_definition(
        project_root,
        verification_task_id,
    )

    connection = _connect_control(project_root)

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing_rows = connection.execute(
            """
            SELECT
                event_id,
                event_type,
                occurred_at
            FROM
                verification_events
            WHERE
                verification_task_id = ?
            ORDER BY
                event_sequence
            """,
            [verification_task_id],
        ).fetchall()

        existing_events = [
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
            }
            for row in existing_rows
        ]

        current_state = reduce_task_events(existing_events)

        validation_event = {
            "event_id": "validation",
            "event_type": event_type,
            "occurred_at": _iso_timestamp(occurred_at or _utc_now()),
        }

        reduce_task_events(
            [
                *existing_events,
                validation_event,
            ]
        )

        if event_type in {
            "task_passed",
            "task_failed",
        } and (current_state.evidence_count_since_reset < 1):
            raise ValueError(f"{event_type} requires an evidence_added event.")

        previous_row = connection.execute(
            """
            SELECT
                event_id,
                chain_hash
            FROM
                verification_events
            WHERE
                verification_task_id = ?
            ORDER BY
                event_sequence DESC
            LIMIT 1
            """,
            [verification_task_id],
        ).fetchone()

        previous_event_id = str(previous_row["event_id"]) if previous_row is not None else None

        previous_chain_hash = (
            str(previous_row["chain_hash"]) if previous_row is not None else "GENESIS"
        )

        event_id = str(uuid.uuid4())

        occurred = _iso_timestamp(occurred_at or _utc_now())
        recorded = _iso_timestamp(_utc_now())

        verification_result = None

        if event_type == "task_passed":
            verification_result = "pass"

        elif event_type == "task_failed":
            verification_result = "fail"

        payload = {
            "event_id": event_id,
            "verification_task_id": (verification_task_id),
            "opportunity_evidence_id": (task["opportunity_evidence_id"]),
            "permit_source_record_id": (task["permit_source_record_id"]),
            "permit_number": (task["permit_number"]),
            "gate_id": task["gate_id"],
            "event_type": event_type,
            "verification_result": (verification_result),
            "evidence_source_type": (evidence_source_value),
            "evidence_reference": (evidence_reference_value),
            "reviewer": reviewer_value,
            "notes": notes_value,
            "occurred_at": occurred,
            "recorded_at": recorded,
            "previous_event_id": (previous_event_id),
            "previous_chain_hash": (previous_chain_hash),
        }

        payload_json = _canonical_event_payload(payload)

        chain_hash = _chain_hash(
            previous_chain_hash,
            payload_json,
        )

        connection.execute(
            """
            INSERT INTO
                verification_events (
                    event_id,
                    verification_task_id,
                    opportunity_evidence_id,
                    permit_source_record_id,
                    permit_number,
                    gate_id,
                    event_type,
                    verification_result,
                    evidence_source_type,
                    evidence_reference,
                    reviewer,
                    notes,
                    occurred_at,
                    recorded_at,
                    previous_event_id,
                    previous_chain_hash,
                    chain_hash,
                    payload_json
                )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                event_id,
                verification_task_id,
                task["opportunity_evidence_id"],
                task["permit_source_record_id"],
                task["permit_number"],
                task["gate_id"],
                event_type,
                verification_result,
                evidence_source_value,
                evidence_reference_value,
                reviewer_value,
                notes_value,
                occurred,
                recorded,
                previous_event_id,
                previous_chain_hash,
                chain_hash,
                payload_json,
            ],
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {
        "event_id": event_id,
        "verification_task_id": (verification_task_id),
        "event_type": event_type,
        "verification_result": (verification_result),
        "chain_hash": chain_hash,
        "append_only": True,
        "outreach_eligible": False,
    }


def _load_events(
    project_root: Path,
) -> list[dict[str, Any]]:
    initialize_verification_ledger(project_root)

    connection = _connect_control(project_root)

    try:
        rows = connection.execute(
            """
            SELECT
                event_sequence,
                event_id,
                verification_task_id,
                opportunity_evidence_id,
                permit_source_record_id,
                permit_number,
                gate_id,
                event_type,
                verification_result,
                evidence_source_type,
                evidence_reference,
                reviewer,
                notes,
                occurred_at,
                recorded_at,
                previous_event_id,
                previous_chain_hash,
                chain_hash,
                payload_json
            FROM
                verification_events
            ORDER BY
                event_sequence
            """
        ).fetchall()

    finally:
        connection.close()

    return [dict(row) for row in rows]


def _verify_event_chains(
    events: list[dict[str, Any]],
) -> int:
    previous_by_task: dict[
        str,
        tuple[str | None, str],
    ] = {}

    violations = 0

    for event in events:
        task_id = str(event["verification_task_id"])

        expected_previous_event_id: str | None
        expected_previous_hash: str

        if task_id in previous_by_task:
            (
                expected_previous_event_id,
                expected_previous_hash,
            ) = previous_by_task[task_id]

        else:
            expected_previous_event_id = None
            expected_previous_hash = "GENESIS"

        if event["previous_event_id"] != expected_previous_event_id:
            violations += 1

        if event["previous_chain_hash"] != expected_previous_hash:
            violations += 1

        payload_json = str(event["payload_json"])

        expected_chain_hash = _chain_hash(
            expected_previous_hash,
            payload_json,
        )

        if event["chain_hash"] != expected_chain_hash:
            violations += 1

        previous_by_task[task_id] = (
            str(event["event_id"]),
            str(event["chain_hash"]),
        )

    return violations


def project_verification_state(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    events = _load_events(project_root)

    chain_violation_count = _verify_event_chains(events)

    if chain_violation_count != 0:
        raise RuntimeError("Verification event-chain integrity check failed.")

    events_by_task: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for event in events:
        events_by_task[str(event["verification_task_id"])].append(event)

    connection = duckdb.connect(str(warehouse))

    transaction_active = False

    try:
        task_rows = connection.execute(
            """
            SELECT
                verification_task_id,
                opportunity_evidence_id,
                permit_source_record_id,
                permit_number,
                application_at_utc,
                event_type,
                signal_strength,
                address_raw,
                evidence_status,
                provisional_business_name,
                provisional_business_source,
                gate_id,
                task_order,
                gate_category,
                task_instruction,
                prerequisite_gate_id,
                required,
                blocking,
                queue_priority,
                workflow_priority_only
            FROM
                silver.brampton_permit_verification_tasks
            ORDER BY
                opportunity_evidence_id,
                task_order,
                gate_id
            """
        ).fetchall()

        task_definitions: list[dict[str, Any]] = []

        state_by_task: dict[
            str,
            VerificationTaskState,
        ] = {}

        task_by_opportunity_gate: dict[
            tuple[str, str],
            str,
        ] = {}

        for row in task_rows:
            task_id = str(row[0])
            opportunity_id = str(row[1])
            gate_id = str(row[11])

            definition = {
                "verification_task_id": (task_id),
                "opportunity_evidence_id": (opportunity_id),
                "permit_source_record_id": (str(row[2])),
                "permit_number": str(row[3]),
                "application_at_utc": (row[4]),
                "permit_event_type": (str(row[5])),
                "signal_strength": str(row[6]),
                "address_raw": str(row[7]),
                "evidence_status": str(row[8]),
                "provisional_business_name": (row[9]),
                "provisional_business_source": (row[10]),
                "gate_id": gate_id,
                "task_order": int(row[12]),
                "gate_category": str(row[13]),
                "task_instruction": str(row[14]),
                "prerequisite_gate_id": (str(row[15]) if row[15] is not None else None),
                "required": bool(row[16]),
                "blocking": bool(row[17]),
                "queue_priority": int(row[18]),
                "workflow_priority_only": (bool(row[19])),
            }

            task_definitions.append(definition)

            state_by_task[task_id] = reduce_task_events(
                events_by_task.get(
                    task_id,
                    [],
                )
            )

            key = (
                opportunity_id,
                gate_id,
            )

            if key in task_by_opportunity_gate:
                raise RuntimeError("Duplicate gate task within an opportunity.")

            task_by_opportunity_gate[key] = task_id

        state_rows: list[tuple[Any, ...]] = []

        for task in task_definitions:
            task_id = str(task["verification_task_id"])

            state = state_by_task[task_id]

            prerequisite_gate_id = task["prerequisite_gate_id"]

            prerequisite_task_id = None
            prerequisite_passed = False

            if prerequisite_gate_id is not None:
                prerequisite_task_id = task_by_opportunity_gate.get(
                    (
                        str(task["opportunity_evidence_id"]),
                        str(prerequisite_gate_id),
                    )
                )

                if prerequisite_task_id is None:
                    raise RuntimeError(f"Missing prerequisite task {prerequisite_gate_id}.")

                prerequisite_passed = state_by_task[prerequisite_task_id].gate_cleared

            task_ready = False
            blocked_reason = None

            if state.task_status == "completed":
                blocked_reason = "task_completed"

            elif (
                state.task_status == "in_progress"
                or prerequisite_gate_id is None
                or prerequisite_passed
            ):
                task_ready = True

            else:
                blocked_reason = "prerequisite_not_passed"

            state_rows.append(
                (
                    task_id,
                    task["opportunity_evidence_id"],
                    task["permit_source_record_id"],
                    task["permit_number"],
                    task["application_at_utc"],
                    task["permit_event_type"],
                    task["signal_strength"],
                    task["address_raw"],
                    task["evidence_status"],
                    task["provisional_business_name"],
                    task["provisional_business_source"],
                    task["gate_id"],
                    task["task_order"],
                    task["gate_category"],
                    task["task_instruction"],
                    prerequisite_gate_id,
                    prerequisite_task_id,
                    prerequisite_passed,
                    task["required"],
                    task["blocking"],
                    task["queue_priority"],
                    task["workflow_priority_only"],
                    state.task_status,
                    state.verification_result,
                    state.gate_cleared,
                    state.evidence_count_total,
                    state.evidence_count_since_reset,
                    state.latest_event_id,
                    state.latest_event_at,
                    task_ready,
                    blocked_reason,
                    False,
                    True,
                    False,
                    "shadow",
                )
            )

        workflow_groups: dict[
            str,
            list[tuple[Any, ...]],
        ] = defaultdict(list)

        for state_row in state_rows:
            workflow_groups[str(state_row[1])].append(state_row)

        workflow_rows: list[tuple[Any, ...]] = []

        for (
            opportunity_id,
            opportunity_tasks,
        ) in workflow_groups.items():
            first = opportunity_tasks[0]

            required_count = len(opportunity_tasks)

            ready_count = sum(bool(row[29]) for row in opportunity_tasks)

            in_progress_count = sum(row[22] == "in_progress" for row in opportunity_tasks)

            completed_count = sum(row[22] == "completed" for row in opportunity_tasks)

            passed_count = sum(row[23] == "pass" for row in opportunity_tasks)

            failed_count = sum(row[23] == "fail" for row in opportunity_tasks)

            all_passed = required_count > 0 and passed_count == required_count

            if failed_count > 0:
                workflow_status = "blocked_failed"

            elif all_passed:
                workflow_status = "verification_complete"

            elif in_progress_count > 0:
                workflow_status = "in_progress"

            else:
                workflow_status = "not_started"

            workflow_rows.append(
                (
                    opportunity_id,
                    first[2],
                    first[3],
                    first[4],
                    first[5],
                    first[6],
                    first[7],
                    first[8],
                    first[9],
                    first[10],
                    required_count,
                    ready_count,
                    in_progress_count,
                    completed_count,
                    passed_count,
                    failed_count,
                    workflow_status,
                    all_passed,
                    all_passed,
                    True,
                    False,
                    False,
                    "shadow",
                )
            )

        connection.execute("BEGIN")
        transaction_active = True

        connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS control
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                control.brampton_verification_events (
                    event_sequence BIGINT,
                    event_id VARCHAR,
                    verification_task_id VARCHAR,
                    opportunity_evidence_id VARCHAR,
                    permit_source_record_id VARCHAR,
                    permit_number VARCHAR,
                    gate_id VARCHAR,
                    event_type VARCHAR,
                    verification_result VARCHAR,
                    evidence_source_type VARCHAR,
                    evidence_reference VARCHAR,
                    reviewer VARCHAR,
                    notes VARCHAR,
                    occurred_at TIMESTAMPTZ,
                    recorded_at TIMESTAMPTZ,
                    previous_event_id VARCHAR,
                    previous_chain_hash VARCHAR,
                    chain_hash VARCHAR,
                    payload_json VARCHAR
                )
            """
        )

        if events:
            connection.executemany(
                """
                INSERT INTO
                    control.brampton_verification_events
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    (
                        event["event_sequence"],
                        event["event_id"],
                        event["verification_task_id"],
                        event["opportunity_evidence_id"],
                        event["permit_source_record_id"],
                        event["permit_number"],
                        event["gate_id"],
                        event["event_type"],
                        event["verification_result"],
                        event["evidence_source_type"],
                        event["evidence_reference"],
                        event["reviewer"],
                        event["notes"],
                        event["occurred_at"],
                        event["recorded_at"],
                        event["previous_event_id"],
                        event["previous_chain_hash"],
                        event["chain_hash"],
                        event["payload_json"],
                    )
                    for event in events
                ],
            )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                control.brampton_verification_task_state (
                    verification_task_id VARCHAR,
                    opportunity_evidence_id VARCHAR,
                    permit_source_record_id VARCHAR,
                    permit_number VARCHAR,
                    application_at_utc TIMESTAMPTZ,
                    permit_event_type VARCHAR,
                    signal_strength VARCHAR,
                    address_raw VARCHAR,
                    evidence_status VARCHAR,
                    provisional_business_name VARCHAR,
                    provisional_business_source VARCHAR,
                    gate_id VARCHAR,
                    task_order INTEGER,
                    gate_category VARCHAR,
                    task_instruction VARCHAR,
                    prerequisite_gate_id VARCHAR,
                    prerequisite_task_id VARCHAR,
                    prerequisite_passed BOOLEAN,
                    required BOOLEAN,
                    blocking BOOLEAN,
                    queue_priority INTEGER,
                    workflow_priority_only BOOLEAN,
                    task_status VARCHAR,
                    verification_result VARCHAR,
                    gate_cleared BOOLEAN,
                    evidence_count_total INTEGER,
                    evidence_count_since_reset INTEGER,
                    latest_event_id VARCHAR,
                    latest_event_at TIMESTAMPTZ,
                    task_ready BOOLEAN,
                    blocked_reason VARCHAR,
                    opportunity_ranked BOOLEAN,
                    outreach_authorization_required BOOLEAN,
                    outreach_eligible BOOLEAN,
                    operating_mode VARCHAR
                )
            """
        )

        if state_rows:
            placeholders = ", ".join(["?"] * 35)

            connection.executemany(
                f"""
                INSERT INTO
                    control.brampton_verification_task_state
                VALUES ({placeholders})
                """,
                state_rows,
            )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                control.brampton_verification_workflow_state (
                    opportunity_evidence_id VARCHAR,
                    permit_source_record_id VARCHAR,
                    permit_number VARCHAR,
                    application_at_utc TIMESTAMPTZ,
                    permit_event_type VARCHAR,
                    signal_strength VARCHAR,
                    address_raw VARCHAR,
                    evidence_status VARCHAR,
                    provisional_business_name VARCHAR,
                    provisional_business_source VARCHAR,
                    required_task_count INTEGER,
                    ready_task_count INTEGER,
                    in_progress_task_count INTEGER,
                    completed_task_count INTEGER,
                    passed_task_count INTEGER,
                    failed_task_count INTEGER,
                    workflow_status VARCHAR,
                    all_required_tasks_passed BOOLEAN,
                    verification_complete BOOLEAN,
                    outreach_authorization_required BOOLEAN,
                    opportunity_ranked BOOLEAN,
                    outreach_eligible BOOLEAN,
                    operating_mode VARCHAR
                )
            """
        )

        if workflow_rows:
            placeholders = ", ".join(["?"] * 23)

            connection.executemany(
                f"""
                INSERT INTO
                    control.brampton_verification_workflow_state
                VALUES ({placeholders})
                """,
                workflow_rows,
            )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                control.brampton_verification_active_queue
            AS
            SELECT *
            FROM
                control.brampton_verification_task_state
            WHERE
                task_ready
                AND task_status
                    IN (
                        'not_started',
                        'in_progress'
                    )
            ORDER BY
                queue_priority,
                application_at_utc DESC,
                permit_number,
                task_order
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                control.brampton_verification_state_summary
            AS
            SELECT
                gate_id,
                task_status,
                verification_result,
                count(*) AS tasks,
                count(*) FILTER (
                    WHERE task_ready
                ) AS ready_tasks,
                count(*) FILTER (
                    WHERE gate_cleared
                ) AS cleared_tasks
            FROM
                control.brampton_verification_task_state
            GROUP BY
                gate_id,
                task_status,
                verification_result
            """
        )

        event_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM
                control.brampton_verification_events
            """,
        )

        task_state_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM
                control.brampton_verification_task_state
            """,
        )

        workflow_state_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM
                control.brampton_verification_workflow_state
            """,
        )

        ready_task_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM
                control.brampton_verification_active_queue
            """,
        )

        completed_task_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM
                control.brampton_verification_task_state
            WHERE
                task_status = 'completed'
            """,
        )

        failed_task_count = _scalar_int(
            connection,
            """
            SELECT count(*)
            FROM
                control.brampton_verification_task_state
            WHERE
                verification_result = 'fail'
            """,
        )

        outreach_eligible_count = _scalar_int(
            connection,
            """
            SELECT
                (
                    SELECT count(*)
                    FROM
                        control.brampton_verification_task_state
                    WHERE outreach_eligible
                )
                +
                (
                    SELECT count(*)
                    FROM
                        control.brampton_verification_workflow_state
                    WHERE outreach_eligible
                )
            """,
        )

        connection.execute("COMMIT")
        transaction_active = False

    except Exception:
        if transaction_active:
            connection.execute("ROLLBACK")

        raise

    finally:
        connection.close()

    if event_count != len(events):
        raise RuntimeError("Verification event projection count mismatch.")

    if task_state_count != len(task_rows):
        raise RuntimeError("Verification task-state count mismatch.")

    if workflow_state_count != len(workflow_groups):
        raise RuntimeError("Verification workflow-state count mismatch.")

    if outreach_eligible_count != 0:
        raise RuntimeError("Verification state projection enabled outreach.")

    report: dict[str, Any] = {
        "model_version": ("brampton-verification-ledger-v1"),
        "ledger_path": str(control_database_path(project_root).relative_to(project_root)),
        "ledger_event_count": event_count,
        "event_chain_violation_count": (chain_violation_count),
        "task_state_count": (task_state_count),
        "workflow_state_count": (workflow_state_count),
        "ready_task_count": (ready_task_count),
        "completed_task_count": (completed_task_count),
        "failed_task_count": (failed_task_count),
        "outreach_eligible_count": (outreach_eligible_count),
        "event_projection_table": ("control.brampton_verification_events"),
        "task_state_table": ("control.brampton_verification_task_state"),
        "workflow_state_table": ("control.brampton_verification_workflow_state"),
        "active_queue_view": ("control.brampton_verification_active_queue"),
        "summary_view": ("control.brampton_verification_state_summary"),
        "policy": {
            "event_ledger_append_only": True,
            "event_chain_enabled": True,
            "source_tables_overwritten": False,
            "automatic_gate_clearance": False,
            "outreach_authorization_required": (True),
            "opportunity_ranked": False,
            "outreach_eligible": False,
            "operating_mode": "shadow",
        },
    }

    contract_path = project_root / "docs" / "data_contracts" / "brampton_verification_ledger.json"

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
