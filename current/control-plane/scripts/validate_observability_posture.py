#!/usr/bin/env python3
"""Frozen OBSERVABILITY-001 evaluator wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FROZEN_SHA256 = {'artifacts/evaluations/observability_lineage.json': '1770d49540b1b8e3dd590a20f3b035842d3512f86cf8f5835dfd0c310a232b14',
 'artifacts/observability/OBSERVABILITY-001-start.json': '968a6f8caadace91988f157b72f713cca224678d49751a24c5b6a50d3a9d770a',
 'artifacts/observability/public_evaluator_contract.json': '1427701b087f5fc5ceb25afaadb5935a0ec8ea83ef010f55720de0d0e3b71036',
 'contracts/lineage_manifest.schema.json': 'a6c9c49b065dd3e750b77cf7846900dc692f21e49ed708c1e60bb601ed4a789e',
 'contracts/observability_posture.schema.json': 'd3ac4bcd4073c445541f834d7476549b5c85ee65d76859472d690709b79d9c93',
 'evals/known_bad/frontier/lineage_missing_asof.json': '8e43bbcb313b2b7011ece12ef3c5b362e0dda343a2316f9d64c63c22e567e5a2',
 'evals/known_bad/frontier/lineage_protected_log.json': '701bc129a08f31e8b801467dc1c0d38bfac09ab2eefda21981387ff5687d6979',
 'evals/known_bad/frontier/observability001/observability_missing_correlation.json': '9118bde12855efdc3c6f8d10edf3fa45c24b0da70434919c4fecb4fad073b3d3',
 'evals/known_bad/frontier/observability001/observability_missing_hash.json': '8b2caa158d57ab3f2b6543f8a4e4191dbc4f25348fc82941975e3337e6089b6b',
 'evals/known_bad/frontier/observability001/observability_missing_lineage_edge.json': 'c91c2c075c2fe8a5f893d4567f5f08fa3d8d46a377702622cb4bc74e47aa8d9c',
 'evals/known_bad/frontier/observability001/observability_missing_replay_identity.json': 'bd134cd3a62e99055e1e1e66d5f1d49691327a472198a1325fbba8a4d76b1628',
 'evals/known_bad/frontier/observability001/observability_missing_version.json': '44f5f30bf4bb1b5aafe0194bbbabbbabaa3c9d1f744c5962b4264f04976e1292',
 'evals/public/observability_posture_evaluator.py': '83abf1f707f46343a8e8c2dcc99e86bbbd73526a333e1d7b2551329450facf4c',
 'scripts/validate_observability_lineage.py': 'd74660193693a1f6453d90eb4db8c38f331a5e629e152edc3e81c486a0684dbd'}

REQUIRED_FIXTURES = ['evals/known_bad/frontier/lineage_missing_asof.json',
 'evals/known_bad/frontier/observability001/observability_missing_version.json',
 'evals/known_bad/frontier/observability001/observability_missing_hash.json',
 'evals/known_bad/frontier/observability001/observability_missing_correlation.json',
 'evals/known_bad/frontier/observability001/observability_missing_replay_identity.json',
 'evals/known_bad/frontier/observability001/observability_missing_lineage_edge.json',
 'evals/known_bad/frontier/lineage_protected_log.json']

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

        actual = file_sha256(path)

        if actual != expected:
            raise SystemExit(
                f"FROZEN HASH MISMATCH: {relative}"
            )


def run_clean() -> int:
    verify_freeze()

    from evals.public import (
        observability_posture_evaluator
        as evaluator,
    )

    subject = evaluator.build_clean_subject()
    result = evaluator.evaluate_subject(subject)

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
        print(
            json.dumps(
                {
                    "result": "REJECTED",
                    "diagnostic": (
                        "LINEAGE-UNREGISTERED-FIXTURE"
                    ),
                },
                sort_keys=True,
            )
        )
        return 1

    if relative not in REQUIRED_FIXTURES:
        print(
            json.dumps(
                {
                    "result": "REJECTED",
                    "diagnostic": (
                        "LINEAGE-UNREGISTERED-FIXTURE"
                    ),
                },
                sort_keys=True,
            )
        )
        return 1

    from evals.public import (
        observability_posture_evaluator
        as evaluator,
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
