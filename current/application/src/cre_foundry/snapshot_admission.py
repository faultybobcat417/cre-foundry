from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "manual_review_required": True,
    "exact_path_required": True,
    "project_boundary_required": True,
    "regular_file_required": True,
    "symlink_allowed": False,
    "checksum_verification_required": True,
    "source_identity_match_required": True,
    "automatic_snapshot_registration": False,
    "automatic_acquisition": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

PATH_KEYS = (
    "resolved_path",
    "artifact_path",
    "path",
    "declared_path",
)


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


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "source_snapshot_admission.json")

    raw_policy = config.get("policy")

    raw_probe = config.get("artifact_probe")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Snapshot-admission policy must be an object.")

    if not isinstance(
        raw_probe,
        dict,
    ):
        raise RuntimeError("Artifact-probe policy must be an object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Snapshot-admission policy mismatch.")

    _require_nonnegative_int(
        raw_probe.get("header_bytes"),
        "artifact_probe.header_bytes",
    )

    _require_nonnegative_int(
        raw_probe.get("json_parse_limit_bytes"),
        "artifact_probe.json_parse_limit_bytes",
    )

    _require_nonnegative_int(
        raw_probe.get("text_header_limit_bytes"),
        "artifact_probe.text_header_limit_bytes",
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


def _stable_hash(
    payload: object,
) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _is_within(
    path: Path,
    root: Path,
) -> bool:
    try:
        path.relative_to(root)
        return True

    except ValueError:
        return False


def _resolve_project_path(
    raw_path: str,
    project_root: Path,
) -> Path:
    candidate = Path(raw_path).expanduser()

    if not candidate.is_absolute():
        candidate = project_root / candidate

    return candidate.resolve(strict=False)


def _extract_artifact_path(
    artifact: dict[str, Any],
) -> str:
    for key in PATH_KEYS:
        value = artifact.get(key)

        if isinstance(value, str) and value.strip():
            return value

    raise RuntimeError("Referenced artifact has no usable path field.")


def _string_list(
    value: object,
    field_name: str,
) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeError(f"{field_name} must be a list.")

    result = []

    for item in value:
        if not isinstance(item, str):
            raise RuntimeError(f"{field_name} values must be strings.")

        result.append(item)

    return result


def _content_kind(
    path: Path,
    header: bytes,
) -> str:
    suffix = path.suffix.lower()

    if header.startswith(b"PAR1"):
        return "parquet"

    if header.startswith(b"PK\x03\x04"):
        return "zip"

    if header.startswith(b"\x1f\x8b"):
        return "gzip"

    stripped = header.lstrip()

    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return "json_like"

    if suffix in {
        ".csv",
        ".tsv",
    }:
        return "delimited_text"

    if suffix in {
        ".json",
        ".jsonl",
        ".ndjson",
    }:
        return "json_like"

    if suffix in {
        ".txt",
        ".log",
        ".md",
        ".xml",
        ".html",
    }:
        return "text"

    return "binary_or_unknown"


def _probe_artifact(
    path: Path,
    *,
    header_bytes: int,
    json_parse_limit_bytes: int,
    text_header_limit_bytes: int,
) -> dict[str, Any]:
    size_bytes = path.stat().st_size

    with path.open("rb") as stream:
        header = stream.read(header_bytes)

    kind = _content_kind(
        path,
        header,
    )

    probe: dict[str, Any] = {
        "suffix": path.suffix.lower(),
        "size_bytes": size_bytes,
        "actual_sha256": _sha256(path),
        "header_sha256": hashlib.sha256(header).hexdigest(),
        "header_bytes_read": len(header),
        "content_kind": kind,
        "json_parse_attempted": False,
        "json_parse_succeeded": False,
        "json_top_level_type": None,
        "json_top_level_count": None,
        "text_header_decodable": False,
        "text_header_line_count": None,
        "delimited_header": None,
    }

    text_header = header[:text_header_limit_bytes]

    try:
        decoded_header = text_header.decode("utf-8")

    except UnicodeDecodeError:
        decoded_header = None

    if decoded_header is not None:
        probe["text_header_decodable"] = True

        probe["text_header_line_count"] = len(decoded_header.splitlines())

    if kind == "json_like" and size_bytes <= json_parse_limit_bytes:
        probe["json_parse_attempted"] = True

        try:
            parsed: object = json.loads(path.read_text(encoding="utf-8"))

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            parsed = None

        else:
            probe["json_parse_succeeded"] = True

            if isinstance(parsed, dict):
                probe["json_top_level_type"] = "object"

                probe["json_top_level_count"] = len(parsed)

            elif isinstance(parsed, list):
                probe["json_top_level_type"] = "array"

                probe["json_top_level_count"] = len(parsed)

            else:
                probe["json_top_level_type"] = type(parsed).__name__

    if kind == "delimited_text" and decoded_header is not None:
        first_line = decoded_header.splitlines()[0] if decoded_header.splitlines() else ""

        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","

        reader = csv.reader(
            io.StringIO(first_line),
            delimiter=delimiter,
        )

        header_row = next(
            reader,
            [],
        )

        probe["delimited_header"] = header_row

    return probe


def build_snapshot_admission(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    raw_probe = config["artifact_probe"]

    if not isinstance(
        raw_probe,
        dict,
    ):
        raise RuntimeError("Artifact-probe configuration is malformed.")

    header_bytes = _require_nonnegative_int(
        raw_probe.get("header_bytes"),
        "artifact_probe.header_bytes",
    )

    json_parse_limit_bytes = _require_nonnegative_int(
        raw_probe.get("json_parse_limit_bytes"),
        "artifact_probe.json_parse_limit_bytes",
    )

    text_header_limit_bytes = _require_nonnegative_int(
        raw_probe.get("text_header_limit_bytes"),
        "artifact_probe.text_header_limit_bytes",
    )

    review = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_bootstrap_review.json"
    )

    raw_packets = review.get("packets")

    if not isinstance(
        raw_packets,
        list,
    ):
        raise RuntimeError("Bootstrap review has no packet list.")

    expected_packet_count = _require_nonnegative_int(
        review.get("packet_count"),
        "bootstrap packet_count",
    )

    if len(raw_packets) != expected_packet_count:
        raise RuntimeError("Bootstrap packet list count mismatch.")

    packets: list[dict[str, Any]] = []

    replay_entries: list[dict[str, Any]] = []

    ready_count = 0
    blocked_count = 0
    total_artifact_count = 0
    total_bytes = 0

    for packet_index, raw_packet in enumerate(raw_packets):
        if not isinstance(
            raw_packet,
            dict,
        ):
            raise RuntimeError("Bootstrap packet must be an object.")

        packet: dict[str, Any] = {str(key): value for key, value in raw_packet.items()}

        source_id = packet.get("source_id")

        manifest_path_value = packet.get("manifest_path")

        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id
        ):
            raise RuntimeError("Bootstrap packet lacks a valid source ID.")

        if (
            not isinstance(
                manifest_path_value,
                str,
            )
            or not manifest_path_value
        ):
            raise RuntimeError("Bootstrap packet lacks a manifest path.")

        packet_violations: list[str] = []

        review_ready = packet.get("review_ready")

        if review_ready is not True:
            packet_violations.append("bootstrap_packet_not_review_ready")

        existing_violations = _string_list(
            packet.get(
                "violations",
                [],
            ),
            "packet violations",
        )

        if existing_violations:
            packet_violations.append("bootstrap_packet_has_violations")

        manifest_path = _resolve_project_path(
            manifest_path_value,
            project_root,
        )

        if not _is_within(
            manifest_path,
            project_root.resolve(),
        ):
            packet_violations.append("manifest_outside_project_boundary")

        if not manifest_path.exists():
            packet_violations.append("manifest_missing")

        elif not manifest_path.is_file():
            packet_violations.append("manifest_not_regular_file")

        elif manifest_path.is_symlink():
            packet_violations.append("manifest_symlink_not_allowed")

        manifest_probe: (
            dict[
                str,
                Any,
            ]
            | None
        ) = None

        if not packet_violations:
            manifest_probe = _probe_artifact(
                manifest_path,
                header_bytes=header_bytes,
                json_parse_limit_bytes=(json_parse_limit_bytes),
                text_header_limit_bytes=(text_header_limit_bytes),
            )

            declared_manifest_hash = packet.get("manifest_actual_sha256")

            if (
                isinstance(
                    declared_manifest_hash,
                    str,
                )
                and declared_manifest_hash != manifest_probe["actual_sha256"]
            ):
                packet_violations.append("manifest_checksum_changed")

        raw_artifacts = packet.get("referenced_artifacts")

        if not isinstance(
            raw_artifacts,
            list,
        ):
            raise RuntimeError("Packet referenced_artifacts must be a list.")

        artifact_records: list[dict[str, Any]] = []

        for artifact_index, raw_artifact in enumerate(raw_artifacts):
            if not isinstance(
                raw_artifact,
                dict,
            ):
                raise RuntimeError("Referenced artifact must be an object.")

            artifact: dict[str, Any] = {str(key): value for key, value in raw_artifact.items()}

            raw_path = _extract_artifact_path(artifact)

            artifact_path = _resolve_project_path(
                raw_path,
                project_root,
            )

            violations = []

            if not _is_within(
                artifact_path,
                project_root.resolve(),
            ):
                violations.append("artifact_outside_project_boundary")

            if not artifact_path.exists():
                violations.append("artifact_missing")

            elif not artifact_path.is_file():
                violations.append("artifact_not_regular_file")

            elif artifact_path.is_symlink():
                violations.append("artifact_symlink_not_allowed")

            artifact_probe: (
                dict[
                    str,
                    Any,
                ]
                | None
            ) = None

            if not violations:
                artifact_probe = _probe_artifact(
                    artifact_path,
                    header_bytes=(header_bytes),
                    json_parse_limit_bytes=(json_parse_limit_bytes),
                    text_header_limit_bytes=(text_header_limit_bytes),
                )

                expected_sha = artifact.get("actual_sha256")

                if (
                    isinstance(
                        expected_sha,
                        str,
                    )
                    and expected_sha != artifact_probe["actual_sha256"]
                ):
                    violations.append("artifact_checksum_changed")

                expected_size = artifact.get("size_bytes")

                if (
                    isinstance(
                        expected_size,
                        int,
                    )
                    and not isinstance(
                        expected_size,
                        bool,
                    )
                    and expected_size != artifact_probe["size_bytes"]
                ):
                    violations.append("artifact_size_changed")

                total_bytes += int(artifact_probe["size_bytes"])

            relative_path = (
                str(artifact_path.relative_to(project_root.resolve()))
                if _is_within(
                    artifact_path,
                    project_root.resolve(),
                )
                else str(artifact_path)
            )

            artifact_record = {
                "artifact_index": artifact_index,
                "declared_path": raw_path,
                "resolved_relative_path": (relative_path),
                "probe": artifact_probe,
                "violations": violations,
                "admission_ready": not violations,
            }

            artifact_records.append(artifact_record)

            total_artifact_count += 1

            if violations:
                packet_violations.extend(violations)

        packet_violations = sorted(set(packet_violations))

        manifest_hash = str(manifest_probe["actual_sha256"]) if manifest_probe is not None else None

        artifact_hashes = [
            str(record["probe"]["actual_sha256"])
            for record in artifact_records
            if isinstance(
                record.get("probe"),
                dict,
            )
        ]

        bundle_payload = {
            "source_id": source_id,
            "manifest_sha256": manifest_hash,
            "artifact_sha256s": sorted(artifact_hashes),
        }

        bundle_sha256 = _stable_hash(bundle_payload)

        admission_ready = not packet_violations and bool(artifact_records)

        if admission_ready:
            ready_count += 1

        else:
            blocked_count += 1

        admission_packet = {
            "packet_index": packet_index,
            "source_id": source_id,
            "manifest_path": (
                str(manifest_path.relative_to(project_root.resolve()))
                if _is_within(
                    manifest_path,
                    project_root.resolve(),
                )
                else str(manifest_path)
            ),
            "manifest_probe": (manifest_probe),
            "artifact_count": len(artifact_records),
            "artifacts": artifact_records,
            "bundle_sha256": (bundle_sha256),
            "violations": (packet_violations),
            "admission_ready": (admission_ready),
            "manual_approval_required": True,
            "snapshot_registration_permitted": False,
            "snapshot_registration_executed": False,
        }

        packets.append(admission_packet)

        replay_entries.append(
            {
                "source_id": source_id,
                "bundle_sha256": (bundle_sha256),
                "manifest_path": (admission_packet["manifest_path"]),
                "artifact_paths": [record["resolved_relative_path"] for record in artifact_records],
                "artifact_sha256s": sorted(artifact_hashes),
                "replay_metadata_ready": (admission_ready),
                "artifact_copy_performed": False,
                "parser_execution_performed": False,
                "snapshot_registration_performed": False,
            }
        )

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-snapshot-admission-v1"),
        "source_packet_count": len(packets),
        "admission_ready_count": (ready_count),
        "blocked_count": blocked_count,
        "artifact_count": (total_artifact_count),
        "total_referenced_bytes": (total_bytes),
        "packets": packets,
        "all_packets_admission_ready": (ready_count == len(packets) and bool(packets)),
        "manual_approval_required": True,
        "snapshot_registration_permitted": False,
        "snapshot_registration_execution_count": 0,
        "artifact_copy_execution_count": 0,
        "automatic_acquisition": False,
        "policy": EXPECTED_POLICY,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    replay: dict[str, Any] = {
        "model_version": ("cre-foundry-source-replay-fixture-index-v1"),
        "entry_count": len(replay_entries),
        "replay_metadata_ready_count": sum(
            bool(entry["replay_metadata_ready"]) for entry in replay_entries
        ),
        "entries": replay_entries,
        "artifact_copy_execution_count": 0,
        "parser_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    markdown_lines = [
        "# Source Snapshot Admission",
        "",
        ("This report cryptographically revalidates the reviewed bootstrap artifacts."),
        "",
        (f"- Source packets: `{len(packets)}`"),
        (f"- Admission-ready: `{ready_count}`"),
        (f"- Blocked: `{blocked_count}`"),
        (f"- Referenced artifacts: `{total_artifact_count}`"),
        (f"- Total bytes: `{total_bytes}`"),
        "",
        "Snapshot registration remains disabled.",
        "",
    ]

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        report_path = contract_root / "source_snapshot_admission.json"

        replay_path = contract_root / "source_replay_fixture_index.json"

        markdown_path = contract_root / "source_snapshot_admission.md"

        paths = {
            "admission": str(report_path.relative_to(project_root)),
            "replay_index": str(replay_path.relative_to(project_root)),
            "markdown": str(markdown_path.relative_to(project_root)),
        }

        report["contract_paths"] = paths

        replay["contract_paths"] = paths

        _atomic_json(
            report_path,
            report,
        )

        _atomic_json(
            replay_path,
            replay,
        )

        _atomic_text(
            markdown_path,
            "\n".join(markdown_lines),
        )

    return {
        "admission": report,
        "replay": replay,
    }
