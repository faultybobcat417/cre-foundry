"""Regenerate the frontier meta evidence (AUTONOMOUS-FRONTIER-META-001).

Runs the autonomous-frontier evaluator self-tests and pins the covered
repository paths to the current HEAD so the meta test can verify that current,
recorded, and committed hashes agree.  Run only from a clean, committed working
tree; commit the regenerated artifact as a follow-up checkpoint.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/evaluations/autonomous_frontier_meta.json"
COVERED_PATHS = [
    "scripts/evaluate_autonomous_frontier.py",
    "contracts/autonomous_frontier_contract.schema.json",
    "control/AUTONOMOUS_FRONTIER_CONTRACT.json",
    "evals/public/test_autonomous_frontier.py",
    "scripts/validate_mission_integrity.py",
    "scripts/validate_frontier_meta.py",
    "scripts/prove_known_bad_fails.py",
]

CLAIM_CEILING = (
    "Mutation-resistant public frontier-evaluator mechanics; not evidence that domain "
    "gates pass or that sealed/hidden independence exists."
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from evals.public import test_autonomous_frontier as module  # noqa: PLC0415

    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    tests = [
        (test.shortDescription() or test._testMethodName)
        for test in suite
        if isinstance(test, unittest.TestCase)
    ]
    payload = {
        "artifact_id": "AUTONOMOUS-FRONTIER-META-001",
        "subject_commit": _git_head(),
        "covered_paths": [
            {"path": relative, "sha256": _file_sha256(ROOT / relative)} for relative in COVERED_PATHS
        ],
        "command": "python evals/public/test_autonomous_frontier.py",
        "exit_code": 0 if result.wasSuccessful() else 1,
        "tests_run": result.testsRun,
        "tests_passed": result.testsRun - len(result.failures) - len(result.errors),
        "tests": tests,
        "proof_level": 4,
        "claim_ceiling": CLAIM_CEILING,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT} subject_commit={payload['subject_commit']} tests={payload['tests_run']}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
