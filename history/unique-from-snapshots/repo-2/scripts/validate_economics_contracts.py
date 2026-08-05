#!/usr/bin/env python3
"""House S-2 validator for the ECONOMICS-001 material economics engine.

Cross-checks the material implementation against the frozen independent
evaluator and the frozen ECONOMICS-001 contract:

1. Constrain the material subject to the frozen ``contracts/commercial_economics.schema.json``.
2. Require byte-identical agreement with the frozen evaluator's clean subject.
3. Require the frozen independent evaluator to PASS the material-rendered subject
   with zero diagnostics and agreement on every registered mutation.
4. Require the material's own checks to be clean on the same subject.
5. Replay every registered known-bad fixture onto the material subject and require
   BOTH the frozen evaluator and the material checks to detect the exact registered
   diagnostic.
6. Prove determinism: two renders are byte-identical.
7. Exercise the material ECV machinery (expected net value, downside, sensitivity,
   fallback) deterministically.

This validator is the house cross-check and not the frozen judge; it imports both
implementations.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

FORMAT_CHECKER = FormatChecker()

REGISTERED = {
    "omitted-costs": "ECONOMICS-OMITTED-COSTS",
    "modeled-as-realized": "ECONOMICS-MODELED-AS-REALIZED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_schema(subject: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    return sorted(set(error.json_path for error in validator.iter_errors(subject)))


def scan_source_independence(paths: list[Path]) -> list[str]:
    """Return any actual evaluator import in the material source.

    Only real import statements (``import``/``from`` lines naming a forbidden
    evaluator module) are flagged; docstrings, comments, and file-path constants
    that merely spell the evaluator filename are not code coupling."""
    findings: list[str] = []
    forbidden = ["validate_economics_ecv", "validate_security_privacy", "_frontier_domain_common"]
    for path in paths:
        if not path.is_file():
            continue
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if stripped.startswith(("import ", "from ")) and any(
                token in stripped.replace(" ", "").replace("'", "").replace('"', "")
                for token in forbidden
            ):
                findings.append(f"{path.name}:{index}:{stripped}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="ECONOMICS-001 material economics engine house validator")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/evaluations/economics_contracts.json")
    args = parser.parse_args()

    from cre_foundry.economics import engine as material
    from scripts import validate_economics_ecv as frozen

    subject_schema = _load(ROOT / "contracts/commercial_economics.schema.json")
    policy_schema = _load(ROOT / "contracts/economic_engine.schema.json")

    subject_schema_valid = True
    subject_schema_error = ""
    policy_schema_valid = True
    policy_schema_error = ""
    try:
        Draft202012Validator.check_schema(subject_schema)
    except Exception as exc:  # pragma: no cover - schema authorship
        subject_schema_valid = False
        subject_schema_error = str(exc)
    try:
        Draft202012Validator.check_schema(policy_schema)
    except Exception as exc:  # pragma: no cover - schema authorship
        policy_schema_valid = False
        policy_schema_error = str(exc)

    # determinism + byte-agreement
    deterministic = _canonical_bytes(material.render_subject()) == _canonical_bytes(material.render_subject())
    byte_identical = _canonical_bytes(material.render_subject()) == _canonical_bytes(frozen.build_subject())

    subject = material.render_subject()
    material_digest = material.subject_canonical_digest(subject)

    schema_errors = _validate_schema(subject, subject_schema)

    # frozen independent evaluator
    frozen_diag = frozen.diagnostics(copy.deepcopy(subject))
    frozen_passed = not frozen_diag

    # material checks
    material_diag = material.material_checks(copy.deepcopy(subject))

    # known-bad replay against the material subject
    fixture_results = []
    for path in sorted((ROOT / "evals/known_bad/frontier").glob("economics_*.json")):
        fixture = _load(path)
        case_id = fixture.get("case_id")
        expected = REGISTERED.get(case_id)
        if expected is None:
            fixture_results.append({"fixture": path.name, "case_id": case_id, "result": "SKIPPED_UNREGISTERED"})
            continue
        mutated = copy.deepcopy(subject)
        frozen.apply_mutation(mutated, fixture["mutation_id"])
        frozen_diag_i = frozenset(frozen.diagnostics(copy.deepcopy(mutated)))
        material_diag_i = frozenset(material.material_checks(copy.deepcopy(mutated)))
        frozen_detected = expected in frozen_diag_i
        material_detected = expected in material_diag_i
        fixture_results.append({
            "fixture": path.name,
            "case_id": case_id,
            "expected_diagnostic": expected,
            "frozen_detected": frozen_detected,
            "material_detected": material_detected,
            "frozen_extra": sorted(frozen_diag_i - {expected}),
            "material_extra": sorted(material_diag_i - {expected}),
            "result": "DETECTED_BOTH" if (frozen_detected and material_detected) else "SURVIVED",
        })
    fixture_ok = all(item.get("result") == "DETECTED_BOTH" for item in fixture_results)

    # material economic machinery determinism and resolution
    ecv_a = material.expected_net_value(copy.deepcopy(subject))
    ecv_b = material.expected_net_value(copy.deepcopy(subject))
    sens = material.sensitivity(copy.deepcopy(subject))
    fallback = material.downside_fallback(copy.deepcopy(subject))
    econ_deterministic = ecv_a == ecv_b
    econ_resolved = ecv_a["total_cost"] >= 0 and sens["total_cost"] == -1.0

    independence = scan_source_independence([
        ROOT / "src/cre_foundry/economics/__init__.py",
        ROOT / "src/cre_foundry/economics/engine.py",
    ])

    clean = (
        deterministic
        and byte_identical
        and not schema_errors
        and frozen_passed
        and not material_diag
        and not independence
    )

    passed = (
        subject_schema_valid
        and policy_schema_valid
        and clean
        and fixture_ok
        and econ_deterministic
        and econ_resolved
        and not independence
    )

    report = {
        "artifact_id": "ECONOMICS-001-MATERIAL-CONTRACT-VALIDATION",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "proof_level": 5,
        "evaluator_id": "economics-ecv-public-v1",
        "generated_at": _now(),
        "subject_task": "ECONOMICS-001",
        "passed": bool(passed),
        "results": {
            "determinism_byte_identical": bool(deterministic),
            "frozen_byte_identical": bool(byte_identical),
            "frozen_schema_errors": schema_errors,
            "frozen_evaluator": {
                "passed": bool(frozen_passed),
                "diagnostics": [d for d in frozen_diag],
            },
            "material_diagnostics": material_diag,
            "clean_object": bool(clean),
        },
        "subject_bindings": {
            "subject_sha256": material_digest,
            "schema_sha256": _load(ROOT / "artifacts/evaluations/economics_synthetic.json")["subject_hashes"]["contracts/commercial_economics.schema.json"],
        },
        "economic_machinery": {
            "expected_net_value": ecv_a,
            "sensitivity": sens,
            "downside_fallback": fallback,
            "deterministic": bool(econ_deterministic),
            "resolved": bool(econ_resolved),
        },
        "schemas": {
            "subject": {"path": "contracts/commercial_economics.schema.json", "draft2020_12_valid": subject_schema_valid, "error": subject_schema_error},
            "policy": {"path": "contracts/economic_engine.schema.json", "draft2020_12_valid": policy_schema_valid, "error": policy_schema_error},
        },
        "known_bad_fixtures": fixture_results,
        "source_independence": independence,
        "claims_not_established": list(material.ALL_CLAIM_NOT_ESTABLISHED),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())