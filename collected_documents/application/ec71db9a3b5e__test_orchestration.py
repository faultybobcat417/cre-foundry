from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from cre_foundry.control import ControlDatabase
from cre_foundry.orchestration import (
    RunProfile,
    build_run_plan,
    load_run_profile,
)
from cre_foundry.source_contracts import (
    SourceConfig,
)


def config() -> SourceConfig:
    return SourceConfig(
        source_id="brampton_plantrak",
        name="Brampton Plantrak",
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


def database(
    tmp_path: Path,
) -> ControlDatabase:
    result = ControlDatabase(tmp_path / "operations.sqlite3")
    result.initialize()
    result.register_source(config())
    return result


def profile(
    *,
    due_only: bool = True,
) -> RunProfile:
    return RunProfile(
        profile_id="metadata_watch",
        run_type="metadata_watch",
        enabled=True,
        source_ids=["brampton_plantrak"],
        due_only=due_only,
        lock_ttl_minutes=15,
    )


def test_loads_metadata_watch_profile(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profile.yaml"
    path.write_text(
        """
profile_id: metadata_watch
run_type: metadata_watch
enabled: true
source_ids:
  - brampton_plantrak
due_only: true
lock_ttl_minutes: 15
""".strip()
    )

    loaded = load_run_profile(path)

    assert loaded.profile_id == "metadata_watch"
    assert loaded.source_ids == ["brampton_plantrak"]


def test_never_scheduled_source_executes(
    tmp_path: Path,
) -> None:
    plan = build_run_plan(
        profile=profile(),
        database=database(tmp_path),
        now=datetime(
            2026,
            7,
            26,
            tzinfo=UTC,
        ),
    )

    assert plan[0].action == "execute"
    assert plan[0].reason == "never_scheduled"


def test_future_source_is_skipped(
    tmp_path: Path,
) -> None:
    control = database(tmp_path)

    now = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    control.update_health(
        source_id="brampton_plantrak",
        success=True,
        changed=False,
        now=now,
    )

    plan = build_run_plan(
        profile=profile(),
        database=control,
        now=now,
    )

    assert plan[0].action == "skip"
    assert plan[0].reason == "not_due"


def test_force_overrides_future_due_time(
    tmp_path: Path,
) -> None:
    control = database(tmp_path)

    now = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    control.update_health(
        source_id="brampton_plantrak",
        success=True,
        changed=False,
        now=now,
    )

    plan = build_run_plan(
        profile=profile(),
        database=control,
        force=True,
        now=now,
    )

    assert plan[0].action == "execute"
    assert plan[0].reason == "forced"
