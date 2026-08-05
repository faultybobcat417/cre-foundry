"""Deterministic bounded reference policy for exactly-ten-or-abstain."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_ROOT = Path(__file__).resolve().parents[3]
_PROBLEM_VALIDATOR = Draft202012Validator(
    json.loads((_ROOT / "contracts/math_decision_policy.schema.json").read_text()),
    format_checker=FormatChecker(),
)


class InvalidDecisionProblem(ValueError):
    """The input is malformed or internally incoherent, not a business abstention."""


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _abstain(problem: dict[str, Any], reason: str, diagnostics: Counter[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "decision_scope": problem["decision_scope"],
        "oracle_version": "bounded-exhaustive-v1",
        "decision_id": problem["decision_id"],
        "snapshot_sha256": problem["snapshot"]["snapshot_sha256"],
        "policy_version": problem["policy"]["policy_version"],
        "policy_sha256": problem["policy"]["policy_sha256"],
        "decision": "ABSTAIN_NO_VALID_TEN",
        "selected": [],
        "reason": reason,
        "diagnostics": dict(sorted(diagnostics.items())),
    }


def _validate_ids(problem: dict[str, Any]) -> None:
    candidates = problem["candidates"]
    ids = [candidate["candidate_id"] for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise InvalidDecisionProblem("candidate_id values must be unique")
    policy = problem["policy"]
    if len(candidates) > policy["maximum_candidates"]:
        raise InvalidDecisionProblem("candidate count exceeds policy maximum")
    known = set(ids)
    pair_collections = [
        policy["incompatible_candidate_pairs"],
        [item["candidate_pair"] for item in policy["redundancy_penalties"]],
        [item["candidate_pair"] for item in policy["interference_penalties"]],
    ]
    for collection in pair_collections:
        canonical_pairs = [tuple(pair) for pair in collection]
        if len(canonical_pairs) != len(set(canonical_pairs)):
            raise InvalidDecisionProblem("candidate pairs must be unique within each policy collection")
    for pair in [pair for collection in pair_collections for pair in collection]:
        if tuple(pair) != tuple(sorted(pair)):
            raise InvalidDecisionProblem("incompatible pairs must use canonical sorted order")
        if not set(pair) <= known:
            raise InvalidDecisionProblem("incompatible pair references unknown candidate")


def _hard_admissible(candidate: dict[str, Any], cutoff: datetime, protected_tokens: set[str], diagnostics: Counter[str]) -> bool:
    if _time(candidate["observed_at"]) > cutoff:
        diagnostics["post_cutoff"] += 1
        return False
    failed = [name for name, state in candidate["gates"].items() if state != "PASS"]
    if failed:
        diagnostics["hard_gate_not_pass"] += 1
        return False
    if candidate["protected_status"] != "CLEAR" or protected_tokens.intersection(candidate["protection_tokens"]):
        diagnostics["protected_not_clear"] += 1
        return False
    return True


def _set_feasible(selected: list[dict[str, Any]], policy: dict[str, Any]) -> bool:
    if len({candidate["physical_location_id"] for candidate in selected}) != 10:
        return False
    for grain in policy["required_unique_grains"]:
        values = [candidate["grain_ids"][grain] for candidate in selected]
        if any(value is None for value in values) or len(set(values)) != 10:
            return False
    if sum(candidate["service_minutes"] for candidate in selected) > policy["max_total_service_minutes"]:
        return False
    counts = Counter(candidate["composition_group"] for candidate in selected if candidate["composition_group"] is not None)
    if any(counts[group] > cap for group, cap in policy["composition_caps"].items()):
        return False
    chosen = {candidate["candidate_id"] for candidate in selected}
    if any(set(pair) <= chosen for pair in policy["incompatible_candidate_pairs"]):
        return False
    return True


def _penalty(selected: list[dict[str, Any]], entries: list[dict[str, Any]]) -> int:
    chosen = {candidate["candidate_id"] for candidate in selected}
    return sum(entry["penalty_units"] for entry in entries if set(entry["candidate_pair"]) <= chosen)


def _has_feasible_ten_with_unknown(rows: list[dict[str, Any]], unknown_ids: set[str], policy: dict[str, Any]) -> bool:
    """Check for a feasible set containing an unresolved objective value."""
    found = False

    def search(start: int, chosen: list[dict[str, Any]]) -> None:
        nonlocal found
        if found:
            return
        need = 10 - len(chosen)
        if need == 0:
            found = any(row["candidate_id"] in unknown_ids for row in chosen) and _set_feasible(chosen, policy)
            return
        if len(rows) - start < need:
            return
        for index in range(start, len(rows)):
            chosen.append(rows[index])
            search(index + 1, chosen)
            chosen.pop()
            if found:
                return

    search(0, [])
    return found


def decide(problem: dict[str, Any]) -> dict[str, Any]:
    """Validate and return the exact bounded decision."""
    schema_errors = list(_PROBLEM_VALIDATOR.iter_errors(problem))
    if schema_errors:
        raise InvalidDecisionProblem(f"decision problem schema violation: {schema_errors[0].message}")
    _validate_ids(problem)
    cutoff = _time(problem["snapshot"]["stage1_cutoff"])
    issued_at = _time(problem["snapshot"]["issued_at"])
    route_date = datetime.fromisoformat(problem["route_day"]["route_date"]).date()
    if cutoff > issued_at or issued_at.date() >= route_date:
        raise InvalidDecisionProblem("observations must precede cutoff, issuance, and route_date")
    diagnostics: Counter[str] = Counter()
    if not problem["snapshot"]["protected_bundle_complete"]:
        diagnostics["protected_bundle_incomplete"] = 1
        return _abstain(problem, "PROTECTED_BUNDLE_INCOMPLETE", diagnostics)
    hard_admissible = []
    all_hard_admissible = []
    unknown_ids: set[str] = set()
    for candidate in problem["candidates"]:
        if not _hard_admissible(candidate, cutoff, set(problem["snapshot"]["protected_tokens"]), diagnostics):
            continue
        all_hard_admissible.append(candidate)
        if candidate["value_state"] == "UNKNOWN":
            unknown_ids.add(candidate["candidate_id"])
            diagnostics["admissible_unknown_value"] += 1
            continue
        hard_admissible.append(candidate)
    policy = problem["policy"]
    if unknown_ids:
        if _has_feasible_ten_with_unknown(all_hard_admissible, unknown_ids, policy):
            return _abstain(problem, "UNRESOLVED_VALUE_COULD_DOMINATE", diagnostics)

    best_key = None
    best_set = None
    feasible_count = 0

    def search(start: int, chosen: list[dict[str, Any]]) -> None:
        nonlocal best_key, best_set, feasible_count
        need = 10 - len(chosen)
        if need == 0:
            if not _set_feasible(chosen, policy):
                return
            feasible_count += 1
            gross = sum(candidate["business_value_units"] for candidate in chosen)
            primary = gross - _penalty(chosen, policy["redundancy_penalties"]) - _penalty(chosen, policy["interference_penalties"])
            proximity = sum(candidate["proximity_cost_units"] for candidate in chosen)
            canonical = tuple(sorted((candidate["physical_location_id"], candidate["candidate_id"]) for candidate in chosen))
            key = (-primary, proximity, canonical)
            if best_key is None or key < best_key:
                best_key, best_set = key, list(chosen)
            return
        if len(hard_admissible) - start < need:
            return
        for index in range(start, len(hard_admissible)):
            chosen.append(hard_admissible[index])
            search(index + 1, chosen)
            chosen.pop()

    search(0, [])
    if best_set is None:
        diagnostics["admissible_candidates"] = len(hard_admissible)
        return _abstain(problem, "NO_FEASIBLE_TEN", diagnostics)
    ordered = sorted(best_set, key=lambda candidate: (candidate["physical_location_id"], candidate["candidate_id"]))
    return {
        "schema_version": "1.0.0",
        "decision_scope": problem["decision_scope"],
        "oracle_version": "bounded-exhaustive-v1",
        "decision_id": problem["decision_id"],
        "snapshot_sha256": problem["snapshot"]["snapshot_sha256"],
        "policy_version": problem["policy"]["policy_version"],
        "policy_sha256": problem["policy"]["policy_sha256"],
        "decision": "ISSUE",
        "selected": [{"candidate_id": candidate["candidate_id"], "physical_location_id": candidate["physical_location_id"]} for candidate in ordered],
        "certificate": {
            "gross_business_value_units": sum(candidate["business_value_units"] for candidate in best_set),
            "redundancy_penalty_units": _penalty(best_set, policy["redundancy_penalties"]),
            "interference_penalty_units": _penalty(best_set, policy["interference_penalties"]),
            "business_value_units": -best_key[0],
            "proximity_cost_units": best_key[1],
            "total_service_minutes": sum(candidate["service_minutes"] for candidate in best_set),
            "feasible_sets_evaluated": feasible_count,
            "canonical_order_not_route_order": True,
        },
    }
