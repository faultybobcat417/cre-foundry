"""Focused tests for the independent CALIBRATION-001 evaluator."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import json
import unittest

from evals.public.calibration_framework_evaluator import (
    BOUNDED_PROPERTY_GRID, INPUT_PATH, INPUT_SCHEMA_PATH, MUTATION_DIAGNOSTICS, MUTATION_RECIPES, RUN_PATH, RUN_SCHEMA_PATH,
    _apply_recipe, _bin, _log_terms, _metrics, _prediction_bin_tv, digest_json, evaluate, evaluate_bounded_property_grid,
    evaluate_registered_mutation, strict_load,
)
from cre_foundry.calibration.framework import build_run


class CalibrationFrameworkTests(unittest.TestCase):
    def test_canonical_passes(self):
        self.assertEqual(evaluate(), [])

    def test_exact_bin_boundaries(self):
        expected = {Fraction(0): "B0", Fraction(1, 5): "B1", Fraction(2, 5): "B2", Fraction(3, 5): "B3", Fraction(4, 5): "B4", Fraction(1): "B4"}
        self.assertEqual({value: _bin(value) for value in expected}, expected)
        quantum = Fraction(1, 1000)
        for edge, below, at in [(Fraction(1, 5), "B0", "B1"), (Fraction(2, 5), "B1", "B2"), (Fraction(3, 5), "B2", "B3"), (Fraction(4, 5), "B3", "B4")]:
            self.assertEqual(_bin(edge - quantum), below)
            self.assertEqual(_bin(edge), at)
            self.assertEqual(_bin(edge + quantum), at)

    def test_validation_only_fit_counts(self):
        run = strict_load(RUN_PATH)
        self.assertEqual([(row["bin_id"], row["mature"], row["positive"]) for row in run["fit"]["cells"]], [("B0", 4, 1), ("B1", 4, 0), ("B2", 4, 2), ("B3", 0, 0), ("B4", 0, 0)])
        self.assertEqual(run["fit"]["population"]["excluded_null_or_late_rows"], 12)

    def test_empty_cells_have_no_probability(self):
        run = strict_load(RUN_PATH)
        empty = [row for row in run["fit"]["cells"] if row["cell_state"] == "EMPTY_NOT_ESTIMABLE"]
        self.assertEqual(len(empty), 2)
        self.assertTrue(all(row["posterior_probability"] is None for row in empty))

    def test_baseline_streams_are_rank_only(self):
        run = strict_load(RUN_PATH)
        self.assertEqual(len(run["probability_eligibility"]["ineligible_rank_streams"]), 5)
        self.assertFalse(run["probability_eligibility"]["ordinal_business_value_is_probability"])

    def test_macro_micro_are_separate(self):
        run = strict_load(RUN_PATH)
        metrics = run["split_metrics"]["TEST"]
        self.assertIn("candidate_micro_brier", metrics)
        self.assertIn("route_day_macro_brier", metrics)

    def test_partial_validation_route_nulls_macro(self):
        run = strict_load(RUN_PATH)
        metrics = run["split_metrics"]["VALIDATION"]
        self.assertIsNone(metrics["route_day_macro_brier"])
        self.assertIsNone(metrics["candidate_micro_brier"])
        self.assertIsNone(metrics["reportable_bin_ece_l1"])
        self.assertEqual(metrics["partial_route_day_ids"], ["ROUTE_DAY:SYN_BASE_05"])
        self.assertEqual(metrics["denominators"]["complete_route_days"], 1)
        self.assertEqual(metrics["denominators"]["partial_route_days"], 1)

    def test_subgroup_metrics_use_test_only_complete_populations(self):
        run = strict_load(RUN_PATH)
        expected = {"A": {"numerator": 1, "denominator": 4}, "B": {"numerator": 5, "denominator": 18}, "C": {"numerator": 7, "denominator": 36}}
        for segment, brier in expected.items():
            with self.subTest(segment=segment):
                cell = run["subgroup_metrics"]["cells"][segment]
                self.assertEqual(cell["analysis_status"], "COMPLETE_SYNTHETIC_MECHANICS")
                self.assertEqual(cell["denominators"]["assigned_candidates"], 8)
                self.assertEqual(cell["denominators"]["complete_route_days"], 2)
                self.assertEqual(cell["candidate_micro_brier"], brier)
        empty = run["subgroup_metrics"]["cells"]["UNKNOWN"]
        self.assertEqual(empty["analysis_status"], "PARTIAL_NOT_COMPARABLE")
        self.assertEqual(empty["denominators"]["assigned_candidates"], 0)
        self.assertEqual(empty["denominators"]["complete_route_days"], 0)

    def test_symbolic_log_loss_no_decimal(self):
        run = strict_load(RUN_PATH)
        value = run["split_metrics"]["TEST"]["symbolic_log_loss"]
        self.assertEqual(value["status"], "CANONICAL_SYMBOLIC_LOG_RATIONAL_TERMS")
        self.assertNotIn("value", value)

    def test_unknown_probability_forces_abstention(self):
        run = strict_load(RUN_PATH)
        scenario = next(row for row in run["scenario_runs"] if row["scenario_id"] == "UNKNOWN_ADMISSIBLE_PROBABILITY")
        self.assertEqual(scenario["math_decision"]["decision"], "ABSTAIN_NO_VALID_TEN")
        self.assertEqual(scenario["math_decision"]["reason"], "UNRESOLVED_VALUE_COULD_DOMINATE")
        self.assertEqual(scenario["math_decision"]["selected"], [])

    def test_occupied_sparse_cell_has_null_reliability(self):
        run = strict_load(RUN_PATH)
        scenario = next(row for row in run["scenario_runs"] if row["scenario_id"] == "SPARSE_OCCUPIED_RELIABILITY_CELL")
        occupied = next(row for row in scenario["metrics"]["reliability_bins"] if row["count"] == 1)
        self.assertEqual(scenario["metrics"]["denominators"]["assigned_candidates"], 12)
        self.assertEqual(occupied["cell_state"], "SPARSE_NOT_ESTIMABLE")
        self.assertIsNone(occupied["mean_probability"])
        self.assertIsNone(scenario["metrics"]["reportable_bin_ece_l1"])

    def test_subgroup_and_temporal_claims_are_sensitivity_only(self):
        run = strict_load(RUN_PATH)
        self.assertIn("NOT_FAIRNESS", run["subgroup_metrics"]["summary"]["claim"])
        self.assertIsNone(run["subgroup_metrics"]["summary"]["pairwise_gaps"])
        self.assertIn("NOT_STABILITY", run["temporal_metrics"]["summary"]["claim"])
        self.assertEqual(run["temporal_metrics"]["summary"]["prediction_bin_total_variation"], {"numerator": 0, "denominator": 1})

    def test_missing_model_feature_is_retained_and_abstains(self):
        run = strict_load(RUN_PATH)
        scenario = next(row for row in run["scenario_runs"] if row["scenario_id"] == "MISSING_MODEL_FEATURE_AND_SUBGROUP")
        self.assertEqual(scenario["metrics"]["denominators"]["assigned_candidates"], 12)
        self.assertEqual(scenario["metrics"]["denominators"]["missing_probability"], 1)
        self.assertEqual(scenario["unknown_subgroup_cell"]["assigned_candidates"], 1)
        self.assertEqual(scenario["math_decision"]["reason"], "UNRESOLVED_VALUE_COULD_DOMINATE")

    def test_symbolic_log_loss_endpoints(self):
        good = _log_terms([{"candidate_id": "p1", "calibrated_probability": {"numerator": 1, "denominator": 1}, "label": True}, {"candidate_id": "p0", "calibrated_probability": {"numerator": 0, "denominator": 1}, "label": False}])
        self.assertEqual(good["status"], "CANONICAL_SYMBOLIC_LOG_RATIONAL_TERMS")
        self.assertTrue(all(row["log_ratio_numerator"] == row["log_ratio_denominator"] == 1 for row in good["terms"]))
        bad = _log_terms([{"candidate_id": "bad", "calibrated_probability": {"numerator": 0, "denominator": 1}, "label": True}])
        self.assertEqual(bad["status"], "POSITIVE_INFINITY")

    def test_temporal_tv_is_computed_and_can_be_nonzero(self):
        run = strict_load(RUN_PATH)
        ledger = deepcopy(run["prediction_ledger"])
        target = next(row for row in ledger if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_08")
        target["calibrated_bin_id"] = "B4"
        self.assertGreater(_prediction_bin_tv(ledger, "ROUTE_DAY:SYN_BASE_07", "ROUTE_DAY:SYN_BASE_08"), 0)

    def test_falsy_subjects_fail_closed(self):
        self.assertEqual(evaluate({}, {}), ["CALIBRATION-SHAPE-SCHEMA"])
        with self.assertRaises((KeyError, TypeError, ValueError)):
            build_run({}, {}, {})

    def test_nested_schemas_reject_hollow_documents(self):
        from jsonschema import Draft202012Validator
        input_schema, run_schema = strict_load(INPUT_SCHEMA_PATH), strict_load(RUN_SCHEMA_PATH)
        frozen_input, run = strict_load(INPUT_PATH), strict_load(RUN_PATH)
        bad_input = deepcopy(frozen_input); bad_input["probability_head"] = {}
        bad_run = deepcopy(run); bad_run["prediction_ledger"] = [{} for _ in range(48)]
        self.assertTrue(list(Draft202012Validator(input_schema).iter_errors(bad_input)))
        self.assertTrue(list(Draft202012Validator(run_schema).iter_errors(bad_run)))
        for field, hollow in [("fit", {}), ("split_metrics", {"VALIDATION": {}, "TEST": {}}), ("subgroup_metrics", {}), ("temporal_metrics", {}), ("math_runs", [{}, {}]), ("scenario_runs", [{}, {}, {}, {}])]:
            with self.subTest(field=field):
                bad_run = deepcopy(run); bad_run[field] = hollow
                self.assertTrue(list(Draft202012Validator(run_schema).iter_errors(bad_run)))
        semantic_holes = []
        bad = deepcopy(run); bad["split_metrics"]["TEST"]["rank_concordance_pair_counts"] = {"garbage": "accepted"}; semantic_holes.append(bad)
        bad = deepcopy(run); bad["math_runs"][0]["math_decision"]["selected"] = [1]; semantic_holes.append(bad)
        bad = deepcopy(run); bad["replay_receipt"]["bindings"] = {f"arbitrary_{index}": "0" * 64 for index in range(14)}; semantic_holes.append(bad)
        bad = deepcopy(run); bad["scenario_runs"][2]["assertion"] = {"garbage": "accepted"}; semantic_holes.append(bad)
        for index, bad_run in enumerate(semantic_holes):
            with self.subTest(semantic_hole=index):
                self.assertTrue(list(Draft202012Validator(run_schema).iter_errors(bad_run)))

    def test_fragment_metrics_fail_closed(self):
        run = strict_load(RUN_PATH)
        row = next(row for row in run["prediction_ledger"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07")
        metrics = _metrics([row], ["ROUTE_DAY:SYN_BASE_07"])
        self.assertEqual(metrics["analysis_status"], "PARTIAL_NOT_COMPARABLE")
        self.assertEqual(metrics["denominators"]["assigned_candidates"], 1)
        self.assertEqual(metrics["denominators"]["partial_route_days"], 1)
        self.assertIsNone(metrics["candidate_micro_brier"])
        self.assertIsNone(metrics["route_day_macro_brier"])

    def test_temporal_tv_all_unknown_is_not_computable(self):
        run = strict_load(RUN_PATH)
        ledger = deepcopy(run["prediction_ledger"])
        for row in ledger:
            if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07":
                row["calibrated_bin_id"] = None
        with self.assertRaisesRegex(ValueError, "NOT_COMPUTABLE_ALL_PROBABILITIES_UNKNOWN"):
            _prediction_bin_tv(ledger, "ROUTE_DAY:SYN_BASE_07", "ROUTE_DAY:SYN_BASE_08")

    def test_cell_threshold_zero_through_five(self):
        run = strict_load(RUN_PATH)
        route_id = "ROUTE_DAY:SYN_BASE_07"
        base = [row for row in run["prediction_ledger"] if row["route_day_id"] == route_id]
        for count in range(6):
            rows = deepcopy(base)
            for row in rows[:count]:
                row["calibrated_probability"] = {"numerator": 9, "denominator": 10}
                row["calibrated_bin_id"] = "B4"
            cell = next(row for row in _metrics(rows, [route_id])["reliability_bins"] if row["bin_id"] == "B4")
            expected = "EMPTY_NOT_ESTIMABLE" if count == 0 else "SPARSE_NOT_ESTIMABLE" if count < 4 else "REPORTABLE_SYNTHETIC_MECHANICS"
            self.assertEqual(cell["cell_state"], expected)

    def test_outcome_null_states_remain_distinct(self):
        states = ["IMMATURE_UNKNOWN", "CENSORED_UNKNOWN", "COMPETING_EVENT_UNKNOWN", "CONFLICTED_UNKNOWN", "UNKNOWN"]
        run = strict_load(RUN_PATH)
        rows = [deepcopy(row) for row in run["prediction_ledger"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07"]
        for row, state in zip(rows, states):
            row["outcome_state"], row["label"] = state, None
        metrics = _metrics(rows, ["ROUTE_DAY:SYN_BASE_07"])
        self.assertEqual(metrics["denominators"]["nullable_labels_by_state"], {state: 1 for state in sorted(states)})
        self.assertEqual(metrics["analysis_status"], "PARTIAL_NOT_COMPARABLE")

    def test_metric_reconstruction_is_row_order_invariant(self):
        run = strict_load(RUN_PATH)
        rows = [row for row in run["prediction_ledger"] if row["route_day_id"] == "ROUTE_DAY:SYN_BASE_07"]
        self.assertEqual(_metrics(rows, ["ROUTE_DAY:SYN_BASE_07"]), _metrics(list(reversed(rows)), ["ROUTE_DAY:SYN_BASE_07"]))

    def test_registered_fixtures_contain_bound_concrete_patches(self):
        root = RUN_PATH.parents[2] / "evals/known_bad/frontier"
        for case_id in MUTATION_DIAGNOSTICS:
            fixture = json.loads((root / f"calibration_{case_id.replace('-', '_')}.json").read_text())
            self.assertEqual(fixture["case_id"], case_id)
            self.assertTrue(fixture["patch"]["operations"])
            for operation in fixture["patch"]["operations"]:
                self.assertIn(operation["document"], {"subject", "input"})
                self.assertTrue(operation["path"])

    def test_every_issue_is_exactly_ten(self):
        run = strict_load(RUN_PATH)
        self.assertTrue(all(len(row["math_decision"]["selected"]) == 10 for row in run["math_runs"] if row["math_decision"]["decision"] == "ISSUE"))

    def test_claims_and_uncertainty_fail_closed(self):
        run = strict_load(RUN_PATH)
        self.assertTrue(all(value is False for value in run["claims"].values()))
        self.assertEqual(run["uncertainty"]["status"], "NOT_EMPIRICALLY_ESTIMABLE")
        self.assertIsNone(run["uncertainty"]["confidence_interval"])

    def test_coordinated_subject_rehash_fails(self):
        run = strict_load(RUN_PATH)
        run["split_metrics"]["TEST"]["candidate_micro_brier"] = {"numerator": 0, "denominator": 1}
        run["replay_receipt"]["split_metrics_sha256"] = "0" * 64
        self.assertTrue(evaluate(run, strict_load(INPUT_PATH)))

    def test_fully_rehashed_mutations_have_internally_valid_digests(self):
        section_bindings = {"prediction_ledger_sha256": "prediction_ledger", "split_metrics_sha256": "split_metrics", "math_runs_sha256": "math_runs"}
        for case_id in ["rehashed-fit", "rehashed-predictions", "rehashed-math-problem-and-decision", "rehashed-metrics", "rehashed-receipt"]:
            with self.subTest(case_id=case_id):
                run, frozen_input = strict_load(RUN_PATH), strict_load(INPUT_PATH)
                _apply_recipe(run, frozen_input, MUTATION_RECIPES[case_id])
                receipt = run["replay_receipt"]
                for receipt_key, section_key in section_bindings.items():
                    self.assertEqual(receipt[receipt_key], digest_json(run[section_key]))
                self.assertEqual(receipt["fit_sha256"], run["fit"]["fit_sha256"])
                for math_run in run["math_runs"]:
                    self.assertEqual(math_run["math_problem_sha256"], digest_json(math_run["math_problem"]))
                    self.assertEqual(math_run["math_decision_sha256"], digest_json(math_run["math_decision"]))
                receipt_core = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
                self.assertEqual(receipt["receipt_sha256"], digest_json(receipt_core))

    def test_complete_bounded_property_grid(self):
        self.assertEqual(len(BOUNDED_PROPERTY_GRID), 13)
        self.assertEqual(evaluate_bounded_property_grid(), [])

    def test_all_registered_mutations_are_rejected(self):
        for case_id, diagnostic in MUTATION_DIAGNOSTICS.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_registered_mutation(case_id), [diagnostic])


if __name__ == "__main__":
    unittest.main()
