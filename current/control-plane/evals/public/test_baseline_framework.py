"""Public tests for the bounded synthetic baseline framework."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.baselines.framework import build_benchmark, build_policy_registry, build_run, digest_json, _fit, _raw_scores
from evals.public.baseline_framework_evaluator import (
    MUTATION_DIAGNOSTICS, POLICY_SCHEMA_PATH, RUN_SCHEMA_PATH,
    evaluate, evaluate_registered_mutation, strict_load,
)
from evals.public.math_oracle_evaluator import evaluate as math_evaluate


class BaselineFrameworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.benchmark = build_benchmark()
        cls.registry = build_policy_registry()
        cls.run_subject = build_run(cls.benchmark, cls.registry)

    def test_canonical_subject_passes_independent_evaluator(self):
        self.assertEqual(evaluate(self.run_subject, self.benchmark, self.registry), [])

    def test_builder_is_byte_deterministic(self):
        self.assertEqual(digest_json(self.run_subject), digest_json(build_run(build_benchmark(), build_policy_registry())))

    def test_policy_and_run_schemas(self):
        for subject, schema_path in [(self.registry, POLICY_SCHEMA_PATH), (self.run_subject, RUN_SCHEMA_PATH)]:
            validator = Draft202012Validator(strict_load(schema_path), format_checker=FormatChecker())
            self.assertEqual(list(validator.iter_errors(subject)), [])

    def test_exact_required_policy_families(self):
        self.assertEqual({row["policy_id"] for row in self.registry["policies"]}, set(MUTATION_POLICY_IDS))

    def test_every_issue_is_exact_ten_distinct_locations(self):
        for row in self.run_subject["policy_runs"]:
            self.assertEqual(row["math_decision"]["decision"], "ISSUE")
            selected = row["math_decision"]["selected"]
            self.assertEqual(len(selected), 10)
            self.assertEqual(len({item["physical_location_id"] for item in selected}), 10)

    def test_identical_candidate_universe_and_non_score_math(self):
        by_route = {}
        for row in self.run_subject["policy_runs"]:
            by_route.setdefault(row["route_day_id"], set()).add((row["candidate_universe_sha256"], row["feature_view_sha256"], row["non_score_math_sha256"]))
        self.assertTrue(all(len(values) == 1 for values in by_route.values()))

    def test_feature_clocks_are_point_in_time_safe(self):
        for route in self.benchmark["routes"]:
            for candidate in route["candidates"]:
                for feature in candidate["features"]:
                    clocks = [feature[name] for name in ["event_at", "recorded_at", "ingested_at", "validation_completed_at", "available_at", "decision_at"]]
                    self.assertEqual(clocks, sorted(clocks))
                    self.assertEqual(feature["source_stage"], 1)

    def test_null_labels_are_not_negative_or_fit_rows(self):
        null_candidates = {row["candidate_id"] for row in self.benchmark["labels"] if row["label"] is None}
        self.assertGreater(len(null_candidates), 0)
        included_candidates = {row.split("|")[1] for row in self.run_subject["fit"]["training_row_ids"]}
        self.assertTrue(null_candidates.isdisjoint(included_candidates))

    def test_train_only_statistical_fit(self):
        self.assertTrue(all(row.startswith(("ROUTE_DAY:SYN_BASE_01|", "ROUTE_DAY:SYN_BASE_02|", "ROUTE_DAY:SYN_BASE_03|", "ROUTE_DAY:SYN_BASE_04|")) for row in self.run_subject["fit"]["training_row_ids"]))

    def test_random_schedule_is_complete_and_replayable(self):
        random_runs = [row for row in self.run_subject["policy_runs"] if row["policy_id"] == "SEEDED_RANDOM_SYNTHETIC_V1"]
        self.assertEqual(len(random_runs), 16 * 8)
        self.assertEqual({row["seed_hex"] for row in random_runs}, set(self.registry["random_seed_schedule"]))

    def test_statistical_scores_are_exact_rationals_and_tied(self):
        rows = [row for row in self.run_subject["policy_runs"] if row["policy_id"] == "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1"]
        for row in rows:
            by_fraction = {}
            for score in row["scores"]:
                self.assertIsInstance(score["numerator"], int)
                self.assertGreater(score["denominator"], 0)
                by_fraction.setdefault((score["numerator"], score["denominator"]), set()).add(score["business_value_units"])
            self.assertTrue(all(len(tiers) == 1 for tiers in by_fraction.values()))

    def test_partial_common_universe_never_finalizes(self):
        rows = [row for row in self.run_subject["policy_runs"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_05"]
        self.assertTrue(all(row["selected_label_summary"]["common_universe_fully_mature"] is False for row in rows))
        self.assertTrue(all(row["selected_label_summary"]["final_f9_count_at_10"] is None for row in rows))

    def test_empirical_uncertainty_and_production_authority_stay_null(self):
        for metric in self.run_subject["metrics"].values():
            uncertainty = metric["empirical_uncertainty"]
            self.assertEqual(uncertainty["status"], "NOT_EMPIRICALLY_ESTIMABLE")
            self.assertIsNone(uncertainty["confidence_interval"])
        self.assertFalse(self.run_subject["replacement_analysis"]["production_replacement_authorized"])
        self.assertFalse(self.run_subject["proof"]["live_use_authorized"])

    def test_recall_primary_is_route_run_macro_and_micro_is_explicit(self):
        expected = {
            "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1": (3, 4, 7, 9),
            "INCUMBENT_SYNTHETIC_V1": (11, 12, 8, 9),
            "RECENCY_SOURCE_SYNTHETIC_V1": (11, 12, 8, 9),
            "SEEDED_RANDOM_SYNTHETIC_V1": (151, 192, 113, 144),
        }
        for policy_id, (macro_n, macro_d, micro_n, micro_d) in expected.items():
            metric = self.run_subject["metrics"][policy_id]
            self.assertEqual(metric["recall_at_10"], {"numerator": macro_n, "denominator": macro_d})
            self.assertEqual(metric["recall_micro_at_10"], {"numerator": micro_n, "denominator": micro_d})

    def test_permuted_candidates_do_not_change_selected_set(self):
        permuted = deepcopy(self.benchmark)
        for route in permuted["routes"]:
            route["candidates"].reverse()
        replay = build_run(permuted, self.registry)
        original = {(row["policy_id"], row["seed_hex"], row["route_day_id"]): {item["candidate_id"] for item in row["math_decision"]["selected"]} for row in self.run_subject["policy_runs"]}
        changed = {(row["policy_id"], row["seed_hex"], row["route_day_id"]): {item["candidate_id"] for item in row["math_decision"]["selected"]} for row in replay["policy_runs"]}
        self.assertEqual(original, changed)

    def test_every_registered_mutation_has_exact_diagnostic(self):
        for case_id, expected in MUTATION_DIAGNOSTICS.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_registered_mutation(case_id), [expected])

    def test_candidate_counts_zero_through_twenty_cover_issue_and_abstain(self):
        template = deepcopy(self.run_subject["policy_runs"][0]["math_problem"])
        source = deepcopy(template["candidates"])
        expanded = []
        for index in range(20):
            candidate = deepcopy(source[index % len(source)])
            candidate["candidate_id"] = f"GRID:CAND:{index:02d}"
            candidate["physical_location_id"] = f"GRID:LOCATION:{index:02d}"
            expanded.append(candidate)
        for count in range(21):
            with self.subTest(count=count):
                problem = deepcopy(template)
                problem["candidates"] = deepcopy(expanded[:count])
                decision = math_evaluate(problem)
                expected = "ISSUE" if count >= 10 else "ABSTAIN_NO_VALID_TEN"
                self.assertEqual(decision["decision"], expected)

    def test_math_clock_minus_one_equal_plus_one_and_gate_unknown(self):
        template = deepcopy(self.run_subject["policy_runs"][0]["math_problem"])
        template["candidates"] = template["candidates"][:10]
        cutoff = template["snapshot"]["stage1_cutoff"]
        cutoff_time = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        before = (cutoff_time - timedelta(seconds=1)).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        after = (cutoff_time + timedelta(seconds=1)).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        for observed_at, expected in [(before, "ISSUE"), (cutoff, "ISSUE"), (after, "ABSTAIN_NO_VALID_TEN")]:
            problem = deepcopy(template)
            problem["candidates"][0]["observed_at"] = observed_at
            self.assertEqual(math_evaluate(problem)["decision"], expected)
        for gate_state in ["FAIL", "UNKNOWN"]:
            problem = deepcopy(template)
            problem["candidates"][0]["gates"]["evidence"] = gate_state
            self.assertEqual(math_evaluate(problem)["decision"], "ABSTAIN_NO_VALID_TEN")

    def test_twenty_policy_input_permutations_are_set_invariant(self):
        problem = deepcopy(self.run_subject["policy_runs"][0]["math_problem"])
        expected = {row["candidate_id"] for row in math_evaluate(problem)["selected"]}
        candidates = problem["candidates"]
        for offset in range(20):
            rotated = deepcopy(problem)
            pivot = offset % len(candidates)
            rotated["candidates"] = deepcopy(candidates[pivot:] + candidates[:pivot])
            self.assertEqual({row["candidate_id"] for row in math_evaluate(rotated)["selected"]}, expected)

    def test_incomplete_test_universe_is_nullable_not_an_error(self):
        benchmark = build_benchmark()
        label = next(row for row in benchmark["labels"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07")
        label["state"], label["label"] = "IMMATURE_UNKNOWN", None
        core = {key: label[key] for key in ["route_day_id", "candidate_id", "state", "available_at"]}
        label["assessment_sha256"] = digest_json({"synthetic_outcomes_current_head": core})
        run = build_run(benchmark, self.registry)
        self.assertTrue(all(metric["comparison_status"] == "NOT_COMPARABLE_INCOMPLETE_LABELS" for metric in run["metrics"].values()))
        self.assertEqual(run["replacement_analysis"]["disposition"], "NOT_COMPARABLE_INCOMPLETE_LABELS")
        incomplete_rows = [row for row in run["policy_runs"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07"]
        self.assertTrue(all(row["rank_concordance"] is None for row in incomplete_rows))

    def test_unseen_statistical_bucket_uses_exact_global_prior(self):
        benchmark = build_benchmark()
        registry = build_policy_registry()
        fit = _fit(benchmark, registry)
        route = deepcopy(benchmark["routes"][-1])
        segment = next(row for row in route["candidates"][0]["features"] if row["feature_definition_id"] == "FEATURE_DEF:market_segment:V1")
        segment["value"] = "UNSEEN"
        policy = next(row for row in registry["policies"] if row["policy_id"] == "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1")
        score = dict(_raw_scores(policy, route, benchmark, registry, fit, None))[route["candidates"][0]["candidate_id"]]
        self.assertEqual((score.numerator, score.denominator), (fit["global_prior"]["numerator"], fit["global_prior"]["denominator"]))


MUTATION_POLICY_IDS = [
    "INCUMBENT_SYNTHETIC_V1", "SEEDED_RANDOM_SYNTHETIC_V1", "TRANSPARENT_RULE_SYNTHETIC_V1",
    "RECENCY_SOURCE_SYNTHETIC_V1", "BETA_BINOMIAL_BUCKET_SYNTHETIC_V1",
]


if __name__ == "__main__":
    unittest.main()
