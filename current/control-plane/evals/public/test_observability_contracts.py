from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from cre_foundry.observability import lineage
from scripts.validate_observability_contracts import (
    build_report,
)


class ObservabilityContractTests(
    unittest.TestCase
):
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
        first = lineage.render_subject()
        second = lineage.render_subject()

        self.assertEqual(
            lineage.canonical_bytes(first),
            lineage.canonical_bytes(second),
        )
        self.assertEqual(
            lineage.lineage_checks(first),
            [],
        )

    def test_complete_nine_stage_chain(
        self,
    ) -> None:
        subject = lineage.render_subject()
        artifacts = subject[
            "decision"
        ]["artifacts"]

        self.assertEqual(
            [
                artifact["stage"]
                for artifact in artifacts
            ],
            list(lineage.REQUIRED_STAGES),
        )

        for index, artifact in enumerate(
            artifacts
        ):
            expected = (
                []
                if index == 0
                else [
                    artifacts[index - 1][
                        "artifact_id"
                    ]
                ]
            )

            self.assertEqual(
                artifact["parents"],
                expected,
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

    def test_replay_and_correlation(
        self,
    ) -> None:
        subject = lineage.render_subject()
        decision = subject["decision"]
        digest = (
            lineage.expected_replay_digest(
                decision
            )
        )

        self.assertEqual(
            decision["replay_identity"][
                "canonical_input_sha256"
            ],
            digest,
        )
        self.assertEqual(
            decision["replay_identity"][
                "replay_id"
            ],
            f"replay_{digest}",
        )

        self.assertTrue(
            all(
                event["correlation_id"]
                == decision["correlation_id"]
                for event in subject["logs"]
            )
        )

    def test_sensitive_logs_are_rejected(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            lineage.log_event(
                level="info",
                message="protected detail",
                correlation_id="run_obs_001",
                payload=["account_001"],
            )

        with self.assertRaises(ValueError):
            lineage.log_event(
                level="info",
                message="secret detail",
                correlation_id="run_obs_001",
                payload=["secret_test_value"],
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
