from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from prefect import flow, task
from pydantic import BaseModel, ConfigDict, Field

from cre_foundry.connectors.plantrak import (
    load_source_config,
)
from cre_foundry.control import (
    ControlDatabase,
    parse_timestamp,
)
from cre_foundry.metadata_watch import (
    execute_plantrak_metadata_watch,
)


class RunProfile(BaseModel):
    """Configuration for one repeatable workflow."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    run_type: Literal["metadata_watch"]
    enabled: bool
    source_ids: list[str] = Field(min_length=1)
    due_only: bool = True
    lock_ttl_minutes: int = Field(
        default=15,
        ge=1,
        le=240,
    )


class PlannedSource(BaseModel):
    """One source decision within a run plan."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    action: Literal["execute", "skip"]
    reason: str
    next_due_at: str | None = None


def load_run_profile(
    path: Path,
) -> RunProfile:
    payload = yaml.safe_load(path.read_text())

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid run profile: {path}")

    return RunProfile.model_validate(payload)


def build_run_plan(
    *,
    profile: RunProfile,
    database: ControlDatabase,
    force: bool = False,
    now: datetime | None = None,
) -> list[PlannedSource]:
    """Select due sources without executing them."""
    observed_at = now or datetime.now(UTC)

    statuses = {str(row["source_id"]): row for row in database.source_status()}

    plan: list[PlannedSource] = []

    for source_id in profile.source_ids:
        status = statuses.get(source_id)

        if status is None:
            plan.append(
                PlannedSource(
                    source_id=source_id,
                    action="skip",
                    reason="source_not_registered",
                )
            )
            continue

        next_due_value = status["next_due_at"]

        if force:
            plan.append(
                PlannedSource(
                    source_id=source_id,
                    action="execute",
                    reason="forced",
                    next_due_at=next_due_value,
                )
            )
            continue

        if not profile.due_only:
            plan.append(
                PlannedSource(
                    source_id=source_id,
                    action="execute",
                    reason="profile_not_due_only",
                    next_due_at=next_due_value,
                )
            )
            continue

        if next_due_value is None:
            plan.append(
                PlannedSource(
                    source_id=source_id,
                    action="execute",
                    reason="never_scheduled",
                )
            )
            continue

        next_due = parse_timestamp(str(next_due_value))

        if next_due <= observed_at:
            plan.append(
                PlannedSource(
                    source_id=source_id,
                    action="execute",
                    reason="due",
                    next_due_at=str(next_due_value),
                )
            )
        else:
            plan.append(
                PlannedSource(
                    source_id=source_id,
                    action="skip",
                    reason="not_due",
                    next_due_at=str(next_due_value),
                )
            )

    return plan


@task(
    retries=2,
    retry_delay_seconds=10,
)
def execute_metadata_watch_task(
    *,
    project_root: str,
    source_id: str,
    lock_ttl_minutes: int,
) -> dict[str, Any]:
    """Execute one supported metadata source."""
    if source_id != "brampton_plantrak":
        raise ValueError(f"Unsupported metadata source: {source_id}")

    return execute_plantrak_metadata_watch(
        project_root=Path(project_root),
        lock_ttl_minutes=lock_ttl_minutes,
    )


@flow(
    name="cre-foundry-profile-run",
    log_prints=True,
)
def run_profile_flow(
    *,
    project_root: str,
    profile_path: str,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute one parameterized foundry profile."""
    root = Path(project_root)
    profile = load_run_profile(Path(profile_path))

    if not profile.enabled:
        raise RuntimeError(f"Run profile {profile.profile_id} is disabled.")

    database = ControlDatabase(root / "data" / "control" / "operations.sqlite3")

    database.initialize()

    plantrak_config = load_source_config(root / "config" / "sources" / "brampton_plantrak.yaml")
    database.register_source(plantrak_config)

    plan = build_run_plan(
        profile=profile,
        database=database,
        force=force,
    )

    result: dict[str, Any] = {
        "profile_id": profile.profile_id,
        "run_type": profile.run_type,
        "force": force,
        "dry_run": dry_run,
        "plan": [item.model_dump() for item in plan],
        "executions": [],
    }

    if dry_run:
        return result

    executions: list[dict[str, Any]] = []

    for item in plan:
        if item.action != "execute":
            continue

        execution = execute_metadata_watch_task(
            project_root=str(root),
            source_id=item.source_id,
            lock_ttl_minutes=(profile.lock_ttl_minutes),
        )

        executions.append(execution)

    result["executions"] = executions
    return result
