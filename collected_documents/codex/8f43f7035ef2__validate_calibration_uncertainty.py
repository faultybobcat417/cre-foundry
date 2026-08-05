#!/usr/bin/env python3
"""Autonomous-frontier compatibility entry point for CALIBRATION-001."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from evals.public.calibration_framework_evaluator import evaluate_registered_mutation
from scripts.validate_calibration_framework import main as validate_main


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--known-bad":
        path = ROOT / sys.argv[2]
        fixture = json.loads(path.read_text())
        case_id = fixture.get("case_id")
        mutation = {"aggregate-hides-subgroup": "pooled-subgroup-hides-cell", "point-estimate-only": "sparse-bin-point-estimate"}.get(case_id)
        errors = ["CALIBRATION-MUTATION-UNKNOWN"] if mutation is None else evaluate_registered_mutation(mutation)
        if not errors or errors == ["CALIBRATION-MUTATION-SURVIVED"]:
            return 1
        print(json.dumps({"result": "DETECTED", "case_id": case_id, "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "diagnostic": f"registered mutation detected: {case_id}"}, sort_keys=True))
        return 0
    if len(sys.argv) != 1:
        return 2
    result = validate_main()
    if result == 0:
        source = ROOT / "artifacts/evaluations/calibration_framework.json"
        target = ROOT / "artifacts/evaluations/calibration_synthetic.json"
        report = json.loads(source.read_text())
        report["artifact_id"] = "CALIBRATION-001-FRONTIER-COMPATIBILITY-EVALUATION"
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
