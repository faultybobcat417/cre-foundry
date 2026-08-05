from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from cre_foundry.bulk_storage import (
    sha256_file,
    write_json_atomic,
)
from cre_foundry.odbus_schema import (
    _select_members,
    _text_settings,
    latest_odbus_manifest,
)

INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
NAICS_PATTERN = re.compile(r"^\d{2,6}$")

REQUIRED_COLUMNS = {
    "business_name",
    "derived_NAICS",
    "source_NAICS_primary",
    "latitude",
    "longitude",
    "city",
    "prov_terr",
    "total_no_employees",
    "status",
    "provider",
    "geo_source",
    "CSDNAME",
    "PRUID",
}

TARGET_MUNICIPALITIES = {
    "brampton",
    "mississauga",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKC",
        value,
    )

    return " ".join(normalized.strip().split())


def canonical_key(value: str) -> str:
    return normalize_text(value).casefold()


def _cell(
    row: Mapping[str, object],
    key: str,
) -> str:
    value = row.get(key)

    if isinstance(value, str):
        return value

    return ""


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


def _counter_payload(
    counter: Counter[str],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return [
        {
            "value": value,
            "count": count,
        }
        for value, count in counter.most_common(limit)
    ]


def _add_example(
    examples: list[str],
    value: str,
    *,
    limit: int = 10,
) -> None:
    if value and value not in examples and len(examples) < limit:
        examples.append(value)


def _coordinate_state() -> dict[str, Any]:
    return {
        "blank_count": 0,
        "valid_count": 0,
        "invalid_count": 0,
        "out_of_range_count": 0,
        "invalid_examples": [],
        "out_of_range_examples": [],
    }


def _update_coordinate(
    state: dict[str, Any],
    raw_value: str,
    *,
    lower: float,
    upper: float,
) -> None:
    value = normalize_text(raw_value)

    if not value:
        state["blank_count"] += 1
        return

    try:
        parsed = float(value)
    except ValueError:
        state["invalid_count"] += 1
        _add_example(
            state["invalid_examples"],
            value,
        )
        return

    if not lower <= parsed <= upper:
        state["out_of_range_count"] += 1
        _add_example(
            state["out_of_range_examples"],
            value,
        )
        return

    state["valid_count"] += 1


def profile_latest_odbus_values(
    project_root: Path,
) -> dict[str, Any]:
    manifest_path = latest_odbus_manifest(project_root)

    manifest = _load_json(manifest_path)

    raw_archive_path = manifest.get("archive_path")
    expected_hash = manifest.get("archive_sha256")

    if not isinstance(
        raw_archive_path,
        str,
    ):
        raise RuntimeError("Manifest archive_path is invalid.")

    if not isinstance(
        expected_hash,
        str,
    ):
        raise RuntimeError("Manifest archive_sha256 is invalid.")

    archive_path = project_root / raw_archive_path

    actual_hash = sha256_file(archive_path)

    if actual_hash != expected_hash:
        raise RuntimeError("Bronze archive hash does not match its manifest.")

    province_counts: Counter[str] = Counter()
    pruid_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    geo_source_counts: Counter[str] = Counter()
    ontario_city_counts: Counter[str] = Counter()
    ontario_csd_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    employee_value_counts: Counter[str] = Counter()
    primary_naics_counts: Counter[str] = Counter()
    derived_naics_counts: Counter[str] = Counter()

    latitude_state = _coordinate_state()
    longitude_state = _coordinate_state()

    employee_integer_count = 0
    employee_non_integer_count = 0
    employee_blank_count = 0
    employee_non_integer_examples: list[str] = []

    primary_naics_valid_count = 0
    primary_naics_invalid_count = 0
    primary_naics_blank_count = 0
    primary_naics_invalid_examples: list[str] = []

    row_count = 0
    extra_field_rows = 0
    missing_business_name_rows = 0
    blank_province_rows = 0

    ontario_by_province_count = 0
    ontario_by_pruid_count = 0
    ontario_intersection_count = 0
    ontario_union_count = 0
    province_pruid_disagreement_count = 0

    target_city_exact_count = 0
    target_csd_exact_count = 0
    target_union_any_province_count = 0
    target_union_ontario_intersection_count = 0
    target_city_csd_conflict_count = 0

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

            fields = {field.strip() for field in reader.fieldnames if field is not None}

            missing_columns = REQUIRED_COLUMNS.difference(fields)

            if missing_columns:
                raise RuntimeError(
                    f"ODBus CSV is missing required columns: {sorted(missing_columns)}"
                )

            for row in reader:
                row_count += 1

                if None in row:
                    extra_field_rows += 1

                business_name = normalize_text(
                    _cell(
                        row,
                        "business_name",
                    )
                )

                if not business_name:
                    missing_business_name_rows += 1

                province = normalize_text(
                    _cell(
                        row,
                        "prov_terr",
                    )
                ).upper()

                pruid = normalize_text(
                    _cell(
                        row,
                        "PRUID",
                    )
                )

                province_counts[province or "<BLANK>"] += 1

                pruid_counts[pruid or "<BLANK>"] += 1

                if not province:
                    blank_province_rows += 1

                by_province = province == "ON"
                by_pruid = pruid == "35"

                if by_province:
                    ontario_by_province_count += 1

                if by_pruid:
                    ontario_by_pruid_count += 1

                if by_province and by_pruid:
                    ontario_intersection_count += 1

                if by_province or by_pruid:
                    ontario_union_count += 1

                if by_province != by_pruid:
                    province_pruid_disagreement_count += 1

                city_raw = normalize_text(_cell(row, "city"))
                csd_raw = normalize_text(_cell(row, "CSDNAME"))

                city_key = canonical_key(city_raw)
                csd_key = canonical_key(csd_raw)

                if by_province and by_pruid:
                    ontario_city_counts[city_raw or "<BLANK>"] += 1

                    ontario_csd_counts[csd_raw or "<BLANK>"] += 1

                city_is_target = city_key in TARGET_MUNICIPALITIES
                csd_is_target = csd_key in TARGET_MUNICIPALITIES

                if city_is_target:
                    target_city_exact_count += 1

                if csd_is_target:
                    target_csd_exact_count += 1

                if city_is_target or csd_is_target:
                    target_union_any_province_count += 1

                if by_province and by_pruid and (city_is_target or csd_is_target):
                    target_union_ontario_intersection_count += 1

                    municipality = city_key if city_is_target else csd_key

                    target_counts[municipality] += 1

                if city_is_target and csd_is_target and city_key != csd_key:
                    target_city_csd_conflict_count += 1

                status = normalize_text(_cell(row, "status"))

                provider = normalize_text(_cell(row, "provider"))

                geo_source = normalize_text(_cell(row, "geo_source"))

                status_counts[status or "<BLANK>"] += 1

                provider_counts[provider or "<BLANK>"] += 1

                geo_source_counts[geo_source or "<BLANK>"] += 1

                _update_coordinate(
                    latitude_state,
                    _cell(row, "latitude"),
                    lower=-90,
                    upper=90,
                )

                _update_coordinate(
                    longitude_state,
                    _cell(row, "longitude"),
                    lower=-180,
                    upper=180,
                )

                employee_value = normalize_text(
                    _cell(
                        row,
                        "total_no_employees",
                    )
                )

                employee_value_counts[employee_value or "<BLANK>"] += 1

                if not employee_value:
                    employee_blank_count += 1
                else:
                    integer_candidate = employee_value.replace(
                        ",",
                        "",
                    )

                    if INTEGER_PATTERN.fullmatch(integer_candidate):
                        employee_integer_count += 1
                    else:
                        employee_non_integer_count += 1
                        _add_example(
                            employee_non_integer_examples,
                            employee_value,
                        )

                primary_naics = normalize_text(
                    _cell(
                        row,
                        "source_NAICS_primary",
                    )
                )

                derived_naics = normalize_text(
                    _cell(
                        row,
                        "derived_NAICS",
                    )
                )

                primary_naics_counts[primary_naics or "<BLANK>"] += 1

                derived_naics_counts[derived_naics or "<BLANK>"] += 1

                if not primary_naics:
                    primary_naics_blank_count += 1
                elif NAICS_PATTERN.fullmatch(primary_naics):
                    primary_naics_valid_count += 1
                else:
                    primary_naics_invalid_count += 1
                    _add_example(
                        primary_naics_invalid_examples,
                        primary_naics,
                    )

    return {
        "source_id": ("statscan_odbus_2023"),
        "manifest_path": str(manifest_path.relative_to(project_root)),
        "archive_path": (raw_archive_path),
        "archive_sha256": actual_hash,
        "data_member": data_member,
        "data_encoding": encoding,
        "data_delimiter": delimiter,
        "row_count": row_count,
        "province_alignment": {
            "ontario_by_prov_terr": (ontario_by_province_count),
            "ontario_by_pruid": (ontario_by_pruid_count),
            "ontario_intersection": (ontario_intersection_count),
            "ontario_union": (ontario_union_count),
            "prov_terr_pruid_disagreements": (province_pruid_disagreement_count),
            "province_counts": (_counter_payload(province_counts)),
            "pruid_counts": (_counter_payload(pruid_counts)),
        },
        "target_market": {
            "municipalities": sorted(TARGET_MUNICIPALITIES),
            "city_exact_any_province": (target_city_exact_count),
            "csd_exact_any_province": (target_csd_exact_count),
            "union_any_province": (target_union_any_province_count),
            "union_ontario_intersection": (target_union_ontario_intersection_count),
            "city_csd_target_conflicts": (target_city_csd_conflict_count),
            "municipality_counts": (_counter_payload(target_counts)),
        },
        "ontario_city_counts": (
            _counter_payload(
                ontario_city_counts,
                limit=100,
            )
        ),
        "ontario_csd_counts": (
            _counter_payload(
                ontario_csd_counts,
                limit=100,
            )
        ),
        "status_counts": (_counter_payload(status_counts)),
        "provider_counts": (_counter_payload(provider_counts)),
        "geo_source_counts": (_counter_payload(geo_source_counts)),
        "coordinate_quality": {
            "latitude": latitude_state,
            "longitude": longitude_state,
        },
        "employee_field": {
            "integer_like_count": (employee_integer_count),
            "non_integer_count": (employee_non_integer_count),
            "blank_count": (employee_blank_count),
            "non_integer_examples": (employee_non_integer_examples),
            "top_values": (_counter_payload(employee_value_counts)),
        },
        "naics_field": {
            "primary_valid_count": (primary_naics_valid_count),
            "primary_invalid_count": (primary_naics_invalid_count),
            "primary_blank_count": (primary_naics_blank_count),
            "primary_invalid_examples": (primary_naics_invalid_examples),
            "primary_top_values": (_counter_payload(primary_naics_counts)),
            "derived_top_values": (_counter_payload(derived_naics_counts)),
        },
        "row_anomalies": {
            "extra_field_rows": (extra_field_rows),
            "missing_business_name_rows": (missing_business_name_rows),
            "blank_province_rows": (blank_province_rows),
        },
    }


def write_value_profile(
    *,
    project_root: Path,
    report: dict[str, Any],
) -> Path:
    destination = (
        project_root / "docs" / "data_contracts" / "statscan_odbus_2023_value_profile.json"
    )

    write_json_atomic(
        destination,
        report,
    )

    return destination
