from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.learning_capture_design import (
    build_learning_capture_design,
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
    _write_json(
        tmp_path / "config" / "learning_capture_design.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "design_only": True,
                "append_only_outcomes_required": True,
                "point_in_time_required": True,
                "future_information_forbidden": True,
                "primary_outcome_requires_client_confirmation": True,
                "economic_parameters_require_client_confirmation": True,
                "source_schedule_activation_enabled": False,
                "automatic_acquisition_enabled": False,
                "historical_backfill_enabled": False,
                "persistent_outcome_database_enabled": False,
                "outcome_event_insertion_enabled": False,
                "label_materialization_enabled": False,
                "model_training_enabled": False,
                "backtest_execution_enabled": False,
                "production_ranking_enabled": False,
                "outreach_enabled": False,
            },
            "source_plans": [
                {
                    "source_id": "source-1",
                    "candidate_record_keys": ["id"],
                    "candidate_temporal_fields": ["observed_at"],
                    "candidate_history_months": 12,
                    "candidate_minimum_snapshots": 12,
                    "capture_policy": ("publication_aligned"),
                    "change_types": [
                        "record_added",
                        "record_removed",
                    ],
                }
            ],
            "candidate_event_types": [
                "recommendation_generated",
                "decision_maker_reached",
                "commercial_requirement_confirmed",
                "not_reached",
            ],
            "required_client_inputs": [
                "primary_success_event",
                "transaction_economics",
                "pilot_representatives_and_capacity",
                "protected_accounts_and_exclusions",
                "operating_environment",
            ],
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_parser_contract_approval_template.json",
        {
            "approvals": [
                {
                    "source_id": "source-1",
                    "parser_contract_approved": False,
                    "schema_contract_approved": False,
                }
            ]
        },
    )

    return tmp_path


def test_outcome_schema_is_append_only(
    tmp_path: Path,
) -> None:
    result = build_learning_capture_design(
        _project(tmp_path),
        write_contracts=False,
    )

    outcomes = result["outcomes"]

    assert outcomes["table_count"] == 5

    assert outcomes["trigger_count"] == 10

    assert outcomes["append_only_update_blocked"] is True

    assert outcomes["append_only_delete_blocked"] is True

    assert outcomes["ephemeral_database_deleted"] is True


def test_history_and_training_are_not_claimed(
    tmp_path: Path,
) -> None:
    result = build_learning_capture_design(
        _project(tmp_path),
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["collection_ready_source_count"] == 0

    assert summary["point_in_time_dataset_ready"] is False

    assert summary["model_training_ready"] is False

    assert summary["historical_backtest_ready"] is False

    assert summary["incremental_roi_proven"] is False


def test_client_inputs_remain_unconfirmed(
    tmp_path: Path,
) -> None:
    result = build_learning_capture_design(
        _project(tmp_path),
        write_contracts=False,
    )

    client_inputs = result["client_inputs"]

    assert client_inputs["section_count"] == 5

    assert client_inputs["confirmed_section_count"] == 0

    assert client_inputs["model_training_permitted"] is False

    assert client_inputs["pilot_execution_permitted"] is False

    assert all(section["confirmed"] is False for section in client_inputs["sections"])
