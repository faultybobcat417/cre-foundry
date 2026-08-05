"""Independent synthetic OBSERVABILITY-001 material implementation.

This module does not import evaluator or legacy validation code. It creates
deterministic, non-sensitive, non-influencing lineage records only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable

CLAIM_CEILING = (
    "Synthetic OBSERVABILITY-001 conformance only; "
    "no production telemetry, durability, recovery, "
    "operational completeness, sealed evaluation, "
    "or deployment claim."
)

CLAIMS_NOT_ESTABLISHED = (
    "production telemetry completeness",
    "production durability",
    "production recovery",
    "operational observability effectiveness",
    "sealed evaluator independence",
    "external hidden-holdout performance",
    "deployment readiness",
)

REQUIRED_STAGES = (
    "source",
    "snapshot",
    "identity",
    "feature",
    "model",
    "policy",
    "route",
    "evaluator",
    "outcome",
)

SENSITIVE_PREFIXES = (
    "account_",
    "addr_",
    "contact_",
    "email_",
    "phone_",
    "secret_",
    "credential_",
    "token_",
    "password_",
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    """Return stable canonical UTF-8 JSON bytes."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def is_sensitive_token(token: Any) -> bool:
    """Classify synthetic tokens conservatively."""

    return (
        not isinstance(token, str)
        or token.startswith(SENSITIVE_PREFIXES)
    )


def log_event(
    *,
    level: str,
    message: str,
    correlation_id: str,
    payload: Iterable[str] = (),
) -> dict[str, Any]:
    """Create a correlated general-log event or reject sensitive payloads."""

    if level not in {
        "debug",
        "info",
        "warning",
        "error",
    }:
        raise ValueError("unsupported log level")

    if not isinstance(correlation_id, str) or not correlation_id:
        raise ValueError("correlation_id is required")

    tokens = list(payload)

    if any(is_sensitive_token(token) for token in tokens):
        raise ValueError(
            "sensitive payload cannot enter general logs"
        )

    return {
        "level": level,
        "message": message,
        "correlation_id": correlation_id,
        "payload": tokens,
    }


def artifact_record(
    *,
    stage: str,
    index: int,
    parent: str | None,
) -> dict[str, Any]:
    """Create one deterministic lineage artifact."""

    if stage not in REQUIRED_STAGES:
        raise ValueError("unsupported lineage stage")

    artifact_id = f"{stage}-001"
    content = (
        f"OBSERVABILITY-001|{index}|{stage}|"
        "2026-08-04T00:00:00Z|1.0.0"
    )

    return {
        "stage": stage,
        "artifact_id": artifact_id,
        "owner": "cre-foundry-synthetic",
        "version": "1.0.0",
        "as_of": f"2026-08-04T00:00:{index:02d}Z",
        "content_sha256": hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
        "parents": [] if parent is None else [parent],
    }


def replay_basis(
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Return the exact data bound into replay identity."""

    return {
        "decision_id": decision["decision_id"],
        "as_of": decision["as_of"],
        "source_public_availability": (
            decision["source_public_availability"]
        ),
        "correlation_id": decision["correlation_id"],
        "artifacts": decision["artifacts"],
    }


def expected_replay_digest(
    decision: dict[str, Any],
) -> str:
    """Recompute the deterministic replay digest."""

    return hashlib.sha256(
        canonical_bytes(replay_basis(decision))
    ).hexdigest()


def bind_replay_identity(
    decision: dict[str, Any],
) -> None:
    """Bind replay identity to the canonical decision inputs."""

    digest = expected_replay_digest(decision)

    decision["replay_identity"] = {
        "algorithm": "sha256",
        "canonical_input_sha256": digest,
        "replay_id": f"replay_{digest}",
    }


def render_subject() -> dict[str, Any]:
    """Render the canonical synthetic observability posture."""

    artifacts: list[dict[str, Any]] = []
    parent: str | None = None

    for index, stage in enumerate(REQUIRED_STAGES):
        artifact = artifact_record(
            stage=stage,
            index=index,
            parent=parent,
        )
        artifacts.append(artifact)
        parent = artifact["artifact_id"]

    decision: dict[str, Any] = {
        "decision_id": "DEC-OBS-001",
        "as_of": "2026-08-04T00:01:00Z",
        "source_public_availability": (
            "2026-08-03T00:00:00Z"
        ),
        "correlation_id": "run_obs_001",
        "artifacts": artifacts,
    }

    bind_replay_identity(decision)

    return {
        "document_kind": "OBSERVABILITY_POSTURE",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "decision": decision,
        "logs": [
            log_event(
                level="info",
                message="synthetic lineage validated",
                correlation_id="run_obs_001",
                payload=["run_obs_001"],
            )
        ],
        "claim_ceiling": CLAIM_CEILING,
    }


def lineage_checks(
    subject: dict[str, Any],
) -> list[str]:
    """Independently evaluate OBSERVABILITY-001 semantics."""

    if not isinstance(subject, dict):
        return ["LINEAGE-SHAPE-INVALID"]

    value = copy.deepcopy(subject)
    decision = value.get("decision")

    if not isinstance(decision, dict):
        return ["LINEAGE-SHAPE-INVALID"]

    diagnostics: list[str] = []

    if (
        not decision.get("as_of")
        or not decision.get(
            "source_public_availability"
        )
    ):
        diagnostics.append("LINEAGE-MISSING-ASOF")

    artifacts = decision.get("artifacts", [])

    if not isinstance(artifacts, list):
        return ["LINEAGE-SHAPE-INVALID"]

    if any(
        not isinstance(item, dict)
        or not item.get("version")
        for item in artifacts
    ):
        diagnostics.append("LINEAGE-MISSING-VERSION")

    if any(
        not isinstance(item, dict)
        or not isinstance(
            item.get("content_sha256"),
            str,
        )
        or HEX64.fullmatch(
            item.get("content_sha256", "")
        )
        is None
        for item in artifacts
    ):
        diagnostics.append("LINEAGE-MISSING-HASH")

    correlation_id = decision.get("correlation_id")
    logs = value.get("logs", [])

    if (
        not isinstance(correlation_id, str)
        or not correlation_id
        or not isinstance(logs, list)
        or any(
            not isinstance(entry, dict)
            or entry.get("correlation_id")
            != correlation_id
            for entry in logs
        )
    ):
        diagnostics.append("LINEAGE-CORRELATION")

    replay = decision.get("replay_identity", {})

    try:
        expected_digest = expected_replay_digest(
            decision
        )
    except (KeyError, TypeError):
        expected_digest = None

    if (
        not isinstance(replay, dict)
        or replay.get("algorithm") != "sha256"
        or expected_digest is None
        or replay.get("canonical_input_sha256")
        != expected_digest
        or replay.get("replay_id")
        != f"replay_{expected_digest}"
    ):
        diagnostics.append(
            "LINEAGE-REPLAY-IDENTITY"
        )

    stages = [
        item.get("stage")
        for item in artifacts
        if isinstance(item, dict)
    ]

    edge_valid = stages == list(REQUIRED_STAGES)

    if edge_valid:
        for index, artifact in enumerate(artifacts):
            expected_parents = (
                []
                if index == 0
                else [
                    artifacts[index - 1][
                        "artifact_id"
                    ]
                ]
            )

            if artifact.get("parents") != expected_parents:
                edge_valid = False
                break

    if not edge_valid:
        diagnostics.append("LINEAGE-MISSING-EDGE")

    sensitive_found = False

    if isinstance(logs, list):
        for entry in logs:
            if not isinstance(entry, dict):
                continue

            payload = entry.get("payload", [])

            if not isinstance(payload, list):
                continue

            if any(
                isinstance(token, str)
                and token.startswith(
                    SENSITIVE_PREFIXES
                )
                for token in payload
            ):
                sensitive_found = True

    if sensitive_found:
        diagnostics.append(
            "LINEAGE-PROTECTED-DETAIL-LOG"
        )

    if value.get("live_permissions") is not False:
        diagnostics.append("LINEAGE-LIVE-DEFAULT")

    if (
        value.get("external_effect_occurred")
        is not False
    ):
        diagnostics.append("LINEAGE-EXTERNAL-EFFECT")

    if (
        value.get("proof_level") != 4
        or value.get("claim_ceiling")
        != CLAIM_CEILING
    ):
        diagnostics.append("LINEAGE-CLAIM-CEILING")

    return sorted(set(diagnostics))
