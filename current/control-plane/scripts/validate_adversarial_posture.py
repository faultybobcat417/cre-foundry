#!/usr/bin/env python3
"""Frozen ADVERSARIAL-001 evaluator wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FROZEN_SHA256 = {'artifacts/adversarial/ADVERSARIAL-001-start.json': 'a646779afd8896409910d2554d69e354b46a73a1f6778b7c0f1244403de6d1f1',
 'artifacts/adversarial/public_evaluator_contract.json': 'aa0dffcca8d02c7efd7cb42731ccc0c5179fa47e64e92ba3ba9b4e2a03db88d7',
 'artifacts/evaluations/full_adversarial_campaign.json': 'a3372324898199e9402602d2b156d4f0ee76fcd5fa7125f0f3c14cfda83c889b',
 'artifacts/evaluations/known_bad_public_result.json': 'f6099f34a3c6267c23a5caf376eef9c63b811ee2e92219fe7ddae09d829a1581',
 'contracts/adversarial_campaign.schema.json': '8c2ebe57cb33bef5ed1254b75940c36da118ceac3ad32ddf5e1a2f37daf5b483',
 'evals/known_bad/exact_name_only_clearance.py': 'de1a1958cf2c5cabbf600d1a5857074b1d6e510507f9530a2b2ffdf97a243516',
 'evals/known_bad/frontier/adversarial001/evaluator_unavailable_pass.json': '8b40f741b750b5fd635f35fab68bddcbfed0ce0a71912367b4d5e6592f672195',
 'evals/known_bad/frontier/adversarial001/evaluator_weakened.json': '4085ae81cca76ec51d9ada40125956ef80b96a49233d3a3d1c272e88d312a784',
 'evals/known_bad/frontier/adversarial001/fault_retry_partial.json': 'f362151d278e6182ef03efbe6482458cea00df8245d0a94239e861094b7956af',
 'evals/known_bad/frontier/adversarial001/identity_protection_bypass.json': '88cc04ba547ba110225c2b267833a4e1f6201eedd6ff4f943390b2f106eac201',
 'evals/known_bad/frontier/adversarial001/malformed_duplicate_key_accepted.json': '18ed9975ae80a313850ae3ddec6a374e50759b28674a4202fb51bb212b85a7a2',
 'evals/known_bad/frontier/adversarial001/metamorphic_property_failure.json': 'a8ebb83ec16e2e2641df348c2df86bc9853fa6023853b42352d14ddc87151a45',
 'evals/known_bad/frontier/adversarial001/outcome_economic_misattribution.json': '52881ded0540afa1a54f5d5a17faa1b5a33e293d2cf8b637c81cda62734dccb2',
 'evals/known_bad/frontier/adversarial001/restore_rollback_mismatch.json': '53895cdad6927714efc5a14745358c2b32a6268c00f6efe79924432c8c4b976a',
 'evals/known_bad/frontier/adversarial001/route_violation.json': '2101dd544c20a7d30595fa98db58c714cf43dda0b8eaa6f5eb97d16d5a3bafa0',
 'evals/known_bad/frontier/adversarial001/security_bypass.json': '75e36586cbbae79ec897cc441379475d55c00d8adcf2a05be37eef7f7c5d45cb',
 'evals/known_bad/frontier/adversarial001/source_integrity_bypass.json': '99129d5f11a90a5f81f96af352d8a29ab2e1b45bbc8cbb0139910001f38bc562',
 'evals/known_bad/frontier/adversarial001/temporal_leakage.json': '028f081b94f80c0a4946d1b613015eade79bde5f66cf2b6c34831e3d378ea50e',
 'evals/known_bad/frontier/adversarial001/uncertainty_bypass.json': '1929e1ec87387233a1778263cc3c27737a150673ce12a306e3c8dce413e93ff3',
 'evals/known_bad/frontier/adversarial_evaluator_unavailable.json': '5995d6a6d8a1f369b29603b4d3d39750be680825d96aeaaeca3a24aee7adea35',
 'evals/public/adversarial_connected_evaluator.py': 'f72d786f9fe5894becc467b95c24461661b6f7057160e12f63828b57fa3aa569',
 'evals/public/route_decision_evaluator.py': '59569c847562b26f3c0740dda05237472e7a73dd0eb66e03d60beb40cf5c3aa8',
 'scripts/prove_known_bad_fails.py': 'e6fa8063ded400a68024ae4dd53dae188280d521551e6c4b9e941e6ee3eb2f69',
 'scripts/run_adversarial_campaign.py': '7d71d91a789b0ca054e943791445c4c36cd871f9c4e58b49d56b8e6c7a5e23f0'}

REQUIRED_FIXTURES = ['evals/known_bad/frontier/adversarial001/malformed_duplicate_key_accepted.json',
 'evals/known_bad/frontier/adversarial001/temporal_leakage.json',
 'evals/known_bad/frontier/adversarial001/source_integrity_bypass.json',
 'evals/known_bad/frontier/adversarial001/identity_protection_bypass.json',
 'evals/known_bad/frontier/adversarial001/uncertainty_bypass.json',
 'evals/known_bad/frontier/adversarial001/route_violation.json',
 'evals/known_bad/frontier/adversarial001/outcome_economic_misattribution.json',
 'evals/known_bad/frontier/adversarial001/security_bypass.json',
 'evals/known_bad/frontier/adversarial001/fault_retry_partial.json',
 'evals/known_bad/frontier/adversarial001/restore_rollback_mismatch.json',
 'evals/known_bad/frontier/adversarial001/evaluator_unavailable_pass.json',
 'evals/known_bad/frontier/adversarial001/evaluator_weakened.json',
 'evals/known_bad/frontier/adversarial001/metamorphic_property_failure.json']

def file_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def strict_load(path: Path) -> dict[str, Any]:
    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(
                    f"duplicate key: {key}"
                )

            result[key] = value

        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
    )

    if not isinstance(value, dict):
        raise ValueError(
            "JSON root must be an object"
        )

    return value


def verify_freeze() -> None:
    for relative, expected in (
        FROZEN_SHA256.items()
    ):
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
        adversarial_connected_evaluator
        as evaluator,
    )

    result = evaluator.evaluate_subject(
        evaluator.build_clean_subject()
    )

    if result["passed"] is not True:
        print(
            json.dumps(
                result,
                sort_keys=True,
            )
        )
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
                    "diagnostic": (
                        "ADVERSARIAL-"
                        "UNREGISTERED-FIXTURE"
                    ),
                    "result": "REJECTED",
                },
                sort_keys=True,
            )
        )
        return 1

    from evals.public import (
        adversarial_connected_evaluator
        as evaluator,
    )

    fixture = strict_load(ROOT / relative)
    subject = evaluator.build_clean_subject()

    evaluator.apply_mutation(
        subject,
        fixture["mutation_id"],
    )

    result = evaluator.evaluate_subject(
        subject
    )

    expected = fixture[
        "expected_diagnostic"
    ]

    detected = (
        result["diagnostics"] == [expected]
    )

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

    print(
        json.dumps(
            payload,
            sort_keys=True,
        )
    )

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

    return run_known_bad(
        args.known_bad
    )


if __name__ == "__main__":
    raise SystemExit(main())
