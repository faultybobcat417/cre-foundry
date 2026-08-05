"""Independent frozen public evaluator for REPLAY-001."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/replay_recovery.schema.json"

EVALUATOR_ID = "replay-recovery-posture-public-v1"

CLAIM_CEILING = (
    "Synthetic REPLAY-001 conformance only; "
    "no production availability, durability, "
    "disaster recovery, recovery-time, migration, "
    "persistence, or deployment claim."
)


def strict_load_json(path: Path) -> dict[str, Any]:
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


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(
        canonical_bytes(value)
    ).hexdigest()


def build_clean_subject() -> dict[str, Any]:
    synthetic_input = {
        "task": "REPLAY-001",
        "candidate_ids": [
            f"C{index:02d}"
            for index in range(10)
        ],
        "as_of": "2026-08-04T00:00:00Z",
    }

    synthetic_output = {
        "decision": "ISSUE_SYNTHETIC",
        "candidate_ids": synthetic_input[
            "candidate_ids"
        ],
        "count": 10,
    }

    input_sha = digest(synthetic_input)
    output_sha = digest(synthetic_output)

    prior_snapshot = {
        "schema_version": "1.0.0",
        "payload_sha256": output_sha,
    }

    backup_sha = digest(prior_snapshot)

    return {
        "document_kind": "REPLAY_RECOVERY_POSTURE",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "input_sha256": input_sha,
        "original_output_sha256": output_sha,
        "replay_output_sha256": output_sha,
        "effects": [
            {
                "effect_id": "EFF-001",
                "idempotency_key": "IDEM-REPLAY-001",
                "effect_sha256": output_sha,
            }
        ],
        "crash_recovery": {
            "journal_state": "COMMITTED",
            "partial_state_accepted": False,
            "resumed": True,
            "resume_output_sha256": output_sha,
        },
        "snapshots": [
            {
                "snapshot_id": "SNAP-001",
                "schema_version": "1.0.0",
                "content_sha256": backup_sha,
                "readable": True,
            }
        ],
        "compatibility": {
            "current_schema_version": "2.0.0",
            "supported_read_versions": [
                "1.0.0",
                "2.0.0",
            ],
            "migration": {
                "from_version": "1.0.0",
                "to_version": "2.0.0",
                "compatible": True,
                "rollback_defined": True,
            },
        },
        "restore": {
            "backup_sha256": backup_sha,
            "restored_sha256": backup_sha,
            "verified": True,
        },
        "rollback": {
            "prior_version": "1.0.0",
            "attempted_from_version": "2.0.0",
            "restored_version": "1.0.0",
            "verified": True,
        },
        "claim_ceiling": CLAIM_CEILING,
    }


def apply_mutation(
    subject: dict[str, Any],
    mutation_id: str,
) -> None:
    if mutation_id == "replay_output_mismatch":
        subject["replay_output_sha256"] = "f" * 64
    elif mutation_id == "duplicate_effect":
        subject["effects"].append(
            {
                "effect_id": "EFF-002",
                "idempotency_key": "IDEM-REPLAY-001",
                "effect_sha256": (
                    subject["original_output_sha256"]
                ),
            }
        )
    elif mutation_id == "partial_crash":
        subject["crash_recovery"].update(
            {
                "journal_state": "PREPARED",
                "partial_state_accepted": True,
                "resumed": False,
            }
        )
    elif mutation_id == "old_snapshot_unreadable":
        subject["snapshots"][0]["readable"] = False
    elif mutation_id == "migration_incompatible":
        subject["compatibility"]["migration"][
            "compatible"
        ] = False
    elif mutation_id == "restore_mismatch":
        subject["restore"]["restored_sha256"] = (
            "e" * 64
        )
    elif mutation_id == "rollback_failure":
        subject["rollback"]["verified"] = False
    else:
        raise ValueError(
            f"unsupported mutation recipe: {mutation_id}"
        )


def diagnostics(
    subject: dict[str, Any],
) -> list[str]:
    if not isinstance(subject, dict):
        return ["REPLAY-SHAPE-INVALID"]

    errors: list[str] = []

    original = subject.get("original_output_sha256")
    replay = subject.get("replay_output_sha256")

    if not original or replay != original:
        errors.append("REPLAY-OUTPUT-MISMATCH")

    effects = subject.get("effects", [])
    keys: list[Any] = []

    if isinstance(effects, list):
        keys = [
            effect.get("idempotency_key")
            for effect in effects
            if isinstance(effect, dict)
        ]

    if len(keys) != len(set(keys)):
        errors.append("REPLAY-DUPLICATE-EFFECT")

    crash = subject.get("crash_recovery", {})

    if (
        not isinstance(crash, dict)
        or crash.get("journal_state") != "COMMITTED"
        or crash.get("partial_state_accepted") is not False
        or crash.get("resumed") is not True
        or crash.get("resume_output_sha256") != original
    ):
        errors.append("REPLAY-PARTIAL-CRASH")

    compatibility = subject.get("compatibility", {})
    supported = (
        compatibility.get("supported_read_versions", [])
        if isinstance(compatibility, dict)
        else []
    )

    snapshots = subject.get("snapshots", [])

    if (
        not isinstance(snapshots, list)
        or any(
            not isinstance(snapshot, dict)
            or snapshot.get("readable") is not True
            or snapshot.get("schema_version")
            not in supported
            for snapshot in snapshots
        )
    ):
        errors.append(
            "REPLAY-OLD-SNAPSHOT-UNREADABLE"
        )

    migration = (
        compatibility.get("migration", {})
        if isinstance(compatibility, dict)
        else {}
    )

    if (
        not isinstance(migration, dict)
        or migration.get("compatible") is not True
        or migration.get("rollback_defined") is not True
        or migration.get("from_version") not in supported
        or migration.get("to_version")
        != compatibility.get("current_schema_version")
    ):
        errors.append(
            "REPLAY-MIGRATION-INCOMPATIBLE"
        )

    restore = subject.get("restore", {})

    if (
        not isinstance(restore, dict)
        or restore.get("verified") is not True
        or restore.get("backup_sha256")
        != restore.get("restored_sha256")
        or not snapshots
        or restore.get("backup_sha256")
        != snapshots[0].get("content_sha256")
    ):
        errors.append("REPLAY-RESTORE-MISMATCH")

    rollback = subject.get("rollback", {})

    if (
        not isinstance(rollback, dict)
        or rollback.get("verified") is not True
        or rollback.get("restored_version")
        != rollback.get("prior_version")
        or rollback.get("attempted_from_version")
        != compatibility.get("current_schema_version")
    ):
        errors.append("REPLAY-ROLLBACK-FAILURE")

    if subject.get("live_permissions") is not False:
        errors.append("REPLAY-LIVE-DEFAULT")

    if (
        subject.get("external_effect_occurred")
        is not False
    ):
        errors.append("REPLAY-EXTERNAL-EFFECT")

    if (
        subject.get("proof_level") != 4
        or subject.get("claim_ceiling")
        != CLAIM_CEILING
    ):
        errors.append("REPLAY-CLAIM-CEILING")

    return sorted(set(errors))


def evaluate_subject(
    subject: dict[str, Any],
) -> dict[str, Any]:
    semantic = diagnostics(copy.deepcopy(subject))

    schema = strict_load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)

    schema_errors = list(
        Draft202012Validator(schema).iter_errors(
            subject
        )
    )

    if semantic:
        result_diagnostics = semantic
    elif schema_errors:
        result_diagnostics = ["REPLAY-SCHEMA"]
    else:
        result_diagnostics = []

    return {
        "passed": not result_diagnostics,
        "diagnostics": result_diagnostics,
        "schema_error_count": len(schema_errors),
    }
