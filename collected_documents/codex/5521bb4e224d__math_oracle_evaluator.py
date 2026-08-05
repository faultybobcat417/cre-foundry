"""Evaluator-owned exhaustive oracle, intentionally independent of src implementation."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from itertools import combinations
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = Draft202012Validator(
    json.loads((_ROOT / "contracts/math_decision_policy.schema.json").read_text()),
    format_checker=FormatChecker(),
)
_DECISION_VALIDATOR = Draft202012Validator(
    json.loads((_ROOT / "contracts/math_route_decision.schema.json").read_text()),
    format_checker=FormatChecker(),
)


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_route_decision(problem, result):
    """Apply output-schema and cross-document mission invariants."""
    errors = [f"schema:{error.json_path}:{error.message}" for error in _DECISION_VALIDATOR.iter_errors(result)]
    if not isinstance(result, dict):
        return errors or ["decision must be an object"]
    for output_field, input_value in (
        ("decision_scope", problem.get("decision_scope")),
        ("decision_id", problem.get("decision_id")),
        ("snapshot_sha256", problem.get("snapshot", {}).get("snapshot_sha256")),
        ("policy_version", problem.get("policy", {}).get("policy_version")),
        ("policy_sha256", problem.get("policy", {}).get("policy_sha256")),
    ):
        if result.get(output_field) != input_value:
            errors.append(f"binding:{output_field}")
    if result.get("decision") == "ISSUE":
        selected = result.get("selected", [])
        candidate_ids = [row.get("candidate_id") for row in selected if isinstance(row, dict)]
        physical_ids = [row.get("physical_location_id") for row in selected if isinstance(row, dict)]
        if len(candidate_ids) != 10 or len(set(candidate_ids)) != 10:
            errors.append("MATH-P01 selected candidate IDs must be exactly ten distinct values")
        if len(physical_ids) != 10 or len(set(physical_ids)) != 10:
            errors.append("MATH-P01 selected physical-location IDs must be exactly ten distinct values")
        candidates = {row.get("candidate_id"): row for row in problem.get("candidates", []) if isinstance(row, dict)}
        for row in selected:
            source = candidates.get(row.get("candidate_id"), {}) if isinstance(row, dict) else {}
            if source.get("physical_location_id") != row.get("physical_location_id"):
                errors.append("MATH-P01 selection does not bind to the input candidate/location pair")
    return list(dict.fromkeys(errors))


def evaluate(problem):
    errors = list(_VALIDATOR.iter_errors(problem))
    if errors:
        raise ValueError(f"decision problem schema violation: {errors[0].message}")
    ids = {row["candidate_id"] for row in problem["candidates"]}
    if len(ids) != len(problem["candidates"]):
        raise ValueError("candidate_id values must be unique")
    collections = [problem["policy"]["incompatible_candidate_pairs"], [row["candidate_pair"] for row in problem["policy"]["redundancy_penalties"]], [row["candidate_pair"] for row in problem["policy"]["interference_penalties"]]]
    for collection in collections:
        if len({tuple(pair) for pair in collection}) != len(collection) or any(tuple(pair) != tuple(sorted(pair)) or not set(pair) <= ids for pair in collection):
            raise ValueError("candidate pairs must be canonical, unique, and resolve")
    diagnostics = Counter()
    base = {
        "schema_version": "1.0.0", "decision_scope": problem["decision_scope"], "oracle_version": "bounded-exhaustive-v1",
        "decision_id": problem["decision_id"], "snapshot_sha256": problem["snapshot"]["snapshot_sha256"],
        "policy_version": problem["policy"]["policy_version"], "policy_sha256": problem["policy"]["policy_sha256"],
    }
    cutoff = _time(problem["snapshot"]["stage1_cutoff"])
    issued_at = _time(problem["snapshot"]["issued_at"])
    if cutoff > issued_at or issued_at.date() >= datetime.fromisoformat(problem["route_day"]["route_date"]).date():
        raise ValueError("observations must precede cutoff, issuance, and route_date")
    if not problem["snapshot"]["protected_bundle_complete"]:
        return {**base, "decision": "ABSTAIN_NO_VALID_TEN", "selected": [], "reason": "PROTECTED_BUNDLE_INCOMPLETE", "diagnostics": {"protected_bundle_incomplete": 1}}
    admissible = []
    all_admissible = []
    unknown_ids = set()
    for row in problem["candidates"]:
        if _time(row["observed_at"]) > cutoff:
            diagnostics["post_cutoff"] += 1
            continue
        if any(state != "PASS" for state in row["gates"].values()):
            diagnostics["hard_gate_not_pass"] += 1
            continue
        if row["protected_status"] != "CLEAR" or set(row["protection_tokens"]) & set(problem["snapshot"]["protected_tokens"]):
            diagnostics["protected_not_clear"] += 1
            continue
        all_admissible.append(row)
        if row["value_state"] == "UNKNOWN":
            diagnostics["admissible_unknown_value"] += 1
            unknown_ids.add(row["candidate_id"])
            continue
        admissible.append(row)
    policy = problem["policy"]
    incompatible = [set(pair) for pair in policy["incompatible_candidate_pairs"]]
    redundancy = [(set(row["candidate_pair"]), row["penalty_units"]) for row in policy["redundancy_penalties"]]
    interference = [(set(row["candidate_pair"]), row["penalty_units"]) for row in policy["interference_penalties"]]

    def feasible(selected):
        ids = {row["candidate_id"] for row in selected}
        if len({row["physical_location_id"] for row in selected}) != 10:
            return False
        for grain in policy["required_unique_grains"]:
            values = [row["grain_ids"][grain] for row in selected]
            if any(value is None for value in values) or len(set(values)) != 10:
                return False
        if sum(row["service_minutes"] for row in selected) > policy["max_total_service_minutes"]:
            return False
        groups = Counter(row["composition_group"] for row in selected if row["composition_group"] is not None)
        return not any(groups[name] > cap for name, cap in policy["composition_caps"].items()) and not any(pair <= ids for pair in incompatible)

    if unknown_ids:
        any_feasible = any(
            any(row["candidate_id"] in unknown_ids for row in selected)
            and feasible(selected)
            for selected in combinations(all_admissible, 10)
        )
        if any_feasible:
            return {**base, "decision": "ABSTAIN_NO_VALID_TEN", "selected": [], "reason": "UNRESOLVED_VALUE_COULD_DOMINATE", "diagnostics": dict(sorted(diagnostics.items()))}
    feasible_sets = []
    for selected in combinations(admissible, 10):
        if not feasible(selected):
            continue
        ids = {row["candidate_id"] for row in selected}
        gross = sum(row["business_value_units"] for row in selected)
        redundancy_units = sum(units for pair, units in redundancy if pair <= ids)
        interference_units = sum(units for pair, units in interference if pair <= ids)
        primary = gross - redundancy_units - interference_units
        proximity = sum(row["proximity_cost_units"] for row in selected)
        canonical = tuple(sorted((row["physical_location_id"], row["candidate_id"]) for row in selected))
        feasible_sets.append((-primary, proximity, canonical, selected))
    if not feasible_sets:
        diagnostics["admissible_candidates"] = len(admissible)
        return {**base, "decision": "ABSTAIN_NO_VALID_TEN", "selected": [], "reason": "NO_FEASIBLE_TEN", "diagnostics": dict(sorted(diagnostics.items()))}
    best = min(feasible_sets, key=lambda item: item[:3])
    ordered = sorted(best[3], key=lambda row: (row["physical_location_id"], row["candidate_id"]))
    best_ids = {row["candidate_id"] for row in best[3]}
    return {**base, "decision": "ISSUE", "selected": [{"candidate_id": row["candidate_id"], "physical_location_id": row["physical_location_id"]} for row in ordered], "certificate": {"gross_business_value_units": sum(row["business_value_units"] for row in best[3]), "redundancy_penalty_units": sum(units for pair, units in redundancy if pair <= best_ids), "interference_penalty_units": sum(units for pair, units in interference if pair <= best_ids), "business_value_units": -best[0], "proximity_cost_units": best[1], "total_service_minutes": sum(row["service_minutes"] for row in best[3]), "feasible_sets_evaluated": len(feasible_sets), "canonical_order_not_route_order": True}}
