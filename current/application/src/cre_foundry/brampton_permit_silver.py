from __future__ import annotations

import gzip
import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import orjson

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path
from cre_foundry.permit_signals import (
    classify_permit_signal,
)

APPROVED_CATEGORIES = {
    "F1: Industrial",
    "F2: Industrial",
    "F3: Industrial",
}


def latest_permit_manifest(
    project_root: Path,
) -> Path:
    manifests = sorted(
        project_root.glob("data/bronze/brampton_building_permits/*/*/*/*/manifest.json"),
        key=lambda path: path.stat().st_mtime_ns,
    )

    if not manifests:
        raise RuntimeError("No Brampton permit manifest found.")

    latest = manifests[-1]
    payload = json.loads(latest.read_text(encoding="utf-8"))

    if payload.get("status") != "succeeded":
        raise RuntimeError("Latest Brampton permit run did not succeed.")

    return latest


def _arcgis_datetime(
    value: object,
) -> datetime | None:
    if value is None:
        return None

    try:
        milliseconds = float(str(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid ArcGIS date value: {value!r}") from exc

    return datetime.fromtimestamp(
        milliseconds / 1000,
        tz=UTC,
    )


def _optional_integer(
    value: object,
) -> int | None:
    if value is None:
        return None

    try:
        return int(float(str(value)))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid integer value: {value!r}") from exc


def _optional_float(
    value: object,
) -> float | None:
    if value is None:
        return None

    try:
        normalized = str(value).strip().replace(",", "")

        if not normalized:
            return None

        return float(normalized)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid numeric value: {value!r}") from exc


def _optional_text(
    value: object,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_permit_silver(
    project_root: Path,
) -> dict[str, Any]:
    manifest_path = latest_permit_manifest(project_root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    snapshots = manifest.get("layer_snapshots", [])

    if len(snapshots) != 1:
        raise RuntimeError("Expected exactly one permit snapshot.")

    snapshot = snapshots[0]

    if snapshot.get("layer_id") != 0:
        raise RuntimeError("Unexpected permit layer in manifest.")

    raw_path = project_root / str(snapshot["raw_path"])

    with gzip.open(raw_path, "rb") as handle:
        raw_bytes = handle.read()

    actual_raw_hash = hashlib.sha256(raw_bytes).hexdigest()

    if actual_raw_hash != snapshot["sha256"]:
        raise RuntimeError("Permit snapshot hash mismatch.")

    collection = orjson.loads(raw_bytes)
    features = collection.get("features")

    if not isinstance(features, list):
        raise RuntimeError("Permit snapshot has no feature list.")

    as_of = datetime.fromisoformat(manifest["as_of_timestamp"])

    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)

    as_of = as_of.astimezone(UTC)

    rows: list[tuple[Any, ...]] = []
    object_ids: list[int] = []
    permit_numbers: list[str] = []
    folder_ids: list[int] = []

    category_counts: Counter[str] = Counter()
    lifecycle_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()

    null_application_dates = 0
    unknown_lifecycle_records = 0

    for feature in features:
        if not isinstance(feature, dict):
            raise RuntimeError("Invalid permit feature.")

        properties = feature.get("properties")
        geometry = feature.get("geometry")

        if not isinstance(properties, dict):
            raise RuntimeError("Permit feature has no properties.")

        category = _optional_text(properties.get("SUBDESC"))

        if category not in APPROVED_CATEGORIES:
            raise RuntimeError(f"Permit silver received an unapproved category: {category!r}")

        object_id = _optional_integer(properties.get("OBJECTID"))
        folder_rsn = _optional_integer(properties.get("FOLDERRSN"))
        permit_number = _optional_text(properties.get("PERMITNUMBER"))

        if object_id is None:
            raise RuntimeError("Permit record has no OBJECTID.")

        if folder_rsn is None:
            raise RuntimeError("Permit record has no FOLDERRSN.")

        if permit_number is None:
            raise RuntimeError("Permit record has no permit number.")

        work_description = _optional_text(properties.get("WORKDESC"))
        status = _optional_text(properties.get("STATUSDESC"))

        classification = classify_permit_signal(
            permit_number=permit_number,
            work_description=work_description,
            status=status,
        )

        application_at = _arcgis_datetime(properties.get("INDATE"))

        if application_at is None:
            null_application_dates += 1

        if classification.lifecycle_stage == "unknown":
            unknown_lifecycle_records += 1

        longitude: float | None = None
        latitude: float | None = None

        if isinstance(geometry, dict):
            coordinates = geometry.get("coordinates")

            if isinstance(coordinates, list) and len(coordinates) >= 2:
                longitude = _optional_float(coordinates[0])
                latitude = _optional_float(coordinates[1])

        category_counts[category] += 1
        lifecycle_counts[classification.lifecycle_stage] += 1
        event_counts[classification.event_type] += 1

        object_ids.append(object_id)
        permit_numbers.append(permit_number)
        folder_ids.append(folder_rsn)

        rows.append(
            (
                "brampton_building_permits",
                str(manifest["run_id"]),
                str(snapshot["sha256"]),
                (f"brampton_building_permits:{object_id}"),
                object_id,
                _optional_float(properties.get("GIS_ID")),
                folder_rsn,
                permit_number,
                "brampton",
                _optional_text(properties.get("ADDRESS")),
                category,
                work_description,
                status,
                classification.lifecycle_stage,
                classification.event_type,
                classification.signal_strength,
                classification.is_revision,
                classification.signal_candidate,
                False,
                application_at,
                _arcgis_datetime(properties.get("ISSUEDATE")),
                _arcgis_datetime(properties.get("PROCESSDATE")),
                _arcgis_datetime(properties.get("EXPIRYDATE")),
                as_of,
                _optional_text(properties.get("BUILDER")),
                _optional_text(properties.get("CONTRACTOR")),
                _optional_float(properties.get("GFA")),
                longitude,
                latitude,
            )
        )

    if len(set(object_ids)) != len(rows):
        raise RuntimeError("Permit OBJECTID values are not unique.")

    if len(set(permit_numbers)) != len(rows):
        raise RuntimeError("Permit numbers are not unique.")

    if len(set(folder_ids)) != len(rows):
        raise RuntimeError("Permit FOLDERRSN values are not unique.")

    if unknown_lifecycle_records != 0:
        raise RuntimeError(
            f"Permit silver contains unknown lifecycle states: {unknown_lifecycle_records}"
        )

    date_path = as_of.astimezone(UTC)

    relative_parquet = (
        Path("data")
        / "silver"
        / "brampton_building_permits"
        / f"{date_path.year:04d}"
        / f"{date_path.month:02d}"
        / f"{date_path.day:02d}"
        / str(manifest["run_id"])
        / "silver-v1"
        / "industrial_permits.parquet"
    )

    parquet_path = project_root / relative_parquet

    parquet_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = parquet_path.with_name(f".{parquet_path.name}.tmp")

    temporary_path.unlink(missing_ok=True)

    staging = duckdb.connect(":memory:")

    try:
        staging.execute(
            """
            CREATE TABLE permit_rows (
                source_id VARCHAR,
                run_id VARCHAR,
                source_snapshot_sha256 VARCHAR,
                source_record_id VARCHAR,
                object_id BIGINT,
                gis_id DOUBLE,
                folder_rsn BIGINT,
                permit_number VARCHAR,
                municipality VARCHAR,
                address_raw VARCHAR,
                subdescription VARCHAR,
                work_description VARCHAR,
                status_raw VARCHAR,
                lifecycle_stage VARCHAR,
                event_type VARCHAR,
                signal_strength VARCHAR,
                is_revision BOOLEAN,
                signal_candidate BOOLEAN,
                outreach_eligible BOOLEAN,
                application_at_utc TIMESTAMPTZ,
                issue_at_utc TIMESTAMPTZ,
                process_at_utc TIMESTAMPTZ,
                expiry_at_utc TIMESTAMPTZ,
                as_of_timestamp TIMESTAMPTZ,
                builder VARCHAR,
                contractor VARCHAR,
                gfa DOUBLE,
                longitude DOUBLE,
                latitude DOUBLE
            )
            """
        )

        placeholders = ", ".join(["?"] * 29)

        staging.executemany(
            f"""
            INSERT INTO permit_rows
            VALUES ({placeholders})
            """,
            rows,
        )

        staging.execute(
            f"""
            COPY permit_rows
            TO '{_sql_path(temporary_path)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )
    finally:
        staging.close()

    os.replace(
        temporary_path,
        parquet_path,
    )

    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(str(warehouse))

    try:
        connection.execute("BEGIN")

        connection.execute("CREATE SCHEMA IF NOT EXISTS silver")

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE
                silver.brampton_industrial_permits
            AS
            SELECT *
            FROM read_parquet(
                '{_sql_path(parquet_path)}'
            )
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_active_permit_signals
            AS
            SELECT
                *,
                date_diff(
                    'day',
                    application_at_utc,
                    as_of_timestamp
                ) AS signal_age_days
            FROM
                silver.brampton_industrial_permits
            WHERE
                signal_candidate
                AND application_at_utc IS NOT NULL
                AND application_at_utc
                    >= as_of_timestamp
                    - INTERVAL '90 days'
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_signal_summary
            AS
            SELECT
                lifecycle_stage,
                event_type,
                signal_strength,
                count(*) AS records,
                count(*) FILTER (
                    WHERE signal_candidate
                ) AS signal_candidates
            FROM
                silver.brampton_industrial_permits
            GROUP BY
                lifecycle_stage,
                event_type,
                signal_strength
            """
        )

        warehouse_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_industrial_permits
            """,
        )

        active_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_active_permit_signals
            """,
        )

        outreach_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_industrial_permits
            WHERE outreach_eligible
            """,
        )

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    if warehouse_count != len(rows):
        raise RuntimeError("DuckDB permit count mismatch.")

    if outreach_count != 0:
        raise RuntimeError("Permit records became outreach-eligible.")

    report: dict[str, Any] = {
        "model_version": ("brampton-permit-silver-v1"),
        "source_id": ("brampton_building_permits"),
        "run_id": manifest["run_id"],
        "manifest_path": str(manifest_path.relative_to(project_root)),
        "source_snapshot_path": (snapshot["raw_path"]),
        "source_snapshot_sha256": (snapshot["sha256"]),
        "source_record_count": len(features),
        "silver_record_count": len(rows),
        "warehouse_record_count": (warehouse_count),
        "active_90_day_signal_count": (active_signal_count),
        "null_application_date_count": (null_application_dates),
        "unknown_lifecycle_count": (unknown_lifecycle_records),
        "outreach_eligible_count": (outreach_count),
        "category_distribution": dict(sorted(category_counts.items())),
        "lifecycle_distribution": dict(sorted(lifecycle_counts.items())),
        "event_distribution": dict(sorted(event_counts.items())),
        "parquet_path": str(relative_parquet),
        "parquet_sha256": _sha256_file(parquet_path),
        "warehouse_path": str(warehouse.relative_to(project_root)),
        "table": ("silver.brampton_industrial_permits"),
        "active_signal_view": ("silver.brampton_active_permit_signals"),
        "summary_view": ("silver.brampton_permit_signal_summary"),
        "policy": {
            "active_window_days": 90,
            "approved_categories": sorted(APPROVED_CATEGORIES),
            "outreach_eligible": False,
        },
    }

    contract_path = project_root / "docs" / "data_contracts" / "brampton_permit_silver.json"

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
