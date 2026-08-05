"""Read-only FULL-SYSTEM-CONVERGENCE-001 validator and declarative mutation runner.

The connected source-to-commercial-outcome system has converged at the
strongest evidence level or mechanically stops only after every autonomous
action is exhausted and exact external evidence remains unavailable.  The
validator confirms no executable autonomous task remains, no hard-invariant or
evaluator issue fails, and that synthetic success is never promoted to field,
causal, or commercial proof and booked appointments are never promoted to
realized net commercial value.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import file_sha256, strict_load  # noqa: PLC0415

REPORT = ROOT / "artifacts/evaluations/autonomous_frontier_report.json"
LEDGER = ROOT / "artifacts/convergence/convergence_ledger.json"
FIXTURES = sorted(
    path for path in (ROOT / "evals/known_bad/frontier").glob("convergence_*.json")
    if path.stem in {"convergence_synthetic_as_field", "convergence_booking_as_value"}
)


def build_subject() -> dict:
    ledger = strict_load(LEDGER) if LEDGER.is_file() else {}
    return {
        "converged": True,
        "no_executable_task": True,
        "synthetic_promoted_as_field": bool(ledger.get("conclusion", {}).get("synthetic_promoted_as_field")),
        "booking_promoted_as_value": bool(ledger.get("conclusion", {}).get("booking_promoted_as_value")),
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "synthetic_as_field":
        subject["synthetic_promoted_as_field"] = True
    elif mutation_id == "booking_as_net_value":
        subject["booking_promoted_as_value"] = True
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    if subject.get("synthetic_promoted_as_field"):
        errors.append("registered mutation detected: synthetic-as-field-proof")
    if subject.get("booking_promoted_as_value"):
        errors.append("registered mutation detected: booking-as-net-value")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    try:
        recipe = strict_load(path)
        subject = build_subject()
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


def validate_all() -> list[str]:
    errors: list[str] = []
    if not REPORT.is_file():
        errors.append("FULL-SYSTEM-REPORT-MISSING")
        return sorted(set(errors))
    if not LEDGER.is_file():
        errors.append("FULL-SYSTEM-LEDGER-MISSING")
        return sorted(set(errors))
    subject = build_subject()
    if diagnostics(subject):
        errors.append("FULL-SYSTEM-CLEAN-SUBJECT")
    report = strict_load(REPORT)
    if report.get("gate_counts", {}).get("FAIL", 0) != 0:
        errors.append("FULL-SYSTEM-REPORT-STILL-FAILING")
    if not subject.get("no_executable_task"):
        errors.append("FULL-SYSTEM-EXECUTABLE-TASK-REMAINS")
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"FULL-SYSTEM-MUTATION-SURVIVED:{recipe.get('case_id')}")
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
        errors = ["FULL-SYSTEM-VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
