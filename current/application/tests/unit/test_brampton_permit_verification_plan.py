from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cre_foundry.brampton_permit_verification_plan import (
    build_brampton_permit_verification_plan,
)


def test_builds_initial_verification_plan(
    tmp_path: Path,
) -> None:
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
            silver.brampton_permit_opportunity_evidence (
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
                high_information_review_required BOOLEAN,
                unresolved_research_required BOOLEAN,
                manual_resolution_required BOOLEAN,
                operating_mode VARCHAR,
                ranked BOOLEAN,
                outreach_eligible BOOLEAN
            )
        """
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_opportunity_evidence
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                "opportunity:1",
                "permit:1",
                "P-1",
                as_of,
                "building_addition",
                "high",
                "1 Test Rd",
                "cross_source_corroborated",
                "Business One",
                "current_brampton_directory",
                False,
                False,
                False,
                "shadow",
                False,
                False,
            ),
            (
                "opportunity:2",
                "permit:2",
                "P-2",
                as_of,
                "alteration",
                "medium",
                "2 Test Rd",
                "cross_source_conflict",
                "Business Two",
                "current_brampton_directory",
                True,
                False,
                True,
                "shadow",
                False,
                False,
            ),
            (
                "opportunity:3",
                "permit:3",
                "P-3",
                as_of,
                "tenant_fitout",
                "high",
                "3 Test Rd",
                "unresolved",
                None,
                None,
                False,
                True,
                True,
                "shadow",
                False,
                False,
            ),
        ],
    )

    connection.close()

    report = build_brampton_permit_verification_plan(tmp_path)

    assert report["opportunity_count"] == 3
    assert report["manual_resolution_opportunity_count"] == 2
    assert report["verification_task_count"] == 32
    assert report["evidence_resolution_task_count"] == 2
    assert report["initial_ready_task_count"] == 3
    assert report["initial_completed_task_count"] == 0
    assert report["safety_violation_count"] == 0

    connection = duckdb.connect(
        str(warehouse),
        read_only=True,
    )

    try:
        ready_tasks = connection.execute(
            """
            SELECT
                permit_number,
                gate_id,
                task_ready,
                task_status,
                verification_result,
                opportunity_ranked,
                outreach_eligible
            FROM
                silver.brampton_permit_verification_queue
            ORDER BY
                permit_number
            """
        ).fetchall()

        workflow_rows = connection.execute(
            """
            SELECT
                permit_number,
                required_task_count,
                ready_task_count,
                completed_task_count,
                all_required_tasks_passed,
                outreach_eligible
            FROM
                silver.brampton_permit_verification_workflow
            ORDER BY
                permit_number
            """
        ).fetchall()

    finally:
        connection.close()

    assert ready_tasks == [
        (
            "P-1",
            "identity_verification",
            True,
            "not_started",
            "unknown",
            False,
            False,
        ),
        (
            "P-2",
            "evidence_resolution",
            True,
            "not_started",
            "unknown",
            False,
            False,
        ),
        (
            "P-3",
            "evidence_resolution",
            True,
            "not_started",
            "unknown",
            False,
            False,
        ),
    ]

    assert workflow_rows == [
        (
            "P-1",
            10,
            1,
            0,
            False,
            False,
        ),
        (
            "P-2",
            11,
            1,
            0,
            False,
            False,
        ),
        (
            "P-3",
            11,
            1,
            0,
            False,
            False,
        ),
    ]
