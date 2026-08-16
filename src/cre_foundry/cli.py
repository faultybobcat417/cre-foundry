from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cre_foundry import __version__
from cre_foundry.adapters import fetch_brampton_permits
from cre_foundry.io import load_businesses, load_events
from cre_foundry.pipeline import run_pipeline

app = typer.Typer(help="Evidence-first commercial real estate signal pipeline.", no_args_is_help=True)
console = Console()


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print_ranked(rows) -> None:
    table = Table(title="CRE Foundry — Daily Research Queue")
    table.add_column("#", justify="right")
    table.add_column("Account")
    table.add_column("Priority", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Top evidence")
    for idx, row in enumerate(rows, 1):
        table.add_row(
            str(idx),
            row.business.name,
            f"{row.priority_score:.1f}",
            f"{row.confidence:.2f}",
            row.signals[0].evidence_summary if row.signals else "—",
        )
    console.print(table)


@app.command()
def demo() -> None:
    """Run the complete deterministic offline demo."""
    project = root()
    rows, summary = run_pipeline(
        businesses_path=project / "fixtures" / "businesses.csv",
        events_path=project / "fixtures" / "events.csv",
        output_dir=project / "outputs" / "demo",
        as_of=date(2026, 8, 15),
    )
    _print_ranked(rows)
    console.print(f"\n[green]Demo complete.[/green] {summary}")
    console.print("Outputs: outputs/demo/")


@app.command("score")
def score(input_set: str = typer.Argument("fixtures")) -> None:
    """Run the scorer against the bundled fixture set."""
    if input_set != "fixtures":
        raise typer.BadParameter("Only the bundled 'fixtures' set is supported in this showcase build.")
    demo()


@app.command("validate")
def validate(input_set: str = typer.Argument("fixtures")) -> None:
    """Validate the bundled source contracts."""
    if input_set != "fixtures":
        raise typer.BadParameter("Only the bundled 'fixtures' set is supported in this showcase build.")
    project = root()
    businesses = load_businesses(project / "fixtures" / "businesses.csv")
    events = load_events(project / "fixtures" / "events.csv")
    console.print(
        f"[green]Validated[/green] {len(businesses)} businesses and {len(events)} evidence events."
    )


@app.command("fetch-brampton")
def fetch_brampton(limit: int = typer.Option(25, min=1, max=250)) -> None:
    """Fetch a bounded sample from the public Brampton building-permits service."""
    events = fetch_brampton_permits(limit=limit)
    console.print(f"Fetched {len(events)} permit event(s).")
    for event in events[:5]:
        console.print(f"- {event.source_record_id}: {event.address} — {event.event_date}")


@app.command()
def doctor() -> None:
    """Print local runtime status."""
    project = root()
    table = Table(title="CRE Foundry Environment")
    table.add_column("Check")
    table.add_column("Value")
    table.add_row("Version", __version__)
    table.add_row("Project", str(project))
    table.add_row("Fixtures", "OK" if (project / "fixtures" / "events.csv").exists() else "MISSING")
    table.add_row("Operating mode", "review-only")
    console.print(table)
