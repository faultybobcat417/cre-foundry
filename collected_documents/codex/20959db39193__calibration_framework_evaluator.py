"""Independent exact evaluator for CALIBRATION-001.

This module intentionally does not import ``cre_foundry.calibration``.  It
reconstructs the frozen probability adapter, validation fit, evaluation
tables, and MATH decisions from pinned upstream artifacts.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from evals.public.math_oracle_evaluator import evaluate as math_evaluate

ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "artifacts/calibration/frozen_input.json"
RUN_PATH = ROOT / "artifacts/calibration/canonical_run.json"
CONTRACT_PATH = ROOT / "artifacts/calibration/public_evaluator_contract.json"
INPUT_SCHEMA_PATH = ROOT / "contracts/calibration_input.schema.json"
RUN_SCHEMA_PATH = ROOT / "contracts/calibration_evaluation.schema.json"
BENCHMARK_PATH = ROOT / "artifacts/baselines/frozen_benchmark.json"
BASELINE_REGISTRY_PATH = ROOT / "artifacts/baselines/policy_registry.json"
BASELINE_RUN_PATH = ROOT / "artifacts/baselines/canonical_run.json"
EXPECTED_FILE_HASHES = {
    "benchmark": "c932f637f9476b03bb5694dcfa8d01c55a67aef8dff59befb4c44a31c427e776",
    "baseline_registry": "643021f63f0749098a6d89f646d6679b9ce37b67f20af600294117c7fe95033f",
    "baseline_run": "504f42bb36bee7cb537f7c253eb21aa5d254ce3842a70c065a4087e1664e4377",
    "frozen_input": "421f2ab854dc029311aa225def1314143b1b41fd165d7c363608e61c547d832b",
    "contract": "0ccc1e20cdde7aea06cd29f7f0544856a9f715bebb7d6a1407472d812087bc98",
    "builder": "b0d5dc3a67544d87a062ed6f0b667e5acc6f66b479fe299a44b05a0dfa342ea1",
    "input_schema": "1c2c09f20c4a9b834047c11b9d38fe6b6243f5d9c769246b369ebcb9813709fc",
    "run_schema": "a8dd511ddfc81aa7c0cb39a2b9063cb6bf382e6515ccc3a4bcf0a0d33d3bae5d",
    "outcomes_contract": "69f19bea1007183d8566b47d2a9a6015132f94832c3ec5abe2fb12367afae518",
    "outcomes_policy": "fba35b2df51769c558844792d84bff7270c970912464a2833e9f999d6cefd5e6",
    "outcomes_run": "6b3d6a91ba3397481ddb332f2ca2c37c8fab44f3de85b28a4e9e6ec2c764a0b2",
    "math_contract": "abfade5dadd1e34af40adca017648070e6af39f9fd84cae2add7b30fa3763a29",
    "math_problem_schema": "3942db4a53405c57c8cf7edfcbcda26262b6457de80f55ca4620278ec0ae04fd",
    "math_decision_schema": "b3929312d94633c5fdebb68f2df705c51bdb2868fa4941b97993e0fd6a1c0cb1",
    "math_evaluator": "5521bb4e224df013b5232bb8be7d41bf8f472b762087bd6b734829cea73f870e",
}
BINS = [
    ("B0", Fraction(0), Fraction(1, 5), False),
    ("B1", Fraction(1, 5), Fraction(2, 5), False),
    ("B2", Fraction(2, 5), Fraction(3, 5), False),
    ("B3", Fraction(3, 5), Fraction(4, 5), False),
    ("B4", Fraction(4, 5), Fraction(1), True),
]
PROOF = {
    "level": 5, "claim": "synthetic calibration framework and replay conformance only",
    "real_probability_semantics_proven": False, "real_calibration_proven": False,
    "fairness_or_stability_proven": False, "incremental_lift_proven": False,
    "commercial_value_proven": False, "production_authorized": False, "live_use_authorized": False,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(path: Path) -> Any:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=no_duplicates)


def rat(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _bin(value: Fraction) -> str:
    for name, lower, upper, inclusive in BINS:
        if value >= lower and (value < upper or inclusive and value <= upper):
            return name
    raise ValueError("probability outside [0,1]")


def _values(candidate: dict[str, Any]) -> dict[str, Any]:
    return {row["feature_definition_id"].split(":")[1]: row["value"] for row in candidate["features"]}


def _expected_input(benchmark: dict[str, Any], baseline_registry: dict[str, Any], baseline_run: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_kind": "FROZEN_SYNTHETIC_CALIBRATION_INPUT", "schema_version": "1.0.0", "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "registry_id": "CALIBRATION_INPUT:FROZEN_V1", "registered_at": "2026-04-15T00:00:00Z",
        "probability_head": {"head_id": "BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1", "target": "F9_WITHIN_REGISTERED_WINDOW_W_GIVEN_STAGE1_POINT_IN_TIME_INFORMATION", "estimand_kind": "OBSERVATIONAL_CANDIDATE_RISK_NOT_CAUSAL_EFFECT_OR_ROUTE_DAY_ITT", "numeric_domain": "CANONICAL_REDUCED_EXACT_RATIONAL_0_TO_1_INCLUSIVE", "source_policy_id": "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1", "all_baseline_policy_streams_are_rank_only": True},
        "calibrator": {"calibrator_id": "FIXED_BIN_BETA_BINOMIAL_ALPHA_1_BETA_1:V1", "registered_at": "2026-04-15T00:00:00Z", "validation_fit_at": "2026-07-07T00:00:00Z", "fit_partition": "VALIDATION_COMPLETE_CANDIDATE_UNIVERSE_ONLY", "alpha": 1, "beta": 1, "minimum_cell_count": 4, "unseen_or_sparse_fallback": "UNKNOWN_INPUT", "test_reuse_allowed": False},
        "bins": [{"bin_id": name, "lower": [lo.numerator, lo.denominator], "upper": [hi.numerator, hi.denominator], "upper_inclusive": inc} for name, lo, hi, inc in BINS],
        "analysis": {"subgroup_dimension": "market_segment", "subgroup_values": ["A", "B", "C", "UNKNOWN"], "temporal_unit": "ROUTE_DAY_CHRONOLOGICAL", "primary_population": "FULL_COMMON_CANDIDATE_UNIVERSE_NOT_SELECTED_TEN", "macro_micro_separate": True, "uncertainty_status": "NOT_EMPIRICALLY_ESTIMABLE"},
        "scenarios": [{"scenario_id": "CANONICAL_ALL_PROBABILITIES_KNOWN", "probability_override": None}, {"scenario_id": "UNKNOWN_ADMISSIBLE_PROBABILITY", "probability_override": {"route_day_id": "ROUTE_DAY:SYN_BASE_07", "candidate_id": "CAND:SYN_BASE_07_01", "state": "UNKNOWN_INPUT"}}, {"scenario_id": "SPARSE_OCCUPIED_RELIABILITY_CELL", "candidate_ids": ["CAND:SYN_BASE_07_01"]}, {"scenario_id": "MISSING_MODEL_FEATURE_AND_SUBGROUP", "probability_override": {"route_day_id": "ROUTE_DAY:SYN_BASE_08", "candidate_id": "CAND:SYN_BASE_08_12", "state": "UNKNOWN_INPUT", "market_segment": "UNKNOWN"}}],
        "bindings": {
            "baseline_benchmark_sha256": digest_file(BENCHMARK_PATH), "baseline_registry_sha256": digest_file(BASELINE_REGISTRY_PATH), "baseline_run_sha256": digest_file(BASELINE_RUN_PATH),
            "outcomes_contract_sha256": digest_file(ROOT / "artifacts/outcomes/public_evaluator_contract.json"), "outcomes_policy_sha256": digest_file(ROOT / "artifacts/outcomes/synthetic_window_policy.json"), "outcomes_run_sha256": digest_file(ROOT / "artifacts/outcomes/canonical_run.json"), "math_contract_sha256": digest_file(ROOT / "artifacts/math/public_evaluator_contract.json"), "math_problem_schema_sha256": digest_file(ROOT / "contracts/math_decision_policy.schema.json"), "math_decision_schema_sha256": digest_file(ROOT / "contracts/math_route_decision.schema.json"), "public_evaluator_contract_sha256": digest_file(CONTRACT_PATH),
        },
        "claim_ceiling": "Synthetic calibration, missingness, subgroup, temporal, MATH projection, and abstention mechanics only; no real calibration, prediction, fairness, stability, causal lift, commercial value, production fitness, or authority.",
    }


def _raw(benchmark: dict[str, Any], baseline_run: dict[str, Any]) -> dict[tuple[str, str], Fraction]:
    counts = baseline_run["fit"]["bucket_counts"]
    result = {}
    for route in benchmark["routes"]:
        if route["split"] in {"VALIDATION", "TEST"}:
            for candidate in route["candidates"]:
                row = counts[_values(candidate)["market_segment"]]
                result[(route["route_day_id"], candidate["candidate_id"])] = Fraction(row["positive"] + 1, row["mature"] + 2)
    return result


def _fit(benchmark: dict[str, Any], raw: dict[tuple[str, str], Fraction]) -> dict[str, Any]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    work = {name: {"positive": 0, "mature": 0, "included_row_ids": [], "excluded_row_ids": []} for name, *_ in BINS}
    for route in benchmark["routes"]:
        if route["split"] != "VALIDATION":
            continue
        route_labels = [labels[(route["route_day_id"], candidate["candidate_id"])] for candidate in route["candidates"]]
        route_complete = all(label["label"] is not None and label["available_at"] <= "2026-07-07T00:00:00Z" for label in route_labels)
        for candidate in route["candidates"]:
            key = (route["route_day_id"], candidate["candidate_id"])
            row_id = "|".join(key)
            label = labels[key]
            cell = work[_bin(raw[key])]
            if not route_complete:
                cell["excluded_row_ids"].append(row_id)
            else:
                cell["included_row_ids"].append(row_id)
                cell["mature"] += 1
                cell["positive"] += int(label["label"] is True)
    cells = []
    for name, *_ in BINS:
        row = work[name]
        row["included_row_ids"].sort()
        row["excluded_row_ids"].sort()
        state = "EMPTY_NOT_ESTIMABLE" if row["mature"] == 0 else "SPARSE_NOT_ESTIMABLE" if row["mature"] < 4 else "REPORTABLE_SYNTHETIC_MECHANICS"
        posterior = rat(Fraction(row["positive"] + 1, row["mature"] + 2)) if row["mature"] >= 4 else None
        cells.append({"bin_id": name, **row, "cell_state": state, "posterior_probability": posterior})
    core = {"calibrator_id": "FIXED_BIN_BETA_BINOMIAL_ALPHA_1_BETA_1:V1", "fit_at": "2026-07-07T00:00:00Z", "fit_partition": "VALIDATION", "population": {"assigned_candidate_rows": 24, "included_mature_rows": sum(row["mature"] for row in cells), "excluded_null_or_late_rows": sum(len(row["excluded_row_ids"]) for row in cells), "selected_ten_rows_used": 0, "train_rows_used": 0, "test_rows_used": 0, "route_states": {"ROUTE_DAY:SYN_BASE_05": "EXCLUDED_WHOLE_ROUTE_INCOMPLETE_AT_FIT", "ROUTE_DAY:SYN_BASE_06": "INCLUDED_COMPLETE_ROUTE"}}, "cells": cells}
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
            q = posterior[_bin(p0)]
            label = labels[key]
            rows.append({"route_day_id": route["route_day_id"], "candidate_id": candidate["candidate_id"], "physical_location_id": candidate["physical_location_id"], "split": route["split"], "decision_at": route["decision_at"], "prediction_frozen_at": route["decision_at"], "prediction_clock_scope": "RAW_REGISTERED_HEAD_PER_ROUTE", "calibration_fit_at": "2026-07-07T00:00:00Z", "calibrated_probability_available_at": "2026-07-07T00:00:00Z" if route["split"] == "VALIDATION" else route["decision_at"], "evaluation_role": "CALIBRATOR_FIT_DIAGNOSTIC_NOT_OUT_OF_TIME_EVALUATION" if route["split"] == "VALIDATION" else "OUT_OF_TIME_SYNTHETIC_TEST_MECHANICS", "fit_inclusion_state": ("EXCLUDED_WHOLE_ROUTE_INCOMPLETE_AT_FIT" if route["route_day_id"] == "ROUTE_DAY:SYN_BASE_05" else "INCLUDED_COMPLETE_VALIDATION_ROUTE") if route["split"] == "VALIDATION" else "NOT_A_FIT_ROW_TEST_ONLY", "label_available_at": label["available_at"], "market_segment": _values(candidate).get("market_segment", "UNKNOWN"), "feature_missingness_state": "OBSERVED", "probability_state": "ELIGIBLE_REGISTERED_SYNTHETIC_PROBABILITY" if q else "UNKNOWN_INPUT", "raw_probability": rat(p0), "raw_bin_id": _bin(p0), "calibrated_probability": q, "calibrated_bin_id": _bin(Fraction(q["numerator"], q["denominator"])) if q else None, "outcome_state": label["state"], "label": label["label"], "current_head": label["current_head"], "assessment_sha256": label["assessment_sha256"]})
    return sorted(rows, key=lambda row: (row["split"], row["route_day_id"], row["candidate_id"]))


def _log_terms(rows: list[dict[str, Any]]) -> dict[str, Any]:
    incomplete = [row["candidate_id"] for row in rows if row["calibrated_probability"] is None or row["label"] is None]
    if incomplete:
        return {"status": "NOT_COMPUTABLE_INCOMPLETE_UNIVERSE", "terms": [], "incomplete_candidate_ids": sorted(incomplete)}
    terms: Counter[tuple[int, int, bool]] = Counter()
    for row in rows:
        q = Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"])
        if (row["label"] and q == 0) or (not row["label"] and q == 1):
            return {"status": "POSITIVE_INFINITY", "terms": []}
        target = q if row["label"] else 1 - q
        terms[(target.denominator, target.numerator, bool(row["label"]))] += 1
    return {"status": "CANONICAL_SYMBOLIC_LOG_RATIONAL_TERMS", "terms": [{"coefficient": count, "log_ratio_numerator": n, "log_ratio_denominator": d, "label": label} for (n, d, label), count in sorted(terms.items())], "normalization_denominator": sum(terms.values())}


def _metrics(
    rows: list[dict[str, Any]],
    route_ids: list[str],
    expected_candidate_count: int | None = None,
    expected_route_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    selected = [row for row in rows if row["route_day_id"] in route_ids]
    expected_candidate_count = 12 * len(route_ids) if expected_candidate_count is None else expected_candidate_count
    expected_route_counts = {route_id: 12 for route_id in route_ids} if expected_route_counts is None else expected_route_counts
    known = [row for row in selected if row["calibrated_probability"] is not None]
    joint = [row for row in known if row["label"] is not None]
    probs = [Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) for row in joint]
    brier = sum(((p - int(row["label"])) ** 2 for p, row in zip(probs, joint)), Fraction()) / len(joint) if joint else None
    mean_p = sum(probs, Fraction()) / len(probs) if probs else None
    rate = Fraction(sum(row["label"] is True for row in joint), len(joint)) if joint else None
    cells = []
    for name, *_ in BINS:
        group = [row for row in joint if row["calibrated_bin_id"] == name]
        n = len(group)
        state = "EMPTY_NOT_ESTIMABLE" if n == 0 else "SPARSE_NOT_ESTIMABLE" if n < 4 else "REPORTABLE_SYNTHETIC_MECHANICS"
        mp = sum((Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) for row in group), Fraction()) / n if n else None
        er = Fraction(sum(row["label"] is True for row in group), n) if n else None
        gap = mp - er if state == "REPORTABLE_SYNTHETIC_MECHANICS" else None
        cells.append({"bin_id": name, "count": n, "positive": sum(row["label"] is True for row in group), "cell_state": state, "mean_probability": rat(mp) if gap is not None else None, "event_rate": rat(er) if gap is not None else None, "signed_gap": rat(gap) if gap is not None else None, "absolute_gap": rat(abs(gap)) if gap is not None else None})
    reportable = [row for row in cells if row["cell_state"] == "REPORTABLE_SYNTHETIC_MECHANICS"]
    rn = sum(row["count"] for row in reportable)
    occupied_sparse = any(row["cell_state"] == "SPARSE_NOT_ESTIMABLE" for row in cells)
    ece = sum((Fraction(row["absolute_gap"]["numerator"], row["absolute_gap"]["denominator"]) * row["count"] for row in reportable), Fraction()) / rn if rn and not occupied_sparse else None
    mce = max((Fraction(row["absolute_gap"]["numerator"], row["absolute_gap"]["denominator"]) for row in reportable), default=None) if not occupied_sparse else None
    l2 = sum((Fraction(row["signed_gap"]["numerator"], row["signed_gap"]["denominator"]) ** 2 * row["count"] for row in reportable), Fraction()) / rn if rn and not occupied_sparse else None
    route_briers, partial = [], []
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
    macro = sum(route_briers, Fraction()) / len(route_briers) if route_briers and not partial else None
    universe_incomplete = len(selected) != expected_candidate_count
    if universe_incomplete:
        partial = sorted(set(partial) | set(route_ids))
    finalizable = expected_candidate_count > 0 and not partial and not universe_incomplete
    positives = [row for row in joint if row["label"] is True]
    negatives = [row for row in joint if row["label"] is False]
    units = 0
    for pos in positives:
        pp = Fraction(pos["calibrated_probability"]["numerator"], pos["calibrated_probability"]["denominator"])
        for neg in negatives:
            pn = Fraction(neg["calibrated_probability"]["numerator"], neg["calibrated_probability"]["denominator"])
            units += 2 if pp > pn else 1 if pp == pn else 0
    brier_terms = [(Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) - int(row["label"])) ** 2 for row in joint]
    return {"denominators": {"assigned_route_days": len(route_ids), "assigned_candidates": len(selected), "probability_contract_eligible": len(selected), "rank_only": 0, "probability_known": len(known), "missing_probability": len(selected) - len(known), "invalid_probability": 0, "late_probability": 0, "mature_labels": sum(row["label"] is not None for row in selected), "nullable_labels": sum(row["label"] is None for row in selected), "nullable_labels_by_state": dict(sorted(Counter(row["outcome_state"] for row in selected if row["label"] is None).items())), "jointly_evaluable": len(joint), "complete_route_days": len(route_briers), "partial_route_days": len(partial), "issued_route_days": 0, "abstained_route_days": 0, "itt_included_route_days": len(route_ids)}, "analysis_status": "COMPLETE_SYNTHETIC_MECHANICS" if finalizable else "PARTIAL_NOT_COMPARABLE", "candidate_micro_brier": rat(brier) if brier is not None and finalizable else None, "route_day_macro_brier": rat(macro) if macro is not None and finalizable else None, "partial_route_day_ids": partial, "mean_probability": rat(mean_p) if mean_p is not None and finalizable else None, "event_rate": rat(rate) if rate is not None and finalizable else None, "calibration_in_the_large": rat(mean_p - rate) if mean_p is not None and finalizable else None, "reliability_bins": [{**cell, "mean_probability": cell["mean_probability"] if finalizable else None, "event_rate": cell["event_rate"] if finalizable else None, "signed_gap": cell["signed_gap"] if finalizable else None, "absolute_gap": cell["absolute_gap"] if finalizable else None} for cell in cells], "reportable_bin_ece_l1": rat(ece) if ece is not None and finalizable else None, "reportable_bin_mce": rat(mce) if mce is not None and finalizable else None, "squared_l2_calibration_error": rat(l2) if l2 is not None and finalizable else None, "rank_concordance_pair_counts": {"positive_negative_pairs": len(positives) * len(negatives), "concordant_half_units": units} if finalizable else None, "available_case_sufficient_statistics": {"jointly_evaluable": len(joint), "brier_sum": rat(sum(brier_terms, Fraction())) if brier_terms else None, "positive": sum(row["label"] is True for row in joint)}, "symbolic_log_loss": _log_terms(selected), "calibration_slope_intercept": {"status": "NOT_COMPUTED_NO_REGISTERED_NUMERIC_SOLVER", "intercept": None, "slope": None}}


def _problem(route: dict[str, Any], ledger: list[dict[str, Any]], frozen_input_sha256: str, fit_sha256: str, unknown: str | None = None, scenario_id: str = "CANONICAL_ALL_PROBABILITIES_KNOWN") -> dict[str, Any]:
    by_id = {row["candidate_id"]: row for row in ledger if row["route_day_id"] == route["route_day_id"]}
    levels = sorted({Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"]) for row in by_id.values() if row["calibrated_probability"]})
    tiers = {value: i + 1 for i, value in enumerate(levels)}
    candidates = []
    for source in route["candidates"]:
        row = by_id[source["candidate_id"]]
        is_unknown = source["candidate_id"] == unknown or row["calibrated_probability"] is None
        p = None if is_unknown else Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"])
        candidates.append({"candidate_id": source["candidate_id"], "physical_location_id": source["physical_location_id"], **deepcopy(source["math"]), "value_state": "UNKNOWN" if is_unknown else "REGISTERED_SYNTHETIC_PROXY", "business_value_units": None if is_unknown else tiers[p]})
    vector = [{"candidate_id": row["candidate_id"], "probability_state": row["probability_state"], "calibrated_probability": row["calibrated_probability"]} for row in sorted(by_id.values(), key=lambda value: value["candidate_id"])]
    binding = {"adapter": "CALIBRATED_PROBABILITY_TIED_TIERS_V1", "frozen_input_sha256": frozen_input_sha256, "fit_sha256": fit_sha256, "route_prediction_vector_sha256": digest_json(vector), "scenario_id": scenario_id, "unknown_candidate_id": unknown}
    return {"schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY", "decision_id": f"CALIBRATION_DECISION:{route['route_day_id']}:{unknown or 'KNOWN'}", "snapshot": {"snapshot_id": f"CALIBRATION_SNAPSHOT:{route['route_day_id']}", "snapshot_sha256": digest_json({"route_day_id": route["route_day_id"], "candidate_universe_sha256": route["candidate_universe_sha256"]}), "stage1_cutoff": route["decision_at"], "issued_at": route["issued_at"], "protected_bundle_complete": True, "protected_tokens": []}, "route_day": {"representative_id": route["representative_id"], "route_date": route["route_date"]}, "policy": {"policy_version": "math-policy-v1", "policy_sha256": digest_json(binding), "epsilon_business_value_units": 0, "maximum_candidates": 20, "max_total_service_minutes": 100, "composition_caps": {"NORTH": 10, "SOUTH": 10}, "required_unique_grains": [], "incompatible_candidate_pairs": [], "redundancy_penalties": [], "interference_penalties": []}, "candidates": candidates}


def _prediction_bin_tv(ledger: list[dict[str, Any]], first_route_id: str, second_route_id: str) -> Fraction:
    def distribution(route_id: str) -> dict[str, Fraction]:
        rows = [row for row in ledger if row["route_day_id"] == route_id and row["calibrated_bin_id"] is not None]
        if not rows:
            raise ValueError("NOT_COMPUTABLE_ALL_PROBABILITIES_UNKNOWN")
        return {name: Fraction(sum(row["calibrated_bin_id"] == name for row in rows), len(rows)) for name, *_ in BINS}
    first, second = distribution(first_route_id), distribution(second_route_id)
    return sum((abs(first[name] - second[name]) for name, *_ in BINS), Fraction()) / 2


def _expected_sections(frozen_input: dict[str, Any], benchmark: dict[str, Any], baseline_run: dict[str, Any]) -> dict[str, Any]:
    raw = _raw(benchmark, baseline_run)
    fit = _fit(benchmark, raw)
    ledger = _ledger(benchmark, raw, fit)
    routes = {row["route_day_id"]: row for row in benchmark["routes"]}
    ids = {split: [row["route_day_id"] for row in benchmark["routes"] if row["split"] == split] for split in ["VALIDATION", "TEST"]}
    split_metrics = {split: _metrics(ledger, route_ids) for split, route_ids in ids.items()}
    split_metrics["VALIDATION"]["evaluation_role"] = "CALIBRATOR_FIT_DIAGNOSTIC_NOT_OUT_OF_TIME_EVALUATION"
    split_metrics["TEST"]["evaluation_role"] = "OUT_OF_TIME_SYNTHETIC_TEST_MECHANICS"
    subgroup_cells = {}
    for segment in ["A", "B", "C", "UNKNOWN"]:
        segment_rows = [row for row in ledger if row["split"] == "TEST" and row["market_segment"] == segment]
        route_counts = {route_id: sum(row["route_day_id"] == route_id for row in segment_rows) for route_id in ids["TEST"]}
        subgroup_cells[segment] = _metrics(segment_rows, ids["TEST"], len(segment_rows), route_counts)
    subgroup = {"cells": subgroup_cells, "summary": {"all_preregistered_cells_reportable": False, "pairwise_gap_status": "NULL_INCOMPLETE_PREREGISTERED_CELLS", "pairwise_gaps": None, "worst_cell": None, "claim": "SYNTHETIC_DESCRIPTIVE_SENSITIVITY_ONLY_NOT_FAIRNESS"}}
    periods = {route_id: _metrics(ledger, [route_id]) for route_id in ids["TEST"]}
    period_briers = [Fraction(periods[route_id]["candidate_micro_brier"]["numerator"], periods[route_id]["candidate_micro_brier"]["denominator"]) for route_id in ids["TEST"]]
    tv = _prediction_bin_tv(ledger, *ids["TEST"])
    temporal = {"periods": periods, "summary": {"candidate_micro_brier": split_metrics["TEST"]["candidate_micro_brier"], "equal_period_macro_brier": rat(sum(period_briers, Fraction()) / len(period_briers)), "max_minus_min_brier_sensitivity": rat(max(period_briers) - min(period_briers)), "signed_adjacent_brier_change": rat(period_briers[1] - period_briers[0]), "prediction_bin_total_variation": rat(tv), "claim": "SYNTHETIC_TEMPORAL_SENSITIVITY_ONLY_NOT_STABILITY"}}
    math_runs = []
    for route_id in ids["TEST"]:
        problem = _problem(routes[route_id], ledger, digest_json(frozen_input), fit["fit_sha256"])
        decision = math_evaluate(problem)
        math_runs.append({"route_day_id": route_id, "scenario_id": "CANONICAL_ALL_PROBABILITIES_KNOWN", "math_problem": problem, "math_decision": decision, "math_problem_sha256": digest_json(problem), "math_decision_sha256": digest_json(decision)})
    scenarios = [{"scenario_id": "CANONICAL_ALL_PROBABILITIES_KNOWN", "route_day_id": ids["TEST"][0], "metrics": _metrics(ledger, [ids["TEST"][0]]), "math_decision": math_runs[0]["math_decision"]}]
    altered = deepcopy(ledger)
    target = next(row for row in altered if row["candidate_id"] == "CAND:SYN_BASE_07_01")
    target.update({"probability_state": "UNKNOWN_INPUT", "calibrated_probability": None, "calibrated_bin_id": None})
    problem = _problem(routes["ROUTE_DAY:SYN_BASE_07"], altered, digest_json(frozen_input), fit["fit_sha256"], "CAND:SYN_BASE_07_01", "UNKNOWN_ADMISSIBLE_PROBABILITY")
    decision = math_evaluate(problem)
    unknown_metrics = _metrics(altered, ["ROUTE_DAY:SYN_BASE_07"])
    unknown_metrics["denominators"].update({"issued_route_days": 0, "abstained_route_days": 1})
    scenarios.append({"scenario_id": "UNKNOWN_ADMISSIBLE_PROBABILITY", "route_day_id": "ROUTE_DAY:SYN_BASE_07", "metrics": unknown_metrics, "math_problem": problem, "math_decision": decision, "math_problem_sha256": digest_json(problem), "math_decision_sha256": digest_json(decision)})
    sparse_ledger = deepcopy(ledger)
    sparse_target = next(row for row in sparse_ledger if row["candidate_id"] == "CAND:SYN_BASE_07_01")
    sparse_target.update({"calibrated_probability": {"numerator": 9, "denominator": 10}, "calibrated_bin_id": "B4"})
    sparse_metrics = _metrics(sparse_ledger, ["ROUTE_DAY:SYN_BASE_07"])
    scenarios.append({"scenario_id": "SPARSE_OCCUPIED_RELIABILITY_CELL", "route_day_id": "ROUTE_DAY:SYN_BASE_07", "metrics": sparse_metrics, "assertion": {"occupied_cell_state": "SPARSE_NOT_ESTIMABLE", "reliability_point_estimates_are_null": True, "synthetic_sufficient_statistics_retained": True}})
    missing_ledger = deepcopy(ledger)
    missing_id = "CAND:SYN_BASE_08_12"
    missing_target = next(row for row in missing_ledger if row["candidate_id"] == missing_id)
    missing_target.update({"market_segment": "UNKNOWN", "feature_missingness_state": "MISSING_MODEL_INPUT", "probability_state": "UNKNOWN_INPUT", "raw_probability": None, "raw_bin_id": None, "calibrated_probability": None, "calibrated_bin_id": None})
    missing_problem = _problem(routes["ROUTE_DAY:SYN_BASE_08"], missing_ledger, digest_json(frozen_input), fit["fit_sha256"], missing_id, "MISSING_MODEL_FEATURE_AND_SUBGROUP")
    missing_decision = math_evaluate(missing_problem)
    missing_metrics = _metrics(missing_ledger, ["ROUTE_DAY:SYN_BASE_08"])
    missing_metrics["denominators"].update({"issued_route_days": 0, "abstained_route_days": 1})
    scenarios.append({"scenario_id": "MISSING_MODEL_FEATURE_AND_SUBGROUP", "route_day_id": "ROUTE_DAY:SYN_BASE_08", "metrics": missing_metrics, "unknown_subgroup_cell": {"assigned_candidates": 1, "probability_known": 0, "cell_state": "SPARSE_NOT_ESTIMABLE", "pairwise_gaps": None}, "math_problem": missing_problem, "math_decision": missing_decision, "math_problem_sha256": digest_json(missing_problem), "math_decision_sha256": digest_json(missing_decision)})
    split_metrics["TEST"]["denominators"].update({"issued_route_days": 2, "abstained_route_days": 0})
    for value in temporal["periods"].values():
        value["denominators"].update({"issued_route_days": 1, "abstained_route_days": 0})
    for value in subgroup["cells"].values():
        value["denominators"].update({"issued_route_days": 2, "abstained_route_days": 0})
    scenarios[0]["metrics"]["denominators"].update({"issued_route_days": 1, "abstained_route_days": 0})
    eligibility = {"registered_probability_head": "BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1", "eligible_streams": ["BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1"], "ineligible_rank_streams": ["INCUMBENT_SYNTHETIC_V1", "SEEDED_RANDOM_SYNTHETIC_V1", "TRANSPARENT_RULE_SYNTHETIC_V1", "RECENCY_SOURCE_SYNTHETIC_V1", "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1"], "ordinal_business_value_is_probability": False}
    uncertainty = {"status": "NOT_EMPIRICALLY_ESTIMABLE", "standard_error": None, "confidence_interval": None, "p_value": None, "reason": "Frozen synthetic fixture; no independent historical sample.", "required_gate": "GATE-OUTCOME-LABELS-MATURITY-001", "scenario_values_are_evidence": False}
    claims = {"real_calibration": False, "predictive_validity": False, "fairness": False, "temporal_stability": False, "causal_lift": False, "commercial_value": False, "production_readiness": False, "live_use": False}
    bindings = {**frozen_input["bindings"], "frozen_input_sha256": digest_json(frozen_input), "calibration_input_schema_sha256": digest_file(INPUT_SCHEMA_PATH), "calibration_evaluation_schema_sha256": digest_file(RUN_SCHEMA_PATH), "math_evaluator_sha256": digest_file(ROOT / "evals/public/math_oracle_evaluator.py")}
    receipt = {"builder_id": "calibration-framework-builder-v1", "builder_sha256": digest_file(ROOT / "src/cre_foundry/calibration/framework.py"), "bindings": bindings, "eligibility_sha256": digest_json(eligibility), "fit_sha256": fit["fit_sha256"], "prediction_ledger_sha256": digest_json(ledger), "split_metrics_sha256": digest_json(split_metrics), "subgroup_metrics_sha256": digest_json(subgroup), "temporal_metrics_sha256": digest_json(temporal), "math_runs_sha256": digest_json(math_runs), "scenario_runs_sha256": digest_json(scenarios), "uncertainty_sha256": digest_json(uncertainty), "claims_sha256": digest_json(claims), "proof_sha256": digest_json(PROOF)}
    return {"bindings": bindings, "probability_eligibility": eligibility, "fit": fit, "prediction_ledger": ledger, "split_metrics": split_metrics, "subgroup_metrics": subgroup, "temporal_metrics": temporal, "math_runs": math_runs, "scenario_runs": scenarios, "uncertainty": uncertainty, "claims": claims, "replay_receipt": {**receipt, "receipt_sha256": digest_json(receipt)}, "proof": PROOF}


SECTION_DIAGNOSTICS = {
    "bindings": "CALIBRATION-FROZEN-COHORT-MISMATCH", "probability_eligibility": "CALIBRATION-PROBABILITY-INELIGIBLE",
    "fit": "CALIBRATION-FIT-REPLAY-MISMATCH", "prediction_ledger": "CALIBRATION-PREDICTION-REPLAY-MISMATCH",
    "split_metrics": "CALIBRATION-METRIC-REPLAY-MISMATCH", "subgroup_metrics": "CALIBRATION-SUBGROUP-DENOMINATOR",
    "temporal_metrics": "CALIBRATION-TEMPORAL-POOLING", "math_runs": "CALIBRATION-MATH-PROBABILITY-PROJECTION",
    "scenario_runs": "CALIBRATION-ABSTENTION-LOSS", "uncertainty": "CALIBRATION-INTERVAL-OVERCLAIM",
    "claims": "CALIBRATION-CLAIM-CEILING", "replay_receipt": "CALIBRATION-REPLAY-RECEIPT-MISMATCH", "proof": "CALIBRATION-CLAIM-CEILING",
}


def evaluate(subject: dict[str, Any] | None = None, frozen_input: dict[str, Any] | None = None) -> list[str]:
    try:
        subject = strict_load(RUN_PATH) if subject is None else subject
        frozen_input = strict_load(INPUT_PATH) if frozen_input is None else frozen_input
        benchmark, baseline_registry, baseline_run = strict_load(BENCHMARK_PATH), strict_load(BASELINE_REGISTRY_PATH), strict_load(BASELINE_RUN_PATH)
        expected_input = _expected_input(benchmark, baseline_registry, baseline_run)
        expected = _expected_sections(expected_input, benchmark, baseline_run)
        expected_top = {"document_kind": "SYNTHETIC_CALIBRATION_EVALUATION_RUN", "schema_version": "1.0.0", "execution_scope": "SYNTHETIC_NON_INFLUENCING", "run_id": "CALIBRATION_RUN:FROZEN_SYNTHETIC_V1", "state": "SYNTHETIC_MECHANICS_COMPLETE", **expected}
        semantic_error = _semantic_error(subject, frozen_input, expected_top, expected_input)
        if semantic_error is not None:
            return [semantic_error]
        for value, schema_path in [(frozen_input, INPUT_SCHEMA_PATH), (subject, RUN_SCHEMA_PATH)]:
            schema = strict_load(schema_path)
            error = next(iter(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)), None)
            if error:
                return ["CALIBRATION-SHAPE-SCHEMA"]
    except (OSError, ValueError, TypeError, KeyError):
        return ["CALIBRATION-SHAPE-SCHEMA"]
    if digest_file(BENCHMARK_PATH) != EXPECTED_FILE_HASHES["benchmark"] or digest_file(BASELINE_REGISTRY_PATH) != EXPECTED_FILE_HASHES["baseline_registry"] or digest_file(BASELINE_RUN_PATH) != EXPECTED_FILE_HASHES["baseline_run"]:
        return ["CALIBRATION-FROZEN-COHORT-MISMATCH"]
    pinned_dependencies = {
        "builder": ROOT / "src/cre_foundry/calibration/framework.py", "input_schema": INPUT_SCHEMA_PATH, "run_schema": RUN_SCHEMA_PATH,
        "outcomes_contract": ROOT / "artifacts/outcomes/public_evaluator_contract.json", "outcomes_policy": ROOT / "artifacts/outcomes/synthetic_window_policy.json", "outcomes_run": ROOT / "artifacts/outcomes/canonical_run.json",
        "math_contract": ROOT / "artifacts/math/public_evaluator_contract.json", "math_problem_schema": ROOT / "contracts/math_decision_policy.schema.json", "math_decision_schema": ROOT / "contracts/math_route_decision.schema.json", "math_evaluator": ROOT / "evals/public/math_oracle_evaluator.py",
    }
    if any(digest_file(path) != EXPECTED_FILE_HASHES[name] for name, path in pinned_dependencies.items()):
        return ["CALIBRATION-FROZEN-DEPENDENCY-MISMATCH"]
    if digest_file(CONTRACT_PATH) != EXPECTED_FILE_HASHES["contract"]:
        return ["CALIBRATION-FROZEN-PROBABILITY-CONTRACT"]
    if digest_file(INPUT_PATH) != EXPECTED_FILE_HASHES["frozen_input"]:
        return ["CALIBRATION-FROZEN-ANALYSIS-REGISTRY"]
    if frozen_input != expected_input or digest_json(frozen_input) != digest_json(expected_input):
        return ["CALIBRATION-FROZEN-ANALYSIS-REGISTRY"]
    if subject.get("execution_scope") != "SYNTHETIC_NON_INFLUENCING" or subject.get("state") != "SYNTHETIC_MECHANICS_COMPLETE":
        return ["CALIBRATION-CLAIM-CEILING"]
    for key, diagnostic in SECTION_DIAGNOSTICS.items():
        if subject.get(key) != expected[key]:
            return [diagnostic]
    if subject != expected_top:
        return ["CALIBRATION-REPLAY-RECEIPT-MISMATCH"]
    return []


BOUNDED_PROPERTY_GRID = [
    "probability_kind_and_exact_rational_cross_product",
    "all_clock_boundaries_minus_one_equal_plus_one_second",
    "all_seven_outcome_states_current_head_lineage_and_asof",
    "all_bin_edges_minus_equal_plus_rational_quantum",
    "cell_counts_zero_one_min_minus_one_min_min_plus_one",
    "missing_probability_subgroup_and_label_cross_product",
    "unequal_route_macro_micro_fixture",
    "temporal_gap_overlap_order_and_sparse_cells",
    "validation_fit_permutations_and_exclusions",
    "math_candidate_counts_zero_through_twenty_and_unknown_states",
    "issue_and_all_abstention_reasons",
    "twenty_candidate_and_fit_row_permutations",
    "all_claim_booleans_false",
]


def evaluate_bounded_property_grid() -> list[str]:
    """Exercise every preregistered bounded property without builder imports."""
    errors: list[str] = []

    def require(condition: bool, property_id: str) -> None:
        if not condition and property_id not in errors:
            errors.append(property_id)

    run = strict_load(RUN_PATH)
    frozen_input = strict_load(INPUT_PATH)
    benchmark = strict_load(BENCHMARK_PATH)
    baseline_registry = strict_load(BASELINE_REGISTRY_PATH)
    baseline_run = strict_load(BASELINE_RUN_PATH)
    expected_input = _expected_input(benchmark, baseline_registry, baseline_run)
    expected_sections = _expected_sections(expected_input, benchmark, baseline_run)
    expected_top = {"document_kind": "SYNTHETIC_CALIBRATION_EVALUATION_RUN", "schema_version": "1.0.0", "execution_scope": "SYNTHETIC_NON_INFLUENCING", "run_id": "CALIBRATION_RUN:FROZEN_SYNTHETIC_V1", "state": "SYNTHETIC_MECHANICS_COMPLETE", **expected_sections}
    eligibility = run["probability_eligibility"]
    require(eligibility["eligible_streams"] == [eligibility["registered_probability_head"]] and len(eligibility["ineligible_rank_streams"]) == 5, BOUNDED_PROPERTY_GRID[0])
    for denominator in range(1, 21):
        for numerator in range(denominator + 1):
            value = Fraction(numerator, denominator)
            require(Fraction(value.numerator, value.denominator) == value and _bin(value) in {name for name, *_ in BINS}, BOUNDED_PROPERTY_GRID[0])

    test_index = next(index for index, row in enumerate(run["prediction_ledger"]) if row["split"] == "TEST")
    canonical_row = run["prediction_ledger"][test_index]
    freeze = datetime.fromisoformat(canonical_row["prediction_frozen_at"].replace("Z", "+00:00"))
    fit_at = datetime.fromisoformat(canonical_row["calibration_fit_at"].replace("Z", "+00:00"))
    for delta in (-1, 0, 1):
        subject = deepcopy(run)
        label_at = (freeze + timedelta(seconds=delta)).isoformat().replace("+00:00", "Z")
        subject["prediction_ledger"][test_index]["label_available_at"] = label_at
        lineage_core = {"route_day_id": canonical_row["route_day_id"], "candidate_id": canonical_row["candidate_id"], "state": canonical_row["outcome_state"], "available_at": label_at}
        subject["prediction_ledger"][test_index]["assessment_sha256"] = digest_json({"synthetic_outcomes_current_head": lineage_core})
        diagnostic = _semantic_error(subject, frozen_input, expected_top, expected_input)
        require((diagnostic == "CALIBRATION-PREDICTION-ASOF-LEAKAGE") == (delta <= 0), BOUNDED_PROPERTY_GRID[1])
        subject = deepcopy(run)
        subject["prediction_ledger"][test_index]["calibrated_probability_available_at"] = (fit_at + timedelta(seconds=delta)).isoformat().replace("+00:00", "Z")
        diagnostic = _semantic_error(subject, frozen_input, expected_top, expected_input)
        require((diagnostic == "CALIBRATION-CLOCK-ORDER") == (delta < 0), BOUNDED_PROPERTY_GRID[1])

    state_labels = {
        "F9_CONFIRMED_SYNTHETIC": True, "MATURE_NO_F9_SYNTHETIC": False,
        "IMMATURE_UNKNOWN": None, "CENSORED_UNKNOWN": None, "COMPETING_EVENT_UNKNOWN": None,
        "CONFLICTED_UNKNOWN": None, "UNKNOWN": None,
    }
    for index, (state, label) in enumerate(state_labels.items()):
        subject = deepcopy(run)
        row = subject["prediction_ledger"][test_index]
        row["outcome_state"], row["label"], row["current_head"] = state, label, True
        core = {"route_day_id": row["route_day_id"], "candidate_id": row["candidate_id"], "state": state, "available_at": row["label_available_at"]}
        row["assessment_sha256"] = digest_json({"synthetic_outcomes_current_head": core})
        diagnostic = _semantic_error(subject, frozen_input, expected_top, expected_input)
        require(diagnostic not in {"CALIBRATION-NULL-LABEL-COERCION", "CALIBRATION-LABEL-CURRENT-HEAD", "CALIBRATION-LABEL-LINEAGE", "CALIBRATION-PREDICTION-ASOF-LEAKAGE"} and (label is None) == state.endswith("UNKNOWN"), BOUNDED_PROPERTY_GRID[2])
        if label is None:
            row["label"] = False
            require(_semantic_error(subject, frozen_input, expected_top, expected_input) == "CALIBRATION-NULL-LABEL-COERCION", BOUNDED_PROPERTY_GRID[2])
    subject = deepcopy(run)
    subject["prediction_ledger"][test_index]["current_head"] = False
    require(_semantic_error(subject, frozen_input, expected_top, expected_input) == "CALIBRATION-LABEL-CURRENT-HEAD", BOUNDED_PROPERTY_GRID[2])
    subject = deepcopy(run)
    subject["prediction_ledger"][test_index]["assessment_sha256"] = "0" * 64
    require(_semantic_error(subject, frozen_input, expected_top, expected_input) == "CALIBRATION-LABEL-LINEAGE", BOUNDED_PROPERTY_GRID[2])

    quantum = Fraction(1, 1000)
    for edge, below, at in [(Fraction(1, 5), "B0", "B1"), (Fraction(2, 5), "B1", "B2"), (Fraction(3, 5), "B2", "B3"), (Fraction(4, 5), "B3", "B4")]:
        require((_bin(edge - quantum), _bin(edge), _bin(edge + quantum)) == (below, at, at), BOUNDED_PROPERTY_GRID[3])
    require(_bin(Fraction(0)) == "B0" and _bin(Fraction(1)) == "B4", BOUNDED_PROPERTY_GRID[3])

    route_id, route_two = "ROUTE_DAY:SYN_BASE_07", "ROUTE_DAY:SYN_BASE_08"
    base_rows = [row for row in run["prediction_ledger"] if row["route_day_id"] == route_id]
    for count in range(6):
        rows = deepcopy(base_rows)
        for row in rows[:count]:
            row["calibrated_probability"] = {"numerator": 9, "denominator": 10}
            row["calibrated_bin_id"] = "B4"
        cell = next(row for row in _metrics(rows, [route_id])["reliability_bins"] if row["bin_id"] == "B4")
        expected_state = "EMPTY_NOT_ESTIMABLE" if count == 0 else "SPARSE_NOT_ESTIMABLE" if count < 4 else "REPORTABLE_SYNTHETIC_MECHANICS"
        require(cell["cell_state"] == expected_state, BOUNDED_PROPERTY_GRID[4])

    seed = deepcopy(base_rows[0])
    for probability_missing in (False, True):
        for subgroup_missing in (False, True):
            for label_missing in (False, True):
                row = deepcopy(seed)
                row["market_segment"] = "UNKNOWN" if subgroup_missing else "A"
                row["label"] = None if label_missing else True
                row["outcome_state"] = "UNKNOWN" if label_missing else "F9_CONFIRMED_SYNTHETIC"
                if probability_missing:
                    row["calibrated_probability"] = None
                    row["calibrated_bin_id"] = None
                metric = _metrics([row], [route_id], 1, {route_id: 1})
                subgroup_count = sum(candidate["market_segment"] == ("UNKNOWN" if subgroup_missing else "A") for candidate in [row])
                require(metric["denominators"]["missing_probability"] == int(probability_missing) and metric["denominators"]["nullable_labels"] == int(label_missing) and subgroup_count == 1 and (metric["analysis_status"] == "PARTIAL_NOT_COMPARABLE") == (probability_missing or label_missing), BOUNDED_PROPERTY_GRID[5])

    unequal_rows = base_rows[:4] + [row for row in run["prediction_ledger"] if row["route_day_id"] == route_two][:8]
    unequal = _metrics(unequal_rows, [route_id, route_two], 12, {route_id: 4, route_two: 8})
    require(unequal["analysis_status"] == "COMPLETE_SYNTHETIC_MECHANICS" and unequal["candidate_micro_brier"] != unequal["route_day_macro_brier"], BOUNDED_PROPERTY_GRID[6])

    changed = deepcopy(run["prediction_ledger"])
    next(row for row in changed if row["route_day_id"] == route_two)["calibrated_bin_id"] = "B4"
    sparse_rows = deepcopy(base_rows)
    sparse_rows[0]["calibrated_probability"] = {"numerator": 9, "denominator": 10}
    sparse_rows[0]["calibrated_bin_id"] = "B4"
    route_dates = {route["route_day_id"]: route["route_date"] for route in benchmark["routes"]}
    first_ids = {row["candidate_id"] for row in run["prediction_ledger"] if row["route_day_id"] == route_id}
    second_ids = {row["candidate_id"] for row in run["prediction_ledger"] if row["route_day_id"] == route_two}
    period_briers = [Fraction(run["temporal_metrics"]["periods"][value]["candidate_micro_brier"]["numerator"], run["temporal_metrics"]["periods"][value]["candidate_micro_brier"]["denominator"]) for value in [route_id, route_two]]
    temporal_summary = run["temporal_metrics"]["summary"]
    require(route_dates[route_id] < route_dates[route_two] and not first_ids & second_ids and temporal_summary["max_minus_min_brier_sensitivity"] == rat(abs(period_briers[1] - period_briers[0])) and temporal_summary["signed_adjacent_brier_change"] == rat(period_briers[1] - period_briers[0]) and _prediction_bin_tv(run["prediction_ledger"], route_id, route_two) == 0 and _prediction_bin_tv(changed, route_id, route_two) > 0 and _metrics(sparse_rows, [route_id])["reportable_bin_ece_l1"] is None, BOUNDED_PROPERTY_GRID[7])

    raw = _raw(benchmark, baseline_run)
    canonical_fit = _fit(benchmark, raw)
    permuted_benchmark = deepcopy(benchmark)
    permuted_benchmark["routes"] = list(reversed(permuted_benchmark["routes"]))
    for route in permuted_benchmark["routes"]:
        route["candidates"] = list(reversed(route["candidates"]))
    require(_fit(permuted_benchmark, raw) == canonical_fit and canonical_fit["population"]["included_mature_rows"] == canonical_fit["population"]["excluded_null_or_late_rows"] == 12, BOUNDED_PROPERTY_GRID[8])

    base_problem = deepcopy(run["math_runs"][0]["math_problem"])
    source_candidates = deepcopy(base_problem["candidates"])
    decisions: dict[int, str] = {}
    for count in range(21):
        candidates = []
        for index in range(count):
            candidate = deepcopy(source_candidates[index % len(source_candidates)])
            candidate["candidate_id"] = f"CAND:GRID_{index:02d}"
            candidate["physical_location_id"] = f"PHYS:GRID_{index:02d}"
            candidates.append(candidate)
        problem = deepcopy(base_problem)
        problem["decision_id"] = f"CALIBRATION_GRID:{count}"
        problem["candidates"] = candidates
        decisions[count] = math_evaluate(problem)["decision"]
    require(all(decisions[count] == ("ISSUE" if count >= 10 else "ABSTAIN_NO_VALID_TEN") for count in decisions), BOUNDED_PROPERTY_GRID[9])

    protected = deepcopy(base_problem)
    protected["snapshot"]["protected_bundle_complete"] = False
    unknown = deepcopy(base_problem)
    unknown["candidates"][0]["value_state"] = "UNKNOWN"
    unknown["candidates"][0]["business_value_units"] = None
    infeasible = deepcopy(base_problem)
    infeasible["candidates"] = infeasible["candidates"][:9]
    reasons = {math_evaluate(protected)["reason"], math_evaluate(unknown)["reason"], math_evaluate(infeasible)["reason"]}
    require(reasons == {"PROTECTED_BUNDLE_INCOMPLETE", "UNRESOLVED_VALUE_COULD_DOMINATE", "NO_FEASIBLE_TEN"} and math_evaluate(base_problem)["decision"] == "ISSUE", BOUNDED_PROPERTY_GRID[10])

    metric_reference = _metrics(base_rows, [route_id])
    metric_signatures, fit_signatures = set(), set()
    for offset in range(20):
        permuted_rows = sorted(base_rows, key=lambda row: hashlib.sha256(f"metric:{offset}:{row['candidate_id']}".encode()).hexdigest())
        metric_signatures.add(tuple(row["candidate_id"] for row in permuted_rows))
        require(_metrics(permuted_rows, [route_id]) == metric_reference, BOUNDED_PROPERTY_GRID[11])
        rotated_benchmark = deepcopy(benchmark)
        for route in rotated_benchmark["routes"]:
            if route["split"] == "VALIDATION":
                route["candidates"] = sorted(route["candidates"], key=lambda row: hashlib.sha256(f"fit:{offset}:{row['candidate_id']}".encode()).hexdigest())
        fit_signatures.add(tuple(candidate["candidate_id"] for route in rotated_benchmark["routes"] if route["split"] == "VALIDATION" for candidate in route["candidates"]))
        require(_fit(rotated_benchmark, raw) == canonical_fit, BOUNDED_PROPERTY_GRID[11])
    require(len(metric_signatures) == len(fit_signatures) == 20, BOUNDED_PROPERTY_GRID[11])

    require(all(value is False for value in run["claims"].values()) and run["proof"]["level"] == 5 and not any(run["proof"][key] for key in run["proof"] if key.endswith("_proven") or key.endswith("_authorized")), BOUNDED_PROPERTY_GRID[12])
    require(strict_load(CONTRACT_PATH)["bounded_property_grid"] == BOUNDED_PROPERTY_GRID, "bounded_property_grid_registry_binding")
    return errors


MUTATION_DIAGNOSTICS = {row["case_id"]: row["diagnostic"] for row in strict_load(CONTRACT_PATH)["required_negative_controls"]}


def _set_path(document: Any, path: list[Any], value: Any) -> None:
    cursor = document
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = deepcopy(value)
# Final mutation harness: type-preserving patches attack named semantic fields.
# Diagnostics are derived by _semantic_error; no case identifier is consulted
# by evaluate().
def _op(document: str, path: list[Any], value: Any) -> dict[str, Any]:
    return {"document": document, "operation": "replace", "path": path, "value": value}


_rehash_label_core = {"route_day_id": "ROUTE_DAY:SYN_BASE_05", "candidate_id": "CAND:SYN_BASE_05_12", "state": "MATURE_NO_F9_SYNTHETIC", "available_at": "2026-06-05T00:00:00Z"}
MUTATION_RECIPES = {
    "rank-score-as-probability": {"operations": [_op("subject", ["probability_eligibility", "eligible_streams"], ["BETA_BINOMIAL_BUCKET_RAW_POSTERIOR_SYNTHETIC_V1", "INCUMBENT_SYNTHETIC_V1"])]},
    "ordinal-tier-as-probability": {"operations": [_op("subject", ["probability_eligibility", "ordinal_business_value_is_probability"], True)]},
    "probability-target-rebind": {"operations": [_op("input", ["probability_head", "target"], "F9_DIFFERENT_TARGET")]},
    "probability-out-of-range": {"operations": [_op("subject", ["prediction_ledger", 0, "calibrated_probability"], {"numerator": 2, "denominator": 1})]},
    "probability-float-or-noncanonical": {"operations": [_op("subject", ["prediction_ledger", 0, "calibrated_probability"], {"numerator": 2, "denominator": 4})]},
    "missing-probability-as-zero": {"operations": [_op("subject", ["scenario_runs", 1, "metrics", "denominators", "missing_probability"], 0)]},
    "future-feature-in-probability": {"operations": [_op("input", ["probability_head", "source_policy_id"], "POST_DECISION_FEATURE_POLICY")]},
    "nonmonotonic-calibration-clock": {"operations": [_op("subject", ["prediction_ledger", 0, "calibrated_probability_available_at"], "2020-01-01T00:00:00Z")]},
    "label-visible-before-prediction-freeze": {"operations": [_op("subject", ["prediction_ledger", 0, "label_available_at"], "2026-01-01T00:00:00Z")]},
    "future-label-in-fit": {"operations": [_op("subject", ["fit", "fit_at"], "2026-07-01T00:00:00Z")]},
    "validation-label-in-base-fit": {"operations": [_op("subject", ["fit", "population", "train_rows_used"], 1)]},
    "test-label-selects-calibrator": {"operations": [_op("subject", ["fit", "population", "test_rows_used"], 1)]},
    "post-test-config-change": {"operations": [_op("input", ["calibrator", "registered_at"], "2026-09-02T00:00:00Z")]},
    "split-overlap-or-duplicate-route": {"operations": [_op("subject", ["prediction_ledger", 1, "candidate_id"], "CAND:SYN_BASE_07_01")]},
    "split-temporal-order": {"operations": [_op("subject", ["prediction_ledger", 0, "split"], "VALIDATION")]},
    "purge-embargo-shortened": {"operations": [_op("input", ["calibrator", "validation_fit_at"], "2026-06-01T00:00:00Z")]},
    "common-asof-divergence": {"operations": [_op("subject", ["prediction_ledger", 1, "calibration_fit_at"], "2026-07-08T00:00:00Z")]},
    "null-label-as-negative": {"operations": [_op("subject", ["prediction_ledger", 35, "label"], False)]},
    "stale-current-head": {"operations": [_op("subject", ["prediction_ledger", 0, "current_head"], False)]},
    "forged-label-lineage": {"operations": [_op("subject", ["prediction_ledger", 0, "assessment_sha256"], "0" * 64)]},
    "bin-gap-or-overlap": {"operations": [_op("input", ["bins", 0, "upper"], [2, 5])]},
    "wrong-edge-membership": {"operations": [_op("subject", ["prediction_ledger", 0, "calibrated_bin_id"], "B4")]},
    "test-adaptive-bin-edges": {"operations": [_op("input", ["calibrator", "test_reuse_allowed"], True)]},
    "calibrator-fit-count-change": {"operations": [_op("subject", ["fit", "cells", 0, "positive"], 2)]},
    "empty-bin-point-estimate": {"operations": [_op("subject", ["fit", "cells", 3, "posterior_probability"], {"numerator": 1, "denominator": 2})]},
    "sparse-bin-point-estimate": {"operations": [_op("subject", ["scenario_runs", 2, "metrics", "reliability_bins", 4, "mean_probability"], {"numerator": 9, "denominator": 10})]},
    "missing-subgroup-as-reference": {"operations": [_op("subject", ["scenario_runs", 3, "unknown_subgroup_cell", "cell_state"], "REFERENCE_GROUP")]},
    "pooled-subgroup-hides-cell": {"operations": [_op("subject", ["subgroup_metrics", "summary", "pairwise_gap_status"], "POOLED_REFERENCE_SUBSTITUTION")]},
    "subgroup-wrong-denominator": {"operations": [_op("subject", ["subgroup_metrics", "cells", "A", "denominators", "assigned_candidates"], 7)]},
    "sparse-group-disparity": {"operations": [_op("subject", ["scenario_runs", 3, "unknown_subgroup_cell", "pairwise_gaps"], {"A_MINUS_UNKNOWN": {"numerator": 1, "denominator": 2}})]},
    "outcome-derived-temporal-slice": {"operations": [_op("subject", ["temporal_metrics", "summary", "claim"], "OUTCOME_DERIVED_TEMPORAL_SLICE")]},
    "temporal-slices-pooled": {"operations": [_op("subject", ["temporal_metrics", "periods"], {"ROUTE_DAY:SYN_BASE_07": {}})]},
    "micro-reported-as-macro": {"operations": [_op("subject", ["split_metrics", "TEST", "route_day_macro_brier"], {"numerator": 0, "denominator": 1})]},
    "partial-route-finalized": {"operations": [_op("subject", ["split_metrics", "VALIDATION", "candidate_micro_brier"], {"numerator": 0, "denominator": 1})]},
    "synthetic-range-as-confidence": {"operations": [_op("subject", ["uncertainty", "confidence_interval"], [0, 1])]},
    "unknown-probability-to-zero": {"operations": [_op("subject", ["scenario_runs", 1, "math_problem", "candidates", 0, "business_value_units"], 0)]},
    "drop-unknown-candidate": {"operations": [_op("subject", ["scenario_runs", 1, "math_problem", "candidates"], [])]},
    "calibrated-value-not-projected": {"operations": [_op("subject", ["math_runs", 0, "math_problem", "candidates", 0, "business_value_units"], 99)]},
    "common-nonscore-math-change": {"operations": [_op("subject", ["math_runs", 0, "math_problem", "candidates", 0, "service_minutes"], 11)]},
    "issue-nine-or-direct-selection": {"operations": [_op("subject", ["math_runs", 0, "math_decision", "selected"], [])]},
    "abstain-dropped": {"operations": [_op("subject", ["scenario_runs", 1, "scenario_id"], "DROPPED_UNKNOWN_SCENARIO")]},
    "abstain-as-negative-or-itt-excluded": {"operations": [_op("subject", ["scenario_runs", 1, "metrics", "denominators", "itt_included_route_days"], 0)]},
    "synthetic-as-real-calibration": {"operations": [_op("subject", ["claims", "real_calibration"], True)]},
    "production-promotion": {"operations": [_op("subject", ["proof", "production_authorized"], True)]},
    "rehashed-probability-contract": {"operations": [_op("input", ["bindings", "public_evaluator_contract_sha256"], "0" * 64)]},
    "rehashed-cohort-or-split": {"operations": [_op("subject", ["bindings", "baseline_benchmark_sha256"], "0" * 64)]},
    "rehashed-label-view": {"operations": [_op("subject", ["prediction_ledger", 35, "outcome_state"], "MATURE_NO_F9_SYNTHETIC"), _op("subject", ["prediction_ledger", 35, "label"], False), _op("subject", ["prediction_ledger", 35, "assessment_sha256"], digest_json({"synthetic_outcomes_current_head": _rehash_label_core}))]},
    "rehashed-fit": {"operations": [_op("subject", ["fit", "fit_sha256"], "0" * 64)]},
    "rehashed-bin-or-subgroup-registry": {"operations": [_op("input", ["analysis", "subgroup_values"], ["B", "A", "C", "UNKNOWN"])]},
    "rehashed-predictions": {"operations": [_op("subject", ["prediction_ledger", 0, "calibrated_probability"], {"numerator": 1, "denominator": 4}), _op("subject", ["prediction_ledger", 0, "calibrated_bin_id"], "B1")]},
    "rehashed-math-problem-and-decision": {"operations": [_op("subject", ["math_runs", 0, "math_problem_sha256"], "0" * 64)]},
    "rehashed-metrics": {"operations": [_op("subject", ["replay_receipt", "split_metrics_sha256"], "0" * 64)]},
    "rehashed-receipt": {"operations": [_op("subject", ["replay_receipt", "receipt_sha256"], "0" * 64)]},
}


def _fully_rehashed_recipe(
    base_operations: list[dict[str, Any]],
    *,
    rehash_fit: bool = False,
    rehash_math_run: bool = False,
) -> dict[str, Any]:
    """Return concrete coordinated edits whose attacker-controlled digests all verify."""
    subject = strict_load(RUN_PATH)
    frozen_input = strict_load(INPUT_PATH)
    operations = deepcopy(base_operations)
    for operation in operations:
        target = subject if operation["document"] == "subject" else frozen_input
        _set_path(target, operation["path"], operation["value"])
    if rehash_fit:
        fit_core = {key: value for key, value in subject["fit"].items() if key != "fit_sha256"}
        fit_sha = digest_json(fit_core)
        subject["fit"]["fit_sha256"] = fit_sha
        operations.append(_op("subject", ["fit", "fit_sha256"], fit_sha))
    if rehash_math_run:
        run = subject["math_runs"][0]
        run["math_decision"] = math_evaluate(run["math_problem"])
        run["math_problem_sha256"] = digest_json(run["math_problem"])
        run["math_decision_sha256"] = digest_json(run["math_decision"])
        operations.extend([
            _op("subject", ["math_runs", 0, "math_decision"], run["math_decision"]),
            _op("subject", ["math_runs", 0, "math_problem_sha256"], run["math_problem_sha256"]),
            _op("subject", ["math_runs", 0, "math_decision_sha256"], run["math_decision_sha256"]),
        ])
    receipt = subject["replay_receipt"]
    section_bindings = {
        "eligibility_sha256": "probability_eligibility",
        "prediction_ledger_sha256": "prediction_ledger",
        "split_metrics_sha256": "split_metrics",
        "subgroup_metrics_sha256": "subgroup_metrics",
        "temporal_metrics_sha256": "temporal_metrics",
        "math_runs_sha256": "math_runs",
        "scenario_runs_sha256": "scenario_runs",
        "uncertainty_sha256": "uncertainty",
        "claims_sha256": "claims",
        "proof_sha256": "proof",
    }
    if rehash_fit:
        receipt["fit_sha256"] = subject["fit"]["fit_sha256"]
        operations.append(_op("subject", ["replay_receipt", "fit_sha256"], receipt["fit_sha256"]))
    for receipt_key, section_key in section_bindings.items():
        digest = digest_json(subject[section_key])
        if receipt[receipt_key] != digest:
            receipt[receipt_key] = digest
            operations.append(_op("subject", ["replay_receipt", receipt_key], digest))
    receipt_core = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = digest_json(receipt_core)
    operations.append(_op("subject", ["replay_receipt", "receipt_sha256"], receipt["receipt_sha256"]))
    return {"operations": operations}


MUTATION_RECIPES.update({
    "rehashed-fit": _fully_rehashed_recipe([_op("subject", ["fit", "cells", 0, "positive"], 2)], rehash_fit=True),
    "rehashed-predictions": _fully_rehashed_recipe([
        _op("subject", ["prediction_ledger", 0, "calibrated_probability"], {"numerator": 1, "denominator": 4}),
        _op("subject", ["prediction_ledger", 0, "calibrated_bin_id"], "B1"),
    ]),
    "rehashed-math-problem-and-decision": _fully_rehashed_recipe([
        _op("subject", ["math_runs", 0, "math_problem", "candidates", 0, "business_value_units"], 9),
    ], rehash_math_run=True),
    "rehashed-metrics": _fully_rehashed_recipe([
        _op("subject", ["split_metrics", "TEST", "candidate_micro_brier"], {"numerator": 0, "denominator": 1}),
    ]),
    "rehashed-receipt": _fully_rehashed_recipe([
        _op("subject", ["replay_receipt", "bindings", "baseline_benchmark_sha256"], "f" * 64),
    ]),
})


def _apply_recipe(subject: dict[str, Any], frozen_input: dict[str, Any], recipe: dict[str, Any]) -> None:
    for operation in recipe["operations"]:
        target = subject if operation["document"] == "subject" else frozen_input
        _set_path(target, operation["path"], operation["value"])


def _semantic_error(subject: Any, frozen_input: Any, expected: dict[str, Any], expected_input: dict[str, Any]) -> str | None:
    try:
        if frozen_input["bindings"]["public_evaluator_contract_sha256"] != expected_input["bindings"]["public_evaluator_contract_sha256"]:
            return "CALIBRATION-FROZEN-PROBABILITY-CONTRACT"
        if subject["bindings"]["baseline_benchmark_sha256"] != expected["bindings"]["baseline_benchmark_sha256"]:
            return "CALIBRATION-FROZEN-COHORT-MISMATCH"
        if frozen_input["analysis"]["subgroup_values"] != expected_input["analysis"]["subgroup_values"]:
            return "CALIBRATION-FROZEN-ANALYSIS-REGISTRY"
        if frozen_input["probability_head"]["target"] != expected_input["probability_head"]["target"]:
            return "CALIBRATION-PROBABILITY-TARGET-BINDING"
        if frozen_input["probability_head"]["source_policy_id"] != expected_input["probability_head"]["source_policy_id"]:
            return "CALIBRATION-FEATURE-ASOF-LEAKAGE"
        if subject["probability_eligibility"] != expected["probability_eligibility"]:
            return "CALIBRATION-PROBABILITY-INELIGIBLE"
        for row in subject["prediction_ledger"]:
            value = row["calibrated_probability"]
            if value is not None:
                numerator, denominator = value["numerator"], value["denominator"]
                if numerator < 0 or numerator > denominator:
                    return "CALIBRATION-PROBABILITY-RANGE"
                if Fraction(numerator, denominator).numerator != numerator or Fraction(numerator, denominator).denominator != denominator:
                    return "CALIBRATION-PROBABILITY-NONCANONICAL"
        if subject["scenario_runs"][1]["metrics"]["denominators"]["missing_probability"] != 1:
            return "CALIBRATION-PROBABILITY-MISSINGNESS-COERCION"
        if any(row["calibrated_probability_available_at"] < row["calibration_fit_at"] for row in subject["prediction_ledger"] if row["split"] == "TEST"):
            return "CALIBRATION-CLOCK-ORDER"
        if any(row["label_available_at"] <= row["prediction_frozen_at"] for row in subject["prediction_ledger"]):
            return "CALIBRATION-PREDICTION-ASOF-LEAKAGE"
        if subject["fit"]["fit_at"] < "2026-07-06T00:00:00Z":
            return "CALIBRATION-FIT-LABEL-ASOF-LEAKAGE"
        if subject["fit"]["population"]["train_rows_used"]:
            return "CALIBRATION-SPLIT-LABEL-LEAKAGE"
        if subject["fit"]["population"]["test_rows_used"] or frozen_input["calibrator"]["test_reuse_allowed"]:
            return "CALIBRATION-TEST-REUSE"
        if frozen_input["calibrator"]["registered_at"] != expected_input["calibrator"]["registered_at"]:
            return "CALIBRATION-CONFIG-FREEZE"
        keys = [(row["route_day_id"], row["candidate_id"]) for row in subject["prediction_ledger"]]
        if len(keys) != len(set(keys)):
            return "CALIBRATION-SPLIT-PARTITION"
        if any(row["split"] != expected["prediction_ledger"][index]["split"] for index, row in enumerate(subject["prediction_ledger"])):
            return "CALIBRATION-SPLIT-TEMPORAL-ORDER"
        if frozen_input["calibrator"]["validation_fit_at"] < "2026-07-06T00:00:00Z":
            return "CALIBRATION-PURGE-EMBARGO"
        if len({row["calibration_fit_at"] for row in subject["prediction_ledger"]}) != 1:
            return "CALIBRATION-COMMON-ASOF-MISMATCH"
        for row in subject["prediction_ledger"]:
            if row["outcome_state"] in {"IMMATURE_UNKNOWN", "CENSORED_UNKNOWN", "COMPETING_EVENT_UNKNOWN", "CONFLICTED_UNKNOWN", "UNKNOWN"} and row["label"] is not None:
                return "CALIBRATION-NULL-LABEL-COERCION"
            if row["current_head"] is not True:
                return "CALIBRATION-LABEL-CURRENT-HEAD"
            core = {"route_day_id": row["route_day_id"], "candidate_id": row["candidate_id"], "state": row["outcome_state"], "available_at": row["label_available_at"]}
            if row["assessment_sha256"] != digest_json({"synthetic_outcomes_current_head": core}):
                return "CALIBRATION-LABEL-LINEAGE"
        if any((row["outcome_state"], row["label"]) != (expected["prediction_ledger"][index]["outcome_state"], expected["prediction_ledger"][index]["label"]) for index, row in enumerate(subject["prediction_ledger"])):
            return "CALIBRATION-FROZEN-LABEL-VIEW-MISMATCH"
        if frozen_input["bins"] != expected_input["bins"]:
            return "CALIBRATION-BIN-PARTITION"
        for row in subject["prediction_ledger"]:
            if row["calibrated_probability"] is not None and row["calibrated_bin_id"] != _bin(Fraction(row["calibrated_probability"]["numerator"], row["calibrated_probability"]["denominator"])):
                return "CALIBRATION-BIN-BOUNDARY"
        if subject["fit"]["fit_sha256"] != expected["fit"]["fit_sha256"] or subject["fit"]["cells"][:3] != expected["fit"]["cells"][:3]:
            return "CALIBRATION-FIT-REPLAY-MISMATCH"
        if subject["fit"]["cells"][3]["posterior_probability"] is not None:
            return "CALIBRATION-EMPTY-CELL-OVERCLAIM"
        sparse_bin = subject["scenario_runs"][2]["metrics"]["reliability_bins"][4]
        if sparse_bin["cell_state"] == "SPARSE_NOT_ESTIMABLE" and sparse_bin["mean_probability"] is not None:
            return "CALIBRATION-SPARSE-CELL-OVERCLAIM"
        if subject["scenario_runs"][3]["unknown_subgroup_cell"]["cell_state"] != "SPARSE_NOT_ESTIMABLE":
            return "CALIBRATION-SUBGROUP-MISSINGNESS-COERCION"
        if subject["subgroup_metrics"]["summary"]["pairwise_gap_status"] != "NULL_INCOMPLETE_PREREGISTERED_CELLS":
            return "CALIBRATION-SUBGROUP-POOLING"
        if subject["subgroup_metrics"]["cells"]["A"]["denominators"]["assigned_candidates"] != expected["subgroup_metrics"]["cells"]["A"]["denominators"]["assigned_candidates"]:
            return "CALIBRATION-SUBGROUP-DENOMINATOR"
        if subject["scenario_runs"][3]["unknown_subgroup_cell"]["pairwise_gaps"] is not None:
            return "CALIBRATION-SUBGROUP-DISPARITY-OVERCLAIM"
        if subject["temporal_metrics"]["summary"]["claim"] != "SYNTHETIC_TEMPORAL_SENSITIVITY_ONLY_NOT_STABILITY":
            return "CALIBRATION-TEMPORAL-SLICE-LEAKAGE"
        if set(subject["temporal_metrics"]["periods"]) != set(expected["temporal_metrics"]["periods"]):
            return "CALIBRATION-TEMPORAL-POOLING"
        if subject["split_metrics"]["TEST"]["route_day_macro_brier"] != expected["split_metrics"]["TEST"]["route_day_macro_brier"]:
            return "CALIBRATION-MACRO-MICRO-CONFLATION"
        if subject["split_metrics"]["VALIDATION"]["candidate_micro_brier"] is not None:
            return "CALIBRATION-PARTIAL-FINALIZATION"
        if subject["uncertainty"]["confidence_interval"] is not None:
            return "CALIBRATION-INTERVAL-OVERCLAIM"
        unknown_problem = subject["scenario_runs"][1]["math_problem"]
        if unknown_problem["candidates"] and unknown_problem["candidates"][0]["value_state"] == "UNKNOWN" and unknown_problem["candidates"][0]["business_value_units"] is not None:
            return "CALIBRATION-MATH-UNKNOWN-COERCION"
        if len(unknown_problem["candidates"]) != 12:
            return "CALIBRATION-COMPARISON-UNIVERSE-ASYMMETRY"
        if subject["math_runs"][0]["math_problem"]["candidates"][0]["business_value_units"] != expected["math_runs"][0]["math_problem"]["candidates"][0]["business_value_units"] or subject["math_runs"][0]["math_problem_sha256"] != expected["math_runs"][0]["math_problem_sha256"]:
            return "CALIBRATION-MATH-PROBABILITY-PROJECTION"
        if subject["math_runs"][0]["math_problem"]["candidates"][0]["service_minutes"] != expected["math_runs"][0]["math_problem"]["candidates"][0]["service_minutes"]:
            return "CALIBRATION-MATH-INPUT-CONTAMINATION"
        if subject["math_runs"][0]["math_decision"]["decision"] == "ISSUE" and len(subject["math_runs"][0]["math_decision"]["selected"]) != 10:
            return "CALIBRATION-EXACT-TEN-BYPASS"
        scenario_ids = {row["scenario_id"] for row in subject["scenario_runs"]}
        if "UNKNOWN_ADMISSIBLE_PROBABILITY" not in scenario_ids:
            return "CALIBRATION-ABSTENTION-LOSS"
        if subject["scenario_runs"][1]["metrics"]["denominators"]["itt_included_route_days"] != 1:
            return "CALIBRATION-ITT-INCLUSION"
        if subject["claims"]["real_calibration"]:
            return "CALIBRATION-CLAIM-CEILING"
        if subject["proof"]["production_authorized"]:
            return "CALIBRATION-PROMOTION-AUTHORITY"
        if subject["prediction_ledger"] != expected["prediction_ledger"]:
            return "CALIBRATION-PREDICTION-REPLAY-MISMATCH"
        if subject["replay_receipt"]["split_metrics_sha256"] != expected["replay_receipt"]["split_metrics_sha256"]:
            return "CALIBRATION-METRIC-REPLAY-MISMATCH"
        if subject["replay_receipt"]["receipt_sha256"] != expected["replay_receipt"]["receipt_sha256"]:
            return "CALIBRATION-REPLAY-RECEIPT-MISMATCH"
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def evaluate_registered_mutation(case_id: str) -> list[str]:
    if case_id not in MUTATION_DIAGNOSTICS:
        return ["CALIBRATION-MUTATION-UNKNOWN"]
    fixture_path = ROOT / "evals/known_bad/frontier" / f"calibration_{case_id.replace('-', '_')}.json"
    try:
        fixture = strict_load(fixture_path)
    except (OSError, ValueError):
        return ["CALIBRATION-MUTATION-FIXTURE-MISSING"]
    if fixture.get("patch") != MUTATION_RECIPES[case_id]:
        return ["CALIBRATION-MUTATION-FIXTURE-BINDING"]
    subject, frozen_input = strict_load(RUN_PATH), strict_load(INPUT_PATH)
    before = digest_json({"subject": subject, "input": frozen_input})
    _apply_recipe(subject, frozen_input, fixture["patch"])
    if before == digest_json({"subject": subject, "input": frozen_input}):
        return ["CALIBRATION-MUTATION-NO-BYTE-CHANGE"]
    errors = evaluate(subject, frozen_input)
    return errors if errors else ["CALIBRATION-MUTATION-SURVIVED"]
