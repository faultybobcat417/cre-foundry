import copy
import random
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.contracts.thin_slice import build_fixture_observations, build_spine_from_observations, canonical_bytes, digest_json
from cre_foundry.vertical.shadow_slice import build_vertical_from_observations, build_vertical_slice
from evals.public.vertical_slice_evaluator import strict_load, validate_outcome_state, validate_vertical_slice


def mutate(subject, mutation_id):
    if mutation_id == "stage2_rewrite":
        subject["upstream_spine"]["observations"][0]["clocks"]["available_at"] = "2026-08-01T00:00:00Z"
    elif mutation_id == "protected_stop_issued":
        cid = subject["route_manifest"]["stops"][0]["candidate_id"]
        candidate = next(row for row in subject["upstream_spine"]["candidates"] if row["candidate_id"] == cid)
        candidate["protection"]["status"] = "PROTECTED"
        candidate["math_candidate"]["protected_status"] = "PROTECTED"
    elif mutation_id == "duplicate_stop_issued":
        duplicate = copy.deepcopy(subject["route_manifest"]["stops"][0])
        duplicate["sequence_position"] = 10
        subject["route_manifest"]["stops"][-1] = duplicate
    elif mutation_id == "route_selection_mismatch":
        selected = {row["candidate_id"] for row in subject["upstream_spine"]["math_decision"]["selected"]}
        replacement = next(row["math_candidate"] for row in subject["upstream_spine"]["candidates"] if row["candidate_id"] not in selected)
        subject["route_manifest"]["stops"][-1]["candidate_id"] = replacement["candidate_id"]
        subject["route_manifest"]["stops"][-1]["physical_location_id"] = replacement["physical_location_id"]
    elif mutation_id == "field_event_before_issuance":
        subject["field_events"][0]["occurred_at"] = "2026-07-31T23:44:59Z"
    elif mutation_id == "immature_outcome_counted":
        outcome = next(row for row in subject["f9_outcomes"] if row["outcome_state"] == "IMMATURE_UNKNOWN")
        outcome["counted_f9"] = False
    elif mutation_id == "replay_receipt_mismatch":
        subject["replay_receipt"]["route_manifest_sha256"] = "0" * 64
    else:
        raise ValueError("unknown mutation")


def refresh_outcome_receipt(subject):
    subject["replay_receipt"]["outcome_digests"] = [
        {"outcome_id": row["outcome_id"], "sha256": digest_json(row)}
        for row in sorted(subject["f9_outcomes"], key=lambda row: row["outcome_id"])
    ]


class VerticalSliceTests(unittest.TestCase):
    def test_schemas_are_strict_and_generated_documents_conform(self):
        subject = build_vertical_slice()
        cases = [
            ("synthetic_route_day.schema.json", [subject["route_manifest"]]),
            ("synthetic_field_event.schema.json", subject["field_events"]),
            ("synthetic_f9_outcome.schema.json", subject["f9_outcomes"]),
        ]
        for name, documents in cases:
            schema = strict_load(ROOT / "contracts" / name)
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            for document in documents:
                self.assertEqual([], list(validator.iter_errors(document)))
            mutant = copy.deepcopy(documents[0])
            mutant["unexpected"] = True
            self.assertTrue(list(validator.iter_errors(mutant)))

    def test_issue_and_abstain_paths(self):
        issued = build_vertical_slice(10)
        self.assertEqual([], validate_vertical_slice(issued))
        self.assertEqual("ISSUE", issued["result"])
        self.assertEqual(10, len(issued["route_manifest"]["stops"]))
        self.assertEqual(10, len({row["physical_location_id"] for row in issued["route_manifest"]["stops"]}))
        abstained = build_vertical_slice(1)
        self.assertEqual([], validate_vertical_slice(abstained))
        self.assertEqual("ABSTAIN_NO_VALID_TEN", abstained["result"])
        self.assertIsNone(abstained["route_manifest"])
        self.assertEqual([], abstained["field_events"])
        self.assertEqual([], abstained["f9_outcomes"])

    def test_stage_one_is_immutable_and_replay_is_permutation_stable(self):
        observations = build_fixture_observations(10)
        expected_spine = build_spine_from_observations(copy.deepcopy(observations))
        forward = build_vertical_from_observations(copy.deepcopy(observations))
        random.Random(20260802).shuffle(observations)
        permuted = build_vertical_from_observations(observations)
        self.assertEqual(canonical_bytes(forward), canonical_bytes(permuted))
        self.assertEqual(digest_json(expected_spine), digest_json(forward["upstream_spine"]))
        self.assertEqual(digest_json(expected_spine), forward["replay_receipt"]["upstream_spine_sha256"])

    def test_f9_positive_and_unknown_states_preserve_claim_boundary(self):
        subject = build_vertical_slice()
        positive = [row for row in subject["f9_outcomes"] if row["counted_f9"] is True]
        unknown = [row for row in subject["f9_outcomes"] if row["counted_f9"] is None]
        self.assertEqual(1, len(positive))
        self.assertEqual(9, len(unknown))
        self.assertEqual("F9_CONFIRMED_SYNTHETIC", positive[0]["outcome_state"])
        self.assertTrue(all(row["outcome_state"] == "IMMATURE_UNKNOWN" for row in unknown))
        self.assertTrue(all(value == "UNKNOWN" for row in subject["f9_outcomes"] for value in row["downstream_states"].values()))
        self.assertFalse(any(value for key, value in subject["proof"].items() if key.endswith("_proven") or key.endswith("_authorized") or key == "fixture_horizon_is_authorized_policy"))

    def test_non_positive_f9_states_remain_non_positive_and_have_explicit_semantics(self):
        base = build_vertical_slice()
        template = next(row for row in base["f9_outcomes"] if row["outcome_state"] == "IMMATURE_UNKNOWN")
        unknown_components = copy.deepcopy(template["components"])
        cases = [
            ("MATURE_NO_F9_SYNTHETIC", "COMPLETE_SYNTHETIC", "2026-09-15T12:00:00Z", False),
            ("CENSORED_UNKNOWN", "CENSORED", "2026-08-03T12:00:00Z", None),
            ("CONFLICTED_UNKNOWN", "CONFLICTED", "2026-08-03T12:00:00Z", None),
            ("UNKNOWN", "UNKNOWN", "2026-08-03T12:00:00Z", None),
        ]
        for state, ascertainment, assessed_at, counted in cases:
            with self.subTest(state=state):
                subject = copy.deepcopy(base)
                outcome = subject["f9_outcomes"][1]
                outcome["outcome_state"] = state
                outcome["window"]["ascertainment_state"] = ascertainment
                outcome["assessed_at"] = assessed_at
                outcome["counted_f9"] = counted
                outcome["components"] = unknown_components
                if state == "MATURE_NO_F9_SYNTHETIC":
                    outcome["components"] = {
                        "decision_maker": "UNKNOWN", "cre_requirement": "UNKNOWN",
                        "appointment": "NOT_OBSERVED_SYNTHETIC", "supporting_evidence": "ABSENT_SYNTHETIC",
                        "adjudication": "FAIL_SYNTHETIC", "deduplication": "UNIQUE_SYNTHETIC",
                    }
                if state == "CENSORED_UNKNOWN":
                    outcome["censored_at"] = "2026-08-02T13:00:00Z"
                    outcome["censor_reason"] = "SYNTHETIC_LOST_TO_FOLLOW_UP"
                self.assertEqual([], validate_outcome_state(outcome, subject["field_events"][1]))

                mutant_outcome = copy.deepcopy(outcome)
                mutant_outcome["counted_f9"] = True if counted is None else None
                self.assertNotEqual([], validate_outcome_state(mutant_outcome, subject["field_events"][1]))

    def test_bounded_counts_one_through_twenty(self):
        for count in range(1, 21):
            with self.subTest(count=count):
                self.assertEqual([], validate_vertical_slice(build_vertical_slice(count)))

    def test_registered_mutations_fail_exactly(self):
        cases = [
            ("stage2_rewrite", "VERTICAL-STAGE1-REWRITE", 10),
            ("protected_stop_issued", "VERTICAL-ROUTE-PROTECTED-STOP", 10),
            ("duplicate_stop_issued", "VERTICAL-ROUTE-DUPLICATE-LOCATION", 10),
            ("route_selection_mismatch", "VERTICAL-ROUTE-SELECTION-MISMATCH", 11),
            ("field_event_before_issuance", "VERTICAL-FIELD-BEFORE-ISSUANCE", 10),
            ("immature_outcome_counted", "VERTICAL-F9-IMMATURE-RELABELED", 10),
            ("replay_receipt_mismatch", "VERTICAL-REPLAY-RECEIPT-MISMATCH", 10),
        ]
        for mutation_id, expected, count in cases:
            with self.subTest(mutation_id=mutation_id):
                subject = build_vertical_slice(count)
                mutate(subject, mutation_id)
                self.assertEqual([expected], validate_vertical_slice(subject))

        duplicated_event = build_vertical_slice()
        duplicated_event["field_events"][1]["stop"] = copy.deepcopy(duplicated_event["field_events"][0]["stop"])
        self.assertEqual(["VERTICAL-FIELD-COVERAGE"], validate_vertical_slice(duplicated_event))

        duplicated_outcome = build_vertical_slice()
        duplicated_outcome["f9_outcomes"][1]["field_event_binding"]["event_id"] = duplicated_outcome["field_events"][0]["event_id"]
        self.assertEqual(["VERTICAL-OUTCOME-COVERAGE"], validate_vertical_slice(duplicated_outcome))

        premature = build_vertical_slice()
        premature["f9_outcomes"][0]["booking_at"] = "2026-08-01T10:00:00Z"
        premature["f9_outcomes"][0]["assessed_at"] = "2026-08-01T10:00:01Z"
        refresh_outcome_receipt(premature)
        self.assertEqual(["VERTICAL-OUTCOME-CHRONOLOGY"], validate_vertical_slice(premature))

        noncanonical = build_vertical_slice()
        noncanonical["route_manifest"]["route_manifest_id"] = "ROUTE:ALTERNATE"
        self.assertEqual(["VERTICAL-REPLAY-NONCANONICAL"], validate_vertical_slice(noncanonical))

        reordered = build_vertical_slice()
        reordered["field_events"].reverse()
        self.assertEqual(["VERTICAL-FIELD-COVERAGE"], validate_vertical_slice(reordered))

        malformed = build_vertical_slice()
        malformed["upstream_spine"]["math_decision"] = []
        self.assertEqual(["VERTICAL-SLICE-MALFORMED"], validate_vertical_slice(malformed))


if __name__ == "__main__":
    unittest.main()
