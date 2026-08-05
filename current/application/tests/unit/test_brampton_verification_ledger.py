from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from cre_foundry.brampton_verification_ledger import (
    control_database_path,
    initialize_verification_ledger,
    project_verification_state,
    record_verification_event,
)


def create_fixture(
    tmp_path: Path,
) -> Path:
    warehouse = tmp_path / "data" / "warehouse" / "fixture.duckdb"

    warehouse.parent.mkdir(parents=True)

    connection = duckdb.connect(str(warehouse))

    as_of = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    connection.execute(
        """
        CREATE SCHEMA silver
        """
    )

    connection.execute(
        """
        CREATE TABLE
            silver.brampton_permit_verification_tasks (
                verification_task_id VARCHAR,
                opportunity_evidence_id VARCHAR,
                permit_source_record_id VARCHAR,
                permit_number VARCHAR,
                application_at_utc TIMESTAMPTZ,
                event_type VARCHAR,
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
                required BOOLEAN,
                blocking BOOLEAN,
                queue_priority INTEGER,
                workflow_priority_only BOOLEAN
            )
        """
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_verification_tasks
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                "opportunity:1:evidence_resolution",
                "opportunity:1",
                "permit:1",
                "P-1",
                as_of,
                "tenant_fitout",
                "high",
                "1 Test Rd",
                "unresolved",
                None,
                None,
                "evidence_resolution",
                0,
                "resolution",
                "Resolve identity evidence.",
                None,
                True,
                True,
                0,
                True,
            ),
            (
                "opportunity:1:identity_verification",
                "opportunity:1",
                "permit:1",
                "P-1",
                as_of,
                "tenant_fitout",
                "high",
                "1 Test Rd",
                "unresolved",
                None,
                None,
                "identity_verification",
                1,
                "identity",
                "Verify identity.",
                "evidence_resolution",
                True,
                True,
                1,
                True,
            ),
            (
                "opportunity:1:permit_occupancy_verification",
                "opportunity:1",
                "permit:1",
                "P-1",
                as_of,
                "tenant_fitout",
                "high",
                "1 Test Rd",
                "unresolved",
                None,
                None,
                "permit_occupancy_verification",
                2,
                "occupancy",
                "Verify occupancy.",
                "identity_verification",
                True,
                True,
                2,
                True,
            ),
        ],
    )

    connection.close()

    return warehouse


def test_initializes_and_projects_zero_event_state(
    tmp_path: Path,
) -> None:
    create_fixture(tmp_path)

    ledger = initialize_verification_ledger(tmp_path)

    assert ledger["event_count"] == 0
    assert ledger["append_only"] is True

    report = project_verification_state(tmp_path)

    assert report["ledger_event_count"] == 0
    assert report["task_state_count"] == 3
    assert report["workflow_state_count"] == 1
    assert report["ready_task_count"] == 1
    assert report["outreach_eligible_count"] == 0

    connection = duckdb.connect(
        str(tmp_path / "data" / "warehouse" / "fixture.duckdb"),
        read_only=True,
    )

    try:
        queue = connection.execute(
            """
            SELECT
                gate_id,
                task_status,
                task_ready,
                outreach_eligible
            FROM
                control.brampton_verification_active_queue
            """
        ).fetchall()

    finally:
        connection.close()

    assert queue == [
        (
            "evidence_resolution",
            "not_started",
            True,
            False,
        )
    ]


def test_records_events_and_unlocks_prerequisite(
    tmp_path: Path,
) -> None:
    create_fixture(tmp_path)

    task_id = "opportunity:1:evidence_resolution"

    record_verification_event(
        tmp_path,
        verification_task_id=task_id,
        event_type="task_started",
        reviewer="analyst@example.test",
    )

    record_verification_event(
        tmp_path,
        verification_task_id=task_id,
        event_type="evidence_added",
        reviewer="analyst@example.test",
        evidence_source_type="official_registry",
        evidence_reference="registry:test-1",
        notes="Identity evidence reviewed.",
    )

    record_verification_event(
        tmp_path,
        verification_task_id=task_id,
        event_type="task_passed",
        reviewer="analyst@example.test",
        notes="Evidence conflict resolved.",
    )

    report = project_verification_state(tmp_path)

    assert report["ledger_event_count"] == 3
    assert report["completed_task_count"] == 1
    assert report["ready_task_count"] == 1
    assert report["outreach_eligible_count"] == 0

    connection = duckdb.connect(
        str(tmp_path / "data" / "warehouse" / "fixture.duckdb"),
        read_only=True,
    )

    try:
        queue = connection.execute(
            """
            SELECT
                gate_id,
                prerequisite_passed,
                task_status,
                task_ready
            FROM
                control.brampton_verification_active_queue
            """
        ).fetchall()

    finally:
        connection.close()

    assert queue == [
        (
            "identity_verification",
            True,
            "not_started",
            True,
        )
    ]


def test_rejects_invalid_transition_and_mutation(
    tmp_path: Path,
) -> None:
    create_fixture(tmp_path)

    task_id = "opportunity:1:evidence_resolution"

    with pytest.raises(
        ValueError,
        match="in_progress",
    ):
        record_verification_event(
            tmp_path,
            verification_task_id=task_id,
            event_type="task_passed",
            reviewer="analyst@example.test",
        )

    record_verification_event(
        tmp_path,
        verification_task_id=task_id,
        event_type="task_started",
        reviewer="analyst@example.test",
    )

    database = sqlite3.connect(control_database_path(tmp_path))

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="append-only",
        ):
            database.execute(
                """
                UPDATE verification_events
                SET notes = 'changed'
                """
            )

    finally:
        database.close()
