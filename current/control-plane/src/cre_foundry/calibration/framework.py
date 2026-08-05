"""Builder for the bounded CALIBRATION-001 synthetic demonstration.

The output is deliberately exact, deterministic, and non-influencing.  It is
not evidence that any real score is a probability or that any real model is
calibrated.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

from cre_foundry.math.reference_oracle import decide

ROOT = Path(__file__).resolve().parents[3]
SCOPE = "SYNTHETIC_NON_INFLUENCING"
CLAIM_CEILING = (
    "Synthetic calibration, missingness, subgroup, temporal, MATH projection, "
    "and abstention mechanics only; no real calibration, prediction, fairness, "
    "stability, causal lift, commercial value, production fitness, or authority."
)
BINS = [
    {"bin_id": "B0", "lower": [0, 1], "upper": [1, 5], "upper_inclusive": False},
    {"bin_id": "B1", "lower": [1, 5], "upper": [2, 5], "upper_inclusive": False},
    {"bin_id": "B2", "lower": [2, 5], "upper": [3, 5], "upper_inclusive": False},
    {"bin_id": "B3", "lower": [3, 5], "upper": [4, 5], "upper_inclusive": False},
    {"bin_id": "B4", "lower": [4, 5], "upper": [1, 1], "upper_inclusive": True},
]
PROOF = {
    "level": 5,
    "claim": "synthetic calibration framework and replay conformance only",
    "real_probability_semantics_proven": False,
    "real_calibration_proven": False,
    "fairness_or_stability_proven": False,
    "incremental_lift_proven": False,
    "commercial_value_proven": False,
    "production_authorized": False,
    "live_use_authorized": False,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rat(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def values(candidate: dict[str, Any]) -> dict[str, Any]:
    return {row["feature_definition_id"].split(":")[1]: row["value"] for row in candidate["features"]}


def bin_id(value: Fraction) -> str:
    if value < Fraction(1, 5):
        return "B0"
    if value < Fraction(2, 5):
        return "B1"
    if value < Fraction(3, 5):
        return "B2"
    if value < Fraction(4, 5):
        return "B3"
    return "B4"


def build_input() -> dict[str, Any]:
    return {
        "document_kind": "FROZEN_SYNTHETIC_CALIBRATION_INPUT",
        "schema_version": "1.0.0",
        "execution_scope": SCOPE,
        "registry_id": "CALIBRATION_INPUT:FROZEN_V1",
        "registered_at": "2026-04-15T00:00:00Z",
        "probability_head": {
            "head_id": "BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1",
            "target": "F9_WITHIN_REGISTERED_WINDOW_W_GIVEN_STAGE1_POINT_IN_TIME_INFORMATION",
            "estimand_kind": "OBSERVATIONAL_CANDIDATE_RISK_NOT_CAUSAL_EFFECT_OR_ROUTE_DAY_ITT",
            "numeric_domain": "CANONICAL_REDUCED_EXACT_RATIONAL_0_TO_1_INCLUSIVE",
            "source_policy_id": "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1",
            "all_baseline_policy_streams_are_rank_only": True,
        },
        "calibrator": {
            "calibrator_id": "FIXED_BIN_BETA_BINOMIAL_ALPHA_1_BETA_1:V1",
            "registered_at": "2026-04-15T00:00:00Z",
            "validation_fit_at": "2026-07-07T00:00:00Z",
            "fit_partition": "VALIDATION_COMPLETE_CANDIDATE_UNIVERSE_ONLY",
            "alpha": 1,
            "beta": 1,
            "minimum_cell_count": 4,
            "unseen_or_sparse_fallback": "UNKNOWN_INPUT",
            "test_reuse_allowed": False,
        },
        "bins": BINS,
        "analysis": {
            "subgroup_dimension": "market_segment",
            "subgroup_values": ["A", "B", "C", "UNKNOWN"],
            "temporal_unit": "ROUTE_DAY_CHRONOLOGICAL",
            "primary_population": "FULL_COMMON_CANDIDATE_UNIVERSE_NOT_SELECTED_TEN",
            "macro_micro_separate": True,
            "uncertainty_status": "NOT_EMPIRICALLY_ESTIMABLE",
        },
        "scenarios": [
            {"scenario_id": "CANONICAL_ALL_PROBABILITIES_KNOWN", "probability_override": None},
            {"scenario_id": "UNKNOWN_ADMISSIBLE_PROBABILITY", "probability_override": {"route_day_id": "ROUTE_DAY:SYN_BASE_07", "candidate_id": "CAND:SYN_BASE_07_01", "state": "UNKNOWN_INPUT"}},
            {"scenario_id": "SPARSE_OCCUPIED_RELIABILITY_CELL", "candidate_ids": ["CAND:SYN_BASE_07_01"]},
            {"scenario_id": "MISSING_MODEL_FEATURE_AND_SUBGROUP", "probability_override": {"route_day_id": "ROUTE_DAY:SYN_BASE_08", "candidate_id": "CAND:SYN_BASE_08_12", "state": "UNKNOWN_INPUT", "market_segment": "UNKNOWN"}},
        ],
        "bindings": {
            "baseline_benchmark_sha256": digest_file(ROOT / "artifacts/baselines/frozen_benchmark.json"),
            "baseline_registry_sha256": digest_file(ROOT / "artifacts/baselines/policy_registry.json"),
            "baseline_run_sha256": digest_file(ROOT / "artifacts/baselines/canonical_run.json"),
            "outcomes_contract_sha256": digest_file(ROOT / "artifacts/outcomes/public_evaluator_contract.json"),
            "outcomes_policy_sha256": digest_file(ROOT / "artifacts/outcomes/synthetic_window_policy.json"),
            "outcomes_run_sha256": digest_file(ROOT / "artifacts/outcomes/canonical_run.json"),
            "math_contract_sha256": digest_file(ROOT / "artifacts/math/public_evaluator_contract.json"),
            "math_problem_schema_sha256": digest_file(ROOT / "contracts/math_decision_policy.schema.json"),
            "math_decision_schema_sha256": digest_file(ROOT / "contracts/math_route_decision.schema.json"),
            "public_evaluator_contract_sha256": digest_file(ROOT / "artifacts/calibration/public_evaluator_contract.json"),
        },
        "claim_ceiling": CLAIM_CEILING,
    }


def _raw_probabilities(benchmark: dict[str, Any], baseline_run: dict[str, Any]) -> dict[tuple[str, str], Fraction]:
    counts = baseline_run["fit"]["bucket_counts"]
    result = {}
    for route in benchmark["routes"]:
        if route["split"] not in {"VALIDATION", "TEST"}:
            continue
        for candidate in route["candidates"]:
            segment = values(candidate)["market_segment"]
            row = counts[segment]
            result[(route["route_day_id"], candidate["candidate_id"])] = Fraction(row["positive"] + 1, row["mature"] + 2)
    return result


def _fit(benchmark: dict[str, Any], raw: dict[tuple[str, str], Fraction]) -> dict[str, Any]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    by_bin = {row["bin_id"]: {"positive": 0, "mature": 0, "included_row_ids": [], "excluded_row_ids": []} for row in BINS}
    for route in benchmark["routes"]:
        if route["split"] != "VALIDATION":
            continue
        route_labels = [labels[(route["route_day_id"], candidate["candidate_id"])] for candidate in route["candidates"]]
        route_complete = all(label["label"] is not None and label["available_at"] <= "2026-07-07T00:00:00Z" for label in route_labels)
        for candidate in route["candidates"]:
            key = (route["route_day_id"], candidate["candidate_id"])
            label = labels[key]
            cell = by_bin[bin_id(raw[key])]
            row_id = "|".join(key)
            if not route_complete:
                cell["excluded_row_ids"].append(row_id)
            else:
                cell["included_row_ids"].append(row_id)
                cell["mature"] += 1
                cell["positive"] += int(label["label"] is True)
    cells = []
    for spec in BINS:
        row = by_bin[spec["bin_id"]]
        row["included_row_ids"].sort()
        row["excluded_row_ids"].sort()
        if row["mature"] == 0:
            state, posterior = "EMPTY_NOT_ESTIMABLE", None
        elif row["mature"] < 4:
            state, posterior = "SPARSE_NOT_ESTIMABLE", None
        else:
            state = "REPORTABLE_SYNTHETIC_MECHANICS"
            posterior = rat(Fraction(row["positive"] + 1, row["mature"] + 2))
        cells.append({"bin_id": spec["bin_id"], **row, "cell_state": state, "posterior_probability": posterior})
    core = {
        "calibrator_id": "FIXED_BIN_BETA_BINOMIAL_ALPHA_1_BETA_1:V1",
        "fit_at": "2026-07-07T00:00:00Z",
        "fit_partition": "VALIDATION",
        "population": {
            "assigned_candidate_rows": 24,
            "included_mature_rows": sum(row["mature"] for row in cells),
            "excluded_null_or_late_rows": sum(len(row["excluded_row_ids"]) for row in cells),
            "selected_ten_rows_used": 0,
            "train_rows_used": 0,
            "test_rows_used": 0,
            "route_states": {"ROUTE_DAY:SYN_BASE_05": "EXCLUDED_WHOLE_ROUTE_INCOMPLETE_AT_FIT", "ROUTE_DAY:SYN_BASE_06": "INCLUDED_COMPLETE_ROUTE"},
        },
        "cells": cells,
    }
    return {**core, "fit_sha256": digest_json(core)}


def _ledger(benchmark: dict[str, Any], raw: dict[tuple[str, str], Fraction], fit: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    posterior = {row["bin_id"]: row["posterior_probability"] for row in fit["cells"]}
    rows = []
    for route in benchmark["routes"]:
        if route["split"] not in {"VALIDATION", "TEST"}:
            continue
        for candidate in route["candidates"]:
            key = (route["route_day_id"], candidate["candidate_id"])
            p0 = raw[key]
            calibrated = posterior[bin_id(p0)]
            state = "ELIGIBLE_REGISTERED_SYNTHETIC_PROBABILITY" if calibrated is not None else "UNKNOWN_INPUT"
            label = labels[key]
            rows.append({
                "route_day_id": route["route_day_id"],
                "candidate_id": candidate["candidate_id"],
                "physical_location_id": candidate["physical_location_id"],
                "split": route["split"],
                "decision_at": route["decision_at"],
                "prediction_frozen_at": route["decision_at"],
                "prediction_clock_scope": "RAW_REGISTERED_HEAD_PER_ROUTE",
                "calibration_fit_at": "2026-07-07T00:00:00Z",
                "calibrated_probability_available_at": "2026-07-07T00:00:00Z" if route["split"] == "VALIDATION" else route["decision_at"],
                "evaluation_role": "CALIBRATOR_FIT_DIAGNOSTIC_NOT_OUT_OF_TIME_EVALUATION" if route["split"] == "VALIDATION" else "OUT_OF_TIME_SYNTHETIC_TEST_MECHANICS",
                "fit_inclusion_state": ("EXCLUDED_WHOLE_ROUTE_INCOMPLETE_AT_FIT" if route["route_day_id"] == "ROUTE_DAY:SYN_BASE_05" else "INCLUDED_COMPLETE_VALIDATION_ROUTE") if route["split"] == "VALIDATION" else "NOT_A_FIT_ROW_TEST_ONLY",
                "label_available_at": label["available_at"],
                "market_segment": values(candidate).get("market_segment", "UNKNOWN"),
                "feature_missingness_state": "OBSERVED",
                "probability_state": state,
                "raw_probability": rat(p0),
                "raw_bin_id": bin_id(p0),
                "calibrated_probability": calibrated,
                "calibrated_bin_id": bin_id(Fraction(calibrated["numerator"], calibrated["denominator"])) if calibrated else None,
                "outcome_state": label["state"],
                "label": label["label"],
                "current_head": label["current_head"],
                "assessment_sha256": label["assessment_sha256"],
            })
    return sorted(rows, key=lambda row: (row["split"], row["route_day_id"], row["candidate_id"]))


def _log_terms(rows: list[dict[str, Any]]) -> dict[str, Any]:
    incomplete = [row["candidate_id"] for row in rows if row["calibrated_probability"] is None or row["label"] is None]
    if incomplete:
        return {"status": "NOT_COMPUTABLE_INCOMPLETE_UNIVERSE", "terms": [], "incomplete_candidate_ids": sorted(incomplete)}
    terms: Counter[tuple[int, int, bool]] = Counter()
    for row in rows:
        p = row["calibrated_probability"]
        if p is None or row["label"] is None:
            continue
        q = Fraction(p["numerator"], p["denominator"])
        if (row["label"] and q == 0) or (not row["label"] and q == 1):
            return {"status": "POSITIVE_INFINITY", "terms": []}
        target = q if row["label"] else 1 - q
        terms[(target.denominator, target.numerator, bool(row["label"]))] += 1
    return {
        "status": "CANONICAL_SYMBOLIC_LOG_RATIONAL_TERMS",
        "terms": [{"coefficient": count, "log_ratio_numerator": n, "log_ratio_denominator": d, "label": label} for (n, d, label), count in sorted(terms.items())],
        "normalization_denominator": sum(terms.values()),
    }


def _metrics(
    rows: list[dict[str, Any]],
    route_ids: list[str],
    expected_candidate_count: int | None = None,
    expected_route_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    selected = [row for row in rows if row["route_day_id"] in route_ids]
    expected_candidate_count = 12 * len(route_ids) if expected_candidate_count is None else expected_candidate_count
    expected_route_counts = {route_id: 12 for route_id in route_ids} if expected_route_counts is None else expected_route_counts
    known_p = [row for row in selected if row["calibrated_probability"] is not None]
    joint = [row for row in known_p if row["label"] is not None]
    brier_terms = [(Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) - int(row["label"])) ** 2 for row in joint]
    brier = sum(brier_terms, Fraction()) / len(brier_terms) if brier_terms else None
    mean_p = sum((Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) for row in joint), Fraction()) / len(joint) if joint else None
    event_rate = Fraction(sum(row["label"] is True for row in joint), len(joint)) if joint else None
    cell_rows = []
    for spec in BINS:
        group = [row for row in joint if row["calibrated_bin_id"] == spec["bin_id"]]
        n = len(group)
        state = "EMPTY_NOT_ESTIMABLE" if n == 0 else "SPARSE_NOT_ESTIMABLE" if n < 4 else "REPORTABLE_SYNTHETIC_MECHANICS"
        mp = sum((Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) for row in group), Fraction()) / n if n else None
        er = Fraction(sum(row["label"] is True for row in group), n) if n else None
        gap = mp - er if state == "REPORTABLE_SYNTHETIC_MECHANICS" else None
        cell_rows.append({"bin_id": spec["bin_id"], "count": n, "positive": sum(row["label"] is True for row in group), "cell_state": state, "mean_probability": rat(mp) if state == "REPORTABLE_SYNTHETIC_MECHANICS" else None, "event_rate": rat(er) if state == "REPORTABLE_SYNTHETIC_MECHANICS" else None, "signed_gap": rat(gap) if gap is not None else None, "absolute_gap": rat(abs(gap)) if gap is not None else None})
    reportable = [row for row in cell_rows if row["cell_state"] == "REPORTABLE_SYNTHETIC_MECHANICS"]
    reportable_n = sum(row["count"] for row in reportable)
    occupied_sparse = any(row["cell_state"] == "SPARSE_NOT_ESTIMABLE" for row in cell_rows)
    ece = sum((Fraction(row["absolute_gap"]["numerator"], row["absolute_gap"]["denominator"]) * row["count"] for row in reportable), Fraction()) / reportable_n if reportable_n and not occupied_sparse else None
    mce = max((Fraction(row["absolute_gap"]["numerator"], row["absolute_gap"]["denominator"]) for row in reportable), default=None) if not occupied_sparse else None
    l2 = sum((Fraction(row["signed_gap"]["numerator"], row["signed_gap"]["denominator"]) ** 2 * row["count"] for row in reportable), Fraction()) / reportable_n if reportable_n and not occupied_sparse else None
    route_briers = []
    partial = []
    for route_id in route_ids:
        rr = [row for row in selected if row["route_day_id"] == route_id]
        expected_in_route = expected_route_counts.get(route_id, 0)
        if expected_in_route == 0:
            continue
        if len(rr) != expected_in_route or any(row["label"] is None or row["calibrated_probability"] is None for row in rr):
            partial.append(route_id)
        else:
            terms = [(Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) - int(row["label"])) ** 2 for row in rr]
            route_briers.append(sum(terms, Fraction()) / len(terms))
    route_macro = sum(route_briers, Fraction()) / len(route_briers) if route_briers and not partial else None
    universe_incomplete = len(selected) != expected_candidate_count
    if universe_incomplete:
        partial = sorted(set(partial) | set(route_ids))
    finalizable = expected_candidate_count > 0 and not partial and not universe_incomplete
    positives = [row for row in joint if row["label"] is True]
    negatives = [row for row in joint if row["label"] is False]
    concordant_units = 0
    for pos in positives:
        pp = Fraction(pos["calibrated_probability"]["numerator"], pos["calibrated_probability"]["denominator"])
        for neg in negatives:
            pn = Fraction(neg["calibrated_probability"]["numerator"], neg["calibrated_probability"]["denominator"])
            concordant_units += 2 if pp > pn else 1 if pp == pn else 0
    return {
        "denominators": {
            "assigned_route_days": len(route_ids), "assigned_candidates": len(selected),
            "probability_contract_eligible": len(selected), "rank_only": 0,
            "probability_known": len(known_p), "missing_probability": len(selected) - len(known_p),
            "invalid_probability": 0, "late_probability": 0,
            "mature_labels": sum(row["label"] is not None for row in selected),
            "nullable_labels": sum(row["label"] is None for row in selected),
            "nullable_labels_by_state": dict(sorted(Counter(row["outcome_state"] for row in selected if row["label"] is None).items())),
            "jointly_evaluable": len(joint), "complete_route_days": len(route_briers), "partial_route_days": len(partial),
            "issued_route_days": 0, "abstained_route_days": 0, "itt_included_route_days": len(route_ids),
        },
        "analysis_status": "COMPLETE_SYNTHETIC_MECHANICS" if finalizable else "PARTIAL_NOT_COMPARABLE",
        "candidate_micro_brier": rat(brier) if brier is not None and finalizable else None,
        "route_day_macro_brier": rat(route_macro) if route_macro is not None and finalizable else None,
        "partial_route_day_ids": partial,
        "mean_probability": rat(mean_p) if mean_p is not None and finalizable else None,
        "event_rate": rat(event_rate) if event_rate is not None and finalizable else None,
        "calibration_in_the_large": rat(mean_p - event_rate) if mean_p is not None and event_rate is not None and finalizable else None,
        "reliability_bins": [{**cell, "mean_probability": cell["mean_probability"] if finalizable else None, "event_rate": cell["event_rate"] if finalizable else None, "signed_gap": cell["signed_gap"] if finalizable else None, "absolute_gap": cell["absolute_gap"] if finalizable else None} for cell in cell_rows],
        "reportable_bin_ece_l1": rat(ece) if ece is not None and finalizable else None,
        "reportable_bin_mce": rat(mce) if mce is not None and finalizable else None,
        "squared_l2_calibration_error": rat(l2) if l2 is not None and finalizable else None,
        "rank_concordance_pair_counts": {"positive_negative_pairs": len(positives) * len(negatives), "concordant_half_units": concordant_units} if finalizable else None,
        "available_case_sufficient_statistics": {"jointly_evaluable": len(joint), "brier_sum": rat(sum(brier_terms, Fraction())) if brier_terms else None, "positive": sum(row["label"] is True for row in joint)},
        "symbolic_log_loss": _log_terms(selected),
        "calibration_slope_intercept": {"status": "NOT_COMPUTED_NO_REGISTERED_NUMERIC_SOLVER", "intercept": None, "slope": None},
    }


def _math_problem(route: dict[str, Any], ledger: list[dict[str, Any]], frozen_input_sha256: str, fit_sha256: str, unknown_candidate: str | None = None, scenario_id: str = "CANONICAL_ALL_PROBABILITIES_KNOWN") -> dict[str, Any]:
    by_id = {row["candidate_id"]: row for row in ledger if row["route_day_id"] == route["route_day_id"]}
    fractions = sorted({Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) for row in by_id.values() if row["calibrated_probability"] is not None})
    tiers = {value: index + 1 for index, value in enumerate(fractions)}
    candidates = []
    for source in route["candidates"]:
        row = by_id[source["candidate_id"]]
        unknown = source["candidate_id"] == unknown_candidate or row["calibrated_probability"] is None
        p = None if unknown else Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"])
        candidates.append({
            "candidate_id": source["candidate_id"], "physical_location_id": source["physical_location_id"], **deepcopy(source["math"]),
            "value_state": "UNKNOWN" if unknown else "REGISTERED_SYNTHETIC_PROXY",
            "business_value_units": None if unknown else tiers[p],
        })
    route_vector = [{"candidate_id": row["candidate_id"], "probability_state": row["probability_state"], "calibrated_probability": row["calibrated_probability"]} for row in sorted(by_id.values(), key=lambda value: value["candidate_id"])]
    policy_binding = {"adapter": "CALIBRATED_PROBABILITY_TIED_TIERS_V1", "frozen_input_sha256": frozen_input_sha256, "fit_sha256": fit_sha256, "route_prediction_vector_sha256": digest_json(route_vector), "scenario_id": scenario_id, "unknown_candidate_id": unknown_candidate}
    return {
        "schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY",
        "decision_id": f"CALIBRATION_DECISION:{route['route_day_id']}:{unknown_candidate or 'KNOWN'}",
        "snapshot": {"snapshot_id": f"CALIBRATION_SNAPSHOT:{route['route_day_id']}", "snapshot_sha256": digest_json({"route_day_id": route["route_day_id"], "candidate_universe_sha256": route["candidate_universe_sha256"]}), "stage1_cutoff": route["decision_at"], "issued_at": route["issued_at"], "protected_bundle_complete": True, "protected_tokens": []},
        "route_day": {"representative_id": route["representative_id"], "route_date": route["route_date"]},
        "policy": {"policy_version": "math-policy-v1", "policy_sha256": digest_json(policy_binding), "epsilon_business_value_units": 0, "maximum_candidates": 20, "max_total_service_minutes": 100, "composition_caps": {"NORTH": 10, "SOUTH": 10}, "required_unique_grains": [], "incompatible_candidate_pairs": [], "redundancy_penalties": [], "interference_penalties": []},
        "candidates": candidates,
    }


def _prediction_bin_tv(ledger: list[dict[str, Any]], first_route_id: str, second_route_id: str) -> Fraction:
    def distribution(route_id: str) -> dict[str, Fraction]:
        rows = [row for row in ledger if row["route_day_id"] == route_id and row["calibrated_bin_id"] is not None]
        if not rows:
            raise ValueError("NOT_COMPUTABLE_ALL_PROBABILITIES_UNKNOWN")
        return {spec["bin_id"]: Fraction(sum(row["calibrated_bin_id"] == spec["bin_id"] for row in rows), len(rows)) for spec in BINS}
    first, second = distribution(first_route_id), distribution(second_route_id)
    return sum((abs(first[row["bin_id"]] - second[row["bin_id"]]) for row in BINS), Fraction()) / 2


def build_run(frozen_input: dict[str, Any] | None = None, benchmark: dict[str, Any] | None = None, baseline_run: dict[str, Any] | None = None) -> dict[str, Any]:
    frozen_input = build_input() if frozen_input is None else frozen_input
    benchmark = json.loads((ROOT / "artifacts/baselines/frozen_benchmark.json").read_text()) if benchmark is None else benchmark
    baseline_run = json.loads((ROOT / "artifacts/baselines/canonical_run.json").read_text()) if baseline_run is None else baseline_run
    raw = _raw_probabilities(benchmark, baseline_run)
    fit = _fit(benchmark, raw)
    ledger = _ledger(benchmark, raw, fit)
    routes = {row["route_day_id"]: row for row in benchmark["routes"]}
    split_route_ids = {split: [row["route_day_id"] for row in benchmark["routes"] if row["split"] == split] for split in ["VALIDATION", "TEST"]}
    split_metrics = {split: _metrics(ledger, route_ids) for split, route_ids in split_route_ids.items()}
    split_metrics["VALIDATION"]["evaluation_role"] = "CALIBRATOR_FIT_DIAGNOSTIC_NOT_OUT_OF_TIME_EVALUATION"
    split_metrics["TEST"]["evaluation_role"] = "OUT_OF_TIME_SYNTHETIC_TEST_MECHANICS"
    subgroup_cells = {}
    for segment in ["A", "B", "C", "UNKNOWN"]:
        segment_rows = [row for row in ledger if row["split"] == "TEST" and row["market_segment"] == segment]
        route_counts = {route_id: sum(row["route_day_id"] == route_id for row in segment_rows) for route_id in split_route_ids["TEST"]}
        subgroup_cells[segment] = _metrics(segment_rows, split_route_ids["TEST"], len(segment_rows), route_counts)
    subgroup_metrics = {"cells": subgroup_cells, "summary": {"all_preregistered_cells_reportable": False, "pairwise_gap_status": "NULL_INCOMPLETE_PREREGISTERED_CELLS", "pairwise_gaps": None, "worst_cell": None, "claim": "SYNTHETIC_DESCRIPTIVE_SENSITIVITY_ONLY_NOT_FAIRNESS"}}
    temporal_periods = {route_id: _metrics(ledger, [route_id]) for route_id in split_route_ids["TEST"]}
    period_briers = [Fraction(temporal_periods[route_id]["candidate_micro_brier"]["numerator"], temporal_periods[route_id]["candidate_micro_brier"]["denominator"]) for route_id in split_route_ids["TEST"]]
    tv = _prediction_bin_tv(ledger, *split_route_ids["TEST"])
    temporal_metrics = {"periods": temporal_periods, "summary": {"candidate_micro_brier": split_metrics["TEST"]["candidate_micro_brier"], "equal_period_macro_brier": rat(sum(period_briers, Fraction()) / len(period_briers)), "max_minus_min_brier_sensitivity": rat(max(period_briers) - min(period_briers)), "signed_adjacent_brier_change": rat(period_briers[1] - period_briers[0]), "prediction_bin_total_variation": rat(tv), "claim": "SYNTHETIC_TEMPORAL_SENSITIVITY_ONLY_NOT_STABILITY"}}
    math_runs = []
    for route_id in split_route_ids["TEST"]:
        problem = _math_problem(routes[route_id], ledger, digest_json(frozen_input), fit["fit_sha256"])
        decision = decide(problem)
        math_runs.append({"route_day_id": route_id, "scenario_id": "CANONICAL_ALL_PROBABILITIES_KNOWN", "math_problem": problem, "math_decision": decision, "math_problem_sha256": digest_json(problem), "math_decision_sha256": digest_json(decision)})
    scenario_runs = [{"scenario_id": "CANONICAL_ALL_PROBABILITIES_KNOWN", "route_day_id": split_route_ids["TEST"][0], "metrics": _metrics(ledger, [split_route_ids["TEST"][0]]), "math_decision": math_runs[0]["math_decision"]}]
    unknown_id = "CAND:SYN_BASE_07_01"
    unknown_ledger = deepcopy(ledger)
    target = next(row for row in unknown_ledger if row["candidate_id"] == unknown_id)
    target.update({"probability_state": "UNKNOWN_INPUT", "calibrated_probability": None, "calibrated_bin_id": None})
    problem = _math_problem(routes["ROUTE_DAY:SYN_BASE_07"], unknown_ledger, digest_json(frozen_input), fit["fit_sha256"], unknown_id, "UNKNOWN_ADMISSIBLE_PROBABILITY")
    decision = decide(problem)
    unknown_metrics = _metrics(unknown_ledger, ["ROUTE_DAY:SYN_BASE_07"])
    unknown_metrics["denominators"].update({"issued_route_days": 0, "abstained_route_days": 1})
    scenario_runs.append({"scenario_id": "UNKNOWN_ADMISSIBLE_PROBABILITY", "route_day_id": "ROUTE_DAY:SYN_BASE_07", "metrics": unknown_metrics, "math_problem": problem, "math_decision": decision, "math_problem_sha256": digest_json(problem), "math_decision_sha256": digest_json(decision)})
    sparse_ledger = deepcopy(ledger)
    sparse_target = next(row for row in sparse_ledger if row["candidate_id"] == "CAND:SYN_BASE_07_01")
    sparse_target.update({"calibrated_probability": {"numerator": 9, "denominator": 10}, "calibrated_bin_id": "B4"})
    sparse_metrics = _metrics(sparse_ledger, ["ROUTE_DAY:SYN_BASE_07"])
    scenario_runs.append({"scenario_id": "SPARSE_OCCUPIED_RELIABILITY_CELL", "route_day_id": "ROUTE_DAY:SYN_BASE_07", "metrics": sparse_metrics, "assertion": {"occupied_cell_state": "SPARSE_NOT_ESTIMABLE", "reliability_point_estimates_are_null": True, "synthetic_sufficient_statistics_retained": True}})
    missing_ledger = deepcopy(ledger)
    missing_id = "CAND:SYN_BASE_08_12"
    missing_target = next(row for row in missing_ledger if row["candidate_id"] == missing_id)
    missing_target.update({"market_segment": "UNKNOWN", "feature_missingness_state": "MISSING_MODEL_INPUT", "probability_state": "UNKNOWN_INPUT", "raw_probability": None, "raw_bin_id": None, "calibrated_probability": None, "calibrated_bin_id": None})
    missing_problem = _math_problem(routes["ROUTE_DAY:SYN_BASE_08"], missing_ledger, digest_json(frozen_input), fit["fit_sha256"], missing_id, "MISSING_MODEL_FEATURE_AND_SUBGROUP")
    missing_decision = decide(missing_problem)
    missing_metrics = _metrics(missing_ledger, ["ROUTE_DAY:SYN_BASE_08"])
    missing_metrics["denominators"].update({"issued_route_days": 0, "abstained_route_days": 1})
    scenario_runs.append({"scenario_id": "MISSING_MODEL_FEATURE_AND_SUBGROUP", "route_day_id": "ROUTE_DAY:SYN_BASE_08", "metrics": missing_metrics, "unknown_subgroup_cell": {"assigned_candidates": 1, "probability_known": 0, "cell_state": "SPARSE_NOT_ESTIMABLE", "pairwise_gaps": None}, "math_problem": missing_problem, "math_decision": missing_decision, "math_problem_sha256": digest_json(missing_problem), "math_decision_sha256": digest_json(missing_decision)})
    split_metrics["TEST"]["denominators"].update({"issued_route_days": 2, "abstained_route_days": 0})
    for value in temporal_metrics["periods"].values():
        value["denominators"].update({"issued_route_days": 1, "abstained_route_days": 0})
    for value in subgroup_metrics["cells"].values():
        value["denominators"].update({"issued_route_days": 2, "abstained_route_days": 0})
    scenario_runs[0]["metrics"]["denominators"].update({"issued_route_days": 1, "abstained_route_days": 0})
    eligibility = {
        "registered_probability_head": "BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1",
        "eligible_streams": ["BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1"],
        "ineligible_rank_streams": ["INCUMBENT_SYNTHETIC_V1", "SEEDED_RANDOM_SYNTHETIC_V1", "TRANSPARENT_RULE_SYNTHETIC_V1", "RECENCY_SOURCE_SYNTHETIC_V1", "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1"],
        "ordinal_business_value_is_probability": False,
    }
    uncertainty = {"status": "NOT_EMPIRICALLY_ESTIMABLE", "standard_error": None, "confidence_interval": None, "p_value": None, "reason": "Frozen synthetic fixture; no independent historical sample.", "required_gate": "GATE-OUTCOME-LABELS-MATURITY-001", "scenario_values_are_evidence": False}
    claims = {"real_calibration": False, "predictive_validity": False, "fairness": False, "temporal_stability": False, "causal_lift": False, "commercial_value": False, "production_readiness": False, "live_use": False}
    bindings = {**frozen_input["bindings"], "frozen_input_sha256": digest_json(frozen_input), "calibration_input_schema_sha256": digest_file(ROOT / "contracts/calibration_input.schema.json"), "calibration_evaluation_schema_sha256": digest_file(ROOT / "contracts/calibration_evaluation.schema.json"), "math_evaluator_sha256": digest_file(ROOT / "evals/public/math_oracle_evaluator.py")}
    receipt_core = {
        "builder_id": "calibration-framework-builder-v1", "builder_sha256": digest_file(Path(__file__)), "bindings": bindings,
        "eligibility_sha256": digest_json(eligibility), "fit_sha256": fit["fit_sha256"], "prediction_ledger_sha256": digest_json(ledger),
        "split_metrics_sha256": digest_json(split_metrics), "subgroup_metrics_sha256": digest_json(subgroup_metrics), "temporal_metrics_sha256": digest_json(temporal_metrics),
        "math_runs_sha256": digest_json(math_runs), "scenario_runs_sha256": digest_json(scenario_runs), "uncertainty_sha256": digest_json(uncertainty), "claims_sha256": digest_json(claims), "proof_sha256": digest_json(PROOF),
    }
    return {
        "document_kind": "SYNTHETIC_CALIBRATION_EVALUATION_RUN", "schema_version": "1.0.0", "execution_scope": SCOPE,
        "run_id": "CALIBRATION_RUN:FROZEN_SYNTHETIC_V1", "state": "SYNTHETIC_MECHANICS_COMPLETE", "bindings": bindings,
        "probability_eligibility": eligibility, "fit": fit, "prediction_ledger": ledger, "split_metrics": split_metrics,
        "subgroup_metrics": subgroup_metrics, "temporal_metrics": temporal_metrics, "math_runs": math_runs, "scenario_runs": scenario_runs,
        "uncertainty": uncertainty, "claims": claims, "replay_receipt": {**receipt_core, "receipt_sha256": digest_json(receipt_core)}, "proof": PROOF,
    }


def write_artifacts() -> dict[str, Any]:
    root = ROOT / "artifacts/calibration"
    root.mkdir(parents=True, exist_ok=True)
    frozen_input = build_input()
    run = build_run(frozen_input)
    (root / "frozen_input.json").write_text(json.dumps(frozen_input, indent=2, sort_keys=True) + "\n")
    (root / "canonical_run.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    return run
