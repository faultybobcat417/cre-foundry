from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cre_foundry.brampton_permit_entity_bridge import (
    build_brampton_permit_entity_bridge,
    normalize_address,
)


def test_normalizes_units_and_street_suffixes() -> None:
    full = normalize_address(
        "10 Test Road, Unit 7, Brampton, ON, L6T 1A1",
        remove_unit=False,
    )

    base = normalize_address(
        "10 Test Road, Unit 7, Brampton, ON, L6T 1A1",
        remove_unit=True,
    )

    assert full == "10 test rd unit 7"
    assert base == "10 test rd"


def test_builds_exact_resolution_tables(
    tmp_path: Path,
) -> None:
    warehouse = tmp_path / "data" / "warehouse" / "cre.duckdb"

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
            silver.brampton_active_permit_signals (
                source_record_id VARCHAR,
                object_id BIGINT,
                permit_number VARCHAR,
                application_at_utc TIMESTAMPTZ,
                event_type VARCHAR,
                signal_strength VARCHAR,
                address_raw VARCHAR
            )
        """
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_active_permit_signals
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "permit:1",
                1,
                "P-1",
                as_of,
                "tenant_fitout",
                "high",
                "1 Test Road, Brampton, ON",
            ),
            (
                "permit:2",
                2,
                "P-2",
                as_of,
                "change_of_use",
                "high",
                "2 Test Road, Brampton, ON",
            ),
            (
                "permit:3",
                3,
                "P-3",
                as_of,
                "alteration",
                "medium",
                "3 Missing Road, Brampton, ON",
            ),
            (
                "permit:4",
                4,
                "P-4",
                as_of,
                "tenant_fitout",
                "high",
                "4 Test Road, Unit 2, Brampton, ON",
            ),
        ],
    )

    connection.execute(
        """
        CREATE TABLE silver.odbus_entities (
            entity_id VARCHAR,
            canonical_business_name VARCHAR,
            alternate_business_name VARCHAR,
            canonical_address VARCHAR,
            postal_code VARCHAR,
            naics_primary VARCHAR,
            business_sector VARCHAR,
            business_subsector VARCHAR,
            resolution_status VARCHAR,
            current_status_verified BOOLEAN,
            municipality VARCHAR
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO silver.odbus_entities
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "E-1",
                "Unique Business",
                None,
                "1 Test Rd",
                None,
                "31",
                "Manufacturing",
                None,
                "resolved",
                False,
                "Brampton",
            ),
            (
                "E-2",
                "Ambiguous One",
                None,
                "2 Test Rd",
                None,
                "42",
                "Wholesale",
                None,
                "resolved",
                False,
                "Brampton",
            ),
            (
                "E-3",
                "Ambiguous Two",
                None,
                "2 Test Rd",
                None,
                "48",
                "Transportation",
                None,
                "resolved",
                False,
                "Brampton",
            ),
            (
                "E-4",
                "Building Match",
                None,
                "4 Test Rd",
                None,
                "31",
                "Manufacturing",
                None,
                "resolved",
                False,
                "Brampton",
            ),
        ],
    )

    connection.close()

    report = build_brampton_permit_entity_bridge(tmp_path)

    assert report["signal_count"] == 4
    assert report["unique_exact_signal_count"] == 2
    assert report["ambiguous_exact_signal_count"] == 1
    assert report["unmatched_signal_count"] == 1
    assert report["candidate_row_count"] == 4
    assert report["unique_link_row_count"] == 2
    assert report["outreach_eligible_count"] == 0

    connection = duckdb.connect(
        str(warehouse),
        read_only=True,
    )

    try:
        links = connection.execute(
            """
            SELECT
                permit_number,
                entity_id,
                match_method,
                outreach_eligible
            FROM
                silver.brampton_permit_entity_unique_links
            ORDER BY permit_number
            """
        ).fetchall()

        ambiguous = connection.execute(
            """
            SELECT
                permit_number,
                candidate_count
            FROM
                silver.brampton_permit_entity_resolution
            WHERE match_status = 'ambiguous'
            """
        ).fetchall()

    finally:
        connection.close()

    assert links == [
        (
            "P-1",
            "E-1",
            "exact_full",
            False,
        ),
        (
            "P-4",
            "E-4",
            "exact_base",
            False,
        ),
    ]

    assert ambiguous == [("P-2", 2)]
