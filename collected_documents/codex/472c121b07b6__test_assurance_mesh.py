from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cre_foundry.assurance_mesh import (
    build_assurance_mesh,
)


def _stable_digest(
    value: object,
) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _file_digest(
    path: Path,
) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _policy() -> dict[str, object]:
    return {
        "operating_mode": "shadow",
        "read_only_input_validation": True,
        "deterministic_double_build_required": True,
        "artifact_digest_continuity_required": True,
        "dependency_dag_required": True,
        "adversarial_scenario_matrix_required": True,
        "state_aware_invariants_required": True,
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
    root = tmp_path / "docs" / "data_contracts"

    input_ids = [
        "primary_success_event",
        "transaction_economics",
        "pilot_representatives_and_capacity",
        "protected_accounts_and_exclusions",
        "operating_environment",
    ]

    decisions = {
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
    }

    manual_summary = {
        "recommended_source_approval_ready": False,
        "historical_registration_dry_run_ready": False,
        "outcome_ledger_ephemeral_bootstrap_ready": False,
        "codex_contract_handoff_ready": False,
        "codex_final_product_handoff_ready": False,
        "client_input_complete_count": 0,
        "client_input_required_count": 5,
    }

    _write_json(
        tmp_path / "config" / "governance_decisions.json",
        decisions,
    )

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

    _write_json(
        root / "client_input_questionnaire.json",
        {
            "questionnaire_digest": ("b" * 64),
            "sections": [
                {
                    "input_id": input_id,
                    "required_fields": ["value"],
                }
                for input_id in input_ids
            ],
        },
    )

    _write_json(
        root / "manual_decision_validation.json",
        {
            "source_results": [],
            "client_results": [],
        },
    )

    _write_json(
        root / "manual_activation_envelope_summary.json",
        manual_summary,
    )

    _write_json(
        root / "historical_registration_execution_envelope.json",
        {"dry_run_ready": False},
    )

    _write_json(
        root / "outcome_ledger_bootstrap_envelope.json",
        {"ephemeral_bootstrap_ready": False},
    )

    _write_json(
        root / "codex_handoff_gate_graph.json",
        {
            "codex_contract_handoff_ready": False,
            "codex_final_product_handoff_ready": False,
            "controlled_pilot_complete": False,
            "incremental_roi_proven": False,
            "production_governance_ready": False,
        },
    )

    _write_json(
        root / "outcome_ledger_activation_request_template.json",
        {
            "outcome_schema_fingerprint": ("c" * 64),
            "client_questionnaire_digest": ("b" * 64),
        },
    )

    _write_json(
        root / "outcome_collection_contract.json",
        {"schema_fingerprint": ("c" * 64)},
    )

    _write_json(
        root / "permit_review.json",
        {"value": "review"},
    )

    _write_json(
        root / "client_answer.json",
        {"value": "client"},
    )

    _write_json(
        root / "commands.json",
        {"value": "commands"},
    )

    manifest_artifact = root / "permit_review.json"

    _write_json(
        root / "codex_manifest.json",
        {
            "artifacts": [
                {
                    "path": ("docs/data_contracts/permit_review.json"),
                    "sha256": _file_digest(manifest_artifact),
                }
            ]
        },
    )

    _write_json(
        root / "human_summary.json",
        {
            "decision_bundle_digest": (_stable_digest(decisions)),
            "activation_summary_digest": (_stable_digest(manual_summary)),
            "database_write_count": 0,
            "snapshot_registration_count": 0,
            "outcome_event_insertion_count": 0,
            "model_training_execution_count": 0,
            "pilot_execution_count": 0,
            "production_ranking_execution_count": 0,
            "outreach_execution_count": 0,
        },
    )

    paths = {
        "governance_decisions": ("config/governance_decisions.json"),
        "governance_approval_packets": (
            "docs/data_contracts/governance_approval_packet_template.json"
        ),
        "client_questionnaire": ("docs/data_contracts/client_input_questionnaire.json"),
        "manual_decision_validation": ("docs/data_contracts/manual_decision_validation.json"),
        "manual_activation_summary": (
            "docs/data_contracts/manual_activation_envelope_summary.json"
        ),
        "historical_envelope": (
            "docs/data_contracts/historical_registration_execution_envelope.json"
        ),
        "outcome_envelope": ("docs/data_contracts/outcome_ledger_bootstrap_envelope.json"),
        "codex_gate_graph": ("docs/data_contracts/codex_handoff_gate_graph.json"),
        "outcome_activation_template": (
            "docs/data_contracts/outcome_ledger_activation_request_template.json"
        ),
        "outcome_contract": ("docs/data_contracts/outcome_collection_contract.json"),
        "codex_manifest": ("docs/data_contracts/codex_manifest.json"),
        "human_workbench_summary": ("docs/data_contracts/human_summary.json"),
        "permit_review_workbook": ("docs/data_contracts/permit_review.json"),
        "client_answer_workbook": ("docs/data_contracts/client_answer.json"),
        "gate_command_templates": ("docs/data_contracts/commands.json"),
    }

    artifact_nodes = [
        {
            "artifact_id": artifact_id,
            "path": relative_path,
            "role": artifact_id,
            "required": True,
        }
        for artifact_id, relative_path in paths.items()
    ]

    artifact_ids = list(paths)

    dependency_edges = [
        {
            "from": artifact_ids[index],
            "to": artifact_ids[index + 1],
        }
        for index in range(len(artifact_ids) - 1)
    ]

    _write_json(
        tmp_path / "config" / "assurance_mesh.json",
        {
            "policy": _policy(),
            "recommended_source_id": ("source-1"),
            "artifact_nodes": (artifact_nodes),
            "dependency_edges": (dependency_edges),
        },
    )

    return tmp_path


def test_pending_state_passes_all_assurance_layers(
    tmp_path: Path,
) -> None:
    result = build_assurance_mesh(
        _project(tmp_path),
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["missing_required_artifact_count"] == 0

    assert summary["dependency_graph_acyclic"] is True

    assert summary["failed_scenario_count"] == 0

    assert summary["failed_invariant_count"] == 0

    assert summary["reproducibility_match"] is True

    assert summary["codex_final_product_handoff_ready"] is False


def test_scenario_matrix_contains_adversarial_loops(
    tmp_path: Path,
) -> None:
    result = build_assurance_mesh(
        _project(tmp_path),
        write_contracts=False,
    )

    scenarios = result["scenarios"]

    scenario_ids = {scenario["scenario_id"] for scenario in scenarios["scenarios"]}

    assert scenarios["scenario_count"] == 8

    assert scenarios["passed_scenario_count"] == 8

    assert {
        "stale_source_digest",
        "partial_source_approval",
        "missing_transaction_economics",
        "stale_outcome_template",
        "complete_pre_execution_inputs",
    }.issubset(scenario_ids)


def test_codex_manifest_drift_is_detected(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    artifact = project / "docs" / "data_contracts" / "permit_review.json"

    artifact.write_text(
        '{"value":"changed"}',
        encoding="utf-8",
    )

    result = build_assurance_mesh(
        project,
        write_contracts=False,
    )

    drift = result["drift"]

    assert drift["codex_manifest_drift_count"] == 1

    invariant_by_id = {row["invariant_id"]: row for row in result["invariants"]["results"]}

    assert invariant_by_id["codex_manifest_continuity"]["passed"] is False


def test_double_build_is_deterministic(
    tmp_path: Path,
) -> None:
    result = build_assurance_mesh(
        _project(tmp_path),
        write_contracts=False,
    )

    reproducibility = result["reproducibility"]

    assert reproducibility["build_count"] == 2

    assert reproducibility["reproducibility_match"] is True

    assert reproducibility["first_build_digest"] == reproducibility["second_build_digest"]

    assert reproducibility["input_mutation_count"] == 0

    assert reproducibility["database_write_count"] == 0
