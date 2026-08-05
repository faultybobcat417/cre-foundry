"""Independent frozen public evaluator for OBSERVABILITY-001."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/observability_posture.schema.json"

EVALUATOR_ID = "observability-posture-public-v1"

CLAIM_CEILING = (
    "Synthetic OBSERVABILITY-001 conformance only; "
    "no production telemetry, durability, recovery, "
    "operational completeness, sealed evaluation, "
    "or deployment claim."
)

REQUIRED_STAGES = [
    "source",
    "snapshot",
    "identity",
    "feature",
    "model",
    "policy",
    "route",
    "evaluator",
    "outcome",
]

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


def _artifact(
    stage: str,
    index: int,
    parent: str | None,
) -> dict[str, Any]:
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


def _replay_basis(
    decision: dict[str, Any],
) -> dict[str, Any]:
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
    return hashlib.sha256(
        canonical_bytes(_replay_basis(decision))
    ).hexdigest()



def refresh_replay_identity(
    decision: dict[str, Any],
) -> None:
    digest = expected_replay_digest(decision)

    decision["replay_identity"] = {
        "algorithm": "sha256",
        "canonical_input_sha256": digest,
        "replay_id": f"replay_{digest}",
    }


def build_clean_subject() -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    parent: str | None = None

    for index, stage in enumerate(REQUIRED_STAGES):
        artifact = _artifact(stage, index, parent)
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

    digest = expected_replay_digest(decision)

    decision["replay_identity"] = {
        "algorithm": "sha256",
        "canonical_input_sha256": digest,
        "replay_id": f"replay_{digest}",
    }

    return {
        "document_kind": "OBSERVABILITY_POSTURE",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "decision": decision,
        "logs": [
            {
                "level": "info",
                "message": "synthetic lineage validated",
                "correlation_id": "run_obs_001",
                "payload": ["run_obs_001"],
            }
        ],
        "claim_ceiling": CLAIM_CEILING,
    }


def apply_mutation(
    subject: dict[str, Any],
    mutation_id: str,
) -> None:
    decision = subject["decision"]

    if mutation_id == "missing_asof":
        decision["as_of"] = ""
        decision["source_public_availability"] = ""
    elif mutation_id == "missing_version":
        decision["artifacts"][3]["version"] = ""
    elif mutation_id == "missing_hash":
        decision["artifacts"][4]["content_sha256"] = ""
    elif mutation_id == "missing_correlation":
        decision["correlation_id"] = ""
        subject["logs"][0]["correlation_id"] = ""
    elif mutation_id == "missing_replay_identity":
        decision["replay_identity"]["replay_id"] = (
            "replay_invalid"
        )
    elif mutation_id == "missing_lineage_edge":
        decision["artifacts"][5]["parents"] = []
    elif mutation_id == "protected_detail_log":
        subject["logs"].append(
            {
                "level": "info",
                "message": "protected match detail",
                "correlation_id": "run_obs_001",
                "payload": [
                    "account_0123",
                    "addr_9",
                ],
            }
        )
    else:
        raise ValueError(
            f"unsupported mutation recipe: {mutation_id}"
        )

    if mutation_id in {
        "missing_asof",
        "missing_version",
        "missing_hash",
        "missing_correlation",
        "missing_lineage_edge",
    }:
        refresh_replay_identity(decision)


def diagnostics(
    subject: dict[str, Any],
) -> list[str]:
    if not isinstance(subject, dict):
        return ["LINEAGE-SHAPE-INVALID"]

    errors: list[str] = []
    decision = subject.get("decision")

    if not isinstance(decision, dict):
        return ["LINEAGE-SHAPE-INVALID"]

    if (
        not decision.get("as_of")
        or not decision.get(
            "source_public_availability"
        )
    ):
        errors.append("LINEAGE-MISSING-ASOF")

    artifacts = decision.get("artifacts", [])

    if not isinstance(artifacts, list):
        return ["LINEAGE-SHAPE-INVALID"]

    if any(
        not isinstance(item, dict)
        or not item.get("version")
        for item in artifacts
    ):
        errors.append("LINEAGE-MISSING-VERSION")

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
        errors.append("LINEAGE-MISSING-HASH")

    correlation = decision.get("correlation_id")

    logs = subject.get("logs", [])

    if (
        not isinstance(correlation, str)
        or not correlation
        or not isinstance(logs, list)
        or any(
            not isinstance(entry, dict)
            or entry.get("correlation_id")
            != correlation
            for entry in logs
        )
    ):
        errors.append("LINEAGE-CORRELATION")

    replay = decision.get("replay_identity", {})
    expected_digest: str | None = None

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
        errors.append("LINEAGE-REPLAY-IDENTITY")

    stages = [
        item.get("stage")
        for item in artifacts
        if isinstance(item, dict)
    ]

    edge_valid = stages == REQUIRED_STAGES

    if edge_valid:
        for index, item in enumerate(artifacts):
            expected_parents = (
                []
                if index == 0
                else [
                    artifacts[index - 1][
                        "artifact_id"
                    ]
                ]
            )

            if item.get("parents") != expected_parents:
                edge_valid = False
                break

    if not edge_valid:
        errors.append("LINEAGE-MISSING-EDGE")

    sensitive_found = False

    for entry in logs if isinstance(logs, list) else []:
        if not isinstance(entry, dict):
            continue

        payload = entry.get("payload", [])

        if not isinstance(payload, list):
            continue

        for token in payload:
            if (
                isinstance(token, str)
                and token.startswith(
                    SENSITIVE_PREFIXES
                )
            ):
                sensitive_found = True

    if sensitive_found:
        errors.append(
            "LINEAGE-PROTECTED-DETAIL-LOG"
        )

    if subject.get("live_permissions") is not False:
        errors.append("LINEAGE-LIVE-DEFAULT")

    if (
        subject.get("external_effect_occurred")
        is not False
    ):
        errors.append("LINEAGE-EXTERNAL-EFFECT")

    if (
        subject.get("proof_level") != 4
        or subject.get("claim_ceiling")
        != CLAIM_CEILING
    ):
        errors.append("LINEAGE-CLAIM-CEILING")

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
        result_diagnostics = ["LINEAGE-SCHEMA"]
    else:
        result_diagnostics = []

    return {
        "passed": not result_diagnostics,
        "diagnostics": result_diagnostics,
        "schema_error_count": len(schema_errors),
    }
