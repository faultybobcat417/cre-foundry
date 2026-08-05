#!/usr/bin/env python3
"""Autonomous-frontier compatibility entry point for BASELINE-001."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from evals.public.baseline_framework_evaluator import evaluate_registered_mutation
from scripts.validate_baseline_framework import main as validate_main


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--known-bad":
        path = ROOT / sys.argv[2]
        fixture = json.loads(path.read_text())
        case_id = fixture.get("case_id")
        mutation = {"missing-baselines": "missing-required-policy", "future-feature": "future-feature"}.get(case_id)
        errors = ["BASELINE-MUTATION-UNKNOWN"] if mutation is None else evaluate_registered_mutation(mutation)
        if not errors or errors == ["BASELINE-MUTATION-SURVIVED"]:
            return 1
        payload = {
            "result": "DETECTED",
            "case_id": case_id,
            "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "diagnostic": f"registered mutation detected: {case_id}",
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    if len(sys.argv) != 1:
        return 2
    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
