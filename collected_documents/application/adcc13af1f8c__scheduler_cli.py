from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from cre_foundry.launchd_agent import (
    LABEL,
    install_launch_agent,
)

scheduler_app = typer.Typer(
    help="Stage and inspect local macOS scheduling.",
    no_args_is_help=True,
)

console = Console()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def service_target() -> str:
    return f"gui/{os.getuid()}/{LABEL}"


@scheduler_app.command("install")
def install(
    minute: int = typer.Option(
        17,
        min=0,
        max=59,
        help="Minute of each hour to poll.",
    ),
) -> None:
    """Install the launch-agent file without loading it."""
    destination = install_launch_agent(
        project_root=project_root(),
        home_directory=Path.home(),
        minute=minute,
    )

    console.print("[bold green]LAUNCH AGENT STAGED[/bold green]")
    console.print(str(destination))
    console.print(f"Configured for minute {minute:02d} of every hour.")
    console.print("The agent has not been loaded by this command.")


@scheduler_app.command("status")
def status() -> None:
    """Report whether the launch agent is loaded."""
    result = subprocess.run(
        [
            "/bin/launchctl",
            "print",
            service_target(),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        console.print("[bold green]LOADED[/bold green]")
        console.print("The hourly launch agent is registered.")
    else:
        console.print("[bold yellow]NOT LOADED[/bold yellow]")
        console.print("No background schedule is active.")
