from __future__ import annotations

from pathlib import Path

import duckdb

from cre_foundry.odbus_segments import (
    build_odbus_industrial_segments,
)


def test_builds_conservative_segments(
    tmp_path: Path,
) -> None:
    warehouse_directory = tmp_path / "data" / "warehouse"

    warehouse_directory.mkdir(parents=True)

    warehouse = warehouse_directory / "fixture.duckdb"

    connection = duckdb.connect(str(warehouse))

    try:
        connection.execute(
            """
            CREATE SCHEMA silver;

            CREATE TABLE silver.odbus_entities (
                entity_id VARCHAR,
                municipality VARCHAR,
                canonical_business_name VARCHAR,
                canonical_address VARCHAR,
                postal_code VARCHAR,
                latitude DOUBLE,
                longitude DOUBLE,
                employee_count_min BIGINT,
                employee_count_max BIGINT,
                resolution_status VARCHAR,
                current_status_verified BOOLEAN,
                naics_primary VARCHAR
            );

            CREATE TABLE
                silver.odbus_entity_observations
            (
                entity_id VARCHAR,
                source_record_id VARCHAR,
                resolution_status VARCHAR,
                current_status_verified BOOLEAN,
                naics_primary VARCHAR
            );
            """
        )

        entities = [
            (
                "e1",
                "brampton",
                "Maker",
                "1 A St",
                "L6A1A1",
                43.7,
                -79.8,
                10,
                19,
                "singleton",
                False,
                "332710",
            ),
            (
                "e2",
                "mississauga",
                "Carrier",
                "2 B St",
                "L5A1A1",
                43.6,
                -79.7,
                20,
                49,
                "singleton",
                False,
                "484110",
            ),
            (
                "e3",
                "brampton",
                "Mixed",
                "3 C St",
                "L6B1B1",
                43.7,
                -79.8,
                5,
                9,
                "resolved_cluster",
                False,
                "332710",
            ),
            (
                "e4",
                "mississauga",
                "Trade",
                "4 D St",
                "L5B1B1",
                43.6,
                -79.7,
                5,
                9,
                "singleton",
                False,
                "238220",
            ),
            (
                "e5",
                "brampton",
                "Broad",
                "5 E St",
                "L6C1C1",
                43.7,
                -79.8,
                None,
                None,
                "singleton",
                False,
                "23",
            ),
            (
                "e6",
                "mississauga",
                "Ambiguous",
                "6 F St",
                "L5C1C1",
                43.6,
                -79.7,
                5,
                9,
                "unresolved_split",
                False,
                "417230",
            ),
        ]

        connection.executemany(
            """
            INSERT INTO silver.odbus_entities
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            entities,
        )

        observations = [
            ("e1", "1", "singleton", False, "332710"),
            ("e2", "2", "singleton", False, "484110"),
            (
                "e3",
                "3",
                "resolved_cluster",
                False,
                "332710",
            ),
            (
                "e3",
                "4",
                "resolved_cluster",
                False,
                "417230",
            ),
            ("e4", "5", "singleton", False, "238220"),
            ("e5", "6", "singleton", False, "23"),
            (
                "e6",
                "7",
                "unresolved_split",
                False,
                "417230",
            ),
        ]

        connection.executemany(
            """
            INSERT INTO silver.odbus_entity_observations
            VALUES (?, ?, ?, ?, ?)
            """,
            observations,
        )

    finally:
        connection.close()

    (tmp_path / "sql").mkdir()

    source_sql = Path(__file__).resolve().parents[2] / "sql" / "odbus_industrial_segments.sql"

    (tmp_path / "sql" / "odbus_industrial_segments.sql").write_text(source_sql.read_text())

    report = build_odbus_industrial_segments(tmp_path)

    assert report["candidate_entities"] == 6
    assert report["core_pool_entities"] == 2
    assert report["outreach_eligible_entities"] == 0
