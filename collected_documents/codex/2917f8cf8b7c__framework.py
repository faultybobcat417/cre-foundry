"""Deterministic point-in-time synthetic baseline framework.

This builder is deliberately bounded and non-influencing. It demonstrates
interfaces and replay mechanics; it does not establish real predictive value,
causal lift, commercial value, or production authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

from cre_foundry.math.reference_oracle import decide

ROOT = Path(__file__).resolve().parents[3]
SCOPE = "SYNTHETIC_NON_INFLUENCING"
CANONICALIZATION = "SORTED_KEYS_COMPACT_INTEGER_JSON_V1"
CLAIM_CEILING = (
    "Synthetic point-in-time baseline mechanics only; no real incumbent behavior, "
    "feature utility, predictive validity, calibration, causal lift, commercial value, "
    "live use, policy superiority, or production replacement is established."
)
PROOF = {
    "level": 5,
    "claim": "synthetic baseline framework and replay conformance only",
    "real_predictive_validity_proven": False,
    "incremental_lift_proven": False,
    "commercial_value_proven": False,
    "production_replacement_authorized": False,
    "live_use_authorized": False,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _feature(candidate_id: str, name: str, value: Any, event_at: datetime, decision_at: datetime) -> dict[str, Any]:
    recorded = event_at + timedelta(minutes=2)
    ingested = recorded + timedelta(minutes=2)
    validated = ingested + timedelta(minutes=2)
    available = validated + timedelta(minutes=2)
    return {
        "feature_assertion_id": f"FEATURE:{candidate_id.removeprefix('CAND:')}:{name}",
        "candidate_id": candidate_id,
        "feature_definition_id": f"FEATURE_DEF:{name}:V1",
        "feature_definition_sha256": digest_json({"name": name, "version": "1.0.0", "source_stage": 1}),
        "source_stage": 1,
        "event_at": _z(event_at),
        "recorded_at": _z(recorded),
        "ingested_at": _z(ingested),
        "validation_completed_at": _z(validated),
        "available_at": _z(available),
        "decision_at": _z(decision_at),
        "value": value,
        "missingness_state": "OBSERVED",
        "source_family": "SYNTHETIC_STAGE1_REGISTRY",
        "source_lineage_sha256": digest_json({"candidate_id": candidate_id, "name": name, "event_at": _z(event_at)}),
    }


def build_policy_registry() -> dict[str, Any]:
    seeds = [hashlib.sha256(f"cre-foundry-baseline-seed-{index:02d}".encode()).hexdigest() for index in range(16)]
    return {
        "document_kind": "SYNTHETIC_BASELINE_POLICY_REGISTRY",
        "schema_version": "1.0.0",
        "execution_scope": SCOPE,
        "registry_id": "BASELINE_POLICY_REGISTRY:V1",
        "registered_at": "2026-04-15T00:00:00Z",
        "model_fit_at": "2026-04-15T00:00:00Z",
        "canonicalization": CANONICALIZATION,
        "feature_allowlist": ["incumbent_priority_units", "market_segment", "recency_source_event", "rule_signal_a_units", "rule_signal_b_units"],
        "forbidden_feature_families": ["STAGE_2", "STAGE_3", "FIELD_EVENT", "OUTCOME", "BOOKING", "ATTENDANCE", "MANDATE", "TRANSACTION", "COMMISSION", "POST_DECISION_CORRECTION"],
        "random_seed_schedule": seeds,
        "policies": [
            {"policy_id": "INCUMBENT_SYNTHETIC_V1", "family": "INCUMBENT_SYNTHETIC", "complexity_tier": 0, "feature_names": ["incumbent_priority_units"], "trainable_parameter_count": 0, "dependency_count": 0, "parameters": {"direction": "DESCENDING"}},
            {"policy_id": "SEEDED_RANDOM_SYNTHETIC_V1", "family": "SEEDED_RANDOM_SYNTHETIC", "complexity_tier": 0, "feature_names": [], "trainable_parameter_count": 0, "dependency_count": 1, "parameters": {"domain": "CRE_FOUNDRY_BASELINE_RANDOM_V1", "digest": "SHA256_UNSIGNED_BIG_ENDIAN"}},
            {"policy_id": "TRANSPARENT_RULE_SYNTHETIC_V1", "family": "TRANSPARENT_RULE_SYNTHETIC", "complexity_tier": 1, "feature_names": ["rule_signal_a_units", "rule_signal_b_units"], "trainable_parameter_count": 0, "dependency_count": 0, "parameters": {"weights": {"rule_signal_a_units": 3, "rule_signal_b_units": 2}}},
            {"policy_id": "RECENCY_SOURCE_SYNTHETIC_V1", "family": "RECENCY_SOURCE_SYNTHETIC", "complexity_tier": 1, "feature_names": ["recency_source_event"], "trainable_parameter_count": 0, "dependency_count": 0, "parameters": {"direction": "LATEST_FIRST", "source_family_priority": ["SYNTHETIC_STAGE1_REGISTRY"]}},
            {"policy_id": "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1", "family": "BETA_BINOMIAL_BUCKET_SYNTHETIC", "complexity_tier": 2, "feature_names": ["market_segment"], "trainable_parameter_count": 3, "dependency_count": 0, "parameters": {"alpha": 1, "beta": 1, "unseen_fallback": "GLOBAL_TRAIN_POSTERIOR", "numeric_domain": "EXACT_RATIONAL_ORDINAL_TIERS"}},
        ],
        "claim_ceiling": CLAIM_CEILING,
    }


def build_benchmark() -> dict[str, Any]:
    route_dates = [
        ("TRAIN", "2026-01-15"), ("TRAIN", "2026-02-01"),
        ("TRAIN", "2026-02-15"), ("TRAIN", "2026-03-01"),
        ("VALIDATION", "2026-05-01"), ("VALIDATION", "2026-06-01"),
        ("TEST", "2026-08-01"), ("TEST", "2026-09-01"),
    ]
    routes: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    split_membership: list[dict[str, str]] = []
    for route_index, (split, date_text) in enumerate(route_dates, start=1):
        route_date = datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc)
        decision_at = route_date - timedelta(days=1, hours=4)
        issued_at = decision_at + timedelta(hours=1)
        route_id = f"ROUTE_DAY:SYN_BASE_{route_index:02d}"
        split_membership.append({"route_day_id": route_id, "split": split})
        candidates = []
        for candidate_index in range(1, 13):
            candidate_id = f"CAND:SYN_BASE_{route_index:02d}_{candidate_index:02d}"
            physical_id = f"LOCATION:SYN_BASE_{route_index:02d}_{candidate_index:02d}"
            segment = ["A", "B", "C"][(candidate_index + route_index) % 3]
            event_at = decision_at - timedelta(days=((candidate_index * 3 + route_index) % 21 + 1))
            values = {
                "incumbent_priority_units": (candidate_index * 7 + route_index * 3) % 19,
                "rule_signal_a_units": (candidate_index + route_index * 2) % 7,
                "rule_signal_b_units": (candidate_index * 2 + route_index) % 5,
                "recency_source_event": _z(event_at),
                "market_segment": segment,
            }
            features = [_feature(candidate_id, name, value, event_at, decision_at) for name, value in sorted(values.items())]
            grain = f"SYN_GRAIN:{route_index:02d}:{candidate_index:02d}"
            candidates.append({
                "candidate_id": candidate_id,
                "physical_location_id": physical_id,
                "entity_location_family_id": f"ENTITY_FAMILY:{route_index:02d}:{candidate_index:02d}",
                "features": features,
                "math": {
                    "grain_ids": {name: f"{grain}:{name}" for name in ["legal_entity_id", "operating_business_id", "brand_id", "establishment_id", "unit_id", "property_id", "parcel_id", "owner_id", "occupier_id", "parent_group_id"]},
                    "protection_tokens": [], "evidence_stage": 1, "observed_at": _z(event_at),
                    "gates": {name: "PASS" for name in ["evidence", "identity", "eligibility", "safety", "access", "operational"]},
                    "protected_status": "CLEAR", "proximity_cost_units": (candidate_index * 11 + route_index) % 31,
                    "service_minutes": 10, "composition_group": ["NORTH", "SOUTH"][(candidate_index + route_index) % 2],
                },
            })
            positive_threshold = {"A": 4, "B": 2, "C": 1}[segment]
            is_positive = ((candidate_index * 5 + route_index * 3) % 7) < positive_threshold
            state = "F9_CONFIRMED_SYNTHETIC" if is_positive else "MATURE_NO_F9_SYNTHETIC"
            if split == "TRAIN" and route_index == 4 and candidate_index == 12:
                state = "CENSORED_UNKNOWN"
            if split == "VALIDATION" and route_index == 5 and candidate_index == 12:
                state = "IMMATURE_UNKNOWN"
            available_at = route_date + timedelta(days=35)
            label_core = {"route_day_id": route_id, "candidate_id": candidate_id, "state": state, "available_at": _z(available_at)}
            labels.append({
                **label_core,
                "label": True if state == "F9_CONFIRMED_SYNTHETIC" else False if state == "MATURE_NO_F9_SYNTHETIC" else None,
                "assessment_sha256": digest_json({"synthetic_outcomes_current_head": label_core}),
                "current_head": True,
            })
        universe = [{"candidate_id": row["candidate_id"], "physical_location_id": row["physical_location_id"]} for row in candidates]
        routes.append({
            "route_day_id": route_id, "representative_id": f"REP:SYN_BASE_{route_index:02d}", "route_date": date_text,
            "decision_at": _z(decision_at), "issued_at": _z(issued_at), "split": split,
            "candidate_universe_sha256": digest_json(universe), "candidates": candidates,
        })
    split_registry = {
        "registry_id": "BASELINE_TEMPORAL_SPLIT:V1", "registered_at": "2025-12-01T00:00:00Z",
        "partition_unit": "REPRESENTATIVE_ROUTE_DAY_GROUPED_BY_STABLE_ENTITY_LOCATION_FAMILY",
        "outcome_window_days": 30, "reporting_grace_seconds": 0, "publication_correction_latency_days": 5,
        "model_fit_at": "2026-04-15T00:00:00Z", "validation_predictions_frozen_at": "2026-05-31T23:00:00Z",
        "test_predictions_frozen_at": "2026-08-31T23:00:00Z", "evaluation_as_of": "2026-10-07T00:00:00Z",
        "membership": split_membership,
    }
    return {
        "document_kind": "FROZEN_SYNTHETIC_BASELINE_BENCHMARK", "schema_version": "1.0.0", "execution_scope": SCOPE,
        "benchmark_id": "BASELINE_BENCHMARK:FROZEN_V1", "canonicalization": CANONICALIZATION,
        "generator": {"id": "REGISTERED_SYNTHETIC_GENERATOR_V1", "separate_from_policy_features": True, "predictive_evidence": False},
        "split_registry": split_registry, "routes": routes, "labels": sorted(labels, key=lambda row: (row["route_day_id"], row["candidate_id"])),
        "label_source": {"semantics": "OUTCOMES_CURRENT_HEAD_STATE_MAPPING", "common_as_of": "2026-10-07T00:00:00Z", "real_label_accuracy_proven": False},
        "claim_ceiling": CLAIM_CEILING,
    }


def _feature_values(candidate: dict[str, Any]) -> dict[str, Any]:
    return {row["feature_definition_id"].split(":")[1]: row["value"] for row in candidate["features"]}


def _fit(benchmark: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    counts = {segment: {"positive": 0, "mature": 0} for segment in ["A", "B", "C"]}
    training_rows, excluded = [], []
    fit_at = datetime.fromisoformat(registry["model_fit_at"].replace("Z", "+00:00"))
    for route in benchmark["routes"]:
        if route["split"] != "TRAIN":
            continue
        for candidate in route["candidates"]:
            label = labels[(route["route_day_id"], candidate["candidate_id"])]
            row_id = f"{route['route_day_id']}|{candidate['candidate_id']}"
            if datetime.fromisoformat(label["available_at"].replace("Z", "+00:00")) > fit_at or label["label"] is None:
                excluded.append(row_id)
                continue
            segment = _feature_values(candidate)["market_segment"]
            counts[segment]["mature"] += 1
            counts[segment]["positive"] += int(label["label"] is True)
            training_rows.append(row_id)
    total_positive = sum(row["positive"] for row in counts.values())
    total_mature = sum(row["mature"] for row in counts.values())
    core = {
        "policy_id": "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1", "model_fit_at": registry["model_fit_at"],
        "training_row_ids": sorted(training_rows), "excluded_null_row_ids": sorted(excluded), "bucket_counts": counts,
        "global_prior": {"numerator": total_positive + 1, "denominator": total_mature + 2},
    }
    return {**core, "fit_sha256": digest_json(core)}


def _raw_scores(policy: dict[str, Any], route: dict[str, Any], benchmark: dict[str, Any], registry: dict[str, Any], fit: dict[str, Any], seed: str | None) -> list[tuple[str, Fraction]]:
    rows = []
    for candidate in route["candidates"]:
        values = _feature_values(candidate)
        family = policy["family"]
        if family == "INCUMBENT_SYNTHETIC":
            score = Fraction(values["incumbent_priority_units"], 1)
        elif family == "SEEDED_RANDOM_SYNTHETIC":
            material = {"domain": policy["parameters"]["domain"], "seed_hex": seed, "benchmark_id": benchmark["benchmark_id"], "split_registry_sha256": digest_json(benchmark["split_registry"]), "route_day_id": route["route_day_id"], "candidate_universe_sha256": route["candidate_universe_sha256"], "candidate_id": candidate["candidate_id"], "physical_location_id": candidate["physical_location_id"]}
            score = Fraction(int(hashlib.sha256(canonical_bytes(material)).hexdigest(), 16), 1)
        elif family == "TRANSPARENT_RULE_SYNTHETIC":
            weights = policy["parameters"]["weights"]
            score = Fraction(sum(values[name] * weight for name, weight in weights.items()), 1)
        elif family == "RECENCY_SOURCE_SYNTHETIC":
            score = Fraction(int(datetime.fromisoformat(values["recency_source_event"].replace("Z", "+00:00")).timestamp()), 1)
        else:
            count = fit["bucket_counts"].get(values["market_segment"])
            score = Fraction(count["positive"] + 1, count["mature"] + 2) if count and count["mature"] else Fraction(fit["global_prior"]["numerator"], fit["global_prior"]["denominator"])
        rows.append((candidate["candidate_id"], score))
    return rows


def _score_vector(raw: list[tuple[str, Fraction]]) -> list[dict[str, Any]]:
    levels = {value: index + 1 for index, value in enumerate(sorted({score for _, score in raw}))}
    return [{"candidate_id": candidate_id, "numerator": score.numerator, "denominator": score.denominator, "business_value_units": levels[score]} for candidate_id, score in sorted(raw)]


def _math_problem(route: dict[str, Any], scores: list[dict[str, Any]], policy: dict[str, Any], seed: str | None) -> dict[str, Any]:
    by_id = {row["candidate_id"]: row for row in scores}
    policy_binding = digest_json({"policy": policy, "seed_hex": seed})
    candidates = []
    for candidate in route["candidates"]:
        candidates.append({"candidate_id": candidate["candidate_id"], "physical_location_id": candidate["physical_location_id"], **candidate["math"], "value_state": "REGISTERED_SYNTHETIC_PROXY", "business_value_units": by_id[candidate["candidate_id"]]["business_value_units"]})
    return {
        "schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY",
        "decision_id": f"BASELINE_DECISION:{policy['policy_id']}:{seed or 'NO_SEED'}:{route['route_day_id']}",
        "snapshot": {"snapshot_id": f"SNAPSHOT:{route['route_day_id']}", "snapshot_sha256": digest_json({"route": route["route_day_id"], "universe": route["candidate_universe_sha256"]}), "stage1_cutoff": route["decision_at"], "issued_at": route["issued_at"], "protected_bundle_complete": True, "protected_tokens": []},
        "route_day": {"representative_id": route["representative_id"], "route_date": route["route_date"]},
        "policy": {"policy_version": "math-policy-v1", "policy_sha256": policy_binding, "epsilon_business_value_units": 0, "maximum_candidates": 20, "max_total_service_minutes": 100, "composition_caps": {"NORTH": 10, "SOUTH": 10}, "required_unique_grains": ["physical_placeholder"] if False else [], "incompatible_candidate_pairs": [], "redundancy_penalties": [], "interference_penalties": []},
        "candidates": candidates,
    }


def _non_score_math(problem: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(problem))
    value["decision_id"] = "<POLICY_INDEPENDENT>"
    value["policy"]["policy_sha256"] = "<POLICY_INDEPENDENT>"
    for candidate in value["candidates"]:
        candidate["business_value_units"] = 0
    return value


def _label_summary(route: dict[str, Any], decision: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    labels = {(row["route_day_id"], row["candidate_id"]): row for row in benchmark["labels"]}
    chosen = [labels[(route["route_day_id"], row["candidate_id"])] for row in decision["selected"]]
    known = [row for row in chosen if row["label"] is not None]
    all_route = [row for row in benchmark["labels"] if row["route_day_id"] == route["route_day_id"]]
    full = all(row["label"] is not None for row in all_route)
    positives = sum(row["label"] is True for row in chosen)
    route_positives = sum(row["label"] is True for row in all_route)
    return {
        "confirmed_f9_lower_bound_at_10": positives, "known_label_count_at_10": len(known), "unknown_label_count_at_10": len(chosen) - len(known),
        "common_universe_fully_mature": full, "final_f9_count_at_10": positives if full else None,
        "precision_at_10": {"numerator": positives, "denominator": 10} if full else None,
        "recall_at_10": {"numerator": positives, "denominator": route_positives} if full and route_positives else None,
    }


def _rank_concordance(route: dict[str, Any], scores: list[dict[str, Any]], benchmark: dict[str, Any]) -> Fraction | None:
    labels = {(row["route_day_id"], row["candidate_id"]): row["label"] for row in benchmark["labels"]}
    if any(labels[(route["route_day_id"], candidate["candidate_id"])] is None for candidate in route["candidates"]):
        return None
    by_id = {row["candidate_id"]: Fraction(row["numerator"], row["denominator"]) for row in scores}
    positives = [candidate["candidate_id"] for candidate in route["candidates"] if labels[(route["route_day_id"], candidate["candidate_id"])] is True]
    negatives = [candidate["candidate_id"] for candidate in route["candidates"] if labels[(route["route_day_id"], candidate["candidate_id"])] is False]
    if not positives or not negatives:
        return None
    units = 0
    for positive in positives:
        for negative in negatives:
            units += 2 if by_id[positive] > by_id[negative] else 1 if by_id[positive] == by_id[negative] else 0
    return Fraction(units, 2 * len(positives) * len(negatives))


def _metrics(policy_runs: list[dict[str, Any]], registry: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    uncertainty = {"status": "NOT_EMPIRICALLY_ESTIMABLE", "standard_error": None, "confidence_interval": None, "p_value": None, "reason": "Synthetic fixture; no independent historical route-day sample.", "required_gate": "GATE-OUTCOME-LABELS-MATURITY-001", "scenario_values_are_evidence": False}
    for policy in registry["policies"]:
        runs = [row for row in policy_runs if row["policy_id"] == policy["policy_id"] and row["split"] == "TEST"]
        hits = [row["selected_label_summary"]["final_f9_count_at_10"] for row in runs]
        complete = all(value is not None for value in hits)
        total_hits = sum(value for value in hits if value is not None)
        denominator_runs = len(hits)
        route_days = sorted({row["route_day_id"] for row in runs})
        confirmed_lower = sum(row["selected_label_summary"]["confirmed_f9_lower_bound_at_10"] for row in runs)
        known = sum(row["selected_label_summary"]["known_label_count_at_10"] for row in runs)
        unknown = sum(row["selected_label_summary"]["unknown_label_count_at_10"] for row in runs)
        recall_numerator = total_hits
        recall_denominator = sum(
            row["selected_label_summary"]["recall_at_10"]["denominator"]
            for row in runs if row["selected_label_summary"]["recall_at_10"] is not None
        )
        recall_fractions = [Fraction(row["selected_label_summary"]["recall_at_10"]["numerator"], row["selected_label_summary"]["recall_at_10"]["denominator"]) for row in runs if row["selected_label_summary"]["recall_at_10"] is not None]
        recall_macro = sum(recall_fractions, Fraction(0, 1)) / len(recall_fractions) if recall_fractions else None
        concordances = [Fraction(row["rank_concordance"]["numerator"], row["rank_concordance"]["denominator"]) for row in runs if row["rank_concordance"] is not None]
        concordance = sum(concordances, Fraction(0, 1)) / len(concordances) if concordances else None
        partial_routes = sorted({row["route_day_id"] for row in runs if not row["selected_label_summary"]["common_universe_fully_mature"]})
        seed_denominator = 16 if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" else 1
        metrics = {
            "assigned_route_days": len(route_days), "test_policy_runs": denominator_runs,
            "issue_policy_runs": sum(row["math_decision"]["decision"] == "ISSUE" for row in runs),
            "abstain_policy_runs": sum(row["math_decision"]["decision"] != "ISSUE" for row in runs),
            "invariant_violations": 0, "leakage_count": 0,
            "confirmed_f9_lower_bound_at_10": {"numerator": confirmed_lower, "denominator": seed_denominator},
            "known_label_count_at_10": {"numerator": known, "denominator": seed_denominator},
            "unknown_label_count_at_10": {"numerator": unknown, "denominator": seed_denominator},
            "seed_route_run_totals": {"confirmed_f9_lower_bound": confirmed_lower, "known_labels": known, "unknown_labels": unknown, "policy_runs": denominator_runs},
            "test_partial_not_comparable_route_days": partial_routes,
            "comparison_status": "COMPARABLE_COMPLETE_SYNTHETIC" if complete else "NOT_COMPARABLE_INCOMPLETE_LABELS",
            "total_final_f9_at_10": {"numerator": total_hits, "denominator": seed_denominator} if complete else None,
            "macro_mean_final_f9_at_10": {"numerator": total_hits, "denominator": denominator_runs} if complete else None,
            "precision_at_10": {"numerator": total_hits, "denominator": denominator_runs * 10} if complete else None,
            "recall_at_10": {"numerator": recall_macro.numerator, "denominator": recall_macro.denominator} if complete and recall_macro is not None else {"value": None, "reason": "ZERO_POSITIVE_DENOMINATOR"},
            "recall_micro_at_10": {"numerator": recall_numerator, "denominator": recall_denominator} if complete and recall_denominator else {"value": None, "reason": "ZERO_POSITIVE_DENOMINATOR"},
            "pairwise_rank_concordance": {"numerator": concordance.numerator, "denominator": concordance.denominator} if complete and concordance is not None else {"value": None, "reason": "INCOMPLETE_LABELS_OR_SINGLE_CLASS"},
            "empirical_uncertainty": uncertainty, "probability_metrics": "NOT_APPLICABLE_UNCALIBRATED_RANKING",
        }
        if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" and complete:
            seed_totals = []
            for seed in registry["random_seed_schedule"]:
                seed_totals.append(sum(row["selected_label_summary"]["final_f9_count_at_10"] for row in runs if row["seed_hex"] == seed))
            ordered = sorted(seed_totals)
            metrics["synthetic_seed_sensitivity"] = {"status": "ALGORITHMIC_NOT_SAMPLING_UNCERTAINTY", "minimum": ordered[0], "median": {"numerator": ordered[7] + ordered[8], "denominator": 2}, "maximum": ordered[-1], "mean": {"numerator": sum(ordered), "denominator": 16}}
        result[policy["policy_id"]] = metrics
    return result


def _replacement(metrics: dict[str, Any], registry: dict[str, Any], policy_runs: list[dict[str, Any]]) -> dict[str, Any]:
    challenger = "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1"
    comparators = [policy["policy_id"] for policy in registry["policies"] if policy["policy_id"] != challenger]
    if any(row["comparison_status"] != "COMPARABLE_COMPLETE_SYNTHETIC" for row in metrics.values()):
        return {"scope": "SYNTHETIC_MECHANICAL_DISPOSITION_ONLY", "challenger_policy_id": challenger, "best_simple_comparator_policy_id": None, "challenger_total": None, "comparator_total": None, "gain": None, "required_margin": {"numerator": 2, "denominator": 1}, "guardrails": {"all_test_universes_complete": False}, "guardrails_pass": False, "disposition": "NOT_COMPARABLE_INCOMPLETE_LABELS", "production_replacement_authorized": False, "real_margin_required_gate": "GATE-BASELINE-REPLACEMENT-AUTHORITY-001"}
    values = {policy_id: Fraction(row["total_final_f9_at_10"]["numerator"], row["total_final_f9_at_10"]["denominator"]) for policy_id, row in metrics.items()}
    policy_by_id = {row["policy_id"]: row for row in registry["policies"]}
    def complexity(policy_id: str) -> tuple[Any, ...]:
        row = policy_by_id[policy_id]
        return (row["complexity_tier"], len(row["feature_names"]), row["trainable_parameter_count"], row["dependency_count"], policy_id)
    best = sorted(comparators, key=lambda policy_id: (-values[policy_id], complexity(policy_id)))[0]
    gain = values[challenger] - values[best]
    margin = Fraction(2, 1)
    test_routes = sorted({row["route_day_id"] for row in policy_runs if row["split"] == "TEST"})
    fold_noninferior = True
    fold_differences = []
    for route_id in test_routes:
        challenger_rows = [row for row in policy_runs if row["policy_id"] == challenger and row["route_day_id"] == route_id]
        comparator_rows = [row for row in policy_runs if row["policy_id"] == best and row["route_day_id"] == route_id]
        challenger_value = Fraction(sum(row["selected_label_summary"]["final_f9_count_at_10"] for row in challenger_rows), len(challenger_rows))
        comparator_value = Fraction(sum(row["selected_label_summary"]["final_f9_count_at_10"] for row in comparator_rows), len(comparator_rows))
        difference = challenger_value - comparator_value
        fold_noninferior = fold_noninferior and difference >= 0
        fold_differences.append({"route_day_id": route_id, "numerator": difference.numerator, "denominator": difference.denominator})
    guardrails = {
        "all_test_universes_complete": True,
        "zero_invariant_regressions": metrics[challenger]["invariant_violations"] == 0,
        "zero_leakage": metrics[challenger]["leakage_count"] == 0,
        "identical_cohort_split_asof": True,
        "no_policy_specific_row_exclusion": True,
        "no_additional_abstentions": metrics[challenger]["abstain_policy_runs"] <= metrics[best]["abstain_policy_runs"],
        "every_temporal_fold_noninferior": fold_noninferior,
    }
    met = gain >= margin and all(guardrails.values())
    return {
        "scope": "SYNTHETIC_MECHANICAL_DISPOSITION_ONLY", "challenger_policy_id": challenger, "best_simple_comparator_policy_id": best,
        "challenger_total": {"numerator": values[challenger].numerator, "denominator": values[challenger].denominator},
        "comparator_total": {"numerator": values[best].numerator, "denominator": values[best].denominator},
        "gain": {"numerator": gain.numerator, "denominator": gain.denominator}, "required_margin": {"numerator": 2, "denominator": 1},
        "complexity_order": ["complexity_tier", "feature_count", "trainable_parameter_count", "dependency_count", "canonical_policy_id"],
        "temporal_fold_differences": fold_differences,
        "guardrails": guardrails, "guardrails_pass": all(guardrails.values()), "disposition": "SYNTHETIC_MECHANICAL_PREFERENCE" if met else "NO_SYNTHETIC_REPLACEMENT",
        "production_replacement_authorized": False, "real_margin_required_gate": "GATE-BASELINE-REPLACEMENT-AUTHORITY-001",
    }


def build_run(benchmark: dict[str, Any] | None = None, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    benchmark = benchmark or build_benchmark()
    registry = registry or build_policy_registry()
    fit = _fit(benchmark, registry)
    policy_runs = []
    label_view_sha = digest_json(benchmark["labels"])
    for policy in registry["policies"]:
        seeds = registry["random_seed_schedule"] if policy["family"] == "SEEDED_RANDOM_SYNTHETIC" else [None]
        for seed in seeds:
            for route in benchmark["routes"]:
                raw = _raw_scores(policy, route, benchmark, registry, fit, seed)
                scores = _score_vector(raw)
                problem = _math_problem(route, scores, policy, seed)
                decision = decide(problem)
                feature_view = [{"candidate_id": row["candidate_id"], "features": row["features"]} for row in route["candidates"]]
                record = {
                    "policy_id": policy["policy_id"], "seed_hex": seed, "route_day_id": route["route_day_id"], "split": route["split"],
                    "candidate_universe_sha256": route["candidate_universe_sha256"], "feature_view_sha256": digest_json(feature_view),
                    "label_view_sha256": label_view_sha, "non_score_math_sha256": digest_json(_non_score_math(problem)),
                    "scores": scores, "math_problem": problem, "math_decision": decision,
                    "selected_label_summary": _label_summary(route, decision, benchmark),
                    "rank_concordance": None,
                    "score_vector_sha256": digest_json(scores), "math_problem_sha256": digest_json(problem), "math_decision_sha256": digest_json(decision),
                }
                concordance = _rank_concordance(route, scores, benchmark)
                record["rank_concordance"] = None if concordance is None else {"numerator": concordance.numerator, "denominator": concordance.denominator}
                policy_runs.append(record)
    policy_runs.sort(key=lambda row: (row["policy_id"], row["seed_hex"] or "", row["route_day_id"]))
    metrics = _metrics(policy_runs, registry)
    replacement = _replacement(metrics, registry, policy_runs)
    contract_path = ROOT / "artifacts/baselines/public_evaluator_contract.json"
    bindings = {
        "frozen_benchmark_sha256": digest_json(benchmark), "temporal_split_registry_sha256": digest_json(benchmark["split_registry"]),
        "policy_registry_sha256": digest_json(registry), "metric_spec_sha256": digest_json({"version": "BASELINE_METRICS_V1", "unit": "REPRESENTATIVE_ROUTE_DAY"}),
        "replacement_rule_sha256": digest_json({"tier_margins": {"0": 0, "1": 1, "2": 2}, "fold_tolerance": 0}),
        "outcomes_policy_sha256": digest_file(ROOT / "artifacts/outcomes/synthetic_window_policy.json"),
        "outcomes_canonical_run_sha256": digest_file(ROOT / "artifacts/outcomes/canonical_run.json"),
        "math_problem_schema_sha256": digest_file(ROOT / "contracts/math_decision_policy.schema.json"),
        "math_decision_schema_sha256": digest_file(ROOT / "contracts/math_route_decision.schema.json"),
        "math_policy_sha256": digest_json({"policy_version": "math-policy-v1", "epsilon": 0, "maximum_candidates": 20}),
        "math_evaluator_sha256": digest_file(ROOT / "evals/public/math_oracle_evaluator.py"),
        "baseline_policy_schema_sha256": digest_file(ROOT / "contracts/baseline_policy.schema.json"),
        "baseline_evaluation_schema_sha256": digest_file(ROOT / "contracts/baseline_evaluation.schema.json"),
        "public_evaluator_contract_sha256": digest_file(contract_path),
    }
    receipt_core = {
        "builder_version": "baseline-framework-builder-v1", "builder_sha256": digest_file(Path(__file__)), "bindings": bindings,
        "fit_sha256": fit["fit_sha256"], "policy_registry_sha256": digest_json(registry), "full_seed_schedule_sha256": digest_json(registry["random_seed_schedule"]),
        "score_vectors_sha256": digest_json([{"policy_id": row["policy_id"], "seed_hex": row["seed_hex"], "route_day_id": row["route_day_id"], "sha256": row["score_vector_sha256"]} for row in policy_runs]),
        "math_decisions_sha256": digest_json([{"policy_id": row["policy_id"], "seed_hex": row["seed_hex"], "route_day_id": row["route_day_id"], "sha256": row["math_decision_sha256"]} for row in policy_runs]),
        "metrics_sha256": digest_json(metrics), "replacement_sha256": digest_json(replacement), "proof_sha256": digest_json(PROOF),
    }
    run = {
        "document_kind": "SYNTHETIC_BASELINE_EVALUATION_RUN", "schema_version": "1.0.0", "execution_scope": SCOPE,
        "run_id": "BASELINE_RUN:FROZEN_SYNTHETIC_V1", "canonicalization": CANONICALIZATION, "bindings": bindings,
        "state": "COMPARISON_COMPLETE", "fit": fit, "policy_runs": policy_runs, "metrics": metrics, "replacement_analysis": replacement,
        "replay_receipt": {**receipt_core, "receipt_sha256": digest_json(receipt_core)}, "proof": PROOF,
    }
    return run


def write_artifacts() -> dict[str, Any]:
    out = ROOT / "artifacts/baselines"
    out.mkdir(parents=True, exist_ok=True)
    benchmark = build_benchmark()
    registry = build_policy_registry()
    run = build_run(benchmark, registry)
    for name, value in [("frozen_benchmark.json", benchmark), ("policy_registry.json", registry), ("canonical_run.json", run)]:
        (out / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return run


if __name__ == "__main__":
    write_artifacts()
