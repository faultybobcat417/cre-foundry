#!/usr/bin/env python3
"""Frozen REPLAY-001 evaluator wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FROZEN_SHA256 = {'artifacts/evaluations/replay_recovery.json': 'fb5b6a27faa2e19fd265d128d0ddfb2b9208d214c24c275170a1cee56171b24a',
 'artifacts/replay/REPLAY-001-start.json': '36071aab87eebb2b3455b4da1a17d294c564235d289a1d42f20da3e9baceedeb',
 'artifacts/replay/public_evaluator_contract.json': '73ca398b4f569fe525a9ec2ef3c72234c9c67e3bc9f482aea0d33cc7aa3c2570',
 'contracts/replay_recovery.schema.json': 'fc914812e66f48c2769b5f92f73b307a72d0226186ad38e66237b40f81999d73',
 'docs/reliability/recovery_and_migrations.md': '95043ee59143244359d7eb2f2bc884e148810b073bfb1341b44ca7d2dc8e4880',
 'evals/known_bad/frontier/replay001/replay_migration_incompatible.json': '28b0f9755e8a5d4d8fd12fcbccdf4fa6640523c701fdedd594ab20914397e4c7',
 'evals/known_bad/frontier/replay001/replay_output_mismatch.json': '897c3bf358826b824bc6a200678eafc92ac1a1a7883e23fc345274cb71455eaa',
 'evals/known_bad/frontier/replay001/replay_partial_crash.json': 'f05f128b0e011e52ba32d2b9aa614511a42dcd005b46c9858911783f2c0c7a27',
 'evals/known_bad/frontier/replay001/replay_restore_mismatch.json': 'e05acb2d8a49b58e60acc031e5522138e020e4f100a59ba440cd7a6a7222ed8a',
 'evals/known_bad/frontier/replay001/replay_rollback_failure.json': '79617e4a72b9f3dd29e7748fe2514cf260f70484545365ea0cf1f84f245bb85e',
 'evals/known_bad/frontier/replay_duplicate_effect.json': 'cbff44e2f96a6ac5116cfb79170299fa279f7419239cfb85dce838b020da4030',
 'evals/known_bad/frontier/replay_old_snapshot.json': 'dc27c65f43faf89874405f83ee4aec35e7aabb5ad6dd210390084a98e0075628',
 'evals/public/replay_recovery_evaluator.py': 'eb24c9f34250c084bb285bf8c47632dcabe616b849df65630508d48dcae50668',
 'scripts/validate_replay_recovery.py': '0ee3aa0fed0b9a75c0e3e5105da2aa2cd43d82a52bf5d3502735d0ab03a001d7'}

REQUIRED_FIXTURES = ['evals/known_bad/frontier/replay001/replay_output_mismatch.json',
 'evals/known_bad/frontier/replay_duplicate_effect.json',
 'evals/known_bad/frontier/replay001/replay_partial_crash.json',
 'evals/known_bad/frontier/replay_old_snapshot.json',
 'evals/known_bad/frontier/replay001/replay_migration_incompatible.json',
 'evals/known_bad/frontier/replay001/replay_restore_mismatch.json',
 'evals/known_bad/frontier/replay001/replay_rollback_failure.json']

def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(path: Path) -> dict[str, Any]:
    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value

        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
    )

    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")

    return value


def verify_freeze() -> None:
    for relative, expected in FROZEN_SHA256.items():
        path = ROOT / relative

        if not path.is_file():
            raise SystemExit(
                f"FROZEN FILE MISSING: {relative}"
            )

        if file_sha256(path) != expected:
            raise SystemExit(
                f"FROZEN HASH MISMATCH: {relative}"
            )


def run_clean() -> int:
    verify_freeze()

    from evals.public import (
        replay_recovery_evaluator as evaluator,
    )

    result = evaluator.evaluate_subject(
        evaluator.build_clean_subject()
    )

    if result["passed"] is not True:
        print(json.dumps(result, sort_keys=True))
        return 1

    print("PASS")
    return 0


def run_known_bad(path: Path) -> int:
    verify_freeze()

    try:
        relative = (
            path.resolve()
            .relative_to(ROOT.resolve())
            .as_posix()
        )
    except ValueError:
        relative = ""

    if relative not in REQUIRED_FIXTURES:
        print(
            json.dumps(
                {
                    "result": "REJECTED",
                    "diagnostic":
                        "REPLAY-UNREGISTERED-FIXTURE",
                },
                sort_keys=True,
            )
        )
        return 1

    from evals.public import (
        replay_recovery_evaluator as evaluator,
    )

    fixture = strict_load(ROOT / relative)
    subject = evaluator.build_clean_subject()

    evaluator.apply_mutation(
        subject,
        fixture["mutation_id"],
    )

    result = evaluator.evaluate_subject(subject)
    expected = fixture["expected_diagnostic"]
    detected = result["diagnostics"] == [expected]

    payload = {
        "case_id": fixture["case_id"],
        "diagnostic": (
            expected
            if detected
            else result["diagnostics"]
        ),
        "fixture_sha256": file_sha256(
            ROOT / relative
        ),
        "result": (
            "DETECTED"
            if detected
            else "SURVIVED"
        ),
    }

    print(json.dumps(payload, sort_keys=True))
    return 0 if detected else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--known-bad",
        type=Path,
    )
    args = parser.parse_args()

    if args.known_bad is None:
        return run_clean()

    return run_known_bad(args.known_bad)


if __name__ == "__main__":
    raise SystemExit(main())
