#!/usr/bin/env python3
"""Independent house cross-validator for REPLAY-001."""

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
    "docs/reliability/recovery_and_migrations.md":
        "95043ee59143244359d7eb2f2bc884e148810b073bfb1341b44ca7d2dc8e4880",
    "scripts/validate_replay_recovery.py":
        "0ee3aa0fed0b9a75c0e3e5105da2aa2cd43d82a52bf5d3502735d0ab03a001d7",
    "artifacts/evaluations/replay_recovery.json":
        "fb5b6a27faa2e19fd265d128d0ddfb2b9208d214c24c275170a1cee56171b24a",
    "evals/known_bad/frontier/replay_duplicate_effect.json":
        "cbff44e2f96a6ac5116cfb79170299fa279f7419239cfb85dce838b020da4030",
    "evals/known_bad/frontier/replay_old_snapshot.json":
        "dc27c65f43faf89874405f83ee4aec35e7aabb5ad6dd210390084a98e0075628",
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
        "replay_recovery_evaluator",
        "validate_replay_posture",
        "validate_replay_recovery",
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


def primitive_checks(
    material: Any,
    clean_subject: dict[str, Any],
) -> dict[str, Any]:
    ledger: list[dict[str, Any]] = []
    payload = material.deterministic_output(
        material.synthetic_input()
    )

    first, first_created = (
        material.execute_idempotent_effect(
            ledger,
            idempotency_key="IDEM-HOUSE-001",
            payload=payload,
        )
    )

    second, second_created = (
        material.execute_idempotent_effect(
            ledger,
            idempotency_key="IDEM-HOUSE-001",
            payload=copy.deepcopy(payload),
        )
    )

    conflict_rejected = False

    try:
        material.execute_idempotent_effect(
            ledger,
            idempotency_key="IDEM-HOUSE-001",
            payload={"different": True},
        )
    except ValueError:
        conflict_rejected = True

    prepared = material.recover_journal(
        journal_state="PREPARED",
        expected_output_sha256=(
            clean_subject[
                "original_output_sha256"
            ]
        ),
    )

    aborted = material.recover_journal(
        journal_state="ABORTED",
        expected_output_sha256=(
            clean_subject[
                "original_output_sha256"
            ]
        ),
    )

    idempotent_retry = (
        first_created is True
        and second_created is False
        and first == second
        and len(ledger) == 1
    )

    prepared_recovery = (
        prepared["journal_state"] == "COMMITTED"
        and prepared["partial_state_accepted"] is False
        and prepared["resumed"] is True
        and prepared["resume_output_sha256"]
        == clean_subject["original_output_sha256"]
    )

    aborted_fail_closed = (
        aborted["journal_state"] == "ABORTED"
        and aborted["partial_state_accepted"] is False
        and aborted["resumed"] is False
    )

    restore_verified = (
        clean_subject["restore"]["verified"] is True
        and clean_subject["restore"]["backup_sha256"]
        == clean_subject["restore"]["restored_sha256"]
    )

    rollback_verified = (
        clean_subject["rollback"]["verified"] is True
        and clean_subject["rollback"]["restored_version"]
        == clean_subject["rollback"]["prior_version"]
    )

    return {
        "passed": all(
            [
                idempotent_retry,
                conflict_rejected,
                prepared_recovery,
                aborted_fail_closed,
                restore_verified,
                rollback_verified,
            ]
        ),
        "idempotent_retry": idempotent_retry,
        "idempotency_conflict_rejected": (
            conflict_rejected
        ),
        "prepared_recovery": prepared_recovery,
        "aborted_fail_closed": aborted_fail_closed,
        "restore_verified": restore_verified,
        "rollback_verified": rollback_verified,
    }


def build_report() -> dict[str, Any]:
    from cre_foundry.replay import (
        recovery as material,
    )
    from evals.public import (
        replay_recovery_evaluator as frozen,
    )

    contract_path = (
        ROOT
        / "artifacts/replay/"
        "public_evaluator_contract.json"
    )
    schema_path = (
        ROOT
        / "contracts/replay_recovery.schema.json"
    )
    material_path = (
        ROOT
        / "src/cre_foundry/replay/recovery.py"
    )
    evaluator_path = (
        ROOT
        / "evals/public/"
        "replay_recovery_evaluator.py"
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
            for error in validator.iter_errors(
                subject_a
            )
        }
    )

    frozen_result = frozen.evaluate_subject(
        copy.deepcopy(subject_a)
    )

    material_diagnostics = (
        material.recovery_checks(
            copy.deepcopy(subject_a)
        )
    )

    output_identity = (
        subject_a["original_output_sha256"]
        == subject_a["replay_output_sha256"]
    )

    effect_count = len(subject_a["effects"])
    unique_idempotency_keys = (
        len(
            {
                row["idempotency_key"]
                for row in subject_a["effects"]
            }
        )
        == effect_count
    )

    snapshot_compatibility = all(
        snapshot["readable"] is True
        and snapshot["schema_version"]
        in subject_a["compatibility"][
            "supported_read_versions"
        ]
        for snapshot in subject_a["snapshots"]
    )

    migration_safe = (
        subject_a["compatibility"]["migration"][
            "compatible"
        ]
        is True
        and subject_a["compatibility"]["migration"][
            "rollback_defined"
        ]
        is True
    )

    clean_passed = (
        deterministic
        and not schema_errors
        and subject_a == frozen_clean
        and frozen_result["passed"] is True
        and frozen_result["diagnostics"] == []
        and material_diagnostics == []
        and output_identity
        and effect_count == 1
        and unique_idempotency_keys
        and snapshot_compatibility
        and migration_safe
        and subject_a["restore"]["verified"] is True
        and subject_a["rollback"]["verified"] is True
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

        material_mutation_diagnostics = (
            material.recovery_checks(
                copy.deepcopy(mutated)
            )
        )

        detected = (
            frozen_diagnostics == [expected]
            and material_mutation_diagnostics
            == [expected]
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
                    material_mutation_diagnostics
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
            row["result"] == "DETECTED_BOTH"
            for row in mutation_results
        )
    )

    primitives = primitive_checks(
        material,
        subject_a,
    )

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
        row["preserved"]
        for row in legacy_results.values()
    )

    passed = (
        clean_passed
        and mutation_passed
        and primitives["passed"]
        and independence["passed"]
        and legacy_preserved
    )

    return {
        "artifact_id": (
            "REPLAY-001-MATERIAL-CONTRACT-VALIDATION"
        ),
        "schema_version": "1.0.0",
        "task_id": "REPLAY-001",
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
                frozen_result["passed"]
            ),
            "frozen_diagnostics": (
                frozen_result["diagnostics"]
            ),
            "material_diagnostics": (
                material_diagnostics
            ),
            "output_identity": output_identity,
            "effect_count": effect_count,
            "unique_idempotency_keys": (
                unique_idempotency_keys
            ),
            "snapshot_compatibility": (
                snapshot_compatibility
            ),
            "migration_safe": migration_safe,
            "restore_verified": subject_a[
                "restore"
            ]["verified"],
            "rollback_verified": subject_a[
                "rollback"
            ]["verified"],
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
            row["result"] == "DETECTED_BOTH"
            for row in mutation_results
        ),
        "primitive_checks": primitives,
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
            "input_sha256": subject_a[
                "input_sha256"
            ],
            "output_sha256": subject_a[
                "original_output_sha256"
            ],
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
            "replay_contracts.json"
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
