from __future__ import annotations

from datetime import UTC, datetime

from cre_foundry.scheduling import (
    calculate_cadence,
)


def test_no_change_streak_slows_every_third_run() -> None:
    now = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    decision = calculate_cadence(
        now=now,
        success=True,
        changed=False,
        base_minutes=360,
        minimum_minutes=60,
        maximum_minutes=1440,
        current_minutes=360,
        no_change_streak=2,
        failure_streak=0,
    )

    assert decision.cadence_minutes == 540
    assert decision.consecutive_no_change == 3
    assert decision.health_status == "healthy"


def test_change_resets_source_to_base_cadence() -> None:
    now = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    decision = calculate_cadence(
        now=now,
        success=True,
        changed=True,
        base_minutes=360,
        minimum_minutes=60,
        maximum_minutes=1440,
        current_minutes=810,
        no_change_streak=8,
        failure_streak=0,
    )

    assert decision.cadence_minutes == 360
    assert decision.consecutive_no_change == 0


def test_third_failure_marks_source_unhealthy() -> None:
    now = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    decision = calculate_cadence(
        now=now,
        success=False,
        changed=False,
        base_minutes=360,
        minimum_minutes=60,
        maximum_minutes=1440,
        current_minutes=720,
        no_change_streak=0,
        failure_streak=2,
    )

    assert decision.cadence_minutes == 1440
    assert decision.consecutive_failures == 3
    assert decision.health_status == "unhealthy"
