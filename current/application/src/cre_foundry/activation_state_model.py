from __future__ import annotations

import copy
import hashlib
import itertools
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

BoolMap = dict[str, bool]
RuleMap = dict[str, list[str]]


EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "exhaustive_state_enumeration_required": True,
    "transition_monotonicity_required": True,
    "prerequisite_integrity_required": True,
    "minimal_cut_set_analysis_required": True,
    "critical_rule_mutation_testing_required": True,
    "chaos_rehearsal_required": True,
    "current_state_reconciliation_required": True,
    "deterministic_double_build_required": True,
    "approval_invention_forbidden": True,
    "client_value_invention_forbidden": True,
    "database_access_enabled": False,
    "database_write_enabled": False,
    "snapshot_registration_enabled": False,
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


EXPECTED_INPUTS = [
    "source_review_complete",
    "client_inputs_complete",
    "outcome_template_current",
    "separate_execution_authorization",
    "schedule_and_acquisition_approval",
    "change_contract_approved",
    "separate_ledger_activation_authorization",
    "pilot_actions_and_windows_complete",
    "sufficient_history",
    "held_out_calibration_window",
    "client_pilot_authorization",
    "transaction_economics_confirmed",
    "monitoring_and_rollback_ready",
    "production_audit_ready",
]


EXPECTED_DERIVED_ORDER = [
    "historical_registration_dry_run_ready",
    "first_authoritative_snapshot_ready",
    "repeated_snapshot_collection_ready",
    "change_detection_ready",
    "outcome_ledger_ephemeral_bootstrap_ready",
    "persistent_outcome_ledger_ready",
    "real_outcome_labels_ready",
    "point_in_time_dataset_ready",
    "baseline_model_training_ready",
    "temporal_backtesting_ready",
    "probability_calibration_ready",
    "shadow_pilot_ready",
    "controlled_pilot_ready",
    "incremental_roi_proven",
    "codex_contract_handoff_ready",
    "production_governance_ready",
    "production_ranking_ready",
    "outreach_ready",
    "codex_final_product_handoff_ready",
]


EXPECTED_RULES: RuleMap = {
    "historical_registration_dry_run_ready": [
        "source_review_complete",
    ],
    "first_authoritative_snapshot_ready": [
        "historical_registration_dry_run_ready",
        "separate_execution_authorization",
    ],
    "repeated_snapshot_collection_ready": [
        "first_authoritative_snapshot_ready",
        "schedule_and_acquisition_approval",
    ],
    "change_detection_ready": [
        "repeated_snapshot_collection_ready",
        "change_contract_approved",
    ],
    "outcome_ledger_ephemeral_bootstrap_ready": [
        "client_inputs_complete",
        "outcome_template_current",
    ],
    "persistent_outcome_ledger_ready": [
        "outcome_ledger_ephemeral_bootstrap_ready",
        "separate_ledger_activation_authorization",
    ],
    "real_outcome_labels_ready": [
        "persistent_outcome_ledger_ready",
        "pilot_actions_and_windows_complete",
    ],
    "point_in_time_dataset_ready": [
        "repeated_snapshot_collection_ready",
        "change_detection_ready",
        "real_outcome_labels_ready",
    ],
    "baseline_model_training_ready": [
        "point_in_time_dataset_ready",
    ],
    "temporal_backtesting_ready": [
        "baseline_model_training_ready",
        "sufficient_history",
    ],
    "probability_calibration_ready": [
        "temporal_backtesting_ready",
        "held_out_calibration_window",
    ],
    "shadow_pilot_ready": [
        "probability_calibration_ready",
        "client_inputs_complete",
    ],
    "controlled_pilot_ready": [
        "shadow_pilot_ready",
        "client_pilot_authorization",
    ],
    "incremental_roi_proven": [
        "controlled_pilot_ready",
        "transaction_economics_confirmed",
    ],
    "codex_contract_handoff_ready": [
        "client_inputs_complete",
        "outcome_template_current",
    ],
    "production_governance_ready": [
        "incremental_roi_proven",
        "monitoring_and_rollback_ready",
        "production_audit_ready",
    ],
    "production_ranking_ready": [
        "probability_calibration_ready",
        "production_governance_ready",
    ],
    "outreach_ready": [
        "controlled_pilot_ready",
        "production_governance_ready",
    ],
    "codex_final_product_handoff_ready": [
        "codex_contract_handoff_ready",
        "incremental_roi_proven",
        "production_governance_ready",
    ],
}


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _object_list(
    value: object,
    *,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(f"{label} must be a list.")

    rows: list[dict[str, Any]] = []

    for index, raw_row in enumerate(value):
        if not isinstance(
            raw_row,
            dict,
        ):
            raise RuntimeError(f"{label}[{index}] must be an object.")

        rows.append({str(key): row_value for key, row_value in raw_row.items()})

    return rows


def _string_list(
    value: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(f"{label} must be a list.")

    values: list[str] = []

    for index, raw_value in enumerate(value):
        if not isinstance(
            raw_value,
            str,
        ):
            raise RuntimeError(f"{label}[{index}] must be a string.")

        values.append(raw_value)

    return values


def _rule_map(
    value: object,
) -> RuleMap:
    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError("Rules must be an object.")

    rules: RuleMap = {}

    for raw_gate, raw_prerequisites in value.items():
        if not isinstance(
            raw_gate,
            str,
        ):
            raise RuntimeError("Rule gate must be a string.")

        rules[raw_gate] = _string_list(
            raw_prerequisites,
            label=f"rules.{raw_gate}",
        )

    return rules


def _stable_digest(
    value: object,
) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(canonical).hexdigest()


def _enumerate_input_states(
    input_names: list[str],
) -> Iterator[BoolMap]:
    for values in itertools.product(
        (False, True),
        repeat=len(input_names),
    ):
        yield dict(
            zip(
                input_names,
                values,
                strict=True,
            )
        )


def _validate_rule_graph(
    *,
    inputs: list[str],
    derived_order: list[str],
    rules: RuleMap,
) -> dict[str, Any]:
    if len(inputs) != len(set(inputs)):
        raise RuntimeError("Duplicate exogenous inputs exist.")

    if len(derived_order) != len(set(derived_order)):
        raise RuntimeError("Duplicate derived gates exist.")

    if set(rules) != set(derived_order):
        raise RuntimeError("Rule gates and derived order differ.")

    known = set(inputs)
    invalid_references: list[str] = []
    empty_rules: list[str] = []

    edges: list[dict[str, str]] = []

    for gate in derived_order:
        prerequisites = rules[gate]

        if not prerequisites:
            empty_rules.append(gate)

        for prerequisite in prerequisites:
            if prerequisite not in known:
                invalid_references.append(f"{prerequisite}->{gate}")

            edges.append(
                {
                    "from": prerequisite,
                    "to": gate,
                }
            )

        known.add(gate)

    return {
        "input_count": len(inputs),
        "derived_gate_count": len(derived_order),
        "rule_count": len(rules),
        "edge_count": len(edges),
        "invalid_reference_count": len(invalid_references),
        "invalid_references": sorted(invalid_references),
        "empty_rule_count": len(empty_rules),
        "empty_rules": sorted(empty_rules),
        "valid": bool(not invalid_references and not empty_rules),
        "edges": edges,
    }


def _evaluate(
    *,
    inputs: BoolMap,
    derived_order: list[str],
    rules: RuleMap,
) -> BoolMap:
    state = dict(inputs)

    for gate in derived_order:
        prerequisites = rules[gate]

        state[gate] = all(
            state.get(
                prerequisite,
                False,
            )
            for prerequisite in prerequisites
        )

    return state


def _prerequisite_violations(
    *,
    state: BoolMap,
    derived_order: list[str],
    rules: RuleMap,
) -> list[str]:
    violations: list[str] = []

    for gate in derived_order:
        if not state[gate]:
            continue

        for prerequisite in rules[gate]:
            if not state.get(
                prerequisite,
                False,
            ):
                violations.append(f"{gate} without {prerequisite}")

    return violations


def _minimal_cut_sets(
    *,
    input_names: list[str],
    derived_order: list[str],
    rules: RuleMap,
    target_gate: str,
) -> list[list[str]]:
    all_true = {input_name: True for input_name in input_names}

    baseline = _evaluate(
        inputs=all_true,
        derived_order=derived_order,
        rules=rules,
    )

    if not baseline[target_gate]:
        raise RuntimeError(f"All-true state does not open {target_gate}.")

    cuts: list[list[str]] = []

    for input_name in input_names:
        candidate = dict(all_true)

        candidate[input_name] = False

        result = _evaluate(
            inputs=candidate,
            derived_order=derived_order,
            rules=rules,
        )

        if not result[target_gate]:
            cuts.append([input_name])

    remaining = [input_name for input_name in input_names if [input_name] not in cuts]

    for first_index, first_name in enumerate(remaining):
        for second_name in remaining[first_index + 1 :]:
            candidate = dict(all_true)

            candidate[first_name] = False

            candidate[second_name] = False

            result = _evaluate(
                inputs=candidate,
                derived_order=derived_order,
                rules=rules,
            )

            if not result[target_gate]:
                cuts.append(
                    sorted(
                        [
                            first_name,
                            second_name,
                        ]
                    )
                )

    return sorted(
        cuts,
        key=lambda row: (
            len(row),
            row,
        ),
    )


def _find_mutant_counterexample(
    *,
    input_names: list[str],
    derived_order: list[str],
    original_rules: RuleMap,
    mutated_rules: RuleMap,
    target_gate: str,
) -> dict[str, Any] | None:
    for inputs in _enumerate_input_states(input_names):
        original = _evaluate(
            inputs=inputs,
            derived_order=derived_order,
            rules=original_rules,
        )

        mutated = _evaluate(
            inputs=inputs,
            derived_order=derived_order,
            rules=mutated_rules,
        )

        if mutated[target_gate] and not original[target_gate]:
            return {
                "inputs": inputs,
                "original_gate_value": (original[target_gate]),
                "mutated_gate_value": (mutated[target_gate]),
            }

    return None


def _build_payloads(
    project_root: Path,
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    input_names = _string_list(
        config.get("exogenous_inputs"),
        label="exogenous_inputs",
    )

    derived_order = _string_list(
        config.get("derived_order"),
        label="derived_order",
    )

    rules = _rule_map(config.get("rules"))

    mutation_rows = _object_list(
        config.get("critical_mutations"),
        label="critical_mutations",
    )

    if input_names != EXPECTED_INPUTS:
        raise RuntimeError("Activation inputs differ from expected model.")

    if derived_order != EXPECTED_DERIVED_ORDER:
        raise RuntimeError("Derived gate order differs from expected model.")

    if rules != EXPECTED_RULES:
        raise RuntimeError("Activation rules differ from expected model.")

    graph_report = _validate_rule_graph(
        inputs=input_names,
        derived_order=derived_order,
        rules=rules,
    )

    if not graph_report["valid"]:
        raise RuntimeError("Activation rule graph is invalid.")

    state_count = 0
    prerequisite_check_count = 0
    prerequisite_violations: list[dict[str, Any]] = []

    monotonicity_check_count = 0
    monotonicity_violations: list[dict[str, Any]] = []

    gate_true_counts = {gate: 0 for gate in derived_order}

    for inputs in _enumerate_input_states(input_names):
        state_count += 1

        state = _evaluate(
            inputs=inputs,
            derived_order=derived_order,
            rules=rules,
        )

        for gate in derived_order:
            if state[gate]:
                gate_true_counts[gate] += 1

        violations = _prerequisite_violations(
            state=state,
            derived_order=derived_order,
            rules=rules,
        )

        prerequisite_check_count += len(derived_order)

        if violations:
            prerequisite_violations.append(
                {
                    "inputs": inputs,
                    "violations": violations,
                }
            )

        for input_name in input_names:
            if inputs[input_name]:
                continue

            monotonicity_check_count += 1

            increased_inputs = dict(inputs)

            increased_inputs[input_name] = True

            increased_state = _evaluate(
                inputs=increased_inputs,
                derived_order=derived_order,
                rules=rules,
            )

            regressed_gates = [
                gate for gate in derived_order if (state[gate] and not increased_state[gate])
            ]

            if regressed_gates:
                monotonicity_violations.append(
                    {
                        "input_changed": (input_name),
                        "inputs_before": (inputs),
                        "regressed_gates": (regressed_gates),
                    }
                )

    model_check_report: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-model-check-v1"),
        "exogenous_input_count": len(input_names),
        "derived_gate_count": len(derived_order),
        "enumerated_state_count": (state_count),
        "expected_state_count": (2 ** len(input_names)),
        "prerequisite_check_count": (prerequisite_check_count),
        "prerequisite_violation_count": len(prerequisite_violations),
        "prerequisite_violations": (prerequisite_violations),
        "monotonicity_check_count": (monotonicity_check_count),
        "monotonicity_violation_count": len(monotonicity_violations),
        "monotonicity_violations": (monotonicity_violations),
        "gate_true_counts": (gate_true_counts),
        "model_check_passed": bool(
            state_count == 2 ** len(input_names)
            and not prerequisite_violations
            and not monotonicity_violations
        ),
    }

    final_cut_sets = _minimal_cut_sets(
        input_names=input_names,
        derived_order=derived_order,
        rules=rules,
        target_gate=("codex_final_product_handoff_ready"),
    )

    historical_cut_sets = _minimal_cut_sets(
        input_names=input_names,
        derived_order=derived_order,
        rules=rules,
        target_gate=("historical_registration_dry_run_ready"),
    )

    outcome_cut_sets = _minimal_cut_sets(
        input_names=input_names,
        derived_order=derived_order,
        rules=rules,
        target_gate=("outcome_ledger_ephemeral_bootstrap_ready"),
    )

    cut_set_report: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-minimal-cut-sets-v1"),
        "targets": [
            {
                "target_gate": ("historical_registration_dry_run_ready"),
                "minimal_cut_set_count": len(historical_cut_sets),
                "minimal_cut_sets": (historical_cut_sets),
            },
            {
                "target_gate": ("outcome_ledger_ephemeral_bootstrap_ready"),
                "minimal_cut_set_count": len(outcome_cut_sets),
                "minimal_cut_sets": (outcome_cut_sets),
            },
            {
                "target_gate": ("codex_final_product_handoff_ready"),
                "minimal_cut_set_count": len(final_cut_sets),
                "minimal_cut_sets": (final_cut_sets),
            },
        ],
    }

    mutation_results: list[dict[str, Any]] = []

    for mutation in mutation_rows:
        mutation_id = str(mutation["mutation_id"])

        gate = str(mutation["gate"])

        removed_prerequisite = str(mutation["remove_prerequisite"])

        if gate not in rules:
            raise RuntimeError(f"Mutation gate is invalid: {gate}")

        if removed_prerequisite not in rules[gate]:
            raise RuntimeError(f"Mutation prerequisite does not exist: {mutation_id}")

        mutated_rules = copy.deepcopy(rules)

        mutated_rules[gate] = [
            prerequisite
            for prerequisite in mutated_rules[gate]
            if prerequisite != removed_prerequisite
        ]

        counterexample = _find_mutant_counterexample(
            input_names=input_names,
            derived_order=derived_order,
            original_rules=rules,
            mutated_rules=mutated_rules,
            target_gate=gate,
        )

        mutation_results.append(
            {
                "mutation_id": mutation_id,
                "gate": gate,
                "removed_prerequisite": (removed_prerequisite),
                "mutant_killed": (counterexample is not None),
                "counterexample": (counterexample),
            }
        )

    mutation_report: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-mutation-report-v1"),
        "mutation_count": len(mutation_results),
        "killed_mutation_count": sum(bool(result["mutant_killed"]) for result in mutation_results),
        "surviving_mutation_count": sum(
            not bool(result["mutant_killed"]) for result in mutation_results
        ),
        "mutations": mutation_results,
    }

    all_true_inputs = {input_name: True for input_name in input_names}

    all_true_state = _evaluate(
        inputs=all_true_inputs,
        derived_order=derived_order,
        rules=rules,
    )

    chaos_definitions = [
        {
            "scenario_id": ("stale_source_review"),
            "disable": ["source_review_complete"],
            "expected_false": [
                ("historical_registration_dry_run_ready"),
                ("first_authoritative_snapshot_ready"),
                ("repeated_snapshot_collection_ready"),
                "point_in_time_dataset_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("missing_client_inputs"),
            "disable": ["client_inputs_complete"],
            "expected_false": [
                ("outcome_ledger_ephemeral_bootstrap_ready"),
                ("persistent_outcome_ledger_ready"),
                "shadow_pilot_ready",
                "codex_contract_handoff_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("stale_outcome_template"),
            "disable": ["outcome_template_current"],
            "expected_false": [
                ("outcome_ledger_ephemeral_bootstrap_ready"),
                ("persistent_outcome_ledger_ready"),
                "codex_contract_handoff_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("execution_authorization_revoked"),
            "disable": [("separate_execution_authorization")],
            "expected_false": [
                ("first_authoritative_snapshot_ready"),
                ("repeated_snapshot_collection_ready"),
                "change_detection_ready",
                "point_in_time_dataset_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("schedule_and_acquisition_revoked"),
            "disable": [("schedule_and_acquisition_approval")],
            "expected_false": [
                ("repeated_snapshot_collection_ready"),
                "change_detection_ready",
                "point_in_time_dataset_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("ledger_activation_revoked"),
            "disable": [("separate_ledger_activation_authorization")],
            "expected_false": [
                ("persistent_outcome_ledger_ready"),
                "real_outcome_labels_ready",
                "point_in_time_dataset_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("observation_windows_incomplete"),
            "disable": [("pilot_actions_and_windows_complete")],
            "expected_false": [
                "real_outcome_labels_ready",
                "point_in_time_dataset_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("insufficient_history"),
            "disable": ["sufficient_history"],
            "expected_false": [
                "temporal_backtesting_ready",
                "probability_calibration_ready",
                "controlled_pilot_ready",
                "incremental_roi_proven",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("transaction_economics_missing"),
            "disable": [("transaction_economics_confirmed")],
            "expected_false": [
                "incremental_roi_proven",
                "production_governance_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("monitoring_and_rollback_missing"),
            "disable": [("monitoring_and_rollback_ready")],
            "expected_false": [
                "production_governance_ready",
                "production_ranking_ready",
                "outreach_ready",
                "codex_final_product_handoff_ready",
            ],
        },
        {
            "scenario_id": ("production_audit_missing"),
            "disable": ["production_audit_ready"],
            "expected_false": [
                "production_governance_ready",
                "production_ranking_ready",
                "outreach_ready",
                "codex_final_product_handoff_ready",
            ],
        },
    ]

    chaos_results: list[dict[str, Any]] = []

    for definition in chaos_definitions:
        scenario_inputs = dict(all_true_inputs)

        disabled_inputs = _string_list(
            definition["disable"],
            label="chaos disable inputs",
        )

        expected_false = _string_list(
            definition["expected_false"],
            label="chaos expected false gates",
        )

        for input_name in disabled_inputs:
            scenario_inputs[input_name] = False

        state = _evaluate(
            inputs=scenario_inputs,
            derived_order=derived_order,
            rules=rules,
        )

        unexpected_true = [gate for gate in expected_false if state[gate]]

        chaos_results.append(
            {
                "scenario_id": (definition["scenario_id"]),
                "disabled_inputs": (disabled_inputs),
                "expected_false_gates": (expected_false),
                "unexpected_true_gates": (unexpected_true),
                "passed": (not unexpected_true),
            }
        )

    chaos_report: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-chaos-matrix-v1"),
        "scenario_count": len(chaos_results),
        "passed_scenario_count": sum(bool(result["passed"]) for result in chaos_results),
        "failed_scenario_count": sum(not bool(result["passed"]) for result in chaos_results),
        "scenarios": chaos_results,
        "execution_count": 0,
    }

    contract_root = project_root / "docs" / "data_contracts"

    manual_summary = _load_object(contract_root / "manual_activation_envelope_summary.json")

    drift = _load_object(contract_root / "assurance_drift_report.json")

    codex_graph = _load_object(contract_root / "codex_handoff_gate_graph.json")

    client_complete_count = int(
        manual_summary.get(
            "client_input_complete_count",
            0,
        )
    )

    client_required_count = int(
        manual_summary.get(
            "client_input_required_count",
            0,
        )
    )

    current_inputs: BoolMap = {
        "source_review_complete": bool(
            manual_summary.get("recommended_source_approval_ready") is True
        ),
        "client_inputs_complete": bool(
            client_required_count > 0 and client_complete_count == client_required_count
        ),
        "outcome_template_current": bool(drift.get("outcome_template_continuity") is True),
        "separate_execution_authorization": False,
        "schedule_and_acquisition_approval": False,
        "change_contract_approved": False,
        "separate_ledger_activation_authorization": False,
        "pilot_actions_and_windows_complete": False,
        "sufficient_history": False,
        "held_out_calibration_window": False,
        "client_pilot_authorization": False,
        "transaction_economics_confirmed": False,
        "monitoring_and_rollback_ready": False,
        "production_audit_ready": False,
    }

    current_state = _evaluate(
        inputs=current_inputs,
        derived_order=derived_order,
        rules=rules,
    )

    existing_gate_values = {
        "historical_registration_dry_run_ready": bool(
            manual_summary.get("historical_registration_dry_run_ready") is True
        ),
        "outcome_ledger_ephemeral_bootstrap_ready": bool(
            manual_summary.get("outcome_ledger_ephemeral_bootstrap_ready") is True
        ),
        "codex_contract_handoff_ready": bool(
            codex_graph.get("codex_contract_handoff_ready") is True
        ),
        "codex_final_product_handoff_ready": bool(
            codex_graph.get("codex_final_product_handoff_ready") is True
        ),
    }

    reconciliation_rows = [
        {
            "gate": gate,
            "modeled_value": (current_state[gate]),
            "existing_value": (existing_value),
            "match": bool(current_state[gate] == existing_value),
        }
        for gate, existing_value in existing_gate_values.items()
    ]

    current_report: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-rehearsal-states-v1"),
        "current_inputs": current_inputs,
        "current_state": current_state,
        "current_gate_reconciliation": (reconciliation_rows),
        "current_gate_reconciliation_count": len(reconciliation_rows),
        "current_gate_mismatch_count": sum(not bool(row["match"]) for row in reconciliation_rows),
        "all_true_inputs": (all_true_inputs),
        "all_true_state": (all_true_state),
        "all_true_final_handoff_ready": bool(all_true_state["codex_final_product_handoff_ready"]),
        "synthetic_only": True,
        "execution_count": 0,
    }

    transition_rows = [
        {
            "gate": gate,
            "prerequisites": rules[gate],
            "prerequisite_count": len(rules[gate]),
            "true_state_count": (gate_true_counts[gate]),
            "true_state_fraction": (gate_true_counts[gate] / state_count),
        }
        for gate in derived_order
    ]

    transition_report: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-transition-matrix-v1"),
        "gate_count": len(transition_rows),
        "transitions": (transition_rows),
        "graph": graph_report,
    }

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-state-model-v1"),
        "exogenous_input_count": len(input_names),
        "derived_gate_count": len(derived_order),
        "enumerated_state_count": (state_count),
        "prerequisite_check_count": (prerequisite_check_count),
        "prerequisite_violation_count": len(prerequisite_violations),
        "monotonicity_check_count": (monotonicity_check_count),
        "monotonicity_violation_count": len(monotonicity_violations),
        "mutation_count": (mutation_report["mutation_count"]),
        "killed_mutation_count": (mutation_report["killed_mutation_count"]),
        "surviving_mutation_count": (mutation_report["surviving_mutation_count"]),
        "chaos_scenario_count": (chaos_report["scenario_count"]),
        "passed_chaos_scenario_count": (chaos_report["passed_scenario_count"]),
        "failed_chaos_scenario_count": (chaos_report["failed_scenario_count"]),
        "current_gate_mismatch_count": (current_report["current_gate_mismatch_count"]),
        "final_handoff_minimal_cut_set_count": len(final_cut_sets),
        "all_true_final_handoff_ready": (current_report["all_true_final_handoff_ready"]),
        "model_check_passed": bool(
            model_check_report["model_check_passed"]
            and mutation_report["surviving_mutation_count"] == 0
            and chaos_report["failed_scenario_count"] == 0
            and current_report["current_gate_mismatch_count"] == 0
        ),
        "current_historical_dry_run_ready": (
            current_state["historical_registration_dry_run_ready"]
        ),
        "current_outcome_bootstrap_ready": (
            current_state["outcome_ledger_ephemeral_bootstrap_ready"]
        ),
        "current_codex_contract_handoff_ready": (current_state["codex_contract_handoff_ready"]),
        "current_codex_final_handoff_ready": (current_state["codex_final_product_handoff_ready"]),
        "automatic_approval_count": 0,
        "client_value_invention_count": 0,
        "input_mutation_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "automatic_acquisition_count": 0,
        "persistent_outcome_database_creation_count": 0,
        "outcome_event_insertion_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "policy": EXPECTED_POLICY,
    }

    state_machine: dict[str, Any] = {
        "model_version": ("cre-foundry-activation-state-machine-v1"),
        "exogenous_inputs": input_names,
        "derived_order": derived_order,
        "rules": rules,
        "target_gate": ("codex_final_product_handoff_ready"),
        "state_count": (2 ** len(input_names)),
        "graph": graph_report,
    }

    return {
        "state_machine": state_machine,
        "model_check": model_check_report,
        "transitions": transition_report,
        "cut_sets": cut_set_report,
        "mutations": mutation_report,
        "chaos": chaos_report,
        "rehearsal": current_report,
        "summary": summary,
    }


def build_activation_state_model(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "activation_state_model.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Activation-state policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Activation-state policy mismatch.")

    first = _build_payloads(
        project_root,
        config,
    )

    second = _build_payloads(
        project_root,
        config,
    )

    first_digest = _stable_digest(first)

    second_digest = _stable_digest(second)

    reproducibility_match = bool(first_digest == second_digest)

    first["summary"]["first_build_digest"] = first_digest

    first["summary"]["second_build_digest"] = second_digest

    first["summary"]["reproducibility_match"] = reproducibility_match

    first["summary"]["model_check_passed"] = bool(
        first["summary"]["model_check_passed"] and reproducibility_match
    )

    if write_contracts:
        root = project_root / "docs" / "data_contracts"

        _atomic_json(
            root / "activation_state_machine.json",
            first["state_machine"],
        )

        _atomic_json(
            root / "activation_model_check_report.json",
            first["model_check"],
        )

        _atomic_json(
            root / "activation_transition_matrix.json",
            first["transitions"],
        )

        _atomic_json(
            root / "activation_minimal_cut_sets.json",
            first["cut_sets"],
        )

        _atomic_json(
            root / "activation_mutation_report.json",
            first["mutations"],
        )

        _atomic_json(
            root / "activation_chaos_matrix.json",
            first["chaos"],
        )

        _atomic_json(
            root / "activation_rehearsal_states.json",
            first["rehearsal"],
        )

        _atomic_json(
            root / "activation_state_model_summary.json",
            first["summary"],
        )

        summary = first["summary"]

        _atomic_text(
            root / "activation_state_model.md",
            "\n".join(
                [
                    "# Activation State Model",
                    "",
                    (
                        "The complete activation gate system "
                        "is exhaustively enumerated and checked "
                        "as a monotone Boolean state machine."
                    ),
                    "",
                    (f"- Exogenous inputs: `{summary['exogenous_input_count']}`"),
                    (f"- Derived gates: `{summary['derived_gate_count']}`"),
                    (f"- Enumerated states: `{summary['enumerated_state_count']}`"),
                    (f"- Prerequisite checks: `{summary['prerequisite_check_count']}`"),
                    (f"- Monotonicity checks: `{summary['monotonicity_check_count']}`"),
                    (f"- Critical mutants killed: `{summary['killed_mutation_count']}`"),
                    (f"- Chaos scenarios passed: `{summary['passed_chaos_scenario_count']}`"),
                    (f"- Current-state mismatches: `{summary['current_gate_mismatch_count']}`"),
                    (
                        "- Deterministic double build: "
                        f"`{str(summary['reproducibility_match']).lower()}`"
                    ),
                    (f"- Model check passed: `{str(summary['model_check_passed']).lower()}`"),
                    "",
                    (
                        "- Current historical dry-run ready: "
                        f"`{str(summary['current_historical_dry_run_ready']).lower()}`"
                    ),
                    (
                        "- Current outcome bootstrap ready: "
                        f"`{str(summary['current_outcome_bootstrap_ready']).lower()}`"
                    ),
                    (
                        "- Current Codex contract handoff ready: "
                        f"`{str(summary['current_codex_contract_handoff_ready']).lower()}`"
                    ),
                    (
                        "- Current Codex final handoff ready: "
                        f"`{str(summary['current_codex_final_handoff_ready']).lower()}`"
                    ),
                    "",
                    "- Automatic approvals: `0`",
                    "- Invented client values: `0`",
                    "- Input mutations: `0`",
                    "- Database accesses: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Model training executions: `0`",
                    "- Pilot executions: `0`",
                    "- Production rankings: `0`",
                    "- Outreach executions: `0`",
                    "",
                ]
            ),
        )

    return first
