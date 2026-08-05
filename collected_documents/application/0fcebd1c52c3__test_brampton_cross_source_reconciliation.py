from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cre_foundry.brampton_cross_source_reconciliation import (
    best_name_pair,
    build_brampton_cross_source_reconciliation,
    classify_reconciliation,
    normalize_business_name,
)


def test_normalizes_business_names() -> None:
    assert (
        normalize_business_name("Can-Art Aluminum Extrusions Inc.") == "can art aluminum extrusions"
    )

    assert normalize_business_name("The Stevens Company Limited") == "the stevens company"


def test_classifies_name_evidence() -> None:
    exact_pair = {
        "exact_normalized": True,
        "token_set_similarity": 100.0,
    }

    conflict_pair = {
        "exact_normalized": False,
        "token_set_similarity": 25.0,
    }

    assert (
        classify_reconciliation(
            "unique",
            "unique",
            exact_pair,
        )
        == "both_unique_name_exact"
    )

    assert (
        classify_reconciliation(
            "unique",
            "unique",
            conflict_pair,
        )
        == "both_unique_name_conflict"
    )

    assert (
        classify_reconciliation(
            "unmatched",
            "unique",
            None,
        )
        == "current_unique_only"
    )


def test_builds_conservative_reconciliation(
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
            silver.brampton_permit_entity_resolution (
                permit_source_record_id VARCHAR,
                object_id BIGINT,
                permit_number VARCHAR,
                application_at_utc TIMESTAMPTZ,
                event_type VARCHAR,
                signal_strength VARCHAR,
                address_raw VARCHAR,
                match_method VARCHAR,
                match_status VARCHAR,
                candidate_count INTEGER
            )
        """
    )

    connection.execute(
        """
        CREATE TABLE
            silver.brampton_permit_directory_resolution (
                permit_source_record_id VARCHAR,
                permit_number VARCHAR,
                match_method VARCHAR,
                match_status VARCHAR,
                candidate_count INTEGER,
                current_directory_address_match BOOLEAN
            )
        """
    )

    connection.execute(
        """
        CREATE TABLE
            silver.brampton_permit_entity_match_candidates (
                permit_source_record_id VARCHAR,
                entity_id VARCHAR,
                canonical_business_name VARCHAR,
                canonical_address VARCHAR,
                naics_primary VARCHAR,
                business_sector VARCHAR,
                candidate_rank INTEGER,
                current_status_verified BOOLEAN,
                outreach_eligible BOOLEAN
            )
        """
    )

    connection.execute(
        """
        CREATE TABLE
            silver.brampton_permit_directory_match_candidates (
                permit_source_record_id VARCHAR,
                directory_global_id VARCHAR,
                company_name VARCHAR,
                business_full_address VARCHAR,
                naics_2 VARCHAR,
                naics_6 VARCHAR,
                employee_group VARCHAR,
                candidate_rank INTEGER,
                directory_operational_at_snapshot BOOLEAN,
                permit_occupant_verified BOOLEAN,
                commercial_requirement_verified BOOLEAN,
                decision_maker_verified BOOLEAN,
                outreach_eligible BOOLEAN
            )
        """
    )

    historical_resolution = [
        (
            "permit:1",
            1,
            "P-1",
            as_of,
            "alteration",
            "medium",
            "1 Test Rd",
            "exact_full",
            "unique",
            1,
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
        ),
        (
            "permit:3",
            3,
            "P-3",
            as_of,
            "tenant_fitout",
            "high",
            "3 Test Rd",
            "none",
            "unmatched",
            0,
        ),
        (
            "permit:4",
            4,
            "P-4",
            as_of,
            "tenant_fitout",
            "high",
            "4 Test Rd",
            "none",
            "unmatched",
            0,
        ),
    ]

    current_resolution = [
        (
            "permit:1",
            "P-1",
            "exact_full",
            "unique",
            1,
            True,
        ),
        (
            "permit:2",
            "P-2",
            "exact_full",
            "unique",
            1,
            True,
        ),
        (
            "permit:3",
            "P-3",
            "exact_full",
            "unique",
            1,
            True,
        ),
        (
            "permit:4",
            "P-4",
            "none",
            "unmatched",
            0,
            False,
        ),
    ]

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_entity_resolution
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        historical_resolution,
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_directory_resolution
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        current_resolution,
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_entity_match_candidates
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "permit:1",
                "E-1",
                "Same Business Inc.",
                "1 Test Rd",
                "311111",
                "Manufacturing",
                1,
                False,
                False,
            ),
            (
                "permit:2",
                "E-2",
                "Old Business",
                "2 Test Rd",
                "311111",
                "Manufacturing",
                1,
                False,
                False,
            ),
        ],
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_permit_directory_match_candidates
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                "permit:1",
                "{G-1}",
                "Same Business",
                "1 Test Rd",
                "Manufacturing",
                "311111",
                "10-19",
                1,
                True,
                False,
                False,
                False,
                False,
            ),
            (
                "permit:2",
                "{G-2}",
                "Replacement Business",
                "2 Test Rd",
                "Manufacturing",
                "311111",
                "10-19",
                1,
                True,
                False,
                False,
                False,
                False,
            ),
            (
                "permit:3",
                "{G-3}",
                "Current Only Business",
                "3 Test Rd",
                "Manufacturing",
                "311111",
                "10-19",
                1,
                True,
                False,
                False,
                False,
                False,
            ),
        ],
    )

    connection.close()

    report = build_brampton_cross_source_reconciliation(tmp_path)

    assert report["signal_count"] == 4
    assert report["cross_source_agreement_count"] == 1
    assert report["cross_source_alignment_count"] == 1
    assert report["review_queue_count"] == 2
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
                reconciliation_class,
                reconciliation_state,
                review_required,
                automatic_identity_promotion,
                permit_occupant_verified,
                outreach_eligible
            FROM
                silver.brampton_permit_cross_source_reconciliation
            ORDER BY permit_number
            """
        ).fetchall()

    finally:
        connection.close()

    assert rows == [
        (
            "P-1",
            "both_unique_name_exact",
            "corroborated_name_agreement",
            False,
            False,
            False,
            False,
        ),
        (
            "P-2",
            "both_unique_name_conflict",
            "cross_source_name_conflict",
            True,
            False,
            False,
            False,
        ),
        (
            "P-3",
            "current_unique_only",
            "current_only_address_evidence",
            True,
            False,
            False,
            False,
        ),
        (
            "P-4",
            "both_unmatched",
            "unresolved",
            False,
            False,
            False,
            False,
        ),
    ]

    pair = best_name_pair(
        [
            {
                "entity_id": "E",
                "business_name": "Test Inc.",
            }
        ],
        [
            {
                "global_id": "G",
                "business_name": "Test",
            }
        ],
    )

    assert pair is not None
    assert pair["exact_normalized"] is True
