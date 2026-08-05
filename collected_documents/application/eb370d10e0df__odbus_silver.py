from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import unicodedata
import zipfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import duckdb
import polars as pl

from cre_foundry.bulk_storage import (
    sha256_file,
    write_json_atomic,
)
from cre_foundry.odbus_schema import (
    _select_members,
    _text_settings,
    latest_odbus_manifest,
)

SOURCE_ID = "statscan_odbus_2023"
TRANSFORMATION_VERSION = "silver-v1"
TARGET_MUNICIPALITIES = {
    "brampton",
    "mississauga",
}

NULL_TOKENS = {
    "",
    "..",
    "NOT AVAILABLE",
}

SOURCE_COLUMNS = {
    "idx",
    "business_name",
    "alt_business_name",
    "business_sector",
    "business_subsector",
    "business_description",
    "business_id_no",
    "licence_number",
    "licence_type",
    "derived_NAICS",
    "source_NAICS_primary",
    "source_NAICS_secondary",
    "NAICS_descr",
    "NAICS_descr2",
    "latitude",
    "longitude",
    "full_address",
    "postal_code",
    "unit",
    "street_no",
    "street_name",
    "street_direction",
    "street_type",
    "city",
    "prov_terr",
    "total_no_employees",
    "status",
    "provider",
    "geo_source",
    "CSDUID",
    "CSDNAME",
    "PRUID",
}

EXACT_INTEGER_PATTERN = re.compile(r"^\d+$")
RANGE_PATTERN = re.compile(
    r"^(\d+)\s*(?:--|to|-)\s*(\d+)$",
    flags=re.IGNORECASE,
)
LOWER_BOUND_PATTERN = re.compile(r"^(\d+)\s*\+$")

SILVER_SCHEMA = {
    "source_id": pl.String,
    "source_record_id": pl.String,
    "source_row_number": pl.Int64,
    "entity_fingerprint": pl.String,
    "business_name": pl.String,
    "alternate_business_name": pl.String,
    "business_sector": pl.String,
    "business_subsector": pl.String,
    "business_description": pl.String,
    "business_id_number": pl.String,
    "licence_number": pl.String,
    "licence_type": pl.String,
    "naics_2d": pl.String,
    "naics_primary": pl.String,
    "naics_secondary_raw": pl.String,
    "naics_description": pl.String,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "coordinate_quality": pl.String,
    "full_address": pl.String,
    "postal_code": pl.String,
    "unit": pl.String,
    "street_number": pl.String,
    "street_name": pl.String,
    "street_direction": pl.String,
    "street_type": pl.String,
    "city_raw": pl.String,
    "csd_name_raw": pl.String,
    "municipality": pl.String,
    "municipality_resolution": pl.String,
    "province_code": pl.String,
    "pruid": pl.String,
    "pruid_ontario_match": pl.Boolean,
    "csduid": pl.String,
    "employee_count_raw": pl.String,
    "employee_count_min": pl.Int64,
    "employee_count_max": pl.Int64,
    "employee_count_method": pl.String,
    "source_status_raw": pl.String,
    "status_normalized": pl.String,
    "provider": pl.String,
    "geo_source": pl.String,
    "current_status_verified": pl.Boolean,
    "source_vintage_start": pl.String,
    "source_vintage_end": pl.String,
    "source_release_date": pl.String,
    "source_archive_sha256": pl.String,
    "bronze_run_id": pl.String,
}

QUARANTINE_SCHEMA = {
    "source_id": pl.String,
    "source_record_id": pl.String,
    "source_row_number": pl.Int64,
    "business_name": pl.String,
    "city_raw": pl.String,
    "csd_name_raw": pl.String,
    "province_code": pl.String,
    "pruid": pl.String,
    "full_address": pl.String,
    "postal_code": pl.String,
    "reason": pl.String,
    "source_archive_sha256": pl.String,
    "bronze_run_id": pl.String,
}


def normalize_text(
    value: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKC",
        value,
    )

    return " ".join(normalized.strip().split())


def canonical_key(
    value: str,
) -> str:
    return normalize_text(value).casefold()


def clean_value(
    value: object,
) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = normalize_text(value)

    if normalized.upper() in NULL_TOKENS:
        return None

    return normalized


def clean_code(
    value: object,
    *,
    minimum_length: int,
    maximum_length: int,
) -> str | None:
    normalized = clean_value(value)

    if normalized is None:
        return None

    if normalized.isdigit() and minimum_length <= len(normalized) <= maximum_length:
        return normalized

    return None


def clean_postal_code(
    value: object,
) -> str | None:
    normalized = clean_value(value)

    if normalized is None:
        return None

    compact = re.sub(
        r"\s+",
        "",
        normalized.upper(),
    )

    if re.fullmatch(
        r"[A-Z]\d[A-Z]\d[A-Z]\d",
        compact,
    ):
        return compact

    return normalized.upper()


def parse_coordinate(
    value: object,
    *,
    lower: float,
    upper: float,
) -> tuple[float | None, str]:
    normalized = clean_value(value)

    if normalized is None:
        return None, "missing"

    try:
        parsed = float(normalized)
    except ValueError:
        return None, "invalid"

    if not lower <= parsed <= upper:
        return None, "out_of_range"

    return parsed, "valid"


def coordinate_quality(
    latitude_state: str,
    longitude_state: str,
) -> str:
    if latitude_state == "valid" and longitude_state == "valid":
        return "valid"

    if latitude_state == "missing" and longitude_state == "missing":
        return "missing"

    if "invalid" in {
        latitude_state,
        longitude_state,
    }:
        return "invalid"

    if "out_of_range" in {
        latitude_state,
        longitude_state,
    }:
        return "out_of_range"

    return "partial"


def parse_employee_count(
    value: object,
) -> dict[str, Any]:
    normalized = clean_value(value)

    if normalized is None:
        return {
            "raw": None,
            "minimum": None,
            "maximum": None,
            "method": "unknown",
        }

    compact = normalized.replace(
        ",",
        "",
    )

    if EXACT_INTEGER_PATTERN.fullmatch(compact):
        parsed = int(compact)

        return {
            "raw": normalized,
            "minimum": parsed,
            "maximum": parsed,
            "method": "exact",
        }

    range_match = RANGE_PATTERN.fullmatch(compact)

    if range_match:
        minimum = int(range_match.group(1))
        maximum = int(range_match.group(2))

        if minimum <= maximum:
            return {
                "raw": normalized,
                "minimum": minimum,
                "maximum": maximum,
                "method": "range",
            }

    lower_match = LOWER_BOUND_PATTERN.fullmatch(compact)

    if lower_match:
        return {
            "raw": normalized,
            "minimum": int(lower_match.group(1)),
            "maximum": None,
            "method": "lower_bound",
        }

    return {
        "raw": normalized,
        "minimum": None,
        "maximum": None,
        "method": "unparsed",
    }


def normalize_status(
    value: object,
) -> tuple[str | None, str]:
    raw = clean_value(value)

    if raw is None:
        return None, "unknown"

    key = canonical_key(raw)

    mapping = {
        "active": "active",
        "pending": "pending",
        "not active": "not_active",
    }

    return raw, mapping.get(
        key,
        "other",
    )


def resolve_target_municipality(
    *,
    city: object,
    csd_name: object,
) -> tuple[str | None, str]:
    city_raw = clean_value(city)
    csd_raw = clean_value(csd_name)

    city_key = canonical_key(city_raw) if city_raw is not None else ""

    csd_key = canonical_key(csd_raw) if csd_raw is not None else ""

    city_target = city_key if city_key in TARGET_MUNICIPALITIES else None

    csd_target = csd_key if csd_key in TARGET_MUNICIPALITIES else None

    if city_target is not None and csd_target is not None and city_target != csd_target:
        return None, "conflict"

    if csd_target is not None:
        return csd_target, "csd"

    if city_target is not None:
        return city_target, "city_fallback"

    return None, "not_target"


def _load_json(
    path: Path,
) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return cast(
        dict[str, Any],
        payload,
    )


def _row_value(
    row: Mapping[str, object],
    key: str,
) -> object:
    return row.get(key)


def _fingerprint(
    *values: str | None,
) -> str:
    payload = "|".join(canonical_key(value) if value is not None else "" for value in values)

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_record_id(
    *,
    raw_idx: object,
    row_number: int,
) -> str:
    idx = clean_value(raw_idx)

    if idx is not None:
        return idx

    return f"row-{row_number:09d}"


def _pruid_match(
    value: object,
) -> bool | None:
    pruid = clean_value(value)

    if pruid is None:
        return None

    return pruid == "35"


def _frame_from_rows(
    rows: list[dict[str, Any]],
    *,
    schema: Mapping[str, Any],
) -> pl.DataFrame:
    if rows:
        return pl.DataFrame(
            rows,
            schema=schema,
            strict=False,
        )

    return pl.DataFrame(schema=schema)


def _latest_warehouse(
    project_root: Path,
) -> Path:
    warehouse_directory = project_root / "data" / "warehouse"

    warehouse_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidates = sorted(warehouse_directory.glob("*.duckdb"))

    if len(candidates) > 1:
        raise RuntimeError(f"Multiple DuckDB warehouse files exist: {candidates}")

    if candidates:
        return candidates[0]

    return warehouse_directory / "cre_foundry.duckdb"


def _sql_literal(
    value: str,
) -> str:
    return (
        "'"
        + value.replace(
            "'",
            "''",
        )
        + "'"
    )


def load_silver_into_duckdb(
    *,
    project_root: Path,
    target_parquet_path: Path,
    conflicts_parquet_path: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    warehouse_path = _latest_warehouse(project_root)

    target_literal = _sql_literal(str(target_parquet_path))
    conflicts_literal = _sql_literal(str(conflicts_parquet_path))

    connection = duckdb.connect(str(warehouse_path))

    try:
        connection.execute("BEGIN TRANSACTION")

        connection.execute("CREATE SCHEMA IF NOT EXISTS silver")
        connection.execute("CREATE SCHEMA IF NOT EXISTS quarantine")
        connection.execute("CREATE SCHEMA IF NOT EXISTS meta")

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE
                silver.odbus_target_businesses
            AS
            SELECT *
            FROM read_parquet({target_literal})
            """
        )

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE
                quarantine.odbus_target_conflicts
            AS
            SELECT *
            FROM read_parquet({conflicts_literal})
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.odbus_target_summary
            AS
            SELECT
                municipality,
                naics_2d,
                status_normalized,
                count(*) AS business_records
            FROM silver.odbus_target_businesses
            GROUP BY
                municipality,
                naics_2d,
                status_normalized
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
                meta.dataset_registry
            (
                dataset_id VARCHAR PRIMARY KEY,
                source_id VARCHAR NOT NULL,
                transformation_version VARCHAR NOT NULL,
                bronze_run_id VARCHAR NOT NULL,
                archive_sha256 VARCHAR NOT NULL,
                parquet_path VARCHAR NOT NULL,
                record_count BIGINT NOT NULL,
                manifest_path VARCHAR NOT NULL
            )
            """
        )

        connection.execute(
            """
            DELETE FROM meta.dataset_registry
            WHERE dataset_id = ?
            """,
            ["statscan_odbus_target_market"],
        )

        connection.execute(
            """
            INSERT INTO meta.dataset_registry
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "statscan_odbus_target_market",
                SOURCE_ID,
                TRANSFORMATION_VERSION,
                report["bronze_run_id"],
                report["source_archive_sha256"],
                report["target_parquet_path"],
                report["silver_row_count"],
                report["transformation_manifest_path"],
            ],
        )

        target_count = connection.execute(
            """
            SELECT count(*)
            FROM silver.odbus_target_businesses
            """
        ).fetchone()

        conflict_count = connection.execute(
            """
            SELECT count(*)
            FROM quarantine.odbus_target_conflicts
            """
        ).fetchone()

        loaded_target_count = int(target_count[0]) if target_count is not None else -1

        loaded_conflict_count = int(conflict_count[0]) if conflict_count is not None else -1

        if loaded_target_count != report["silver_row_count"]:
            raise RuntimeError("DuckDB target count does not match the silver manifest.")

        if loaded_conflict_count != report["quarantined_conflict_count"]:
            raise RuntimeError("DuckDB quarantine count does not match the silver manifest.")

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    return {
        "warehouse_path": str(warehouse_path.relative_to(project_root)),
        "duckdb_target_count": (loaded_target_count),
        "duckdb_conflict_count": (loaded_conflict_count),
        "target_table": ("silver.odbus_target_businesses"),
        "conflict_table": ("quarantine.odbus_target_conflicts"),
        "summary_view": ("silver.odbus_target_summary"),
    }


def build_latest_odbus_silver(
    project_root: Path,
) -> dict[str, Any]:
    manifest_path = latest_odbus_manifest(project_root)

    bronze_manifest = _load_json(manifest_path)

    raw_archive_path = bronze_manifest.get("archive_path")
    expected_hash = bronze_manifest.get("archive_sha256")

    if not isinstance(
        raw_archive_path,
        str,
    ):
        raise RuntimeError("Bronze manifest archive_path is invalid.")

    if not isinstance(
        expected_hash,
        str,
    ):
        raise RuntimeError("Bronze manifest archive_sha256 is invalid.")

    archive_path = project_root / raw_archive_path

    actual_hash = sha256_file(archive_path)

    if actual_hash != expected_hash:
        raise RuntimeError("Bronze archive hash does not match.")

    bronze_run_id = manifest_path.parent.name

    silver_directory = (
        project_root / "data" / "silver" / SOURCE_ID / bronze_run_id / TRANSFORMATION_VERSION
    )

    quarantine_directory = (
        project_root / "data" / "quarantine" / SOURCE_ID / bronze_run_id / TRANSFORMATION_VERSION
    )

    transformation_manifest_path = silver_directory / "manifest.json"

    target_parquet_path = silver_directory / "target_market.parquet"

    conflicts_parquet_path = quarantine_directory / "target_market_conflicts.parquet"

    if transformation_manifest_path.exists():
        report = _load_json(transformation_manifest_path)

        if report.get("source_archive_sha256") != actual_hash:
            raise RuntimeError("Existing silver output belongs to another bronze archive.")

        if not target_parquet_path.exists():
            raise RuntimeError("Existing silver manifest has no target Parquet file.")

        if not conflicts_parquet_path.exists():
            raise RuntimeError("Existing silver manifest has no quarantine Parquet file.")

        report["reused_existing"] = True

        report.update(
            load_silver_into_duckdb(
                project_root=project_root,
                target_parquet_path=(target_parquet_path),
                conflicts_parquet_path=(conflicts_parquet_path),
                report=report,
            )
        )

        return report

    temporary_root = (
        project_root / "data" / "control" / "tmp" / (f"odbus-silver-{bronze_run_id}-{os.getpid()}")
    )

    if temporary_root.exists():
        shutil.rmtree(temporary_root)

    temporary_silver = temporary_root / "silver"

    temporary_quarantine = temporary_root / "quarantine"

    temporary_silver.mkdir(parents=True)
    temporary_quarantine.mkdir(parents=True)

    source_row_count = 0
    ontario_row_count = 0
    target_candidate_count = 0
    conflict_count = 0
    pruid_unknown_count = 0
    invalid_coordinate_count = 0
    employee_unparsed_count = 0

    municipality_counts: Counter[str] = Counter()
    municipality_resolution_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    target_rows: list[dict[str, Any]] = []

    conflict_rows: list[dict[str, Any]] = []

    try:
        with zipfile.ZipFile(
            archive_path,
            mode="r",
        ) as archive:
            data_member, _ = _select_members(archive)

            encoding, delimiter = _text_settings(
                archive,
                data_member,
            )

            with (
                archive.open(
                    data_member,
                    mode="r",
                ) as binary_handle,
                io.TextIOWrapper(
                    binary_handle,
                    encoding=encoding,
                    newline="",
                ) as text_handle,
            ):
                reader = csv.DictReader(
                    text_handle,
                    delimiter=delimiter,
                )

                if reader.fieldnames is None:
                    raise RuntimeError("ODBus CSV has no header.")

                observed_columns = {
                    field.strip() for field in reader.fieldnames if field is not None
                }

                missing_columns = SOURCE_COLUMNS.difference(observed_columns)

                if missing_columns:
                    raise RuntimeError(
                        f"ODBus CSV is missing required columns: {sorted(missing_columns)}"
                    )

                for row_number, row in enumerate(
                    reader,
                    start=1,
                ):
                    source_row_count += 1

                    province = clean_value(
                        _row_value(
                            row,
                            "prov_terr",
                        )
                    )

                    province_code = province.upper() if province is not None else None

                    if province_code != "ON":
                        continue

                    ontario_row_count += 1

                    municipality, resolution = resolve_target_municipality(
                        city=_row_value(
                            row,
                            "city",
                        ),
                        csd_name=_row_value(
                            row,
                            "CSDNAME",
                        ),
                    )

                    if resolution == "not_target":
                        continue

                    target_candidate_count += 1

                    source_record_id = _source_record_id(
                        raw_idx=_row_value(
                            row,
                            "idx",
                        ),
                        row_number=row_number,
                    )

                    business_name = clean_value(
                        _row_value(
                            row,
                            "business_name",
                        )
                    )

                    city_raw = clean_value(
                        _row_value(
                            row,
                            "city",
                        )
                    )

                    csd_name_raw = clean_value(
                        _row_value(
                            row,
                            "CSDNAME",
                        )
                    )

                    pruid = clean_value(
                        _row_value(
                            row,
                            "PRUID",
                        )
                    )

                    full_address = clean_value(
                        _row_value(
                            row,
                            "full_address",
                        )
                    )

                    postal_code = clean_postal_code(
                        _row_value(
                            row,
                            "postal_code",
                        )
                    )

                    if resolution == "conflict":
                        conflict_count += 1

                        conflict_rows.append(
                            {
                                "source_id": SOURCE_ID,
                                "source_record_id": (source_record_id),
                                "source_row_number": (row_number),
                                "business_name": (business_name),
                                "city_raw": city_raw,
                                "csd_name_raw": (csd_name_raw),
                                "province_code": (province_code),
                                "pruid": pruid,
                                "full_address": (full_address),
                                "postal_code": (postal_code),
                                "reason": ("target_city_csd_conflict"),
                                "source_archive_sha256": (actual_hash),
                                "bronze_run_id": (bronze_run_id),
                            }
                        )

                        continue

                    if municipality is None:
                        raise RuntimeError("Resolved target municipality is unexpectedly null.")

                    latitude, latitude_state = parse_coordinate(
                        _row_value(
                            row,
                            "latitude",
                        ),
                        lower=-90,
                        upper=90,
                    )

                    longitude, longitude_state = parse_coordinate(
                        _row_value(
                            row,
                            "longitude",
                        ),
                        lower=-180,
                        upper=180,
                    )

                    coordinate_state = coordinate_quality(
                        latitude_state,
                        longitude_state,
                    )

                    if coordinate_state not in {
                        "valid",
                        "missing",
                    }:
                        invalid_coordinate_count += 1

                    employees = parse_employee_count(
                        _row_value(
                            row,
                            "total_no_employees",
                        )
                    )

                    if employees["method"] in {
                        "unknown",
                        "unparsed",
                    }:
                        employee_unparsed_count += 1

                    status_raw, status_normalized = normalize_status(
                        _row_value(
                            row,
                            "status",
                        )
                    )

                    pruid_match = _pruid_match(
                        _row_value(
                            row,
                            "PRUID",
                        )
                    )

                    if pruid_match is None:
                        pruid_unknown_count += 1

                    alternate_name = clean_value(
                        _row_value(
                            row,
                            "alt_business_name",
                        )
                    )

                    street_number = clean_value(
                        _row_value(
                            row,
                            "street_no",
                        )
                    )

                    street_name = clean_value(
                        _row_value(
                            row,
                            "street_name",
                        )
                    )

                    entity_fingerprint = _fingerprint(
                        business_name,
                        alternate_name,
                        postal_code,
                        street_number,
                        street_name,
                        municipality,
                    )

                    municipality_counts[municipality] += 1

                    municipality_resolution_counts[resolution] += 1

                    status_counts[status_normalized] += 1

                    target_rows.append(
                        {
                            "source_id": SOURCE_ID,
                            "source_record_id": (source_record_id),
                            "source_row_number": (row_number),
                            "entity_fingerprint": (entity_fingerprint),
                            "business_name": (business_name),
                            "alternate_business_name": (alternate_name),
                            "business_sector": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "business_sector",
                                    )
                                )
                            ),
                            "business_subsector": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "business_subsector",
                                    )
                                )
                            ),
                            "business_description": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "business_description",
                                    )
                                )
                            ),
                            "business_id_number": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "business_id_no",
                                    )
                                )
                            ),
                            "licence_number": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "licence_number",
                                    )
                                )
                            ),
                            "licence_type": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "licence_type",
                                    )
                                )
                            ),
                            "naics_2d": clean_code(
                                _row_value(
                                    row,
                                    "derived_NAICS",
                                ),
                                minimum_length=2,
                                maximum_length=2,
                            ),
                            "naics_primary": (
                                clean_code(
                                    _row_value(
                                        row,
                                        "source_NAICS_primary",
                                    ),
                                    minimum_length=2,
                                    maximum_length=6,
                                )
                            ),
                            "naics_secondary_raw": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "source_NAICS_secondary",
                                    )
                                )
                            ),
                            "naics_description": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "NAICS_descr",
                                    )
                                )
                            ),
                            "latitude": latitude,
                            "longitude": longitude,
                            "coordinate_quality": (coordinate_state),
                            "full_address": (full_address),
                            "postal_code": (postal_code),
                            "unit": clean_value(
                                _row_value(
                                    row,
                                    "unit",
                                )
                            ),
                            "street_number": (street_number),
                            "street_name": (street_name),
                            "street_direction": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "street_direction",
                                    )
                                )
                            ),
                            "street_type": (
                                clean_value(
                                    _row_value(
                                        row,
                                        "street_type",
                                    )
                                )
                            ),
                            "city_raw": city_raw,
                            "csd_name_raw": (csd_name_raw),
                            "municipality": (municipality),
                            "municipality_resolution": (resolution),
                            "province_code": (province_code),
                            "pruid": pruid,
                            "pruid_ontario_match": (pruid_match),
                            "csduid": clean_value(
                                _row_value(
                                    row,
                                    "CSDUID",
                                )
                            ),
                            "employee_count_raw": (employees["raw"]),
                            "employee_count_min": (employees["minimum"]),
                            "employee_count_max": (employees["maximum"]),
                            "employee_count_method": (employees["method"]),
                            "source_status_raw": (status_raw),
                            "status_normalized": (status_normalized),
                            "provider": clean_value(
                                _row_value(
                                    row,
                                    "provider",
                                )
                            ),
                            "geo_source": clean_value(
                                _row_value(
                                    row,
                                    "geo_source",
                                )
                            ),
                            "current_status_verified": (False),
                            "source_vintage_start": (
                                bronze_manifest.get(
                                    "vintage_start",
                                    "2022-05-01",
                                )
                            ),
                            "source_vintage_end": (
                                bronze_manifest.get(
                                    "vintage_end",
                                    "2022-12-31",
                                )
                            ),
                            "source_release_date": (
                                bronze_manifest.get(
                                    "release_date",
                                    "2023-11-28",
                                )
                            ),
                            "source_archive_sha256": (actual_hash),
                            "bronze_run_id": (bronze_run_id),
                        }
                    )

        target_frame = _frame_from_rows(
            target_rows,
            schema=SILVER_SCHEMA,
        ).sort(
            [
                "municipality",
                "business_name",
                "postal_code",
                "source_record_id",
            ],
            nulls_last=True,
        )

        conflict_frame = _frame_from_rows(
            conflict_rows,
            schema=QUARANTINE_SCHEMA,
        ).sort(
            [
                "business_name",
                "source_record_id",
            ],
            nulls_last=True,
        )

        temporary_target_path = temporary_silver / "target_market.parquet"

        temporary_conflict_path = temporary_quarantine / "target_market_conflicts.parquet"

        target_frame.write_parquet(
            temporary_target_path,
            compression="zstd",
            statistics=True,
        )

        conflict_frame.write_parquet(
            temporary_conflict_path,
            compression="zstd",
            statistics=True,
        )

        duplicate_fingerprint_count = (
            target_frame.height - target_frame["entity_fingerprint"].n_unique()
        )

        silver_directory.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        quarantine_directory.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        os.replace(
            temporary_silver,
            silver_directory,
        )

        os.replace(
            temporary_quarantine,
            quarantine_directory,
        )

        target_hash = sha256_file(target_parquet_path)

        conflict_hash = sha256_file(conflicts_parquet_path)

        report = {
            "source_id": SOURCE_ID,
            "transformation_version": (TRANSFORMATION_VERSION),
            "bronze_run_id": bronze_run_id,
            "source_manifest_path": str(manifest_path.relative_to(project_root)),
            "source_archive_path": (raw_archive_path),
            "source_archive_sha256": (actual_hash),
            "source_row_count": (source_row_count),
            "ontario_row_count": (ontario_row_count),
            "target_candidate_count": (target_candidate_count),
            "silver_row_count": (target_frame.height),
            "quarantined_conflict_count": (conflict_frame.height),
            "municipality_counts": dict(sorted(municipality_counts.items())),
            "municipality_resolution_counts": (
                dict(sorted(municipality_resolution_counts.items()))
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "pruid_unknown_count": (pruid_unknown_count),
            "invalid_coordinate_count": (invalid_coordinate_count),
            "employee_unparsed_count": (employee_unparsed_count),
            "duplicate_entity_fingerprint_count": (duplicate_fingerprint_count),
            "target_parquet_path": str(target_parquet_path.relative_to(project_root)),
            "target_parquet_sha256": (target_hash),
            "target_parquet_bytes": (target_parquet_path.stat().st_size),
            "conflicts_parquet_path": str(conflicts_parquet_path.relative_to(project_root)),
            "conflicts_parquet_sha256": (conflict_hash),
            "conflicts_parquet_bytes": (conflicts_parquet_path.stat().st_size),
            "transformation_manifest_path": (
                str(transformation_manifest_path.relative_to(project_root))
            ),
            "filter_policy": {
                "province_gate": ("normalized prov_terr equals ON"),
                "pruid_policy": ("validation only; missing PRUID does not exclude an Ontario row"),
                "municipality_policy": ("prefer target CSDNAME, then target city fallback"),
                "conflict_policy": (
                    "quarantine rows where target city and target CSDNAME disagree"
                ),
            },
            "current_status_verified": False,
            "reused_existing": False,
        }

        write_json_atomic(
            transformation_manifest_path,
            report,
        )

        report.update(
            load_silver_into_duckdb(
                project_root=project_root,
                target_parquet_path=(target_parquet_path),
                conflicts_parquet_path=(conflicts_parquet_path),
                report=report,
            )
        )

        return report

    except Exception:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)

        raise
