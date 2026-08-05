from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cre_foundry.brampton_verification_review_packets import (
    GATE_CHECKLISTS,
    build_brampton_verification_review_packets,
)


def _create_fixture(
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
        CREATE SCHEMA control
        """
    )

    connection.execute(
        """
        CREATE SCHEMA silver
        """
    )

    connection.execute(
        """
        CREATE TABLE
            control.brampton_verification_active_queue (
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
                task_ready BOOLEAN,
                outreach_authorization_required BOOLEAN,
                opportunity_ranked BOOLEAN,
                outreach_eligible BOOLEAN,
                operating_mode VARCHAR
            )
        """
    )

    connection.execute(
        """
        CREATE TABLE
            control.brampton_verification_events (
                event_id VARCHAR
            )
        """
    )

    connection.execute(
        """
        CREATE TABLE
            silver.brampton_permit_opportunity_evidence (
                opportunity_evidence_id VARCHAR,
                reconciliation_class VARCHAR,
                reconciliation_state VARCHAR,
                historical_candidate_names_json VARCHAR,
                current_candidate_names_json VARCHAR,
                name_similarity DOUBLE,
                directory_global_id VARCHAR,
                current_directory_naics_2 VARCHAR,
                current_directory_naics_6 VARCHAR,
                current_directory_employee_group VARCHAR,
                current_directory_phone_present BOOLEAN,
                current_directory_website_present BOOLEAN,
                high_information_review_required BOOLEAN,
                unresolved_research_required BOOLEAN,
                manual_resolution_required BOOLEAN
            )
        """
    )

    connection.execute(
        """
        INSERT INTO
            control.brampton_verification_active_queue
        VALUES (
            'opportunity:1:identity_verification',
            'opportunity:1',
            'permit:1',
            'P-1',
            ?,
            'building_addition',
            'high',
            '1 Test Rd',
            'cross_source_corroborated',
            'Business One',
            'current_brampton_directory',
            'identity_verification',
            1,
            'identity',
            'Verify the current business identity.',
            NULL,
            NULL,
            false,
            true,
            true,
            21,
            true,
            'not_started',
            'unknown',
            false,
            0,
            0,
            true,
            true,
            false,
            false,
            'shadow'
        )
        """,
        [as_of],
    )

    connection.execute(
        """
        INSERT INTO
            silver.brampton_permit_opportunity_evidence
        VALUES (
            'opportunity:1',
            'both_unique_name_exact',
            'corroborated_name_agreement',
            '["Business One Inc."]',
            '["Business One"]',
            100.0,
            '{G-1}',
            'Manufacturing',
            '311111',
            '10-19',
            true,
            true,
            false,
            false,
            false
        )
        """
    )

    connection.close()

    return warehouse


def test_defines_checklists_for_every_gate() -> None:
    expected_gates = {
        "evidence_resolution",
        "identity_verification",
        "permit_occupancy_verification",
        "commercial_requirement_verification",
        "decision_maker_verification",
        "existing_client_exclusion",
        "protected_relationship_check",
        "active_assignment_conflict_check",
        "territory_restriction_check",
        "relationship_owner_check",
        "do_not_contact_check",
    }

    assert set(GATE_CHECKLISTS) == expected_gates

    assert all(GATE_CHECKLISTS[gate] for gate in expected_gates)


def test_exports_packet_without_changing_state(
    tmp_path: Path,
) -> None:
    warehouse = _create_fixture(tmp_path)

    generated_at = datetime(
        2026,
        7,
        26,
        1,
        30,
        tzinfo=UTC,
    )

    report = build_brampton_verification_review_packets(
        tmp_path,
        generated_at=generated_at,
    )

    assert report["projected_event_count"] == 0
    assert report["active_queue_count"] == 1
    assert report["packet_count"] == 1
    assert report["json_packet_count"] == 1
    assert report["markdown_packet_count"] == 1
    assert report["safety_violation_count"] == 0

    output_root = tmp_path / report["output_root"]

    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["packet_count"] == 1

    packet_path = output_root / manifest["packets"][0]["json_path"]

    packet = json.loads(packet_path.read_text(encoding="utf-8"))

    assert packet["verification_task_id"] == ("opportunity:1:identity_verification")

    assert packet["task_state"]["verification_result"] == "unknown"

    assert packet["task_state"]["gate_cleared"] is False

    assert packet["policy"]["automatic_conclusion_allowed"] is False

    assert packet["policy"]["outreach_authorization_required"] is True

    assert packet["policy"]["outreach_eligible"] is False

    assert "<reviewer>" in packet["event_command_templates"]["start"]

    connection = duckdb.connect(
        str(warehouse),
        read_only=True,
    )

    try:
        queue_row = connection.execute(
            """
            SELECT
                task_status,
                verification_result,
                gate_cleared,
                outreach_eligible
            FROM
                control.brampton_verification_active_queue
            """
        ).fetchone()

        event_row = connection.execute(
            """
            SELECT count(*)
            FROM
                control.brampton_verification_events
            """
        ).fetchone()

    finally:
        connection.close()

    assert queue_row == (
        "not_started",
        "unknown",
        False,
        False,
    )

    assert event_row is not None
    assert int(event_row[0]) == 0
