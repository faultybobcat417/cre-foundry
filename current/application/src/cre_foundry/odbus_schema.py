from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, cast

from cre_foundry.bulk_storage import (
    sha256_file,
    write_json_atomic,
)

INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


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


def latest_odbus_manifest(
    project_root: Path,
) -> Path:
    manifests = list(
        (project_root / "data" / "bronze" / "statscan_odbus_2023").rglob("manifest.json")
    )

    if not manifests:
        raise FileNotFoundError("No ODBus bronze manifest exists.")

    return max(
        manifests,
        key=lambda path: path.stat().st_mtime,
    )


def _detect_encoding(
    sample: bytes,
) -> str:
    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
    ):
        try:
            sample.decode(
                encoding,
                errors="strict",
            )
        except UnicodeDecodeError:
            continue

        return encoding

    return "latin-1"


def _detect_delimiter(
    sample_text: str,
) -> str:
    try:
        dialect = csv.Sniffer().sniff(
            sample_text,
            delimiters=",;\t|",
        )
    except csv.Error:
        return ","

    return dialect.delimiter


def _select_members(
    archive: zipfile.ZipFile,
) -> tuple[str, str]:
    files = [entry for entry in archive.infolist() if not entry.is_dir()]

    data_candidates = [
        entry
        for entry in files
        if entry.filename.lower().endswith(".csv")
        and "record-layout" not in (entry.filename.lower())
        and "sources" not in (entry.filename.lower())
    ]

    layout_candidates = [
        entry
        for entry in files
        if "record-layout" in (entry.filename.lower()) and entry.filename.lower().endswith(".csv")
    ]

    if not data_candidates:
        raise RuntimeError("Could not identify the primary ODBus CSV.")

    if not layout_candidates:
        raise RuntimeError("Could not identify the ODBus record layout.")

    data_member = max(
        data_candidates,
        key=lambda entry: entry.file_size,
    )

    layout_member = layout_candidates[0]

    return (
        data_member.filename,
        layout_member.filename,
    )


def _text_settings(
    archive: zipfile.ZipFile,
    member_name: str,
) -> tuple[str, str]:
    with archive.open(
        member_name,
        mode="r",
    ) as handle:
        sample = handle.read(256 * 1024)

    encoding = _detect_encoding(sample)

    sample_text = sample.decode(
        encoding,
        errors="strict",
    )

    delimiter = _detect_delimiter(sample_text)

    return encoding, delimiter


def _new_column_state() -> dict[str, Any]:
    return {
        "non_empty_count": 0,
        "empty_count": 0,
        "maximum_length": 0,
        "all_integer_like": True,
        "all_numeric_like": True,
    }


def _update_column_state(
    state: dict[str, Any],
    raw_value: object,
) -> None:
    value = raw_value.strip() if isinstance(raw_value, str) else ""

    if not value:
        state["empty_count"] += 1
        return

    state["non_empty_count"] += 1
    state["maximum_length"] = max(
        int(state["maximum_length"]),
        len(value),
    )

    if INTEGER_PATTERN.fullmatch(value) is None:
        state["all_integer_like"] = False

    try:
        float(value)
    except ValueError:
        state["all_numeric_like"] = False


def _candidate_type(
    state: dict[str, Any],
) -> str:
    non_empty = int(state["non_empty_count"])

    if non_empty == 0:
        return "empty"

    if bool(state["all_integer_like"]):
        return "integer-like"

    if bool(state["all_numeric_like"]):
        return "numeric-like"

    return "string-like"


def _profile_data_member(
    archive: zipfile.ZipFile,
    *,
    member_name: str,
    encoding: str,
    delimiter: str,
) -> dict[str, Any]:
    with (
        archive.open(
            member_name,
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
            raise RuntimeError("ODBus CSV has no header row.")

        columns = [field.strip() for field in reader.fieldnames if field is not None]

        if not columns:
            raise RuntimeError("ODBus CSV header is empty.")

        if len(columns) != len(set(columns)):
            raise RuntimeError("ODBus CSV contains duplicate columns.")

        states = {column: _new_column_state() for column in columns}

        row_count = 0

        for row in reader:
            row_count += 1

            for column in columns:
                _update_column_state(
                    states[column],
                    row.get(column),
                )

    column_profiles = []

    for position, column in enumerate(
        columns,
        start=1,
    ):
        state = states[column]

        column_profiles.append(
            {
                "position": position,
                "name": column,
                "candidate_type": (_candidate_type(state)),
                "non_empty_count": int(state["non_empty_count"]),
                "empty_count": int(state["empty_count"]),
                "maximum_length": int(state["maximum_length"]),
            }
        )

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "column_profiles": (column_profiles),
    }


def _read_record_layout(
    archive: zipfile.ZipFile,
    *,
    member_name: str,
) -> dict[str, Any]:
    encoding, delimiter = _text_settings(
        archive,
        member_name,
    )

    with (
        archive.open(
            member_name,
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

        fieldnames = list(reader.fieldnames) if reader.fieldnames is not None else []

        rows: list[dict[str, str]] = []

        for raw_row in reader:
            normalized: dict[
                str,
                str,
            ] = {}

            for key, value in raw_row.items():
                if key is None:
                    continue

                normalized[key] = (
                    value
                    if isinstance(
                        value,
                        str,
                    )
                    else ""
                )

            rows.append(normalized)

    return {
        "encoding": encoding,
        "delimiter": delimiter,
        "columns": fieldnames,
        "row_count": len(rows),
        "rows": rows,
    }


def inspect_latest_odbus_schema(
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

    with zipfile.ZipFile(
        archive_path,
        mode="r",
    ) as archive:
        data_member, layout_member = _select_members(archive)

        encoding, delimiter = _text_settings(
            archive,
            data_member,
        )

        data_profile = _profile_data_member(
            archive,
            member_name=data_member,
            encoding=encoding,
            delimiter=delimiter,
        )

        record_layout = _read_record_layout(
            archive,
            member_name=layout_member,
        )

        archive_members = [
            {
                "name": entry.filename,
                "compressed_bytes": (entry.compress_size),
                "uncompressed_bytes": (entry.file_size),
                "is_directory": (entry.is_dir()),
            }
            for entry in archive.infolist()
        ]

    return {
        "source_id": ("statscan_odbus_2023"),
        "manifest_path": str(manifest_path.relative_to(project_root)),
        "archive_path": (raw_archive_path),
        "archive_sha256": actual_hash,
        "archive_members": (archive_members),
        "data_member": data_member,
        "record_layout_member": (layout_member),
        "data_encoding": encoding,
        "data_delimiter": delimiter,
        **data_profile,
        "record_layout": (record_layout),
    }


def write_schema_report(
    *,
    project_root: Path,
    report: dict[str, Any],
) -> Path:
    destination = project_root / "docs" / "data_contracts" / "statscan_odbus_2023_schema.json"

    write_json_atomic(
        destination,
        report,
    )

    return destination
