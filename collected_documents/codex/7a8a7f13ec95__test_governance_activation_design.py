from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.governance_activation_design import (
    build_governance_activation_design,
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


def _policy() -> dict[str, object]:
    return {
        "operating_mode": "shadow",
        "templates_only": True,
        "evidence_digest_required": True,
        "manual_source_approval_required": True,
        "manual_client_confirmation_required": True,
        "manual_registration_approval_required": True,
        "manual_outcome_ledger_activation_required": True,
        "approval_invention_forbidden": True,
        "automatic_approval_enabled": False,
        "source_schedule_activation_enabled": False,
        "automatic_acquisition_enabled": False,
        "historical_registration_enabled": False,
        "persistent_outcome_ledger_enabled": False,
        "point_in_time_materialization_enabled": False,
        "model_training_enabled": False,
        "backtest_execution_enabled": False,
        "pilot_execution_enabled": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
        "codex_final_handoff_enabled": False,
    }


def _project(
    tmp_path: Path,
) -> Path:
    _write_json(
        tmp_path / "config" / "governance_activation_design.json",
        {
            "policy": _policy(),
            "source_order": ["source-1"],
            "recommended_first_registration_source_id": ("source-1"),
            "recommended_first_registration_reason": ("Test source."),
            "required_source_decisions": [
                "parser_contract_approved",
                "schema_contract_approved",
                "record_key_approved",
                "temporal_semantics_approved",
                "capture_policy_approved",
                "change_contract_approved",
                "registration_approved",
            ],
            "client_input_definitions": [
                {
                    "input_id": ("primary_success_event"),
                    "question": ("What is success?"),
                    "required_fields": ["event_name"],
                }
            ],
            "historical_registration_defaults": {
                "enabled": False,
                "dry_run_only": True,
                "maximum_source_count": 1,
                "maximum_snapshot_count": 1,
                "automatic_retry_enabled": False,
                "schedule_activation_enabled": False,
                "automatic_acquisition_enabled": False,
            },
            "outcome_ledger_activation_defaults": {
                "enabled": False,
                "ephemeral_validation_only": True,
                "persistent_database_creation_enabled": False,
                "event_insertion_enabled": False,
                "label_materialization_enabled": False,
            },
        },
    )

    root = tmp_path / "docs" / "data_contracts"

    _write_json(
        root / "source_parser_contract_validation.json",
        {
            "validations": [
                {
                    "source_id": "source-1",
                    "validation_complete": True,
                    "reproducibility_match": True,
                    "first_run": {
                        "artifact_path": ("data/bronze/source-1/file.gz"),
                        "artifact_sha256": ("a" * 64),
                        "parser_type": "test",
                        "record_count": 1,
                        "field_count": 1,
                        "schema_fingerprint": ("b" * 64),
                        "dataset_digest": ("c" * 64),
                    },
                }
            ]
        },
    )

    _write_json(
        root / "source_parser_contract_approval_template.json",
        {
            "approvals": [
                {
                    "source_id": "source-1",
                    "candidate_record_keys": ["id"],
                    "candidate_temporal_fields": ["observed_at"],
                }
            ]
        },
    )

    _write_json(
        root / "longitudinal_collection_plan.json",
        {
            "source_plans": [
                {
                    "source_id": "source-1",
                    "capture_policy": ("publication_aligned"),
                }
            ]
        },
    )

    _write_json(
        root / "historical_coverage_requirements.json",
        {
            "requirements": [
                {
                    "source_id": "source-1",
                    "candidate_history_months": 12,
                    "candidate_minimum_snapshots": 12,
                }
            ]
        },
    )

    _write_json(
        root / "source_change_detection_contracts.json",
        {
            "contracts": [
                {
                    "source_id": "source-1",
                    "change_types": ["record_added"],
                }
            ]
        },
    )

    _write_json(
        root / "client_input_capture_template.json",
        {
            "sections": [
                {
                    "input_id": ("primary_success_event"),
                    "authoritative_value": None,
                    "confirmed": False,
                }
            ]
        },
    )

    _write_json(
        root / "learning_capture_design_summary.json",
        {"model_version": "test-learning"},
    )

    _write_json(
        root / "outcome_collection_contract.json",
        {"schema_fingerprint": "d" * 64},
    )

    _write_json(
        root / "pilot_experiment_design.json",
        {"model_version": "test-pilot"},
    )

    return tmp_path


def test_all_activation_gates_remain_closed(
    tmp_path: Path,
) -> None:
    result = build_governance_activation_design(
        _project(tmp_path),
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["source_packet_count"] == 1

    assert summary["evidence_complete_source_packet_count"] == 1

    assert summary["source_approval_complete_count"] == 0

    assert summary["client_input_confirmed_count"] == 0

    assert summary["first_historical_registration_ready"] is False

    assert summary["persistent_outcome_ledger_ready"] is False

    assert summary["model_training_ready"] is False

    assert summary["codex_final_handoff_ready"] is False


def test_source_packet_is_checksum_bound(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    first = build_governance_activation_design(
        project,
        write_contracts=False,
    )

    second = build_governance_activation_design(
        project,
        write_contracts=False,
    )

    first_packet = first["source_packets"]["packets"][0]

    second_packet = second["source_packets"]["packets"][0]

    assert first_packet["evidence_bundle_digest"] == second_packet["evidence_bundle_digest"]

    assert len(first_packet["evidence_bundle_digest"]) == 64

    assert first_packet["approval_complete"] is False

    assert first_packet["registration_eligible"] is False


def test_execution_templates_are_disabled(
    tmp_path: Path,
) -> None:
    result = build_governance_activation_design(
        _project(tmp_path),
        write_contracts=False,
    )

    historical = result["historical_registration_template"]

    outcome = result["outcome_activation_template"]

    assert historical["enabled"] is False

    assert historical["dry_run_only"] is True

    assert historical["registration_permitted"] is False

    assert historical["registration_execution_count"] == 0

    assert outcome["enabled"] is False

    assert outcome["ephemeral_validation_only"] is True

    assert outcome["persistent_database_creation_enabled"] is False

    assert outcome["activation_permitted"] is False

    assert outcome["event_insertion_count"] == 0
