from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.human_input_workbench import (
    build_human_input_workbench,
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
        "read_only_inputs_required": True,
        "human_completion_required": True,
        "approval_invention_forbidden": True,
        "client_value_invention_forbidden": True,
        "executable_command_generation_enabled": False,
        "archive_generation_enabled": False,
        "database_access_enabled": False,
        "database_write_enabled": False,
        "snapshot_registration_enabled": False,
        "source_schedule_activation_enabled": False,
        "automatic_acquisition_enabled": False,
        "persistent_outcome_ledger_enabled": False,
        "outcome_event_insertion_enabled": False,
        "point_in_time_materialization_enabled": False,
        "model_training_enabled": False,
        "backtest_execution_enabled": False,
        "pilot_execution_enabled": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
    }


def _project(
    tmp_path: Path,
) -> Path:
    artifact_path = tmp_path / "docs" / "data_contracts" / "artifact.json"

    _write_json(
        artifact_path,
        {"value": "test"},
    )

    _write_json(
        tmp_path / "config" / "human_input_workbench.json",
        {
            "policy": _policy(),
            "review_source_id": "source-1",
            "decision_bundle_path": ("config/governance_decisions.json"),
            "client_input_order": [
                "primary_success_event",
                "transaction_economics",
                "pilot_representatives_and_capacity",
                "protected_accounts_and_exclusions",
                "operating_environment",
            ],
            "codex_contract_artifacts": ["docs/data_contracts/artifact.json"],
        },
    )

    root = tmp_path / "docs" / "data_contracts"

    _write_json(
        root / "governance_approval_packet_template.json",
        {
            "packets": [
                {
                    "source_id": "source-1",
                    "evidence_bundle_digest": ("a" * 64),
                    "evidence": {
                        "candidate_record_keys": ["id"],
                        "candidate_temporal_fields": ["observed_at"],
                    },
                }
            ]
        },
    )

    input_ids = [
        "primary_success_event",
        "transaction_economics",
        "pilot_representatives_and_capacity",
        "protected_accounts_and_exclusions",
        "operating_environment",
    ]

    _write_json(
        root / "client_input_questionnaire.json",
        {
            "questionnaire_digest": ("b" * 64),
            "sections": [
                {
                    "input_id": input_id,
                    "question": (f"Question for {input_id}"),
                    "required_fields": ["value"],
                }
                for input_id in input_ids
            ],
        },
    )

    _write_json(
        root / "manual_decision_validation.json",
        {
            "source_results": [
                {
                    "source_id": "source-1",
                    "decision_complete": False,
                    "stale_evidence": False,
                    "blockers": ["reviewer_id_missing"],
                }
            ],
            "client_results": [
                {
                    "input_id": input_id,
                    "input_complete": False,
                    "missing_required_fields": ["value"],
                    "blockers": ["client_confirmation_false"],
                }
                for input_id in input_ids
            ],
        },
    )

    _write_json(
        root / "manual_activation_envelope_summary.json",
        {"model_version": "test"},
    )

    _write_json(
        root / "historical_registration_execution_envelope.json",
        {
            "dry_run_ready": False,
            "execution_blockers": ["reviewer_id_missing"],
        },
    )

    _write_json(
        root / "outcome_ledger_bootstrap_envelope.json",
        {
            "ephemeral_bootstrap_ready": False,
            "execution_blockers": input_ids,
        },
    )

    _write_json(
        root / "codex_handoff_gate_graph.json",
        {
            "codex_contract_handoff_ready": False,
            "codex_final_product_handoff_ready": False,
        },
    )

    _write_json(
        tmp_path / "config" / "governance_decisions.json",
        {
            "decision_bundle_version": ("cre-foundry-governance-decisions-v1"),
            "source_decisions": [
                {
                    "source_id": "source-1",
                    "evidence_bundle_digest": ("a" * 64),
                    "parser_contract_approved": False,
                    "schema_contract_approved": False,
                    "approved_record_key": None,
                    "approved_temporal_fields": [],
                    "capture_policy_approved": False,
                    "change_contract_approved": False,
                    "registration_approved": False,
                    "reviewer_id": None,
                    "reviewed_at": None,
                    "evidence_reference": None,
                }
            ],
            "client_inputs": [
                {
                    "input_id": input_id,
                    "authoritative_value": None,
                    "confirmed": False,
                    "confirmed_by": None,
                    "confirmed_at": None,
                    "evidence_reference": None,
                }
                for input_id in input_ids
            ],
        },
    )

    return tmp_path


def test_pending_workbench_keeps_all_gates_closed(
    tmp_path: Path,
) -> None:
    result = build_human_input_workbench(
        _project(tmp_path),
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["review_source_decision_complete"] is False

    assert summary["client_section_complete_count"] == 0

    assert summary["historical_dry_run_generation_ready"] is False

    assert summary["outcome_bootstrap_generation_ready"] is False

    assert summary["codex_contract_handoff_ready"] is False

    assert summary["codex_final_product_handoff_ready"] is False


def test_review_packet_preserves_evidence_digest(
    tmp_path: Path,
) -> None:
    result = build_human_input_workbench(
        _project(tmp_path),
        write_contracts=False,
    )

    review = result["review_workbook"]

    assert review["source_id"] == "source-1"

    assert review["evidence_bundle_digest"] == "a" * 64

    assert review["candidate_record_keys"] == ["id"]

    assert review["candidate_temporal_fields"] == ["observed_at"]

    assert review["automatic_approval"] is False


def test_client_workbook_contains_all_required_sections(
    tmp_path: Path,
) -> None:
    result = build_human_input_workbench(
        _project(tmp_path),
        write_contracts=False,
    )

    workbook = result["client_workbook"]

    assert workbook["section_count"] == 5

    assert workbook["completed_section_count"] == 0

    assert all(section["answer_template"] == {"value": None} for section in workbook["sections"])

    assert workbook["automatic_completion"] is False

    assert workbook["client_value_invention"] is False


def test_no_executable_or_codex_archive_is_created(
    tmp_path: Path,
) -> None:
    result = build_human_input_workbench(
        _project(tmp_path),
        write_contracts=False,
    )

    commands = result["command_templates"]

    manifest = result["codex_manifest"]

    assert commands["executable_script_created"] is False

    assert commands["subprocess_execution_count"] == 0

    assert commands["database_write_count"] == 0

    assert manifest["present_artifact_count"] == 1

    assert manifest["bundle_archive_created"] is False

    assert manifest["archive_generation_enabled"] is False

    assert manifest["contract_handoff_ready"] is False
