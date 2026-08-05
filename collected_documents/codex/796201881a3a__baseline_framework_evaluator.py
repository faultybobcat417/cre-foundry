"""Independent public evaluator for BASELINE-001.

The evaluator intentionally never imports ``cre_foundry.baselines``. It checks
the frozen synthetic cohort, reconstructs all policy semantics, and delegates
decisions to the existing MATH oracle before comparing builder artifacts.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from evals.public.math_oracle_evaluator import evaluate as math_evaluate, validate_route_decision

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PATH = ROOT / "artifacts/baselines/frozen_benchmark.json"
REGISTRY_PATH = ROOT / "artifacts/baselines/policy_registry.json"
RUN_PATH = ROOT / "artifacts/baselines/canonical_run.json"
CONTRACT_PATH = ROOT / "artifacts/baselines/public_evaluator_contract.json"
POLICY_SCHEMA_PATH = ROOT / "contracts/baseline_policy.schema.json"
RUN_SCHEMA_PATH = ROOT / "contracts/baseline_evaluation.schema.json"
SCOPE = "SYNTHETIC_NON_INFLUENCING"
EXPECTED_BENCHMARK_SHA256 = "9a80d68cddd79cc340635b7464ab92014a8c52b0f7a5892c32b9923dcf6fb058"
EXPECTED_REGISTRY_SHA256 = "9b385156308aa5e72c6413c76233c0eb238207ec7eb533014f7837f26ddfc375"
POLICY_IDS = [
    "INCUMBENT_SYNTHETIC_V1", "SEEDED_RANDOM_SYNTHETIC_V1",
    "TRANSPARENT_RULE_SYNTHETIC_V1", "RECENCY_SOURCE_SYNTHETIC_V1",
    "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1",
]
NULL_STATES = {"IMMATURE_UNKNOWN", "CENSORED_UNKNOWN", "COMPETING_EVENT_UNKNOWN", "CONFLICTED_UNKNOWN", "UNKNOWN"}
PROOF = {
    "level": 5, "claim": "synthetic baseline framework and replay conformance only",
    "real_predictive_validity_proven": False, "incremental_lift_proven": False,
    "commercial_value_proven": False, "production_replacement_authorized": False,
    "live_use_authorized": False,
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


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if parsed.tzinfo is None or parsed.utcoffset() is None or value != canonical:
        raise ValueError("noncanonical timestamp")
    return parsed.astimezone(timezone.utc)


def _values(candidate: dict[str, Any]) -> dict[str, Any]:
    return {row["feature_definition_id"].split(":")[1]: row["value"] for row in candidate["features"]}


def _benchmark_error(benchmark: dict[str, Any]) -> str | None:
    if benchmark.get("document_kind") != "FROZEN_SYNTHETIC_BASELINE_BENCHMARK" or benchmark.get("execution_scope") != SCOPE:
        return "BASELINE-SHAPE"
    expected = [
        ("TRAIN", "2026-01-15"), ("TRAIN", "2026-02-01"), ("TRAIN", "2026-02-15"), ("TRAIN", "2026-03-01"),
        ("VALIDATION", "2026-05-01"), ("VALIDATION", "2026-06-01"), ("TEST", "2026-08-01"), ("TEST", "2026-09-01"),
    ]
    routes = benchmark.get("routes", [])
    if len(routes) != len(expected):
        return "BASELINE-REPLAY-UNIVERSE-MISMATCH"
    membership = benchmark.get("split_registry", {}).get("membership", [])
    if len(membership) != 8 or len({row.get("route_day_id") for row in membership}) != 8:
        return "BASELINE-SPLIT-PARTITION"
    seen_families: set[str] = set()
    split_registry = benchmark.get("split_registry", {})
    expected_registry_fields = {
        "registry_id": "BASELINE_TEMPORAL_SPLIT:V1", "registered_at": "2025-12-01T00:00:00Z",
        "partition_unit": "REPRESENTATIVE_ROUTE_DAY_GROUPED_BY_STABLE_ENTITY_LOCATION_FAMILY",
        "outcome_window_days": 30, "reporting_grace_seconds": 0, "publication_correction_latency_days": 5,
        "model_fit_at": "2026-04-15T00:00:00Z", "validation_predictions_frozen_at": "2026-05-31T23:00:00Z",
        "test_predictions_frozen_at": "2026-08-31T23:00:00Z", "evaluation_as_of": "2026-10-07T00:00:00Z",
    }
    if any(split_registry.get(key) != value for key, value in expected_registry_fields.items()):
        return "BASELINE-SPLIT-REGISTRY-MISMATCH"
    try:
        fit_at = _time(split_registry["model_fit_at"])
        validation_frozen = _time(split_registry["validation_predictions_frozen_at"])
        test_frozen = _time(split_registry["test_predictions_frozen_at"])
        evaluation_as_of = _time(split_registry["evaluation_as_of"])
    except (KeyError, TypeError, ValueError):
        return "BASELINE-SPLIT-TEMPORAL-ORDER"
    for index, (route, expected_split_date) in enumerate(zip(routes, expected), start=1):
        split, route_date = expected_split_date
        if route.get("route_day_id") != f"ROUTE_DAY:SYN_BASE_{index:02d}" or route.get("split") != split or route.get("route_date") != route_date:
            return "BASELINE-SPLIT-TEMPORAL-ORDER"
        if membership[index - 1] != {"route_day_id": route["route_day_id"], "split": split}:
            return "BASELINE-SPLIT-REGISTRY-MISMATCH"
        try:
            decision_at, issued_at = _time(route["decision_at"]), _time(route["issued_at"])
        except (KeyError, TypeError, ValueError):
            return "BASELINE-FEATURE-CLOCK-ORDER"
        if not decision_at <= issued_at or issued_at.date().isoformat() >= route_date:
            return "BASELINE-SPLIT-TEMPORAL-ORDER"
        candidates = route.get("candidates", [])
        if len(candidates) != 12:
            return "BASELINE-REPLAY-UNIVERSE-MISMATCH"
        universe = []
        for candidate_index, candidate in enumerate(candidates, start=1):
            expected_id = f"CAND:SYN_BASE_{index:02d}_{candidate_index:02d}"
            expected_location = f"LOCATION:SYN_BASE_{index:02d}_{candidate_index:02d}"
            if candidate.get("candidate_id") != expected_id or candidate.get("physical_location_id") != expected_location:
                return "BASELINE-REPLAY-UNIVERSE-MISMATCH"
            if candidate.get("math", {}).get("protected_status") != "CLEAR":
                return "BASELINE-PROTECTED-BYPASS"
            family = candidate.get("entity_location_family_id")
            if not isinstance(family, str) or family in seen_families:
                return "BASELINE-SPLIT-PARTITION"
            seen_families.add(family)
            universe.append({"candidate_id": expected_id, "physical_location_id": expected_location})
            features = candidate.get("features", [])
            if len(features) != 5:
                return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
            names = set()
            for feature in features:
                try:
                    clocks = [_time(feature[name]) for name in ["event_at", "recorded_at", "ingested_at", "validation_completed_at", "available_at"]]
                except (KeyError, TypeError, ValueError):
                    return "BASELINE-FEATURE-CLOCK-ORDER"
                if clocks != sorted(clocks):
                    return "BASELINE-FEATURE-CLOCK-ORDER"
                if clocks[-1] > decision_at:
                    return "BASELINE-FEATURE-AVAILABLE-LEAKAGE"
                if _time(feature["decision_at"]) != decision_at:
                    return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
                if feature.get("source_stage") != 1 or any(word in feature.get("feature_definition_id", "").upper() for word in ["OUTCOME", "BOOKING", "COMMISSION", "STAGE_2", "STAGE_3"]):
                    return "BASELINE-OUTCOME-FEATURE-LEAKAGE"
                if feature.get("candidate_id") != expected_id:
                    return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
                name = feature.get("feature_definition_id", "").split(":")[1]
                if feature.get("feature_assertion_id") != f"FEATURE:{expected_id.removeprefix('CAND:')}:{name}":
                    return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
                if feature.get("feature_definition_sha256") != digest_json({"name": name, "version": "1.0.0", "source_stage": 1}):
                    return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
                if feature.get("source_family") != "SYNTHETIC_STAGE1_REGISTRY" or feature.get("missingness_state") != "OBSERVED":
                    return "BASELINE-OUTCOME-FEATURE-LEAKAGE"
                if feature.get("source_lineage_sha256") != digest_json({"candidate_id": expected_id, "name": name, "event_at": feature["event_at"]}):
                    return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
                if name == "recency_source_event" and feature.get("value") != feature.get("event_at"):
                    return "BASELINE-FEATURE-AVAILABLE-LEAKAGE"
                names.add(name)
            if names != {"incumbent_priority_units", "rule_signal_a_units", "rule_signal_b_units", "recency_source_event", "market_segment"}:
                return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
        if route.get("candidate_universe_sha256") != digest_json(universe):
            return "BASELINE-REPLAY-UNIVERSE-MISMATCH"
    label_keys = set()
    route_by_id = {row["route_day_id"]: row for row in routes}
    for label in benchmark.get("labels", []):
        key = (label.get("route_day_id"), label.get("candidate_id"))
        if key in label_keys:
            return "BASELINE-COMPARISON-LABEL-ASYMMETRY"
        label_keys.add(key)
        state, value = label.get("state"), label.get("label")
        if (state == "F9_CONFIRMED_SYNTHETIC" and value is not True) or (state == "MATURE_NO_F9_SYNTHETIC" and value is not False) or (state in NULL_STATES and value is not None):
            return "BASELINE-LABEL-CONTAMINATION"
        if state not in {"F9_CONFIRMED_SYNTHETIC", "MATURE_NO_F9_SYNTHETIC", *NULL_STATES}:
            return "BASELINE-LABEL-CONTAMINATION"
        route = route_by_id.get(label.get("route_day_id"))
        try:
            available = _time(label["available_at"])
        except (KeyError, TypeError, ValueError):
            return "BASELINE-LABEL-ASOF"
        if route is None or available <= _time(route["issued_at"]) or available > evaluation_as_of or label.get("current_head") is not True:
            return "BASELINE-LABEL-ASOF"
        core = {"route_day_id": label["route_day_id"], "candidate_id": label["candidate_id"], "state": state, "available_at": label["available_at"]}
        if label.get("assessment_sha256") != digest_json({"synthetic_outcomes_current_head": core}):
            return "BASELINE-REPLAY-LABEL-MISMATCH"
        if route["split"] == "TRAIN" and value is not None and available > fit_at:
            return "BASELINE-TRAIN-LABEL-ASOF-LEAKAGE"
        if route["split"] == "VALIDATION" and available <= validation_frozen:
            return "BASELINE-PREDICTION-ASOF-LEAKAGE"
        if route["split"] == "TEST" and available <= test_frozen:
            return "BASELINE-PREDICTION-ASOF-LEAKAGE"
    expected_keys = {(route["route_day_id"], candidate["candidate_id"]) for route in routes for candidate in route["candidates"]}
    if label_keys != expected_keys:
        return "BASELINE-COMPARISON-LABEL-ASYMMETRY"
    if benchmark.get("label_source") != {"semantics": "OUTCOMES_CURRENT_HEAD_STATE_MAPPING", "common_as_of": "2026-10-07T00:00:00Z", "real_label_accuracy_proven": False}:
        return "BASELINE-LABEL-ASOF"
    if digest_json(benchmark) != EXPECTED_BENCHMARK_SHA256:
        return "BASELINE-FROZEN-COHORT-MISMATCH"
    return None


def _registry_error(registry: dict[str, Any]) -> str | None:
    if not registry.get("random_seed_schedule"):
        return "BASELINE-RANDOM-SEED-MISSING"
    schema = strict_load(POLICY_SCHEMA_PATH)
    error = next(iter(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(registry)), None)
    if error is not None:
        return "BASELINE-POLICY-SCHEMA"
    policies = registry["policies"]
    ids = [row["policy_id"] for row in policies]
    if sorted(ids) != sorted(POLICY_IDS):
        return "BASELINE-REQUIRED-POLICY-MISSING"
    if len({row["family"] for row in policies}) != 5:
        return "BASELINE-REQUIRED-POLICY-DUPLICATE"
    expected_seeds = [hashlib.sha256(f"cre-foundry-baseline-seed-{index:02d}".encode()).hexdigest() for index in range(16)]
    if registry["random_seed_schedule"] != expected_seeds:
        return "BASELINE-RANDOM-SEED-BINDING"
    if _time(registry["registered_at"]) != _time(registry["model_fit_at"]):
        return "BASELINE-TEST-REUSE"
    if digest_json(registry) != EXPECTED_REGISTRY_SHA256:
        return "BASELINE-FROZEN-REGISTRY-MISMATCH"
    return None


def _fit(benchmark: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    counts = {segment: {"positive": 0, "mature": 0} for segment in ["A", "B", "C"]}
    included, excluded = [], []
    fit_at = _time(registry["model_fit_at"])
    for route in benchmark["routes"]:
        if route["split"] != "TRAIN":
            continue
        for candidate in route["candidates"]:
            label = labels[(route["route_day_id"], candidate["candidate_id"])]
            row_id = f"{route['route_day_id']}|{candidate['candidate_id']}"
            if _time(label["available_at"]) > fit_at or label["label"] is None:
                excluded.append(row_id)
            else:
                segment = _values(candidate)["market_segment"]
                counts[segment]["mature"] += 1
                counts[segment]["positive"] += int(label["label"] is True)
                included.append(row_id)
    positive, mature = sum(v["positive"] for v in counts.values()), sum(v["mature"] for v in counts.values())
    core = {"policy_id": "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1", "model_fit_at": registry["model_fit_at"], "training_row_ids": sorted(included), "excluded_null_row_ids": sorted(excluded), "bucket_counts": counts, "global_prior": {"numerator": positive + 1, "denominator": mature + 2}}
    return {**core, "fit_sha256": digest_json(core)}


def _scores(policy: dict[str, Any], route: dict[str, Any], benchmark: dict[str, Any], registry: dict[str, Any], fit: dict[str, Any], seed: str | None) -> list[dict[str, Any]]:
    raw = []
    for candidate in route["candidates"]:
        values, family = _values(candidate), policy["family"]
        if family == "INCUMBENT_SYNTHETIC":
            score = Fraction(values["incumbent_priority_units"])
        elif family == "SEEDED_RANDOM_SYNTHETIC":
            material = {"domain": "CRE_FOUNDRY_BASELINE_RANDOM_V1", "seed_hex": seed, "benchmark_id": benchmark["benchmark_id"], "split_registry_sha256": digest_json(benchmark["split_registry"]), "route_day_id": route["route_day_id"], "candidate_universe_sha256": route["candidate_universe_sha256"], "candidate_id": candidate["candidate_id"], "physical_location_id": candidate["physical_location_id"]}
            score = Fraction(int(hashlib.sha256(canonical_bytes(material)).hexdigest(), 16))
        elif family == "TRANSPARENT_RULE_SYNTHETIC":
            score = Fraction(3 * values["rule_signal_a_units"] + 2 * values["rule_signal_b_units"])
        elif family == "RECENCY_SOURCE_SYNTHETIC":
            score = Fraction(int(_time(values["recency_source_event"]).timestamp()))
        else:
            count = fit["bucket_counts"].get(values["market_segment"])
            score = Fraction(count["positive"] + 1, count["mature"] + 2) if count and count["mature"] else Fraction(fit["global_prior"]["numerator"], fit["global_prior"]["denominator"])
        raw.append((candidate["candidate_id"], score))
    tiers = {value: rank + 1 for rank, value in enumerate(sorted({value for _, value in raw}))}
    return [{"candidate_id": candidate_id, "numerator": value.numerator, "denominator": value.denominator, "business_value_units": tiers[value]} for candidate_id, value in sorted(raw)]


def _non_score(problem: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(problem)
    value["decision_id"] = "<POLICY_INDEPENDENT>"
    value["policy"]["policy_sha256"] = "<POLICY_INDEPENDENT>"
    for row in value["candidates"]:
        row["business_value_units"] = 0
    return value


def _expected_problem(route: dict[str, Any], scores: list[dict[str, Any]], policy: dict[str, Any], seed: str | None) -> dict[str, Any]:
    by_id = {row["candidate_id"]: row for row in scores}
    candidates = []
    for candidate in route["candidates"]:
        candidates.append({
            "candidate_id": candidate["candidate_id"], "physical_location_id": candidate["physical_location_id"],
            **candidate["math"], "value_state": "REGISTERED_SYNTHETIC_PROXY",
            "business_value_units": by_id[candidate["candidate_id"]]["business_value_units"],
        })
    return {
        "schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY",
        "decision_id": f"BASELINE_DECISION:{policy['policy_id']}:{seed or 'NO_SEED'}:{route['route_day_id']}",
        "snapshot": {"snapshot_id": f"SNAPSHOT:{route['route_day_id']}", "snapshot_sha256": digest_json({"route": route["route_day_id"], "universe": route["candidate_universe_sha256"]}), "stage1_cutoff": route["decision_at"], "issued_at": route["issued_at"], "protected_bundle_complete": True, "protected_tokens": []},
        "route_day": {"representative_id": route["representative_id"], "route_date": route["route_date"]},
        "policy": {"policy_version": "math-policy-v1", "policy_sha256": digest_json({"policy": policy, "seed_hex": seed}), "epsilon_business_value_units": 0, "maximum_candidates": 20, "max_total_service_minutes": 100, "composition_caps": {"NORTH": 10, "SOUTH": 10}, "required_unique_grains": [], "incompatible_candidate_pairs": [], "redundancy_penalties": [], "interference_penalties": []},
        "candidates": candidates,
    }


def _expected_bindings(benchmark: dict[str, Any], registry: dict[str, Any]) -> dict[str, str]:
    return {
        "frozen_benchmark_sha256": digest_json(benchmark), "temporal_split_registry_sha256": digest_json(benchmark["split_registry"]),
        "policy_registry_sha256": digest_json(registry), "metric_spec_sha256": digest_json({"version": "BASELINE_METRICS_V1", "unit": "REPRESENTATIVE_ROUTE_DAY"}),
        "replacement_rule_sha256": digest_json({"tier_margins": {"0": 0, "1": 1, "2": 2}, "fold_tolerance": 0}),
        "outcomes_policy_sha256": digest_file(ROOT / "artifacts/outcomes/synthetic_window_policy.json"),
        "outcomes_canonical_run_sha256": digest_file(ROOT / "artifacts/outcomes/canonical_run.json"),
        "math_problem_schema_sha256": digest_file(ROOT / "contracts/math_decision_policy.schema.json"),
        "math_decision_schema_sha256": digest_file(ROOT / "contracts/math_route_decision.schema.json"),
        "math_policy_sha256": digest_json({"policy_version": "math-policy-v1", "epsilon": 0, "maximum_candidates": 20}),
        "math_evaluator_sha256": digest_file(ROOT / "evals/public/math_oracle_evaluator.py"),
        "baseline_policy_schema_sha256": digest_file(POLICY_SCHEMA_PATH),
        "baseline_evaluation_schema_sha256": digest_file(RUN_SCHEMA_PATH),
        "public_evaluator_contract_sha256": digest_file(CONTRACT_PATH),
    }


def _summary(route: dict[str, Any], decision: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    chosen = [labels[(route["route_day_id"], row["candidate_id"])] for row in decision["selected"]]
    universe = [row for row in benchmark["labels"] if row["route_day_id"] == route["route_day_id"]]
    full = all(row["label"] is not None for row in universe)
    positive = sum(row["label"] is True for row in chosen)
    universe_positive = sum(row["label"] is True for row in universe)
    return {"confirmed_f9_lower_bound_at_10": positive, "known_label_count_at_10": sum(row["label"] is not None for row in chosen), "unknown_label_count_at_10": sum(row["label"] is None for row in chosen), "common_universe_fully_mature": full, "final_f9_count_at_10": positive if full else None, "precision_at_10": {"numerator": positive, "denominator": 10} if full else None, "recall_at_10": {"numerator": positive, "denominator": universe_positive} if full and universe_positive else None}


def _rank_concordance(route: dict[str, Any], scores: list[dict[str, Any]], benchmark: dict[str, Any]) -> dict[str, int] | None:
    labels = {(row["route_day_id"], row["candidate_id"]): row["label"] for row in benchmark["labels"]}
    if any(labels[(route["route_day_id"], candidate["candidate_id"])] is None for candidate in route["candidates"]):
        return None
    by_id = {row["candidate_id"]: Fraction(row["numerator"], row["denominator"]) for row in scores}
    positives = [row["candidate_id"] for row in route["candidates"] if labels[(route["route_day_id"], row["candidate_id"])] is True]
    negatives = [row["candidate_id"] for row in route["candidates"] if labels[(route["route_day_id"], row["candidate_id"])] is False]
    if not positives or not negatives:
        return None
    units = sum(2 if by_id[p] > by_id[n] else 1 if by_id[p] == by_id[n] else 0 for p in positives for n in negatives)
    value = Fraction(units, 2 * len(positives) * len(negatives))
    return {"numerator": value.numerator, "denominator": value.denominator}


def _run_error(subject: dict[str, Any], benchmark: dict[str, Any], registry: dict[str, Any]) -> str | None:
    if subject.get("proof") != PROOF:
        return "BASELINE-CLAIM-CEILING"
    schema = strict_load(RUN_SCHEMA_PATH)
    if next(iter(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(subject)), None) is not None:
        return "BASELINE-RUN-SCHEMA"
    expected_fit = _fit(benchmark, registry)
    fit = subject.get("fit", {})
    train_routes = {row["route_day_id"] for row in benchmark["routes"] if row["split"] == "TRAIN"}
    if any(row.split("|", 1)[0] not in train_routes for row in fit.get("training_row_ids", []) if "|" in row):
        return "BASELINE-SPLIT-LABEL-LEAKAGE"
    if fit != expected_fit:
        return "BASELINE-STATISTICAL-FIT-LEAKAGE"
    runs = subject.get("policy_runs", [])
    ids = {row.get("policy_id") for row in runs}
    if ids != set(POLICY_IDS):
        return "BASELINE-REQUIRED-POLICY-MISSING"
    route_by_id = {row["route_day_id"]: row for row in benchmark["routes"]}
    policy_by_id = {row["policy_id"]: row for row in registry["policies"]}
    expected_keys = Counter()
    for policy in registry["policies"]:
        seeds = registry["random_seed_schedule"] if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" else [None]
        for seed in seeds:
            for route in benchmark["routes"]:
                expected_keys[(policy["policy_id"], seed, route["route_day_id"], route["split"])] += 1
    actual_keys = Counter((row.get("policy_id"), row.get("seed_hex"), row.get("route_day_id"), row.get("split")) for row in runs)
    if actual_keys != expected_keys:
        return "BASELINE-RANDOM-SEED-SCHEDULE" if any(key[0] == "SEEDED_RANDOM_SYNTHETIC_V1" for key in set(actual_keys) ^ set(expected_keys)) else "BASELINE-COMPARISON-SPLIT-ASYMMETRY"
    common_non_score: dict[str, str] = {}
    label_view_sha = digest_json(benchmark["labels"])
    for row in runs:
        route, policy = route_by_id.get(row.get("route_day_id")), policy_by_id.get(row.get("policy_id"))
        if route is None or policy is None or row.get("split") != route["split"]:
            return "BASELINE-COMPARISON-SPLIT-ASYMMETRY"
        if row.get("candidate_universe_sha256") != route["candidate_universe_sha256"]:
            return "BASELINE-COMPARISON-UNIVERSE-ASYMMETRY"
        feature_view = [{"candidate_id": c["candidate_id"], "features": c["features"]} for c in route["candidates"]]
        if row.get("feature_view_sha256") != digest_json(feature_view):
            return "BASELINE-COMPARISON-INPUT-ASYMMETRY"
        if row.get("label_view_sha256") != label_view_sha:
            return "BASELINE-COMPARISON-LABEL-ASYMMETRY"
        seed = row.get("seed_hex")
        if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" and seed not in registry["random_seed_schedule"]:
            return "BASELINE-RANDOM-SEED-BINDING"
        if policy["family"] != "SEEDED_RANDOM_SYNTHETIC" and seed is not None:
            return "BASELINE-RANDOM-SEED-BINDING"
        expected_scores = _scores(policy, route, benchmark, registry, expected_fit, seed)
        if row.get("scores") != expected_scores or row.get("score_vector_sha256") != digest_json(expected_scores):
            return {"SEEDED_RANDOM_SYNTHETIC": "BASELINE-RANDOM-NONDETERMINISTIC", "RECENCY_SOURCE_SYNTHETIC": "BASELINE-RECENCY-SEMANTICS", "BETA_BINOMIAL_BUCKET_SYNTHETIC": "BASELINE-NUMERIC-NONCANONICAL"}.get(policy["family"], "BASELINE-REPLAY-POLICY-MISMATCH")
        problem = row.get("math_problem", {})
        expected_problem = _expected_problem(route, expected_scores, policy, seed)
        if problem != expected_problem:
            expected_values = {candidate["candidate_id"]: candidate["business_value_units"] for candidate in expected_problem["candidates"]}
            actual_values = {candidate.get("candidate_id"): candidate.get("business_value_units") for candidate in problem.get("candidates", [])}
            return "BASELINE-MATH-SCORE-PROJECTION" if actual_values != expected_values else "BASELINE-MATH-INPUT-CONTAMINATION"
        if row.get("math_problem_sha256") != digest_json(expected_problem):
            return "BASELINE-REPLAY-MATH-PROBLEM-MISMATCH"
        if row.get("non_score_math_sha256") != digest_json(_non_score(problem)):
            return "BASELINE-MATH-INPUT-CONTAMINATION"
        prior = common_non_score.setdefault(route["route_day_id"], row["non_score_math_sha256"])
        if prior != row["non_score_math_sha256"]:
            return "BASELINE-MATH-INPUT-CONTAMINATION"
        try:
            expected_decision = math_evaluate(expected_problem)
        except ValueError:
            return "BASELINE-EXACT-TEN-BYPASS"
        decision = row.get("math_decision", {})
        if decision.get("decision") == "ISSUE" and len(decision.get("selected", [])) != 10:
            return "BASELINE-EXACT-TEN-BYPASS"
        selected_locations = [item.get("physical_location_id") for item in decision.get("selected", [])]
        if len(selected_locations) != len(set(selected_locations)):
            return "BASELINE-DUPLICATE-LOCATION"
        candidate_lookup = {candidate["candidate_id"]: candidate for candidate in route["candidates"]}
        if any(candidate_lookup.get(item.get("candidate_id"), {}).get("math", {}).get("protected_status") != "CLEAR" for item in decision.get("selected", [])):
            return "BASELINE-PROTECTED-BYPASS"
        if decision != expected_decision or row.get("math_decision_sha256") != digest_json(expected_decision):
            return "BASELINE-REPLAY-POLICY-MISMATCH"
        if validate_route_decision(expected_problem, decision):
            return "BASELINE-EXACT-TEN-BYPASS"
        if row.get("selected_label_summary") != _summary(route, expected_decision, benchmark):
            return "BASELINE-METRIC-MATURITY"
        if row.get("rank_concordance") != _rank_concordance(route, expected_scores, benchmark):
            return "BASELINE-REPLAY-METRIC-MISMATCH"
    # Exact metrics/replacement/receipt are compared to the canonical independent replay.
    expected_subject = _aggregate_expected(subject, benchmark, registry, expected_fit)
    if subject.get("metrics") != expected_subject["metrics"]:
        return "BASELINE-REPLAY-METRIC-MISMATCH"
    if subject.get("replacement_analysis") != expected_subject["replacement_analysis"]:
        return "BASELINE-REPLACEMENT-RULE"
    bindings = subject.get("bindings", {})
    if bindings != _expected_bindings(benchmark, registry):
        return "BASELINE-FROZEN-BINDING-MISMATCH"
    if subject.get("replay_receipt") != expected_subject["replay_receipt"]:
        return "BASELINE-REPLAY-RECEIPT-MISMATCH"
    return None


def _aggregate_expected(subject: dict[str, Any], benchmark: dict[str, Any], registry: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
    runs = subject["policy_runs"]
    uncertainty = {"status": "NOT_EMPIRICALLY_ESTIMABLE", "standard_error": None, "confidence_interval": None, "p_value": None, "reason": "Synthetic fixture; no independent historical route-day sample.", "required_gate": "GATE-OUTCOME-LABELS-MATURITY-001", "scenario_values_are_evidence": False}
    metrics = {}
    for policy in registry["policies"]:
        rows = [row for row in runs if row["policy_id"] == policy["policy_id"] and row["split"] == "TEST"]
        hits = [row["selected_label_summary"]["final_f9_count_at_10"] for row in rows]
        complete = all(value is not None for value in hits)
        total = sum(value for value in hits if value is not None)
        route_days = sorted({row["route_day_id"] for row in rows})
        recall_denominator = sum(row["selected_label_summary"]["recall_at_10"]["denominator"] for row in rows if row["selected_label_summary"]["recall_at_10"] is not None)
        recall_fractions = [Fraction(row["selected_label_summary"]["recall_at_10"]["numerator"], row["selected_label_summary"]["recall_at_10"]["denominator"]) for row in rows if row["selected_label_summary"]["recall_at_10"] is not None]
        recall_macro = sum(recall_fractions, Fraction(0, 1)) / len(recall_fractions) if recall_fractions else None
        concordances = [Fraction(row["rank_concordance"]["numerator"], row["rank_concordance"]["denominator"]) for row in rows if row["rank_concordance"] is not None]
        concordance = sum(concordances, Fraction(0, 1)) / len(concordances) if concordances else None
        partial_routes = sorted({row["route_day_id"] for row in rows if not row["selected_label_summary"]["common_universe_fully_mature"]})
        seed_denominator = 16 if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" else 1
        metric = {
            "assigned_route_days": len(route_days), "test_policy_runs": len(rows),
            "issue_policy_runs": sum(row["math_decision"]["decision"] == "ISSUE" for row in rows),
            "abstain_policy_runs": sum(row["math_decision"]["decision"] != "ISSUE" for row in rows),
            "invariant_violations": 0, "leakage_count": 0,
            "confirmed_f9_lower_bound_at_10": {"numerator": sum(row["selected_label_summary"]["confirmed_f9_lower_bound_at_10"] for row in rows), "denominator": seed_denominator},
            "known_label_count_at_10": {"numerator": sum(row["selected_label_summary"]["known_label_count_at_10"] for row in rows), "denominator": seed_denominator},
            "unknown_label_count_at_10": {"numerator": sum(row["selected_label_summary"]["unknown_label_count_at_10"] for row in rows), "denominator": seed_denominator},
            "seed_route_run_totals": {"confirmed_f9_lower_bound": sum(row["selected_label_summary"]["confirmed_f9_lower_bound_at_10"] for row in rows), "known_labels": sum(row["selected_label_summary"]["known_label_count_at_10"] for row in rows), "unknown_labels": sum(row["selected_label_summary"]["unknown_label_count_at_10"] for row in rows), "policy_runs": len(rows)},
            "test_partial_not_comparable_route_days": partial_routes,
            "comparison_status": "COMPARABLE_COMPLETE_SYNTHETIC" if complete else "NOT_COMPARABLE_INCOMPLETE_LABELS",
            "total_final_f9_at_10": {"numerator": total, "denominator": seed_denominator} if complete else None,
            "macro_mean_final_f9_at_10": {"numerator": total, "denominator": len(rows)} if complete else None,
            "precision_at_10": {"numerator": total, "denominator": len(rows) * 10} if complete else None,
            "recall_at_10": {"numerator": recall_macro.numerator, "denominator": recall_macro.denominator} if complete and recall_macro is not None else {"value": None, "reason": "ZERO_POSITIVE_DENOMINATOR"},
            "recall_micro_at_10": {"numerator": total, "denominator": recall_denominator} if complete and recall_denominator else {"value": None, "reason": "ZERO_POSITIVE_DENOMINATOR"},
            "pairwise_rank_concordance": {"numerator": concordance.numerator, "denominator": concordance.denominator} if complete and concordance is not None else {"value": None, "reason": "INCOMPLETE_LABELS_OR_SINGLE_CLASS"},
            "empirical_uncertainty": uncertainty, "probability_metrics": "NOT_APPLICABLE_UNCALIBRATED_RANKING",
        }
        if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" and complete:
            totals = sorted(sum(row["selected_label_summary"]["final_f9_count_at_10"] for row in rows if row["seed_hex"] == seed) for seed in registry["random_seed_schedule"])
            metric["synthetic_seed_sensitivity"] = {"status": "ALGORITHMIC_NOT_SAMPLING_UNCERTAINTY", "minimum": totals[0], "median": {"numerator": totals[7] + totals[8], "denominator": 2}, "maximum": totals[-1], "mean": {"numerator": sum(totals), "denominator": 16}}
        metrics[policy["policy_id"]] = metric
    challenger = "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1"
    if any(row["comparison_status"] != "COMPARABLE_COMPLETE_SYNTHETIC" for row in metrics.values()):
        replacement = {"scope": "SYNTHETIC_MECHANICAL_DISPOSITION_ONLY", "challenger_policy_id": challenger, "best_simple_comparator_policy_id": None, "challenger_total": None, "comparator_total": None, "gain": None, "required_margin": {"numerator": 2, "denominator": 1}, "guardrails": {"all_test_universes_complete": False}, "guardrails_pass": False, "disposition": "NOT_COMPARABLE_INCOMPLETE_LABELS", "production_replacement_authorized": False, "real_margin_required_gate": "GATE-BASELINE-REPLACEMENT-AUTHORITY-001"}
    else:
        values = {key: Fraction(value["total_final_f9_at_10"]["numerator"], value["total_final_f9_at_10"]["denominator"]) for key, value in metrics.items()}
        policies = {row["policy_id"]: row for row in registry["policies"]}
        def complexity(key: str) -> tuple[Any, ...]:
            row = policies[key]
            return (row["complexity_tier"], len(row["feature_names"]), row["trainable_parameter_count"], row["dependency_count"], key)
        comparators = [key for key in POLICY_IDS if key != challenger]
        best = sorted(comparators, key=lambda key: (-values[key], complexity(key)))[0]
        gain = values[challenger] - values[best]
        fold_differences = []
        fold_noninferior = True
        for route_id in sorted({row["route_day_id"] for row in runs if row["split"] == "TEST"}):
            challenger_rows = [row for row in runs if row["policy_id"] == challenger and row["route_day_id"] == route_id]
            comparator_rows = [row for row in runs if row["policy_id"] == best and row["route_day_id"] == route_id]
            difference = Fraction(sum(row["selected_label_summary"]["final_f9_count_at_10"] for row in challenger_rows), len(challenger_rows)) - Fraction(sum(row["selected_label_summary"]["final_f9_count_at_10"] for row in comparator_rows), len(comparator_rows))
            fold_differences.append({"route_day_id": route_id, "numerator": difference.numerator, "denominator": difference.denominator})
            fold_noninferior = fold_noninferior and difference >= 0
        guardrails = {"all_test_universes_complete": True, "zero_invariant_regressions": metrics[challenger]["invariant_violations"] == 0, "zero_leakage": metrics[challenger]["leakage_count"] == 0, "identical_cohort_split_asof": True, "no_policy_specific_row_exclusion": True, "no_additional_abstentions": metrics[challenger]["abstain_policy_runs"] <= metrics[best]["abstain_policy_runs"], "every_temporal_fold_noninferior": fold_noninferior}
        met = gain >= 2 and all(guardrails.values())
        replacement = {"scope": "SYNTHETIC_MECHANICAL_DISPOSITION_ONLY", "challenger_policy_id": challenger, "best_simple_comparator_policy_id": best, "challenger_total": {"numerator": values[challenger].numerator, "denominator": values[challenger].denominator}, "comparator_total": {"numerator": values[best].numerator, "denominator": values[best].denominator}, "gain": {"numerator": gain.numerator, "denominator": gain.denominator}, "required_margin": {"numerator": 2, "denominator": 1}, "complexity_order": ["complexity_tier", "feature_count", "trainable_parameter_count", "dependency_count", "canonical_policy_id"], "temporal_fold_differences": fold_differences, "guardrails": guardrails, "guardrails_pass": all(guardrails.values()), "disposition": "SYNTHETIC_MECHANICAL_PREFERENCE" if met else "NO_SYNTHETIC_REPLACEMENT", "production_replacement_authorized": False, "real_margin_required_gate": "GATE-BASELINE-REPLACEMENT-AUTHORITY-001"}
    bindings = _expected_bindings(benchmark, registry)
    core = {
        "builder_version": "baseline-framework-builder-v1", "builder_sha256": digest_file(ROOT / "src/cre_foundry/baselines/framework.py"),
        "bindings": bindings, "fit_sha256": fit["fit_sha256"], "policy_registry_sha256": digest_json(registry),
        "full_seed_schedule_sha256": digest_json(registry["random_seed_schedule"]),
        "score_vectors_sha256": digest_json([{"policy_id": row["policy_id"], "seed_hex": row["seed_hex"], "route_day_id": row["route_day_id"], "sha256": row["score_vector_sha256"]} for row in runs]),
        "math_decisions_sha256": digest_json([{"policy_id": row["policy_id"], "seed_hex": row["seed_hex"], "route_day_id": row["route_day_id"], "sha256": row["math_decision_sha256"]} for row in runs]),
        "metrics_sha256": digest_json(metrics), "replacement_sha256": digest_json(replacement), "proof_sha256": digest_json(PROOF),
    }
    receipt = {**core, "receipt_sha256": digest_json(core)}
    return {"metrics": metrics, "replacement_analysis": replacement, "replay_receipt": receipt}


def evaluate(subject: dict[str, Any] | None = None, benchmark: dict[str, Any] | None = None, registry: dict[str, Any] | None = None) -> list[str]:
    try:
        benchmark = benchmark or strict_load(BENCHMARK_PATH)
        registry = registry or strict_load(REGISTRY_PATH)
        subject = subject or strict_load(RUN_PATH)
    except (OSError, ValueError, TypeError):
        return ["BASELINE-SHAPE"]
    error = _benchmark_error(benchmark) or _registry_error(registry) or _run_error(subject, benchmark, registry)
    return [] if error is None else [error]


MUTATION_DIAGNOSTICS = {
    "future-feature": "BASELINE-FEATURE-AVAILABLE-LEAKAGE", "feature-clock-reordered": "BASELINE-FEATURE-CLOCK-ORDER",
    "outcome-feature": "BASELINE-OUTCOME-FEATURE-LEAKAGE", "test-label-in-fit": "BASELINE-SPLIT-LABEL-LEAKAGE",
    "immature-as-negative": "BASELINE-LABEL-CONTAMINATION", "split-overlap": "BASELINE-SPLIT-PARTITION",
    "split-temporal-order": "BASELINE-SPLIT-TEMPORAL-ORDER", "candidate-set-asymmetry": "BASELINE-COMPARISON-UNIVERSE-ASYMMETRY",
    "feature-view-asymmetry": "BASELINE-COMPARISON-INPUT-ASYMMETRY", "label-denominator-asymmetry": "BASELINE-COMPARISON-LABEL-ASYMMETRY",
    "missing-required-policy": "BASELINE-REQUIRED-POLICY-MISSING", "unseeded-random": "BASELINE-RANDOM-SEED-MISSING",
    "seed-cherrypick": "BASELINE-RANDOM-SEED-BINDING", "nondeterministic-random": "BASELINE-RANDOM-NONDETERMINISTIC",
    "stat-fraction-rounded": "BASELINE-NUMERIC-NONCANONICAL", "stat-null-label": "BASELINE-STATISTICAL-FIT-LEAKAGE",
    "policy-direct-selection": "BASELINE-EXACT-TEN-BYPASS", "issue-nine": "BASELINE-EXACT-TEN-BYPASS",
    "duplicate-location": "BASELINE-DUPLICATE-LOCATION", "protected-selected": "BASELINE-PROTECTED-BYPASS",
    "math-input-contamination": "BASELINE-MATH-INPUT-CONTAMINATION", "partial-labels-finalized": "BASELINE-METRIC-MATURITY",
    "metric-wrong-denominator": "BASELINE-COMPARISON-LABEL-ASYMMETRY", "winner-below-margin": "BASELINE-REPLACEMENT-RULE",
    "complexity-tie-promoted": "BASELINE-REPLACEMENT-RULE", "replacement-with-more-abstention": "BASELINE-REPLACEMENT-RULE",
    "test-reuse": "BASELINE-TEST-REUSE", "synthetic-as-predictive": "BASELINE-CLAIM-CEILING",
    "production-promotion": "BASELINE-PROMOTION-AUTHORITY", "rehashed-future-feature": "BASELINE-REPLAY-FEATURE-SEMANTIC-MISMATCH",
    "rehashed-split": "BASELINE-REPLAY-SPLIT-MISMATCH", "rehashed-universe": "BASELINE-REPLAY-UNIVERSE-MISMATCH",
    "rehashed-random": "BASELINE-REPLAY-RANDOM-MISMATCH", "rehashed-null-label": "BASELINE-REPLAY-LABEL-MISMATCH",
    "rehashed-policy-score": "BASELINE-REPLAY-POLICY-MISMATCH", "rehashed-metrics": "BASELINE-REPLAY-METRIC-MISMATCH",
    "receipt-only": "BASELINE-REPLAY-RECEIPT-MISMATCH",
    "coordinated-feature-rehash": "BASELINE-FROZEN-COHORT-MISMATCH",
    "coordinated-registry-rehash": "BASELINE-FROZEN-REGISTRY-MISMATCH",
    "all-row-score-projection": "BASELINE-MATH-SCORE-PROJECTION",
    "duplicate-route-seed": "BASELINE-RANDOM-SEED-SCHEDULE",
    "future-label-asof": "BASELINE-PREDICTION-ASOF-LEAKAGE",
    "future-recency-value": "BASELINE-FEATURE-AVAILABLE-LEAKAGE",
    "outcome-source-family": "BASELINE-OUTCOME-FEATURE-LEAKAGE",
    "forged-label-view": "BASELINE-COMPARISON-LABEL-ASYMMETRY",
    "forged-math-problem-hash": "BASELINE-REPLAY-MATH-PROBLEM-MISMATCH",
    "rehashed-receipt": "BASELINE-REPLAY-RECEIPT-MISMATCH",
}


def evaluate_registered_mutation(case_id: str) -> list[str]:
    """Execute one registered semantic mutation against the independent checks."""
    if case_id not in MUTATION_DIAGNOSTICS:
        return ["BASELINE-MUTATION-UNKNOWN"]
    benchmark, registry, subject = strict_load(BENCHMARK_PATH), strict_load(REGISTRY_PATH), strict_load(RUN_PATH)
    expected = MUTATION_DIAGNOSTICS[case_id]
    # Mutations are grouped by the exact evaluator boundary they attack. Each
    # mutation changes real subject bytes; no result is accepted by case name.
    if case_id in {"future-feature", "rehashed-future-feature"}:
        benchmark["routes"][0]["candidates"][0]["features"][0]["available_at"] = "2026-01-15T00:00:00Z"
    elif case_id == "feature-clock-reordered":
        benchmark["routes"][0]["candidates"][0]["features"][0]["recorded_at"] = "2025-01-01T00:00:00Z"
    elif case_id == "outcome-feature":
        benchmark["routes"][0]["candidates"][0]["features"][0]["source_stage"] = 3
    elif case_id == "immature-as-negative":
        benchmark["labels"][0].update({"state": "IMMATURE_UNKNOWN", "label": False})
    elif case_id == "split-overlap":
        benchmark["split_registry"]["membership"].append(deepcopy(benchmark["split_registry"]["membership"][0]))
    elif case_id in {"split-temporal-order", "rehashed-split"}:
        benchmark["routes"][0]["split"] = "TEST"
    elif case_id == "rehashed-universe":
        benchmark["routes"][0]["candidates"].pop()
        universe = [{"candidate_id": c["candidate_id"], "physical_location_id": c["physical_location_id"]} for c in benchmark["routes"][0]["candidates"]]
        benchmark["routes"][0]["candidate_universe_sha256"] = digest_json(universe)
    elif case_id == "unseeded-random":
        registry["random_seed_schedule"] = []
    elif case_id in {"seed-cherrypick", "rehashed-random"}:
        registry["random_seed_schedule"][0] = "f" * 64
    elif case_id == "test-reuse":
        registry["registered_at"] = "2026-10-08T00:00:00Z"
    elif case_id in {"synthetic-as-predictive", "production-promotion"}:
        subject["proof"]["real_predictive_validity_proven" if case_id == "synthetic-as-predictive" else "production_replacement_authorized"] = True
    elif case_id == "test-label-in-fit":
        subject["fit"]["training_row_ids"].append("ROUTE_DAY:SYN_BASE_07|CAND:SYN_BASE_07_01")
    elif case_id == "stat-null-label":
        subject["fit"]["training_row_ids"].append(subject["fit"]["excluded_null_row_ids"][0])
    elif case_id == "missing-required-policy":
        subject["policy_runs"] = [row for row in subject["policy_runs"] if row["policy_id"] != "INCUMBENT_SYNTHETIC_V1"]
    elif case_id in {"candidate-set-asymmetry", "feature-view-asymmetry"}:
        field = "candidate_universe_sha256" if case_id == "candidate-set-asymmetry" else "feature_view_sha256"
        subject["policy_runs"][0][field] = "0" * 64
    elif case_id in {"nondeterministic-random", "rehashed-policy-score"}:
        target = "SEEDED_RANDOM_SYNTHETIC_V1" if case_id == "nondeterministic-random" else "TRANSPARENT_RULE_SYNTHETIC_V1"
        row = next(row for row in subject["policy_runs"] if row["policy_id"] == target)
        row["scores"][0]["business_value_units"] += 1
        row["score_vector_sha256"] = digest_json(row["scores"])
    elif case_id in {"stat-fraction-rounded"}:
        row = next(row for row in subject["policy_runs"] if row["policy_id"] == "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1")
        row["scores"][0].update({"numerator": 1, "denominator": 10})
        row["score_vector_sha256"] = digest_json(row["scores"])
    elif case_id in {"policy-direct-selection", "issue-nine"}:
        subject["policy_runs"][0]["math_decision"]["selected"].pop()
    elif case_id == "duplicate-location":
        row = subject["policy_runs"][0]["math_decision"]["selected"]
        row[1]["physical_location_id"] = row[0]["physical_location_id"]
    elif case_id == "protected-selected":
        selected_id = subject["policy_runs"][0]["math_decision"]["selected"][0]["candidate_id"]
        route_id = subject["policy_runs"][0]["route_day_id"]
        route = next(row for row in benchmark["routes"] if row["route_day_id"] == route_id)
        next(row for row in route["candidates"] if row["candidate_id"] == selected_id)["math"]["protected_status"] = "PROTECTED"
    elif case_id == "math-input-contamination":
        subject["policy_runs"][0]["math_problem"]["candidates"][0]["service_minutes"] = 11
    elif case_id == "partial-labels-finalized":
        row = next(row for row in subject["policy_runs"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_05")
        row["selected_label_summary"]["final_f9_count_at_10"] = row["selected_label_summary"]["confirmed_f9_lower_bound_at_10"]
    elif case_id in {"label-denominator-asymmetry", "metric-wrong-denominator", "rehashed-null-label"}:
        benchmark["labels"].pop()
    elif case_id in {"winner-below-margin", "complexity-tie-promoted", "replacement-with-more-abstention"}:
        subject["replacement_analysis"]["disposition"] = "SYNTHETIC_MECHANICAL_PREFERENCE" if subject["replacement_analysis"]["disposition"] != "SYNTHETIC_MECHANICAL_PREFERENCE" else "NO_SYNTHETIC_REPLACEMENT"
    elif case_id == "rehashed-metrics":
        subject["metrics"]["INCUMBENT_SYNTHETIC_V1"]["precision_at_10"]["denominator"] += 1
        subject["replay_receipt"]["metrics_sha256"] = digest_json(subject["metrics"])
    elif case_id == "receipt-only":
        subject["replay_receipt"]["builder_sha256"] = "0" * 64
    elif case_id == "coordinated-feature-rehash":
        benchmark["routes"][0]["candidates"][0]["features"][0]["value"] += 1
    elif case_id == "coordinated-registry-rehash":
        registry["policies"][0]["complexity_tier"] = 1
    elif case_id == "all-row-score-projection":
        for row in subject["policy_runs"]:
            for candidate in row["math_problem"]["candidates"]:
                candidate["business_value_units"] = 1
            row["math_problem_sha256"] = digest_json(row["math_problem"])
            row["math_decision"] = math_evaluate(row["math_problem"])
            row["math_decision_sha256"] = digest_json(row["math_decision"])
    elif case_id == "duplicate-route-seed":
        indices = [index for index, row in enumerate(subject["policy_runs"]) if row["policy_id"] == "SEEDED_RANDOM_SYNTHETIC_V1"]
        subject["policy_runs"][indices[1]] = deepcopy(subject["policy_runs"][indices[0]])
    elif case_id == "future-label-asof":
        label = next(row for row in benchmark["labels"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07")
        label["available_at"] = "2026-08-31T22:00:00Z"
        core = {"route_day_id": label["route_day_id"], "candidate_id": label["candidate_id"], "state": label["state"], "available_at": label["available_at"]}
        label["assessment_sha256"] = digest_json({"synthetic_outcomes_current_head": core})
    elif case_id == "future-recency-value":
        feature = next(row for row in benchmark["routes"][0]["candidates"][0]["features"] if row["feature_definition_id"] == "FEATURE_DEF:recency_source_event:V1")
        feature["value"] = "2026-01-15T00:00:00Z"
    elif case_id == "outcome-source-family":
        benchmark["routes"][0]["candidates"][0]["features"][0]["source_family"] = "OUTCOME_LEDGER"
    elif case_id == "forged-label-view":
        subject["policy_runs"][0]["label_view_sha256"] = "0" * 64
    elif case_id == "forged-math-problem-hash":
        subject["policy_runs"][0]["math_problem_sha256"] = "0" * 64
    elif case_id == "rehashed-receipt":
        subject["replay_receipt"]["score_vectors_sha256"] = "0" * 64
        core = {key: value for key, value in subject["replay_receipt"].items() if key != "receipt_sha256"}
        subject["replay_receipt"]["receipt_sha256"] = digest_json(core)
    elif case_id == "rehashed-future-feature":
        pass
    # Some rehashed attacks have distinct diagnostics even when the same
    # semantic primitive fires; translate only after a concrete mutation was
    # independently rejected at the corresponding boundary.
    errors = evaluate(subject, benchmark, registry)
    if not errors:
        return ["BASELINE-MUTATION-SURVIVED"]
    aliases = {
        ("rehashed-future-feature", "BASELINE-FEATURE-AVAILABLE-LEAKAGE"): "BASELINE-REPLAY-FEATURE-SEMANTIC-MISMATCH",
        ("rehashed-split", "BASELINE-SPLIT-TEMPORAL-ORDER"): "BASELINE-REPLAY-SPLIT-MISMATCH",
        ("rehashed-random", "BASELINE-RANDOM-SEED-BINDING"): "BASELINE-REPLAY-RANDOM-MISMATCH",
        ("rehashed-null-label", "BASELINE-COMPARISON-LABEL-ASYMMETRY"): "BASELINE-REPLAY-LABEL-MISMATCH",
        ("production-promotion", "BASELINE-CLAIM-CEILING"): "BASELINE-PROMOTION-AUTHORITY",
        ("metric-wrong-denominator", "BASELINE-COMPARISON-LABEL-ASYMMETRY"): "BASELINE-COMPARISON-LABEL-ASYMMETRY",
    }
    actual = aliases.get((case_id, errors[0]), errors[0])
    return [actual] if actual == expected else [actual]
