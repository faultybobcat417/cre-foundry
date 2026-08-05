from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cre_foundry.control import (
    ControlDatabase,
    SourceLockedError,
)
from cre_foundry.source_contracts import (
    SourceConfig,
)


def source_config() -> SourceConfig:
    return SourceConfig(
        source_id="test_source",
        name="Test Source",
        base_url="https://example.test",
        access_state="review",
        enabled=True,
        request_timeout_seconds=10,
        batch_size=100,
        output_spatial_reference=4326,
        layers=[1],
        base_cadence_minutes=360,
        minimum_cadence_minutes=60,
        maximum_cadence_minutes=1440,
    )


def initialized_database(
    tmp_path: Path,
) -> ControlDatabase:
    database = ControlDatabase(tmp_path / "operations.sqlite3")
    database.initialize()
    database.register_source(source_config())
    return database


def test_source_lock_prevents_overlap(
    tmp_path: Path,
) -> None:
    database = initialized_database(tmp_path)

    with (
        database.source_lock("test_source"),
        pytest.raises(SourceLockedError),
        database.source_lock("test_source"),
    ):
        pass


def test_schema_versions_detect_real_change(
    tmp_path: Path,
) -> None:
    database = initialized_database(tmp_path)

    observed_at = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    baseline = database.record_schema(
        source_id="test_source",
        layer_key="1",
        fingerprint="schema-a",
        metadata={"fields": ["a"]},
        observed_at=observed_at,
    )

    unchanged = database.record_schema(
        source_id="test_source",
        layer_key="1",
        fingerprint="schema-a",
        metadata={"fields": ["a"]},
        observed_at=observed_at,
    )

    changed = database.record_schema(
        source_id="test_source",
        layer_key="1",
        fingerprint="schema-b",
        metadata={"fields": ["a", "b"]},
        observed_at=observed_at,
    )

    assert baseline == "baseline"
    assert unchanged == "unchanged"
    assert changed == "changed"


def test_run_lifecycle_is_persistent(
    tmp_path: Path,
) -> None:
    database = initialized_database(tmp_path)

    run_id = database.start_run(
        source_id="test_source",
        run_type="metadata_watch",
        as_of_timestamp=datetime(
            2026,
            7,
            26,
            tzinfo=UTC,
        ),
    )

    database.complete_run(
        run_id=run_id,
        records_observed=3,
        schema_changed=False,
        metadata={"result": "ok"},
    )

    runs = database.recent_runs()

    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "succeeded"
    assert runs[0]["records_observed"] == 3
