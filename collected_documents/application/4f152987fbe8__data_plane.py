from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

SOURCE_COMMAND_PATTERN = re.compile(
    r"""@source_app\.command\(\s*["']([^"']+)["']""",
    re.MULTILINE,
)


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    kind: str
    required_tokens: tuple[str, ...]
    preferred_tokens: tuple[str, ...]
    aliases: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class ResolvedStage:
    stage_id: str
    kind: str
    command: str | None
    required: bool
    resolution: str


BRAMPTON_STAGE_SPECS: tuple[StageSpec, ...] = (
    StageSpec(
        stage_id="permit_rules",
        kind="transform",
        required_tokens=(
            "brampton",
            "permit",
        ),
        preferred_tokens=(
            "rule",
            "rules",
            "classifier",
        ),
        aliases=(
            "build-brampton-permit-rules",
            "compile-brampton-permit-rules",
        ),
        required=False,
    ),
    StageSpec(
        stage_id="permits_bronze",
        kind="acquisition",
        required_tokens=(
            "brampton",
            "permit",
        ),
        preferred_tokens=(
            "acquire",
            "fetch",
            "bronze",
            "snapshot",
        ),
        aliases=(
            "acquire-brampton-permits",
            "acquire-brampton-permit-snapshots",
            "fetch-brampton-permits",
            "build-brampton-permits-bronze",
        ),
    ),
    StageSpec(
        stage_id="permit_lifecycle",
        kind="validation",
        required_tokens=(
            "brampton",
            "permit",
        ),
        preferred_tokens=(
            "lifecycle",
            "terminal",
            "status",
        ),
        aliases=(
            "inspect-brampton-permits",
            "build-brampton-permit-lifecycle",
            "classify-brampton-permit-lifecycle",
        ),
    ),
    StageSpec(
        stage_id="permit_silver",
        kind="transform",
        required_tokens=(
            "brampton",
            "permit",
        ),
        preferred_tokens=(
            "silver",
            "normalize",
            "normalized",
        ),
        aliases=(
            "build-brampton-permit-silver",
            "normalize-brampton-permits",
        ),
    ),
    StageSpec(
        stage_id="permit_entity_bridge",
        kind="transform",
        required_tokens=(
            "brampton",
            "permit",
            "entity",
        ),
        preferred_tokens=(
            "bridge",
            "historical",
            "exact",
        ),
        aliases=(
            "build-brampton-permit-entity-bridge",
            "bridge-brampton-permits-to-entities",
        ),
    ),
    StageSpec(
        stage_id="business_directory_bronze",
        kind="acquisition",
        required_tokens=(
            "brampton",
            "business",
            "directory",
        ),
        preferred_tokens=(
            "acquire",
            "fetch",
            "bronze",
            "snapshot",
        ),
        aliases=(
            "acquire-brampton-business-directory",
            "fetch-brampton-business-directory",
            "build-brampton-business-directory-bronze",
        ),
    ),
    StageSpec(
        stage_id="business_directory_silver",
        kind="transform",
        required_tokens=(
            "brampton",
            "business",
            "directory",
        ),
        preferred_tokens=(
            "silver",
            "normalize",
            "normalized",
        ),
        aliases=(
            "build-brampton-business-directory-silver",
            "normalize-brampton-business-directory",
        ),
    ),
    StageSpec(
        stage_id="permit_directory_bridge",
        kind="transform",
        required_tokens=(
            "brampton",
            "permit",
            "directory",
        ),
        preferred_tokens=(
            "bridge",
            "current",
            "address",
        ),
        aliases=(
            "build-brampton-permit-directory-bridge",
            "bridge-brampton-permits-to-directory",
        ),
    ),
    StageSpec(
        stage_id="cross_source_reconciliation",
        kind="transform",
        required_tokens=(
            "brampton",
            "cross",
            "source",
        ),
        preferred_tokens=(
            "reconciliation",
            "reconcile",
        ),
        aliases=(
            "build-brampton-cross-source-reconciliation",
            "reconcile-brampton-cross-source-records",
        ),
    ),
    StageSpec(
        stage_id="opportunity_evidence",
        kind="transform",
        required_tokens=(
            "brampton",
            "permit",
            "opportunity",
            "evidence",
        ),
        preferred_tokens=(
            "build",
            "unified",
        ),
        aliases=(
            "build-brampton-permit-opportunity-evidence",
            "build-brampton-opportunity-evidence",
        ),
    ),
    StageSpec(
        stage_id="verification_plan",
        kind="transform",
        required_tokens=(
            "brampton",
            "permit",
            "verification",
            "plan",
        ),
        preferred_tokens=(
            "build",
            "task",
            "gate",
        ),
        aliases=(
            "build-brampton-permit-verification-plan",
            "build-brampton-verification-plan",
        ),
    ),
    StageSpec(
        stage_id="initialize_verification_ledger",
        kind="control",
        required_tokens=(
            "brampton",
            "verification",
            "ledger",
        ),
        preferred_tokens=(
            "initialize",
            "init",
        ),
        aliases=("initialize-brampton-verification-ledger",),
        required=False,
    ),
    StageSpec(
        stage_id="project_verification_state",
        kind="control",
        required_tokens=(
            "brampton",
            "verification",
            "state",
        ),
        preferred_tokens=(
            "project",
            "projection",
        ),
        aliases=("project-brampton-verification-state",),
    ),
)


PIPELINES: dict[str, tuple[StageSpec, ...]] = {
    "brampton_operational": BRAMPTON_STAGE_SPECS,
}


EXACT_STAGE_COMMANDS: dict[str, str] = {
    "business_directory_bronze": ("acquire-brampton-business-directory"),
    "business_directory_silver": ("build-brampton-business-directory-silver"),
    "cross_source_reconciliation": ("build-brampton-cross-source-reconciliation"),
    "initialize_verification_ledger": ("initialize-brampton-verification-ledger"),
    "opportunity_evidence": ("build-brampton-permit-opportunity-evidence"),
    "permit_directory_bridge": ("build-brampton-permit-directory-bridge"),
    "permit_entity_bridge": ("build-brampton-permit-entity-bridge"),
    "permit_lifecycle": "inspect-brampton-permits",
    "permit_silver": "build-brampton-permit-silver",
    "permits_bronze": "acquire-brampton-permits",
    "project_verification_state": ("project-brampton-verification-state"),
    "verification_plan": ("build-brampton-permit-verification-plan"),
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%S%fZ")


def _atomic_write_text(
    path: Path,
    text: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")

    try:
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

        temporary.replace(path)

    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(
    path: Path,
    value: Any,
) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
    )


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    path = project_root / "config" / "data_plane.json"

    if not path.exists():
        raise RuntimeError(f"Missing data-plane config: {path}")

    parsed = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        parsed,
        dict,
    ):
        raise RuntimeError("Data-plane config must be a JSON object.")

    required = {
        "minimum_free_disk_gib",
        "default_stage_timeout_seconds",
        "acquisition_retries",
        "transform_retries",
        "retry_base_seconds",
        "policies",
    }

    missing = required - set(parsed)

    if missing:
        raise RuntimeError(f"Data-plane config is missing: {sorted(missing)}")

    policies = parsed["policies"]

    if not isinstance(
        policies,
        dict,
    ):
        raise RuntimeError("Data-plane policies must be an object.")

    expected_policy = {
        "operating_mode": "shadow",
        "automatic_conclusions": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "require_exclusive_lock": True,
        "fail_fast": True,
        "allow_partial_batch_success": False,
    }

    for key, expected in expected_policy.items():
        actual = policies.get(key)

        if actual != expected:
            raise RuntimeError(
                f"Unsafe data-plane policy {key}: expected {expected!r}, found {actual!r}"
            )

    return parsed


def _normalized_tokens(
    value: str,
) -> set[str]:
    raw_tokens = {
        token
        for token in re.split(
            r"[^a-z0-9]+",
            value.lower(),
        )
        if token
    }

    tokens = set(raw_tokens)

    for token in raw_tokens:
        if token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])

    return tokens


def discover_source_commands(
    cli_path: Path,
) -> list[str]:
    text = cli_path.read_text(encoding="utf-8")

    commands = sorted(set(SOURCE_COMMAND_PATTERN.findall(text)))

    if not commands:
        raise RuntimeError("No source commands were discovered.")

    return commands


def _resolve_stage(
    spec: StageSpec,
    commands: Sequence[str],
) -> ResolvedStage:
    command_set = set(commands)

    bound_command = EXACT_STAGE_COMMANDS.get(spec.stage_id)

    if bound_command is None:
        if spec.required:
            raise RuntimeError(
                f"No static command binding exists for required stage {spec.stage_id}."
            )

        return ResolvedStage(
            stage_id=spec.stage_id,
            kind=spec.kind,
            command=None,
            required=False,
            resolution="optional_static_binding_absent",
        )

    if bound_command not in command_set:
        raise RuntimeError(
            "The statically bound command "
            f"{bound_command!r} for stage "
            f"{spec.stage_id!r} is not registered "
            "in the current CLI."
        )

    return ResolvedStage(
        stage_id=spec.stage_id,
        kind=spec.kind,
        command=bound_command,
        required=spec.required,
        resolution="exact_static_binding",
    )


def build_data_plane_plan(
    project_root: Path,
    *,
    pipeline: str,
    include_acquisition: bool,
) -> dict[str, Any]:
    _load_config(project_root)

    specs = PIPELINES.get(pipeline)

    if specs is None:
        raise RuntimeError(f"Unknown data pipeline: {pipeline}")

    commands = discover_source_commands(project_root / "src" / "cre_foundry" / "cli.py")

    stages = [
        _resolve_stage(
            spec,
            commands,
        )
        for spec in specs
    ]

    executable_stages: list[dict[str, Any]] = []

    for position, stage in enumerate(
        stages,
        start=1,
    ):
        skip_reason: str | None = None

        if stage.command is None:
            skip_reason = "optional command unavailable"

        elif stage.kind == "acquisition" and not include_acquisition:
            skip_reason = "acquisition disabled"

        executable_stages.append(
            {
                "position": position,
                **asdict(stage),
                "enabled": (skip_reason is None),
                "skip_reason": (skip_reason),
            }
        )

    return {
        "plan_version": ("cre-foundry-data-plane-plan-v1"),
        "generated_at": _timestamp(),
        "pipeline": pipeline,
        "include_acquisition": (include_acquisition),
        "discovered_source_command_count": len(commands),
        "discovered_source_commands": (commands),
        "stages": executable_stages,
        "policy": {
            "operating_mode": "shadow",
            "automatic_conclusions": False,
            "opportunity_ranked": False,
            "outreach_eligible": False,
            "queue_priority_is_ranking": False,
        },
    }


def _tool_version(
    command: Sequence[str],
) -> str | None:
    try:
        completed = subprocess.run(
            list(command),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ):
        return None

    output = completed.stdout.strip() or completed.stderr.strip()

    return output.splitlines()[0] if output else None


def _quote_identifier(
    value: str,
) -> str:
    return (
        '"'
        + value.replace(
            '"',
            '""',
        )
        + '"'
    )


def _datetime_text(
    value: Any,
) -> str | None:
    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        parsed = value

    else:
        try:
            parsed = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            return str(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _age_days(
    value: Any,
) -> float | None:
    if value is None:
        return None

    parsed_value: datetime

    if isinstance(
        value,
        datetime,
    ):
        parsed_value = value

    else:
        try:
            parsed_value = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            return None

    if parsed_value.tzinfo is None:
        parsed_value = parsed_value.replace(tzinfo=UTC)

    delta = _utc_now() - parsed_value.astimezone(UTC)

    seconds: float = delta.total_seconds()

    return round(
        seconds / 86400.0,
        3,
    )


def _freshness_column(
    columns: Sequence[tuple[str, str]],
) -> str | None:
    preferred_fragments = (
        "as_of",
        "snapshot",
        "observed",
        "application_at",
        "recorded_at",
        "updated_at",
        "created_at",
        "timestamp",
        "date",
        "_at",
    )

    timestamp_like = [
        name
        for name, data_type in columns
        if ("TIMESTAMP" in data_type.upper() or data_type.upper() == "DATE")
    ]

    for fragment in preferred_fragments:
        for name in timestamp_like:
            if fragment in name.lower():
                return name

    return timestamp_like[0] if timestamp_like else None


def _warehouse_inventory(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = project_root / "data" / "warehouse" / "cre.duckdb"

    if not warehouse.exists():
        return {
            "exists": False,
            "path": str(warehouse.relative_to(project_root)),
            "tables": [],
            "views": [],
        }

    connection = duckdb.connect(
        str(warehouse),
        read_only=True,
    )

    try:
        table_rows = connection.execute(
            """
            SELECT
                table_schema,
                table_name,
                table_type
            FROM
                information_schema.tables
            WHERE
                table_schema NOT IN (
                    'information_schema',
                    'pg_catalog'
                )
            ORDER BY
                table_schema,
                table_name
            """
        ).fetchall()

        column_rows = connection.execute(
            """
            SELECT
                table_schema,
                table_name,
                column_name,
                data_type,
                ordinal_position
            FROM
                information_schema.columns
            WHERE
                table_schema NOT IN (
                    'information_schema',
                    'pg_catalog'
                )
            ORDER BY
                table_schema,
                table_name,
                ordinal_position
            """
        ).fetchall()

        columns_by_table: dict[
            tuple[str, str],
            list[tuple[str, str]],
        ] = {}

        for (
            schema_name,
            table_name,
            column_name,
            data_type,
            _,
        ) in column_rows:
            key = (
                str(schema_name),
                str(table_name),
            )

            columns_by_table.setdefault(
                key,
                [],
            ).append(
                (
                    str(column_name),
                    str(data_type),
                )
            )

        tables: list[dict[str, Any]] = []

        views: list[dict[str, Any]] = []

        for (
            schema_name_value,
            table_name_value,
            table_type_value,
        ) in table_rows:
            schema_name = str(schema_name_value)
            table_name = str(table_name_value)
            table_type = str(table_type_value)

            key = (
                schema_name,
                table_name,
            )

            columns = columns_by_table.get(
                key,
                [],
            )

            item: dict[str, Any] = {
                "schema": schema_name,
                "name": table_name,
                "type": table_type,
                "column_count": len(columns),
                "freshness_column": None,
                "max_observed_at": None,
                "age_days": None,
            }

            if table_type == "BASE TABLE":
                qualified = f"{_quote_identifier(schema_name)}.{_quote_identifier(table_name)}"

                count_row = connection.execute(
                    f"""
                    SELECT count(*)
                    FROM {qualified}
                    """
                ).fetchone()

                if count_row is None:
                    raise RuntimeError(
                        f"Warehouse row-count query returned no row for {qualified}."
                    )

                item["row_count"] = int(count_row[0])

                freshness_column = _freshness_column(columns)

                item["freshness_column"] = freshness_column

                if freshness_column is not None:
                    quoted_column = _quote_identifier(freshness_column)

                    freshness_row = connection.execute(
                        f"""
                            SELECT max(
                                try_cast(
                                    {quoted_column}
                                    AS TIMESTAMP
                                )
                            )
                            FROM {qualified}
                            """
                    ).fetchone()

                    if freshness_row is not None:
                        maximum = freshness_row[0]

                        item["max_observed_at"] = _datetime_text(maximum)

                        item["age_days"] = _age_days(maximum)

                tables.append(item)

            else:
                views.append(item)

    finally:
        connection.close()

    stat = warehouse.stat()

    return {
        "exists": True,
        "path": str(warehouse.relative_to(project_root)),
        "size_bytes": stat.st_size,
        "modified_at": _datetime_text(
            datetime.fromtimestamp(
                stat.st_mtime,
                tz=UTC,
            )
        ),
        "table_count": len(tables),
        "view_count": len(views),
        "tables": tables,
        "views": views,
    }


def _sqlite_inventory(
    project_root: Path,
) -> dict[str, Any]:
    database = project_root / "data" / "control" / "operations.sqlite3"

    if not database.exists():
        return {
            "exists": False,
            "path": str(database.relative_to(project_root)),
            "tables": [],
            "triggers": [],
        }

    connection = sqlite3.connect(database)

    try:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        trigger_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
            ORDER BY name
            """
        ).fetchall()

        table_inventory: list[dict[str, Any]] = []

        for row in table_rows:
            table_name = str(row[0])

            quoted = _quote_identifier(table_name)

            count_row = connection.execute(
                f"""
                SELECT count(*)
                FROM {quoted}
                """
            ).fetchone()

            if count_row is None:
                raise RuntimeError(f"SQLite row-count query returned no row for {table_name}.")

            table_inventory.append(
                {
                    "name": table_name,
                    "row_count": int(count_row[0]),
                }
            )

    finally:
        connection.close()

    stat = database.stat()

    return {
        "exists": True,
        "path": str(database.relative_to(project_root)),
        "size_bytes": stat.st_size,
        "modified_at": _datetime_text(
            datetime.fromtimestamp(
                stat.st_mtime,
                tz=UTC,
            )
        ),
        "tables": table_inventory,
        "triggers": [str(row[0]) for row in trigger_rows],
    }


def _git_metadata(
    project_root: Path,
) -> dict[str, Any]:
    def run_git(
        *arguments: str,
    ) -> str:
        completed = subprocess.run(
            [
                "git",
                *arguments,
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return completed.stdout.strip()

    return {
        "commit": run_git(
            "rev-parse",
            "HEAD",
        ),
        "short_commit": run_git(
            "rev-parse",
            "--short",
            "HEAD",
        ),
        "branch": run_git(
            "branch",
            "--show-current",
        ),
        "worktree_clean": (
            run_git(
                "status",
                "--short",
            )
            == ""
        ),
    }


def _guard_existing_policy(
    project_root: Path,
) -> None:
    paths = (
        project_root / "docs" / "data_contracts" / "brampton_verification_ledger.json",
        project_root / "docs" / "data_contracts" / "brampton_verification_review_packets.json",
    )

    for path in paths:
        if not path.exists():
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))

        policy = payload.get(
            "policy",
            {},
        )

        if policy.get("operating_mode") != "shadow":
            raise RuntimeError(f"Non-shadow policy in {path}.")

        if policy.get("opportunity_ranked"):
            raise RuntimeError(f"Ranking enabled in {path}.")

        if policy.get("outreach_eligible"):
            raise RuntimeError(f"Outreach enabled in {path}.")


def build_data_plane_readiness(
    project_root: Path,
    *,
    write_contract: bool,
) -> dict[str, Any]:
    config = _load_config(project_root)

    _guard_existing_policy(project_root)

    disk = shutil.disk_usage(project_root)

    free_disk_gib = disk.free / (1024**3)

    minimum_free_disk_gib = float(config["minimum_free_disk_gib"])

    if free_disk_gib < minimum_free_disk_gib:
        raise RuntimeError(
            "Insufficient free disk space: "
            f"{free_disk_gib:.2f} GiB available; "
            f"{minimum_free_disk_gib:.2f} GiB required."
        )

    plan = build_data_plane_plan(
        project_root,
        pipeline="brampton_operational",
        include_acquisition=False,
    )

    unresolved_required = [
        stage["stage_id"]
        for stage in plan["stages"]
        if (stage["required"] and stage["command"] is None)
    ]

    report: dict[str, Any] = {
        "readiness_version": ("cre-foundry-data-plane-readiness-v1"),
        "generated_at": _timestamp(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "uv_version": _tool_version(
                (
                    "uv",
                    "--version",
                )
            ),
            "git_version": _tool_version(
                (
                    "git",
                    "--version",
                )
            ),
            "free_disk_gib": round(
                free_disk_gib,
                3,
            ),
            "minimum_free_disk_gib": (minimum_free_disk_gib),
        },
        "git": _git_metadata(project_root),
        "pipeline_plan": plan,
        "warehouse": _warehouse_inventory(project_root),
        "control_database": (_sqlite_inventory(project_root)),
        "unresolved_required_stage_count": len(unresolved_required),
        "unresolved_required_stages": (unresolved_required),
        "ready": (len(unresolved_required) == 0),
        "policy": {
            "operating_mode": "shadow",
            "automatic_conclusions": False,
            "opportunity_ranked": False,
            "outreach_eligible": False,
            "acquisition_enabled_in_plan": False,
            "partial_success_allowed": False,
        },
    }

    if not report["ready"]:
        raise RuntimeError(f"Data plane is not ready. Unresolved stages: {unresolved_required}")

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "data_plane_readiness.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_write_json(
            contract_path,
            report,
        )

    return report


@contextmanager
def _exclusive_lock(
    project_root: Path,
) -> Iterator[Path]:
    lock_path = project_root / "data" / "control" / "data_plane.lock"

    lock_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with lock_path.open(
        "a+",
        encoding="utf-8",
    ) as stream:
        try:
            fcntl.flock(
                stream.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )

        except BlockingIOError as error:
            raise RuntimeError(
                "Another data-plane run already holds the exclusive lock."
            ) from error

        stream.seek(0)
        stream.truncate()
        stream.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "acquired_at": _timestamp(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())

        try:
            yield lock_path

        finally:
            fcntl.flock(
                stream.fileno(),
                fcntl.LOCK_UN,
            )


def _sha256_file(
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


def _database_fingerprint(
    project_root: Path,
) -> dict[str, Any]:
    paths = {
        "warehouse": (project_root / "data" / "warehouse" / "cre.duckdb"),
        "control": (project_root / "data" / "control" / "operations.sqlite3"),
    }

    fingerprint: dict[
        str,
        Any,
    ] = {}

    for name, path in paths.items():
        if not path.exists():
            fingerprint[name] = {
                "exists": False,
            }
            continue

        stat = path.stat()

        fingerprint[name] = {
            "exists": True,
            "size_bytes": stat.st_size,
            "modified_at": _datetime_text(
                datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=UTC,
                )
            ),
        }

    return fingerprint


def run_data_plane(
    project_root: Path,
    *,
    pipeline: str,
    include_acquisition: bool,
    dry_run: bool,
) -> dict[str, Any]:
    config = _load_config(project_root)

    _guard_existing_policy(project_root)

    plan = build_data_plane_plan(
        project_root,
        pipeline=pipeline,
        include_acquisition=include_acquisition,
    )

    run_id = _run_id()

    output_root = project_root / "logs" / "data_plane" / run_id

    output_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    manifest_path = output_root / "manifest.json"

    stage_results: list[dict[str, Any]] = []

    manifest: dict[str, Any] = {
        "run_version": ("cre-foundry-data-plane-run-v1"),
        "run_id": run_id,
        "started_at": _timestamp(),
        "finished_at": None,
        "pipeline": pipeline,
        "include_acquisition": (include_acquisition),
        "dry_run": dry_run,
        "status": "planned",
        "plan": plan,
        "before_fingerprint": (_database_fingerprint(project_root)),
        "after_fingerprint": None,
        "stage_results": stage_results,
        "policy": {
            "operating_mode": "shadow",
            "automatic_conclusions": False,
            "opportunity_ranked": False,
            "outreach_eligible": False,
            "partial_success_allowed": False,
        },
    }

    _atomic_write_json(
        manifest_path,
        manifest,
    )

    if dry_run:
        for stage in plan["stages"]:
            stage_results.append(
                {
                    "stage_id": stage["stage_id"],
                    "command": stage["command"],
                    "kind": stage["kind"],
                    "status": ("planned" if stage["enabled"] else "skipped"),
                    "skip_reason": stage["skip_reason"],
                }
            )

        manifest["finished_at"] = _timestamp()
        manifest["status"] = "dry_run_complete"
        manifest["after_fingerprint"] = _database_fingerprint(project_root)

        _atomic_write_json(
            manifest_path,
            manifest,
        )

        return {
            "run_id": run_id,
            "status": manifest["status"],
            "dry_run": True,
            "manifest_path": str(manifest_path.relative_to(project_root)),
            "enabled_stage_count": sum(1 for stage in plan["stages"] if stage["enabled"]),
            "skipped_stage_count": sum(1 for stage in plan["stages"] if not stage["enabled"]),
            "policy": manifest["policy"],
        }

    uv = shutil.which("uv")

    if uv is None:
        raise RuntimeError("uv is not available on PATH.")

    timeout_seconds = int(config["default_stage_timeout_seconds"])

    retry_base_seconds = float(config["retry_base_seconds"])

    manifest["status"] = "running"

    _atomic_write_json(
        manifest_path,
        manifest,
    )

    with _exclusive_lock(project_root):
        for stage in plan["stages"]:
            stage_id = str(stage["stage_id"])

            command = stage["command"]

            if not stage["enabled"]:
                stage_results.append(
                    {
                        "stage_id": stage_id,
                        "command": command,
                        "kind": stage["kind"],
                        "status": "skipped",
                        "skip_reason": stage["skip_reason"],
                    }
                )

                _atomic_write_json(
                    manifest_path,
                    manifest,
                )

                continue

            if command is None:
                raise RuntimeError(f"Enabled stage lacks command: {stage_id}")

            attempts_allowed = int(
                config[
                    "acquisition_retries" if stage["kind"] == "acquisition" else "transform_retries"
                ]
            )

            stage_log = output_root / f"{stage['position']:02d}_{stage_id}.log"

            stage_started = _timestamp()
            start_monotonic = time.monotonic()

            stage_result: dict[
                str,
                Any,
            ] = {
                "stage_id": stage_id,
                "command": command,
                "kind": stage["kind"],
                "status": "running",
                "started_at": (stage_started),
                "finished_at": None,
                "duration_seconds": None,
                "attempts": 0,
                "log_path": str(stage_log.relative_to(project_root)),
                "return_code": None,
            }

            stage_results.append(stage_result)

            _atomic_write_json(
                manifest_path,
                manifest,
            )

            final_return_code: int | None = None
            final_output = ""

            for attempt in range(
                1,
                attempts_allowed + 1,
            ):
                stage_result["attempts"] = attempt

                try:
                    completed = subprocess.run(
                        [
                            uv,
                            "run",
                            "cre-foundry",
                            "source",
                            command,
                        ],
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        check=False,
                    )

                    final_return_code = completed.returncode

                    final_output = (
                        f"===== ATTEMPT {attempt} STDOUT =====\n"
                        f"{completed.stdout}\n"
                        f"===== ATTEMPT {attempt} STDERR =====\n"
                        f"{completed.stderr}\n"
                    )

                except subprocess.TimeoutExpired as error:
                    final_return_code = 124

                    stdout = (
                        error.stdout
                        if isinstance(
                            error.stdout,
                            str,
                        )
                        else ""
                    )

                    stderr = (
                        error.stderr
                        if isinstance(
                            error.stderr,
                            str,
                        )
                        else ""
                    )

                    final_output = f"===== ATTEMPT {attempt} TIMEOUT =====\n{stdout}\n{stderr}\n"

                _atomic_write_text(
                    stage_log,
                    final_output,
                )

                if final_return_code == 0:
                    break

                if attempt < attempts_allowed:
                    time.sleep(retry_base_seconds * (2 ** (attempt - 1)))

            finished_at = _timestamp()

            duration_seconds = round(
                time.monotonic() - start_monotonic,
                3,
            )

            stage_result.update(
                {
                    "finished_at": (finished_at),
                    "duration_seconds": (duration_seconds),
                    "return_code": (final_return_code),
                    "status": ("passed" if final_return_code == 0 else "failed"),
                }
            )

            _atomic_write_json(
                manifest_path,
                manifest,
            )

            if final_return_code != 0:
                manifest["finished_at"] = _timestamp()
                manifest["status"] = "failed"
                manifest["failed_stage_id"] = stage_id
                manifest["after_fingerprint"] = _database_fingerprint(project_root)

                _atomic_write_json(
                    manifest_path,
                    manifest,
                )

                raise RuntimeError(f"Data-plane stage failed: {stage_id}. See {stage_log}.")

    readiness = build_data_plane_readiness(
        project_root,
        write_contract=False,
    )

    manifest["finished_at"] = _timestamp()
    manifest["status"] = "passed"
    manifest["after_fingerprint"] = _database_fingerprint(project_root)
    manifest["post_run_readiness"] = readiness

    _atomic_write_json(
        manifest_path,
        manifest,
    )

    manifest_sha256 = _sha256_file(manifest_path)

    return {
        "run_id": run_id,
        "status": "passed",
        "dry_run": False,
        "manifest_path": str(manifest_path.relative_to(project_root)),
        "manifest_sha256": (manifest_sha256),
        "passed_stage_count": sum(1 for result in stage_results if result["status"] == "passed"),
        "skipped_stage_count": sum(1 for result in stage_results if result["status"] == "skipped"),
        "readiness": {
            "ready": readiness["ready"],
            "warehouse_table_count": (
                readiness["warehouse"].get(
                    "table_count",
                    0,
                )
            ),
            "warehouse_view_count": (
                readiness["warehouse"].get(
                    "view_count",
                    0,
                )
            ),
        },
        "policy": manifest["policy"],
    }
