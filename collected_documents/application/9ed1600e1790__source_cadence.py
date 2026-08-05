from __future__ import annotations

import json
import os
import sqlite3
import statistics
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "manifest_declared_timestamps_only": True,
    "filesystem_mtime_as_cadence_evidence": False,
    "minimum_observations_for_interval": 2,
    "minimum_observations_for_baseline": 4,
    "automatic_schedule_activation": False,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

TIMESTAMP_KEYS = {
    "acquired_at",
    "completed_at",
    "created_at",
    "fetched_at",
    "generated_at",
    "observed_at",
    "retrieved_at",
    "run_started_at",
    "started_at",
}


def _parse_iso8601(
    value: str,
) -> datetime:
    normalized = value.strip()

    if not normalized:
        raise ValueError("ISO-8601 timestamp cannot be blank.")

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


def _require_nonnegative_int(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{field_name} must be a nonnegative integer.")

    return value


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "source_cadence.json")

    raw_policy = config.get("policy")

    raw_scan = config.get("scan")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Source-cadence policy must be an object.")

    if not isinstance(
        raw_scan,
        dict,
    ):
        raise RuntimeError("Source-cadence scan configuration must be an object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Source-cadence policy mismatch.")

    _require_nonnegative_int(
        raw_scan.get("maximum_candidate_files"),
        "scan.maximum_candidate_files",
    )

    return config


def _configured_sources(
    project_root: Path,
) -> list[str]:
    database_path = project_root / "data" / "control" / "operations.sqlite3"

    connection = sqlite3.connect(
        ("file:" + str(database_path) + "?mode=ro"),
        uri=True,
    )

    try:
        columns = {
            str(row[1])
            for row in connection.execute(
                """
                PRAGMA table_info(
                    source_operation_policies
                )
                """
            ).fetchall()
        }

        if "source_id" not in columns:
            raise RuntimeError("source_operation_policies has no source_id column.")

        rows = connection.execute(
            """
            SELECT DISTINCT source_id
            FROM source_operation_policies
            ORDER BY source_id
            """
        ).fetchall()

    finally:
        connection.close()

    sources = [str(row[0]) for row in rows if row[0] is not None]

    if not sources:
        raise RuntimeError("No governed source policies were found.")

    return sources


def _walk_values(
    value: object,
) -> tuple[
    set[str],
    list[
        tuple[
            str,
            datetime,
            str,
        ]
    ],
]:
    source_ids: set[str] = set()

    timestamps: list[
        tuple[
            str,
            datetime,
            str,
        ]
    ] = []

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
                        parsed = _parse_iso8601(nested)

                    except (
                        TypeError,
                        ValueError,
                    ):
                        parsed = None

                    if parsed is not None:
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=UTC)

                        parsed = parsed.astimezone(UTC)

                        timestamps.append(
                            (
                                key,
                                parsed,
                                nested_breadcrumb,
                            )
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

    return (
        source_ids,
        timestamps,
    )


def _candidate_files(
    project_root: Path,
    roots: list[str],
    tokens: list[str],
    maximum_files: int,
    explicit_paths: set[Path],
) -> tuple[
    list[Path],
    int,
]:
    discovered: set[Path] = set(explicit_paths)

    for relative_root in roots:
        scan_root = project_root / relative_root

        if not scan_root.exists():
            continue

        for path in scan_root.rglob("*.json"):
            lowered_name = path.name.lower()

            if any(token in lowered_name for token in tokens):
                discovered.add(path.resolve())

    ordered = sorted(discovered)

    overflow = max(
        0,
        len(ordered) - maximum_files,
    )

    return (
        ordered[:maximum_files],
        overflow,
    )


def build_source_cadence(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    raw_scan = config["scan"]

    if not isinstance(
        raw_scan,
        dict,
    ):
        raise RuntimeError("Source-cadence scan configuration is malformed.")

    raw_roots = raw_scan.get("roots")

    raw_tokens = raw_scan.get("candidate_filename_tokens")

    if not isinstance(
        raw_roots,
        list,
    ):
        raise RuntimeError("Cadence scan roots must be a list.")

    if not isinstance(
        raw_tokens,
        list,
    ):
        raise RuntimeError("Cadence filename tokens must be a list.")

    roots = []

    for value in raw_roots:
        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError("Cadence roots must be strings.")

        roots.append(value)

    tokens = []

    for value in raw_tokens:
        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError("Cadence filename tokens must be strings.")

        tokens.append(value.lower())

    maximum_files = _require_nonnegative_int(
        raw_scan.get("maximum_candidate_files"),
        "scan.maximum_candidate_files",
    )

    source_ids = _configured_sources(project_root)

    admission = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_admission.json"
    )

    raw_packets = admission.get("packets")

    if not isinstance(
        raw_packets,
        list,
    ):
        raise RuntimeError("Snapshot-admission packets must be a list.")

    explicit_paths: set[Path] = set()

    for raw_packet in raw_packets:
        if not isinstance(
            raw_packet,
            dict,
        ):
            raise RuntimeError("Admission packet must be an object.")

        manifest_path = raw_packet.get("manifest_path")

        if (
            isinstance(
                manifest_path,
                str,
            )
            and manifest_path
        ):
            explicit_paths.add((project_root / manifest_path).resolve())

    candidate_files, overflow_count = _candidate_files(
        project_root,
        roots,
        tokens,
        maximum_files,
        explicit_paths,
    )

    observations_by_source: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    scan_records = []

    parse_error_count = 0
    no_source_id_count = 0
    no_timestamp_count = 0

    governed_source_set = set(source_ids)

    for path in candidate_files:
        relative_path = (
            str(path.relative_to(project_root.resolve()))
            if path.is_relative_to(project_root.resolve())
            else str(path)
        )

        try:
            payload: object = json.loads(path.read_text(encoding="utf-8"))

        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            parse_error_count += 1

            scan_records.append(
                {
                    "path": relative_path,
                    "parse_succeeded": False,
                    "error_type": type(error).__name__,
                    "source_ids": [],
                    "timestamp_count": 0,
                }
            )

            continue

        source_values, timestamps = _walk_values(payload)

        governed_sources = sorted(source_values & governed_source_set)

        if not governed_sources:
            no_source_id_count += 1

        if not timestamps:
            no_timestamp_count += 1

        scan_records.append(
            {
                "path": relative_path,
                "parse_succeeded": True,
                "source_ids": (governed_sources),
                "timestamp_count": len(timestamps),
            }
        )

        for source_id in governed_sources:
            for (
                timestamp_key,
                observed_at,
                breadcrumb,
            ) in timestamps:
                observations_by_source[source_id].append(
                    {
                        "source_id": source_id,
                        "observed_at": (observed_at.isoformat()),
                        "timestamp_key": (timestamp_key),
                        "breadcrumb": breadcrumb,
                        "manifest_path": (relative_path),
                        "evidence_strength": ("manifest_declared"),
                    }
                )

    source_reports = []
    cadence_candidates = []

    for source_id in source_ids:
        raw_observations = observations_by_source.get(
            source_id,
            [],
        )

        unique_by_time: dict[
            str,
            dict[str, Any],
        ] = {}

        for observation in raw_observations:
            timestamp = str(observation["observed_at"])

            unique_by_time.setdefault(
                timestamp,
                observation,
            )

        observations = sorted(
            unique_by_time.values(),
            key=lambda observation: str(observation["observed_at"]),
        )

        parsed_times = [
            _parse_iso8601(str(observation["observed_at"])) for observation in observations
        ]

        intervals = [
            (later - earlier).total_seconds() / 3600.0
            for earlier, later in pairwise(parsed_times)
            if later > earlier
        ]

        observation_count = len(observations)

        interval_count = len(intervals)

        if observation_count < 2:
            status = "insufficient_history"

        elif observation_count < 4:
            status = "provisional_history"

        else:
            status = "observed_baseline"

        median_interval = (
            round(
                statistics.median(intervals),
                6,
            )
            if intervals
            else None
        )

        minimum_interval = (
            round(
                min(intervals),
                6,
            )
            if intervals
            else None
        )

        maximum_interval = (
            round(
                max(intervals),
                6,
            )
            if intervals
            else None
        )

        source_report = {
            "source_id": source_id,
            "observation_count": (observation_count),
            "interval_count": (interval_count),
            "first_observed_at": (observations[0]["observed_at"] if observations else None),
            "latest_observed_at": (observations[-1]["observed_at"] if observations else None),
            "minimum_interval_hours": (minimum_interval),
            "median_interval_hours": (median_interval),
            "maximum_interval_hours": (maximum_interval),
            "cadence_status": status,
            "observations": observations,
            "filesystem_mtime_used": False,
            "schedule_activation_permitted": False,
            "automatic_acquisition_permitted": False,
        }

        source_reports.append(source_report)

        cadence_candidates.append(
            {
                "source_id": source_id,
                "cadence_status": status,
                "observation_count": (observation_count),
                "observed_median_interval_hours": (median_interval),
                "proposed_schedule_interval_hours": None,
                "freshness_target_hours": None,
                "maximum_staleness_hours": None,
                "manual_approval_required": True,
                "schedule_activation_permitted": False,
                "schedule_activation_executed": False,
                "automatic_acquisition_permitted": False,
            }
        )

    observations_contract: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-source-cadence-observations-v1"),
        "configured_source_count": len(source_ids),
        "candidate_file_count": len(candidate_files),
        "candidate_file_overflow_count": (overflow_count),
        "parse_error_count": (parse_error_count),
        "files_without_governed_source_id_count": (no_source_id_count),
        "files_without_declared_timestamp_count": (no_timestamp_count),
        "source_reports": source_reports,
        "scan_records": scan_records,
        "manifest_declared_timestamps_only": True,
        "filesystem_mtime_used": False,
        "schedule_activation_execution_count": 0,
        "automatic_acquisition_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "policy": EXPECTED_POLICY,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    candidate_contract: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-source-cadence-candidates-v1"),
        "source_count": len(cadence_candidates),
        "insufficient_history_count": sum(
            candidate["cadence_status"] == "insufficient_history"
            for candidate in cadence_candidates
        ),
        "provisional_history_count": sum(
            candidate["cadence_status"] == "provisional_history" for candidate in cadence_candidates
        ),
        "observed_baseline_count": sum(
            candidate["cadence_status"] == "observed_baseline" for candidate in cadence_candidates
        ),
        "candidates": cadence_candidates,
        "approved_schedule_count": 0,
        "enabled_schedule_count": 0,
        "schedule_activation_execution_count": 0,
        "automatic_acquisition_execution_count": 0,
        "manual_approval_required": True,
        "policy": EXPECTED_POLICY,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    markdown_lines = [
        "# Empirical Source Cadence",
        "",
        (
            "Cadence evidence is derived only from "
            "timestamps declared inside governed JSON manifests."
        ),
        "",
        (f"- Governed sources: `{len(source_ids)}`"),
        (f"- Candidate files scanned: `{len(candidate_files)}`"),
        (f"- Parse errors: `{parse_error_count}`"),
        ("- Filesystem modification times used: `false`"),
        ("- Enabled schedules: `0`"),
        "",
    ]

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        observations_path = contract_root / "source_cadence_observations.json"

        candidates_path = contract_root / "source_cadence_candidates.json"

        markdown_path = contract_root / "source_cadence.md"

        paths = {
            "observations": str(observations_path.relative_to(project_root)),
            "candidates": str(candidates_path.relative_to(project_root)),
            "markdown": str(markdown_path.relative_to(project_root)),
        }

        observations_contract["contract_paths"] = paths

        candidate_contract["contract_paths"] = paths

        _atomic_json(
            observations_path,
            observations_contract,
        )

        _atomic_json(
            candidates_path,
            candidate_contract,
        )

        _atomic_text(
            markdown_path,
            "\n".join(markdown_lines),
        )

    return {
        "observations": (observations_contract),
        "candidates": (candidate_contract),
    }
