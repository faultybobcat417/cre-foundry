"""Validate MATH-001 without trusting stored PASS labels.

Normal mode is read-only and emits exactly PASS or FAIL.  ``--known-bad``
applies a declarative mutation to an in-memory copy of the estimand registry
and emits the strict mutation payload expected by the frontier evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "artifacts/math/estimand_registry.json"
SCHEMA = ROOT / "contracts/estimand_registry.schema.json"
REPORT = ROOT / "artifacts/evaluations/math_contracts.json"
AUTHORITY_TEMPLATE = ROOT / "artifacts/math/human_authority_input_template.json"
AUTHORITY_SCHEMA = ROOT / "contracts/math_authority_input.schema.json"

REQUIRED_ESTIMANDS = {
    "EST-F9-BASELINE-RATE",
    "EST-F9-BASELINE-VARIANCE",
    "EST-F9-ITT",
    "EST-PREDICTIVE-F9-RISK",
    "EST-POWER-SAMPLE-SIZE",
    "EST-RISK-ADJUSTED-NET-VALUE",
}
INPUT_SIGNATURES = {
    "baseline_f9_rate": ("p0", "ACCESS_DEPENDENT", "bookings_per_route_day", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "baseline_f9_variance": ("sigma2", "ACCESS_DEPENDENT", "bookings_squared_per_route_day", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "incremental_f9_effect": ("tau", "EMPIRICAL_ONLY", "bookings_per_route_day", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "predictive_f9_risk": ("p_f9", "EMPIRICAL_ONLY", "probability", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "f9_maturity_horizon_days": ("W", "HUMAN_AUTHORITATIVE", "days", "GATE-OUTCOME-LABELS-MATURITY-001", {"human_authoritative"}),
    "candidate_incremental_effect": ("delta_i", "EMPIRICAL_ONLY", "incremental_bookings_per_candidate", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "attendance_probability": ("p_attend", "EMPIRICAL_ONLY", "probability", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "mandate_probability": ("p_mandate", "EMPIRICAL_ONLY", "probability", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "transaction_probability": ("p_transaction", "EMPIRICAL_ONLY", "probability", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "expected_commission": ("commission", "ACCESS_DEPENDENT", "currency_per_transaction", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "incremental_operational_cost": ("cost", "ACCESS_DEPENDENT", "currency_per_candidate", "firm_economics_services_territories", {"unknown", "measured"}),
    "risk_uncertainty_penalty": ("risk", "EMPIRICAL_ONLY", "currency_per_candidate", "GATE-FULL-EXTERNAL-EVIDENCE-001", {"unknown", "measured"}),
    "risk_aversion_policy": ("lambda", "HUMAN_AUTHORITATIVE", "dimensionless_utility_weight", "firm_economics_services_territories", {"human_authoritative"}),
    "minimum_meaningful_absolute_lift": ("Delta", "HUMAN_AUTHORITATIVE", "bookings_per_route_day", "firm_economics_services_territories", {"human_authoritative"}),
    "alpha": ("alpha", "HUMAN_AUTHORITATIVE", "probability", "GATE-EXPERIMENT-PROTOCOL-001", {"human_authoritative"}),
    "target_power": ("one_minus_beta", "HUMAN_AUTHORITATIVE", "probability", "GATE-EXPERIMENT-PROTOCOL-001", {"human_authoritative"}),
    "allocation_ratio": ("rho", "HUMAN_AUTHORITATIVE", "ratio", "GATE-EXPERIMENT-PROTOCOL-001", {"human_authoritative"}),
    "route_day_cluster_size": ("m", "EMPIRICAL_ONLY", "route_days_per_cluster", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "intracluster_correlation": ("icc", "EMPIRICAL_ONLY", "correlation", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "interference_structure": ("I", "EMPIRICAL_ONLY", "registered_radius_or_exposure", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "adherence_rate": ("adh", "EMPIRICAL_ONLY", "proportion", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "substitution_rate": ("sub", "EMPIRICAL_ONLY", "proportion", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "attrition_rate": ("attr", "EMPIRICAL_ONLY", "proportion", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
    "outcome_maturity_rate": ("mat", "EMPIRICAL_ONLY", "proportion", "GATE-OUTCOME-LABELS-MATURITY-001", {"unknown", "measured"}),
}
POWER_INPUTS = {"baseline_f9_rate", "baseline_f9_variance", "minimum_meaningful_absolute_lift", "alpha", "target_power", "allocation_ratio", "route_day_cluster_size", "intracluster_correlation", "interference_structure", "adherence_rate", "substitution_rate", "attrition_rate", "outcome_maturity_rate"}
ESTIMAND_SIGNATURES = {
    "EST-F9-BASELINE-RATE": ("representative_route_day", "F9_BASELINE_MEAN_V1", "E[Y_F9(W) | assigned comparator]", {"p0", "W"}, {"baseline_f9_rate", "f9_maturity_horizon_days"}, 6),
    "EST-F9-BASELINE-VARIANCE": ("representative_route_day", "F9_BASELINE_VARIANCE_V1", "Var[Y_F9(W) | assigned comparator]", {"sigma2", "W"}, {"baseline_f9_variance", "f9_maturity_horizon_days"}, 6),
    "EST-F9-ITT": ("representative_route_day", "F9_ROUTE_DAY_ITT_V1", "E[Y_j(a,W)-Y_j(b,W)] with preregistered blocks and clustering", {"tau", "W"}, {"incremental_f9_effect", "f9_maturity_horizon_days"}, 8),
    "EST-PREDICTIVE-F9-RISK": ("candidate_physical_location_at_prediction_time", "F9_CANDIDATE_RISK_V1", "P(T_i_F9 <= W | X_i_t, R_r, M_t)", {"p_f9", "W"}, {"predictive_f9_risk", "f9_maturity_horizon_days"}, 6),
    "EST-POWER-SAMPLE-SIZE": ("representative_route_day", "F9_CLUSTER_POWER_V1", "cluster_trial_power(p0,sigma2,Delta,alpha,one_minus_beta,rho,m,icc,I,adh,sub,attr,mat)", {"p0", "sigma2", "Delta", "alpha", "one_minus_beta", "rho", "m", "icc", "I", "adh", "sub", "attr", "mat"}, POWER_INPUTS, 4),
    "EST-RISK-ADJUSTED-NET-VALUE": ("candidate_physical_location_at_prediction_time", "CANDIDATE_RISK_ADJUSTED_VALUE_V1", "mode(delta_i,p_f9)*p_attend*p_mandate*p_transaction*commission-cost-lambda*risk", {"delta_i", "p_f9", "p_attend", "p_mandate", "p_transaction", "commission", "cost", "lambda", "risk"}, {"candidate_incremental_effect", "predictive_f9_risk", "attendance_probability", "mandate_probability", "transaction_probability", "expected_commission", "incremental_operational_cost", "risk_aversion_policy", "risk_uncertainty_penalty"}, 9),
}
ESTIMAND_OUTPUTS = {
    "EST-F9-BASELINE-RATE": ("bookings_per_route_day", "W from registered outcome-maturity policy", None),
    "EST-F9-BASELINE-VARIANCE": ("bookings_squared_per_route_day", "W from registered outcome-maturity policy", None),
    "EST-F9-ITT": ("bookings_per_route_day", "W from registered outcome-maturity policy", None),
    "EST-PREDICTIVE-F9-RISK": ("probability", "W from registered outcome-maturity policy", None),
    "EST-POWER-SAMPLE-SIZE": ("representative_route_days", None, None),
    "EST-RISK-ADJUSTED-NET-VALUE": ("currency_per_candidate", None, "CAUSAL_DELTA requires admissible delta_i; otherwise NON_CAUSAL_PROXY uses p_f9 and caps every output below causal proof."),
}
DIAGNOSTICS = {
    "undefined": "MATH-P08 decision estimand is undefined or conflated",
    "hardcoded": "MATH-P07 power result uses unset inputs",
    "scenario": "MATH-P07 scenario value promoted to measured evidence",
}
REQUIRED_SUBJECTS = {
    "control/GATES.json",
    "contracts/estimand_registry.schema.json", "contracts/math_authority_input.schema.json",
    "contracts/math_decision_policy.schema.json", "contracts/math_route_decision.schema.json",
    "artifacts/math/estimand_registry.json", "artifacts/math/human_authority_input_template.json",
    "artifacts/math/formal_decisions.json", "artifacts/math/public_evaluator_contract.json",
    "src/cre_foundry/math/reference_oracle.py", "evals/public/math_oracle_evaluator.py",
    "evals/public/test_math_contracts.py", "scripts/build_math_contracts.py", "scripts/finalize_math_contracts.py", "scripts/validate_math_contracts.py",
    "evals/known_bad/math/issue_nine.py", "evals/known_bad/math/fill_with_protected_alias.py",
    "evals/known_bad/math/collapse_duplicate_physical_locations.py", "evals/known_bad/math/use_stage2_field_observation.py",
    "evals/known_bad/math/prefer_proximity_below_value_floor.py", "evals/known_bad/math/permutation_sensitive.py",
    "evals/known_bad/math/greedy_individual_value.py", "evals/known_bad/frontier/math_undefined_estimand.json",
    "evals/known_bad/frontier/math_hardcoded_power.json", "evals/known_bad/frontier/math_scenario_as_measured.json",
    "evals/known_bad/frontier/exact_ten_wrong_cardinality.json", "evals/known_bad/frontier/exact_ten_protected_fill.json",
}


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def load(path: Path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(rows: list[dict], field: str, label: str, errors: list[str]) -> dict[str, dict]:
    values = [row.get(field) for row in rows]
    if None in values or len(values) != len(set(values)):
        errors.append(f"MATH-DUPLICATE-ID: {label}")
    return {row.get(field): row for row in rows if row.get(field) is not None}


def derived_proof_level(input_ids: set[str], inputs: dict[str, dict], ceiling: int) -> int:
    """Public P09 rule: a result cannot outrank its weakest load-bearing leaf."""
    if not input_ids or any(inputs.get(input_id, {}).get("value") is None for input_id in input_ids):
        return 0
    return min(ceiling, *(inputs[input_id].get("proof_level", 0) for input_id in input_ids))


def validate_registry(document: dict) -> list[str]:
    errors: list[str] = []
    power = document.get("power_result", {})
    inputs_raw = document.get("inputs", [])
    inputs = keyed(inputs_raw, "input_id", "inputs", errors) if isinstance(inputs_raw, list) else {}
    # Stable mutation diagnostics take precedence over generic schema errors.
    if power.get("estimate") is not None and power.get("status") != "sensitivity_only" and any(
        inputs.get(input_id, {}).get("value") is None for input_id in POWER_INPUTS
    ):
        return [DIAGNOSTICS["hardcoded"]]
    for row in inputs.values():
        if row.get("state") in {"symbolic", "unknown"} and row.get("value") is not None:
            return [DIAGNOSTICS["scenario"]]
        if row.get("state") == "human_authoritative" and row.get("value") is not None and row.get("authority_attestation") is None:
            return [DIAGNOSTICS["scenario"]]
    if any(row.get("value") is not None for row in inputs.values()):
        return ["MATH-V1-FORMAL-ONLY: numeric evidence transitions require a later independently reviewed evidence-bound contract version"]

    try:
        schema = load(SCHEMA)
        Draft202012Validator.check_schema(schema)
        schema_errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
            key=lambda error: (list(error.absolute_path), error.message),
        )
        errors.extend(f"MATH-SCHEMA:{error.json_path}: {error.message}" for error in schema_errors)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"MATH-SCHEMA-UNAVAILABLE: {type(exc).__name__}"]

    if not isinstance(document.get("estimands"), list):
        return errors
    estimands = keyed(document["estimands"], "estimand_id", "estimands", errors)
    if set(estimands) != REQUIRED_ESTIMANDS:
        errors.append("MATH-ESTIMAND-COVERAGE: registry must contain exactly the six registered estimands")
    if set(inputs) != set(INPUT_SIGNATURES):
        errors.append("MATH-INPUT-COVERAGE: registry input set changed")
    gate_rows = {gate.get("gate_id"): gate for gate in load(ROOT / "control/GATES.json").get("gates", []) if isinstance(gate, dict)}
    for input_id, row in inputs.items():
        signature = INPUT_SIGNATURES.get(input_id)
        if signature is None:
            continue
        symbol, info_class, unit, required_gate, allowed_states = signature
        if (row.get("symbol"), row.get("information_class"), row.get("unit"), row.get("gate_id")) != (symbol, info_class, unit, required_gate) or row.get("state") not in allowed_states:
            errors.append(f"MATH-INPUT-BOUNDARY: {input_id} state/class/unit/gate differs from registered capability contract")
        state = row.get("state")
        value = row.get("value")
        gate = row.get("gate_id")
        if gate not in gate_rows:
            errors.append(f"MATH-UNREGISTERED-GATE: {input_id}:{gate}")
        if value is not None and str(gate_rows.get(gate, {}).get("status", "")).startswith("OPEN"):
            errors.append(f"MATH-OPEN-GATE-VALUE: {input_id}")
        evidence = row.get("measurement") if state == "measured" else row.get("authority_attestation") if state == "human_authoritative" and value is not None else None
        if evidence is not None:
            if state == "human_authoritative" and evidence.get("subject_input_id") != input_id:
                errors.append(f"MATH-ATTESTATION-SUBJECT: {input_id}")
            path = ROOT / evidence.get("artifact", "")
            if not path.is_file() or sha256(path) != evidence.get("artifact_sha256"):
                errors.append(f"MATH-EVIDENCE-HASH: {input_id}")
            if row.get("proof_level") != evidence.get("proof_level"):
                errors.append(f"MATH-INPUT-PROOF: {input_id}")
    known_symbols = {row.get("symbol") for row in inputs.values()}
    for estimand_id, row in estimands.items():
        signature = ESTIMAND_SIGNATURES.get(estimand_id)
        if signature:
            unit, formula_id, expression, symbols, input_ids, proof = signature
            actual_formula = row.get("formula", {})
            expected_output_unit, expected_window, expected_mode = ESTIMAND_OUTPUTS[estimand_id]
            if (
                row.get("decision_unit") != unit
                or actual_formula.get("expression_id") != formula_id
                or actual_formula.get("expression") != expression
                or set(actual_formula.get("symbols", [])) != set(symbols)
                or set(row.get("input_ids", [])) != set(input_ids)
                or row.get("required_proof_level") != proof
                or actual_formula.get("output_unit") != expected_output_unit
                or row.get("scale") != expected_output_unit
                or row.get("time_window") != expected_window
                or actual_formula.get("mode_rule") != expected_mode
            ):
                errors.append(DIAGNOSTICS["undefined"])
        dangling = set(row.get("input_ids", [])) - set(inputs)
        unknown_symbols = set(row.get("formula", {}).get("symbols", [])) - known_symbols
        if dangling or unknown_symbols:
            errors.append(f"MATH-DANGLING-DEPENDENCY: {estimand_id}")
    itt = estimands.get("EST-F9-ITT", {})
    predictive = estimands.get("EST-PREDICTIVE-F9-RISK", {})
    if (
        itt.get("treatment") != "assigned candidate list policy a"
        or itt.get("comparator") != "assigned registered baseline policy b"
        or itt.get("aggregation") != "intention-to-treat mean difference adjusted for preregistered blocks and clustering"
        or itt.get("time_window") != "W from registered outcome-maturity policy"
        or predictive.get("treatment") != "none; observational"
        or "never a treatment effect" not in predictive.get("claim_ceiling", "").lower()
    ):
        errors.append(DIAGNOSTICS["undefined"])
    sensitivity = document.get("sensitivity_policy", {})
    set_rows = sensitivity.get("sets", []) if isinstance(sensitivity, dict) else []
    set_ids = keyed(set_rows, "sensitivity_set_id", "sensitivity_sets", errors) if isinstance(set_rows, list) else {}
    for set_id, row in set_ids.items():
        input_row = inputs.get(row.get("input_id"), {})
        if row.get("unit") != input_row.get("unit") or row.get("proof_level", 9) > 4:
            errors.append(f"MATH-SENSITIVITY-BOUNDARY: {set_id}")
    for input_id, row in inputs.items():
        if set(row.get("sensitivity_set_ids", [])) - set(set_ids):
            errors.append(f"MATH-DANGLING-SENSITIVITY: {input_id}")

    design = document.get("power_design", {})
    design_fields = {"analysis_family", "sidedness", "multiplicity_policy", "randomization_unit", "estimator", "variance_model", "interference_representation"}
    if design.get("state") != "human_authoritative_unset" or design.get("gate_id") != "GATE-EXPERIMENT-PROTOCOL-001" or any(design.get(field) is not None for field in design_fields):
        errors.append("MATH-POWER-DESIGN: v1.1 protocol design must remain explicitly human-authoritative and unset")

    if set(power.get("input_ids", [])) != POWER_INPUTS:
        errors.append("MATH-POWER-INPUTS: power leaves differ from the registered design")
    if power.get("status") == "not_computable":
        if power.get("estimate") is not None or power.get("proof_level") != 0 or power.get("evidence_refs"):
            errors.append("MATH-POWER-STATUS: unavailable inputs require explicit not_computable null output")
    elif power.get("status") == "computed":
        leaves = [inputs.get(input_id, {}) for input_id in POWER_INPUTS]
        if any(row.get("value") is None for row in leaves):
            errors.append(DIAGNOSTICS["hardcoded"])
        else:
            if power.get("proof_level", 9) > derived_proof_level(POWER_INPUTS, inputs, 4):
                errors.append("MATH-P09 derived proof exceeds weakest load-bearing input")
            evidence_ids = {
                evidence.get("evidence_id")
                for row in leaves
                for evidence in (row.get("measurement"), row.get("authority_attestation"))
                if isinstance(evidence, dict)
            }
            if set(power.get("evidence_refs", [])) != evidence_ids:
                errors.append("MATH-POWER-EVIDENCE: computed result does not bind every leaf")
    elif power.get("status") == "sensitivity_only":
        errors.append("MATH-V1-FORMAL-ONLY: numeric sensitivity outputs require a later registered computation contract")
    return list(dict.fromkeys(errors))


def validate_authority_template(document: dict) -> list[str]:
    try:
        template = load(AUTHORITY_TEMPLATE)
        schema = load(AUTHORITY_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"MATH-AUTHORITY-TEMPLATE-UNAVAILABLE: {type(exc).__name__}"]
    errors = [
        f"MATH-AUTHORITY-TEMPLATE-SCHEMA:{error.json_path}: {error.message}"
        for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(template)
    ]
    expected = {
        input_id for input_id, signature in INPUT_SIGNATURES.items()
        if signature[1] == "HUMAN_AUTHORITATIVE"
    }
    actual = {row.get("input_id") for row in template.get("eligible_inputs", [])}
    if actual != expected or template.get("live_authority_granted") is not False or template.get("ingestion_status") != "NOT_AN_INGESTION_INTERFACE" or any(value is not None for value in template.get("submission", {}).values()):
        errors.append("MATH-AUTHORITY-TEMPLATE-BOUNDARY: eligible inputs or live authority differ")
    registry_rows = {row.get("input_id"): row for row in document.get("inputs", [])}
    for row in template.get("eligible_inputs", []):
        source = registry_rows.get(row.get("input_id"), {})
        if any(row.get(field) != source.get(field) for field in ("unit", "owner", "gate_id")):
            errors.append(f"MATH-AUTHORITY-TEMPLATE-DRIFT: {row.get('input_id')}")
    return errors


def validate_report() -> list[str]:
    try:
        report = load(REPORT)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"MATH-REPORT-UNAVAILABLE: {type(exc).__name__}"]
    errors: list[str] = []
    if report.get("result") != "PASS" or report.get("proof_level") != 4:
        errors.append("MATH-REPORT-STATUS: stored report must record public proof level 4 PASS")
    if report.get("differential_domains") != 40 or report.get("unit_tests") != 10:
        errors.append("MATH-REPORT-COVERAGE: expected 10 tests and 40 differential domains")
    expected_controls = {
        "issue-nine", "protected-alias-clear", "duplicate-physical-location",
        "stage-two-leakage", "proximity-first", "undefined-estimand",
        "hardcoded-power", "scenario-as-measured", "permutation-sensitive",
        "greedy-differs-from-oracle",
    }
    controls = report.get("negative_controls", [])
    if {row.get("case_id") for row in controls if isinstance(row, dict)} != expected_controls or any(row.get("result") != "DETECTED" for row in controls if isinstance(row, dict)):
        errors.append("MATH-REPORT-NEGATIVE-CONTROLS: all ten registered controls must be detected")
    bindings = report.get("subject_files", [])
    if {row.get("path") for row in bindings if isinstance(row, dict)} != REQUIRED_SUBJECTS or len(bindings) != len(REQUIRED_SUBJECTS):
        errors.append("MATH-REPORT-HASH: subject binding set is incomplete or duplicated")
    for binding in bindings:
        try:
            path = ROOT / binding["path"]
            if not path.is_file() or sha256(path) != binding["sha256"]:
                errors.append(f"MATH-REPORT-HASH: {binding.get('path')}")
        except (KeyError, TypeError):
            errors.append("MATH-REPORT-HASH: malformed binding")
    return errors


def run_tests() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "evals.public.test_math_contracts"],
        cwd=ROOT, text=True, capture_output=True, timeout=60,
    )
    if result.returncode != 0:
        return ["MATH-TESTS-FAILED"]
    return []


def pointer_target(document: dict, pointer: str):
    parts = [part for part in pointer.split("/") if part]
    parent = document
    for part in parts[:-1]:
        if isinstance(parent, list):
            matches = [row for row in parent if part in {row.get("estimand_id"), row.get("input_id")}]
            if len(matches) != 1:
                raise ValueError("semantic pointer did not select exactly one row")
            parent = matches[0]
        else:
            parent = parent[part]
    return parent, parts[-1]


def run_known_bad(path: Path) -> tuple[int, dict]:
    recipe = load(path)
    if set(recipe) == {"case_id", "target", "mutant", "problem_case", "expected_diagnostic"} and recipe["target"] == "decision_policy":
        return run_algorithm_known_bad(path, recipe)
    required = {"case_id", "target", "pointer", "expected_before", "value", "expected_diagnostic"}
    if set(recipe) != required or recipe["target"] != "artifacts/math/estimand_registry.json":
        raise ValueError("unsupported mutation recipe")
    document = load(REGISTRY)
    if validate_registry(document):
        raise ValueError("pristine registry does not pass")
    parent, field = pointer_target(document, recipe["pointer"])
    if parent[field] != recipe["expected_before"] or parent[field] == recipe["value"]:
        raise ValueError("stale or no-op mutation")
    parent[field] = recipe["value"]
    diagnostics = validate_registry(document)
    detected = diagnostics == [recipe["expected_diagnostic"]]
    payload = {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": recipe["case_id"],
        "fixture_sha256": sha256(path),
        "diagnostic": recipe["expected_diagnostic"] if detected else "; ".join(diagnostics),
    }
    return (0 if detected else 1), payload


def run_algorithm_known_bad(path: Path, recipe: dict) -> tuple[int, dict]:
    def candidate(index):
        return {
            "candidate_id": f"C{index:02d}", "physical_location_id": f"L{index:02d}",
            "grain_ids": {name: None for name in ["legal_entity_id", "operating_business_id", "brand_id", "establishment_id", "unit_id", "property_id", "parcel_id", "owner_id", "occupier_id", "parent_group_id"]},
            "protection_tokens": [], "evidence_stage": 1, "observed_at": "2026-08-01T12:00:00Z",
            "gates": {name: "PASS" for name in ["evidence", "identity", "eligibility", "safety", "access", "operational"]},
            "protected_status": "CLEAR", "value_state": "REGISTERED_SYNTHETIC_PROXY", "business_value_units": 100 - index,
            "proximity_cost_units": index, "service_minutes": 10, "composition_group": None,
        }

    count = 9 if recipe["problem_case"] == "nine" else 10
    problem = {
        "schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY", "decision_id": "D-KNOWN-BAD",
        "snapshot": {"snapshot_id": "S-KNOWN-BAD", "snapshot_sha256": "0" * 64, "stage1_cutoff": "2026-08-01T23:00:00Z", "issued_at": "2026-08-01T23:30:00Z", "protected_bundle_complete": True, "protected_tokens": []},
        "route_day": {"representative_id": "R-1", "route_date": "2026-08-02"},
        "policy": {"policy_version": "math-policy-v1", "policy_sha256": "1" * 64, "epsilon_business_value_units": 0, "maximum_candidates": 20, "max_total_service_minutes": 200, "composition_caps": {}, "required_unique_grains": [], "incompatible_candidate_pairs": [], "redundancy_penalties": [], "interference_penalties": []},
        "candidates": [candidate(index) for index in range(count)],
    }
    if recipe["problem_case"] == "protected_alias":
        problem["snapshot"]["protected_tokens"] = ["ALIAS:PROTECTED"]
        problem["candidates"][-1]["protection_tokens"] = ["ALIAS:PROTECTED"]
    elif recipe["problem_case"] != "nine":
        raise ValueError("unsupported decision-policy problem case")
    mutant = ROOT / recipe["mutant"]
    if not mutant.is_file() or ROOT not in mutant.resolve().parents:
        raise ValueError("unsafe or missing mutant")
    sys.path.insert(0, str(ROOT / "evals/public"))
    from math_oracle_evaluator import evaluate
    expected = evaluate(problem)
    with tempfile.TemporaryDirectory(prefix="math-mutant-") as temp:
        problem_path = Path(temp) / "problem.json"
        problem_path.write_text(json.dumps(problem))
        process = subprocess.run([sys.executable, str(mutant), "--input", str(problem_path)], cwd=ROOT, text=True, capture_output=True, timeout=30)
    try:
        actual = json.loads(process.stdout)
        decision_schema = load(ROOT / "contracts/math_route_decision.schema.json")
        invalid = bool(list(Draft202012Validator(decision_schema, format_checker=FormatChecker()).iter_errors(actual)))
    except (json.JSONDecodeError, ValueError):
        actual, invalid = None, True
    detected = process.returncode == 0 and process.stderr == "" and (invalid or actual != expected)
    payload = {"result": "DETECTED" if detected else "SURVIVED", "case_id": recipe["case_id"], "fixture_sha256": sha256(path), "diagnostic": recipe["expected_diagnostic"] if detected else "decision-policy mutation survived"}
    return (0 if detected else 1), payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()
    if args.known_bad:
        path = args.known_bad if args.known_bad.is_absolute() else ROOT / args.known_bad
        try:
            code, payload = run_known_bad(path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            code, payload = 1, {"result": "SURVIVED", "case_id": "invalid", "fixture_sha256": sha256(path) if path.is_file() else "", "diagnostic": str(exc)}
        print(json.dumps(payload, sort_keys=True))
        return code
    try:
        registry = load(REGISTRY)
        errors = validate_registry(registry) + validate_authority_template(registry) + run_tests() + validate_report()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors = ["MATH-VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
