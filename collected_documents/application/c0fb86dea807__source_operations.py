from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUTHORIZED_STATUSES = {
    "approved",
    "registered_existing_source",
}

APPEND_ONLY_TABLES = (
    "source_snapshots",
    "source_snapshot_events",
    "source_quarantine_events",
    "source_replay_events",
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(
    value: datetime,
) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_datetime(
    value: str | None,
) -> datetime:
    if value is None:
        return _utc_now()

    parsed = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


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


def _config(
    project_root: Path,
) -> dict[str, Any]:
    path = project_root / "config" / "source_operations.json"

    raw_payload: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw_payload,
        dict,
    ):
        raise RuntimeError("Source-operations config must be a JSON object.")

    payload: dict[str, Any] = {str(key): value for key, value in raw_payload.items()}

    expected_policies: dict[str, Any] = {
        "content_addressed_storage": True,
        "snapshot_updates_allowed": False,
        "snapshot_deletes_allowed": False,
        "deduplicate_by_source_and_sha256": True,
        "quarantine_on_checksum_mismatch": True,
        "reacquire_during_replay": False,
        "automatic_conclusions": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "operating_mode": "shadow",
    }

    raw_policies = payload.get("policies")

    if not isinstance(
        raw_policies,
        dict,
    ):
        raise RuntimeError("Source-operations policies must be a JSON object.")

    policies: dict[str, Any] = {str(key): value for key, value in raw_policies.items()}

    if policies != expected_policies:
        raise RuntimeError("Source-operations safety policy does not match the required policy.")

    raw_sources = payload.get("sources")

    if (
        not isinstance(
            raw_sources,
            dict,
        )
        or not raw_sources
    ):
        raise RuntimeError("Source-operations config contains no registered sources.")

    for source_id, raw_policy in raw_sources.items():
        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id.strip()
        ):
            raise RuntimeError("Every source must have a non-empty string identifier.")

        if not isinstance(
            raw_policy,
            dict,
        ):
            raise RuntimeError(f"Source policy must be an object: {source_id}")

        authorization_status = raw_policy.get("authorization_status")

        if not isinstance(
            authorization_status,
            str,
        ):
            raise RuntimeError(f"Source authorization status must be a string: {source_id}")

        acquisition_methods = raw_policy.get("allowed_acquisition_methods")

        if (
            not isinstance(
                acquisition_methods,
                list,
            )
            or not acquisition_methods
            or not all(
                isinstance(
                    method,
                    str,
                )
                and method
                for method in acquisition_methods
            )
        ):
            raise RuntimeError(
                f"Source acquisition methods must be a non-empty string list: {source_id}"
            )

        domain_allowlist = raw_policy.get("domain_allowlist")

        if not isinstance(
            domain_allowlist,
            list,
        ) or not all(
            isinstance(
                domain,
                str,
            )
            for domain in domain_allowlist
        ):
            raise RuntimeError(f"Source domain allowlist must be a string list: {source_id}")

    return payload


def _database_path(
    project_root: Path,
) -> Path:
    return project_root / "data" / "control" / "operations.sqlite3"


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


def _source_slug(
    source_id: str,
) -> str:
    base = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "-",
        source_id,
    ).strip("-")

    if not base:
        base = "source"

    suffix = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:10]

    return f"{base}-{suffix}"


def _append_only_triggers(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    connection.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS
            {table_name}_block_update
        BEFORE UPDATE ON {table_name}
        BEGIN
            SELECT RAISE(
                ABORT,
                '{table_name} is append-only'
            );
        END
        """
    )

    connection.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS
            {table_name}_block_delete
        BEFORE DELETE ON {table_name}
        BEGIN
            SELECT RAISE(
                ABORT,
                '{table_name} is append-only'
            );
        END
        """
    )


def initialize_source_operations(
    project_root: Path,
) -> dict[str, Any]:
    config = _config(project_root)

    database_path = _database_path(project_root)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                source_operation_policies (
                    source_id TEXT PRIMARY KEY,
                    policy_version TEXT NOT NULL,
                    authorization_status TEXT NOT NULL,
                    schedule_enabled INTEGER NOT NULL,
                    freshness_target_hours REAL,
                    maximum_staleness_hours REAL,
                    allowed_acquisition_methods_json TEXT NOT NULL,
                    domain_allowlist_json TEXT NOT NULL,
                    owner TEXT,
                    credential_reference TEXT,
                    parser_version TEXT,
                    schema_version TEXT,
                    browser_automation_status TEXT NOT NULL,
                    configured_at TEXT NOT NULL
                );

            CREATE TABLE IF NOT EXISTS
                source_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    artifact_relative_path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    acquisition_method TEXT NOT NULL,
                    acquisition_run_id TEXT,
                    parent_snapshot_id TEXT,
                    parser_version TEXT,
                    schema_version TEXT,
                    metadata_json TEXT NOT NULL,
                    UNIQUE (
                        source_id,
                        content_sha256
                    )
                );

            CREATE TABLE IF NOT EXISTS
                source_snapshot_events (
                    event_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

            CREATE TABLE IF NOT EXISTS
                source_quarantine_events (
                    event_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    snapshot_id TEXT,
                    reason_code TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );

            CREATE TABLE IF NOT EXISTS
                source_replay_events (
                    event_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

            CREATE INDEX IF NOT EXISTS
                source_snapshots_source_index
            ON source_snapshots (
                source_id,
                acquired_at
            );

            CREATE INDEX IF NOT EXISTS
                source_snapshot_events_snapshot_index
            ON source_snapshot_events (
                snapshot_id,
                occurred_at
            );
            """
        )

        for table_name in APPEND_ONLY_TABLES:
            _append_only_triggers(
                connection,
                table_name,
            )

        configured_at = _iso(_utc_now())

        sources = config["sources"]

        for source_id, policy in sources.items():
            connection.execute(
                """
                INSERT INTO
                    source_operation_policies (
                        source_id,
                        policy_version,
                        authorization_status,
                        schedule_enabled,
                        freshness_target_hours,
                        maximum_staleness_hours,
                        allowed_acquisition_methods_json,
                        domain_allowlist_json,
                        owner,
                        credential_reference,
                        parser_version,
                        schema_version,
                        browser_automation_status,
                        configured_at
                    )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT (
                    source_id
                )
                DO UPDATE SET
                    policy_version = excluded.policy_version,
                    authorization_status =
                        excluded.authorization_status,
                    schedule_enabled =
                        excluded.schedule_enabled,
                    freshness_target_hours =
                        excluded.freshness_target_hours,
                    maximum_staleness_hours =
                        excluded.maximum_staleness_hours,
                    allowed_acquisition_methods_json =
                        excluded.allowed_acquisition_methods_json,
                    domain_allowlist_json =
                        excluded.domain_allowlist_json,
                    owner = excluded.owner,
                    credential_reference =
                        excluded.credential_reference,
                    parser_version =
                        excluded.parser_version,
                    schema_version =
                        excluded.schema_version,
                    browser_automation_status =
                        excluded.browser_automation_status,
                    configured_at =
                        excluded.configured_at
                """,
                (
                    source_id,
                    config["config_version"],
                    policy["authorization_status"],
                    int(policy["schedule_enabled"]),
                    policy["freshness_target_hours"],
                    policy["maximum_staleness_hours"],
                    json.dumps(
                        policy["allowed_acquisition_methods"],
                        sort_keys=True,
                    ),
                    json.dumps(
                        policy["domain_allowlist"],
                        sort_keys=True,
                    ),
                    policy["owner"],
                    policy["credential_reference"],
                    policy["parser_version"],
                    policy["schema_version"],
                    policy["browser_automation_status"],
                    configured_at,
                ),
            )

        connection.commit()

        counts = {}

        for table_name in (
            "source_operation_policies",
            "source_snapshots",
            "source_snapshot_events",
            "source_quarantine_events",
            "source_replay_events",
        ):
            row = connection.execute(
                f"""
                SELECT count(*)
                FROM {table_name}
                """
            ).fetchone()

            if row is None:
                raise RuntimeError(f"No count returned for {table_name}.")

            counts[table_name] = int(row[0])

        trigger_row = connection.execute(
            """
            SELECT count(*)
            FROM sqlite_master
            WHERE
                type = 'trigger'
                AND (
                    name LIKE
                        'source_snapshots_block_%'
                    OR name LIKE
                        'source_snapshot_events_block_%'
                    OR name LIKE
                        'source_quarantine_events_block_%'
                    OR name LIKE
                        'source_replay_events_block_%'
                )
            """
        ).fetchone()

    finally:
        connection.close()

    if trigger_row is None:
        raise RuntimeError("Append-only trigger count returned no row.")

    return {
        "model_version": ("cre-foundry-source-operations-v1"),
        "database_path": str(database_path.relative_to(project_root)),
        "configured_source_count": len(config["sources"]),
        "table_counts": counts,
        "append_only_trigger_count": int(trigger_row[0]),
        "policy": config["policies"],
    }


def register_source_snapshot(
    project_root: Path,
    *,
    source_id: str,
    file_path: Path,
    observed_at: str | None,
    acquisition_method: str,
    content_type: str,
    metadata: dict[str, Any] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    config = _config(project_root)

    policy = config["sources"].get(source_id)

    if policy is None:
        raise RuntimeError(f"Unknown source_id: {source_id}")

    if policy["authorization_status"] not in AUTHORIZED_STATUSES:
        raise RuntimeError(f"Source {source_id} is not authorized.")

    if acquisition_method not in policy["allowed_acquisition_methods"]:
        raise RuntimeError(
            f"Acquisition method is not allowed for {source_id}: {acquisition_method}"
        )

    source_file = file_path.resolve()

    if not source_file.is_file():
        raise RuntimeError(f"Snapshot input is not a file: {source_file}")

    digest = _sha256(source_file)

    snapshot_id = hashlib.sha256((source_id + "\0" + digest).encode("utf-8")).hexdigest()

    observed = _parse_datetime(observed_at)

    acquired = _utc_now()

    relative_artifact = (
        Path("data") / "snapshots" / _source_slug(source_id) / digest[:2] / f"{digest}.blob"
    )

    artifact_path = project_root / relative_artifact

    report = {
        "snapshot_id": snapshot_id,
        "source_id": source_id,
        "content_sha256": digest,
        "byte_size": source_file.stat().st_size,
        "content_type": content_type,
        "observed_at": _iso(observed),
        "acquired_at": _iso(acquired),
        "acquisition_method": acquisition_method,
        "artifact_relative_path": str(relative_artifact),
        "dry_run": dry_run,
        "policy": {
            "content_addressed_storage": True,
            "snapshot_immutable": True,
            "deduplicate": True,
            "operating_mode": "shadow",
        },
    }

    if dry_run:
        report["status"] = "validated"
        return report

    database_path = _database_path(project_root)

    connection = sqlite3.connect(database_path)

    created_artifact = False

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT
                snapshot_id,
                artifact_relative_path
            FROM source_snapshots
            WHERE
                source_id = ?
                AND content_sha256 = ?
            """,
            (
                source_id,
                digest,
            ),
        ).fetchone()

        if existing is not None:
            event_id = str(uuid.uuid4())

            connection.execute(
                """
                INSERT INTO
                    source_snapshot_events (
                        event_id,
                        snapshot_id,
                        source_id,
                        event_type,
                        occurred_at,
                        payload_json
                    )
                VALUES (
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    event_id,
                    str(existing[0]),
                    source_id,
                    "duplicate_observed",
                    _iso(acquired),
                    json.dumps(
                        {
                            "input_path": str(source_file),
                            "content_sha256": digest,
                        },
                        sort_keys=True,
                    ),
                ),
            )

            connection.commit()

            report["snapshot_id"] = str(existing[0])
            report["artifact_relative_path"] = str(existing[1])
            report["status"] = "duplicate"

            return report

        artifact_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = artifact_path.with_name(f".{artifact_path.name}.{uuid.uuid4().hex}.tmp")

        shutil.copyfile(
            source_file,
            temporary_path,
        )

        copied_digest = _sha256(temporary_path)

        if copied_digest != digest:
            temporary_path.unlink(missing_ok=True)

            raise RuntimeError("Snapshot checksum changed during copy.")

        temporary_path.replace(artifact_path)
        created_artifact = True

        metadata_payload = metadata if metadata is not None else {}

        connection.execute(
            """
            INSERT INTO
                source_snapshots (
                    snapshot_id,
                    source_id,
                    content_sha256,
                    artifact_relative_path,
                    content_type,
                    byte_size,
                    observed_at,
                    acquired_at,
                    acquisition_method,
                    acquisition_run_id,
                    parent_snapshot_id,
                    parser_version,
                    schema_version,
                    metadata_json
                )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                snapshot_id,
                source_id,
                digest,
                str(relative_artifact),
                content_type,
                source_file.stat().st_size,
                _iso(observed),
                _iso(acquired),
                acquisition_method,
                None,
                None,
                policy["parser_version"],
                policy["schema_version"],
                json.dumps(
                    metadata_payload,
                    sort_keys=True,
                ),
            ),
        )

        connection.execute(
            """
            INSERT INTO
                source_snapshot_events (
                    event_id,
                    snapshot_id,
                    source_id,
                    event_type,
                    occurred_at,
                    payload_json
                )
            VALUES (
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                str(uuid.uuid4()),
                snapshot_id,
                source_id,
                "registered",
                _iso(acquired),
                json.dumps(
                    {
                        "content_sha256": digest,
                        "artifact_relative_path": str(relative_artifact),
                    },
                    sort_keys=True,
                ),
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()

        if created_artifact:
            artifact_path.unlink(missing_ok=True)

        raise

    finally:
        connection.close()

    report["status"] = "registered"

    return report


def plan_snapshot_replay(
    project_root: Path,
    *,
    snapshot_id: str,
) -> dict[str, Any]:
    database_path = _database_path(project_root)

    connection = sqlite3.connect(database_path)

    try:
        row = connection.execute(
            """
            SELECT
                source_id,
                content_sha256,
                artifact_relative_path,
                parser_version,
                schema_version
            FROM source_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()

    finally:
        connection.close()

    if row is None:
        raise RuntimeError(f"Unknown snapshot_id: {snapshot_id}")

    artifact_path = project_root / str(row[2])

    if not artifact_path.is_file():
        raise RuntimeError(f"Snapshot artifact is missing: {artifact_path}")

    actual_digest = _sha256(artifact_path)

    expected_digest = str(row[1])

    if actual_digest != expected_digest:
        raise RuntimeError("Snapshot checksum verification failed.")

    return {
        "status": "replay_ready",
        "snapshot_id": snapshot_id,
        "source_id": str(row[0]),
        "artifact_relative_path": str(row[2]),
        "content_sha256": expected_digest,
        "parser_version": row[3],
        "schema_version": row[4],
        "reacquire": False,
        "writes_performed": False,
        "operating_mode": "shadow",
    }


def audit_source_operations(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    config = _config(project_root)

    database_path = _database_path(project_root)

    connection = sqlite3.connect(database_path)

    try:
        policy_rows = connection.execute(
            """
            SELECT
                source_id,
                authorization_status,
                schedule_enabled,
                freshness_target_hours,
                maximum_staleness_hours
            FROM source_operation_policies
            ORDER BY source_id
            """
        ).fetchall()

        snapshot_rows = connection.execute(
            """
            SELECT
                snapshot_id,
                source_id,
                content_sha256,
                artifact_relative_path,
                observed_at,
                acquired_at
            FROM source_snapshots
            ORDER BY
                source_id,
                acquired_at
            """
        ).fetchall()

        count_rows = {}

        for table_name in (
            "source_snapshots",
            "source_snapshot_events",
            "source_quarantine_events",
            "source_replay_events",
        ):
            row = connection.execute(
                f"""
                SELECT count(*)
                FROM {table_name}
                """
            ).fetchone()

            if row is None:
                raise RuntimeError(f"No count returned for {table_name}.")

            count_rows[table_name] = int(row[0])

        trigger_row = connection.execute(
            """
            SELECT count(*)
            FROM sqlite_master
            WHERE
                type = 'trigger'
                AND (
                    name LIKE
                        'source_snapshots_block_%'
                    OR name LIKE
                        'source_snapshot_events_block_%'
                    OR name LIKE
                        'source_quarantine_events_block_%'
                    OR name LIKE
                        'source_replay_events_block_%'
                )
            """
        ).fetchone()

    finally:
        connection.close()

    if trigger_row is None:
        raise RuntimeError("Trigger count returned no row.")

    missing_artifacts = []
    checksum_mismatches = []

    latest_by_source: dict[
        str,
        datetime,
    ] = {}

    for row in snapshot_rows:
        snapshot_id = str(row[0])
        source_id = str(row[1])
        expected_digest = str(row[2])
        artifact_path = project_root / str(row[3])

        if not artifact_path.is_file():
            missing_artifacts.append(snapshot_id)
            continue

        actual_digest = _sha256(artifact_path)

        if actual_digest != expected_digest:
            checksum_mismatches.append(snapshot_id)

        observed = _parse_datetime(str(row[4]))

        current = latest_by_source.get(source_id)

        if current is None or observed > current:
            latest_by_source[source_id] = observed

    now = _utc_now()

    source_health = []

    for row in policy_rows:
        source_id = str(row[0])
        latest = latest_by_source.get(source_id)
        maximum_staleness = row[4]

        if latest is None:
            freshness_state = "missing"
            age_hours = None

        else:
            age_hours = round(
                (now - latest).total_seconds() / 3600.0,
                3,
            )

            if maximum_staleness is None:
                freshness_state = "unconfigured"

            elif age_hours > float(maximum_staleness):
                freshness_state = "stale"

            else:
                freshness_state = "current"

        source_health.append(
            {
                "source_id": source_id,
                "authorization_status": str(row[1]),
                "schedule_enabled": bool(row[2]),
                "freshness_target_hours": row[3],
                "maximum_staleness_hours": row[4],
                "latest_observed_at": (_iso(latest) if latest is not None else None),
                "age_hours": age_hours,
                "freshness_state": freshness_state,
            }
        )

    report = {
        "model_version": ("cre-foundry-source-operations-v1"),
        "generated_at": _iso(now),
        "configured_source_count": len(policy_rows),
        "snapshot_count": len(snapshot_rows),
        "table_counts": count_rows,
        "append_only_trigger_count": int(trigger_row[0]),
        "missing_artifact_count": len(missing_artifacts),
        "checksum_mismatch_count": len(checksum_mismatches),
        "missing_artifacts": missing_artifacts,
        "checksum_mismatches": (checksum_mismatches),
        "source_health": source_health,
        "policy": config["policies"],
        "ready": (int(trigger_row[0]) == 8 and not missing_artifacts and not checksum_mismatches),
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "source_operations.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
