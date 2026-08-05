from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "governed_source_required": True,
    "admission_ready_required": True,
    "container_recon_ready_required": True,
    "manifest_source_identity_match_required": True,
    "manifest_timestamp_required": True,
    "manual_parser_approval_required": True,
    "manual_temporal_approval_required": True,
    "manual_registration_approval_required": True,
    "registration_sql_generation_enabled": False,
    "snapshot_registration_enabled": False,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

TIMESTAMP_KEYS = {
    "acquired_at",
    "completed_at",
    "created_at",
    "effective_at",
    "fetched_at",
    "generated_at",
    "observed_at",
    "retrieved_at",
    "run_started_at",
    "started_at",
}


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _load_config(
    project_root: Path,
) -> None:
    config = _load_object(project_root / "config" / "snapshot_registration_review.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Registration policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Registration-review policy mismatch.")


def _stable_hash(
    payload: object,
) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _parse_timestamp(
    value: str,
) -> datetime:
    normalized = value.strip()

    if normalized.endswith(
        (
            "Z",
            "z",
        )
    ):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def _manifest_metadata(
    value: object,
) -> tuple[
    set[str],
    list[dict[str, str]],
]:
    source_ids: set[str] = set()

    timestamps: list[dict[str, str]] = []

    def visit(
        current: object,
        breadcrumb: str,
    ) -> None:
        if isinstance(
            current,
            dict,
        ):
            for raw_key, nested in current.items():
                key = str(raw_key)

                nested_breadcrumb = breadcrumb + "." + key

                if (
                    key == "source_id"
                    and isinstance(
                        nested,
                        str,
                    )
                    and nested
                ):
                    source_ids.add(nested)

                if key in TIMESTAMP_KEYS and isinstance(
                    nested,
                    str,
                ):
                    try:
                        parsed = _parse_timestamp(nested)

                    except ValueError:
                        parsed = None

                    if parsed is not None:
                        timestamps.append(
                            {
                                "timestamp_key": key,
                                "declared_value": nested,
                                "normalized_utc": (parsed.isoformat()),
                                "breadcrumb": (nested_breadcrumb),
                            }
                        )

                visit(
                    nested,
                    nested_breadcrumb,
                )

        elif isinstance(
            current,
            list,
        ):
            for index, nested in enumerate(current):
                visit(
                    nested,
                    (breadcrumb + "[" + str(index) + "]"),
                )

    visit(
        value,
        "$",
    )

    unique = {
        (
            item["timestamp_key"],
            item["normalized_utc"],
            item["breadcrumb"],
        ): item
        for item in timestamps
    }

    return (
        source_ids,
        sorted(
            unique.values(),
            key=lambda item: (
                item["normalized_utc"],
                item["timestamp_key"],
            ),
        ),
    )


def _operations_state(
    project_root: Path,
) -> dict[str, Any]:
    database_path = project_root / "data" / "control" / "operations.sqlite3"

    connection = sqlite3.connect(
        ("file:" + str(database_path) + "?mode=ro"),
        uri=True,
    )

    try:
        required_tables = {
            "source_operation_policies",
            "source_snapshots",
            "source_snapshot_events",
        }

        available_tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        missing_tables = required_tables - available_tables

        if missing_tables:
            raise RuntimeError(f"Missing operations tables: {sorted(missing_tables)}")

        policy_columns = {
            str(row[1])
            for row in connection.execute(
                """
                PRAGMA table_info(
                    source_operation_policies
                )
                """
            ).fetchall()
        }

        snapshot_columns = [
            {
                "index": int(row[0]),
                "name": str(row[1]),
                "data_type": str(row[2] or ""),
                "not_null": bool(row[3]),
                "primary_key_position": int(row[5]),
            }
            for row in connection.execute(
                """
                PRAGMA table_info(
                    source_snapshots
                )
                """
            ).fetchall()
        ]

        if "source_id" not in policy_columns:
            raise RuntimeError("Source policy table lacks source_id.")

        if "source_id" not in {item["name"] for item in snapshot_columns}:
            raise RuntimeError("Source snapshot table lacks source_id.")

        governed_sources = [
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT source_id
                FROM source_operation_policies
                ORDER BY source_id
                """
            ).fetchall()
        ]

        snapshot_counts = {
            source_id: int(
                connection.execute(
                    """
                    SELECT count(*)
                    FROM source_snapshots
                    WHERE source_id = ?
                    """,
                    [source_id],
                ).fetchone()[0]
            )
            for source_id in governed_sources
        }

        snapshot_count = int(
            connection.execute(
                """
                SELECT count(*)
                FROM source_snapshots
                """
            ).fetchone()[0]
        )

        event_count = int(
            connection.execute(
                """
                SELECT count(*)
                FROM source_snapshot_events
                """
            ).fetchone()[0]
        )

    finally:
        connection.close()

    return {
        "database_path": str(database_path.relative_to(project_root)),
        "governed_sources": (governed_sources),
        "governed_source_count": len(governed_sources),
        "snapshot_counts": (snapshot_counts),
        "existing_snapshot_count": (snapshot_count),
        "snapshot_event_count": (event_count),
        "snapshot_schema": (snapshot_columns),
        "snapshot_schema_fingerprint": (_stable_hash(snapshot_columns)),
    }


def build_snapshot_registration_review(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    _load_config(project_root)

    admission = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_admission.json"
    )

    containers = _load_object(
        project_root / "docs" / "data_contracts" / "source_container_inventory.json"
    )

    operations = _operations_state(project_root)

    raw_packets = admission.get("packets")

    raw_entries = containers.get("entries")

    if not isinstance(
        raw_packets,
        list,
    ):
        raise RuntimeError("Admission packets must be a list.")

    if not isinstance(
        raw_entries,
        list,
    ):
        raise RuntimeError("Container entries must be a list.")

    container_by_path: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_entry in raw_entries:
        if not isinstance(
            raw_entry,
            dict,
        ):
            raise RuntimeError("Container entry must be an object.")

        artifact_path = raw_entry.get("artifact_path")

        if (
            not isinstance(
                artifact_path,
                str,
            )
            or not artifact_path
        ):
            raise RuntimeError("Container entry lacks artifact_path.")

        container_by_path[artifact_path] = {str(key): value for key, value in raw_entry.items()}

    governed_sources = set(operations["governed_sources"])

    candidates = []
    approvals = []
    admitted_sources: set[str] = set()

    for raw_packet in raw_packets:
        if not isinstance(
            raw_packet,
            dict,
        ):
            raise RuntimeError("Admission packet must be an object.")

        source_id = raw_packet.get("source_id")

        manifest_path = raw_packet.get("manifest_path")

        bundle_sha256 = raw_packet.get("bundle_sha256")

        raw_artifacts = raw_packet.get("artifacts")

        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id
        ):
            raise RuntimeError("Admission packet lacks source_id.")

        if (
            not isinstance(
                manifest_path,
                str,
            )
            or not manifest_path
        ):
            raise RuntimeError("Admission packet lacks manifest_path.")

        if (
            not isinstance(
                bundle_sha256,
                str,
            )
            or not bundle_sha256
        ):
            raise RuntimeError("Admission packet lacks bundle_sha256.")

        if not isinstance(
            raw_artifacts,
            list,
        ):
            raise RuntimeError("Admission artifacts must be a list.")

        admitted_sources.add(source_id)

        manifest_file = (project_root / manifest_path).resolve(strict=False)

        if not manifest_file.is_file():
            raise RuntimeError(f"Manifest is missing: {manifest_path}")

        manifest = _load_object(manifest_file)

        (
            manifest_source_ids,
            timestamp_candidates,
        ) = _manifest_metadata(manifest)

        source_identity_match = manifest_source_ids == {source_id}

        violations = []

        if raw_packet.get("admission_ready") is not True:
            violations.append("admission_not_ready")

        if source_id not in governed_sources:
            violations.append("governed_source_missing")

        if not source_identity_match:
            violations.append("manifest_source_identity_mismatch")

        temporal_evidence_missing = not timestamp_candidates

        artifact_reviews: list[dict[str, Any]] = []
        for raw_artifact in raw_artifacts:
            if not isinstance(
                raw_artifact,
                dict,
            ):
                raise RuntimeError("Admission artifact must be an object.")

            artifact_path = raw_artifact.get("resolved_relative_path")

            raw_probe = raw_artifact.get("probe")

            if (
                not isinstance(
                    artifact_path,
                    str,
                )
                or not artifact_path
            ):
                raise RuntimeError("Admission artifact lacks path.")

            if not isinstance(
                raw_probe,
                dict,
            ):
                raise RuntimeError("Admission artifact lacks probe.")

            container_entry = container_by_path.get(artifact_path)

            if container_entry is None:
                violations.append("container_recon_missing")

            elif container_entry.get("container_recon_ready") is not True:
                violations.append("container_recon_not_ready")

            artifact_reviews.append(
                {
                    "artifact_path": (artifact_path),
                    "artifact_sha256": (raw_probe.get("actual_sha256")),
                    "size_bytes": (raw_probe.get("size_bytes")),
                    "container_type": (
                        container_entry.get("container_type")
                        if container_entry is not None
                        else None
                    ),
                    "format_candidates": (
                        container_entry.get("format_candidates")
                        if container_entry is not None
                        else []
                    ),
                    "parser_contract_approved": False,
                    "parser_execution_permitted": False,
                }
            )

        violations = sorted(set(violations))

        structurally_ready = not violations

        execution_blockers = list(violations)

        execution_blockers.extend(
            [
                "manual_parser_approval_missing",
                "manual_temporal_approval_missing",
                "manual_registration_approval_missing",
                "snapshot_registration_disabled",
            ]
        )

        if temporal_evidence_missing:
            execution_blockers.append("manifest_timestamp_evidence_missing")

        existing_snapshot_count = int(
            operations["snapshot_counts"].get(
                source_id,
                0,
            )
        )

        if existing_snapshot_count:
            execution_blockers.append("duplicate_snapshot_review_required")

        execution_blockers = sorted(set(execution_blockers))

        logical_payload = {
            "source_id": (source_id),
            "bundle_sha256": (bundle_sha256),
            "manifest_path": (manifest_path),
            "timestamp_candidates": (timestamp_candidates),
            "approved_observed_at": None,
            "approved_acquired_at": None,
            "artifacts": (artifact_reviews),
            "snapshot_schema_fingerprint": (operations["snapshot_schema_fingerprint"]),
        }

        request_id = "snapshot_request_" + _stable_hash(logical_payload)[:20]

        candidates.append(
            {
                "registration_request_id": (request_id),
                "source_id": (source_id),
                "bundle_sha256": (bundle_sha256),
                "manifest_path": (manifest_path),
                "manifest_source_ids": sorted(manifest_source_ids),
                "manifest_source_identity_match": (source_identity_match),
                "timestamp_candidate_count": len(timestamp_candidates),
                "timestamp_candidates": (timestamp_candidates),
                "temporal_evidence_missing": (temporal_evidence_missing),
                "temporal_evidence_status": (
                    "missing_manifest_timestamp"
                    if temporal_evidence_missing
                    else "manifest_declared"
                ),
                "artifact_count": len(artifact_reviews),
                "artifacts": (artifact_reviews),
                "existing_snapshot_count": (existing_snapshot_count),
                "structural_violations": (violations),
                "ready_for_human_review": (structurally_ready),
                "execution_blockers": (execution_blockers),
                "logical_registration_payload": (logical_payload),
                "registration_sql_generated": False,
                "registration_execution_permitted": False,
                "registration_execution_count": 0,
            }
        )

        approvals.append(
            {
                "registration_request_id": (request_id),
                "source_id": (source_id),
                "allowed_bundle_sha256": (bundle_sha256),
                "parser_contract_approved": False,
                "temporal_semantics_approved": False,
                "registration_approved": False,
                "approved_observed_at": None,
                "approved_acquired_at": None,
                "approved_by": None,
                "approved_at": None,
                "approval_evidence_reference": None,
                "registration_execution_requested": False,
                "registration_execution_permitted": False,
            }
        )

    candidates.sort(key=lambda item: str(item["source_id"]))

    approvals.sort(key=lambda item: str(item["source_id"]))

    unadmitted_sources = sorted(governed_sources - admitted_sources)

    review_ready_count = sum(bool(candidate["ready_for_human_review"]) for candidate in candidates)

    review: dict[str, Any] = {
        "model_version": ("cre-foundry-snapshot-registration-review-v1"),
        "governed_source_count": (operations["governed_source_count"]),
        "candidate_count": len(candidates),
        "review_ready_count": (review_ready_count),
        "structurally_blocked_count": (len(candidates) - review_ready_count),
        "unadmitted_source_count": len(unadmitted_sources),
        "unadmitted_source_ids": (unadmitted_sources),
        "existing_snapshot_count": (operations["existing_snapshot_count"]),
        "snapshot_event_count": (operations["snapshot_event_count"]),
        "operations_state": (operations),
        "candidates": candidates,
        "approved_registration_count": 0,
        "registration_sql_generation_count": 0,
        "snapshot_registration_execution_count": 0,
        "automatic_acquisition_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    approval_template: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-snapshot-registration-approval-template-v1"),
        "approval_count": len(approvals),
        "approved_parser_contract_count": 0,
        "approved_temporal_semantics_count": 0,
        "approved_registration_count": 0,
        "approvals": (approvals),
        "automatic_approval": False,
        "registration_execution_permitted": False,
        "snapshot_registration_execution_count": 0,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        review_path = contract_root / "snapshot_registration_review.json"

        approval_path = contract_root / "snapshot_registration_approval_template.json"

        markdown_path = contract_root / "snapshot_registration_review.md"

        _atomic_json(
            review_path,
            review,
        )

        _atomic_json(
            approval_path,
            approval_template,
        )

        _atomic_text(
            markdown_path,
            "\n".join(
                [
                    "# Manual Snapshot Registration Review",
                    "",
                    (
                        "This layer creates exact human-review "
                        "packets. It does not generate SQL or "
                        "register source snapshots."
                    ),
                    "",
                    (f"- Governed sources: `{review['governed_source_count']}`"),
                    (f"- Candidates: `{review['candidate_count']}`"),
                    (f"- Review-ready: `{review_ready_count}`"),
                    (f"- Existing snapshots: `{review['existing_snapshot_count']}`"),
                    "",
                    "- Registration SQL generated: `false`",
                    "- Snapshot registration executed: `false`",
                    "",
                ]
            ),
        )

    return {
        "review": review,
        "approval_template": (approval_template),
    }
