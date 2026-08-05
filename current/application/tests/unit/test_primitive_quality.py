from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import duckdb

from cre_foundry.primitive_quality import (
    build_primitive_quality_profile,
)


def _checksum(
    path: Path,
) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project(
    tmp_path: Path,
    *,
    unsafe_outreach: bool = False,
) -> Path:
    config_root = tmp_path / "config"

    contract_root = tmp_path / "docs" / "data_contracts"

    warehouse_path = tmp_path / "data" / "warehouse" / "cre.duckdb"

    control_path = tmp_path / "data" / "control" / "operations.sqlite3"

    config_root.mkdir(parents=True)

    contract_root.mkdir(parents=True)

    warehouse_path.parent.mkdir(parents=True)

    control_path.parent.mkdir(parents=True)

    (config_root / "primitive_quality.json").write_text(
        json.dumps(
            {
                "policy": {
                    "operating_mode": "shadow",
                    "read_only": True,
                    "schema_driven": True,
                    "sample_values_enabled": False,
                    "safety_control_values_enabled": True,
                    "automatic_acquisition": False,
                    "automatic_snapshot_registration": False,
                    "browser_execution": False,
                    "computer_vision_execution": False,
                    "automatic_conclusions": False,
                    "opportunity_ranked": False,
                    "outreach_eligible": False,
                },
                "thresholds": {
                    "high_null_ratio": 0.95,
                    "material_null_ratio": 0.5,
                    "maximum_safety_distinct_values": 20,
                },
            }
        ),
        encoding="utf-8",
    )

    warehouse = duckdb.connect(str(warehouse_path))

    try:
        warehouse.execute(
            """
            CREATE SCHEMA silver
            """
        )

        warehouse.execute(
            """
            CREATE TABLE silver.example (
                record_id VARCHAR,
                source_id VARCHAR,
                observed_at TIMESTAMP,
                normalized_address VARCHAR,
                review_status VARCHAR,
                opportunity_ranked BOOLEAN,
                outreach_eligible BOOLEAN,
                operating_mode VARCHAR
            )
            """
        )

        warehouse.execute(
            """
            INSERT INTO silver.example
            VALUES (
                'record-1',
                'source-1',
                TIMESTAMP '2026-07-26 12:00:00',
                NULL,
                'pending',
                FALSE,
                ?,
                'shadow'
            )
            """,
            [unsafe_outreach],
        )

    finally:
        warehouse.close()

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
                'source-1',
                '2026-07-26T12:00:00Z'
            );
            """
        )

        control.commit()

    finally:
        control.close()

    primitives = []

    duckdb_columns = [
        (
            "record_id",
            "VARCHAR",
            {
                "identity_candidate": True,
            },
        ),
        (
            "source_id",
            "VARCHAR",
            {
                "identity_candidate": True,
                "lineage_candidate": True,
            },
        ),
        (
            "observed_at",
            "TIMESTAMP",
            {
                "temporal_candidate": True,
            },
        ),
        (
            "normalized_address",
            "VARCHAR",
            {
                "geography_candidate": True,
            },
        ),
        (
            "review_status",
            "VARCHAR",
            {
                "verification_candidate": True,
            },
        ),
        (
            "opportunity_ranked",
            "BOOLEAN",
            {
                "safety_control": True,
            },
        ),
        (
            "outreach_eligible",
            "BOOLEAN",
            {
                "safety_control": True,
            },
        ),
        (
            "operating_mode",
            "VARCHAR",
            {
                "safety_control": True,
            },
        ),
    ]

    for index, (
        column_name,
        data_type,
        classification,
    ) in enumerate(
        duckdb_columns,
        start=1,
    ):
        primitives.append(
            {
                "primitive_id": ("duckdb:silver.example." + column_name),
                "engine": "duckdb",
                "schema": "silver",
                "relation": "example",
                "column": column_name,
                "ordinal_position": index,
                "data_type": data_type,
                "nullable": True,
                "classification": {
                    "identity_candidate": False,
                    "temporal_candidate": False,
                    "lineage_candidate": False,
                    "geography_candidate": False,
                    "verification_candidate": False,
                    "safety_control": False,
                    **classification,
                },
            }
        )

    sqlite_columns = [
        (
            "run_id",
            "TEXT",
            {
                "identity_candidate": True,
                "lineage_candidate": True,
            },
        ),
        (
            "source_id",
            "TEXT",
            {
                "identity_candidate": True,
                "lineage_candidate": True,
            },
        ),
        (
            "observed_at",
            "TEXT",
            {
                "temporal_candidate": True,
            },
        ),
    ]

    for index, (
        column_name,
        data_type,
        classification,
    ) in enumerate(
        sqlite_columns,
        start=1,
    ):
        primitives.append(
            {
                "primitive_id": ("sqlite:main.source_runs." + column_name),
                "engine": "sqlite",
                "schema": "main",
                "relation": "source_runs",
                "column": column_name,
                "ordinal_position": index,
                "data_type": data_type,
                "nullable": True,
                "classification": {
                    "identity_candidate": False,
                    "temporal_candidate": False,
                    "lineage_candidate": False,
                    "geography_candidate": False,
                    "verification_candidate": False,
                    "safety_control": False,
                    **classification,
                },
            }
        )

    (contract_root / "primitive_inventory.json").write_text(
        json.dumps(
            {
                "inventory_ready": True,
                "primitive_count": len(primitives),
                "relation_count": 2,
                "primitives": primitives,
            }
        ),
        encoding="utf-8",
    )

    return tmp_path


def test_profiles_actual_values_read_only(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    warehouse_path = project / "data" / "warehouse" / "cre.duckdb"

    control_path = project / "data" / "control" / "operations.sqlite3"

    before = (
        _checksum(warehouse_path),
        _checksum(control_path),
    )

    report = build_primitive_quality_profile(
        project,
        write_contracts=False,
    )

    after = (
        _checksum(warehouse_path),
        _checksum(control_path),
    )

    assert before == after

    summary = report["summary"]

    assert summary["profile_ready"] is True

    assert summary["safety_ready"] is True

    assert summary["safety_violation_count"] == 0


def test_detects_blocked_safety_control(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        unsafe_outreach=True,
    )

    report = build_primitive_quality_profile(
        project,
        write_contracts=False,
    )

    summary = report["summary"]

    assert summary["safety_ready"] is False

    assert summary["safety_violation_count"] == 1


def test_builds_engineering_remediation_only(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_primitive_quality_profile(
        project,
        write_contracts=False,
    )

    remediation = report["remediation"]

    assert remediation["opportunity_ranking"] is False

    assert remediation["account_ranking"] is False

    assert any(
        issue["issue_type"] == "all_null_important_primitive" for issue in remediation["issues"]
    )
