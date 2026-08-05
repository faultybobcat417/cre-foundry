"""Builder-visible deterministic evaluator for the exact-ten decision boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
DECISION_SCHEMA = json.loads((ROOT / "contracts/route_decision.schema.json").read_text())


def eligible_ids(fixture: dict) -> set[str]:
    return {
        item["location_id"]
        for item in fixture["candidates"]
        if item.get("eligible") is True and item.get("protected_match") is not True
    }


def evaluate(fixture: dict, decision: dict) -> list[str]:
    schema_errors = sorted(
        Draft202012Validator(DECISION_SCHEMA).iter_errors(decision),
        key=lambda error: list(error.path),
    )
    if schema_errors:
        return [f"CONTRACT route decision: {error.message}" for error in schema_errors]
    errors: list[str] = []
    valid = eligible_ids(fixture)
    selected = decision.get("locations", [])
    if len(selected) != len(set(selected)):
        errors.append("INV-003 duplicate physical location")
    if not set(selected).issubset(valid):
        errors.append("INV-004 protected or ineligible location cleared")
    if len(valid) < 10:
        if decision.get("decision") != "ABSTAIN_NO_VALID_TEN" or selected:
            errors.append("INV-001 fewer than ten valid locations must abstain")
    elif decision.get("decision") == "ISSUE":
        if len(selected) != 10:
            errors.append("INV-001 issued route must contain exactly ten locations")
    elif decision.get("decision") == "ABSTAIN_NO_VALID_TEN":
        errors.append("INV-001 fully valid conformance fixture must issue exactly ten locations")
    elif decision.get("decision") != "ABSTAIN_NO_VALID_TEN":
        errors.append("decision must ISSUE or ABSTAIN_NO_VALID_TEN")
    return errors


def run(candidate: Path, fixture_path: Path) -> list[str]:
    fixture = json.loads(fixture_path.read_text())
    proc = subprocess.run(
        [sys.executable, str(candidate), "--input", str(fixture_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return [f"candidate exited {proc.returncode}: {proc.stderr.strip()}"]
    try:
        decision = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [f"candidate emitted invalid JSON: {exc}"]
    return evaluate(fixture, decision)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    errors = run(args.candidate, args.fixture)
    payload = {"passed": not errors, "errors": errors}
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
