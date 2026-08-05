import copy
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.outcomes.ledger import build_input_ledger, build_itt_inclusion_cases, build_outcome_run
from evals.public.outcomes_labels_evaluator import (
    _booking_groups_at, canonical_bytes, closed_window_contains, digest_json,
    strict_load, validate_itt_inclusion_cases, validate_outcome_run,
)
from scripts.validate_outcomes_labels import apply_mutation


class OutcomesLabelsTests(unittest.TestCase):
    def test_schema_is_strict_and_all_assessment_revisions_conform(self):
        schema = strict_load(ROOT / "contracts/f9_outcome.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        run = build_outcome_run()
        for assessment in run["assessments"]:
            self.assertEqual([], list(validator.iter_errors(assessment)))
        mutant = copy.deepcopy(run["assessments"][0]); mutant["unexpected"] = True
        self.assertTrue(list(validator.iter_errors(mutant)))

    def test_seven_states_have_exact_label_mapping(self):
        run = build_outcome_run()
        mapping = {row["assessment_state"]: row["counted_f9"] for row in run["current_heads"]}
        self.assertEqual({
            "F9_CONFIRMED_SYNTHETIC": True, "MATURE_NO_F9_SYNTHETIC": False,
            "IMMATURE_UNKNOWN": None, "CENSORED_UNKNOWN": None,
            "COMPETING_EVENT_UNKNOWN": None, "CONFLICTED_UNKNOWN": None, "UNKNOWN": None,
        }, mapping)
        self.assertEqual([], validate_outcome_run(run))

    def test_route_day_reports_lower_bound_not_premature_final(self):
        aggregate = build_outcome_run()["route_day_aggregate"]
        self.assertEqual(3, aggregate["confirmed_f9_lower_bound"])
        self.assertIsNone(aggregate["final_f9_count"])
        self.assertEqual("IMMATURE_PARTIAL", aggregate["route_day_ascertainment_state"])
        self.assertTrue(aggregate["include_in_itt"])

    def test_window_is_assignment_anchored_and_downstream_unknown(self):
        run = build_outcome_run()
        for assessment in run["assessments"]:
            self.assertEqual("ROUTE_DAY_ASSIGNMENT", assessment["window"]["anchor_type"])
            self.assertEqual("2026-08-01T00:00:00Z", assessment["window"]["anchor_at"])
            self.assertEqual("CLOSED_START_CLOSED_END_SYNTHETIC", assessment["window"]["interval_convention"])
            self.assertTrue(all(value == "UNKNOWN" for value in assessment["downstream_states"].values()))

    def test_correction_is_append_only_and_prior_bytes_are_preserved(self):
        run = build_outcome_run()
        revisions = [row for row in run["assessments"] if row["outcome_unit_id"].endswith(":10")]
        self.assertEqual(3, len(revisions))
        self.assertEqual("CONFLICTED_UNKNOWN", revisions[0]["assessment_state"])
        self.assertEqual("F9_CONFIRMED_SYNTHETIC", revisions[1]["assessment_state"])
        self.assertEqual("F9_CONFIRMED_SYNTHETIC", revisions[2]["assessment_state"])
        self.assertEqual(revisions[0]["assessment_id"], revisions[1]["predecessor"]["assessment_id"])
        self.assertEqual(revisions[1]["assessment_id"], revisions[2]["predecessor"]["assessment_id"])
        self.assertNotEqual(canonical_bytes(revisions[0]), canonical_bytes(revisions[1]))

    def test_current_heads_share_one_registered_route_day_asof(self):
        run = build_outcome_run()
        self.assertEqual(20, len(run["assessments"]))
        self.assertEqual({"2026-08-31T00:01:00Z"}, {row["assessed_at"] for row in run["current_heads"]})

    def test_itt_includes_abstain_and_nonadherence_without_inventing_counts(self):
        cases = build_itt_inclusion_cases()
        self.assertEqual([], validate_itt_inclusion_cases(cases))
        self.assertTrue(all(row["include_in_itt"] for row in cases["cases"]))
        self.assertEqual({"ISSUE", "ABSTAIN_NO_VALID_TEN"}, {row["assignment_result"] for row in cases["cases"]})
        self.assertFalse(cases["outcome_count_claimed"])

    def test_closed_window_boundaries_are_exact(self):
        start, end = "2026-08-01T00:00:00Z", "2026-08-31T00:00:00Z"
        self.assertFalse(closed_window_contains("2026-07-31T23:59:59Z", start, end))
        self.assertTrue(closed_window_contains(start, start, end))
        self.assertTrue(closed_window_contains("2026-08-01T00:00:01Z", start, end))
        self.assertTrue(closed_window_contains("2026-08-30T23:59:59Z", start, end))
        self.assertTrue(closed_window_contains(end, start, end))
        self.assertFalse(closed_window_contains("2026-08-31T00:00:01Z", start, end))

    def test_active_asof_dedupe_excludes_future_and_retracted_evidence(self):
        ledger = build_input_ledger()
        unit8 = next(row for row in ledger["units"] if row["sequence_position"] == 8)
        f9 = next(row for row in unit8["assertions"] if row["assertion_type"] == "F9_EVIDENCE")
        f9["available_at"] = "2026-09-01T00:00:00Z"
        groups = _booking_groups_at(ledger, "2026-08-31T00:01:00Z")
        self.assertEqual(["OUTCOME_UNIT:ROUTE_DAY_001:09"], groups["BOOKING:SYN_SHARED_008_009"])

        run = build_outcome_run()
        unit9 = next(row for row in run["current_heads"] if row["outcome_unit_id"].endswith(":09"))
        self.assertEqual(digest_json(_booking_groups_at(run["input_ledger"], unit9["assessed_at"])), unit9["dedupe_snapshot_sha256"])

        ledger = build_input_ledger()
        unit8 = next(row for row in ledger["units"] if row["sequence_position"] == 8)
        f9 = next(row for row in unit8["assertions"] if row["assertion_type"] == "F9_EVIDENCE")
        correction = {
            "assertion_id": "ASSERTION:ROUTE_DAY_001:08:02", "assertion_type": "CORRECTION",
            "outcome_unit_id": unit8["outcome_unit_id"], "occurred_at": "2026-08-05T11:00:00Z",
            "recorded_at": "2026-08-05T11:01:00Z", "ingested_at": "2026-08-05T11:02:00Z",
            "validation_completed_at": "2026-08-05T12:00:00Z", "available_at": "2026-08-05T12:00:00Z",
            "payload": {"action": "RETRACT", "corrects_assertion_id": f9["assertion_id"], "corrects_assertion_sha256": digest_json(f9), "reason": "SYNTHETIC_ADJUDICATED_RETRACTION"},
        }
        unit8["assertions"].append(correction)
        groups = _booking_groups_at(ledger, "2026-08-31T00:01:00Z")
        self.assertEqual(["OUTCOME_UNIT:ROUTE_DAY_001:09"], groups["BOOKING:SYN_SHARED_008_009"])

    def test_output_schema_conditionally_binds_state_and_label(self):
        schema = strict_load(ROOT / "contracts/f9_outcome.schema.json")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        positive = copy.deepcopy(next(row for row in build_outcome_run()["current_heads"] if row["counted_f9"] is True))
        positive["counted_f9"] = None
        self.assertTrue(list(validator.iter_errors(positive)))
        run = build_outcome_run()
        by_state = {row["assessment_state"]: copy.deepcopy(row) for row in run["current_heads"]}
        censored = by_state["CENSORED_UNKNOWN"]; censored["event_ascertainment_state"] = "WINDOW_OPEN"; censored["stopping_event"] = None
        self.assertTrue(list(validator.iter_errors(censored)))
        competing = by_state["COMPETING_EVENT_UNKNOWN"]; competing["event_ascertainment_state"] = "CENSORED"; competing["stopping_event"]["type"] = "CENSORING"
        self.assertTrue(list(validator.iter_errors(competing)))
        mature = by_state["MATURE_NO_F9_SYNTHETIC"]; mature["components"] = copy.deepcopy(next(row for row in run["current_heads"] if row["counted_f9"] is True)["components"])
        self.assertTrue(list(validator.iter_errors(mature)))
        conflicted = by_state["CONFLICTED_UNKNOWN"]; conflicted["event_ascertainment_state"] = "UNKNOWN"; conflicted["components"]["deduplication"] = "CANONICAL_BOOKING_EPISODE"
        self.assertTrue(list(validator.iter_errors(conflicted)))

    def test_strict_input_ledger_schema_rejects_extra_and_cross_unit_fields(self):
        schema = strict_load(ROOT / "contracts/f9_outcome_input_ledger.schema.json")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        ledger = build_input_ledger(); ledger["unexpected_float"] = 1.25
        self.assertTrue(list(validator.iter_errors(ledger)))
        ledger = build_input_ledger(); ledger["units"][0]["assertions"][0]["unexpected"] = True
        self.assertTrue(list(validator.iter_errors(ledger)))
        policy_schema = strict_load(ROOT / "contracts/f9_window_policy.schema.json")
        policy = strict_load(ROOT / "artifacts/outcomes/synthetic_window_policy.json")
        self.assertEqual([], list(Draft202012Validator(policy_schema, format_checker=FormatChecker()).iter_errors(policy)))
        policy["horizon_days"] = 31
        self.assertTrue(list(Draft202012Validator(policy_schema, format_checker=FormatChecker()).iter_errors(policy)))

    def test_malformed_subjects_and_duplicate_json_keys_fail_closed(self):
        run = build_outcome_run()
        mutant = copy.deepcopy(run); mutant["unexpected"] = True
        self.assertEqual(["OUTCOMES-SHAPE"], validate_outcome_run(mutant))
        mutant = copy.deepcopy(run); mutant["schema_version"] = "99.0.0"
        self.assertEqual(["OUTCOMES-BOUNDARY"], validate_outcome_run(mutant))
        mutant = copy.deepcopy(run); mutant["input_ledger"]["units"][0]["assertions"][0]["recorded_at"] = "2026-08-02T11:01:00"
        self.assertEqual(["OUTCOMES-CLOCK-ORDER"], validate_outcome_run(mutant))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):
                strict_load(path)

    def test_input_permutation_and_exact_duplicate_presentation_are_canonical(self):
        expected = canonical_bytes(build_outcome_run())
        for seed in range(20):
            ledger = build_input_ledger()
            random.Random(20260802 + seed).shuffle(ledger["units"])
            for unit in ledger["units"]:
                random.Random(seed * 100 + unit["sequence_position"]).shuffle(unit["assertions"])
            multiplicity = 1 + seed % 3
            for _ in range(multiplicity - 1):
                ledger["units"][0]["assertions"].append(copy.deepcopy(ledger["units"][0]["assertions"][0]))
            self.assertEqual(expected, canonical_bytes(build_outcome_run(ledger)))

    def test_all_registered_mutations_fail_exactly(self):
        contract = strict_load(ROOT / "artifacts/outcomes/public_evaluator_contract.json")
        for mutation in contract["registered_mutations"]:
            with self.subTest(mutation_id=mutation["mutation_id"]):
                subject = build_outcome_run()
                apply_mutation(subject, mutation["mutation_id"])
                self.assertEqual([mutation["expected_diagnostic"]], validate_outcome_run(subject))


if __name__ == "__main__":
    unittest.main()
