import unittest
from pathlib import Path

from route_decision_evaluator import evaluate, run


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals/public/fixtures/protected_alias_exact_ten.json"
TEN_VALID = ROOT / "evals/public/fixtures/ten_valid.json"


class RouteDecisionEvaluatorTest(unittest.TestCase):
    def test_reference_passes(self):
        errors = run(ROOT / "evals/reference/fail_closed_reference.py", FIXTURE)
        self.assertEqual([], errors)

    def test_known_bad_is_rejected(self):
        errors = run(ROOT / "evals/known_bad/exact_name_only_clearance.py", FIXTURE)
        self.assertIn("INV-004 protected or ineligible location cleared", errors)
        self.assertIn("INV-001 fewer than ten valid locations must abstain", errors)

    def test_always_abstain_is_rejected(self):
        errors = run(ROOT / "evals/known_bad/always_abstain.py", TEN_VALID)
        self.assertEqual(
            ["INV-001 fully valid conformance fixture must issue exactly ten locations"],
            errors,
        )

    def test_missing_abstention_reason_is_contract_error(self):
        fixture = {"candidates": []}
        errors = evaluate(fixture, {"decision": "ABSTAIN_NO_VALID_TEN", "locations": []})
        self.assertTrue(errors[0].startswith("CONTRACT route decision:"))

    def test_extra_issue_property_is_contract_error(self):
        fixture = {
            "candidates": [
                {"location_id": f"V{i:02d}", "eligible": True, "protected_match": False}
                for i in range(1, 11)
            ]
        }
        decision = {
            "decision": "ISSUE",
            "locations": [f"V{i:02d}" for i in range(1, 11)],
            "unexpected": True,
        }
        errors = evaluate(fixture, decision)
        self.assertTrue(errors[0].startswith("CONTRACT route decision:"))


if __name__ == "__main__":
    unittest.main()
