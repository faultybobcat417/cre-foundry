from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import duckdb

from cre_foundry.primitive_inventory import (
    build_primitive_inventory,
)


def _project(
    tmp_path: Path,
) -> Path:
    config_path = tmp_path / "config" / "primitive_inventory.json"

    config_path.parent.mkdir(parents=True)

    config_path.write_text(
        json.dumps(
            {
                "policy": {
                    "operating_mode": "shadow",
                    "read_only": True,
                    "schema_driven": True,
                    "sample_values_enabled": False,
                    "automatic_conclusions": False,
                    "opportunity_ranked": False,
                    "outreach_eligible": False,
                    "automatic_acquisition": False,
                    "browser_execution": False,
                    "computer_vision_execution": False,
                },
                "excluded_duckdb_schemas": [
                    "information_schema",
                    "pg_catalog",
                ],
            }
        ),
        encoding="utf-8",
    )

    warehouse_path = tmp_path / "data" / "warehouse" / "cre.duckdb"

    warehouse_path.parent.mkdir(parents=True)

    warehouse = duckdb.connect(str(warehouse_path))

    try:
        warehouse.execute(
            """
            CREATE SCHEMA silver
            """
        )

        warehouse.execute(
            """
            CREATE TABLE
                silver.example (
                    permit_id VARCHAR,
                    observed_at TIMESTAMP,
                    normalized_address VARCHAR,
                    opportunity_ranked BOOLEAN,
                    outreach_eligible BOOLEAN
                )
            """
        )

        warehouse.execute(
            """
            INSERT INTO
                silver.example
            VALUES (
                'permit-1',
                TIMESTAMP '2026-07-26 12:00:00',
                '1 Main Street',
                FALSE,
                FALSE
            )
            """
        )

    finally:
        warehouse.close()

    control_path = tmp_path / "data" / "control" / "operations.sqlite3"

    control_path.parent.mkdir(parents=True)

    control = sqlite3.connect(control_path)

    try:
        control.executescript(
            """
            CREATE TABLE source_runs (
                run_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                observed_at TEXT
            );

            INSERT INTO source_runs (
                run_id,
                source_id,
                observed_at
            )
            VALUES (
                'run-1',
                'test_source',
                '2026-07-26T12:00:00Z'
            );
            """
        )

        control.commit()

    finally:
        control.close()

    return tmp_path


def test_inventory_uses_actual_schemas(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_primitive_inventory(
        project,
        write_contract=False,
    )

    assert report["inventory_ready"] is True

    assert report["relation_count"] == 2

    assert report["primitive_count"] == 8

    assert report["duplicate_primitive_ids"] == []


def test_inventory_detects_safety_controls(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_primitive_inventory(
        project,
        write_contract=False,
    )

    columns = {control["column"] for control in report["safety_controls"]}

    assert "opportunity_ranked" in columns

    assert "outreach_eligible" in columns

    assert report["production_ranking_ready"] is False

    assert report["outreach_ready"] is False


def test_inventory_detects_lineage_and_time(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_primitive_inventory(
        project,
        write_contract=False,
    )

    counts = report["classification_counts"]

    assert counts["identity_candidate"] >= 2

    assert counts["temporal_candidate"] >= 2

    assert counts["lineage_candidate"] >= 2
