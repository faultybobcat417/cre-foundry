from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cre_foundry.activation_state_model import (
    EXPECTED_DERIVED_ORDER,
    EXPECTED_INPUTS,
    EXPECTED_POLICY,
    EXPECTED_RULES,
    build_activation_state_model,
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


def _project(
    tmp_path: Path,
) -> Path:
    manual_summary = {
        "recommended_source_approval_ready": False,
        "client_input_complete_count": 0,
        "client_input_required_count": 5,
        "historical_registration_dry_run_ready": False,
        "outcome_ledger_ephemeral_bootstrap_ready": False,
    }

    _write_json(
        tmp_path / "docs" / "data_contracts" / "manual_activation_envelope_summary.json",
        manual_summary,
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "assurance_drift_report.json",
        {"outcome_template_continuity": True},
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "codex_handoff_gate_graph.json",
        {
            "codex_contract_handoff_ready": False,
            "codex_final_product_handoff_ready": False,
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "assurance_mesh_summary.json",
        {"model_version": "test"},
    )

    _write_json(
        tmp_path / "config" / "governance_decisions.json",
        {"decision_bundle_version": "test"},
    )

    mutations = [
        {
            "mutation_id": ("remove_source_review_from_history"),
            "gate": ("historical_registration_dry_run_ready"),
            "remove_prerequisite": ("source_review_complete"),
        },
        {
            "mutation_id": ("remove_template_from_outcome"),
            "gate": ("outcome_ledger_ephemeral_bootstrap_ready"),
            "remove_prerequisite": ("outcome_template_current"),
        },
        {
            "mutation_id": ("remove_client_inputs_from_codex"),
            "gate": ("codex_contract_handoff_ready"),
            "remove_prerequisite": ("client_inputs_complete"),
        },
        {
            "mutation_id": ("remove_ledger_from_labels"),
            "gate": ("real_outcome_labels_ready"),
            "remove_prerequisite": ("persistent_outcome_ledger_ready"),
        },
        {
            "mutation_id": ("remove_labels_from_point_in_time"),
            "gate": ("point_in_time_dataset_ready"),
            "remove_prerequisite": ("real_outcome_labels_ready"),
        },
        {
            "mutation_id": ("remove_economics_from_roi"),
            "gate": ("incremental_roi_proven"),
            "remove_prerequisite": ("transaction_economics_confirmed"),
        },
        {
            "mutation_id": ("remove_governance_from_final_handoff"),
            "gate": ("codex_final_product_handoff_ready"),
            "remove_prerequisite": ("production_governance_ready"),
        },
    ]

    _write_json(
        tmp_path / "config" / "activation_state_model.json",
        {
            "policy": EXPECTED_POLICY,
            "exogenous_inputs": EXPECTED_INPUTS,
            "derived_order": (EXPECTED_DERIVED_ORDER),
            "rules": EXPECTED_RULES,
            "critical_mutations": mutations,
        },
    )

    return tmp_path


def test_exhaustive_model_check_passes(
    tmp_path: Path,
) -> None:
    result = build_activation_state_model(
        _project(tmp_path),
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["enumerated_state_count"] == 16384

    assert summary["prerequisite_violation_count"] == 0

    assert summary["monotonicity_violation_count"] == 0

    assert summary["model_check_passed"] is True

    assert summary["reproducibility_match"] is True


def test_all_critical_mutants_are_killed(
    tmp_path: Path,
) -> None:
    result = build_activation_state_model(
        _project(tmp_path),
        write_contracts=False,
    )

    mutations = result["mutations"]

    assert mutations["mutation_count"] == 7

    assert mutations["killed_mutation_count"] == 7

    assert mutations["surviving_mutation_count"] == 0

    assert all(mutation["counterexample"] is not None for mutation in mutations["mutations"])


def test_chaos_scenarios_fail_closed(
    tmp_path: Path,
) -> None:
    result = build_activation_state_model(
        _project(tmp_path),
        write_contracts=False,
    )

    chaos = result["chaos"]

    assert chaos["scenario_count"] == 11

    assert chaos["passed_scenario_count"] == 11

    assert chaos["failed_scenario_count"] == 0

    assert all(scenario["unexpected_true_gates"] == [] for scenario in chaos["scenarios"])


def test_current_state_matches_existing_gates(
    tmp_path: Path,
) -> None:
    result = build_activation_state_model(
        _project(tmp_path),
        write_contracts=False,
    )

    rehearsal = result["rehearsal"]

    assert rehearsal["current_gate_mismatch_count"] == 0

    assert rehearsal["all_true_final_handoff_ready"] is True

    assert rehearsal["synthetic_only"] is True

    assert rehearsal["execution_count"] == 0

    assert _stable_digest(result["state_machine"]) != ""
