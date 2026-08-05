from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "checksum_revalidation_required": True,
    "project_boundary_required": True,
    "symlink_allowed": False,
    "bounded_stream_reads_enabled": True,
    "bounded_in_memory_decompression_enabled": True,
    "archive_extraction_enabled": False,
    "full_decompression_enabled": False,
    "full_parser_execution_enabled": False,
    "schema_mutation_enabled": False,
    "row_materialization_enabled": False,
    "automatic_parser_approval": False,
    "snapshot_registration_enabled": False,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

BINARY_FORMATS: dict[str, str] = {
    ".dbf": "dbf_member",
    ".parquet": "parquet",
    ".shp": "shapefile_geometry_member",
    ".shx": "shapefile_index_member",
}


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _require_nonnegative_int(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{field_name} must be a nonnegative integer.")

    return value


def _require_positive_number(
    value: object,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise RuntimeError(f"{field_name} must be positive.")

    return float(value)


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "bounded_parser_probe.json")

    raw_policy = config.get("policy")
    raw_limits = config.get("limits")

    if not isinstance(raw_policy, dict):
        raise RuntimeError("Bounded-probe policy must be an object.")

    if not isinstance(raw_limits, dict):
        raise RuntimeError("Bounded-probe limits must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Bounded-probe policy mismatch.")

    for field in (
        "maximum_gzip_prefix_bytes",
        "maximum_zip_member_prefix_bytes",
        "maximum_zip_members_probed",
        "maximum_detected_columns",
        "maximum_detected_json_keys",
    ):
        _require_nonnegative_int(
            raw_limits.get(field),
            f"limits.{field}",
        )

    _require_positive_number(
        raw_limits.get("maximum_member_compression_ratio"),
        "limits.maximum_member_compression_ratio",
    )

    return config


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _inside_project(
    path: Path,
    project_root: Path,
) -> bool:
    try:
        path.relative_to(project_root)
        return True

    except ValueError:
        return False


def _safe_member_name(
    member_name: str,
) -> bool:
    normalized = member_name.replace(
        "\\",
        "/",
    )

    if not normalized or "\x00" in normalized:
        return False

    member_path = PurePosixPath(normalized)

    return not member_path.is_absolute() and ".." not in member_path.parts


def _decode_text(
    data: bytes,
) -> tuple[str | None, str | None]:
    for encoding in (
        "utf-8-sig",
        "utf-8",
    ):
        try:
            return (
                data.decode(encoding),
                encoding,
            )

        except UnicodeDecodeError:
            continue

    return (
        None,
        None,
    )


def _json_evidence(
    text: str,
    maximum_keys: int,
) -> dict[str, Any]:
    stripped = text.lstrip()

    top_level_hint: str | None = None

    if stripped.startswith("{"):
        top_level_hint = "object"

    elif stripped.startswith("["):
        top_level_hint = "array"

    key_candidates: list[str] = []

    decoder = json.JSONDecoder()

    try:
        parsed, _ = decoder.raw_decode(stripped)

    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        key_candidates = [str(key) for key in list(parsed.keys())[:maximum_keys]]

    feature_collection = '"FeatureCollection"' in stripped and '"features"' in stripped

    return {
        "top_level_hint": top_level_hint,
        "bounded_json_decode_succeeded": (parsed is not None),
        "detected_keys": key_candidates,
        "geojson_feature_collection_detected": (feature_collection),
    }


def _delimited_evidence(
    text: str,
    suffix: str,
    maximum_columns: int,
) -> dict[str, Any]:
    sample = text[
        : min(
            len(text),
            32768,
        )
    ]

    delimiter: str | None = None

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=",;\t|",
        )

        delimiter = str(dialect.delimiter)

    except csv.Error:
        if suffix == ".tsv":
            delimiter = "\t"

        elif suffix == ".csv":
            delimiter = ","

    lines = text.splitlines()

    first_line = lines[0] if lines else ""

    header_columns: list[str] = []

    if delimiter is not None and first_line:
        header_columns = [
            value.strip()
            for value in next(
                csv.reader(
                    io.StringIO(first_line),
                    delimiter=delimiter,
                ),
                [],
            )[:maximum_columns]
        ]

    return {
        "delimiter": delimiter,
        "header_columns": header_columns,
        "header_column_count": len(header_columns),
    }


def _classify_prefix(
    logical_name: str,
    data: bytes,
    *,
    maximum_columns: int,
    maximum_json_keys: int,
) -> dict[str, Any]:
    suffix = Path(logical_name).suffix.lower()

    prefix_sha256 = hashlib.sha256(data).hexdigest()

    if suffix == ".parquet" or data.startswith(b"PAR1"):
        return {
            "recognized_format": "parquet",
            "prefix_sha256": prefix_sha256,
            "prefix_bytes": len(data),
            "text_decodable": False,
            "encoding": None,
            "json_evidence": None,
            "delimited_evidence": None,
        }

    if suffix in BINARY_FORMATS:
        return {
            "recognized_format": (BINARY_FORMATS[suffix]),
            "prefix_sha256": prefix_sha256,
            "prefix_bytes": len(data),
            "text_decodable": False,
            "encoding": None,
            "json_evidence": None,
            "delimited_evidence": None,
        }

    text, encoding = _decode_text(data)

    if text is None:
        return {
            "recognized_format": None,
            "prefix_sha256": prefix_sha256,
            "prefix_bytes": len(data),
            "text_decodable": False,
            "encoding": None,
            "json_evidence": None,
            "delimited_evidence": None,
        }

    stripped = text.lstrip()

    json_evidence: dict[str, Any] | None = None
    delimited_evidence: dict[str, Any] | None = None
    recognized_format: str | None = None

    if suffix in {
        ".geojson",
        ".json",
        ".jsonl",
        ".ndjson",
    } or stripped.startswith(
        (
            "{",
            "[",
        )
    ):
        json_evidence = _json_evidence(
            text,
            maximum_json_keys,
        )

        if json_evidence["geojson_feature_collection_detected"]:
            recognized_format = "geojson_feature_collection"

        elif suffix in {
            ".jsonl",
            ".ndjson",
        }:
            recognized_format = "json_lines_candidate"

        else:
            recognized_format = "json_candidate"

    else:
        delimited_evidence = _delimited_evidence(
            text,
            suffix,
            maximum_columns,
        )

        if suffix in {
            ".csv",
            ".tsv",
        } or (
            delimited_evidence["delimiter"] is not None
            and delimited_evidence["header_column_count"] >= 2
        ):
            recognized_format = "delimited_text"

    return {
        "recognized_format": recognized_format,
        "prefix_sha256": prefix_sha256,
        "prefix_bytes": len(data),
        "text_decodable": True,
        "encoding": encoding,
        "json_evidence": json_evidence,
        "delimited_evidence": (delimited_evidence),
    }


def _probe_gzip(
    path: Path,
    artifact_path: str,
    *,
    prefix_limit: int,
    maximum_columns: int,
    maximum_json_keys: int,
) -> dict[str, Any]:
    operational_errors: list[str] = []
    data = b""
    truncated = False

    try:
        with gzip.open(
            path,
            mode="rb",
        ) as stream:
            raw = stream.read(prefix_limit + 1)

        truncated = len(raw) > prefix_limit

        data = raw[:prefix_limit]

    except (
        EOFError,
        OSError,
        gzip.BadGzipFile,
    ) as error:
        operational_errors.append(type(error).__name__)

    logical_name = str(Path(artifact_path).with_suffix(""))

    classification = (
        _classify_prefix(
            logical_name,
            data,
            maximum_columns=(maximum_columns),
            maximum_json_keys=(maximum_json_keys),
        )
        if not operational_errors
        else None
    )

    return {
        "container_type": "gzip",
        "logical_name": logical_name,
        "bounded_prefix_bytes": len(data),
        "prefix_truncated": truncated,
        "classification": classification,
        "operational_errors": (operational_errors),
        "bounded_stream_read_performed": (not operational_errors),
        "bounded_decompression_performed": (not operational_errors),
        "full_decompression_performed": False,
        "full_parser_execution_performed": False,
    }


def _probe_zip(
    path: Path,
    *,
    prefix_limit: int,
    member_limit: int,
    maximum_ratio: float,
    maximum_columns: int,
    maximum_json_keys: int,
) -> dict[str, Any]:
    member_results: list[dict[str, Any]] = []

    container_errors: list[str] = []

    try:
        with zipfile.ZipFile(
            path,
            mode="r",
        ) as archive:
            candidate_members = [member for member in archive.infolist() if not member.is_dir()][
                :member_limit
            ]

            for member in candidate_members:
                member_name = member.filename.replace(
                    "\\",
                    "/",
                )

                member_errors: list[str] = []

                if not _safe_member_name(member_name):
                    member_errors.append("unsafe_member_name")

                if member.flag_bits & 0x1:
                    member_errors.append("encrypted_member")

                compression_ratio = (
                    float(member.file_size) / float(member.compress_size)
                    if member.compress_size > 0
                    else None
                )

                if compression_ratio is not None and compression_ratio > maximum_ratio:
                    member_errors.append("compression_ratio_limit_exceeded")

                data = b""
                truncated = False

                if not member_errors:
                    try:
                        with archive.open(
                            member,
                            mode="r",
                        ) as stream:
                            raw = stream.read(prefix_limit + 1)

                        truncated = len(raw) > prefix_limit

                        data = raw[:prefix_limit]

                    except (
                        OSError,
                        RuntimeError,
                        zipfile.BadZipFile,
                    ) as error:
                        member_errors.append(type(error).__name__)

                classification = (
                    _classify_prefix(
                        member_name,
                        data,
                        maximum_columns=(maximum_columns),
                        maximum_json_keys=(maximum_json_keys),
                    )
                    if not member_errors
                    else None
                )

                member_results.append(
                    {
                        "member_name": member_name,
                        "compressed_size": int(member.compress_size),
                        "uncompressed_size": int(member.file_size),
                        "compression_ratio": (
                            round(
                                compression_ratio,
                                6,
                            )
                            if compression_ratio is not None
                            else None
                        ),
                        "bounded_prefix_bytes": (len(data)),
                        "prefix_truncated": (truncated),
                        "classification": (classification),
                        "operational_errors": (member_errors),
                        "bounded_stream_read_performed": (not member_errors),
                        "bounded_decompression_performed": (not member_errors),
                    }
                )

    except (
        OSError,
        zipfile.BadZipFile,
    ) as error:
        container_errors.append(type(error).__name__)

    return {
        "container_type": "zip",
        "member_probe_count": len(member_results),
        "members": member_results,
        "operational_errors": (container_errors),
        "archive_extraction_performed": False,
        "full_decompression_performed": False,
        "full_parser_execution_performed": False,
    }


def _probe_plain_file(
    path: Path,
    artifact_path: str,
    *,
    prefix_limit: int,
    maximum_columns: int,
    maximum_json_keys: int,
) -> dict[str, Any]:
    operational_errors: list[str] = []
    data = b""
    truncated = False

    try:
        with path.open("rb") as stream:
            raw = stream.read(prefix_limit + 1)

        truncated = len(raw) > prefix_limit

        data = raw[:prefix_limit]

    except OSError as error:
        operational_errors.append(type(error).__name__)

    classification = (
        _classify_prefix(
            artifact_path,
            data,
            maximum_columns=(maximum_columns),
            maximum_json_keys=(maximum_json_keys),
        )
        if not operational_errors
        else None
    )

    return {
        "container_type": "plain_file",
        "logical_name": artifact_path,
        "bounded_prefix_bytes": len(data),
        "prefix_truncated": truncated,
        "classification": classification,
        "operational_errors": (operational_errors),
        "bounded_stream_read_performed": (not operational_errors),
        "bounded_decompression_performed": False,
        "full_decompression_performed": False,
        "full_parser_execution_performed": False,
    }


def build_bounded_parser_probe(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    raw_limits = config["limits"]

    if not isinstance(raw_limits, dict):
        raise RuntimeError("Bounded-probe limits are malformed.")

    gzip_prefix_limit = _require_nonnegative_int(
        raw_limits.get("maximum_gzip_prefix_bytes"),
        "maximum_gzip_prefix_bytes",
    )

    zip_prefix_limit = _require_nonnegative_int(
        raw_limits.get("maximum_zip_member_prefix_bytes"),
        "maximum_zip_member_prefix_bytes",
    )

    zip_member_limit = _require_nonnegative_int(
        raw_limits.get("maximum_zip_members_probed"),
        "maximum_zip_members_probed",
    )

    maximum_ratio = _require_positive_number(
        raw_limits.get("maximum_member_compression_ratio"),
        "maximum_member_compression_ratio",
    )

    maximum_columns = _require_nonnegative_int(
        raw_limits.get("maximum_detected_columns"),
        "maximum_detected_columns",
    )

    maximum_json_keys = _require_nonnegative_int(
        raw_limits.get("maximum_detected_json_keys"),
        "maximum_detected_json_keys",
    )

    admission = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_admission.json"
    )

    containers = _load_object(
        project_root / "docs" / "data_contracts" / "source_container_inventory.json"
    )

    raw_packets = admission.get("packets")

    raw_container_entries = containers.get("entries")

    if not isinstance(raw_packets, list):
        raise RuntimeError("Admission packets must be a list.")

    if not isinstance(
        raw_container_entries,
        list,
    ):
        raise RuntimeError("Container entries must be a list.")

    container_by_path: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_entry in raw_container_entries:
        if not isinstance(raw_entry, dict):
            raise RuntimeError("Container entry must be an object.")

        artifact_path = raw_entry.get("artifact_path")

        if (
            not isinstance(
                artifact_path,
                str,
            )
            or not artifact_path
        ):
            raise RuntimeError("Container entry lacks artifact_path.")

        container_by_path[artifact_path] = {str(key): value for key, value in raw_entry.items()}

    root = project_root.resolve()

    entries: list[dict[str, Any]] = []

    approval_templates: list[dict[str, Any]] = []

    integrity_violation_count = 0
    probe_completed_count = 0
    recognized_artifact_count = 0
    bounded_stream_read_count = 0
    bounded_decompression_count = 0

    for raw_packet in raw_packets:
        if not isinstance(raw_packet, dict):
            raise RuntimeError("Admission packet must be an object.")

        source_id = raw_packet.get("source_id")

        raw_artifacts = raw_packet.get("artifacts")

        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id
        ):
            raise RuntimeError("Admission packet lacks source_id.")

        if not isinstance(
            raw_artifacts,
            list,
        ):
            raise RuntimeError("Admission artifacts must be a list.")

        for raw_artifact in raw_artifacts:
            if not isinstance(
                raw_artifact,
                dict,
            ):
                raise RuntimeError("Admission artifact must be an object.")

            artifact_path = raw_artifact.get("resolved_relative_path")

            raw_probe = raw_artifact.get("probe")

            if (
                not isinstance(
                    artifact_path,
                    str,
                )
                or not artifact_path
            ):
                raise RuntimeError("Admission artifact lacks path.")

            if not isinstance(raw_probe, dict):
                raise RuntimeError("Admission artifact lacks checksum probe.")

            expected_sha256 = raw_probe.get("actual_sha256")

            if (
                not isinstance(
                    expected_sha256,
                    str,
                )
                or not expected_sha256
            ):
                raise RuntimeError("Admission artifact lacks SHA-256.")

            path = (project_root / artifact_path).resolve(strict=False)

            integrity_violations: list[str] = []

            if not _inside_project(
                path,
                root,
            ):
                integrity_violations.append("artifact_outside_project")

            elif not path.is_file():
                integrity_violations.append("artifact_missing")

            elif path.is_symlink():
                integrity_violations.append("artifact_symlink_not_allowed")

            actual_sha256 = _sha256(path) if not integrity_violations else None

            if actual_sha256 is not None and actual_sha256 != expected_sha256:
                integrity_violations.append("artifact_checksum_changed")

            container_entry = container_by_path.get(artifact_path)

            if container_entry is None:
                integrity_violations.append("container_inventory_missing")

            container_type = (
                str(container_entry.get("container_type"))
                if container_entry is not None
                else "unknown"
            )

            result: dict[str, Any]

            if integrity_violations:
                result = {
                    "container_type": (container_type),
                    "operational_errors": [],
                    "full_parser_execution_performed": False,
                }

            elif container_type == "gzip":
                result = _probe_gzip(
                    path,
                    artifact_path,
                    prefix_limit=(gzip_prefix_limit),
                    maximum_columns=(maximum_columns),
                    maximum_json_keys=(maximum_json_keys),
                )

            elif container_type == "zip":
                result = _probe_zip(
                    path,
                    prefix_limit=(zip_prefix_limit),
                    member_limit=(zip_member_limit),
                    maximum_ratio=(maximum_ratio),
                    maximum_columns=(maximum_columns),
                    maximum_json_keys=(maximum_json_keys),
                )

            else:
                result = _probe_plain_file(
                    path,
                    artifact_path,
                    prefix_limit=(zip_prefix_limit),
                    maximum_columns=(maximum_columns),
                    maximum_json_keys=(maximum_json_keys),
                )

            operational_errors_raw = result.get("operational_errors")

            operational_errors = (
                [str(value) for value in operational_errors_raw]
                if isinstance(
                    operational_errors_raw,
                    list,
                )
                else []
            )

            recognized_formats: set[str] = set()

            if container_type == "zip":
                raw_members = result.get("members")

                if isinstance(raw_members, list):
                    for raw_member in raw_members:
                        if not isinstance(
                            raw_member,
                            dict,
                        ):
                            continue

                        member_errors = raw_member.get("operational_errors")

                        if isinstance(
                            member_errors,
                            list,
                        ):
                            operational_errors.extend(str(value) for value in member_errors)

                        classification = raw_member.get("classification")

                        if isinstance(
                            classification,
                            dict,
                        ):
                            recognized = classification.get("recognized_format")

                            if isinstance(
                                recognized,
                                str,
                            ):
                                recognized_formats.add(recognized)

                        if raw_member.get("bounded_stream_read_performed"):
                            bounded_stream_read_count += 1

                        if raw_member.get("bounded_decompression_performed"):
                            bounded_decompression_count += 1

            else:
                classification = result.get("classification")

                if isinstance(
                    classification,
                    dict,
                ):
                    recognized = classification.get("recognized_format")

                    if isinstance(
                        recognized,
                        str,
                    ):
                        recognized_formats.add(recognized)

                if result.get("bounded_stream_read_performed"):
                    bounded_stream_read_count += 1

                if result.get("bounded_decompression_performed"):
                    bounded_decompression_count += 1

            normalized_operational_errors = sorted(set(operational_errors))

            probe_completed = not integrity_violations and not normalized_operational_errors

            parser_approval_ready = probe_completed and bool(recognized_formats)

            if integrity_violations:
                integrity_violation_count += 1

            if probe_completed:
                probe_completed_count += 1

            if recognized_formats:
                recognized_artifact_count += 1

            entries.append(
                {
                    "source_id": source_id,
                    "artifact_path": (artifact_path),
                    "expected_sha256": (expected_sha256),
                    "actual_sha256": (actual_sha256),
                    "container_type": (container_type),
                    "integrity_violations": (sorted(set(integrity_violations))),
                    "operational_errors": (normalized_operational_errors),
                    "recognized_formats": (sorted(recognized_formats)),
                    "probe_result": result,
                    "probe_completed": (probe_completed),
                    "parser_approval_ready": (parser_approval_ready),
                    "archive_extraction_performed": False,
                    "full_decompression_performed": False,
                    "full_parser_execution_performed": False,
                    "schema_mutation_performed": False,
                    "row_materialization_performed": False,
                    "snapshot_registration_performed": False,
                }
            )

            approval_templates.append(
                {
                    "source_id": source_id,
                    "artifact_path": (artifact_path),
                    "allowed_artifact_sha256": (expected_sha256),
                    "recognized_formats": (sorted(recognized_formats)),
                    "approved_parser_type": None,
                    "approved_decoder_chain": [],
                    "approved_encoding": None,
                    "approved_delimiter": None,
                    "approved_columns": [],
                    "approved_member_names": [],
                    "expected_schema_contract": None,
                    "record_identity_rule": None,
                    "record_count_rule": None,
                    "parser_contract_approved": False,
                    "approved_by": None,
                    "approved_at": None,
                    "approval_evidence_reference": None,
                    "parser_execution_requested": False,
                    "parser_execution_permitted": False,
                }
            )

    entries.sort(
        key=lambda item: (
            str(item["source_id"]),
            str(item["artifact_path"]),
        )
    )

    approval_templates.sort(
        key=lambda item: (
            str(item["source_id"]),
            str(item["artifact_path"]),
        )
    )

    entry_count = len(entries)

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-bounded-parser-probe-v1"),
        "entry_count": entry_count,
        "probe_completed_count": (probe_completed_count),
        "recognized_artifact_count": (recognized_artifact_count),
        "parser_approval_ready_count": sum(
            bool(entry["parser_approval_ready"]) for entry in entries
        ),
        "blocked_count": (entry_count - probe_completed_count),
        "integrity_violation_count": (integrity_violation_count),
        "bounded_stream_read_count": (bounded_stream_read_count),
        "bounded_decompression_count": (bounded_decompression_count),
        "entries": entries,
        "archive_extraction_execution_count": 0,
        "full_decompression_execution_count": 0,
        "full_parser_execution_count": 0,
        "schema_mutation_execution_count": 0,
        "row_materialization_execution_count": 0,
        "parser_contract_approval_count": 0,
        "snapshot_registration_execution_count": 0,
        "automatic_acquisition_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    approval_report: dict[str, Any] = {
        "model_version": ("cre-foundry-parser-probe-approval-template-v1"),
        "approval_count": len(approval_templates),
        "approved_parser_contract_count": 0,
        "parser_execution_requested_count": 0,
        "parser_execution_permitted_count": 0,
        "approvals": approval_templates,
        "automatic_approval": False,
        "snapshot_registration_permitted": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        report_path = contract_root / "bounded_parser_probe.json"

        approval_path = contract_root / "source_parser_probe_approval_template.json"

        markdown_path = contract_root / "bounded_parser_probe.md"

        _atomic_json(
            report_path,
            report,
        )

        _atomic_json(
            approval_path,
            approval_report,
        )

        _atomic_text(
            markdown_path,
            "\n".join(
                [
                    "# Bounded Parser Reconnaissance",
                    "",
                    (
                        "This layer reads strictly bounded "
                        "in-memory prefixes from admitted artifacts."
                    ),
                    "",
                    (
                        "ZIP members are streamed directly from "
                        "their archive. No member is extracted."
                    ),
                    "",
                    ("GZIP data is decompressed only until the configured prefix limit."),
                    "",
                    f"- Artifacts: `{entry_count}`",
                    (f"- Completed probes: `{probe_completed_count}`"),
                    (f"- Recognized artifacts: `{recognized_artifact_count}`"),
                    (f"- Integrity violations: `{integrity_violation_count}`"),
                    "",
                    "- Archive extraction: `false`",
                    "- Full decompression: `false`",
                    "- Full parsing: `false`",
                    "- Row materialization: `false`",
                    "- Snapshot registration: `false`",
                    "",
                ]
            ),
        )

    return {
        "probe": report,
        "approval_template": (approval_report),
    }
