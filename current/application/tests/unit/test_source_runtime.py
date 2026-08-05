from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cre_foundry.source_runtime import (
    audit_source_runtime,
    discover_snapshot_bootstrap_candidates,
    initialize_source_runtime,
    plan_source_acquisitions,
)


def _project(
    tmp_path: Path,
) -> Path:
    config_root = tmp_path / "config"

    source_root = tmp_path / "src" / "cre_foundry"

    database_root = tmp_path / "data" / "control"

    config_root.mkdir(parents=True)

    source_root.mkdir(parents=True)

    database_root.mkdir(parents=True)

    (config_root / "source_runtime.json").write_text(
        json.dumps(
            {
                "config_version": "test",
                "policies": {
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
                },
                "sources": {
                    "test_source": {
                        "command": ("acquire-test-source"),
                        "schedule_enabled": False,
                        "interval_seconds": None,
                        "jitter_seconds": 0,
                        "browser_recipe_id": None,
                        "execution_mode": "manual_only",
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (source_root / "cli.py").write_text(
        """
@source_app.command(
    "acquire-test-source"
)
def acquire_test_source() -> None:
    pass
""",
        encoding="utf-8",
    )

    connection = sqlite3.connect(database_root / "operations.sqlite3")

    try:
        connection.executescript(
            """
            CREATE TABLE
                source_operation_policies (
                    source_id TEXT PRIMARY KEY,
                    authorization_status TEXT NOT NULL,
                    schedule_enabled INTEGER NOT NULL,
                    freshness_target_hours REAL,
                    maximum_staleness_hours REAL
                );

            INSERT INTO
                source_operation_policies (
                    source_id,
                    authorization_status,
                    schedule_enabled,
                    freshness_target_hours,
                    maximum_staleness_hours
                )
            VALUES (
                'test_source',
                'approved',
                0,
                NULL,
                NULL
            );

            CREATE TABLE
                source_runs (
                    run_id TEXT PRIMARY KEY,
                    source_id TEXT,
                    artifact_path TEXT
                );
            """
        )

        connection.commit()

    finally:
        connection.close()

    return tmp_path


def test_initializes_source_runtime(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = initialize_source_runtime(project)

    assert report["runtime_state_count"] == 1

    assert report["append_only_trigger_count"] == 4

    audit = audit_source_runtime(
        project,
        write_contract=False,
    )

    assert audit["ready"] is True

    assert audit["enabled_schedule_sources"] == []


def test_plan_keeps_execution_disabled(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_source_runtime(project)

    report = plan_source_acquisitions(
        project,
        now=datetime(
            2026,
            7,
            26,
            12,
            0,
            tzinfo=UTC,
        ),
        write_contract=False,
    )

    assert report["automatic_execution_count"] == 0

    assert report["browser_execution_count"] == 0

    assert report["computer_vision_execution_count"] == 0

    assert report["plans"][0]["status"] == "disabled"

    assert report["plans"][0]["reason"] == "runtime_schedule_disabled"


def test_bootstrap_discovers_only_explicit_paths(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_source_runtime(project)

    artifact = project / "data" / "raw" / "test.json"

    artifact.parent.mkdir(parents=True)

    artifact.write_text(
        '{"test": true}\n',
        encoding="utf-8",
    )

    connection = sqlite3.connect(project / "data" / "control" / "operations.sqlite3")

    try:
        connection.execute(
            """
            INSERT INTO
                source_runs (
                    run_id,
                    source_id,
                    artifact_path
                )
            VALUES (
                'run-1',
                'test_source',
                'data/raw/test.json'
            )
            """
        )

        connection.commit()

    finally:
        connection.close()

    report = discover_snapshot_bootstrap_candidates(
        project,
        write_contract=False,
    )

    assert report["exact_candidate_count"] == 1

    assert report["automatic_registration_performed"] is False

    candidate = report["exact_candidates"][0]

    assert candidate["source_id"] == "test_source"

    assert candidate["provenance"] == "source_runs_explicit_path"
