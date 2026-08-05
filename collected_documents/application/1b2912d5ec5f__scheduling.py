from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal


@dataclass(frozen=True)
class CadenceDecision:
    """Result of one adaptive cadence decision."""

    cadence_minutes: int
    consecutive_no_change: int
    consecutive_failures: int
    health_status: Literal[
        "healthy",
        "degraded",
        "unhealthy",
    ]
    next_due_at: datetime


def calculate_cadence(
    *,
    now: datetime,
    success: bool,
    changed: bool,
    base_minutes: int,
    minimum_minutes: int,
    maximum_minutes: int,
    current_minutes: int,
    no_change_streak: int,
    failure_streak: int,
) -> CadenceDecision:
    """Calculate a bounded, explainable next-run cadence."""
    if minimum_minutes > base_minutes:
        raise ValueError("minimum_minutes cannot exceed base_minutes.")

    if base_minutes > maximum_minutes:
        raise ValueError("base_minutes cannot exceed maximum_minutes.")

    if success:
        new_failure_streak = 0

        if changed:
            new_no_change_streak = 0
            cadence = base_minutes
        else:
            new_no_change_streak = no_change_streak + 1
            cadence = current_minutes

            # Slow the source after each third
            # consecutive no-change observation.
            if new_no_change_streak % 3 == 0:
                cadence = math.ceil(current_minutes * 1.5)

        cadence = min(
            maximum_minutes,
            max(minimum_minutes, cadence),
        )

        health_status: Literal[
            "healthy",
            "degraded",
            "unhealthy",
        ] = "healthy"

    else:
        new_no_change_streak = no_change_streak
        new_failure_streak = failure_streak + 1

        cadence = min(
            maximum_minutes,
            max(
                base_minutes,
                current_minutes * 2,
            ),
        )

        health_status = "unhealthy" if new_failure_streak >= 3 else "degraded"

    return CadenceDecision(
        cadence_minutes=cadence,
        consecutive_no_change=(new_no_change_streak),
        consecutive_failures=(new_failure_streak),
        health_status=health_status,
        next_due_at=now + timedelta(minutes=cadence),
    )
