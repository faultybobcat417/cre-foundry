"""Read-only VERTICAL-001 validator and declarative mutation runner."""
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

from cre_foundry.vertical.shadow_slice import build_vertical_slice
from evals.public.vertical_slice_evaluator import validate_vertical_slice

MANIFEST = ROOT / "artifacts/vertical-slice/run_manifest.json"
REPORT = ROOT / "artifacts/evaluations/vertical_slice.json"
EVALUATOR_CONTRACT = ROOT / "artifacts/vertical/public_evaluator_contract.json"
KNOWN_BAD_PATHS = sorted((ROOT / "evals/known_bad/frontier").glob("vertical_*.json"))
REPORT_SUBJECTS = {
    "contracts/synthetic_route_day.schema.json",
    "contracts/synthetic_field_event.schema.json",
    "contracts/synthetic_f9_outcome.schema.json",
    "src/cre_foundry/vertical/shadow_slice.py",
    "evals/public/vertical_slice_evaluator.py",
    "evals/public/test_vertical_slice.py",
    "scripts/validate_vertical_slice.py",
    "artifacts/vertical-slice/run_manifest.json",
    "artifacts/vertical/public_evaluator_contract.json",
}
REPORT_FIELDS = {
    "artifact_id", "schema_version", "execution_scope", "result", "proof_level", "evaluator_id",
    "tests", "commands", "subject_hashes", "mutation_results", "claim", "claim_ceiling",
}
EXPECTED_TESTS = {
    "public_test_cases": 7,
    "bounded_input_sizes": 20,
    "registered_mutations_detected": 7,
    "registered_mutations_total": 7,
    "full_public_suite_tests": 56,
}
EXPECTED_COMMANDS = [
    {"argv": ["python", "scripts/validate_vertical_slice.py"], "exit_code": 0, "stdout": "PASS"},
    {"argv": ["python", "-m", "unittest", "discover", "-s", "evals/public", "-p", "test_*.py"], "exit_code": 0, "result": "56 tests passed"},
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


def manifest_summary(subject: dict) -> dict:
    states: dict[str, int] = {}
    for row in subject["f9_outcomes"]:
        states[row["outcome_state"]] = states.get(row["outcome_state"], 0) + 1
    spine = subject["upstream_spine"]
    return {
        "artifact_id": "VERTICAL-001-RUN-MANIFEST",
        "schema_version": "1.0.0",
        "execution_scope": subject["execution_scope"],
        "slice_id": subject["slice_id"],
        "result": subject["result"],
        "upstream": {
            "source_snapshot_sha256": spine["source_snapshot_sha256"],
            "candidate_snapshot_sha256": spine["candidate_snapshot_sha256"],
            "math_decision_sha256": spine["replay_receipt"]["math_decision_sha256"],
            "policy_sha256": spine["replay_receipt"]["policy_sha256"],
            "decision_id": spine["math_problem"]["decision_id"],
            "representative_id": spine["math_problem"]["route_day"]["representative_id"],
            "route_date": spine["math_problem"]["route_day"]["route_date"],
        },
        "schema_bindings": subject["schema_bindings"],
        "route_manifest": subject["route_manifest"],
        "field_event_count": len(subject["field_events"]),
        "outcome_count": len(subject["f9_outcomes"]),
        "outcome_state_counts": dict(sorted(states.items())),
        "counted_f9_positive_units": sum(row["counted_f9"] is True for row in subject["f9_outcomes"]),
        "not_yet_labelled_count": sum(row["counted_f9"] is None for row in subject["f9_outcomes"]),
        "replay_receipt": subject["replay_receipt"],
        "proof": subject["proof"],
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "stage2_rewrite":
        subject["upstream_spine"]["observations"][0]["clocks"]["available_at"] = "2026-08-01T00:00:00Z"
    elif mutation_id == "protected_stop_issued":
        cid = subject["route_manifest"]["stops"][0]["candidate_id"]
        candidate = next(row for row in subject["upstream_spine"]["candidates"] if row["candidate_id"] == cid)
        candidate["protection"]["status"] = "PROTECTED"
        candidate["math_candidate"]["protected_status"] = "PROTECTED"
    elif mutation_id == "duplicate_stop_issued":
        duplicate = copy.deepcopy(subject["route_manifest"]["stops"][0])
        duplicate["sequence_position"] = 10
        subject["route_manifest"]["stops"][-1] = duplicate
    elif mutation_id == "route_selection_mismatch":
        selected = {row["candidate_id"] for row in subject["upstream_spine"]["math_decision"]["selected"]}
        replacement = next(row["math_candidate"] for row in subject["upstream_spine"]["candidates"] if row["candidate_id"] not in selected)
        subject["route_manifest"]["stops"][-1]["candidate_id"] = replacement["candidate_id"]
        subject["route_manifest"]["stops"][-1]["physical_location_id"] = replacement["physical_location_id"]
    elif mutation_id == "field_event_before_issuance":
        subject["field_events"][0]["occurred_at"] = "2026-07-31T23:44:59Z"
    elif mutation_id == "immature_outcome_counted":
        outcome = next(row for row in subject["f9_outcomes"] if row["outcome_state"] == "IMMATURE_UNKNOWN")
        outcome["counted_f9"] = False
    elif mutation_id == "replay_receipt_mismatch":
        subject["replay_receipt"]["route_manifest_sha256"] = "0" * 64
    else:
        raise ValueError("unsupported mutation recipe")


def run_known_bad(path: Path) -> tuple[int, dict]:
    recipe = strict_load(path)
    count = 11 if recipe["mutation_id"] == "route_selection_mismatch" else 10
    subject = build_vertical_slice(count)
    apply_mutation(subject, recipe["mutation_id"])
    diagnostics = validate_vertical_slice(subject)
    detected = diagnostics == [recipe["expected_diagnostic"]]
    payload = {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": recipe["case_id"],
        "fixture_sha256": file_sha256(path),
        "diagnostic": diagnostics[0] if len(diagnostics) == 1 else "unexpected diagnostics",
    }
    return (0 if detected else 1), payload


def validate_report(recipes: list[dict]) -> list[str]:
    errors = []
    report = strict_load(REPORT)
    if set(report) != REPORT_FIELDS or (
        report.get("artifact_id") != "VERTICAL-001-PUBLIC-EVALUATION"
        or report.get("schema_version") != "1.0.0"
        or report.get("execution_scope") != "SYNTHETIC_NON_INFLUENCING"
        or report.get("result") != "PASS"
        or report.get("proof_level") != 5
        or report.get("evaluator_id") != "vertical-slice-public-v1"
        or report.get("tests") != EXPECTED_TESTS
        or report.get("commands") != EXPECTED_COMMANDS
        or report.get("claim") != "The bounded synthetic source-to-route-to-field-to-outcome slice conforms to its public contracts and replay semantics."
        or report.get("claim_ceiling") != "No real source, identity, protection, route, outreach, F9, lift, value, usability, or production claim is established."
    ):
        errors.append("VERTICAL-REPORT-CLAIM")
    subject_hashes = report.get("subject_hashes", {})
    if set(subject_hashes) != REPORT_SUBJECTS:
        errors.append("VERTICAL-REPORT-SUBJECT-COVERAGE")
    else:
        for relative, expected_sha in subject_hashes.items():
            if file_sha256(ROOT / relative) != expected_sha:
                errors.append(f"VERTICAL-REPORT-SUBJECT-DIGEST:{relative}")
    mutation_results = {row.get("case_id"): row for row in report.get("mutation_results", [])}
    by_case = {row["case_id"]: row for row in recipes}
    if set(mutation_results) != set(by_case):
        errors.append("VERTICAL-REPORT-MUTATION-COVERAGE")
    else:
        path_by_case = {strict_load(path)["case_id"]: path for path in KNOWN_BAD_PATHS}
        for case_id, recipe in by_case.items():
            expected = {"case_id": case_id, "diagnostic": recipe["expected_diagnostic"], "fixture_sha256": file_sha256(path_by_case[case_id]), "result": "DETECTED"}
            if mutation_results[case_id] != expected:
                errors.append(f"VERTICAL-REPORT-MUTATION:{case_id}")
    return errors


def validate() -> list[str]:
    errors = []
    issued = build_vertical_slice(10)
    abstained = build_vertical_slice(1)
    errors.extend(validate_vertical_slice(issued))
    errors.extend(validate_vertical_slice(abstained))
    if strict_load(MANIFEST) != manifest_summary(issued):
        errors.append("VERTICAL-RUN-MANIFEST-MISMATCH")
    process = subprocess.run([sys.executable, "-m", "unittest", "evals.public.test_vertical_slice"], cwd=ROOT, text=True, capture_output=True, timeout=45)
    if process.returncode != 0:
        errors.append("VERTICAL-PUBLIC-TESTS")
    evaluator_contract = strict_load(EVALUATOR_CONTRACT)
    registered = {row["mutation_id"]: row["expected_diagnostic"] for row in evaluator_contract.get("registered_mutations", [])}
    recipes = [strict_load(path) for path in KNOWN_BAD_PATHS]
    if len(recipes) != 7 or set(registered) != {row.get("mutation_id") for row in recipes}:
        errors.append("VERTICAL-MUTATION-COVERAGE")
    for path, recipe in zip(KNOWN_BAD_PATHS, recipes):
        if registered.get(recipe.get("mutation_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"VERTICAL-MUTATION-REGISTRY:{recipe.get('case_id')}")
        code, payload = run_known_bad(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"VERTICAL-MUTATION-SURVIVED:{recipe.get('case_id')}")
    errors.extend(validate_report(recipes))
    return sorted(set(errors))


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
        errors = ["VERTICAL-VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
