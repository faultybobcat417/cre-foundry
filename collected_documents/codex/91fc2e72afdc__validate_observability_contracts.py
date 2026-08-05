#!/usr/bin/env python3
"""House cross-validator for OBSERVABILITY-001."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

LEGACY_BINDINGS = {
    "contracts/lineage_manifest.schema.json":
        "a6c9c49b065dd3e750b77cf7846900dc692f21e49ed708c1e60bb601ed4a789e",
    "scripts/validate_observability_lineage.py":
        "d74660193693a1f6453d90eb4db8c38f331a5e629e152edc3e81c486a0684dbd",
    "artifacts/evaluations/observability_lineage.json":
        "1770d49540b1b8e3dd590a20f3b035842d3512f86cf8f5835dfd0c310a232b14",
    "evals/known_bad/frontier/lineage_missing_asof.json":
        "8e43bbcb313b2b7011ece12ef3c5b362e0dda343a2316f9d64c63c22e567e5a2",
    "evals/known_bad/frontier/lineage_protected_log.json":
        "701bc129a08f31e8b801467dc1c0d38bfac09ab2eefda21981387ff5687d6979",
}


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
        raise ValueError(f"{path} must contain an object")

    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material_independence(
    path: Path,
) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    forbidden = (
        "observability_posture_evaluator",
        "validate_observability_posture",
        "validate_observability_lineage",
        "_frontier_domain_common",
    )

    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                alias.name for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    forbidden_imports = [
        name
        for name in imports
        if any(fragment in name for fragment in forbidden)
    ]

    forbidden_references = [
        fragment
        for fragment in forbidden
        if fragment in source
    ]

    return {
        "passed": (
            not forbidden_imports
            and not forbidden_references
        ),
        "forbidden_imports": forbidden_imports,
        "forbidden_references": forbidden_references,
    }


def chain_is_complete(
    artifacts: list[dict[str, Any]],
    required_stages: list[str],
) -> bool:
    if [
        artifact.get("stage")
        for artifact in artifacts
    ] != required_stages:
        return False

    for index, artifact in enumerate(artifacts):
        expected_parents = (
            []
            if index == 0
            else [
                artifacts[index - 1]["artifact_id"]
            ]
        )

        if artifact.get("parents") != expected_parents:
            return False

    return True


def build_report() -> dict[str, Any]:
    from cre_foundry.observability import (
        lineage as material,
    )
    from evals.public import (
        observability_posture_evaluator as frozen,
    )

    contract_path = (
        ROOT
        / "artifacts/observability/"
        "public_evaluator_contract.json"
    )
    schema_path = (
        ROOT
        / "contracts/observability_posture.schema.json"
    )
    material_path = (
        ROOT
        / "src/cre_foundry/observability/lineage.py"
    )
    evaluator_path = (
        ROOT
        / "evals/public/"
        "observability_posture_evaluator.py"
    )

    contract = strict_load(contract_path)
    schema = strict_load(schema_path)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    subject_a = material.render_subject()
    subject_b = material.render_subject()
    frozen_clean = frozen.build_clean_subject()

    deterministic = (
        material.canonical_bytes(subject_a)
        == material.canonical_bytes(subject_b)
    )

    schema_errors = sorted(
        {
            error.json_path
            for error in validator.iter_errors(subject_a)
        }
    )

    frozen_clean_result = frozen.evaluate_subject(
        copy.deepcopy(subject_a)
    )
    material_clean_diagnostics = (
        material.lineage_checks(
            copy.deepcopy(subject_a)
        )
    )

    decision = subject_a["decision"]
    artifacts = decision["artifacts"]

    complete_chain = chain_is_complete(
        artifacts,
        list(material.REQUIRED_STAGES),
    )

    correlation_complete = (
        bool(decision["correlation_id"])
        and all(
            entry["correlation_id"]
            == decision["correlation_id"]
            for entry in subject_a["logs"]
        )
    )

    replay_digest = material.expected_replay_digest(
        decision
    )
    replay_complete = (
        decision["replay_identity"][
            "algorithm"
        ]
        == "sha256"
        and decision["replay_identity"][
            "canonical_input_sha256"
        ]
        == replay_digest
        and decision["replay_identity"][
            "replay_id"
        ]
        == f"replay_{replay_digest}"
    )

    artifact_bindings_complete = all(
        artifact.get("artifact_id")
        and artifact.get("owner")
        and artifact.get("version")
        and artifact.get("as_of")
        and len(
            artifact.get("content_sha256", "")
        )
        == 64
        for artifact in artifacts
    )

    clean_passed = (
        deterministic
        and not schema_errors
        and subject_a == frozen_clean
        and frozen_clean_result["passed"] is True
        and frozen_clean_result["diagnostics"] == []
        and material_clean_diagnostics == []
        and len(artifacts) == 9
        and complete_chain
        and correlation_complete
        and replay_complete
        and artifact_bindings_complete
        and subject_a["live_permissions"] is False
        and subject_a[
            "external_effect_occurred"
        ]
        is False
    )

    mutation_results: list[dict[str, Any]] = []

    for relative in contract["required_fixtures"]:
        fixture_path = ROOT / relative
        fixture = strict_load(fixture_path)

        mutated = copy.deepcopy(subject_a)

        frozen.apply_mutation(
            mutated,
            fixture["mutation_id"],
        )

        expected = fixture[
            "expected_diagnostic"
        ]

        frozen_diagnostics = (
            frozen.evaluate_subject(
                copy.deepcopy(mutated)
            )["diagnostics"]
        )

        material_diagnostics = (
            material.lineage_checks(
                copy.deepcopy(mutated)
            )
        )

        detected = (
            frozen_diagnostics == [expected]
            and material_diagnostics == [expected]
        )

        mutation_results.append(
            {
                "fixture": relative,
                "fixture_sha256": file_sha256(
                    fixture_path
                ),
                "case_id": fixture["case_id"],
                "mutation_id": fixture[
                    "mutation_id"
                ],
                "expected_diagnostic": expected,
                "frozen_diagnostics": (
                    frozen_diagnostics
                ),
                "material_diagnostics": (
                    material_diagnostics
                ),
                "result": (
                    "DETECTED_BOTH"
                    if detected
                    else "SURVIVED"
                ),
            }
        )

    mutation_passed = (
        len(mutation_results) == 7
        and all(
            result["result"] == "DETECTED_BOTH"
            for result in mutation_results
        )
    )

    protected_log_rejected = False
    secret_log_rejected = False

    try:
        material.log_event(
            level="info",
            message="protected detail",
            correlation_id="run_obs_001",
            payload=["account_001"],
        )
    except ValueError:
        protected_log_rejected = True

    try:
        material.log_event(
            level="info",
            message="secret detail",
            correlation_id="run_obs_001",
            payload=["secret_test_value"],
        )
    except ValueError:
        secret_log_rejected = True

    independence = material_independence(
        material_path
    )

    legacy_results = {
        relative: {
            "expected_sha256": expected,
            "actual_sha256": file_sha256(
                ROOT / relative
            ),
            "preserved": (
                file_sha256(ROOT / relative)
                == expected
            ),
        }
        for relative, expected
        in LEGACY_BINDINGS.items()
    }

    legacy_preserved = all(
        item["preserved"]
        for item in legacy_results.values()
    )

    passed = (
        clean_passed
        and mutation_passed
        and protected_log_rejected
        and secret_log_rejected
        and independence["passed"]
        and legacy_preserved
    )

    return {
        "artifact_id": (
            "OBSERVABILITY-001-"
            "MATERIAL-CONTRACT-VALIDATION"
        ),
        "schema_version": "1.0.0",
        "task_id": "OBSERVABILITY-001",
        "execution_scope": (
            "SYNTHETIC_NON_INFLUENCING"
        ),
        "proof_level": 4,
        "result": "PASS" if passed else "FAIL",
        "passed": passed,
        "evaluator_id": frozen.EVALUATOR_ID,
        "clean_subject": {
            "passed": clean_passed,
            "deterministic": deterministic,
            "schema_errors": schema_errors,
            "material_equals_frozen": (
                subject_a == frozen_clean
            ),
            "frozen_passed": (
                frozen_clean_result["passed"]
            ),
            "frozen_diagnostics": (
                frozen_clean_result[
                    "diagnostics"
                ]
            ),
            "material_diagnostics": (
                material_clean_diagnostics
            ),
            "lineage_stage_count": len(
                artifacts
            ),
            "complete_chain": complete_chain,
            "artifact_bindings_complete": (
                artifact_bindings_complete
            ),
            "correlation_complete": (
                correlation_complete
            ),
            "replay_identity_complete": (
                replay_complete
            ),
            "live_permissions": subject_a[
                "live_permissions"
            ],
            "external_effect_occurred": (
                subject_a[
                    "external_effect_occurred"
                ]
            ),
        },
        "mutation_results": mutation_results,
        "registered_mutation_count": len(
            mutation_results
        ),
        "registered_mutations_detected": sum(
            item["result"] == "DETECTED_BOTH"
            for item in mutation_results
        ),
        "sensitive_log_controls": {
            "protected_log_rejected": (
                protected_log_rejected
            ),
            "secret_log_rejected": (
                secret_log_rejected
            ),
            "passed": (
                protected_log_rejected
                and secret_log_rejected
            ),
        },
        "material_independence": independence,
        "legacy_boundary": {
            "passed": legacy_preserved,
            "bindings": legacy_results,
        },
        "bindings": {
            "contract_sha256": file_sha256(
                contract_path
            ),
            "schema_sha256": file_sha256(
                schema_path
            ),
            "material_sha256": file_sha256(
                material_path
            ),
            "frozen_evaluator_sha256": (
                file_sha256(evaluator_path)
            ),
            "material_subject_sha256": (
                hashlib.sha256(
                    material.canonical_bytes(
                        subject_a
                    )
                ).hexdigest()
            ),
            "replay_input_sha256": (
                replay_digest
            ),
        },
        "claims_not_established": list(
            material.CLAIMS_NOT_ESTABLISHED
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=(
            ROOT
            / "artifacts/evaluations/"
            "observability_contracts.json"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
    )
    args = parser.parse_args()

    report = build_report()

    if not args.check_only:
        serialized = (
            json.dumps(
                report,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        args.out.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
            not args.out.exists()
            or args.out.read_text(
                encoding="utf-8"
            )
            != serialized
        ):
            temporary = args.out.with_suffix(
                args.out.suffix + ".tmp"
            )
            temporary.write_text(
                serialized,
                encoding="utf-8",
            )
            temporary.replace(args.out)

    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
