from __future__ import annotations

import copy
import json
from pathlib import Path

from cre_foundry.manual_activation_envelopes import build_manual_activation_envelopes


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _policy() -> dict[str, object]:
    return {
        "operating_mode": "shadow",
        "validation_only": True,
        "exact_evidence_digest_required": True,
        "stale_approval_rejection_required": True,
        "complete_reviewer_attribution_required": True,
        "complete_client_attribution_required": True,
        "automatic_approval_enabled": False,
        "automatic_value_invention_enabled": False,
        "historical_registration_execution_enabled": False,
        "persistent_outcome_ledger_enabled": False,
        "source_schedule_activation_enabled": False,
        "automatic_acquisition_enabled": False,
        "point_in_time_materialization_enabled": False,
        "model_training_enabled": False,
        "backtest_execution_enabled": False,
        "pilot_execution_enabled": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
        "codex_final_handoff_enabled": False,
    }


def _project(tmp_path: Path) -> Path:
    _write_json(
        tmp_path / "config" / "manual_activation_envelopes.json",
        {
            "policy": _policy(),
            "decision_bundle_path": "config/governance_decisions.json",
            "recommended_first_registration_source_id": "source-1",
            "historical_registration_limits": {
                "maximum_source_count": 1,
                "maximum_snapshot_count": 1,
                "dry_run_only": True,
                "automatic_retry_enabled": False,
            },
            "codex_handoff_policy": {
                "contract_handoff_requires_all_client_inputs": True,
                "contract_handoff_requires_governance_contracts": True,
                "final_handoff_requires_incremental_roi_proof": True,
                "final_handoff_requires_controlled_pilot": True,
                "final_handoff_requires_production_governance": True,
            },
        },
    )
    root = tmp_path / "docs" / "data_contracts"
    _write_json(
        root / "governance_approval_packet_template.json",
        {
            "packets": [
                {
                    "source_id": "source-1",
                    "evidence_bundle_digest": "a" * 64,
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
            "sections": [
                {"input_id": input_id, "required_fields": ["value"]} for input_id in input_ids
            ],
            "questionnaire_digest": "e" * 64,
        },
    )
    _write_json(
        root / "historical_registration_request_template.json",
        {
            "source_id": "source-1",
            "expected_evidence_bundle_digest": "a" * 64,
            "artifact_sha256": "b" * 64,
            "dataset_digest": "c" * 64,
        },
    )
    _write_json(
        root / "outcome_ledger_activation_request_template.json",
        {
            "enabled": False,
            "outcome_schema_fingerprint": "d" * 64,
            "client_questionnaire_digest": "e" * 64,
        },
    )
    _write_json(root / "outcome_collection_contract.json", {"schema_fingerprint": "d" * 64})
    _write_json(
        tmp_path / "config" / "governance_decisions.json",
        {
            "decision_bundle_version": "cre-foundry-governance-decisions-v1",
            "source_decisions": [
                {
                    "source_id": "source-1",
                    "evidence_bundle_digest": "a" * 64,
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


def _load_decisions(project: Path) -> dict[str, object]:
    raw = json.loads((project / "config" / "governance_decisions.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return copy.deepcopy(raw)


def test_pending_bundle_keeps_every_gate_closed(tmp_path: Path) -> None:
    result = build_manual_activation_envelopes(_project(tmp_path), write_contracts=False)
    summary = result["summary"]
    assert summary["source_decision_complete_count"] == 0
    assert summary["client_input_complete_count"] == 0
    assert summary["historical_registration_dry_run_ready"] is False
    assert summary["outcome_ledger_ephemeral_bootstrap_ready"] is False
    assert summary["codex_contract_handoff_ready"] is False
    assert summary["codex_final_product_handoff_ready"] is False


def test_approved_source_opens_only_dry_run_gate(tmp_path: Path) -> None:
    project = _project(tmp_path)
    decisions = _load_decisions(project)
    source_decisions = decisions["source_decisions"]
    assert isinstance(source_decisions, list)
    source = source_decisions[0]
    assert isinstance(source, dict)
    source.update(
        {
            "parser_contract_approved": True,
            "schema_contract_approved": True,
            "approved_record_key": "id",
            "approved_temporal_fields": ["observed_at"],
            "capture_policy_approved": True,
            "change_contract_approved": True,
            "registration_approved": True,
            "reviewer_id": "reviewer-1",
            "reviewed_at": "2026-07-27T12:00:00-04:00",
            "evidence_reference": "review-record-1",
        }
    )
    _write_json(project / "config" / "governance_decisions.json", decisions)
    result = build_manual_activation_envelopes(project, write_contracts=False)
    summary = result["summary"]
    historical = result["historical_envelope"]
    assert summary["source_decision_complete_count"] == 1
    assert summary["historical_registration_dry_run_ready"] is True
    assert historical["approval_ready"] is True
    assert historical["dry_run_ready"] is True
    assert historical["authoritative_execution_enabled"] is False
    assert historical["registration_execution_count"] == 0


def test_stale_digest_blocks_source_approval(tmp_path: Path) -> None:
    project = _project(tmp_path)
    decisions = _load_decisions(project)
    source_decisions = decisions["source_decisions"]
    assert isinstance(source_decisions, list)
    source = source_decisions[0]
    assert isinstance(source, dict)
    source["evidence_bundle_digest"] = "f" * 64
    _write_json(project / "config" / "governance_decisions.json", decisions)
    result = build_manual_activation_envelopes(project, write_contracts=False)
    validation = result["validation"]
    assert validation["stale_source_decision_count"] == 1
    assert validation["recommended_source_approval_ready"] is False


def test_complete_client_inputs_open_only_ephemeral_gate(tmp_path: Path) -> None:
    project = _project(tmp_path)
    decisions = _load_decisions(project)
    client_inputs = decisions["client_inputs"]
    assert isinstance(client_inputs, list)
    for client_input in client_inputs:
        assert isinstance(client_input, dict)
        client_input.update(
            {
                "authoritative_value": {"value": "confirmed"},
                "confirmed": True,
                "confirmed_by": "client-authority",
                "confirmed_at": "2026-07-27T12:00:00-04:00",
                "evidence_reference": "client-record",
            }
        )
    _write_json(project / "config" / "governance_decisions.json", decisions)
    result = build_manual_activation_envelopes(project, write_contracts=False)
    summary = result["summary"]
    outcome = result["outcome_envelope"]
    assert summary["client_input_complete_count"] == 5
    assert summary["outcome_ledger_ephemeral_bootstrap_ready"] is True
    assert summary["codex_contract_handoff_ready"] is True
    assert outcome["ephemeral_bootstrap_ready"] is True
    assert outcome["persistent_database_creation_enabled"] is False
    assert outcome["event_insertion_count"] == 0
    assert summary["codex_final_product_handoff_ready"] is False


def test_stale_outcome_template_blocks_bootstrap(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    decisions = _load_decisions(project)

    client_inputs = decisions["client_inputs"]

    assert isinstance(
        client_inputs,
        list,
    )

    for client_input in client_inputs:
        assert isinstance(
            client_input,
            dict,
        )

        client_input.update(
            {
                "authoritative_value": {"value": "confirmed"},
                "confirmed": True,
                "confirmed_by": ("client-authority"),
                "confirmed_at": ("2026-07-27T12:00:00-04:00"),
                "evidence_reference": ("client-record"),
            }
        )

    _write_json(
        project / "config" / "governance_decisions.json",
        decisions,
    )

    _write_json(
        project / "docs" / "data_contracts" / "outcome_ledger_activation_request_template.json",
        {
            "enabled": False,
            "outcome_schema_fingerprint": ("d" * 64),
            "client_questionnaire_digest": ("f" * 64),
        },
    )

    result = build_manual_activation_envelopes(
        project,
        write_contracts=False,
    )

    summary = result["summary"]

    outcome = result["outcome_envelope"]

    assert summary["client_input_complete_count"] == 5

    assert outcome["ephemeral_bootstrap_ready"] is False

    assert summary["codex_contract_handoff_ready"] is False

    assert summary["codex_final_product_handoff_ready"] is False


def test_missing_transaction_economics_blocks_codex_handoff(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    decisions = _load_decisions(project)

    client_inputs = decisions["client_inputs"]

    assert isinstance(
        client_inputs,
        list,
    )

    completed_count = 0

    for client_input in client_inputs:
        assert isinstance(
            client_input,
            dict,
        )

        if client_input["input_id"] == "transaction_economics":
            continue

        client_input.update(
            {
                "authoritative_value": {"value": "confirmed"},
                "confirmed": True,
                "confirmed_by": ("client-authority"),
                "confirmed_at": ("2026-07-27T12:00:00-04:00"),
                "evidence_reference": ("client-record"),
            }
        )

        completed_count += 1

    assert completed_count == 4

    _write_json(
        project / "config" / "governance_decisions.json",
        decisions,
    )

    result = build_manual_activation_envelopes(
        project,
        write_contracts=False,
    )

    summary = result["summary"]

    outcome = result["outcome_envelope"]

    assert summary["client_input_complete_count"] == 4

    assert summary["outcome_ledger_ephemeral_bootstrap_ready"] is False

    assert outcome["all_client_inputs_complete"] is False

    assert outcome["ephemeral_bootstrap_ready"] is False

    assert summary["codex_contract_handoff_ready"] is False

    assert summary["codex_final_product_handoff_ready"] is False
