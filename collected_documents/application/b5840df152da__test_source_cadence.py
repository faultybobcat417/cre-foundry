from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cre_foundry.source_cadence import (
    build_source_cadence,
)


def _write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _project(
    tmp_path: Path,
) -> Path:
    _write_json(
        tmp_path / "config" / "source_cadence.json",
        {
            "policy": {
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
            },
            "scan": {
                "roots": ["data/bronze"],
                "candidate_filename_tokens": ["manifest"],
                "maximum_candidate_files": 100,
            },
        },
    )

    database_path = tmp_path / "data" / "control" / "operations.sqlite3"

    database_path.parent.mkdir(parents=True)

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE source_operation_policies (
                source_id TEXT PRIMARY KEY
            )
            """
        )

        connection.execute(
            """
            INSERT INTO source_operation_policies
            VALUES ('source-1')
            """
        )

        connection.execute(
            """
            INSERT INTO source_operation_policies
            VALUES ('source-2')
            """
        )

        connection.commit()

    finally:
        connection.close()

    manifest_root = tmp_path / "data" / "bronze" / "source-1"

    for index, timestamp in enumerate(
        (
            "2026-07-01T00:00:00Z",
            "2026-07-02T00:00:00Z",
            "2026-07-03T00:00:00Z",
            "2026-07-04T00:00:00Z",
        ),
        start=1,
    ):
        _write_json(
            manifest_root / f"manifest-{index}.json",
            {
                "source_id": "source-1",
                "acquired_at": timestamp,
            },
        )

    explicit_manifest = manifest_root / "manifest-1.json"

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {"packets": [{"manifest_path": str(explicit_manifest.relative_to(tmp_path))}]},
    )

    return tmp_path


def test_builds_observed_baseline_from_manifests(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_source_cadence(
        project,
        write_contracts=False,
    )

    sources = {item["source_id"]: item for item in report["observations"]["source_reports"]}

    source_one = sources["source-1"]

    assert source_one["observation_count"] == 4

    assert source_one["interval_count"] == 3

    assert source_one["median_interval_hours"] == 24.0

    assert source_one["cadence_status"] == "observed_baseline"

    assert source_one["schedule_activation_permitted"] is False


def test_marks_missing_history_as_insufficient(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_source_cadence(
        project,
        write_contracts=False,
    )

    sources = {item["source_id"]: item for item in report["observations"]["source_reports"]}

    source_two = sources["source-2"]

    assert source_two["observation_count"] == 0

    assert source_two["cadence_status"] == "insufficient_history"

    assert source_two["median_interval_hours"] is None


def test_never_activates_schedules(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_source_cadence(
        project,
        write_contracts=False,
    )

    candidates = report["candidates"]

    assert candidates["approved_schedule_count"] == 0

    assert candidates["enabled_schedule_count"] == 0

    assert candidates["schedule_activation_execution_count"] == 0

    assert candidates["automatic_acquisition_execution_count"] == 0

    for candidate in candidates["candidates"]:
        assert candidate["proposed_schedule_interval_hours"] is None

        assert candidate["schedule_activation_permitted"] is False


def test_accepts_z_and_offset_timestamps(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    extra_manifest = project / "data" / "bronze" / "source-1" / "manifest-offset.json"

    _write_json(
        extra_manifest,
        {
            "source_id": "source-1",
            "acquired_at": ("2026-07-05T01:00:00+01:00"),
        },
    )

    report = build_source_cadence(
        project,
        write_contracts=False,
    )

    sources = {item["source_id"]: item for item in report["observations"]["source_reports"]}

    source_one = sources["source-1"]

    assert source_one["latest_observed_at"] == "2026-07-05T00:00:00+00:00"
