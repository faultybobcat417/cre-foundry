from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from cre_foundry.orchestration import (
    run_profile_flow,
)

orchestration_app = typer.Typer(
    help="Run parameterized foundry workflows.",
    no_args_is_help=True,
)

console = Console()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@orchestration_app.command("profile")
def run_profile(
    profile: str = typer.Option(
        "metadata_watch",
        help="Run-profile name without .yaml.",
    ),
    force: bool = typer.Option(
        False,
        help="Execute even when sources are not due.",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Build the plan without executing it.",
    ),
) -> None:
    """Plan or execute a configured workflow."""
    root = project_root()

    profile_path = root / "config" / "run_profiles" / f"{profile}.yaml"

    if not profile_path.exists():
        raise typer.BadParameter(f"Run profile does not exist: {profile_path}")

    result = run_profile_flow(
        project_root=str(root),
        profile_path=str(profile_path),
        force=force,
        dry_run=dry_run,
    )

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )
