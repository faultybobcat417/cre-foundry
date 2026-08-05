from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from cre_foundry.security import posture
from scripts.validate_security_contracts import (
    build_report,
)


class SecurityContractTests(unittest.TestCase):
    def test_house_report_passes(self) -> None:
        report = build_report()

        self.assertTrue(report["passed"])
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["proof_level"], 4)

    def test_clean_subject_is_deterministic(self) -> None:
        first = posture.render_subject()
        second = posture.render_subject()

        self.assertEqual(
            posture.canonical_bytes(first),
            posture.canonical_bytes(second),
        )
        self.assertEqual(
            posture.material_checks(first),
            [],
        )

    def test_all_seven_mutations_detected_both(
        self,
    ) -> None:
        report = build_report()

        self.assertEqual(
            report["registered_mutation_count"],
            7,
        )
        self.assertEqual(
            report[
                "registered_mutations_detected"
            ],
            7,
        )

        self.assertTrue(
            all(
                row["result"] == "DETECTED_BOTH"
                for row in report[
                    "mutation_results"
                ]
            )
        )

    def test_negative_authorization_fails_closed(
        self,
    ) -> None:
        for decision in [
            posture.authorization_decision(
                target="synthetic-crm",
                authorized=False,
                live_permissions=True,
            ),
            posture.authorization_decision(
                target="synthetic-crm",
                authorized=True,
                live_permissions=False,
            ),
            posture.authorization_decision(
                target="synthetic-crm",
                authorized=True,
                live_permissions=True,
                authority_source="retrieved-content",
            ),
        ]:
            self.assertEqual(
                decision["decision"],
                "DENY",
            )
            self.assertFalse(
                decision["executed"]
            )

    def test_restricted_logs_are_rejected(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            posture.log_event(
                "info",
                "synthetic secret",
                ["secret_test_credential"],
            )

        with self.assertRaises(ValueError):
            posture.log_event(
                "info",
                "synthetic protected record",
                ["account_001"],
            )

    def test_report_is_byte_stable(self) -> None:
        first = build_report()
        second = build_report()

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
