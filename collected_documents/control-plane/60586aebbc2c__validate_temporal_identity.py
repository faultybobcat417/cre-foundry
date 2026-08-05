#!/usr/bin/env python3
"""IDENTITY-001 S-1B independent temporal identity validator.

Read-only validation of the frozen temporal identity subject layer.  The
default run builds the deterministic clean synthetic subject, checks the two
frozen S-1A inputs by SHA-256, validates the subject against the frozen schema,
and judges it with the independent public evaluator.  It never imports the
identity material implementation, never writes an artifact (no
``artifacts/evaluations/identity_synthetic.json``), and is fully deterministic
under ``CRE_FRONTIER_COMMAND_REPLAY=1``.

Modes:
  * default          build clean subject, schema-validate, evaluate -> print "PASS"
  * --input PATH     strictly parse and evaluate one subject document
  * --known-bad PATH evaluate one registered mutation fixture for the house CLI
                     contract ({"result","case_id","fixture_sha256","diagnostic"})
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker

from evals.public.temporal_identity_evaluator import (
    build_clean_subject, evaluate_subject, evaluate_path, evaluate_known_bad,
    strict_load_json, CONTRACT_PATH, SCHEMA_PATH,
)

FROZEN_SHA256: dict[str, str] = {
    "artifacts/identity/public_evaluator_contract.json": "583e7715e2af53e82309e934d6136d1b161bcda45771cebc948e9a9137525282",
    "contracts/temporal_identity.schema.json": "0c3b42f906063169b46cc760f9e7cf516b3c73c7c84f6293eb4cfcf826cc55ba",
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_frozen(errors: list[str]) -> None:
    for relative, expected in FROZEN_SHA256.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"FROZEN:{relative} missing")
        elif _file_sha256(path) != expected:
            errors.append(f"FROZEN:{relative} sha256 changed")


def _check_clean_subject(errors: list[str]) -> dict[str, Any]:
    subject = build_clean_subject()
    schema = strict_load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted({error.message for error in validator.iter_errors(subject)})
    if schema_errors:
        for message in schema_errors:
            errors.append(f"SCHEMA:{message}")
    payload = evaluate_subject(subject)
    if not payload["passed"]:
        errors.append(f"EVALUATOR:diagnostics {payload['diagnostics']}")
    return payload


def run_default() -> int:
    errors: list[str] = []
    _check_frozen(errors)
    _check_clean_subject(errors)
    if errors:
        print("FAIL")
        for error in sorted(set(errors)):
            print(f"  {error}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


def run_input(path: Path) -> int:
    try:
        diagnostics, payload = evaluate_path(path)
    except (OSError, ValueError, json.JSONDecodeError):
        print("FAIL")
        return 1
    if payload["passed"]:
        print("PASS")
        return 0
    print("FAIL")
    for diagnostic in diagnostics:
        print(f"  {diagnostic}", file=sys.stderr)
    return 1


def run_known_bad(raw_path: Path) -> int:
    path = raw_path if raw_path.is_absolute() else ROOT / raw_path
    try:
        payload = evaluate_known_bad(path)
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {"result": "SURVIVED", "case_id": "unknown", "fixture_sha256": "", "diagnostic": "fixture not strictly parseable"}
        print(json.dumps(payload, sort_keys=True))
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["result"] == "DETECTED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="IDENTITY-001 S-1B independent temporal identity validator")
    parser.add_argument("--input", type=Path, help="strictly parse and evaluate one subject document")
    parser.add_argument("--known-bad", type=Path, help="run one registered mutation fixture for the house CLI contract")
    args = parser.parse_args()
    if args.known_bad is not None and args.input is not None:
        print("FAIL", file=sys.stderr)
        return 1
    if args.known_bad is not None:
        return run_known_bad(args.known_bad)
    if args.input is not None:
        return run_input(args.input)
    return run_default()


if __name__ == "__main__":
    raise SystemExit(main())
