"""Read-only CONTRACT-001 validator and registered mutation runner."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.contracts.thin_slice import build_spine
from evals.public.contract_spine_evaluator import validate_spine

ARTIFACT = ROOT / "artifacts/contracts/contract_spine.json"
REPORT = ROOT / "artifacts/evaluations/contract_spine.json"
EVALUATOR_CONTRACT = ROOT / "artifacts/contracts/public_evaluator_contract.json"
KNOWN_BAD_PATHS = sorted((ROOT / "evals/known_bad/frontier").glob("contract_*.json"))
REPORT_SUBJECTS = {
    "contracts/thin_slice_observation.schema.json",
    "contracts/thin_slice_candidate.schema.json",
    "src/cre_foundry/contracts/thin_slice.py",
    "evals/public/contract_spine_evaluator.py",
    "evals/public/test_contract_spine.py",
    "scripts/validate_contract_spine.py",
    "artifacts/contracts/contract_spine.json",
    "artifacts/contracts/public_evaluator_contract.json",
}
REPORT_FIELDS = {
    "artifact_id", "schema_version", "decision_scope", "result", "proof_level", "evaluator_id",
    "tests", "commands", "subject_hashes", "mutation_results", "claim", "claim_ceiling",
}
EXPECTED_REPORT_TESTS = {
    "public_test_cases": 5,
    "registered_mutations_detected": 5,
    "registered_mutations_total": 5,
    "full_public_suite_tests": 49,
}
EXPECTED_REPORT_COMMANDS = [
    {"argv": ["python", "scripts/validate_contract_spine.py"], "exit_code": 0, "stdout": "PASS"},
    {"argv": ["python", "-m", "unittest", "discover", "-s", "evals/public", "-p", "test_*.py"], "exit_code": 0, "result": "49 tests passed"},
]
SUMMARY_FIELDS = [
    "document_kind", "schema_version", "decision_scope", "contract_id",
    "canonicalization", "normalizer_version", "adapter_version", "adapter_sha256",
    "supported_version_transition", "schema_bindings", "source_snapshot_sha256",
    "candidate_snapshot_sha256", "replay_receipt", "proof",
]


def strict_load(path: Path):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_summary(spine: dict) -> dict:
    return {field: spine[field] for field in SUMMARY_FIELDS}


def validate() -> list[str]:
    spine = build_spine()
    errors = validate_spine(spine, check_replay=True)
    if strict_load(ARTIFACT) != artifact_summary(spine):
        errors.append("CONTRACT-ARTIFACT-REPLAY-MISMATCH")
    process = subprocess.run(
        [sys.executable, "-m", "unittest", "evals.public.test_contract_spine"],
        cwd=ROOT, text=True, capture_output=True, timeout=30,
    )
    if process.returncode != 0:
        errors.append("CONTRACT-PUBLIC-TESTS")
    evaluator_contract = strict_load(EVALUATOR_CONTRACT)
    registered = {row["mutation_id"]: row["expected_diagnostic"] for row in evaluator_contract.get("registered_mutations", [])}
    recipes = []
    for path in KNOWN_BAD_PATHS:
        recipe = strict_load(path)
        recipes.append(recipe)
        if registered.get(recipe.get("mutation_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"CONTRACT-MUTATION-REGISTRY:{recipe.get('case_id')}")
        code, payload = run_known_bad(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"CONTRACT-MUTATION-SURVIVED:{recipe.get('case_id')}")
    if set(registered) != {row.get("mutation_id") for row in recipes} or len(recipes) != 5:
        errors.append("CONTRACT-MUTATION-COVERAGE")
    report = strict_load(REPORT)
    if set(report) != REPORT_FIELDS or (
        report.get("artifact_id") != "CONTRACT-001-PUBLIC-EVALUATION"
        or report.get("schema_version") != "1.0.0"
        or report.get("decision_scope") != "SYNTHETIC_FORMAL_ONLY"
        or report.get("result") != "PASS"
        or report.get("proof_level") != 4
        or report.get("evaluator_id") != "contract-spine-public-v1"
        or report.get("tests") != EXPECTED_REPORT_TESTS
        or report.get("commands") != EXPECTED_REPORT_COMMANDS
        or report.get("claim") != "The bounded synthetic contract spine conforms to its strict public schemas and deterministic replay semantics."
        or report.get("claim_ceiling") != "No real source, identity, protection, value, route-feasibility, empirical, or live-use claim is established."
    ):
        errors.append("CONTRACT-REPORT-CLAIM")
    subject_hashes = report.get("subject_hashes", {})
    if set(subject_hashes) != REPORT_SUBJECTS:
        errors.append("CONTRACT-REPORT-SUBJECT-COVERAGE")
    else:
        for relative, expected_sha in subject_hashes.items():
            if file_sha256(ROOT / relative) != expected_sha:
                errors.append(f"CONTRACT-REPORT-SUBJECT-DIGEST:{relative}")
    mutation_results = {row.get("case_id"): row for row in report.get("mutation_results", [])}
    if set(mutation_results) != {row.get("case_id") for row in recipes}:
        errors.append("CONTRACT-REPORT-MUTATION-COVERAGE")
    else:
        for recipe, path in zip(recipes, KNOWN_BAD_PATHS):
            row = mutation_results[recipe["case_id"]]
            if row != {"case_id": recipe["case_id"], "diagnostic": recipe["expected_diagnostic"], "fixture_sha256": file_sha256(path), "result": "DETECTED"}:
                errors.append(f"CONTRACT-REPORT-MUTATION:{recipe['case_id']}")
    return sorted(set(errors))


def apply_mutation(spine: dict, mutation_id: str) -> None:
    if mutation_id == "future_observation_accepted":
        spine["observations"][0]["clocks"]["available_at"] = "2026-08-01T00:00:00Z"
    elif mutation_id == "brand_collapsed_into_physical_location":
        spine["candidates"][0]["identity"]["grain_ids"]["brand_id"] = spine["candidates"][0]["identity"]["physical_location_id"]
    elif mutation_id == "protected_alias_omitted":
        spine["candidates"][0]["protection"]["candidate_tokens"] = spine["candidates"][0]["protection"]["candidate_tokens"][:-1]
    elif mutation_id == "decision_digest_mismatch":
        spine["replay_receipt"]["math_decision_sha256"] = "0" * 64
    elif mutation_id == "schema_version_silently_upgraded":
        spine["observations"][0]["schema_version"] = "9.9.9"
    else:
        raise ValueError("unsupported mutation recipe")


def run_known_bad(path: Path) -> tuple[int, dict]:
    recipe = strict_load(path)
    spine = build_spine()
    apply_mutation(spine, recipe["mutation_id"])
    diagnostics = validate_spine(spine)
    detected = diagnostics == [recipe["expected_diagnostic"]]
    payload = {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": recipe["case_id"],
        "fixture_sha256": file_sha256(path),
        "diagnostic": diagnostics[0] if len(diagnostics) == 1 else "unexpected diagnostics",
    }
    return (0 if detected else 1), payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()
    if args.known_bad:
        path = args.known_bad if args.known_bad.is_absolute() else ROOT / args.known_bad
        try:
            code, payload = run_known_bad(path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            code, payload = 1, {"result": "SURVIVED", "case_id": "invalid", "fixture_sha256": file_sha256(path) if path.is_file() else "", "diagnostic": str(exc)}
        print(json.dumps(payload, sort_keys=True))
        return code
    try:
        errors = validate()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors = ["CONTRACT-VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
