from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from cre_foundry.replay import recovery
from scripts.validate_replay_contracts import (
    build_report,
)


class ReplayContractTests(unittest.TestCase):
    def test_house_report_passes(self) -> None:
        report = build_report()

        self.assertTrue(report["passed"])
        self.assertEqual(
            report["result"],
            "PASS",
        )
        self.assertEqual(
            report["proof_level"],
            4,
        )

    def test_clean_subject_is_deterministic(
        self,
    ) -> None:
        first = recovery.render_subject()
        second = recovery.render_subject()

        self.assertEqual(
            recovery.canonical_bytes(first),
            recovery.canonical_bytes(second),
        )
        self.assertEqual(
            recovery.recovery_checks(first),
            [],
        )
        self.assertEqual(
            first["original_output_sha256"],
            first["replay_output_sha256"],
        )

    def test_idempotent_retry_and_conflict(
        self,
    ) -> None:
        ledger: list[dict] = []
        payload = recovery.deterministic_output(
            recovery.synthetic_input()
        )

        first, created_first = (
            recovery.execute_idempotent_effect(
                ledger,
                idempotency_key="IDEM-TEST-001",
                payload=payload,
            )
        )

        second, created_second = (
            recovery.execute_idempotent_effect(
                ledger,
                idempotency_key="IDEM-TEST-001",
                payload=copy.deepcopy(payload),
            )
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first, second)
        self.assertEqual(len(ledger), 1)

        with self.assertRaises(ValueError):
            recovery.execute_idempotent_effect(
                ledger,
                idempotency_key="IDEM-TEST-001",
                payload={"different": True},
            )

    def test_partial_crash_recovery(
        self,
    ) -> None:
        subject = recovery.render_subject()

        result = recovery.recover_journal(
            journal_state="PREPARED",
            expected_output_sha256=(
                subject[
                    "original_output_sha256"
                ]
            ),
        )

        self.assertEqual(
            result["journal_state"],
            "COMMITTED",
        )
        self.assertFalse(
            result["partial_state_accepted"]
        )
        self.assertTrue(result["resumed"])

    def test_restore_and_rollback(
        self,
    ) -> None:
        subject = recovery.render_subject()

        self.assertTrue(
            subject["restore"]["verified"]
        )
        self.assertEqual(
            subject["restore"]["backup_sha256"],
            subject["restore"][
                "restored_sha256"
            ],
        )
        self.assertTrue(
            subject["rollback"]["verified"]
        )
        self.assertEqual(
            subject["rollback"][
                "restored_version"
            ],
            subject["rollback"][
                "prior_version"
            ],
        )

    def test_all_mutations_detected_both(
        self,
    ) -> None:
        report = build_report()

        self.assertEqual(
            report[
                "registered_mutation_count"
            ],
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
                row["result"]
                == "DETECTED_BOTH"
                for row in report[
                    "mutation_results"
                ]
            )
        )

    def test_report_is_byte_stable(
        self,
    ) -> None:
        self.assertEqual(
            build_report(),
            build_report(),
        )


if __name__ == "__main__":
    unittest.main()
