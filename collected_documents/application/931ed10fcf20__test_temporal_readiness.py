from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.temporal_readiness import (
    build_temporal_readiness_bundle,
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

    _write_json(
        config_root / "temporal_readiness.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "automatic_temporal_semantics_approval": False,
                "automatic_feature_approval": False,
                "automatic_snapshot_registration": False,
                "dataset_materialization_enabled": False,
                "model_training_enabled": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            }
        },
    )

    primitives = [
        {
            "primitive_id": ("duckdb:silver.complete.record_id"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "complete",
            "column": "record_id",
            "data_type": "VARCHAR",
            "classification": {
                "identity_candidate": True,
                "temporal_candidate": False,
                "lineage_candidate": False,
            },
        },
        {
            "primitive_id": ("duckdb:silver.complete.observed_at"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "complete",
            "column": "observed_at",
            "data_type": "TIMESTAMP",
            "classification": {
                "identity_candidate": False,
                "temporal_candidate": True,
                "lineage_candidate": False,
            },
        },
        {
            "primitive_id": ("duckdb:silver.complete.source_id"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "complete",
            "column": "source_id",
            "data_type": "VARCHAR",
            "classification": {
                "identity_candidate": False,
                "temporal_candidate": False,
                "lineage_candidate": True,
            },
        },
        {
            "primitive_id": ("duckdb:silver.complete.employee_count"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "complete",
            "column": "employee_count",
            "data_type": "INTEGER",
            "classification": {
                "identity_candidate": False,
                "temporal_candidate": False,
                "lineage_candidate": False,
            },
        },
        {
            "primitive_id": ("duckdb:silver.timeless.record_id"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "timeless",
            "column": "record_id",
            "data_type": "VARCHAR",
            "classification": {
                "identity_candidate": True,
                "temporal_candidate": False,
                "lineage_candidate": False,
            },
        },
    ]

    column_profiles = [
        {
            "primitive_id": primitive["primitive_id"],
            "column": primitive["column"],
            "null_ratio": 0.0,
        }
        for primitive in primitives
    ]

    feature_entries = [
        {
            "primitive_id": (primitive["primitive_id"]),
            "feature_role": (
                "review_required" if primitive["column"] == "employee_count" else "join_key_only"
            ),
        }
        for primitive in primitives
    ]

    contracts: dict[
        str,
        dict[str, object],
    ] = {
        "primitive_inventory.json": {
            "primitive_count": 5,
            "relation_count": 2,
            "primitives": primitives,
        },
        "primitive_quality_profile.json": {
            "relation_profiles": [{"column_profiles": (column_profiles)}]
        },
        "relation_dependency_graph.json": {
            "nodes": [
                {
                    "relation": ("duckdb:silver.complete"),
                    "downstream_relation_count": 1,
                },
                {
                    "relation": ("duckdb:silver.timeless"),
                    "downstream_relation_count": 0,
                },
            ]
        },
        "shadow_feature_review.json": {"entries": feature_entries},
        "shadow_learning_audit.json": {
            "feature_snapshot_count": 0,
            "outcome_event_count": 0,
        },
        "shadow_evaluation_plan.json": {"blockers": ["label_protocol_not_approved"]},
        "pilot_readiness_dossier.json": {"missing_client_input_count": 5},
        "source_snapshot_bootstrap_review.json": {"registration_execution_count": 0},
    }

    for filename, payload in contracts.items():
        _write_json(
            contract_root / filename,
            payload,
        )

    return tmp_path


def test_reviews_every_relation(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_temporal_readiness_bundle(
        project,
        write_contracts=False,
    )

    temporal = report["temporal_review"]

    assert temporal["review_ready"] is True

    assert temporal["relation_count"] == 2

    assert temporal["approved_temporal_relation_count"] == 0

    statuses = {relation["relation"]: relation["status"] for relation in temporal["relations"]}

    assert statuses["duckdb:silver.complete"] == "review_temporal_semantics"

    assert statuses["duckdb:silver.timeless"] == "blocked_no_temporal_semantics"


def test_builds_unapproved_feature_definitions(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_temporal_readiness_bundle(
        project,
        write_contracts=False,
    )

    queue = report["feature_queue"]

    assert queue["definition_count"] == 1

    assert queue["approved_definition_count"] == 0

    assert queue["enabled_feature_count"] == 0

    definition = queue["definitions"][0]

    assert definition["column"] == "employee_count"

    assert definition["model_feature_enabled"] is False


def test_dataset_plan_fails_closed(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_temporal_readiness_bundle(
        project,
        write_contracts=False,
    )

    plan = report["dataset_plan"]

    assert plan["plan_ready"] is True

    assert plan["dataset_build_ready"] is False

    assert plan["dataset_build_execution_permitted"] is False

    assert plan["snapshot_registration_permitted"] is False

    assert plan["model_training_permitted"] is False

    assert plan["production_ranking_permitted"] is False

    assert plan["outreach_permitted"] is False

    assert "no_approved_temporal_relations" in plan["blockers"]

    assert "no_registered_source_snapshots" in plan["blockers"]
