import copy
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cre_foundry.math.reference_oracle import InvalidDecisionProblem, decide
try:
    from evals.public.math_oracle_evaluator import evaluate as independent_decide, validate_route_decision
except ModuleNotFoundError:  # unittest discovery adds evals/public directly
    from math_oracle_evaluator import evaluate as independent_decide, validate_route_decision
from scripts.validate_math_contracts import derived_proof_level, validate_registry

PROBLEM_SCHEMA = json.loads((ROOT / "contracts/math_decision_policy.schema.json").read_text())
DECISION_SCHEMA = json.loads((ROOT / "contracts/math_route_decision.schema.json").read_text())
ESTIMAND_SCHEMA = json.loads((ROOT / "contracts/estimand_registry.schema.json").read_text())
AUTHORITY_SCHEMA = json.loads((ROOT / "contracts/math_authority_input.schema.json").read_text())


def candidate(index, **overrides):
    row = {
        "candidate_id": f"C{index:02d}", "physical_location_id": f"L{index:02d}",
        "grain_ids": {name: None for name in ["legal_entity_id", "operating_business_id", "brand_id", "establishment_id", "unit_id", "property_id", "parcel_id", "owner_id", "occupier_id", "parent_group_id"]},
        "protection_tokens": [], "evidence_stage": 1, "observed_at": "2026-08-01T12:00:00Z",
        "gates": {name: "PASS" for name in ["evidence", "identity", "eligibility", "safety", "access", "operational"]},
        "protected_status": "CLEAR", "value_state": "REGISTERED_SYNTHETIC_PROXY", "business_value_units": 100 - index,
        "proximity_cost_units": index, "service_minutes": 10, "composition_group": None,
    }
    row.update(overrides)
    return row


def problem(rows):
    return {
        "schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY", "decision_id": "D-TEST",
        "snapshot": {"snapshot_id": "S-1", "snapshot_sha256": "0" * 64, "stage1_cutoff": "2026-08-01T23:59:59Z", "issued_at": "2026-08-01T23:59:59Z", "protected_bundle_complete": True, "protected_tokens": []},
        "route_day": {"representative_id": "R-1", "route_date": "2026-08-02"},
        "policy": {"policy_version": "math-policy-v1", "policy_sha256": "1" * 64, "epsilon_business_value_units": 0, "maximum_candidates": 20, "max_total_service_minutes": 200, "composition_caps": {}, "required_unique_grains": [], "incompatible_candidate_pairs": [], "redundancy_penalties": [], "interference_penalties": []},
        "candidates": rows,
    }


def schema_errors(schema, value):
    return list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))


class MathContractTests(unittest.TestCase):
    def assert_conforms(self, value):
        self.assertEqual([], [error.message for error in schema_errors(DECISION_SCHEMA, value)])

    def test_schemas_and_estimand_registry(self):
        registry = json.loads((ROOT / "artifacts/math/estimand_registry.json").read_text())
        self.assertEqual([], [error.message for error in schema_errors(ESTIMAND_SCHEMA, registry)])
        self.assertEqual({"EST-F9-BASELINE-RATE", "EST-F9-BASELINE-VARIANCE", "EST-F9-ITT", "EST-PREDICTIVE-F9-RISK", "EST-POWER-SAMPLE-SIZE", "EST-RISK-ADJUSTED-NET-VALUE"}, {row["estimand_id"] for row in registry["estimands"]})
        self.assertIsNone(registry["power_result"]["estimate"])
        self.assertTrue(all(row["value"] is None for row in registry["inputs"]))
        authority = json.loads((ROOT / "artifacts/math/human_authority_input_template.json").read_text())
        self.assertEqual([], [error.message for error in schema_errors(AUTHORITY_SCHEMA, authority)])
        self.assertEqual("NOT_AN_INGESTION_INTERFACE", authority["ingestion_status"])

    def test_estimand_boundary_mutations_and_weakest_leaf_proof(self):
        registry = json.loads((ROOT / "artifacts/math/estimand_registry.json").read_text())
        relabeled = copy.deepcopy(registry)
        baseline = next(row for row in relabeled["inputs"] if row["input_id"] == "baseline_f9_rate")
        baseline["state"] = "symbolic"
        baseline["gate_id"] = None
        self.assertTrue(any("MATH-INPUT-BOUNDARY" in error for error in validate_registry(relabeled)))
        constant = copy.deepcopy(registry)
        power = next(row for row in constant["estimands"] if row["estimand_id"] == "EST-POWER-SAMPLE-SIZE")
        power["formula"]["expression"] = "12"
        self.assertIn("MATH-P08 decision estimand is undefined or conflated", validate_registry(constant))
        fabricated = copy.deepcopy(registry)
        baseline = next(row for row in fabricated["inputs"] if row["input_id"] == "baseline_f9_rate")
        baseline.update({"state": "measured", "value": 0.1, "proof_level": 2, "measurement": {"evidence_id": "FAKE", "artifact": "artifacts/math/not-real.json", "artifact_sha256": "0" * 64, "source_owner": "fake", "population": "fake", "window_start": "2026-01-01T00:00:00Z", "window_end": "2026-02-01T00:00:00Z", "sample_size": 1, "estimator_id": "fake", "uncertainty": {"method": "fake", "level": 0.95, "lower": 0, "upper": 1}, "proof_level": 2}})
        fabricated_errors = validate_registry(fabricated)
        self.assertEqual(["MATH-V1-FORMAL-ONLY: numeric evidence transitions require a later independently reviewed evidence-bound contract version"], fabricated_errors)
        wrong_dimensions = copy.deepcopy(registry)
        economics = next(row for row in wrong_dimensions["estimands"] if row["estimand_id"] == "EST-RISK-ADJUSTED-NET-VALUE")
        economics["scale"] = "probability"
        economics["formula"]["output_unit"] = "days"
        self.assertIn("MATH-P08 decision estimand is undefined or conflated", validate_registry(wrong_dimensions))
        missing_horizon = copy.deepcopy(registry)
        predictive = next(row for row in missing_horizon["estimands"] if row["estimand_id"] == "EST-PREDICTIVE-F9-RISK")
        predictive["time_window"] = None
        self.assertIn("MATH-P08 decision estimand is undefined or conflated", validate_registry(missing_horizon))
        leaves = {"a": {"value": 1, "proof_level": 4}, "b": {"value": 1, "proof_level": 2}}
        self.assertEqual(2, derived_proof_level({"a", "b"}, leaves, 4))
        self.assertEqual(0, derived_proof_level({"a", "missing"}, leaves, 4))

    def test_exactly_ten_or_abstain(self):
        issued = decide(problem([candidate(i) for i in range(10)]))
        self.assert_conforms(issued)
        self.assertEqual("ISSUE", issued["decision"])
        self.assertEqual(10, len(issued["selected"]))
        abstained = decide(problem([candidate(i) for i in range(9)]))
        self.assert_conforms(abstained)
        self.assertEqual("ABSTAIN_NO_VALID_TEN", abstained["decision"])
        bounded = decide(problem([candidate(i) for i in range(20)]))
        self.assertEqual([f"C{i:02d}" for i in range(10)], [row["candidate_id"] for row in bounded["selected"]])
        oversized = problem([candidate(i) for i in range(21)])
        self.assertTrue(schema_errors(PROBLEM_SCHEMA, oversized))
        with self.assertRaises(InvalidDecisionProblem):
            decide(oversized)

    def test_physical_uniqueness_and_protected_unknown(self):
        rows = [candidate(i) for i in range(10)]
        rows[-1]["physical_location_id"] = rows[-2]["physical_location_id"]
        self.assertEqual("ABSTAIN_NO_VALID_TEN", decide(problem(rows))["decision"])
        rows.append(candidate(10))
        result = decide(problem(rows))
        self.assertEqual("ISSUE", result["decision"])
        self.assertEqual(10, len({row["physical_location_id"] for row in result["selected"]}))
        rows[0]["protected_status"] = "UNKNOWN"
        self.assertNotIn("C00", {row["candidate_id"] for row in decide(problem(rows))["selected"]})
        alias_rows = [candidate(i) for i in range(11)]
        alias_rows[0]["protection_tokens"] = ["ALIAS:PROTECTED-GROUP"]
        alias_problem = problem(alias_rows)
        alias_problem["snapshot"]["protected_tokens"] = ["ALIAS:PROTECTED-GROUP"]
        self.assertNotIn("C00", {row["candidate_id"] for row in decide(alias_problem)["selected"]})
        valid_problem = problem([candidate(i) for i in range(10)])
        duplicate_output = decide(valid_problem)
        duplicate_output["selected"][-1]["physical_location_id"] = duplicate_output["selected"][-2]["physical_location_id"]
        self.assertEqual([], schema_errors(DECISION_SCHEMA, duplicate_output))
        self.assertTrue(any("physical-location" in error for error in validate_route_decision(valid_problem, duplicate_output)))

    def test_stage_isolation_and_unknown_value(self):
        rows = [candidate(i) for i in range(10)]
        rows[-1]["observed_at"] = "2026-08-02T00:00:00Z"
        self.assertEqual("ABSTAIN_NO_VALID_TEN", decide(problem(rows))["decision"])
        rows[-1]["observed_at"] = "2026-08-01T12:00:00Z"
        rows[-1]["value_state"] = "UNKNOWN"
        rows[-1]["business_value_units"] = None
        result = decide(problem(rows))
        self.assertEqual("UNRESOLVED_VALUE_COULD_DOMINATE", result["reason"])
        too_few = rows[:9]
        self.assertEqual("NO_FEASIBLE_TEN", decide(problem(too_few))["reason"])
        measured = [candidate(i) for i in range(10)]
        impossible_unknown = candidate(10, value_state="UNKNOWN", business_value_units=None, service_minutes=201)
        resolved = decide(problem(measured + [impossible_unknown]))
        self.assertEqual("ISSUE", resolved["decision"])
        self.assertNotIn("C10", {row["candidate_id"] for row in resolved["selected"]})

    def test_joint_feasibility_and_composition(self):
        rows = [candidate(i, composition_group="A") for i in range(10)]
        instance = problem(rows)
        instance["policy"]["composition_caps"] = {"A": 9}
        self.assertEqual("ABSTAIN_NO_VALID_TEN", decide(instance)["decision"])
        instance["policy"]["composition_caps"] = {}
        instance["policy"]["max_total_service_minutes"] = 99
        self.assertEqual("ABSTAIN_NO_VALID_TEN", decide(instance)["decision"])
        grains = [candidate(i) for i in range(11)]
        for i, row in enumerate(grains):
            row["grain_ids"]["brand_id"] = f"B{i:02d}"
        grains[9]["grain_ids"]["brand_id"] = "B08"
        grain_problem = problem(grains)
        grain_problem["policy"]["required_unique_grains"] = ["brand_id"]
        self.assertNotIn("C09", {row["candidate_id"] for row in decide(grain_problem)["selected"]})
        penalty_problem = problem([candidate(i) for i in range(11)])
        penalty_problem["policy"]["redundancy_penalties"] = [{"candidate_pair": ["C00", "C01"], "penalty_units": 1000}]
        self.assertNotEqual({"C00", "C01"}, {"C00", "C01"} & {row["candidate_id"] for row in decide(penalty_problem)["selected"]})

    def test_value_before_proximity_and_canonical_tie(self):
        anchors = [candidate(i, business_value_units=90, proximity_cost_units=0) for i in range(9)]
        alternatives = [candidate(9, business_value_units=190, proximity_cost_units=100), candidate(10, business_value_units=90, proximity_cost_units=2), candidate(11, business_value_units=89, proximity_cost_units=1)]
        instance = problem(anchors + alternatives)
        instance["policy"]["incompatible_candidate_pairs"] = [["C09", "C10"], ["C09", "C11"], ["C10", "C11"]]
        result = decide(instance)
        self.assertIn("C09", {row["candidate_id"] for row in result["selected"]})
        tied = problem([candidate(i, business_value_units=10, proximity_cost_units=1) for i in range(11)])
        self.assertEqual(tuple(f"C{i:02d}" for i in range(10)), tuple(row["candidate_id"] for row in decide(tied)["selected"]))

    def test_permutation_and_independent_differential(self):
        rng = random.Random(20260802)
        domains = 0
        for size in range(10, 15):
            for iteration in range(8):
                rows = [candidate(i, business_value_units=rng.randint(-50, 150), proximity_cost_units=rng.randint(0, 30), service_minutes=rng.randint(1, 20), composition_group=rng.choice([None, "A", "B"])) for i in range(size)]
                for row in rows:
                    if rng.random() < 0.12:
                        row["protected_status"] = rng.choice(["PROTECTED", "UNKNOWN"])
                    if rng.random() < 0.1:
                        row["gates"]["eligibility"] = rng.choice(["FAIL", "UNKNOWN"])
                    if rng.random() < 0.08:
                        row["value_state"] = "UNKNOWN"
                        row["business_value_units"] = None
                    if rng.random() < 0.08:
                        row["observed_at"] = "2026-08-02T00:00:00Z"
                    if row["candidate_id"] != "C00" and rng.random() < 0.08:
                        row["physical_location_id"] = "L00"
                instance = problem(rows)
                instance["policy"]["composition_caps"] = {"A": 6, "B": 7}
                candidate_ids = [row["candidate_id"] for row in rows]
                if len(candidate_ids) >= 2 and rng.random() < 0.5:
                    pair = sorted(rng.sample(candidate_ids, 2))
                    instance["policy"]["incompatible_candidate_pairs"] = [pair]
                if len(candidate_ids) >= 2 and rng.random() < 0.5:
                    pair = sorted(rng.sample(candidate_ids, 2))
                    instance["policy"]["interference_penalties"] = [{"candidate_pair": pair, "penalty_units": rng.randint(1, 80)}]
                expected = independent_decide(instance)
                self.assertEqual(expected, decide(instance))
                shuffled = copy.deepcopy(instance)
                rng.shuffle(shuffled["candidates"])
                self.assertEqual(expected, decide(shuffled))
                domains += 1
        self.assertEqual(40, domains)

    def test_invalid_input_is_not_business_abstention(self):
        instance = problem([candidate(i) for i in range(10)])
        instance["candidates"][1]["candidate_id"] = "C00"
        with self.assertRaises(InvalidDecisionProblem):
            decide(instance)
        future_cutoff = problem([candidate(i) for i in range(10)])
        future_cutoff["snapshot"]["stage1_cutoff"] = "2027-01-02T00:00:00Z"
        with self.assertRaises(InvalidDecisionProblem):
            decide(future_cutoff)
        stage_two = problem([candidate(i) for i in range(10)])
        stage_two["candidates"][0]["evidence_stage"] = 2
        with self.assertRaises(InvalidDecisionProblem):
            decide(stage_two)

    def run_mutant(self, relative, instance):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "problem.json"
            path.write_text(json.dumps(instance))
            proc = subprocess.run([sys.executable, str(ROOT / relative), "--input", str(path)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            return json.loads(proc.stdout)

    def assert_mutant_killed(self, relative, instance):
        actual = self.run_mutant(relative, instance)
        expected = independent_decide(instance)
        self.assertTrue(validate_route_decision(instance, actual) or actual != expected, relative)

    def test_all_registered_negative_controls_fail(self):
        self.assert_mutant_killed("evals/known_bad/math/issue_nine.py", problem([candidate(i) for i in range(9)]))
        protected = [candidate(i) for i in range(10)]
        protected[-1]["protection_tokens"] = ["ALIAS:PROTECTED-GROUP"]
        protected_problem = problem(protected)
        protected_problem["snapshot"]["protected_tokens"] = ["ALIAS:PROTECTED-GROUP"]
        self.assert_mutant_killed("evals/known_bad/math/fill_with_protected_alias.py", protected_problem)
        duplicate = [candidate(i) for i in range(10)]
        duplicate[-1]["physical_location_id"] = duplicate[-2]["physical_location_id"]
        self.assert_mutant_killed("evals/known_bad/math/collapse_duplicate_physical_locations.py", problem(duplicate))
        future = [candidate(i) for i in range(10)]
        future[-1]["observed_at"] = "2026-08-02T00:00:00Z"
        self.assert_mutant_killed("evals/known_bad/math/use_stage2_field_observation.py", problem(future))
        anchors = [candidate(i, business_value_units=90, proximity_cost_units=0) for i in range(9)]
        alternatives = [candidate(9, business_value_units=190, proximity_cost_units=100), candidate(10, business_value_units=90, proximity_cost_units=2), candidate(11, business_value_units=89, proximity_cost_units=1)]
        proximity = problem(anchors + alternatives)
        proximity["policy"]["incompatible_candidate_pairs"] = [["C09", "C10"], ["C09", "C11"], ["C10", "C11"]]
        self.assert_mutant_killed("evals/known_bad/math/prefer_proximity_below_value_floor.py", proximity)
        permutation = problem([candidate(10, business_value_units=-100)] + [candidate(i) for i in range(10)])
        self.assert_mutant_killed("evals/known_bad/math/permutation_sensitive.py", permutation)
        greedy = problem([candidate(i, business_value_units=100 - i) for i in range(12)])
        greedy["policy"]["incompatible_candidate_pairs"] = [["C00", "C01"]]
        self.assert_mutant_killed("evals/known_bad/math/greedy_individual_value.py", greedy)
        for fixture in (
            "math_undefined_estimand.json",
            "math_hardcoded_power.json",
            "math_scenario_as_measured.json",
            "exact_ten_wrong_cardinality.json",
            "exact_ten_protected_fill.json",
        ):
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate_math_contracts.py"), "--known-bad", f"evals/known_bad/frontier/{fixture}"],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual("DETECTED", json.loads(proc.stdout)["result"])


if __name__ == "__main__":
    unittest.main()
