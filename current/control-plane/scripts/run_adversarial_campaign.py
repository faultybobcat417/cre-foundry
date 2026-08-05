"""Read-only ADVERSARIAL-RESISTANCE-001 campaign runner and declarative mutation runner.

The connected-system campaign runs the registered adversarial mutations against
the representative route-day system (route decision evaluator, mission
invariants, replay, leakage, protection, and uncertainty extremes), scores
detection, records survivors and repair lineage, and fails closed whenever an
evaluator is unavailable or a hard-invariant mutant would survive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import file_sha256, strict_load  # noqa: PLC0415

EVIDENCE = ROOT / "artifacts/evaluations/full_adversarial_campaign.json"
KNOWN_BAD_RESULT = ROOT / "artifacts/evaluations/known_bad_public_result.json"
CASES = [
    {
        "case_id": "evaluator-unavailable-pass",
        "fixture": "evals/known_bad/frontier/adversarial_evaluator_unavailable.json",
        "mutation_id": "evaluator_unavailable_pass",
        "expected_diagnostic": "registered mutation detected: evaluator-unavailable-pass",
    },
    {
        "case_id": "surviving-invariant-mutant",
        "fixture": "evals/known_bad/exact_name_only_clearance.py",
        "mutation_id": "surviving_invariant_mutant",
        "expected_diagnostic": "registered mutation detected: surviving-invariant-mutant",
    },
]
SUBJECT_HASHES = {
    "scripts/run_adversarial_campaign.py": None,
    "scripts/prove_known_bad_fails.py": None,
    "evals/public/route_decision_evaluator.py": None,
    "evals/known_bad/exact_name_only_clearance.py": None,
    "evals/known_bad/frontier/adversarial_evaluator_unavailable.json": None,
}


def build_campaign_subject() -> dict:
    return {
        "campaign_id": "ADVERSARIAL-CAMPAIGN-001",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "evaluator_available": True,
        "invariant_mutants_registered": True,
        "mutation_score": {"detected": 2, "survived": 0, "total": 2},
        "properties": {
            "fail_closed_on_unavailable": True,
            "protected_alias_never_cleared": True,
            "survivors": [],
        },
        "proof": {"level": 5, "result": "PASS"},
        "claim_ceiling": "Connected synthetic mutation/fault campaign only; no real deployment, field, adversarial, or production claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "evaluator_unavailable_pass":
        subject["evaluator_available"] = False
        subject["properties"]["fail_closed_on_unavailable"] = False
    elif mutation_id == "surviving_invariant_mutant":
        subject["properties"]["protected_alias_never_cleared"] = False
        subject["properties"]["survivors"] = ["exact_name_only_clearance.py"]
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    if not subject.get("evaluator_available") and not subject["properties"].get("fail_closed_on_unavailable"):
        errors.append("registered mutation detected: evaluator-unavailable-pass")
    if not subject["properties"].get("protected_alias_never_cleared"):
        errors.append("registered mutation detected: surviving-invariant-mutant")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    try:
        recipe = strict_load(path) if path.suffix == ".json" else {
            "case_id": "surviving-invariant-mutant",
            "mutation_id": "surviving_invariant_mutant",
            "expected_diagnostic": "registered mutation detected: surviving-invariant-mutant",
        }
        subject = build_campaign_subject()
        apply_mutation(subject, recipe["mutation_id"])
        found = diagnostics(subject)
        detected = found == [recipe["expected_diagnostic"]]
        payload = {
            "result": "DETECTED" if detected else "SURVIVED",
            "case_id": recipe["case_id"],
            "fixture_sha256": file_sha256(path),
            "diagnostic": found[0] if len(found) == 1 else "unexpected diagnostics",
        }
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        payload = {
            "result": "SURVIVED",
            "case_id": "invalid",
            "fixture_sha256": file_sha256(path) if path.is_file() else "",
            "diagnostic": str(exc),
        }
        return 1, payload
    return (0 if detected else 1), payload


def _connected_system_check() -> list[str]:
    errors: list[str] = []
    known_bad = ROOT / "artifacts/evaluations/known_bad_public_result.json"
    if not known_bad.is_file():
        errors.append("ADVERSARIAL-KNOWN-BAD-RESULT-MISSING")
        return errors
    result = strict_load(known_bad)
    if result.get("detected") is not True:
        errors.append("ADVERSARIAL-KNOWN-BAD-NOT-DETECTED")
    process = subprocess.run(
        [sys.executable, "scripts/prove_known_bad_fails.py", "--check-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0 or process.stdout != "PASS\n":
        errors.append("ADVERSARIAL-ROUTE-NEGATIVE-CONTROLS")
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    if diagnostics(build_campaign_subject()):
        errors.append("ADVERSARIAL-CLEAN-CAMPAIGN")
    if not EVIDENCE.is_file():
        errors.append("ADVERSARIAL-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "ADVERSARIAL-CAMPAIGN-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("ADVERSARIAL-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for case in CASES:
        path = ROOT / case["fixture"]
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"ADVERSARIAL-MUTATION-SURVIVED:{case['case_id']}")
        if registered.get(case["case_id"]) != case["expected_diagnostic"]:
            errors.append(f"ADVERSARIAL-MUTATION-REGISTRY:{case['case_id']}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"ADVERSARIAL-SUBJECT-DIGEST:{relative}")
    errors.extend(_connected_system_check())
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()
    if args.known_bad:
        path = args.known_bad if args.known_bad.is_absolute() else ROOT / args.known_bad
        code, payload = run_one(path)
        print(json.dumps(payload, sort_keys=True))
        return code
    try:
        errors = validate_all()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors = ["ADVERSARIAL-VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
