from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "authoritative_database_read_only": True,
    "ephemeral_database_clone_required": True,
    "schema_introspection_required": True,
    "required_column_mapping_required": True,
    "transaction_rollback_required": True,
    "count_reconciliation_required": True,
    "manual_parser_approval_required": True,
    "manual_temporal_approval_required": True,
    "manual_registration_approval_required": True,
    "authoritative_registration_enabled": False,
    "snapshot_event_insertion_enabled": False,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
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

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


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


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _load_config(
    project_root: Path,
) -> None:
    config = _load_object(project_root / "config" / "snapshot_registration_preflight.json")

    raw_policy = config.get("policy")

    if not isinstance(raw_policy, dict):
        raise RuntimeError("Preflight policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Preflight policy mismatch.")


def _table_schema(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()

    return [
        {
            "index": int(row[0]),
            "name": str(row[1]),
            "data_type": str(row[2] or ""),
            "not_null": bool(row[3]),
            "default_value": (str(row[4]) if row[4] is not None else None),
            "primary_key_position": int(row[5]),
        }
        for row in rows
    ]


def _required_columns(
    schema: list[dict[str, Any]],
) -> list[str]:
    required: list[str] = []

    for column in schema:
        column_name = str(column["name"])

        data_type = str(column["data_type"]).upper()

        primary_key_position = int(column["primary_key_position"])

        if primary_key_position > 0 and "INT" in data_type:
            continue

        if (
            bool(column["not_null"]) and column["default_value"] is None
        ) or primary_key_position > 0:
            required.append(column_name)

    return sorted(set(required))


def _candidate_timestamp(
    candidate: dict[str, Any],
) -> str:
    raw_candidates = candidate.get("timestamp_candidates")

    if isinstance(raw_candidates, list):
        for raw_timestamp in raw_candidates:
            if not isinstance(
                raw_timestamp,
                dict,
            ):
                continue

            normalized = raw_timestamp.get("normalized_utc")

            if isinstance(
                normalized,
                str,
            ):
                return normalized

    return "2000-01-01T00:00:00+00:00"


def _context_object(
    context: dict[str, Any],
    key: str,
) -> object:
    if key not in context:
        raise RuntimeError(f"Preflight context lacks required key: {key}")

    value: object = context[key]
    return value


def _column_value(
    column_name: str,
    *,
    table_name: str,
    context: dict[str, Any],
) -> object | None:
    normalized = column_name.lower()

    timestamp_value = _context_object(
        context,
        "timestamp",
    )

    timestamp = str(timestamp_value)

    raw_event_payload = context.get("event_payload")

    if not isinstance(
        raw_event_payload,
        dict,
    ):
        raise RuntimeError("Preflight event payload must be an object.")

    event_payload: dict[str, Any] = {str(key): value for key, value in raw_event_payload.items()}

    payload_json = json.dumps(
        event_payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    mappings: dict[str, object] = {
        "snapshot_id": _context_object(
            context,
            "snapshot_id",
        ),
        "event_id": _context_object(
            context,
            "event_id",
        ),
        "source_id": _context_object(
            context,
            "source_id",
        ),
        "manifest_path": _context_object(
            context,
            "manifest_path",
        ),
        "manifest_sha256": _context_object(
            context,
            "manifest_sha256",
        ),
        "artifact_path": _context_object(
            context,
            "artifact_path",
        ),
        "artifact_sha256": _context_object(
            context,
            "artifact_sha256",
        ),
        "bundle_sha256": _context_object(
            context,
            "bundle_sha256",
        ),
        "registration_request_id": _context_object(
            context,
            "registration_request_id",
        ),
        "run_id": _context_object(
            context,
            "registration_request_id",
        ),
        "source_run_id": _context_object(
            context,
            "registration_request_id",
        ),
        "event_type": ("snapshot_registration_preflight"),
        "status": "preflight",
        "state": "preflight",
        "payload_json": payload_json,
        "metadata_json": payload_json,
        "details_json": payload_json,
        "context_json": payload_json,
        "content_type": ("application/octet-stream"),
        "mime_type": ("application/octet-stream"),
        "size_bytes": _context_object(
            context,
            "size_bytes",
        ),
        "artifact_size_bytes": _context_object(
            context,
            "size_bytes",
        ),
        "previous_hash": "0" * 64,
        "previous_event_hash": "0" * 64,
        "parent_hash": "0" * 64,
        "event_hash": _context_object(
            context,
            "event_hash",
        ),
        "record_hash": _context_object(
            context,
            "event_hash",
        ),
        "hash": _context_object(
            context,
            "event_hash",
        ),
        "approved": 0,
        "authorized": 0,
        "is_active": 0,
        "is_valid": 0,
        "acquisition_method": "historical_bootstrap_preflight",
        "artifact_relative_path": _context_object(
            context,
            "artifact_path",
        ),
        "byte_size": _context_object(
            context,
            "size_bytes",
        ),
        "content_sha256": _context_object(
            context,
            "artifact_sha256",
        ),
    }

    if normalized in mappings:
        mapped_value: object = mappings[normalized]

        return mapped_value

    if normalized in {
        "acquired_at",
        "observed_at",
        "effective_at",
        "snapshot_at",
        "created_at",
        "recorded_at",
        "event_at",
        "timestamp",
        "occurred_at",
    }:
        return timestamp

    if normalized == "id":
        identifier_key = "snapshot_id" if table_name == "source_snapshots" else "event_id"

        return _context_object(
            context,
            identifier_key,
        )

    return None


def _build_values(
    schema: list[dict[str, Any]],
    *,
    table_name: str,
    context: dict[str, Any],
) -> tuple[
    dict[str, object],
    list[str],
]:
    values: dict[str, object] = {}
    unmapped_required: list[str] = []

    required = set(_required_columns(schema))

    for column in schema:
        column_name = str(column["name"])

        value = _column_value(
            column_name,
            table_name=table_name,
            context=context,
        )

        if value is not None:
            values[column_name] = value

        elif column_name in required:
            unmapped_required.append(column_name)

    return (
        values,
        sorted(unmapped_required),
    )


def _insert_statement(
    table_name: str,
    values: dict[str, object],
) -> tuple[str, list[object]]:
    columns = list(values.keys())

    quoted_columns = ", ".join(f'"{column}"' for column in columns)

    placeholders = ", ".join("?" for _ in columns)

    statement = f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'

    parameters = [values[column] for column in columns]

    return (
        statement,
        parameters,
    )


def build_snapshot_registration_preflight(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    _load_config(project_root)

    review = _load_object(
        project_root / "docs" / "data_contracts" / "snapshot_registration_review.json"
    )

    replay = _load_object(
        project_root / "docs" / "data_contracts" / "deterministic_replay_spec.json"
    )

    raw_candidates = review.get("candidates")

    if not isinstance(raw_candidates, list):
        raise RuntimeError("Registration candidates must be a list.")

    eligible_candidates: list[dict[str, Any]] = []

    for raw_candidate in raw_candidates:
        if not isinstance(
            raw_candidate,
            dict,
        ):
            continue

        if (
            raw_candidate.get("ready_for_human_review") is True
            and raw_candidate.get("temporal_evidence_missing") is False
            and int(
                raw_candidate.get(
                    "existing_snapshot_count",
                    0,
                )
            )
            == 0
        ):
            eligible_candidates.append({str(key): value for key, value in raw_candidate.items()})

    eligible_candidates.sort(key=lambda candidate: str(candidate["source_id"]))

    selected_candidate = eligible_candidates[0] if eligible_candidates else None

    authoritative_database = project_root / "data" / "control" / "operations.sqlite3"

    authoritative_sha256_before = _sha256(authoritative_database)

    read_only_connection = sqlite3.connect(
        ("file:" + str(authoritative_database) + "?mode=ro"),
        uri=True,
    )

    try:
        snapshot_schema = _table_schema(
            read_only_connection,
            "source_snapshots",
        )

        event_schema = _table_schema(
            read_only_connection,
            "source_snapshot_events",
        )

        snapshot_count = int(
            read_only_connection.execute(
                """
                SELECT count(*)
                FROM source_snapshots
                """
            ).fetchone()[0]
        )

        event_count = int(
            read_only_connection.execute(
                """
                SELECT count(*)
                FROM source_snapshot_events
                """
            ).fetchone()[0]
        )

    finally:
        read_only_connection.close()

    status = "no_temporally_eligible_candidate"
    selected_source_id: str | None = None
    snapshot_values: dict[str, object] = {}
    event_values: dict[str, object] = {}
    unmapped_snapshot_columns: list[str] = []
    unmapped_event_columns: list[str] = []
    ephemeral_attempt_count = 0
    ephemeral_transaction_verified = False
    ephemeral_error_type: str | None = None
    ephemeral_error_message: str | None = None
    clone_counts: dict[str, int] = {}

    if selected_candidate is not None:
        selected_source_id = str(selected_candidate["source_id"])

        raw_artifacts = selected_candidate.get("artifacts")

        if (
            not isinstance(
                raw_artifacts,
                list,
            )
            or not raw_artifacts
        ):
            raise RuntimeError("Selected candidate has no artifact.")

        first_artifact = raw_artifacts[0]

        if not isinstance(
            first_artifact,
            dict,
        ):
            raise RuntimeError("Selected artifact is malformed.")

        manifest_path = str(selected_candidate["manifest_path"])

        manifest_file = (project_root / manifest_path).resolve(strict=False)

        manifest_sha256 = _sha256(manifest_file)

        registration_request_id = str(selected_candidate["registration_request_id"])

        snapshot_id = (
            "preflight_snapshot_"
            + _stable_hash(
                {
                    "source_id": (selected_source_id),
                    "request": (registration_request_id),
                }
            )[:20]
        )

        event_id = (
            "preflight_event_"
            + _stable_hash(
                {
                    "snapshot_id": snapshot_id,
                    "type": ("snapshot_registration_preflight"),
                }
            )[:20]
        )

        event_payload = {
            "preflight_only": True,
            "authoritative_execution": False,
            "source_id": selected_source_id,
            "registration_request_id": (registration_request_id),
            "replay_model_version": (replay.get("model_version")),
        }

        context: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "event_id": event_id,
            "source_id": selected_source_id,
            "manifest_path": manifest_path,
            "manifest_sha256": (manifest_sha256),
            "artifact_path": str(first_artifact["artifact_path"]),
            "artifact_sha256": str(first_artifact["artifact_sha256"]),
            "bundle_sha256": str(selected_candidate["bundle_sha256"]),
            "registration_request_id": (registration_request_id),
            "timestamp": (_candidate_timestamp(selected_candidate)),
            "size_bytes": int(
                first_artifact.get(
                    "size_bytes",
                    0,
                )
                or 0
            ),
            "event_payload": event_payload,
        }

        context["event_hash"] = _stable_hash(event_payload)

        (
            snapshot_values,
            unmapped_snapshot_columns,
        ) = _build_values(
            snapshot_schema,
            table_name="source_snapshots",
            context=context,
        )

        (
            event_values,
            unmapped_event_columns,
        ) = _build_values(
            event_schema,
            table_name=("source_snapshot_events"),
            context=context,
        )

        if unmapped_snapshot_columns or unmapped_event_columns:
            status = "schema_mapping_incomplete"

        else:
            status = "ephemeral_transaction_attempted"
            ephemeral_attempt_count = 1

            with tempfile.TemporaryDirectory(
                prefix=("cre-foundry-registration-preflight-")
            ) as temporary_directory:
                clone_path = Path(temporary_directory) / "operations.sqlite3"

                shutil.copy2(
                    authoritative_database,
                    clone_path,
                )

                clone_connection = sqlite3.connect(clone_path)

                try:
                    clone_connection.execute("PRAGMA foreign_keys = ON")

                    before_snapshot_count = int(
                        clone_connection.execute(
                            """
                            SELECT count(*)
                            FROM source_snapshots
                            """
                        ).fetchone()[0]
                    )

                    before_event_count = int(
                        clone_connection.execute(
                            """
                            SELECT count(*)
                            FROM source_snapshot_events
                            """
                        ).fetchone()[0]
                    )

                    clone_connection.execute("BEGIN IMMEDIATE")

                    (
                        snapshot_statement,
                        snapshot_parameters,
                    ) = _insert_statement(
                        "source_snapshots",
                        snapshot_values,
                    )

                    clone_connection.execute(
                        snapshot_statement,
                        snapshot_parameters,
                    )

                    (
                        event_statement,
                        event_parameters,
                    ) = _insert_statement(
                        "source_snapshot_events",
                        event_values,
                    )

                    clone_connection.execute(
                        event_statement,
                        event_parameters,
                    )

                    inserted_snapshot_count = int(
                        clone_connection.execute(
                            """
                            SELECT count(*)
                            FROM source_snapshots
                            """
                        ).fetchone()[0]
                    )

                    inserted_event_count = int(
                        clone_connection.execute(
                            """
                            SELECT count(*)
                            FROM source_snapshot_events
                            """
                        ).fetchone()[0]
                    )

                    clone_connection.rollback()

                    rolled_back_snapshot_count = int(
                        clone_connection.execute(
                            """
                            SELECT count(*)
                            FROM source_snapshots
                            """
                        ).fetchone()[0]
                    )

                    rolled_back_event_count = int(
                        clone_connection.execute(
                            """
                            SELECT count(*)
                            FROM source_snapshot_events
                            """
                        ).fetchone()[0]
                    )

                    clone_counts = {
                        "before_snapshot_count": (before_snapshot_count),
                        "before_event_count": (before_event_count),
                        "inserted_snapshot_count": (inserted_snapshot_count),
                        "inserted_event_count": (inserted_event_count),
                        "rolled_back_snapshot_count": (rolled_back_snapshot_count),
                        "rolled_back_event_count": (rolled_back_event_count),
                    }

                    ephemeral_transaction_verified = (
                        inserted_snapshot_count == before_snapshot_count + 1
                        and inserted_event_count == before_event_count + 1
                        and rolled_back_snapshot_count == before_snapshot_count
                        and rolled_back_event_count == before_event_count
                    )

                    status = (
                        "transactionally_verified_on_ephemeral_clone"
                        if ephemeral_transaction_verified
                        else "ephemeral_count_reconciliation_failed"
                    )

                except sqlite3.DatabaseError as error:
                    clone_connection.rollback()

                    ephemeral_error_type = type(error).__name__

                    ephemeral_error_message = str(error)

                    status = "ephemeral_transaction_failed_closed"

                finally:
                    clone_connection.close()

    authoritative_sha256_after = _sha256(authoritative_database)

    authoritative_unchanged = authoritative_sha256_before == authoritative_sha256_after

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-snapshot-registration-preflight-v1"),
        "preflight_status": status,
        "selected_source_id": (selected_source_id),
        "temporally_eligible_candidate_count": (len(eligible_candidates)),
        "authoritative_database_path": str(authoritative_database.relative_to(project_root)),
        "authoritative_database_sha256_before": (authoritative_sha256_before),
        "authoritative_database_sha256_after": (authoritative_sha256_after),
        "authoritative_database_unchanged": (authoritative_unchanged),
        "authoritative_snapshot_count": (snapshot_count),
        "authoritative_event_count": (event_count),
        "snapshot_schema": snapshot_schema,
        "event_schema": event_schema,
        "snapshot_required_columns": (_required_columns(snapshot_schema)),
        "event_required_columns": (_required_columns(event_schema)),
        "mapped_snapshot_columns": sorted(snapshot_values),
        "mapped_event_columns": sorted(event_values),
        "unmapped_snapshot_columns": (unmapped_snapshot_columns),
        "unmapped_event_columns": (unmapped_event_columns),
        "ephemeral_transaction_attempt_count": (ephemeral_attempt_count),
        "ephemeral_transaction_verified": (ephemeral_transaction_verified),
        "ephemeral_clone_counts": (clone_counts),
        "ephemeral_error_type": (ephemeral_error_type),
        "ephemeral_error_message": (ephemeral_error_message),
        "authoritative_registration_execution_count": 0,
        "authoritative_event_insertion_count": 0,
        "parser_approval_count": 0,
        "temporal_approval_count": 0,
        "registration_approval_count": 0,
        "automatic_acquisition_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        report_path = contract_root / "snapshot_registration_preflight.json"

        markdown_path = contract_root / "snapshot_registration_preflight.md"

        _atomic_json(
            report_path,
            report,
        )

        _atomic_text(
            markdown_path,
            "\n".join(
                [
                    "# Snapshot Registration Preflight",
                    "",
                    ("The authoritative operations database is opened read-only."),
                    "",
                    (
                        "When the actual schema can be mapped, "
                        "inserts are attempted only in a disposable "
                        "database clone and are rolled back."
                    ),
                    "",
                    (f"- Status: `{status}`"),
                    (f"- Selected source: `{selected_source_id}`"),
                    (f"- Authoritative DB unchanged: `{authoritative_unchanged}`"),
                    (f"- Ephemeral transaction verified: `{ephemeral_transaction_verified}`"),
                    "",
                    "- Authoritative registrations: `0`",
                    "- Authoritative event insertions: `0`",
                    "",
                ]
            ),
        )

    return report
