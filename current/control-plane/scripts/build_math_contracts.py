"""Build MATH-001's symbolic registry and authority-input template."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/math"


def unavailable(input_id, symbol, info, unit, owner, gate):
    state = "human_authoritative" if info == "HUMAN_AUTHORITATIVE" else "unknown"
    return {
        "input_id": input_id, "symbol": symbol, "state": state,
        "information_class": info, "unit": unit, "value": None,
        "owner": owner, "gate_id": gate, "proof_level": 0,
        "measurement": None, "authority_attestation": None, "sensitivity_set_ids": [],
    }


def formula(expression_id, expression, symbols, output_unit, mode_rule=None):
    return {"expression_id": expression_id, "expression": expression, "symbols": symbols, "output_unit": output_unit, "mode_rule": mode_rule}


def estimand(identifier, unit, outcome, expression, proof, status, inputs, ceiling, *, treatment=None, comparator=None, aggregation="definition", window=None, population="standardized representative route-days in the registered pilot scope"):
    return {
        "estimand_id": identifier, "decision_unit": unit, "population": population,
        "treatment": treatment, "comparator": comparator, "outcome": outcome,
        "time_window": window, "aggregation": aggregation, "scale": expression["output_unit"],
        "formula": expression, "required_proof_level": proof, "current_status": status,
        "input_ids": inputs, "claim_ceiling": ceiling,
    }


def build_registry():
    outcome = "GATE-OUTCOME-LABELS-MATURITY-001"
    economics = "firm_economics_services_territories"
    full = "GATE-FULL-EXTERNAL-EVIDENCE-001"
    protocol = "GATE-EXPERIMENT-PROTOCOL-001"
    inputs = [
        unavailable("baseline_f9_rate", "p0", "ACCESS_DEPENDENT", "bookings_per_route_day", "authorized firm outcome-data custodian", outcome),
        unavailable("baseline_f9_variance", "sigma2", "ACCESS_DEPENDENT", "bookings_squared_per_route_day", "authorized firm outcome-data custodian", outcome),
        unavailable("incremental_f9_effect", "tau", "EMPIRICAL_ONLY", "bookings_per_route_day", "randomized experiment and outcome custodian", full),
        unavailable("predictive_f9_risk", "p_f9", "EMPIRICAL_ONLY", "probability", "historical point-in-time model and outcome custodian", full),
        unavailable("f9_maturity_horizon_days", "W", "HUMAN_AUTHORITATIVE", "days", "authorized outcome-policy owner", outcome),
        unavailable("candidate_incremental_effect", "delta_i", "EMPIRICAL_ONLY", "incremental_bookings_per_candidate", "randomized experiment and outcome custodian", full),
        unavailable("attendance_probability", "p_attend", "EMPIRICAL_ONLY", "probability", "authorized mature-funnel outcome custodian", full),
        unavailable("mandate_probability", "p_mandate", "EMPIRICAL_ONLY", "probability", "authorized mature-funnel outcome custodian", full),
        unavailable("transaction_probability", "p_transaction", "EMPIRICAL_ONLY", "probability", "authorized mature-funnel outcome custodian", full),
        unavailable("expected_commission", "commission", "ACCESS_DEPENDENT", "currency_per_transaction", "authorized finance and outcome custodian", full),
        unavailable("incremental_operational_cost", "cost", "ACCESS_DEPENDENT", "currency_per_candidate", "authorized finance and operations custodian", economics),
        unavailable("risk_uncertainty_penalty", "risk", "EMPIRICAL_ONLY", "currency_per_candidate", "authorized risk and outcome custodian", full),
        unavailable("risk_aversion_policy", "lambda", "HUMAN_AUTHORITATIVE", "dimensionless_utility_weight", "authorized firm decision-maker", economics),
        unavailable("minimum_meaningful_absolute_lift", "Delta", "HUMAN_AUTHORITATIVE", "bookings_per_route_day", "authorized firm decision-maker", economics),
        unavailable("alpha", "alpha", "HUMAN_AUTHORITATIVE", "probability", "authorized experimental protocol owner", protocol),
        unavailable("target_power", "one_minus_beta", "HUMAN_AUTHORITATIVE", "probability", "authorized experimental protocol owner", protocol),
        unavailable("allocation_ratio", "rho", "HUMAN_AUTHORITATIVE", "ratio", "authorized experimental protocol owner", protocol),
        unavailable("route_day_cluster_size", "m", "EMPIRICAL_ONLY", "route_days_per_cluster", "field instrumentation and outcome custodian", outcome),
        unavailable("intracluster_correlation", "icc", "EMPIRICAL_ONLY", "correlation", "field instrumentation and outcome custodian", outcome),
        unavailable("interference_structure", "I", "EMPIRICAL_ONLY", "registered_radius_or_exposure", "field instrumentation and outcome custodian", outcome),
        unavailable("adherence_rate", "adh", "EMPIRICAL_ONLY", "proportion", "field instrumentation and outcome custodian", outcome),
        unavailable("substitution_rate", "sub", "EMPIRICAL_ONLY", "proportion", "field instrumentation and outcome custodian", outcome),
        unavailable("attrition_rate", "attr", "EMPIRICAL_ONLY", "proportion", "field instrumentation and outcome custodian", outcome),
        unavailable("outcome_maturity_rate", "mat", "EMPIRICAL_ONLY", "proportion", "outcome maturity custodian", outcome),
    ]
    power_inputs = ["baseline_f9_rate", "baseline_f9_variance", "minimum_meaningful_absolute_lift", "alpha", "target_power", "allocation_ratio", "route_day_cluster_size", "intracluster_correlation", "interference_structure", "adherence_rate", "substitution_rate", "attrition_rate", "outcome_maturity_rate"]
    estimands = [
        estimand("EST-F9-BASELINE-RATE", "representative_route_day", "mature adjudicated F9 booking count", formula("F9_BASELINE_MEAN_V1", "E[Y_F9(W) | assigned comparator]", ["p0", "W"], "bookings_per_route_day"), 6, "unknown_not_computable", ["baseline_f9_rate", "f9_maturity_horizon_days"], "No baseline rate before authorized mature point-in-time outcomes.", comparator="assigned registered baseline policy", aggregation="mean", window="W from registered outcome-maturity policy"),
        estimand("EST-F9-BASELINE-VARIANCE", "representative_route_day", "mature adjudicated F9 booking count", formula("F9_BASELINE_VARIANCE_V1", "Var[Y_F9(W) | assigned comparator]", ["sigma2", "W"], "bookings_squared_per_route_day"), 6, "unknown_not_computable", ["baseline_f9_variance", "f9_maturity_horizon_days"], "No variance or power claim before authorized mature route-day outcomes.", comparator="assigned registered baseline policy", aggregation="variance with registered clustering", window="W from registered outcome-maturity policy"),
        estimand("EST-F9-ITT", "representative_route_day", "mature adjudicated F9 booking count", formula("F9_ROUTE_DAY_ITT_V1", "E[Y_j(a,W)-Y_j(b,W)] with preregistered blocks and clustering", ["tau", "W"], "bookings_per_route_day"), 8, "symbolic_only", ["incremental_f9_effect", "f9_maturity_horizon_days"], "Symbolic route-day ITT only; no causal estimate before preregistered randomized evidence.", treatment="assigned candidate list policy a", comparator="assigned registered baseline policy b", aggregation="intention-to-treat mean difference adjusted for preregistered blocks and clustering", window="W from registered outcome-maturity policy"),
        estimand("EST-PREDICTIVE-F9-RISK", "candidate_physical_location_at_prediction_time", "future mature adjudicated F9 booking", formula("F9_CANDIDATE_RISK_V1", "P(T_i_F9 <= W | X_i_t, R_r, M_t)", ["p_f9", "W"], "probability"), 6, "symbolic_only", ["predictive_f9_risk", "f9_maturity_horizon_days"], "Observational point-in-time prediction only and never a treatment effect.", treatment="none; observational", comparator="transparent predictive baselines", aggregation="point-in-time calibrated probability", window="W from registered outcome-maturity policy", population="eligible candidate physical locations at registered prediction times"),
        estimand("EST-POWER-SAMPLE-SIZE", "representative_route_day", "confirmatory route-day sample size", formula("F9_CLUSTER_POWER_V1", "cluster_trial_power(p0,sigma2,Delta,alpha,one_minus_beta,rho,m,icc,I,adh,sub,attr,mat)", ["p0", "sigma2", "Delta", "alpha", "one_minus_beta", "rho", "m", "icc", "I", "adh", "sub", "attr", "mat"], "representative_route_days"), 4, "unknown_not_computable", power_inputs, "Not computable until every empirical and protocol-authoritative input is admissible.", treatment="assigned candidate list policy a", comparator="assigned registered baseline policy b"),
        estimand("EST-RISK-ADJUSTED-NET-VALUE", "candidate_physical_location_at_prediction_time", "expected candidate incremental risk-adjusted net commercial value", formula("CANDIDATE_RISK_ADJUSTED_VALUE_V1", "mode(delta_i,p_f9)*p_attend*p_mandate*p_transaction*commission-cost-lambda*risk", ["delta_i", "p_f9", "p_attend", "p_mandate", "p_transaction", "commission", "cost", "lambda", "risk"], "currency_per_candidate", "CAUSAL_DELTA requires admissible delta_i; otherwise NON_CAUSAL_PROXY uses p_f9 and caps every output below causal proof."), 9, "symbolic_only", ["candidate_incremental_effect", "predictive_f9_risk", "attendance_probability", "mandate_probability", "transaction_probability", "expected_commission", "incremental_operational_cost", "risk_aversion_policy", "risk_uncertainty_penalty"], "Expression only; delta_i requires causal evidence, proxy mode is explicitly non-causal, and no positive or realized value is claimed.", treatment="candidate intervention when causally identified; otherwise explicitly non-causal proxy mode", comparator="registered candidate baseline", aggregation="risk-adjusted expected incremental value", population="eligible candidate physical locations at registered prediction times"),
    ]
    return {
        "artifact_id": "MATH-001-ESTIMAND-REGISTRY", "schema_version": "1.1.0", "as_of": "2026-08-02",
        "input_states": ["symbolic", "measured", "unknown", "human_authoritative"],
        "inputs": inputs, "estimands": estimands,
        "power_design": {"state": "human_authoritative_unset", "gate_id": protocol, "owner": "authorized experimental protocol owner", "analysis_family": None, "sidedness": None, "multiplicity_policy": None, "randomization_unit": None, "estimator": None, "variance_model": None, "interference_representation": None},
        "power_result": {"estimate": None, "status": "not_computable", "reason": "required empirical and human-authoritative inputs are unset", "unit": "representative_route_days", "input_ids": power_inputs, "proof_level": 0, "evidence_refs": []},
        "sensitivity_policy": {"sets": [], "scenario_values_are_evidence": False, "maximum_proof_level": 4, "required_output_label": "sensitivity_only_not_measured"},
        "claim_ceiling": "Formal symbolic registry only; no numeric power, predictive, causal, operational, or commercial claim.",
    }


def build_authority_template(registry):
    return {
        "artifact_id": "MATH-001-HUMAN-AUTHORITY-INPUT-TEMPLATE", "schema_version": "1.0.0",
        "instructions": "Copy this blank collection template into a future independently reviewed ingestion workflow. This artifact is not an ingestion interface, grants no authority, and must remain blank in v1.1. Codex does not self-attest.",
        "eligible_inputs": [{"input_id": row["input_id"], "unit": row["unit"], "owner": row["owner"], "gate_id": row["gate_id"]} for row in registry["inputs"] if row["information_class"] == "HUMAN_AUTHORITATIVE"],
        "submission": {"input_id": None, "value": None, "issuer": None, "issued_at": None, "evidence_artifact": None, "artifact_sha256": None, "approval_scope": None},
        "ingestion_status": "NOT_AN_INGESTION_INTERFACE", "live_authority_granted": False,
    }


def main() -> int:
    registry = build_registry()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "estimand_registry.json").write_text(json.dumps(registry, indent=2) + "\n")
    (OUT / "human_authority_input_template.json").write_text(json.dumps(build_authority_template(registry), indent=2) + "\n")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
