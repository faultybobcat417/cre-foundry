from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cre_foundry.data_plane import (
    discover_source_commands,
)
from cre_foundry.source_operations import (
    AUTHORIZED_STATUSES,
)

APPEND_ONLY_TABLES = (
    "source_runtime_events",
    "source_schedule_events",
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(
    value: datetime,
) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_optional_datetime(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

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


def _load_json_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _runtime_config(
    project_root: Path,
) -> dict[str, Any]:
    path = project_root / "config" / "source_runtime.json"

    payload = _load_json_object(path)

    expected_policy: dict[str, Any] = {
        "operating_mode": "shadow",
        "automatic_execution": False,
        "automatic_browser_execution": False,
        "automatic_computer_vision_execution": False,
        "automatic_conclusions": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "failure_threshold": 3,
        "base_backoff_seconds": 900,
        "maximum_backoff_seconds": 21600,
    }

    raw_policy = payload.get("policies")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Source-runtime policies must be a JSON object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != expected_policy:
        raise RuntimeError("Source-runtime policy does not match the required safety policy.")

    raw_sources = payload.get("sources")

    if (
        not isinstance(
            raw_sources,
            dict,
        )
        or not raw_sources
    ):
        raise RuntimeError("Source-runtime config contains no sources.")

    for source_id, raw_source in raw_sources.items():
        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id
        ):
            raise RuntimeError("Runtime source IDs must be non-empty strings.")

        if not isinstance(
            raw_source,
            dict,
        ):
            raise RuntimeError(f"Runtime source policy must be an object: {source_id}")

        command = raw_source.get("command")

        if (
            not isinstance(
                command,
                str,
            )
            or not command
        ):
            raise RuntimeError(f"Runtime source requires an exact command: {source_id}")

        interval = raw_source.get("interval_seconds")

        if interval is not None and (
            not isinstance(
                interval,
                int,
            )
            or interval <= 0
        ):
            raise RuntimeError(f"interval_seconds must be null or positive: {source_id}")

    return payload


def _database_path(
    project_root: Path,
) -> Path:
    return project_root / "data" / "control" / "operations.sqlite3"


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


def initialize_source_runtime(
    project_root: Path,
) -> dict[str, Any]:
    config = _runtime_config(project_root)

    database_path = _database_path(project_root)

    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")

        policy_rows = connection.execute(
            """
            SELECT
                source_id
            FROM source_operation_policies
            ORDER BY source_id
            """
        ).fetchall()

        policy_source_ids = {str(row[0]) for row in policy_rows}

        configured_source_ids = set(str(source_id) for source_id in config["sources"])

        if policy_source_ids != configured_source_ids:
            raise RuntimeError(
                "Runtime sources do not match "
                "source-operation policies. "
                f"Runtime-only: "
                f"{sorted(configured_source_ids - policy_source_ids)}; "
                f"policy-only: "
                f"{sorted(policy_source_ids - configured_source_ids)}"
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                source_runtime_state (
                    source_id TEXT PRIMARY KEY,
                    config_version TEXT NOT NULL,
                    consecutive_failures INTEGER NOT NULL,
                    circuit_state TEXT NOT NULL,
                    circuit_open_until TEXT,
                    next_due_at TEXT,
                    last_started_at TEXT,
                    last_completed_at TEXT,
                    last_status TEXT,
                    last_snapshot_id TEXT,
                    last_content_changed INTEGER,
                    updated_at TEXT NOT NULL,
                    CHECK (
                        circuit_state IN (
                            'closed',
                            'open',
                            'half_open'
                        )
                    )
                );

            CREATE TABLE IF NOT EXISTS
                source_runtime_events (
                    event_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    run_id TEXT,
                    event_type TEXT NOT NULL,
                    status TEXT,
                    snapshot_id TEXT,
                    occurred_at TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );

            CREATE TABLE IF NOT EXISTS
                source_schedule_events (
                    event_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    planned_for TEXT,
                    details_json TEXT NOT NULL
                );

            CREATE INDEX IF NOT EXISTS
                source_runtime_events_source_index
            ON source_runtime_events (
                source_id,
                occurred_at
            );

            CREATE INDEX IF NOT EXISTS
                source_schedule_events_source_index
            ON source_schedule_events (
                source_id,
                occurred_at
            );
            """
        )

        for table_name in APPEND_ONLY_TABLES:
            _append_only_triggers(
                connection,
                table_name,
            )

        now = _iso(_utc_now())

        for source_id in sorted(configured_source_ids):
            connection.execute(
                """
                INSERT INTO
                    source_runtime_state (
                        source_id,
                        config_version,
                        consecutive_failures,
                        circuit_state,
                        circuit_open_until,
                        next_due_at,
                        last_started_at,
                        last_completed_at,
                        last_status,
                        last_snapshot_id,
                        last_content_changed,
                        updated_at
                    )
                VALUES (
                    ?, ?, 0, 'closed',
                    NULL, NULL, NULL, NULL,
                    NULL, NULL, NULL, ?
                )
                ON CONFLICT (
                    source_id
                )
                DO UPDATE SET
                    config_version =
                        excluded.config_version,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    source_id,
                    config["config_version"],
                    now,
                ),
            )

        connection.commit()

        state_row = connection.execute(
            """
            SELECT count(*)
            FROM source_runtime_state
            """
        ).fetchone()

        trigger_row = connection.execute(
            """
            SELECT count(*)
            FROM sqlite_master
            WHERE
                type = 'trigger'
                AND (
                    name LIKE
                        'source_runtime_events_block_%'
                    OR name LIKE
                        'source_schedule_events_block_%'
                )
            """
        ).fetchone()

    finally:
        connection.close()

    if state_row is None:
        raise RuntimeError("Runtime-state count returned no row.")

    if trigger_row is None:
        raise RuntimeError("Runtime-trigger count returned no row.")

    return {
        "model_version": ("cre-foundry-source-runtime-v1"),
        "database_path": str(database_path.relative_to(project_root)),
        "runtime_state_count": int(state_row[0]),
        "append_only_trigger_count": int(trigger_row[0]),
        "policy": config["policies"],
    }


def plan_source_acquisitions(
    project_root: Path,
    *,
    now: datetime | None = None,
    write_contract: bool = True,
) -> dict[str, Any]:
    config = _runtime_config(project_root)

    effective_now = (
        now.astimezone(UTC)
        if now is not None and now.tzinfo is not None
        else (now.replace(tzinfo=UTC) if now is not None else _utc_now())
    )

    registered_commands = set(
        discover_source_commands(project_root / "src" / "cre_foundry" / "cli.py")
    )

    database_path = _database_path(project_root)

    connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

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

        state_rows = connection.execute(
            """
            SELECT
                source_id,
                consecutive_failures,
                circuit_state,
                circuit_open_until,
                next_due_at,
                last_started_at,
                last_completed_at,
                last_status,
                last_snapshot_id,
                last_content_changed
            FROM source_runtime_state
            ORDER BY source_id
            """
        ).fetchall()

    finally:
        connection.close()

    policies = {str(row["source_id"]): row for row in policy_rows}

    states = {str(row["source_id"]): row for row in state_rows}

    plans = []

    for source_id, raw_runtime in sorted(config["sources"].items()):
        if not isinstance(
            raw_runtime,
            dict,
        ):
            raise RuntimeError(f"Invalid runtime source: {source_id}")

        policy = policies.get(source_id)

        state = states.get(source_id)

        if policy is None:
            raise RuntimeError(f"Missing source-operation policy: {source_id}")

        if state is None:
            raise RuntimeError(f"Missing source-runtime state: {source_id}")

        command = str(raw_runtime["command"])

        command_registered = command in registered_commands

        runtime_schedule_enabled = bool(raw_runtime["schedule_enabled"])

        policy_schedule_enabled = bool(policy["schedule_enabled"])

        schedule_enabled = runtime_schedule_enabled and policy_schedule_enabled

        interval_seconds = raw_runtime.get("interval_seconds")

        authorization_status = str(policy["authorization_status"])

        circuit_state = str(state["circuit_state"])

        circuit_open_until = _parse_optional_datetime(state["circuit_open_until"])

        next_due_at = _parse_optional_datetime(state["next_due_at"])

        reason: str
        status: str

        if authorization_status not in AUTHORIZED_STATUSES:
            status = "blocked"
            reason = "source_not_authorized"

        elif not command_registered:
            status = "blocked"
            reason = "command_not_registered"

        elif not runtime_schedule_enabled:
            status = "disabled"
            reason = "runtime_schedule_disabled"

        elif not policy_schedule_enabled:
            status = "disabled"
            reason = "policy_schedule_disabled"

        elif interval_seconds is None:
            status = "blocked"
            reason = "cadence_unconfigured"

        elif (
            circuit_state == "open"
            and circuit_open_until is not None
            and circuit_open_until > effective_now
        ):
            status = "blocked"
            reason = "circuit_open"

        elif next_due_at is not None and next_due_at > effective_now:
            status = "not_due"
            reason = "next_due_in_future"

        else:
            status = "due"
            reason = "source_due"

        plans.append(
            {
                "source_id": source_id,
                "command": command,
                "command_registered": (command_registered),
                "authorization_status": (authorization_status),
                "runtime_schedule_enabled": (runtime_schedule_enabled),
                "policy_schedule_enabled": (policy_schedule_enabled),
                "effective_schedule_enabled": (schedule_enabled),
                "interval_seconds": (interval_seconds),
                "freshness_target_hours": (policy["freshness_target_hours"]),
                "maximum_staleness_hours": (policy["maximum_staleness_hours"]),
                "consecutive_failures": int(state["consecutive_failures"]),
                "circuit_state": circuit_state,
                "circuit_open_until": (
                    _iso(circuit_open_until) if circuit_open_until is not None else None
                ),
                "next_due_at": (_iso(next_due_at) if next_due_at is not None else None),
                "last_status": state["last_status"],
                "last_snapshot_id": state["last_snapshot_id"],
                "status": status,
                "reason": reason,
                "automatic_execution_permitted": False,
                "browser_execution_permitted": False,
                "computer_vision_execution_permitted": False,
            }
        )

    status_counts: dict[str, int] = {}

    for plan in plans:
        status = str(plan["status"])

        status_counts[status] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    report = {
        "model_version": ("cre-foundry-source-runtime-plan-v1"),
        "generated_at": _iso(effective_now),
        "source_count": len(plans),
        "status_counts": status_counts,
        "plans": plans,
        "policy": config["policies"],
        "automatic_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "source_acquisition_plan.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report


def audit_source_runtime(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    config = _runtime_config(project_root)

    database_path = _database_path(project_root)

    registered_commands = set(
        discover_source_commands(project_root / "src" / "cre_foundry" / "cli.py")
    )

    connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

    try:
        state_rows = connection.execute(
            """
            SELECT
                source_id,
                consecutive_failures,
                circuit_state,
                circuit_open_until,
                next_due_at,
                last_status,
                updated_at
            FROM source_runtime_state
            ORDER BY source_id
            """
        ).fetchall()

        policy_rows = connection.execute(
            """
            SELECT
                source_id
            FROM source_operation_policies
            ORDER BY source_id
            """
        ).fetchall()

        trigger_row = connection.execute(
            """
            SELECT count(*)
            FROM sqlite_master
            WHERE
                type = 'trigger'
                AND (
                    name LIKE
                        'source_runtime_events_block_%'
                    OR name LIKE
                        'source_schedule_events_block_%'
                )
            """
        ).fetchone()

        event_row = connection.execute(
            """
            SELECT
                (
                    SELECT count(*)
                    FROM source_runtime_events
                ),
                (
                    SELECT count(*)
                    FROM source_schedule_events
                )
            """
        ).fetchone()

    finally:
        connection.close()

    if trigger_row is None:
        raise RuntimeError("Runtime trigger query returned no row.")

    if event_row is None:
        raise RuntimeError("Runtime event query returned no row.")

    configured_sources = set(str(source_id) for source_id in config["sources"])

    state_sources = {str(row["source_id"]) for row in state_rows}

    policy_sources = {str(row["source_id"]) for row in policy_rows}

    missing_state_sources = sorted(configured_sources - state_sources)

    unexpected_state_sources = sorted(state_sources - configured_sources)

    policy_mismatch = sorted(configured_sources ^ policy_sources)

    unregistered_commands = {
        source_id: raw_source["command"]
        for source_id, raw_source in config["sources"].items()
        if (
            isinstance(
                raw_source,
                dict,
            )
            and raw_source["command"] not in registered_commands
        )
    }

    enabled_schedule_sources = [
        source_id
        for source_id, raw_source in config["sources"].items()
        if (
            isinstance(
                raw_source,
                dict,
            )
            and bool(raw_source["schedule_enabled"])
        )
    ]

    runtime_states = [
        {
            "source_id": str(row["source_id"]),
            "consecutive_failures": int(row["consecutive_failures"]),
            "circuit_state": str(row["circuit_state"]),
            "circuit_open_until": row["circuit_open_until"],
            "next_due_at": row["next_due_at"],
            "last_status": row["last_status"],
            "updated_at": str(row["updated_at"]),
        }
        for row in state_rows
    ]

    ready = (
        not missing_state_sources
        and not unexpected_state_sources
        and not policy_mismatch
        and not unregistered_commands
        and int(trigger_row[0]) == 4
    )

    report = {
        "model_version": ("cre-foundry-source-runtime-v1"),
        "generated_at": _iso(_utc_now()),
        "configured_source_count": len(configured_sources),
        "runtime_state_count": len(state_sources),
        "missing_state_sources": (missing_state_sources),
        "unexpected_state_sources": (unexpected_state_sources),
        "policy_source_mismatch": (policy_mismatch),
        "unregistered_commands": (unregistered_commands),
        "enabled_schedule_sources": (enabled_schedule_sources),
        "append_only_trigger_count": int(trigger_row[0]),
        "runtime_event_count": int(event_row[0]),
        "schedule_event_count": int(event_row[1]),
        "runtime_states": runtime_states,
        "policy": config["policies"],
        "ready": ready,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "source_runtime.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report


def discover_snapshot_bootstrap_candidates(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    database_path = _database_path(project_root)

    connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

    try:
        source_columns = connection.execute(
            """
            PRAGMA table_info(source_runs)
            """
        ).fetchall()

        column_names = [str(column[1]) for column in source_columns]

        source_column = next(
            (
                candidate
                for candidate in (
                    "source_id",
                    "source_name",
                    "name",
                )
                if candidate in column_names
            ),
            None,
        )

        path_columns = [
            column_name
            for column_name in column_names
            if any(
                fragment in column_name.lower()
                for fragment in (
                    "path",
                    "file",
                    "artifact",
                    "output",
                    "snapshot",
                )
            )
        ]

        rows = connection.execute(
            """
            SELECT *
            FROM source_runs
            ORDER BY rowid
            """
        ).fetchall()

        configured_rows = connection.execute(
            """
            SELECT source_id
            FROM source_operation_policies
            ORDER BY source_id
            """
        ).fetchall()

    finally:
        connection.close()

    configured_sources = {str(row[0]) for row in configured_rows}

    exact_candidates = []
    rejected_candidates = []
    seen = set()

    if source_column is not None:
        for row in rows:
            raw_source_id = row[source_column]

            if raw_source_id is None:
                continue

            source_id = str(raw_source_id)

            if source_id not in configured_sources:
                continue

            for path_column in path_columns:
                raw_path = row[path_column]

                if (
                    raw_path is None
                    or not isinstance(
                        raw_path,
                        str,
                    )
                    or not raw_path.strip()
                ):
                    continue

                candidate_path = Path(raw_path).expanduser()

                if not candidate_path.is_absolute():
                    candidate_path = project_root / candidate_path

                candidate_path = candidate_path.resolve()

                key = (
                    source_id,
                    str(candidate_path),
                )

                if key in seen:
                    continue

                seen.add(key)

                payload: dict[str, Any] = {
                    "source_id": source_id,
                    "path_column": path_column,
                    "path": str(candidate_path),
                    "provenance": ("source_runs_explicit_path"),
                }

                if candidate_path.is_file():
                    payload["size_bytes"] = candidate_path.stat().st_size

                    exact_candidates.append(payload)

                else:
                    payload["reason"] = "path_not_file"

                    rejected_candidates.append(payload)

    storage_inventory = []

    for relative_root in (
        Path("data/raw"),
        Path("data/bronze"),
        Path("data/landing"),
    ):
        absolute_root = project_root / relative_root

        files = []

        if absolute_root.exists():
            for path in sorted(absolute_root.rglob("*")):
                if path.is_file():
                    files.append(
                        {
                            "path": str(path.relative_to(project_root)),
                            "size_bytes": (path.stat().st_size),
                            "suffix": path.suffix.lower(),
                        }
                    )

        storage_inventory.append(
            {
                "root": str(relative_root),
                "file_count": len(files),
                "files": files,
            }
        )

    report = {
        "model_version": ("cre-foundry-source-bootstrap-v1"),
        "generated_at": _iso(_utc_now()),
        "source_runs_columns": column_names,
        "source_id_column": source_column,
        "path_columns": path_columns,
        "source_run_count": len(rows),
        "configured_source_count": len(configured_sources),
        "exact_candidate_count": len(exact_candidates),
        "rejected_candidate_count": len(rejected_candidates),
        "exact_candidates": exact_candidates,
        "rejected_candidates": (rejected_candidates),
        "storage_inventory": storage_inventory,
        "automatic_registration_performed": False,
        "review_required_before_registration": True,
        "policy": {
            "exact_source_attribution_required": True,
            "explicit_file_path_required": True,
            "ambiguous_files_not_registered": True,
            "operating_mode": "shadow",
        },
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "source_snapshot_bootstrap.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
