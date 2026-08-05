from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

import duckdb
import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from cre_foundry.control_cli import control_app
from cre_foundry.orchestration_cli import orchestration_app
from cre_foundry.scheduler_cli import scheduler_app

app = typer.Typer(
    name="cre-foundry",
    help="Local-first commercial real estate intelligence foundry.",
    no_args_is_help=True,
)

console = Console()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@app.command()
def doctor() -> None:
    """Verify the local architecture and core analytical dependencies."""
    root = project_root()
    warehouse_dir = root / "data" / "warehouse"
    control_dir = root / "data" / "control"

    warehouse_dir.mkdir(parents=True, exist_ok=True)
    control_dir.mkdir(parents=True, exist_ok=True)

    duckdb_path = warehouse_dir / "cre.duckdb"

    with duckdb.connect(str(duckdb_path)) as connection:
        duckdb_version_row = connection.execute("SELECT version()").fetchone()

        if duckdb_version_row is None:
            raise RuntimeError("DuckDB did not return its version.")

        duckdb_version = duckdb_version_row[0]

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS system_metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            INSERT OR REPLACE INTO system_metadata (key, value)
            VALUES ('operating_mode', 'shadow')
            """
        )

        operating_mode_row = connection.execute(
            """
            SELECT value
            FROM system_metadata
            WHERE key = 'operating_mode'
            """
        ).fetchone()

        if operating_mode_row is None:
            raise RuntimeError("Operating mode was not initialized.")

        operating_mode = operating_mode_row[0]

    disk = shutil.disk_usage(root)

    table = Table(title="CRE Foundry Environment")
    table.add_column("Check", style="bold")
    table.add_column("Value")

    table.add_row("Project root", str(root))
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Architecture", platform.machine())
    table.add_row("Executable", sys.executable)
    table.add_row("DuckDB", str(duckdb_version))
    table.add_row("Polars", pl.__version__)
    table.add_row("Warehouse", str(duckdb_path))
    table.add_row("Operating mode", str(operating_mode))
    table.add_row(
        "Disk available",
        f"{disk.free / (1024**3):.1f} GiB",
    )

    console.print(table)

    if platform.machine() != "arm64":
        raise typer.Exit(code=1)

    if operating_mode != "shadow":
        console.print("[bold red]Unsafe operating mode detected.[/bold red]")
        raise typer.Exit(code=1)

    console.print("\n[bold green]FOUNDATION CHECK PASSED[/bold green]")
    console.print("Native ARM64, shadow mode, DuckDB, and Polars are operational.")


@app.command()
def version() -> None:
    """Display the project version."""
    console.print("cre-foundry 0.1.0")


source_app = typer.Typer(
    help="Inspect and acquire approved external sources.",
    no_args_is_help=True,
)

app.add_typer(source_app, name="source")


@source_app.command("inspect-plantrak")
def inspect_plantrak() -> None:
    """Inspect current Brampton Plantrak service contracts."""
    import orjson

    from cre_foundry.connectors.plantrak import (
        PlantrakConnector,
        load_source_config,
    )

    root = project_root()
    config = load_source_config(root / "config" / "sources" / "brampton_plantrak.yaml")

    connector = PlantrakConnector(
        project_root=root,
        config=config,
    )

    result = connector.inspect_service()

    console.print_json(
        orjson.dumps(
            result,
            option=orjson.OPT_INDENT_2,
        ).decode()
    )


@source_app.command("fetch-plantrak")
def fetch_plantrak(
    layers: str = typer.Option(
        "1,2",
        help="Comma-separated configured layer IDs.",
    ),
) -> None:
    """Acquire immutable Plantrak layer snapshots."""
    from cre_foundry.connectors.plantrak import (
        PlantrakConnector,
        load_source_config,
    )

    layer_ids = [int(value.strip()) for value in layers.split(",") if value.strip()]

    root = project_root()
    config = load_source_config(root / "config" / "sources" / "brampton_plantrak.yaml")

    connector = PlantrakConnector(
        project_root=root,
        config=config,
    )

    manifest = connector.fetch(layer_ids=layer_ids)

    console.print(f"[bold green]Source run succeeded:[/bold green] {manifest.run_id}")

    for snapshot in manifest.layer_snapshots:
        console.print(
            f"Layer {snapshot.layer_id}: {snapshot.record_count} records -> {snapshot.raw_path}"
        )


app.add_typer(
    control_app,
    name="control",
)


app.add_typer(
    orchestration_app,
    name="run",
)


app.add_typer(
    scheduler_app,
    name="scheduler",
)


@source_app.command("preflight-odbus")
def preflight_odbus() -> None:
    """Inspect the licensed ODBus archive before download."""
    import json

    from cre_foundry.connectors.statscan_odbus import (
        ODBusConnector,
        load_odbus_config,
    )

    root = project_root()

    config = load_odbus_config(root / "config" / "sources" / "statscan_odbus.yaml")

    connector = ODBusConnector(
        project_root=root,
        config=config,
    )

    result = connector.preflight()

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    if not result["disk_safe_for_download"]:
        console.print("[bold red]DISK SAFETY CHECK FAILED[/bold red]")
        raise typer.Exit(code=1)

    console.print("[bold green]ODBUS PREFLIGHT PASSED[/bold green]")


@source_app.command("acquire-odbus")
def acquire_odbus() -> None:
    """Acquire one immutable licensed ODBus archive."""
    import json

    from cre_foundry.connectors.statscan_odbus import (
        ODBusConnector,
        load_odbus_config,
    )
    from cre_foundry.control import (
        ControlDatabase,
        utc_now,
    )

    root = project_root()

    config = load_odbus_config(root / "config" / "sources" / "statscan_odbus.yaml")

    database = ControlDatabase(root / "data" / "control" / "operations.sqlite3")

    database.initialize()
    database.register_source(config)

    as_of = utc_now()

    with database.source_lock(
        config.source_id,
        ttl_minutes=120,
    ):
        run_id = database.start_run(
            source_id=config.source_id,
            run_type="bulk_acquisition",
            as_of_timestamp=as_of,
        )

        connector = ODBusConnector(
            project_root=root,
            config=config,
        )

        try:
            result = connector.acquire(
                run_id=run_id,
                as_of_timestamp=as_of,
            )

            database.complete_run(
                run_id=run_id,
                records_observed=(result["member_count"]),
                bytes_written=(result["archive_bytes"]),
                schema_changed=False,
                manifest_path=(result["manifest_path"]),
                metadata=result,
            )

            cadence = database.update_health(
                source_id=config.source_id,
                success=True,
                changed=True,
                now=as_of,
            )

        except Exception as exc:
            database.fail_run(
                run_id=run_id,
                error=exc,
            )

            database.update_health(
                source_id=config.source_id,
                success=False,
                changed=False,
                error=exc,
                now=as_of,
            )

            raise

    result["next_due_at"] = cadence.next_due_at.isoformat()

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ODBUS BRONZE ACQUISITION PASSED[/bold green]")


@source_app.command("inspect-odbus-schema")
def inspect_odbus_schema() -> None:
    """Profile the immutable ODBus CSV and record layout."""
    import json

    from cre_foundry.odbus_schema import (
        inspect_latest_odbus_schema,
        write_schema_report,
    )

    root = project_root()

    report = inspect_latest_odbus_schema(root)

    report_path = write_schema_report(
        project_root=root,
        report=report,
    )

    summary = {
        "source_id": report["source_id"],
        "archive_sha256": report["archive_sha256"],
        "data_member": report["data_member"],
        "data_encoding": report["data_encoding"],
        "data_delimiter": report["data_delimiter"],
        "row_count": report["row_count"],
        "column_count": report["column_count"],
        "columns": report["column_profiles"],
        "record_layout_columns": (report["record_layout"]["columns"]),
        "record_layout_rows": (report["record_layout"]["row_count"]),
        "report_path": str(report_path.relative_to(root)),
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ODBUS SCHEMA INSPECTION PASSED[/bold green]")


@source_app.command("profile-odbus-values")
def profile_odbus_values() -> None:
    """Profile ODBus geography and business-field values."""
    import json

    from cre_foundry.odbus_semantics import (
        profile_latest_odbus_values,
        write_value_profile,
    )

    root = project_root()

    report = profile_latest_odbus_values(root)

    report_path = write_value_profile(
        project_root=root,
        report=report,
    )

    summary = {
        "source_id": report["source_id"],
        "row_count": report["row_count"],
        "province_alignment": report["province_alignment"],
        "target_market": report["target_market"],
        "status_counts": report["status_counts"],
        "provider_counts": report["provider_counts"],
        "geo_source_counts": report["geo_source_counts"],
        "coordinate_quality": report["coordinate_quality"],
        "employee_field": report["employee_field"],
        "naics_field": report["naics_field"],
        "row_anomalies": report["row_anomalies"],
        "report_path": str(report_path.relative_to(root)),
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ODBUS VALUE PROFILING PASSED[/bold green]")


@source_app.command("build-odbus-silver")
def build_odbus_silver_command() -> None:
    """Build target-market silver Parquet and DuckDB tables."""
    import json

    from cre_foundry.bulk_storage import (
        write_json_atomic,
    )
    from cre_foundry.odbus_silver import (
        build_latest_odbus_silver,
    )

    root = project_root()

    report = build_latest_odbus_silver(root)

    contract_path = root / "docs" / "data_contracts" / "statscan_odbus_target_market_silver.json"

    write_json_atomic(
        contract_path,
        report,
    )

    summary = {
        "source_id": report["source_id"],
        "transformation_version": report["transformation_version"],
        "source_row_count": report["source_row_count"],
        "ontario_row_count": report["ontario_row_count"],
        "target_candidate_count": report["target_candidate_count"],
        "silver_row_count": report["silver_row_count"],
        "quarantined_conflict_count": report["quarantined_conflict_count"],
        "municipality_counts": report["municipality_counts"],
        "municipality_resolution_counts": (report["municipality_resolution_counts"]),
        "pruid_unknown_count": report["pruid_unknown_count"],
        "invalid_coordinate_count": report["invalid_coordinate_count"],
        "employee_unparsed_count": report["employee_unparsed_count"],
        "duplicate_entity_fingerprint_count": (report["duplicate_entity_fingerprint_count"]),
        "target_parquet_path": report["target_parquet_path"],
        "target_parquet_sha256": report["target_parquet_sha256"],
        "conflicts_parquet_path": report["conflicts_parquet_path"],
        "warehouse_path": report["warehouse_path"],
        "duckdb_target_count": report["duckdb_target_count"],
        "duckdb_conflict_count": report["duckdb_conflict_count"],
        "current_status_verified": report["current_status_verified"],
        "reused_existing": report["reused_existing"],
        "contract_path": str(contract_path.relative_to(root)),
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ODBUS SILVER BUILD PASSED[/bold green]")


@source_app.command("build-odbus-entities")
def build_odbus_entities_command() -> None:
    """Build canonical entities while retaining observations."""
    import json

    from cre_foundry.odbus_entities import (
        build_odbus_entity_model,
    )

    report = build_odbus_entity_model(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ODBUS ENTITY MODEL PASSED[/bold green]")


@source_app.command("build-odbus-segments")
def build_odbus_segments_command() -> None:
    """Build conservative industrial segmentation."""
    import json

    from cre_foundry.odbus_segments import (
        build_odbus_industrial_segments,
    )

    report = build_odbus_industrial_segments(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ODBUS INDUSTRIAL SEGMENTATION PASSED[/bold green]")


@source_app.command("inspect-brampton-permits")
def inspect_brampton_permits() -> None:
    """Inspect the approved Brampton permit source."""
    import json

    from cre_foundry.connectors.brampton_permits import (
        BramptonPermitConnector,
        load_permit_config,
    )

    root = project_root()

    config = load_permit_config(root / "config" / "sources" / "brampton_building_permits.yaml")

    connector = BramptonPermitConnector(
        project_root=root,
        config=config,
    )

    result = connector.inspect_service()

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT INSPECTION PASSED[/bold green]")


@source_app.command("acquire-brampton-permits")
def acquire_brampton_permits() -> None:
    """Acquire an immutable industrial-permit snapshot."""
    import json

    from cre_foundry.connectors.brampton_permits import (
        BramptonPermitConnector,
        load_permit_config,
    )
    from cre_foundry.control import (
        ControlDatabase,
        utc_now,
    )

    root = project_root()

    config = load_permit_config(root / "config" / "sources" / "brampton_building_permits.yaml")

    database = ControlDatabase(root / "data" / "control" / "operations.sqlite3")

    database.initialize()
    database.register_source(config)

    as_of = utc_now()

    with database.source_lock(
        config.source_id,
        ttl_minutes=120,
    ):
        run_id = database.start_run(
            source_id=config.source_id,
            run_type="filtered_snapshot_acquisition",
            as_of_timestamp=as_of,
        )

        connector = BramptonPermitConnector(
            project_root=root,
            config=config,
        )

        try:
            result = connector.acquire(
                run_id=run_id,
                as_of_timestamp=as_of,
            )

            database.complete_run(
                run_id=run_id,
                records_observed=(result["record_count"]),
                bytes_written=(result["bytes_written"]),
                schema_changed=False,
                manifest_path=(result["manifest_path"]),
                metadata=result,
            )

            cadence = database.update_health(
                source_id=config.source_id,
                success=True,
                changed=True,
                now=as_of,
            )

        except Exception as exc:
            database.fail_run(
                run_id=run_id,
                error=exc,
            )

            database.update_health(
                source_id=config.source_id,
                success=False,
                changed=False,
                error=exc,
                now=as_of,
            )

            raise

    result["next_due_at"] = cadence.next_due_at.isoformat()

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT BRONZE ACQUISITION PASSED[/bold green]")


@source_app.command("build-brampton-permit-silver")
def build_brampton_permit_silver_command() -> None:
    """Normalize the latest industrial-permit snapshot."""
    import json

    from cre_foundry.brampton_permit_silver import (
        build_brampton_permit_silver,
    )

    report = build_brampton_permit_silver(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT SILVER BUILD PASSED[/bold green]")


@source_app.command("build-brampton-permit-entity-bridge")
def build_brampton_permit_entity_bridge_command() -> None:
    """Link active permits to exact ODBus address candidates."""
    import json

    from cre_foundry.brampton_permit_entity_bridge import (
        build_brampton_permit_entity_bridge,
    )

    report = build_brampton_permit_entity_bridge(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT-ENTITY BRIDGE PASSED[/bold green]")


@source_app.command("inspect-brampton-business-directory")
def inspect_brampton_business_directory() -> None:
    """Inspect the approved production directory."""
    import json

    from cre_foundry.connectors.brampton_business_directory import (
        BramptonBusinessDirectoryConnector,
        load_business_directory_config,
    )

    root = project_root()

    config = load_business_directory_config(
        root / "config" / "sources" / "brampton_business_directory.yaml"
    )

    connector = BramptonBusinessDirectoryConnector(
        project_root=root,
        config=config,
    )

    result = connector.inspect_service()

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON BUSINESS DIRECTORY INSPECTION PASSED[/bold green]")


@source_app.command("acquire-brampton-business-directory")
def acquire_brampton_business_directory() -> None:
    """Acquire the licensed production directory."""
    import json

    from cre_foundry.connectors.brampton_business_directory import (
        BramptonBusinessDirectoryConnector,
        load_business_directory_config,
    )
    from cre_foundry.control import (
        ControlDatabase,
        utc_now,
    )

    root = project_root()

    config = load_business_directory_config(
        root / "config" / "sources" / "brampton_business_directory.yaml"
    )

    database = ControlDatabase(root / "data" / "control" / "operations.sqlite3")

    database.initialize()
    database.register_source(config)

    as_of = utc_now()

    with database.source_lock(
        config.source_id,
        ttl_minutes=120,
    ):
        run_id = database.start_run(
            source_id=config.source_id,
            run_type=("current_directory_snapshot"),
            as_of_timestamp=as_of,
        )

        connector = BramptonBusinessDirectoryConnector(
            project_root=root,
            config=config,
        )

        try:
            result = connector.acquire(
                run_id=run_id,
                as_of_timestamp=as_of,
            )

            database.complete_run(
                run_id=run_id,
                records_observed=(result["record_count"]),
                bytes_written=(result["bytes_written"]),
                schema_changed=False,
                manifest_path=(result["manifest_path"]),
                metadata=result,
            )

            cadence = database.update_health(
                source_id=config.source_id,
                success=True,
                changed=True,
                now=as_of,
            )

        except Exception as exc:
            database.fail_run(
                run_id=run_id,
                error=exc,
            )

            database.update_health(
                source_id=config.source_id,
                success=False,
                changed=False,
                error=exc,
                now=as_of,
            )

            raise

    result["next_due_at"] = cadence.next_due_at.isoformat()

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON BUSINESS DIRECTORY BRONZE ACQUISITION PASSED[/bold green]")


@source_app.command("build-brampton-business-directory-silver")
def build_brampton_business_directory_silver_command() -> None:
    """Normalize the latest production directory."""
    import json

    from cre_foundry.brampton_business_directory_silver import (
        build_brampton_business_directory_silver,
    )

    report = build_brampton_business_directory_silver(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON BUSINESS DIRECTORY SILVER BUILD PASSED[/bold green]")


@source_app.command("build-brampton-permit-directory-bridge")
def build_brampton_permit_directory_bridge_command() -> None:
    """Link active permits to current directory addresses."""
    import json

    from cre_foundry.brampton_permit_directory_bridge import (
        build_brampton_permit_directory_bridge,
    )

    report = build_brampton_permit_directory_bridge(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT-DIRECTORY BRIDGE PASSED[/bold green]")


@source_app.command("build-brampton-cross-source-reconciliation")
def build_brampton_cross_source_reconciliation_command() -> None:
    """Reconcile historical and current permit address evidence."""
    import json

    from cre_foundry.brampton_cross_source_reconciliation import (
        build_brampton_cross_source_reconciliation,
    )

    report = build_brampton_cross_source_reconciliation(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON CROSS-SOURCE RECONCILIATION PASSED[/bold green]")


@source_app.command("build-brampton-permit-opportunity-evidence")
def build_brampton_permit_opportunity_evidence_command() -> None:
    """Build one conservative evidence row per active permit."""
    import json

    from cre_foundry.brampton_permit_opportunity_evidence import (
        build_brampton_permit_opportunity_evidence,
    )

    report = build_brampton_permit_opportunity_evidence(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT OPPORTUNITY EVIDENCE BUILD PASSED[/bold green]")


@source_app.command("build-brampton-permit-verification-plan")
def build_brampton_permit_verification_plan_command() -> None:
    """Create the initial verification workflow and work queue."""
    import json

    from cre_foundry.brampton_permit_verification_plan import (
        build_brampton_permit_verification_plan,
    )

    report = build_brampton_permit_verification_plan(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON PERMIT VERIFICATION PLAN BUILD PASSED[/bold green]")


@source_app.command("initialize-brampton-verification-ledger")
def initialize_brampton_verification_ledger_command() -> None:
    """Initialize the append-only verification event ledger."""
    import json

    from cre_foundry.brampton_verification_ledger import (
        initialize_verification_ledger,
    )

    report = initialize_verification_ledger(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON VERIFICATION LEDGER INITIALIZATION PASSED[/bold green]")


@source_app.command("project-brampton-verification-state")
def project_brampton_verification_state_command() -> None:
    """Project append-only verification events into current state."""
    import json

    from cre_foundry.brampton_verification_ledger import (
        project_verification_state,
    )

    report = project_verification_state(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON VERIFICATION STATE PROJECTION PASSED[/bold green]")


@source_app.command("record-brampton-verification-event")
def record_brampton_verification_event_command(
    verification_task_id: str,
    event_type: str,
    reviewer: str = "",
    evidence_source_type: str = "",
    evidence_reference: str = "",
    notes: str = "",
) -> None:
    """Append one validated verification event."""
    import json

    from cre_foundry.brampton_verification_ledger import (
        record_verification_event,
    )

    report = record_verification_event(
        project_root(),
        verification_task_id=(verification_task_id),
        event_type=event_type,
        reviewer=reviewer or None,
        evidence_source_type=(evidence_source_type or None),
        evidence_reference=(evidence_reference or None),
        notes=notes or None,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON VERIFICATION EVENT RECORDED[/bold green]")


@source_app.command("export-brampton-verification-review-packets")
def export_brampton_verification_review_packets_command() -> None:
    """Export review packets for every ready verification task."""
    import json

    from cre_foundry.brampton_verification_review_packets import (
        build_brampton_verification_review_packets,
    )

    report = build_brampton_verification_review_packets(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BRAMPTON VERIFICATION REVIEW PACKET EXPORT PASSED[/bold green]")


@source_app.command("plan-data-plane")
def plan_data_plane_command(
    pipeline: str = "brampton_operational",
    include_acquisition: bool = False,
) -> None:
    """Resolve and print the governed data-pipeline execution plan."""
    import json

    from cre_foundry.data_plane import (
        build_data_plane_plan,
    )

    report = build_data_plane_plan(
        project_root(),
        pipeline=pipeline,
        include_acquisition=include_acquisition,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DATA-PLANE PLAN PASSED[/bold green]")


@source_app.command("audit-data-plane")
def audit_data_plane_command() -> None:
    """Audit tools, storage, command wiring, warehouse and control state."""
    import json

    from cre_foundry.data_plane import (
        build_data_plane_readiness,
    )

    report = build_data_plane_readiness(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DATA-PLANE READINESS AUDIT PASSED[/bold green]")


@source_app.command("run-data-plane")
def run_data_plane_command(
    pipeline: str = "brampton_operational",
    include_acquisition: bool = False,
    dry_run: bool = True,
) -> None:
    """Run the governed data pipeline with locking and stage manifests."""
    import json

    from cre_foundry.data_plane import (
        run_data_plane,
    )

    report = run_data_plane(
        project_root(),
        pipeline=pipeline,
        include_acquisition=include_acquisition,
        dry_run=dry_run,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DATA-PLANE RUN PASSED[/bold green]")


@source_app.command("initialize-source-operations")
def initialize_source_operations_command() -> None:
    """Initialize governed immutable source-snapshot controls."""
    import json

    from cre_foundry.source_operations import (
        initialize_source_operations,
    )

    report = initialize_source_operations(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE OPERATIONS INITIALIZATION PASSED[/bold green]")


@source_app.command("audit-source-operations")
def audit_source_operations_command() -> None:
    """Audit source policies, snapshots, checksums and freshness."""
    import json

    from cre_foundry.source_operations import (
        audit_source_operations,
    )

    report = audit_source_operations(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE OPERATIONS AUDIT PASSED[/bold green]")


@source_app.command("register-source-snapshot")
def register_source_snapshot_command(
    source_id: str,
    file_path: Path,
    observed_at: str | None = None,
    acquisition_method: str = "manual_file",
    content_type: str = "application/octet-stream",
    dry_run: bool = True,
) -> None:
    """Validate or register one immutable content-addressed snapshot."""
    import json

    from cre_foundry.source_operations import (
        register_source_snapshot,
    )

    report = register_source_snapshot(
        project_root(),
        source_id=source_id,
        file_path=file_path,
        observed_at=observed_at,
        acquisition_method=acquisition_method,
        content_type=content_type,
        dry_run=dry_run,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE SNAPSHOT REGISTRATION PASSED[/bold green]")


@source_app.command("plan-source-snapshot-replay")
def plan_source_snapshot_replay_command(
    snapshot_id: str,
) -> None:
    """Verify an immutable snapshot and create a no-reacquisition replay plan."""
    import json

    from cre_foundry.source_operations import (
        plan_snapshot_replay,
    )

    report = plan_snapshot_replay(
        project_root(),
        snapshot_id=snapshot_id,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE SNAPSHOT REPLAY PLAN PASSED[/bold green]")


@source_app.command("audit-browser-acquisition")
def audit_browser_acquisition_command() -> None:
    """Audit governed browser and computer-vision acquisition readiness."""
    import json

    from cre_foundry.browser_acquisition import (
        audit_browser_acquisition,
    )

    report = audit_browser_acquisition(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BROWSER ACQUISITION AUDIT PASSED[/bold green]")


@source_app.command("initialize-source-runtime")
def initialize_source_runtime_command() -> None:
    """Initialize source scheduling and circuit-breaker state."""
    import json

    from cre_foundry.source_runtime import (
        initialize_source_runtime,
    )

    report = initialize_source_runtime(project_root())

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE RUNTIME INITIALIZATION PASSED[/bold green]")


@source_app.command("plan-source-acquisitions")
def plan_source_acquisitions_command() -> None:
    """Plan authorized source acquisitions without executing them."""
    import json

    from cre_foundry.source_runtime import (
        plan_source_acquisitions,
    )

    report = plan_source_acquisitions(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE ACQUISITION PLAN PASSED[/bold green]")


@source_app.command("audit-source-runtime")
def audit_source_runtime_command() -> None:
    """Audit source runtime state, bindings and circuit controls."""
    import json

    from cre_foundry.source_runtime import (
        audit_source_runtime,
    )

    report = audit_source_runtime(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE RUNTIME AUDIT PASSED[/bold green]")


@source_app.command("plan-source-snapshot-bootstrap")
def plan_source_snapshot_bootstrap_command() -> None:
    """Discover exactly attributable existing source artifacts."""
    import json

    from cre_foundry.source_runtime import (
        discover_snapshot_bootstrap_candidates,
    )

    report = discover_snapshot_bootstrap_candidates(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE SNAPSHOT BOOTSTRAP PLAN PASSED[/bold green]")


@source_app.command("audit-browser-recipes")
def audit_browser_recipes_command() -> None:
    """Audit browser/CV recipes without executing a browser."""
    import json

    from cre_foundry.browser_recipes import (
        audit_browser_recipes,
    )

    report = audit_browser_recipes(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BROWSER RECIPE AUDIT PASSED[/bold green]")


@source_app.command("audit-primitive-inventory")
def audit_primitive_inventory_command() -> None:
    """Inventory actual DuckDB and SQLite schema primitives."""
    import json

    from cre_foundry.primitive_inventory import (
        build_primitive_inventory,
    )

    report = build_primitive_inventory(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]PRIMITIVE INVENTORY AUDIT PASSED[/bold green]")


@source_app.command("audit-primitive-quality")
def audit_primitive_quality_command() -> None:
    """Profile actual primitives without sampling or mutation."""
    import json

    from cre_foundry.primitive_quality import (
        build_primitive_quality_profile,
    )

    report = build_primitive_quality_profile(
        project_root(),
        write_contracts=True,
    )

    summary = report["summary"]

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]PRIMITIVE QUALITY AUDIT PASSED[/bold green]")


@source_app.command("audit-snapshot-bootstrap-review")
def audit_snapshot_bootstrap_review_command() -> None:
    """Verify exact bootstrap manifests without registration."""
    import json

    from cre_foundry.snapshot_bootstrap_review import (
        build_snapshot_bootstrap_review,
    )

    report = build_snapshot_bootstrap_review(
        project_root(),
        write_contract=True,
        write_packets=True,
    )

    summary = {
        "model_version": report["model_version"],
        "candidate_count": report["candidate_count"],
        "packet_count": report["packet_count"],
        "review_ready_count": report["review_ready_count"],
        "blocked_review_count": report["blocked_review_count"],
        "violation_count": report["violation_count"],
        "total_referenced_bytes": report["total_referenced_bytes"],
        "automatic_registration_performed": (report["automatic_registration_performed"]),
        "registration_execution_count": (report["registration_execution_count"]),
        "registration_permitted": (report["registration_permitted"]),
        "human_approval_required": (report["human_approval_required"]),
        "operating_mode": report["operating_mode"],
        "opportunity_ranked": report["opportunity_ranked"],
        "outreach_eligible": report["outreach_eligible"],
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SNAPSHOT BOOTSTRAP REVIEW PASSED[/bold green]")


@source_app.command("audit-pilot-readiness")
def audit_pilot_readiness_command() -> None:
    """Build the consolidated controlled-pilot readiness dossier."""
    import json

    from cre_foundry.pilot_readiness import (
        build_pilot_readiness_dossier,
    )

    report = build_pilot_readiness_dossier(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["model_version"],
        "overall_status": report["overall_status"],
        "capabilities": report["capabilities"],
        "missing_client_input_count": report["missing_client_input_count"],
        "missing_client_input_ids": report["missing_client_input_ids"],
        "source_state": report["source_state"],
        "data_state": report["data_state"],
        "verification_state": report["verification_state"],
        "bootstrap_state": report["bootstrap_state"],
        "browser_state": report["browser_state"],
        "next_actions": report["next_actions"],
        "research_foundation_ready": report["research_foundation_ready"],
        "manual_verification_workflow_ready": report["manual_verification_workflow_ready"],
        "pilot_execution_ready": report["pilot_execution_ready"],
        "production_ranking_ready": report["production_ranking_ready"],
        "outreach_ready": report["outreach_ready"],
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]PILOT READINESS DOSSIER PASSED[/bold green]")


@source_app.command("initialize-data-health")
def initialize_data_health_command() -> None:
    """Create the dependency-aware data-health baseline."""
    import json

    from cre_foundry.data_health import (
        build_data_health_bundle,
    )

    report = build_data_health_bundle(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "baseline_ready": report["baseline"]["baseline_ready"],
        "relation_count": report["baseline"]["relation_count"],
        "primitive_count": report["baseline"]["primitive_count"],
        "issue_count": report["baseline"]["issue_count"],
        "dependency_edge_count": report["dependencies"]["edge_count"],
        "remediation_work_item_count": report["remediation"]["work_item_count"],
        "automatic_schema_mutation": False,
        "automatic_backfill": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DATA HEALTH BASELINE PASSED[/bold green]")


@source_app.command("audit-data-health")
def audit_data_health_command() -> None:
    """Compare current relation health with the saved baseline."""
    import json

    from cre_foundry.data_health import (
        audit_data_health_baseline,
    )

    report = audit_data_health_baseline(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DATA HEALTH AUDIT PASSED[/bold green]")


@source_app.command("initialize-shadow-learning")
def initialize_shadow_learning_command() -> None:
    """Initialize the empty fail-closed shadow-learning database."""
    import json

    from cre_foundry.shadow_learning import (
        initialize_shadow_learning,
    )

    report = initialize_shadow_learning(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SHADOW LEARNING INITIALIZATION PASSED[/bold green]")


@source_app.command("audit-shadow-learning")
def audit_shadow_learning_command() -> None:
    """Audit empty shadow-learning tables and blockers."""
    import json

    from cre_foundry.shadow_learning import (
        audit_shadow_learning,
    )

    report = audit_shadow_learning(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SHADOW LEARNING AUDIT PASSED[/bold green]")


@source_app.command("audit-shadow-feature-review")
def audit_shadow_feature_review_command() -> None:
    """Review all real primitives for future feature safety."""
    import json

    from cre_foundry.shadow_learning import (
        build_shadow_feature_review,
    )

    report = build_shadow_feature_review(
        project_root(),
        write_contract=True,
    )

    summary = {
        "model_version": report["model_version"],
        "primitive_count": report["primitive_count"],
        "missing_quality_profile_count": report["missing_quality_profile_count"],
        "feature_role_counts": report["feature_role_counts"],
        "approved_feature_count": report["approved_feature_count"],
        "enabled_feature_count": report["enabled_feature_count"],
        "review_ready": report["review_ready"],
        "model_training_enabled": report["model_training_enabled"],
        "production_ranking_enabled": report["production_ranking_enabled"],
        "outreach_enabled": report["outreach_enabled"],
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SHADOW FEATURE REVIEW PASSED[/bold green]")


@source_app.command("plan-shadow-evaluation")
def plan_shadow_evaluation_command() -> None:
    """Plan forward-chaining evaluation without execution."""
    import json

    from cre_foundry.shadow_learning import (
        plan_shadow_evaluation,
    )

    report = plan_shadow_evaluation(
        project_root(),
        write_contract=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SHADOW EVALUATION PLAN PASSED[/bold green]")


@source_app.command("export-client-input-bundle")
def export_client_input_bundle_command() -> None:
    """Export the five authoritative client-input templates."""
    import json

    from cre_foundry.shadow_learning import (
        export_client_input_bundle,
    )

    report = export_client_input_bundle(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]CLIENT INPUT BUNDLE PASSED[/bold green]")


@source_app.command("audit-temporal-readiness")
def audit_temporal_readiness_command() -> None:
    """Build point-in-time and feature-definition readiness contracts."""
    import json

    from cre_foundry.temporal_readiness import (
        build_temporal_readiness_bundle,
    )

    report = build_temporal_readiness_bundle(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["temporal_review"]["model_version"],
        "relation_count": report["temporal_review"]["relation_count"],
        "primitive_count": report["temporal_review"]["primitive_count"],
        "status_counts": report["temporal_review"]["status_counts"],
        "approved_temporal_relation_count": report["temporal_review"][
            "approved_temporal_relation_count"
        ],
        "feature_definition_count": report["feature_queue"]["definition_count"],
        "approved_feature_definition_count": report["feature_queue"]["approved_definition_count"],
        "dataset_blocker_count": report["dataset_plan"]["blocker_count"],
        "dataset_build_ready": report["dataset_plan"]["dataset_build_ready"],
        "dataset_build_execution_permitted": report["dataset_plan"][
            "dataset_build_execution_permitted"
        ],
        "model_training_permitted": report["dataset_plan"]["model_training_permitted"],
        "production_ranking_permitted": report["dataset_plan"]["production_ranking_permitted"],
        "outreach_permitted": report["dataset_plan"]["outreach_permitted"],
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]TEMPORAL READINESS AUDIT PASSED[/bold green]")


@source_app.command("audit-snapshot-admission")
def audit_snapshot_admission_command() -> None:
    """Cryptographically validate reviewed snapshot candidates."""
    import json

    from cre_foundry.snapshot_admission import (
        build_snapshot_admission,
    )

    report = build_snapshot_admission(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["admission"]["model_version"],
        "source_packet_count": report["admission"]["source_packet_count"],
        "admission_ready_count": report["admission"]["admission_ready_count"],
        "blocked_count": report["admission"]["blocked_count"],
        "artifact_count": report["admission"]["artifact_count"],
        "total_referenced_bytes": report["admission"]["total_referenced_bytes"],
        "all_packets_admission_ready": report["admission"]["all_packets_admission_ready"],
        "replay_metadata_ready_count": report["replay"]["replay_metadata_ready_count"],
        "snapshot_registration_permitted": report["admission"]["snapshot_registration_permitted"],
        "snapshot_registration_execution_count": report["admission"][
            "snapshot_registration_execution_count"
        ],
        "artifact_copy_execution_count": report["admission"]["artifact_copy_execution_count"],
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SNAPSHOT ADMISSION AUDIT PASSED[/bold green]")


@source_app.command("audit-source-cadence")
def audit_source_cadence_command() -> None:
    """Derive source cadence only from declared manifest history."""
    import json

    from cre_foundry.source_cadence import (
        build_source_cadence,
    )

    report = build_source_cadence(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["observations"]["model_version"],
        "configured_source_count": report["observations"]["configured_source_count"],
        "candidate_file_count": report["observations"]["candidate_file_count"],
        "candidate_file_overflow_count": report["observations"]["candidate_file_overflow_count"],
        "parse_error_count": report["observations"]["parse_error_count"],
        "insufficient_history_count": report["candidates"]["insufficient_history_count"],
        "provisional_history_count": report["candidates"]["provisional_history_count"],
        "observed_baseline_count": report["candidates"]["observed_baseline_count"],
        "approved_schedule_count": report["candidates"]["approved_schedule_count"],
        "enabled_schedule_count": report["candidates"]["enabled_schedule_count"],
        "automatic_acquisition_execution_count": report["candidates"][
            "automatic_acquisition_execution_count"
        ],
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE CADENCE AUDIT PASSED[/bold green]")


@source_app.command("audit-source-containers")
def audit_source_containers_command() -> None:
    """Inspect admitted containers without extraction."""
    import json

    from cre_foundry.source_container_recon import (
        build_source_container_recon,
    )

    report = build_source_container_recon(
        project_root(),
        write_contracts=True,
    )

    inventory = report["inventory"]

    parser_evidence = report["parser_evidence"]

    summary = {
        "entry_count": inventory["entry_count"],
        "zip_container_count": inventory["zip_container_count"],
        "gzip_container_count": inventory["gzip_container_count"],
        "plain_file_count": inventory["plain_file_count"],
        "recon_ready_count": inventory["recon_ready_count"],
        "blocked_count": inventory["blocked_count"],
        "parser_evidence_ready_count": (parser_evidence["evidence_ready_count"]),
        "approved_parser_contract_count": 0,
        "archive_extraction_execution_count": 0,
        "gzip_decompression_execution_count": 0,
        "parser_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE CONTAINER AUDIT PASSED[/bold green]")


@source_app.command("audit-snapshot-registration-review")
def audit_snapshot_registration_review_command() -> None:
    """Build manual snapshot-registration review packets."""
    import json

    from cre_foundry.snapshot_registration_review import (
        build_snapshot_registration_review,
    )

    report = build_snapshot_registration_review(
        project_root(),
        write_contracts=True,
    )

    review = report["review"]

    summary = {
        "governed_source_count": review["governed_source_count"],
        "candidate_count": review["candidate_count"],
        "review_ready_count": review["review_ready_count"],
        "structurally_blocked_count": review["structurally_blocked_count"],
        "unadmitted_source_count": review["unadmitted_source_count"],
        "unadmitted_source_ids": review["unadmitted_source_ids"],
        "existing_snapshot_count": review["existing_snapshot_count"],
        "snapshot_event_count": review["snapshot_event_count"],
        "approved_registration_count": 0,
        "registration_sql_generation_count": 0,
        "snapshot_registration_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SNAPSHOT REGISTRATION REVIEW PASSED[/bold green]")


@source_app.command("audit-bounded-parser-probes")
def audit_bounded_parser_probes_command() -> None:
    """Inspect bounded artifact prefixes without full parsing."""
    import json

    from cre_foundry.bounded_parser_probe import (
        build_bounded_parser_probe,
    )

    report = build_bounded_parser_probe(
        project_root(),
        write_contracts=True,
    )

    probe = report["probe"]

    summary = {
        "model_version": probe["model_version"],
        "entry_count": probe["entry_count"],
        "probe_completed_count": probe["probe_completed_count"],
        "recognized_artifact_count": probe["recognized_artifact_count"],
        "parser_approval_ready_count": probe["parser_approval_ready_count"],
        "blocked_count": probe["blocked_count"],
        "integrity_violation_count": probe["integrity_violation_count"],
        "bounded_stream_read_count": probe["bounded_stream_read_count"],
        "bounded_decompression_count": probe["bounded_decompression_count"],
        "archive_extraction_execution_count": 0,
        "full_decompression_execution_count": 0,
        "full_parser_execution_count": 0,
        "row_materialization_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]BOUNDED PARSER PROBE PASSED[/bold green]")


@source_app.command("audit-deterministic-replay-specs")
def audit_deterministic_replay_specs_command() -> None:
    """Build checksum-pinned deterministic replay specifications."""
    import json

    from cre_foundry.deterministic_replay_spec import (
        build_deterministic_replay_spec,
    )

    report = build_deterministic_replay_spec(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["model_version"],
        "specification_count": report["specification_count"],
        "replay_ready_count": report["replay_ready_count"],
        "blocked_count": report["blocked_count"],
        "duplicate_replay_id_count": report["duplicate_replay_id_count"],
        "artifact_copy_execution_count": 0,
        "parser_execution_count": 0,
        "row_materialization_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DETERMINISTIC REPLAY SPEC PASSED[/bold green]")


@source_app.command("audit-snapshot-registration-preflight")
def audit_snapshot_registration_preflight_command() -> None:
    """Exercise snapshot registration only on an ephemeral DB clone."""
    import json

    from cre_foundry.snapshot_registration_preflight import (
        build_snapshot_registration_preflight,
    )

    report = build_snapshot_registration_preflight(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["model_version"],
        "preflight_status": report["preflight_status"],
        "selected_source_id": report["selected_source_id"],
        "temporally_eligible_candidate_count": report["temporally_eligible_candidate_count"],
        "authoritative_database_unchanged": report["authoritative_database_unchanged"],
        "unmapped_snapshot_columns": report["unmapped_snapshot_columns"],
        "unmapped_event_columns": report["unmapped_event_columns"],
        "ephemeral_transaction_attempt_count": report["ephemeral_transaction_attempt_count"],
        "ephemeral_transaction_verified": report["ephemeral_transaction_verified"],
        "authoritative_registration_execution_count": 0,
        "authoritative_event_insertion_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SNAPSHOT REGISTRATION PREFLIGHT PASSED[/bold green]")


@source_app.command("validate-source-parser-contracts")
def validate_source_parser_contracts_command() -> None:
    """Validate checksum-pinned source parsers twice."""
    import json

    from cre_foundry.source_parser_contracts import (
        build_source_parser_contracts,
    )

    result = build_source_parser_contracts(
        project_root(),
        write_contracts=True,
    )

    report = result["validation"]

    summary = {
        "model_version": report["model_version"],
        "contract_count": report["contract_count"],
        "validation_complete_count": report["validation_complete_count"],
        "reproducibility_match_count": report["reproducibility_match_count"],
        "parser_execution_count": report["parser_execution_count"],
        "parser_contract_approval_count": 0,
        "schema_contract_approval_count": 0,
        "warehouse_write_count": 0,
        "operations_database_write_count": 0,
        "snapshot_registration_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE PARSER CONTRACT VALIDATION PASSED[/bold green]")


@source_app.command("audit-source-parser-isolation")
def audit_source_parser_isolation_command() -> None:
    """Prove source parsers cannot access project databases."""
    import json

    from cre_foundry.source_parser_isolation import (
        build_source_parser_isolation,
    )

    report = build_source_parser_isolation(
        project_root(),
        write_contracts=True,
    )

    summary = {
        "model_version": report["model_version"],
        "static_isolation_passed": report["static_scan"]["static_isolation_passed"],
        "artifact_boundary_passed": report["artifact_boundary_scan"]["artifact_boundary_passed"],
        "runtime_guard_passed": report["runtime_guard_passed"],
        "validated_contract_count": report["validated_contract_count"],
        "reproducibility_match_count": report["reproducibility_match_count"],
        "guarded_parser_execution_count": report["guarded_parser_execution_count"],
        "authoritative_database_connection_count": 0,
        "authoritative_database_write_count": 0,
        "snapshot_registration_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SOURCE PARSER ISOLATION PASSED[/bold green]")


@app.command("build-learning-capture-design")
def build_learning_capture_design_command() -> None:
    """Build history, outcome and pilot capture contracts."""
    import json

    from cre_foundry.learning_capture_design import (
        build_learning_capture_design,
    )

    result = build_learning_capture_design(
        project_root(),
        write_contracts=True,
    )

    summary = result["summary"]

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]LEARNING CAPTURE DESIGN PASSED[/bold green]")


@app.command("build-governance-activation-design")
def build_governance_activation_design_command() -> None:
    """Build approval packets and disabled activation requests."""
    import json

    from cre_foundry.governance_activation_design import (
        build_governance_activation_design,
    )

    result = build_governance_activation_design(
        project_root(),
        write_contracts=True,
    )

    summary = result["summary"]

    console.print_json(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]GOVERNANCE ACTIVATION DESIGN PASSED[/bold green]")


@app.command("build-manual-activation-envelopes")
def build_manual_activation_envelopes_command() -> None:
    """Validate human decisions and build disabled envelopes."""
    import json

    from cre_foundry.manual_activation_envelopes import (
        build_manual_activation_envelopes,
    )

    result = build_manual_activation_envelopes(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]MANUAL ACTIVATION ENVELOPES PASSED[/bold green]")


@app.command("build-human-input-workbench")
def build_human_input_workbench_command() -> None:
    """Build reviewer and client input workbooks."""
    import json

    from cre_foundry.human_input_workbench import (
        build_human_input_workbench,
    )

    result = build_human_input_workbench(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]HUMAN INPUT WORKBENCH PASSED[/bold green]")


@app.command("build-assurance-mesh")
def build_assurance_mesh_command() -> None:
    """Build layered integrity and gate assurance."""
    import json

    from cre_foundry.assurance_mesh import (
        build_assurance_mesh,
    )

    result = build_assurance_mesh(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ASSURANCE MESH PASSED[/bold green]")


@app.command("build-activation-state-model")
def build_activation_state_model_command() -> None:
    """Exhaustively model-check activation gates."""
    import json

    from cre_foundry.activation_state_model import (
        build_activation_state_model,
    )

    result = build_activation_state_model(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]ACTIVATION STATE MODEL PASSED[/bold green]")


@app.command("build-contract-resilience-audit")
def build_contract_resilience_audit_command() -> None:
    """Fuzz contracts and build the audit evidence spine."""
    import json

    from cre_foundry.contract_resilience_audit import (
        build_contract_resilience_audit,
    )

    result = build_contract_resilience_audit(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]CONTRACT RESILIENCE AUDIT PASSED[/bold green]")


@app.command("build-devsecops-scanner-control-plane")
def build_devsecops_scanner_control_plane_command() -> None:
    """Normalize and govern DevSecOps scanner findings."""
    import json

    from cre_foundry.devsecops_scanner_control_plane import (
        build_devsecops_scanner_control_plane,
    )

    result = build_devsecops_scanner_control_plane(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]DEVSECOPS SCANNER CONTROL PLANE PASSED[/bold green]")


@app.command("build-sql-safety-remediation-inventory")
def build_sql_safety_remediation_inventory_command() -> None:
    """Inventory every blocking dynamic-SQL finding."""
    import json

    from cre_foundry.sql_safety_remediation_inventory import (
        build_sql_safety_remediation_inventory,
    )

    result = build_sql_safety_remediation_inventory(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result["summary"],
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SQL SAFETY REMEDIATION INVENTORY PASSED[/bold green]")


@app.command("build-security-blocker-ratchet")
def build_security_blocker_ratchet_command() -> None:
    """Compare blocking findings against the temporary baseline."""
    import json

    from cre_foundry.security_blocker_ratchet import (
        build_security_blocker_ratchet,
    )

    result = build_security_blocker_ratchet(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SECURITY BLOCKER RATCHET BUILT[/bold green]")


@app.command("build-sql-safety-primitives-report")
def build_sql_safety_primitives_report_command() -> None:
    """Validate strict SQL identifier primitives."""
    import json

    from cre_foundry.sql_safety import (
        build_sql_safety_primitives_report,
    )

    result = build_sql_safety_primitives_report(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SQL SAFETY PRIMITIVES PASSED[/bold green]")


@app.command("build-sql-safety-wave1a-plan")
def build_sql_safety_wave1a_plan_command() -> None:
    """Build the parameter-aware SQL migration queue."""
    import json

    from cre_foundry.sql_safety_wave1a_planner import (
        build_sql_safety_wave1a_plan,
    )

    result = build_sql_safety_wave1a_plan(
        project_root(),
        write_contracts=True,
    )

    console.print_json(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    console.print("[bold green]SQL SAFETY WAVE 1A PLAN PASSED[/bold green]")
