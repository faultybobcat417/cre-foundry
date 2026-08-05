from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from cre_foundry.brampton_permit_directory_bridge import (
    build_brampton_permit_directory_bridge,
)


def test_builds_conservative_current_directory_bridge(
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
        CREATE TABLE
            silver.brampton_business_directory (
                source_record_id VARCHAR,
                global_id VARCHAR,
                company_name VARCHAR,
                business_full_address VARCHAR,
                normalized_full_address VARCHAR,
                normalized_base_address VARCHAR,
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
                as_of_timestamp TIMESTAMPTZ,
                commercial_requirement_verified BOOLEAN,
                decision_maker_verified BOOLEAN,
                outreach_eligible BOOLEAN
            )
        """
    )

    connection.executemany(
        """
        INSERT INTO
            silver.brampton_business_directory
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                "directory:1",
                "{GLOBAL-1}",
                "Unique Business",
                "1 Test Rd",
                "1 test rd",
                "1 test rd",
                None,
                None,
                "905-555-0001",
                None,
                "Manufacturing",
                "311111",
                None,
                "1-4",
                1,
                4,
                1000,
                True,
                as_of,
                False,
                False,
                False,
            ),
            (
                "directory:2",
                "{GLOBAL-2}",
                "Ambiguous One",
                "2 Test Rd",
                "2 test rd",
                "2 test rd",
                None,
                None,
                None,
                None,
                "Wholesale trade",
                "414110",
                None,
                "5-9",
                5,
                9,
                None,
                True,
                as_of,
                False,
                False,
                False,
            ),
            (
                "directory:3",
                "{GLOBAL-3}",
                "Ambiguous Two",
                "2 Test Rd",
                "2 test rd",
                "2 test rd",
                None,
                None,
                None,
                None,
                "Transportation and warehousing",
                "484110",
                None,
                "10-19",
                10,
                19,
                None,
                True,
                as_of,
                False,
                False,
                False,
            ),
            (
                "directory:4",
                "{GLOBAL-4}",
                "Base Address Business",
                "4 Test Rd",
                "4 test rd",
                "4 test rd",
                None,
                None,
                None,
                None,
                "Manufacturing",
                "332710",
                None,
                "20-49",
                20,
                49,
                5000,
                True,
                as_of,
                False,
                False,
                False,
            ),
        ],
    )

    connection.close()

    report = build_brampton_permit_directory_bridge(tmp_path)

    assert report["signal_count"] == 4
    assert report["unique_exact_signal_count"] == 2
    assert report["ambiguous_exact_signal_count"] == 1
    assert report["unmatched_signal_count"] == 1
    assert report["candidate_row_count"] == 4
    assert report["unique_link_row_count"] == 2
    assert report["directory_operational_candidate_count"] == 4
    assert report["permit_occupant_verified_count"] == 0
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
                directory_global_id,
                match_method,
                address_evidence_only,
                permit_occupant_verified,
                commercial_requirement_verified,
                decision_maker_verified,
                outreach_eligible
            FROM
                silver.brampton_permit_directory_unique_address_links
            ORDER BY
                permit_number
            """
        ).fetchall()

        ambiguous = connection.execute(
            """
            SELECT
                permit_number,
                candidate_count
            FROM
                silver.brampton_permit_directory_resolution
            WHERE
                match_status = 'ambiguous'
            """
        ).fetchall()

    finally:
        connection.close()

    assert links == [
        (
            "P-1",
            "{GLOBAL-1}",
            "exact_full",
            True,
            False,
            False,
            False,
            False,
        ),
        (
            "P-4",
            "{GLOBAL-4}",
            "exact_base",
            True,
            False,
            False,
            False,
            False,
        ),
    ]

    assert ambiguous == [("P-2", 2)]
