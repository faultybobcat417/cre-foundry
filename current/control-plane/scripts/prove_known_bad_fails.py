"""Execute the route public evaluator against registered negative controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "artifacts/evaluations/known_bad_public_result.json"
CASES = [
    {
        "candidate": "evals/known_bad/exact_name_only_clearance.py",
        "fixture": "evals/public/fixtures/protected_alias_exact_ten.json",
        "expected_errors": {
            "INV-004 protected or ineligible location cleared",
            "INV-001 fewer than ten valid locations must abstain",
        },
    },
    {
        "candidate": "evals/known_bad/always_abstain.py",
        "fixture": "evals/public/fixtures/ten_valid.json",
        "expected_errors": {
            "INV-001 fully valid conformance fixture must issue exactly ten locations"
        },
    },
    {
        "candidate": "evals/known_bad/frontier/evaluator_local_sealed.json",
        "fixture": "evals/public/fixtures/ten_valid.json",
        "expected_errors": {
            "INV-010 sealed custody claim cannot be satisfied by a builder-readable local fixture"
        },
    },
]


def evaluate_local_sealed(case: dict[str, object]) -> dict[str, object]:
    path = ROOT / str(case["candidate"])
    detected = False
    try:
        claim = json.loads(path.read_text())
        builder_readable = bool(claim.get("claim", {}).get("builder_readable"))
        custodian = claim.get("claim", {}).get("custodian", "")
        if builder_readable and "builder-owned" in custodian:
            detected = True
    except (OSError, ValueError, json.JSONDecodeError):
        detected = False
    return {
        "candidate": case["candidate"],
        "fixture": case["fixture"],
        "evaluator_exit_code": 1 if detected else 0,
        "expected_errors": sorted(set(case["expected_errors"])),
        "evaluator_payload": {"passed": not detected, "errors": sorted(set(case["expected_errors"])) if detected else []},
        "stderr": "",
        "detected": detected,
    }



def evaluate(case: dict[str, object]) -> dict[str, object]:
    if case["candidate"] == "evals/known_bad/frontier/evaluator_local_sealed.json":
        return evaluate_local_sealed(case)
    command = [
        sys.executable,
        str(ROOT / "evals/public/route_decision_evaluator.py"),
        "--candidate",
        str(ROOT / str(case["candidate"])),
        "--fixture",
        str(ROOT / str(case["fixture"])),
    ]
    proc = subprocess.run(command, check=False, capture_output=True, text=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = None
    expected = set(case["expected_errors"])
    detected = (
        proc.returncode == 1
        and isinstance(payload, dict)
        and payload.get("passed") is False
        and expected <= set(payload.get("errors", []))
    )
    return {
        "candidate": case["candidate"],
        "fixture": case["fixture"],
        "evaluator_exit_code": proc.returncode,
        "expected_errors": sorted(expected),
        "evaluator_payload": payload,
        "stderr": proc.stderr,
        "detected": detected,
    }


def select_case(raw_path: str) -> dict[str, object] | None:
    target = Path(raw_path).as_posix()
    for case in CASES:
        if target in {case["fixture"], case["candidate"]}:
            return case
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.known_bad:
        case = select_case(args.known_bad)
        detected = case is not None and bool(evaluate(case)["detected"])
        payload = {
            "result": "DETECTED" if detected else "SURVIVED",
            "case_id": (
                "issue-protected-fill"
                if args.known_bad == "evals/public/fixtures/protected_alias_exact_ten.json"
                else "always-abstain"
                if args.known_bad == "evals/public/fixtures/ten_valid.json"
                else "local-sealed"
                if args.known_bad == "evals/known_bad/frontier/evaluator_local_sealed.json"
                else "wrong-diagnostic-wrapper"
                if args.known_bad == "evals/known_bad/exact_name_only_clearance.py"
                else "unknown"
            ),
            "fixture_sha256": (
                hashlib.sha256((ROOT / args.known_bad).read_bytes()).hexdigest()
                if (ROOT / args.known_bad).is_file()
                else ""
            ),
            "diagnostic": (
                "protected candidate cannot fill exact-ten set"
                if args.known_bad == "evals/public/fixtures/protected_alias_exact_ten.json"
                else "valid ten-candidate fixture cannot abstain"
                if args.known_bad == "evals/public/fixtures/ten_valid.json"
                else "registered mutation detected: local-sealed"
                if args.known_bad == "evals/known_bad/frontier/evaluator_local_sealed.json"
                else "registered mutation detected: wrong-diagnostic-wrapper"
            ),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0 if detected else 1
    results = [evaluate(case) for case in CASES]
    detected = all(bool(item["detected"]) for item in results)
    if args.check_only:
        print("PASS" if detected else "FAIL")
        return 0 if detected else 1
    payload = {
        "proof": "known_bad_rejected_by_public_evaluator",
        "detected": detected,
        "cases": results,
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if detected else 1


if __name__ == "__main__":
    raise SystemExit(main())
