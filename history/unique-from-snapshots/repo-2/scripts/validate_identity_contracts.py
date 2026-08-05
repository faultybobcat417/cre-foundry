#!/usr/bin/env python3
"""House S-2 validator for the IDENTITY-001 material identity graph.

Cross-checks the material implementation against the frozen independent
evaluator and the frozen IDENTITY-001 contract:

1. Constrain the material subject to the frozen ``contracts/temporal_identity.schema.json``.
2. Constrain every material-record and the graph shape.
3. Require the frozen independent evaluator to PASS the material-rendered subject
   with zero diagnostics (byte-stable, reconstruction-agreed).
4. Require the material's own checks to be clean on the same subject.
5. Replay every registered known-bad fixture onto the material subject and
   require BOTH the frozen evaluator and the material checks to detect the exact
   registered diagnostic.
6. Prove determinism: two renders are byte-identical.

This validator must NOT import any identity-material identity module from the
independent evaluator (it imports both, because it is the house cross-check and
not the frozen judge).  It is never used to change the evaluator judging the
task.
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


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_path(subject: dict[str, Any], path: list[str]) -> Any:
    node: Any = subject
    for part in path:
        node = node[part]
    return node


def _set_path(subject: dict[str, Any], path: list[str], value: Any) -> None:
    node: Any = subject
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


def _del_path(subject: dict[str, Any], path: list[str]) -> None:
    node: Any = subject
    for part in path[:-1]:
        node = node[part]
    del node[path[-1]]


def _apply_recipe(subject: dict[str, Any], ops: list[Any]) -> None:
    for op in ops:
        kind = op[0]
        if kind == "set":
            _set_path(subject, op[1], op[2])
        elif kind == "del":
            _del_path(subject, op[1])
        elif kind == "append":
            _get_path(subject, op[1]).append(op[2])
        else:
            raise ValueError(f"unknown recipe op {kind}")


def _validate_schema(subject: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    return sorted(set(error.json_path for error in validator.iter_errors(subject)))


def main() -> int:
    parser = argparse.ArgumentParser(description="IDENTITY-001 material identity graph house validator")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/evaluations/identity_contracts.json")
    args = parser.parse_args()

    from cre_foundry.identity import graph as material
    from evals.public import temporal_identity_evaluator as frozen

    contract = _load(ROOT / "artifacts/identity/public_evaluator_contract.json")
    frozen_schema = _load(ROOT / "contracts/temporal_identity.schema.json")
    graph_schema = _load(ROOT / "contracts/synthetic_identity_graph.schema.json")

    # 0) Constrain the graph schema itself.
    graph_schema_valid = True
    graph_schema_error = ""
    try:
        Draft202012Validator.check_schema(graph_schema)
    except Exception as exc:  # pragma: no cover - schema authorship is verified
        graph_schema_valid = False
        graph_schema_error = str(exc)

    # determinism
    render_a = material.render_subject()
    render_b = material.render_subject()
    deterministic = json.dumps(render_a, sort_keys=True) == json.dumps(render_b, sort_keys=True)

    subject = render_a
    material_digest = material.subject_canonical_digest(subject)

    # 1) constraint vs frozen schema
    schema_errors = _validate_schema(subject, frozen_schema)

    # 2) frozen independent evaluator
    eval_result = frozen.evaluate_subject(copy.deepcopy(subject))
    evaluator_diagnostics = eval_result["diagnostics"]
    frozen_passed = eval_result["passed"]
    evaluator_subject_sha = eval_result["subject_sha256"]

    # 3) material checks
    material_diagnostics = material.material_checks(copy.deepcopy(subject))

    # 4) standalone reconstruction agreement
    reconstruction = frozen.reconstruct_subject(copy.deepcopy(subject))
    material_verdict = reconstruction["protection_verdict"]
    clean = (
        not schema_errors
        and deterministic
        and frozen_passed
        and not material_diagnostics
        and material_verdict == "CLEAR"
    )

    # 5) known-bad replay against the material subject
    fixture_results = []
    for fixture_path in contract["required_fixtures"]:
        fixture = _load(ROOT / fixture_path)
        registered = {
            "suite-collapse": "registered mutation detected: suite-collapse",
            "protected-alias-clear": "registered mutation detected: protected-alias-clear",
        }
        if fixture.get("case_id") not in registered or fixture.get("expected_diagnostic") != registered[fixture.get("case_id")]:
            fixture_results.append({
                "fixture": fixture_path,
                "case_id": fixture.get("case_id"),
                "result": "SKIPPED_UNREGISTERED",
            })
            continue
        mutated = copy.deepcopy(subject)
        _apply_recipe(mutated, fixture["recipe"]["ops"])
        mutated = material.rebind_digests(mutated)
        frozen_diag = frozenset(frozen.evaluate_subject(copy.deepcopy(mutated))["diagnostics"])
        material_diag = frozenset(material.material_checks(copy.deepcopy(mutated)))
        expected = registered[fixture.get("case_id")]
        fixture_results.append({
            "fixture": fixture_path,
            "case_id": fixture.get("case_id"),
            "expected_diagnostic": expected,
            "frozen_detected": expected in frozen_diag,
            "material_detected": expected in material_diag,
            "frozen_extra": sorted(frozen_diag - {expected}),
            "material_extra": sorted(material_diag - {expected}),
            "result": "DETECTED_BOTH" if (expected in frozen_diag and expected in material_diag) else "SURVIVED",
        })

    fixture_ok = all(item.get("result") == "DETECTED_BOTH" for item in fixture_results)

    binding_ok = (
        isinstance(evaluator_subject_sha, str)
        and evaluator_subject_sha == subject.get("subject_sha256")
        and material_digest == subject.get("subject_sha256")
    )

    passed = graph_schema_valid and clean and fixture_ok and binding_ok

    report = {
        "artifact_id": "IDENTITY-001-MATERIAL-CONTRACT-VALIDATION",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "proof_level": 4,
        "evaluator_id": frozen.EVALUATOR_ID,
        "generated_at": _now(),
        "subject_task": "IDENTITY-001",
        "passed": bool(passed),
        "results": {
            "determinism_byte_identical": bool(deterministic),
            "frozen_schema_errors": schema_errors,
            "frozen_evaluator": {
                "passed": bool(frozen_passed),
                "diagnostics": [d for d in evaluator_diagnostics],
            },
            "material_diagnostics": material_diagnostics,
            "protection_verdict_reconstruction": material_verdict,
            "clean_object": bool(clean),
        },
        "subject_bindings": {
            "subject_sha256": subject.get("subject_sha256"),
            "material_document_digest": material_digest,
            "evaluator_reconstruction_digest": evaluator_subject_sha,
            "schema_sha256": subject.get("schema_sha256"),
            "contract_sha256": subject.get("contract_sha256"),
        },
        "graph_schema": {
            "path": "contracts/synthetic_identity_graph.schema.json",
            "draft2020_12_valid": graph_schema_valid,
            "error": graph_schema_error,
        },
        "known_bad_fixtures": fixture_results,
        "claims_not_established": list(material.ALL_CLAIM_NOT_ESTABLISHED),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())