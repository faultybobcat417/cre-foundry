from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from cre_foundry.launchd_agent import (
    LABEL,
    build_launch_agent_payload,
    install_launch_agent,
)


def test_launch_agent_uses_hourly_calendar_event(
    tmp_path: Path,
) -> None:
    payload = build_launch_agent_payload(
        project_root=tmp_path / "project",
        home_directory=tmp_path / "home",
        minute=17,
    )

    assert payload["Label"] == LABEL
    assert payload["RunAtLoad"] is False
    assert payload["KeepAlive"] is False
    assert payload["StartCalendarInterval"] == {"Minute": 17}
    assert "StartInterval" not in payload


def test_install_writes_valid_absolute_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    home = tmp_path / "home"

    runner = root / "scripts" / "run_metadata_watch.sh"
    runner.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    runner.write_text("#!/bin/zsh\nexit 0\n")
    runner.chmod(0o755)

    destination = install_launch_agent(
        project_root=root,
        home_directory=home,
        minute=17,
    )

    with destination.open("rb") as handle:
        payload = plistlib.load(handle)

    assert destination.is_absolute()
    assert payload["ProgramArguments"] == [str(runner)]
    assert payload["WorkingDirectory"] == str(root)
    assert payload["StartCalendarInterval"] == {"Minute": 17}


@pytest.mark.parametrize(
    "minute",
    [-1, 60],
)
def test_rejects_invalid_calendar_minute(
    tmp_path: Path,
    minute: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 59",
    ):
        build_launch_agent_payload(
            project_root=tmp_path,
            home_directory=tmp_path,
            minute=minute,
        )
