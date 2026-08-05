from __future__ import annotations

from pathlib import Path

import duckdb

from cre_foundry.odbus_entities import (
    build_odbus_entity_model,
)


def test_builds_conservative_entity_model(
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

            CREATE TABLE
                silver.odbus_target_businesses
            (
                source_id VARCHAR,
                source_record_id VARCHAR,
                entity_fingerprint VARCHAR,
                business_name VARCHAR,
                alternate_business_name VARCHAR,
                full_address VARCHAR,
                postal_code VARCHAR,
                latitude DOUBLE,
                longitude DOUBLE,
                municipality VARCHAR,
                business_id_number VARCHAR,
                licence_number VARCHAR,
                naics_2d VARCHAR,
                naics_primary VARCHAR,
                employee_count_raw VARCHAR,
                employee_count_min BIGINT,
                employee_count_max BIGINT,
                business_sector VARCHAR,
                business_subsector VARCHAR,
                provider VARCHAR,
                status_normalized VARCHAR,
                current_status_verified BOOLEAN
            )
            """
        )

        rows = [
            (
                "s",
                "1",
                "fp-safe",
                "Safe",
                None,
                "1 Main St",
                "L6A1A1",
                43.7,
                -79.8,
                "brampton",
                "B1",
                "L1",
                "54",
                "541611",
                "5",
                5,
                5,
                "Consulting",
                None,
                "P1",
                "active",
                False,
            ),
            (
                "s",
                "2",
                "fp-safe",
                "Safe",
                None,
                "1 Main St",
                "L6A1A1",
                43.7,
                -79.8,
                "brampton",
                "B1",
                "L2",
                "54",
                "541611",
                "5",
                5,
                5,
                "Consulting",
                None,
                "P1",
                "active",
                False,
            ),
            (
                "s",
                "3",
                "fp-var",
                "Variation",
                None,
                "2 Main St",
                "L6A1A2",
                43.7,
                -79.8,
                "brampton",
                None,
                None,
                "44",
                "445110",
                "2",
                2,
                2,
                "Retail",
                None,
                "P1",
                "active",
                False,
            ),
            (
                "s",
                "4",
                "fp-var",
                "Variation",
                None,
                "2 Main St",
                "L6A1A2",
                43.7,
                -79.8,
                "brampton",
                None,
                None,
                "44",
                "445120",
                "4",
                4,
                4,
                "Retail",
                None,
                "P1",
                "active",
                False,
            ),
            (
                "s",
                "5",
                "fp-amb",
                "Ambiguous",
                None,
                "3 Main St",
                "L6A1A3",
                43.7,
                -79.8,
                "brampton",
                None,
                None,
                "23",
                "236110",
                None,
                None,
                None,
                "Construction",
                None,
                "P1",
                "active",
                False,
            ),
            (
                "s",
                "6",
                "fp-amb",
                "Ambiguous",
                None,
                "4 Main St",
                "L6A1A3",
                43.7,
                -79.8,
                "brampton",
                None,
                None,
                "23",
                "236110",
                None,
                None,
                None,
                "Construction",
                None,
                "P1",
                "active",
                False,
            ),
            (
                "s",
                "7",
                "fp-single",
                "Singleton",
                None,
                "5 Main St",
                "L6A1A4",
                43.7,
                -79.8,
                "brampton",
                None,
                None,
                "72",
                "722511",
                "3",
                3,
                3,
                "Restaurant",
                None,
                "P1",
                "active",
                False,
            ),
        ]

        connection.executemany(
            """
            INSERT INTO silver.odbus_target_businesses
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )
    finally:
        connection.close()

    (tmp_path / "sql").mkdir()
    source_sql = Path(__file__).resolve().parents[2] / "sql" / "odbus_entity_model.sql"

    (tmp_path / "sql" / "odbus_entity_model.sql").write_text(source_sql.read_text())

    report = build_odbus_entity_model(tmp_path)

    assert report["observation_count"] == 7
    assert report["entity_count"] == 5
    assert report["collapsed_observation_count"] == 2
    assert report["ambiguous_cluster_count"] == 1
