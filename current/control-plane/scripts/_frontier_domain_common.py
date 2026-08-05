"""Shared read-only helpers for the frontier domain validators.

Each Phase-1 domain validator follows the same shape: a deterministic
canonical synthetic subject, a pure ``diagnostics(subject)`` predicate list, a
declarative mutation recipe applied for each registered known-bad fixture, and
a sha256-bound evidence artifact that records mutation results.  All functions
here are read-only; generators live in ``build_phase1_evidence.py``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def run_known_bad(
    root: Path,
    fixtures: list[Path],
    build_subject,
    apply_mutation,
    diagnostics,
    recipe_path: Path,
) -> tuple[int, dict[str, Any]]:
    """Run one known-bad fixture: mutate the canonical subject and require the
    exact registered diagnostic.  Mirrors the vertical-slice recipe contract."""
    try:
        recipe = strict_load(recipe_path)
        subject = build_subject()
        apply_mutation(subject, recipe["mutation_id"])
        found = diagnostics(subject)
        detected = found == [recipe["expected_diagnostic"]]
        payload = {
            "result": "DETECTED" if detected else "SURVIVED",
            "case_id": recipe["case_id"],
            "fixture_sha256": file_sha256(recipe_path),
            "diagnostic": found[0] if len(found) == 1 else "unexpected diagnostics",
        }
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        payload = {
            "result": "SURVIVED",
            "case_id": "invalid",
            "fixture_sha256": file_sha256(recipe_path) if recipe_path.is_file() else "",
            "diagnostic": str(exc),
        }
        return 1, payload
    return (0 if detected else 1), payload


def known_bad_main(
    argv,
    root: Path,
    build_subject,
    apply_mutation,
    diagnostics,
    validate_all,
) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args(argv)
    if args.known_bad:
        path = args.known_bad if args.known_bad.is_absolute() else root / args.known_bad
        code, payload = run_known_bad(
            root,
            [],
            build_subject,
            apply_mutation,
            diagnostics,
            path,
        )
        print(json.dumps(payload, sort_keys=True))
        return code
    try:
        errors = validate_all()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors = ["VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1
