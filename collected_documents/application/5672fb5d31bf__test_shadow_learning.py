from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cre_foundry.shadow_learning import (
    audit_shadow_learning,
    build_shadow_feature_review,
    export_client_input_bundle,
    initialize_shadow_learning,
    plan_shadow_evaluation,
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
        config_root / "shadow_learning.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "outcome_event_recording_enabled": False,
                "feature_snapshot_registration_enabled": False,
                "evaluation_run_execution_enabled": False,
                "model_training_enabled": False,
                "automatic_conclusions": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
            "label_protocol": {
                "approval_status": "unapproved",
                "approved_success_event": None,
                "approved_negative_event": None,
                "active_prediction_horizon_days": None,
                "candidate_event_types": ["requirement_confirmed"],
            },
            "evaluation_protocol": {
                "split_strategy": "forward_chaining",
                "point_in_time_features_required": True,
                "embargo_required": True,
                "approved_embargo_days": None,
                "minimum_positive_events": None,
                "minimum_negative_events": None,
            },
        },
    )

    required_inputs = [
        {
            "input_id": ("pilot_success_event"),
            "description": "Success event.",
            "provided": False,
        },
        {
            "input_id": ("transaction_economics"),
            "description": "Economics.",
            "provided": False,
        },
        {
            "input_id": ("pilot_representatives"),
            "description": "Representatives.",
            "provided": False,
        },
        {
            "input_id": ("protected_accounts_and_exclusions"),
            "description": "Exclusions.",
            "provided": False,
        },
        {
            "input_id": ("operating_environment"),
            "description": "Environment.",
            "provided": False,
        },
    ]

    _write_json(
        config_root / "pilot_readiness.json",
        {"required_client_inputs": (required_inputs)},
    )

    _write_json(
        contract_root / "pilot_readiness_dossier.json",
        {"missing_client_input_count": 5},
    )

    primitives = [
        {
            "primitive_id": ("duckdb:silver.example.record_id"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "example",
            "column": "record_id",
            "data_type": "VARCHAR",
            "classification": {
                "identity_candidate": True,
                "temporal_candidate": False,
                "lineage_candidate": False,
                "safety_control": False,
            },
        },
        {
            "primitive_id": ("duckdb:silver.example.outreach_eligible"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "example",
            "column": "outreach_eligible",
            "data_type": "BOOLEAN",
            "classification": {
                "identity_candidate": False,
                "temporal_candidate": False,
                "lineage_candidate": False,
                "safety_control": True,
            },
        },
        {
            "primitive_id": ("duckdb:silver.example.employee_count"),
            "engine": "duckdb",
            "schema": "silver",
            "relation": "example",
            "column": "employee_count",
            "data_type": "INTEGER",
            "classification": {
                "identity_candidate": False,
                "temporal_candidate": False,
                "lineage_candidate": False,
                "safety_control": False,
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

    _write_json(
        contract_root / "primitive_inventory.json",
        {
            "primitive_count": 3,
            "primitives": primitives,
        },
    )

    _write_json(
        contract_root / "primitive_quality_profile.json",
        {"relation_profiles": [{"column_profiles": (column_profiles)}]},
    )

    return tmp_path


def test_initializes_empty_fail_closed_database(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_shadow_learning(
        project,
        write_contract=False,
    )

    audit = audit_shadow_learning(
        project,
        write_contract=False,
    )

    assert audit["infrastructure_ready"] is True

    assert audit["table_count"] == 3

    assert audit["trigger_count"] == 9

    assert audit["outcome_event_count"] == 0

    assert audit["feature_snapshot_count"] == 0

    assert audit["evaluation_run_count"] == 0


def test_outcome_insert_is_blocked(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_shadow_learning(
        project,
        write_contract=False,
    )

    database_path = project / "data" / "control" / "shadow_learning.sqlite3"

    connection = sqlite3.connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO outcome_events (
                    event_id,
                    opportunity_id,
                    event_type,
                    occurred_at,
                    observed_at,
                    evidence_reference,
                    actor_reference,
                    previous_event_hash,
                    event_hash,
                    created_at
                )
                VALUES (
                    'event-1',
                    'opportunity-1',
                    'requirement_confirmed',
                    '2026-07-26T12:00:00Z',
                    '2026-07-26T12:00:00Z',
                    'evidence-1',
                    'actor-1',
                    NULL,
                    'hash-1',
                    '2026-07-26T12:00:00Z'
                )
                """
            )

    finally:
        connection.close()


def test_reviews_all_primitives_without_enabling_features(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_shadow_feature_review(
        project,
        write_contract=False,
    )

    assert report["review_ready"] is True

    assert report["primitive_count"] == 3

    assert report["missing_quality_profile_count"] == 0

    assert report["approved_feature_count"] == 0

    assert report["enabled_feature_count"] == 0

    roles = {entry["column"]: entry["feature_role"] for entry in report["entries"]}

    assert roles["record_id"] == "join_key_only"

    assert roles["outreach_eligible"] == "blocked_safety_control"

    assert roles["employee_count"] == "review_required"


def test_evaluation_plan_fails_closed(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_shadow_learning(
        project,
        write_contract=False,
    )

    plan = plan_shadow_evaluation(
        project,
        write_contract=False,
    )

    assert plan["evaluation_ready"] is False

    assert plan["execution_permitted"] is False

    assert plan["model_training_permitted"] is False

    assert plan["production_ranking_permitted"] is False

    assert plan["outreach_permitted"] is False

    assert "label_protocol_not_approved" in plan["blockers"]

    assert "no_outcome_events" in plan["blockers"]

    assert "no_point_in_time_feature_snapshots" in plan["blockers"]

    assert "no_approved_model_features" in plan["blockers"]


def test_exports_five_client_sections(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    bundle = export_client_input_bundle(
        project,
        write_contracts=False,
    )

    assert bundle["section_count"] == 5

    assert bundle["all_inputs_complete"] is False

    assert bundle["automatic_approval"] is False

    assert bundle["model_training_enabled"] is False

    assert bundle["opportunity_ranked"] is False

    assert bundle["outreach_eligible"] is False
