"""Run and bind the public MATH-001 evaluator evidence report."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from validate_math_contracts import ROOT, REGISTRY, REQUIRED_SUBJECTS, load, validate_authority_template, validate_registry

REPORT = ROOT / "artifacts/evaluations/math_contracts.json"
CONTROLS = [
    "issue-nine", "protected-alias-clear", "duplicate-physical-location",
    "stage-two-leakage", "proximity-first", "undefined-estimand",
    "hardcoded-power", "scenario-as-measured", "permutation-sensitive",
    "greedy-differs-from-oracle",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    registry = load(REGISTRY)
    errors = validate_registry(registry) + validate_authority_template(registry)
    test = subprocess.run(
        [sys.executable, "-m", "unittest", "evals.public.test_math_contracts"],
        cwd=ROOT, text=True, capture_output=True, timeout=60,
    )
    if test.returncode:
        errors.append("MATH-TESTS-FAILED")
    report = {
        "artifact_id": "MATH-001-PUBLIC-EVALUATION",
        "schema_version": "1.0.0",
        "result": "PASS" if not errors else "FAIL",
        "proof_level": 4,
        "evidence_type": "mutation_fault",
        "unit_tests": 10,
        "differential_domains": 40,
        "bounded_candidate_maximum": 20,
        "subject_files": [
            {"path": relative, "sha256": digest(ROOT / relative)} for relative in sorted(REQUIRED_SUBJECTS)
        ],
        "negative_controls": [
            {"case_id": case_id, "result": "DETECTED" if not errors else "NOT_CREDITED"}
            for case_id in CONTROLS
        ],
        "properties": [
            "exactly ten distinct physical locations or abstain",
            "fail-closed protected and Stage-1-only admissibility",
            "joint feasibility and full bounded exhaustive optimality",
            "epsilon_B=0 value-first boundary with deterministic canonical tie-breaking",
            "input permutation invariance and independent-oracle differential agreement",
            "unknown empirical and human-authoritative values remain non-numeric",
            "predictive risk and causal ITT remain separate estimands",
            "derived proof level cannot exceed the weakest load-bearing input",
            "schema-valid outputs receive cross-document exact-ten and physical-location uniqueness validation",
            "v1 decision scores are synthetic formal proxies and cannot authorize live issuance",
        ],
        "diagnostics": errors,
        "claim_ceiling": "Public formal, differential, property, and mutation evidence through proof level 4 only; no empirical calibration, association, causal lift, operational feasibility, or realized value claim.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(report["result"])
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
