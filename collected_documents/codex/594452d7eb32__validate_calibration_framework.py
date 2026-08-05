#!/usr/bin/env python3
"""Validate and report CALIBRATION-001 public synthetic conformance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from evals.public.calibration_framework_evaluator import (
    BOUNDED_PROPERTY_GRID, CONTRACT_PATH, INPUT_PATH, INPUT_SCHEMA_PATH, MUTATION_DIAGNOSTICS, RUN_PATH,
    RUN_SCHEMA_PATH, evaluate, evaluate_bounded_property_grid, evaluate_registered_mutation, strict_load,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    try:
        frozen_input, run = strict_load(INPUT_PATH), strict_load(RUN_PATH)
        for value, schema_path in [(frozen_input, INPUT_SCHEMA_PATH), (run, RUN_SCHEMA_PATH)]:
            schema = strict_load(schema_path)
            Draft202012Validator.check_schema(schema)
            error = next(iter(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)), None)
            if error:
                return fail(f"schema violation: {error.message}")
    except (OSError, ValueError, TypeError) as exc:
        return fail(str(exc))
    errors = evaluate()
    if errors:
        return fail(errors[0])
    property_errors = evaluate_bounded_property_grid()
    if property_errors:
        return fail(f"CALIBRATION-PROPERTY-GRID:{property_errors[0]}")
    fixtures = [path for path in sorted((ROOT / "evals/known_bad/frontier").glob("calibration_*.json")) if strict_load(path).get("document_kind") == "REGISTERED_CALIBRATION_MUTATION"]
    if len(fixtures) != len(MUTATION_DIAGNOSTICS):
        return fail("CALIBRATION-MUTATION-REGISTRY-COVERAGE")
    results, seen = [], set()
    for path in fixtures:
        fixture = strict_load(path)
        case_id = fixture.get("case_id")
        if case_id in seen or MUTATION_DIAGNOSTICS.get(case_id) != fixture.get("expected_diagnostic"):
            return fail("CALIBRATION-MUTATION-REGISTRY-BINDING")
        seen.add(case_id)
        actual = evaluate_registered_mutation(case_id)
        if actual != [fixture["expected_diagnostic"]]:
            return fail(f"{case_id}: expected {fixture['expected_diagnostic']}, got {actual}")
        results.append({"case_id": case_id, "diagnostic": actual[0], "fixture_sha256": sha(path), "result": "DETECTED"})
    contract = strict_load(CONTRACT_PATH)
    if {row["case_id"]: row["diagnostic"] for row in contract["required_negative_controls"]} != MUTATION_DIAGNOSTICS:
        return fail("CALIBRATION-EVALUATOR-CONTRACT-MUTATION-MISMATCH")
    report = {
        "artifact_id": "CALIBRATION-001-PUBLIC-EVALUATION", "schema_version": "1.0.0", "evaluator_id": "calibration-framework-public-v1",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING", "result": "PASS", "proof_level": 5,
        "claim": "A separately registered synthetic probability head conforms to exact validation-fit, fixed-bin, missingness, subgroup, temporal, MATH, abstention, and replay mechanics.",
        "claim_ceiling": contract["claim_ceiling"], "registered_mutations_total": len(results), "registered_mutations_detected": len(results), "mutation_results": results,
        "bounded_property_grid": {"result": "PASS", "properties": BOUNDED_PROPERTY_GRID, "passed": len(BOUNDED_PROPERTY_GRID), "total": len(BOUNDED_PROPERTY_GRID)},
        "subjects": {"prediction_rows": len(run["prediction_ledger"]), "fit_bins": len(run["fit"]["cells"]), "test_route_days": len(run["math_runs"]), "scenarios": len(run["scenario_runs"])},
        "metrics": run["split_metrics"], "uncertainty": run["uncertainty"], "proof": run["proof"],
        "subject_hashes": {"artifacts/calibration/frozen_input.json": sha(INPUT_PATH), "artifacts/calibration/canonical_run.json": sha(RUN_PATH), "artifacts/calibration/public_evaluator_contract.json": sha(CONTRACT_PATH), "contracts/calibration_input.schema.json": sha(INPUT_SCHEMA_PATH), "contracts/calibration_evaluation.schema.json": sha(RUN_SCHEMA_PATH), "src/cre_foundry/calibration/framework.py": sha(ROOT / "src/cre_foundry/calibration/framework.py"), "evals/public/calibration_framework_evaluator.py": sha(ROOT / "evals/public/calibration_framework_evaluator.py"), "scripts/validate_calibration_framework.py": sha(Path(__file__))},
    }
    out = ROOT / "artifacts/evaluations/calibration_framework.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
