from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cre_foundry.brampton_permit_opportunity_evidence import (
    build_brampton_permit_opportunity_evidence,
    derive_evidence_status,
)


def test_derives_evidence_status() -> None:
    assert derive_evidence_status("corroborated_name_agreement") == "cross_source_corroborated"

    assert derive_evidence_status("cross_source_name_conflict") == "cross_source_conflict"

    assert derive_evidence_status("unresolved") == "unresolved"


def test_builds_one_safe_row_per_permit(
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
            silver.brampton_permit_cross_source_reconciliation (
                permit_source_record_id VARCHAR,
                object_id BIGINT,
                permit_number VARCHAR,
                application_at_utc TIMESTAMPTZ,
                event_type VARCHAR,
                signal_strength VARCHAR,
                address_raw VARCHAR,
                historical_match_method VARCHAR,
                historical_match_status VARCHAR,
                historical_candidate_count INTEGER,
                current_match_method VARCHAR,
                current_match_status VARCHAR,
                current_candidate_count INTEGER,
                current_directory_address_match BOOLEAN,
                historical_unique_entity_id VARCHAR,
                historical_unique_business_name VARCHAR,
                current_unique_global_id VARCHAR,
                current_unique_business_name VARCHAR,
                best_historical_entity_id VARCHAR,
                best_historical_business_name VARCHAR,
                best_current_global_id VARCHAR,
                best_current_business_name VARCHAR,
                name_similarity DOUBLE,
                normalized_name_exact BOOLEAN,
                reconciliation_class VARCHAR,
                reconciliation_state VARCHAR,
                cross_source_name_alignment BOOLEAN,
                review_required BOOLEAN,
                historical_candidate_names_json VARCHAR,
                current_candidate_names_json VARCHAR
            )
        """
    )

    connection.execute(
        """
        CREATE TABLE
            silver.brampton_permit_directory_unique_address_links (
                permit_source_record_id VARCHAR,
                directory_source_record_id VARCHAR,
                directory_global_id VARCHAR,
                company_name VARCHAR,
                business_full_address VARCHAR,
                unit VARCHAR,
                postal_code VARCHAR,
                phone VARCHAR,
                website VARCHAR,
                naics_2 VARCHAR,
                naics_6 VARCHAR,
                product_description VARCHAR,
                employee_group VARCHAR,
                employee_count_min INTEGER,
                employee_count_max INTEGER,
                gfa_square_feet BIGINT,
                directory_operational_at_snapshot BOOLEAN,
                directory_as_of_timestamp TIMESTAMPTZ
            )
        """
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_cross_source_reconciliation
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                "permit:1",
                1,
                "P-1",
                as_of,
                "building_addition",
                "high",
                "1 Test Rd",
                "exact_full",
                "unique",
                1,
                "exact_full",
                "unique",
                1,
                True,
                "E-1",
                "Same Business Inc.",
                "{G-1}",
                "Same Business",
                "E-1",
                "Same Business Inc.",
                "{G-1}",
                "Same Business",
                100.0,
                True,
                "both_unique_name_exact",
                "corroborated_name_agreement",
                True,
                False,
                '["Same Business Inc."]',
                '["Same Business"]',
            ),
            (
                "permit:2",
                2,
                "P-2",
                as_of,
                "alteration",
                "medium",
                "2 Test Rd",
                "exact_full",
                "unique",
                1,
                "exact_full",
                "unique",
                1,
                True,
                "E-2",
                "Old Business",
                "{G-2}",
                "New Business",
                "E-2",
                "Old Business",
                "{G-2}",
                "New Business",
                20.0,
                False,
                "both_unique_name_conflict",
                "cross_source_name_conflict",
                False,
                True,
                '["Old Business"]',
                '["New Business"]',
            ),
            (
                "permit:3",
                3,
                "P-3",
                as_of,
                "tenant_fitout",
                "high",
                "3 Missing Rd",
                "none",
                "unmatched",
                0,
                "none",
                "unmatched",
                0,
                False,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                False,
                "both_unmatched",
                "unresolved",
                False,
                False,
                "[]",
                "[]",
            ),
        ],
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_directory_unique_address_links
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                "permit:1",
                "directory:1",
                "{G-1}",
                "Same Business",
                "1 Test Rd",
                None,
                "L6T 1A1",
                "905-555-0001",
                "https://example.test",
                "Manufacturing",
                "311111",
                "Products",
                "10-19",
                10,
                19,
                10000,
                True,
                as_of,
            ),
            (
                "permit:2",
                "directory:2",
                "{G-2}",
                "New Business",
                "2 Test Rd",
                None,
                "L6T 1A2",
                None,
                None,
                "Wholesale Trade",
                "414110",
                None,
                "5-9",
                5,
                9,
                None,
                True,
                as_of,
            ),
        ],
    )

    connection.close()

    report = build_brampton_permit_opportunity_evidence(tmp_path)

    assert report["record_count"] == 3
    assert report["current_directory_record_count"] == 2
    assert report["cross_source_corroborated_count"] == 1
    assert report["review_queue_count"] == 1
    assert report["unresolved_count"] == 1
    assert report["ranked_count"] == 0
    assert report["safety_violation_count"] == 0

    connection = duckdb.connect(
        str(warehouse),
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                permit_number,
                evidence_status,
                provisional_business_name,
                provisional_business_source,
                manual_resolution_required,
                identity_verification_required,
                exclusions_cleared,
                outreach_eligible,
                ranked,
                opportunity_score,
                opportunity_rank
            FROM
                silver.brampton_permit_opportunity_evidence
            ORDER BY
                permit_number
            """
        ).fetchall()

    finally:
        connection.close()

    assert rows == [
        (
            "P-1",
            "cross_source_corroborated",
            "Same Business",
            "current_brampton_directory",
            False,
            True,
            False,
            False,
            False,
            None,
            None,
        ),
        (
            "P-2",
            "cross_source_conflict",
            "New Business",
            "current_brampton_directory",
            True,
            True,
            False,
            False,
            False,
            None,
            None,
        ),
        (
            "P-3",
            "unresolved",
            None,
            None,
            True,
            True,
            False,
            False,
            False,
            None,
            None,
        ),
    ]
