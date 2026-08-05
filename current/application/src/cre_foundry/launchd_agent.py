from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

LABEL = "com.comfiance.cre-foundry.metadata-watch"


def build_launch_agent_payload(
    *,
    project_root: Path,
    home_directory: Path,
    minute: int,
) -> dict[str, Any]:
    """Build a wake-aware hourly macOS launch agent."""
    if not 0 <= minute <= 59:
        raise ValueError("Calendar minute must be between 0 and 59.")

    runner = project_root / "scripts" / "run_metadata_watch.sh"

    logs = project_root / "logs"

    return {
        "Label": LABEL,
        "ProgramArguments": [str(runner)],
        "WorkingDirectory": str(project_root),
        "StartCalendarInterval": {
            "Minute": minute,
        },
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "ThrottleInterval": 60,
        "StandardOutPath": str(logs / "launchd_metadata_watch.stdout.log"),
        "StandardErrorPath": str(logs / "launchd_metadata_watch.stderr.log"),
        "EnvironmentVariables": {
            "HOME": str(home_directory),
            "DO_NOT_TRACK": "1",
            "PREFECT_SERVER_ANALYTICS_ENABLED": ("false"),
        },
    }


def install_launch_agent(
    *,
    project_root: Path,
    home_directory: Path,
    minute: int,
) -> Path:
    """Write the launch-agent plist without loading it."""
    runner = project_root / "scripts" / "run_metadata_watch.sh"

    if not runner.exists():
        raise FileNotFoundError(f"Runner does not exist: {runner}")

    if not runner.stat().st_mode & 0o111:
        raise PermissionError(f"Runner is not executable: {runner}")

    destination = home_directory / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = build_launch_agent_payload(
        project_root=project_root,
        home_directory=home_directory,
        minute=minute,
    )

    with destination.open("wb") as handle:
        plistlib.dump(
            payload,
            handle,
            sort_keys=True,
        )

    destination.chmod(0o644)

    return destination
