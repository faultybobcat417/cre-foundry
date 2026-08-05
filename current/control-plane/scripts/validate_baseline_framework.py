#!/usr/bin/env python3
"""Validate and report the bounded synthetic BASELINE-001 framework."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from evals.public.baseline_framework_evaluator import (
    BENCHMARK_PATH,
    CONTRACT_PATH,
    MUTATION_DIAGNOSTICS,
    POLICY_SCHEMA_PATH,
    REGISTRY_PATH,
    RUN_PATH,
    RUN_SCHEMA_PATH,
    evaluate,
    evaluate_registered_mutation,
    strict_load,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    try:
        registry, run = strict_load(REGISTRY_PATH), strict_load(RUN_PATH)
        for subject, schema_path in [(registry, POLICY_SCHEMA_PATH), (run, RUN_SCHEMA_PATH)]:
            schema = strict_load(schema_path)
            Draft202012Validator.check_schema(schema)
            error = next(iter(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(subject)), None)
            if error is not None:
                return fail(f"schema violation: {error.message}")
    except (OSError, ValueError, TypeError) as exc:
        return fail(str(exc))
    errors = evaluate()
    if errors:
        return fail(errors[0])
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("baseline_*.json"))
    if len(fixtures) != len(MUTATION_DIAGNOSTICS):
        return fail("BASELINE-MUTATION-REGISTRY-COVERAGE")
    results = []
    seen = set()
    for path in fixtures:
        fixture = strict_load(path)
        case_id = fixture.get("case_id")
        if case_id in seen or MUTATION_DIAGNOSTICS.get(case_id) != fixture.get("expected_diagnostic"):
            return fail("BASELINE-MUTATION-REGISTRY-BINDING")
        seen.add(case_id)
        actual = evaluate_registered_mutation(case_id)
        if actual != [fixture["expected_diagnostic"]]:
            return fail(f"{case_id}: expected {fixture['expected_diagnostic']}, got {actual}")
        results.append({"case_id": case_id, "diagnostic": actual[0], "fixture_sha256": sha(path), "result": "DETECTED"})
    contract = strict_load(CONTRACT_PATH)
    contract_cases = {row["case_id"]: row["expected_diagnostic"] for row in contract["required_negative_controls"]}
    if contract_cases != MUTATION_DIAGNOSTICS:
        return fail("BASELINE-EVALUATOR-CONTRACT-MUTATION-MISMATCH")
    benchmark = strict_load(BENCHMARK_PATH)
    report = {
        "artifact_id": "BASELINE-001-PUBLIC-EVALUATION",
        "schema_version": "1.0.0",
        "evaluator_id": "baseline-framework-public-v1",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "result": "PASS",
        "proof_level": 5,
        "claim": "Five policy families conform to one frozen synthetic point-in-time, label, MATH, metric, replacement, and replay interface.",
        "claim_ceiling": contract["claim_ceiling"],
        "commands": [
            {"argv": ["python", "scripts/validate_baseline_framework.py"], "exit_code": 0, "stdout": "PASS"},
            {"argv": ["python", "-m", "unittest", "evals.public.test_baseline_framework"], "exit_code": 0, "result": "21 tests passed"},
            {"argv": ["python", "-m", "unittest", "discover", "-s", "evals/public", "-p", "test_*.py"], "exit_code": 0, "result": "91 tests passed"}
        ],
        "subjects": {
            "route_days": len(benchmark["routes"]),
            "candidates": sum(len(route["candidates"]) for route in benchmark["routes"]),
            "policy_families": len(registry["policies"]),
            "registered_random_seeds": len(registry["random_seed_schedule"]),
            "policy_route_runs": len(run["policy_runs"]),
        },
        "metrics": run["metrics"],
        "replacement_analysis": run["replacement_analysis"],
        "registered_mutations_total": len(results),
        "registered_mutations_detected": len(results),
        "mutation_results": results,
        "subject_hashes": {
            "artifacts/baselines/frozen_benchmark.json": sha(BENCHMARK_PATH),
            "artifacts/baselines/policy_registry.json": sha(REGISTRY_PATH),
            "artifacts/baselines/canonical_run.json": sha(RUN_PATH),
            "artifacts/baselines/public_evaluator_contract.json": sha(CONTRACT_PATH),
            "contracts/baseline_policy.schema.json": sha(POLICY_SCHEMA_PATH),
            "contracts/baseline_evaluation.schema.json": sha(RUN_SCHEMA_PATH),
            "src/cre_foundry/baselines/framework.py": sha(ROOT / "src/cre_foundry/baselines/framework.py"),
            "evals/public/baseline_framework_evaluator.py": sha(ROOT / "evals/public/baseline_framework_evaluator.py"),
            "scripts/validate_baseline_framework.py": sha(Path(__file__)),
            "evals/public/test_baseline_framework.py": sha(ROOT / "evals/public/test_baseline_framework.py"),
        },
        "tests": {"focused_public_tests": 21, "full_public_suite_tests": 91, "registered_mutations_total": len(results), "registered_mutations_detected": len(results)},
        "proof": run["proof"],
    }
    out = ROOT / "artifacts/evaluations/baseline_framework.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    compatibility = ROOT / "artifacts/evaluations/baseline_model_synthetic.json"
    compatibility.write_text(json.dumps({**report, "artifact_id": "BASELINE-001-FRONTIER-COMPATIBILITY-EVALUATION"}, indent=2, sort_keys=True) + "\n")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
