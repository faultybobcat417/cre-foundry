from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cre_foundry.connectors.plantrak import (
    load_source_config,
)
from cre_foundry.control import ControlDatabase
from cre_foundry.metadata_watch import (
    execute_plantrak_metadata_watch,
)

control_app = typer.Typer(
    help="Persistent source-run control plane.",
    no_args_is_help=True,
)

console = Console()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def control_database() -> ControlDatabase:
    return ControlDatabase(project_root() / "data" / "control" / "operations.sqlite3")


def plantrak_config_path() -> Path:
    return project_root() / "config" / "sources" / "brampton_plantrak.yaml"


@control_app.command("init")
def initialize_control_plane() -> None:
    """Initialize operational tables and sources."""
    database = control_database()
    database.initialize()

    config = load_source_config(plantrak_config_path())
    database.register_source(config)

    console.print("[bold green]CONTROL PLANE INITIALIZED[/bold green]")


@control_app.command("inspect-plantrak")
def inspect_plantrak() -> None:
    """Inspect and record the Plantrak schema."""
    summary = execute_plantrak_metadata_watch(
        project_root=project_root(),
    )

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )


@control_app.command("status")
def status() -> None:
    """Display source health and recent runs."""
    database = control_database()
    database.initialize()

    source_table = Table(title="Source Health")
    source_table.add_column("Source")
    source_table.add_column("Access")
    source_table.add_column("Health")
    source_table.add_column("Failures")
    source_table.add_column("No Change")
    source_table.add_column("Cadence")
    source_table.add_column("Next Due")

    for row in database.source_status():
        source_table.add_row(
            str(row["source_id"]),
            str(row["access_state"]),
            str(row["health_status"]),
            str(row["consecutive_failures"]),
            str(row["consecutive_no_change"]),
            f"{row['current_cadence_minutes']}m",
            str(row["next_due_at"] or "not set"),
        )

    console.print(source_table)

    run_table = Table(title="Recent Source Runs")
    run_table.add_column("Run")
    run_table.add_column("Source")
    run_table.add_column("Type")
    run_table.add_column("Status")
    run_table.add_column("Records")
    run_table.add_column("Schema Change")
    run_table.add_column("Started")

    for row in database.recent_runs():
        records = row["records_observed"] if row["records_observed"] is not None else "-"

        schema_change = bool(row["schema_changed"]) if row["schema_changed"] is not None else "-"

        run_table.add_row(
            str(row["run_id"]),
            str(row["source_id"]),
            str(row["run_type"]),
            str(row["status"]),
            str(records),
            str(schema_change),
            str(row["started_at"]),
        )

    console.print(run_table)
