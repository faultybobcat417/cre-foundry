"""Independent synthetic REPLAY-001 material implementation.

This module does not import the frozen or legacy evaluator. It implements
deterministic replay, idempotency, bounded crash recovery, compatibility,
restore verification, and rollback verification using synthetic,
non-influencing records only.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

CLAIM_CEILING = (
    "Synthetic REPLAY-001 conformance only; "
    "no production availability, durability, "
    "disaster recovery, recovery-time, migration, "
    "persistence, or deployment claim."
)

CLAIMS_NOT_ESTABLISHED = (
    "production availability",
    "production durability",
    "production disaster recovery",
    "production recovery time",
    "production persistence correctness",
    "live migration safety",
    "deployment readiness",
    "sealed evaluator independence",
)


def canonical_bytes(value: Any) -> bytes:
    """Serialize a value into stable canonical UTF-8 JSON."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return the SHA-256 digest of canonical JSON."""

    return hashlib.sha256(
        canonical_bytes(value)
    ).hexdigest()


def synthetic_input() -> dict[str, Any]:
    """Return the fixed synthetic replay input."""

    return {
        "task": "REPLAY-001",
        "candidate_ids": [
            f"C{index:02d}"
            for index in range(10)
        ],
        "as_of": "2026-08-04T00:00:00Z",
    }


def deterministic_output(
    replay_input: dict[str, Any],
) -> dict[str, Any]:
    """Create the deterministic output for a replay input."""

    candidate_ids = list(
        replay_input["candidate_ids"]
    )

    if len(candidate_ids) != 10:
        raise ValueError(
            "synthetic replay requires exactly ten candidates"
        )

    return {
        "decision": "ISSUE_SYNTHETIC",
        "candidate_ids": candidate_ids,
        "count": 10,
    }


def execute_idempotent_effect(
    ledger: list[dict[str, Any]],
    *,
    idempotency_key: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Record one effect or return its prior idempotent result."""

    effect_sha256 = digest(payload)

    for existing in ledger:
        if (
            existing["idempotency_key"]
            != idempotency_key
        ):
            continue

        if (
            existing["effect_sha256"]
            != effect_sha256
        ):
            raise ValueError(
                "idempotency key reused with different payload"
            )

        return copy.deepcopy(existing), False

    record = {
        "effect_id": (
            f"EFF-{len(ledger) + 1:03d}"
        ),
        "idempotency_key": idempotency_key,
        "effect_sha256": effect_sha256,
    }

    ledger.append(copy.deepcopy(record))
    return record, True


def recover_journal(
    *,
    journal_state: str,
    expected_output_sha256: str,
) -> dict[str, Any]:
    """Fail closed and deterministically resume a prepared journal."""

    if journal_state not in {
        "COMMITTED",
        "PREPARED",
        "ABORTED",
    }:
        raise ValueError("unsupported journal state")

    if journal_state == "ABORTED":
        return {
            "journal_state": "ABORTED",
            "partial_state_accepted": False,
            "resumed": False,
            "resume_output_sha256": (
                expected_output_sha256
            ),
        }

    return {
        "journal_state": "COMMITTED",
        "partial_state_accepted": False,
        "resumed": True,
        "resume_output_sha256": (
            expected_output_sha256
        ),
    }


def verify_restore(
    *,
    backup_payload: dict[str, Any],
    restored_payload: dict[str, Any],
) -> dict[str, Any]:
    """Bind a restored payload to its synthetic backup."""

    backup_sha256 = digest(backup_payload)
    restored_sha256 = digest(restored_payload)

    return {
        "backup_sha256": backup_sha256,
        "restored_sha256": restored_sha256,
        "verified": (
            backup_sha256 == restored_sha256
        ),
    }


def verify_rollback(
    *,
    prior_version: str,
    attempted_from_version: str,
    restored_version: str,
) -> dict[str, Any]:
    """Record whether rollback restored the prior version."""

    return {
        "prior_version": prior_version,
        "attempted_from_version": (
            attempted_from_version
        ),
        "restored_version": restored_version,
        "verified": (
            restored_version == prior_version
        ),
    }


def render_subject() -> dict[str, Any]:
    """Render the canonical synthetic REPLAY-001 posture."""

    replay_input = synthetic_input()
    output = deterministic_output(replay_input)

    input_sha256 = digest(replay_input)
    output_sha256 = digest(output)

    ledger: list[dict[str, Any]] = []

    execute_idempotent_effect(
        ledger,
        idempotency_key="IDEM-REPLAY-001",
        payload=output,
    )

    prior_snapshot = {
        "schema_version": "1.0.0",
        "payload_sha256": output_sha256,
    }

    restore = verify_restore(
        backup_payload=prior_snapshot,
        restored_payload=copy.deepcopy(
            prior_snapshot
        ),
    )

    return {
        "document_kind": "REPLAY_RECOVERY_POSTURE",
        "schema_version": "1.0.0",
        "execution_scope": (
            "SYNTHETIC_NON_INFLUENCING"
        ),
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "input_sha256": input_sha256,
        "original_output_sha256": output_sha256,
        "replay_output_sha256": digest(
            deterministic_output(
                copy.deepcopy(replay_input)
            )
        ),
        "effects": ledger,
        "crash_recovery": recover_journal(
            journal_state="COMMITTED",
            expected_output_sha256=output_sha256,
        ),
        "snapshots": [
            {
                "snapshot_id": "SNAP-001",
                "schema_version": "1.0.0",
                "content_sha256": restore[
                    "backup_sha256"
                ],
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
        "restore": restore,
        "rollback": verify_rollback(
            prior_version="1.0.0",
            attempted_from_version="2.0.0",
            restored_version="1.0.0",
        ),
        "claim_ceiling": CLAIM_CEILING,
    }


def recovery_checks(
    subject: dict[str, Any],
) -> list[str]:
    """Independently evaluate REPLAY-001 semantics."""

    if not isinstance(subject, dict):
        return ["REPLAY-SHAPE-INVALID"]

    value = copy.deepcopy(subject)
    errors: list[str] = []

    original = value.get(
        "original_output_sha256"
    )
    replay = value.get(
        "replay_output_sha256"
    )

    if not original or replay != original:
        errors.append("REPLAY-OUTPUT-MISMATCH")

    effects = value.get("effects", [])
    idempotency_keys: list[Any] = []

    if isinstance(effects, list):
        idempotency_keys = [
            effect.get("idempotency_key")
            for effect in effects
            if isinstance(effect, dict)
        ]

    if len(idempotency_keys) != len(
        set(idempotency_keys)
    ):
        errors.append("REPLAY-DUPLICATE-EFFECT")

    crash = value.get("crash_recovery", {})

    if (
        not isinstance(crash, dict)
        or crash.get("journal_state")
        != "COMMITTED"
        or crash.get(
            "partial_state_accepted"
        )
        is not False
        or crash.get("resumed") is not True
        or crash.get(
            "resume_output_sha256"
        )
        != original
    ):
        errors.append("REPLAY-PARTIAL-CRASH")

    compatibility = value.get(
        "compatibility",
        {},
    )

    supported_versions = (
        compatibility.get(
            "supported_read_versions",
            [],
        )
        if isinstance(compatibility, dict)
        else []
    )

    snapshots = value.get("snapshots", [])

    if (
        not isinstance(snapshots, list)
        or any(
            not isinstance(snapshot, dict)
            or snapshot.get("readable")
            is not True
            or snapshot.get(
                "schema_version"
            )
            not in supported_versions
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
        or migration.get("compatible")
        is not True
        or migration.get(
            "rollback_defined"
        )
        is not True
        or migration.get("from_version")
        not in supported_versions
        or migration.get("to_version")
        != compatibility.get(
            "current_schema_version"
        )
    ):
        errors.append(
            "REPLAY-MIGRATION-INCOMPATIBLE"
        )

    restore = value.get("restore", {})

    if (
        not isinstance(restore, dict)
        or restore.get("verified")
        is not True
        or restore.get("backup_sha256")
        != restore.get("restored_sha256")
        or not snapshots
        or restore.get("backup_sha256")
        != snapshots[0].get(
            "content_sha256"
        )
    ):
        errors.append("REPLAY-RESTORE-MISMATCH")

    rollback = value.get("rollback", {})

    if (
        not isinstance(rollback, dict)
        or rollback.get("verified")
        is not True
        or rollback.get(
            "restored_version"
        )
        != rollback.get("prior_version")
        or rollback.get(
            "attempted_from_version"
        )
        != compatibility.get(
            "current_schema_version"
        )
    ):
        errors.append("REPLAY-ROLLBACK-FAILURE")

    if value.get("live_permissions") is not False:
        errors.append("REPLAY-LIVE-DEFAULT")

    if (
        value.get("external_effect_occurred")
        is not False
    ):
        errors.append("REPLAY-EXTERNAL-EFFECT")

    if (
        value.get("proof_level") != 4
        or value.get("claim_ceiling")
        != CLAIM_CEILING
    ):
        errors.append("REPLAY-CLAIM-CEILING")

    return sorted(set(errors))
