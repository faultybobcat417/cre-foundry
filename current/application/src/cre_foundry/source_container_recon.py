from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "checksum_revalidation_required": True,
    "project_boundary_required": True,
    "symlink_allowed": False,
    "zip_central_directory_inspection": True,
    "zip_extraction_enabled": False,
    "gzip_header_inspection": True,
    "gzip_decompression_enabled": False,
    "parser_execution_enabled": False,
    "schema_validation_enabled": False,
    "row_validation_enabled": False,
    "snapshot_registration_enabled": False,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
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

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _require_nonnegative_int(
    value: object,
    field_name: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise RuntimeError(f"{field_name} must be a nonnegative integer.")

    return value


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "source_container_recon.json")

    raw_policy = config.get("policy")

    raw_limits = config.get("limits")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Container policy must be an object.")

    if not isinstance(
        raw_limits,
        dict,
    ):
        raise RuntimeError("Container limits must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Container policy mismatch.")

    _require_nonnegative_int(
        raw_limits.get("maximum_zip_members"),
        "maximum_zip_members",
    )

    _require_nonnegative_int(
        raw_limits.get("maximum_member_name_length"),
        "maximum_member_name_length",
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


def _safe_zip_name(
    member_name: str,
    maximum_length: int,
) -> bool:
    if not member_name or len(member_name) > maximum_length or "\x00" in member_name:
        return False

    normalized = member_name.replace(
        "\\",
        "/",
    )

    pure_path = PurePosixPath(normalized)

    return not pure_path.is_absolute() and ".." not in pure_path.parts


def _zip_inventory(
    path: Path,
    maximum_members: int,
    maximum_name_length: int,
) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(
            path,
            mode="r",
        ) as archive:
            all_members = archive.infolist()

    except zipfile.BadZipFile:
        return {
            "valid": False,
            "violations": ["invalid_zip_container"],
            "members": [],
        }

    selected_members = all_members[:maximum_members]

    overflow_count = max(
        0,
        len(all_members) - len(selected_members),
    )

    member_names = [
        member.filename.replace(
            "\\",
            "/",
        )
        for member in selected_members
    ]

    duplicate_names = sorted(name for name, count in Counter(member_names).items() if count > 1)

    extension_counts: Counter[str] = Counter()

    records = []
    unsafe_names = []
    encrypted_names = []

    total_compressed = 0
    total_uncompressed = 0

    for member in selected_members:
        normalized_name = member.filename.replace(
            "\\",
            "/",
        )

        safe_name = _safe_zip_name(
            normalized_name,
            maximum_name_length,
        )

        encrypted = bool(member.flag_bits & 0x1)

        suffix = Path(normalized_name).suffix.lower()

        extension_counts[suffix or "[none]"] += 1

        total_compressed += int(member.compress_size)

        total_uncompressed += int(member.file_size)

        if not safe_name:
            unsafe_names.append(normalized_name)

        if encrypted:
            encrypted_names.append(normalized_name)

        records.append(
            {
                "member_name": normalized_name,
                "is_directory": (member.is_dir()),
                "safe_member_name": (safe_name),
                "encrypted": encrypted,
                "compression_type": int(member.compress_type),
                "compressed_size": int(member.compress_size),
                "uncompressed_size": int(member.file_size),
                "crc32": (f"{member.CRC:08x}"),
                "suffix": (suffix or None),
            }
        )

    violations = []

    if overflow_count:
        violations.append("zip_member_limit_exceeded")

    if unsafe_names:
        violations.append("unsafe_zip_member_paths")

    if encrypted_names:
        violations.append("encrypted_zip_members")

    if duplicate_names:
        violations.append("duplicate_zip_member_names")

    return {
        "valid": True,
        "member_count": len(all_members),
        "inventoried_member_count": len(records),
        "member_overflow_count": (overflow_count),
        "total_compressed_size": (total_compressed),
        "total_uncompressed_size": (total_uncompressed),
        "compression_ratio": (
            round(
                total_uncompressed / total_compressed,
                6,
            )
            if total_compressed
            else None
        ),
        "extension_counts": dict(sorted(extension_counts.items())),
        "unsafe_member_count": len(unsafe_names),
        "encrypted_member_count": len(encrypted_names),
        "duplicate_name_count": len(duplicate_names),
        "duplicate_names": (duplicate_names),
        "members": records,
        "violations": (violations),
    }


def _gzip_inventory(
    path: Path,
) -> dict[str, Any]:
    size_bytes = path.stat().st_size

    with path.open("rb") as stream:
        header = stream.read(10)

        trailer = b""

        if size_bytes >= 8:
            stream.seek(
                -8,
                os.SEEK_END,
            )

            trailer = stream.read(8)

    violations = []

    if len(header) != 10:
        violations.append("truncated_gzip_header")

        return {
            "valid": False,
            "violations": (violations),
        }

    if header[:2] != b"\x1f\x8b":
        violations.append("invalid_gzip_magic")

    compression_method = int(header[2])

    if compression_method != 8:
        violations.append("unsupported_gzip_compression_method")

    trailer_crc32 = None
    uncompressed_size_modulo = None

    if len(trailer) == 8:
        trailer_crc32 = f"{int.from_bytes(trailer[:4], 'little'):08x}"

        uncompressed_size_modulo = int.from_bytes(
            trailer[4:],
            "little",
        )

    else:
        violations.append("missing_gzip_trailer")

    return {
        "valid": not violations,
        "compression_method": (compression_method),
        "flags": int(header[3]),
        "modification_time_raw": (
            int.from_bytes(
                header[4:8],
                "little",
            )
        ),
        "extra_flags": int(header[8]),
        "operating_system": int(header[9]),
        "trailer_crc32": (trailer_crc32),
        "uncompressed_size_modulo_2_32": (uncompressed_size_modulo),
        "violations": (violations),
    }


def _format_candidates(
    artifact_path: str,
    container_type: str,
    inventory: dict[str, Any],
) -> list[str]:
    suffixes = [suffix.lower() for suffix in Path(artifact_path).suffixes]

    candidates: set[str] = set()

    if container_type == "gzip":
        if suffixes[-2:] == [
            ".geojson",
            ".gz",
        ]:
            candidates.add("gzip_geojson")

        elif suffixes[-2:] == [
            ".csv",
            ".gz",
        ]:
            candidates.add("gzip_csv")

        elif suffixes[-2:] == [
            ".json",
            ".gz",
        ]:
            candidates.add("gzip_json")

    elif container_type == "zip":
        raw_extensions = inventory.get("extension_counts")

        extensions = (
            {str(key) for key in raw_extensions}
            if isinstance(
                raw_extensions,
                dict,
            )
            else set()
        )

        if ".csv" in extensions:
            candidates.add("zip_csv_members")

        if ".json" in extensions:
            candidates.add("zip_json_members")

        if ".geojson" in extensions:
            candidates.add("zip_geojson_members")

        if {
            ".shp",
            ".dbf",
        }.issubset(extensions):
            candidates.add("zip_shapefile_bundle")

    if not candidates:
        candidates.add("manual_format_review")

    return sorted(candidates)


def build_source_container_recon(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    raw_limits = config["limits"]

    if not isinstance(
        raw_limits,
        dict,
    ):
        raise RuntimeError("Container limits are malformed.")

    maximum_zip_members = _require_nonnegative_int(
        raw_limits.get("maximum_zip_members"),
        "maximum_zip_members",
    )

    maximum_name_length = _require_nonnegative_int(
        raw_limits.get("maximum_member_name_length"),
        "maximum_member_name_length",
    )

    admission = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_admission.json"
    )

    raw_packets = admission.get("packets")

    if not isinstance(
        raw_packets,
        list,
    ):
        raise RuntimeError("Admission packets must be a list.")

    root = project_root.resolve()

    entries = []
    parser_candidates = []

    type_counts: Counter[str] = Counter()

    ready_count = 0
    blocked_count = 0

    for raw_packet in raw_packets:
        if not isinstance(
            raw_packet,
            dict,
        ):
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

            relative_path = raw_artifact.get("resolved_relative_path")

            raw_probe = raw_artifact.get("probe")

            if (
                not isinstance(
                    relative_path,
                    str,
                )
                or not relative_path
            ):
                raise RuntimeError("Admission artifact lacks a path.")

            if not isinstance(
                raw_probe,
                dict,
            ):
                raise RuntimeError("Admission artifact lacks a probe.")

            expected_sha256 = raw_probe.get("actual_sha256")

            if (
                not isinstance(
                    expected_sha256,
                    str,
                )
                or not expected_sha256
            ):
                raise RuntimeError("Admission artifact lacks SHA-256.")

            path = (project_root / relative_path).resolve(strict=False)

            violations = []

            if not _inside_project(
                path,
                root,
            ):
                violations.append("artifact_outside_project")

            elif not path.is_file():
                violations.append("artifact_missing")

            elif path.is_symlink():
                violations.append("artifact_symlink_not_allowed")

            actual_sha256 = _sha256(path) if not violations else None

            if actual_sha256 is not None and actual_sha256 != expected_sha256:
                violations.append("artifact_checksum_changed")

            container_type = "unknown"

            inventory: dict[
                str,
                Any,
            ] = {
                "valid": False,
                "violations": [],
            }

            if not violations:
                with path.open("rb") as stream:
                    magic = stream.read(4)

                if path.suffix.lower() == ".zip" or magic.startswith(b"PK"):
                    container_type = "zip"

                    inventory = _zip_inventory(
                        path,
                        maximum_zip_members,
                        maximum_name_length,
                    )

                elif path.suffix.lower() == ".gz" or magic.startswith(b"\x1f\x8b"):
                    container_type = "gzip"

                    inventory = _gzip_inventory(path)

                else:
                    container_type = "plain_file"

                    inventory = {
                        "valid": True,
                        "violations": [],
                    }

            raw_inventory_violations = inventory.get("violations")

            if isinstance(
                raw_inventory_violations,
                list,
            ):
                violations.extend(str(value) for value in raw_inventory_violations)

            violations = sorted(set(violations))

            type_counts[container_type] += 1

            ready = not violations

            if ready:
                ready_count += 1

            else:
                blocked_count += 1

            format_candidates = _format_candidates(
                relative_path,
                container_type,
                inventory,
            )

            entries.append(
                {
                    "source_id": (source_id),
                    "artifact_path": (relative_path),
                    "artifact_sha256": (actual_sha256),
                    "container_type": (container_type),
                    "inventory": (inventory),
                    "format_candidates": (format_candidates),
                    "violations": (violations),
                    "container_recon_ready": (ready),
                    "archive_extraction_performed": False,
                    "gzip_decompression_performed": False,
                    "parser_execution_performed": False,
                    "schema_validation_performed": False,
                    "row_validation_performed": False,
                }
            )

            parser_candidates.append(
                {
                    "source_id": (source_id),
                    "artifact_path": (relative_path),
                    "artifact_sha256": (actual_sha256),
                    "container_type": (container_type),
                    "format_candidates": (format_candidates),
                    "evidence_ready": (ready),
                    "parser_contract_approved": False,
                    "parser_execution_permitted": False,
                    "parser_execution_count": 0,
                }
            )

    entries.sort(
        key=lambda item: (
            str(item["source_id"]),
            str(item["artifact_path"]),
        )
    )

    parser_candidates.sort(
        key=lambda item: (
            str(item["source_id"]),
            str(item["artifact_path"]),
        )
    )

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-container-recon-v1"),
        "entry_count": len(entries),
        "zip_container_count": int(
            type_counts.get(
                "zip",
                0,
            )
        ),
        "gzip_container_count": int(
            type_counts.get(
                "gzip",
                0,
            )
        ),
        "plain_file_count": int(
            type_counts.get(
                "plain_file",
                0,
            )
        ),
        "unknown_count": int(
            type_counts.get(
                "unknown",
                0,
            )
        ),
        "recon_ready_count": (ready_count),
        "blocked_count": (blocked_count),
        "entries": entries,
        "archive_extraction_execution_count": 0,
        "gzip_decompression_execution_count": 0,
        "parser_execution_count": 0,
        "schema_validation_execution_count": 0,
        "row_validation_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "automatic_acquisition_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    parser_report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-parser-evidence-v1"),
        "candidate_count": len(parser_candidates),
        "evidence_ready_count": sum(bool(item["evidence_ready"]) for item in parser_candidates),
        "approved_parser_contract_count": 0,
        "parser_execution_count": 0,
        "candidates": (parser_candidates),
        "manual_approval_required": True,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        inventory_path = contract_root / "source_container_inventory.json"

        parser_path = contract_root / "source_parser_evidence.json"

        markdown_path = contract_root / "source_container_recon.md"

        _atomic_json(
            inventory_path,
            report,
        )

        _atomic_json(
            parser_path,
            parser_report,
        )

        _atomic_text(
            markdown_path,
            "\n".join(
                [
                    "# Source Container Reconnaissance",
                    "",
                    (
                        "ZIP central directories and GZIP "
                        "headers are inspected without extraction "
                        "or decompression."
                    ),
                    "",
                    f"- Artifacts: `{len(entries)}`",
                    (f"- ZIP containers: `{report['zip_container_count']}`"),
                    (f"- GZIP containers: `{report['gzip_container_count']}`"),
                    (f"- Plain files: `{report['plain_file_count']}`"),
                    (f"- Recon-ready: `{ready_count}`"),
                    (f"- Blocked: `{blocked_count}`"),
                    "",
                    "- Archive extraction: `false`",
                    "- GZIP decompression: `false`",
                    "- Parser execution: `false`",
                    "",
                ]
            ),
        )

    return {
        "inventory": report,
        "parser_evidence": (parser_report),
    }
