from __future__ import annotations

import json
from pathlib import Path

import duckdb

from cre_foundry.data_health import (
    audit_data_health_baseline,
    build_data_health_bundle,
)


def _write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _project(
    tmp_path: Path,
) -> Path:
    config_root = tmp_path / "config"

    contract_root = tmp_path / "docs" / "data_contracts"

    warehouse_path = tmp_path / "data" / "warehouse" / "cre.duckdb"

    warehouse_path.parent.mkdir(parents=True)

    _write_json(
        config_root / "data_health.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "automatic_schema_mutation": False,
                "automatic_backfill": False,
                "automatic_acquisition": False,
                "automatic_conclusions": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
            "priority_mapping": {
                "critical": "P0",
                "high": "P1",
                "medium": "P2",
                "low": "P3",
            },
        },
    )

    primitives = [
        {
            "primitive_id": ("duckdb:silver.base.record_id"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "base",
            "column": "record_id",
            "data_type": "VARCHAR",
            "nullable": False,
            "classification": {"identity_candidate": True},
        },
        {
            "primitive_id": ("duckdb:silver.base.observed_at"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "base",
            "column": "observed_at",
            "data_type": "TIMESTAMP",
            "nullable": False,
            "classification": {
                "temporal_candidate": True,
                "lineage_candidate": True,
            },
        },
        {
            "primitive_id": ("duckdb:silver.derived.record_id"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "derived",
            "column": "record_id",
            "data_type": "VARCHAR",
            "nullable": False,
            "classification": {"identity_candidate": True},
        },
    ]

    relation_profiles = [
        {
            "engine": "duckdb",
            "schema": "silver",
            "relation": "base",
            "row_count": 1,
            "column_profiles": [
                {
                    "primitive_id": ("duckdb:silver.base.record_id"),
                    "column": "record_id",
                    "row_count": 1,
                    "null_count": 0,
                    "null_ratio": 0.0,
                    "distinct_count": 1,
                },
                {
                    "primitive_id": ("duckdb:silver.base.observed_at"),
                    "column": "observed_at",
                    "row_count": 1,
                    "null_count": 0,
                    "null_ratio": 0.0,
                    "distinct_count": 1,
                },
            ],
        },
        {
            "engine": "duckdb",
            "schema": "silver",
            "relation": "derived",
            "row_count": 1,
            "column_profiles": [
                {
                    "primitive_id": ("duckdb:silver.derived.record_id"),
                    "column": "record_id",
                    "row_count": 1,
                    "null_count": 0,
                    "null_ratio": 0.0,
                    "distinct_count": 1,
                }
            ],
        },
    ]

    _write_json(
        contract_root / "primitive_inventory.json",
        {
            "inventory_ready": True,
            "primitive_count": 3,
            "relation_count": 2,
            "primitives": primitives,
        },
    )

    _write_json(
        contract_root / "primitive_quality_profile.json",
        {
            "profile_ready": True,
            "relation_profiles": (relation_profiles),
        },
    )

    _write_json(
        contract_root / "primitive_remediation_queue.json",
        {
            "issues": [
                {
                    "issue_type": ("nonempty_relation_without_lineage_primitive"),
                    "severity": "medium",
                    "relation": ("duckdb:silver.derived"),
                    "engineering_only": True,
                }
            ]
        },
    )

    connection = duckdb.connect(str(warehouse_path))

    try:
        connection.execute("CREATE SCHEMA silver")

        connection.execute(
            """
            CREATE TABLE silver.base (
                record_id VARCHAR,
                observed_at TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            INSERT INTO silver.base
            VALUES (
                'record-1',
                TIMESTAMP '2026-07-26 12:00:00'
            )
            """
        )

        connection.execute(
            """
            CREATE VIEW silver.derived AS
            SELECT record_id
            FROM silver.base
            """
        )

    finally:
        connection.close()

    return tmp_path


def test_builds_deterministic_health_baseline(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    first = build_data_health_bundle(
        project,
        write_contracts=False,
    )

    second = build_data_health_bundle(
        project,
        write_contracts=False,
    )

    assert first["baseline"]["relation_fingerprints"] == second["baseline"]["relation_fingerprints"]

    assert first["baseline"]["baseline_ready"] is True

    assert first["dependencies"]["edge_count"] == 1


def test_builds_engineering_remediation_only(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_data_health_bundle(
        project,
        write_contracts=False,
    )

    remediation = report["remediation"]

    assert remediation["work_item_count"] == 1

    assert remediation["opportunity_ranking"] is False

    assert remediation["account_ranking"] is False

    assert remediation["automatic_schema_mutation"] is False


def test_detects_quality_fingerprint_drift(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    build_data_health_bundle(
        project,
        write_contracts=True,
    )

    profile_path = project / "docs" / "data_contracts" / "primitive_quality_profile.json"

    payload = json.loads(profile_path.read_text(encoding="utf-8"))

    payload["relation_profiles"][0]["row_count"] = 2

    profile_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    audit = audit_data_health_baseline(
        project,
        write_contract=False,
    )

    assert audit["drift_detected"] is True

    assert audit["changed_relation_count"] == 1
