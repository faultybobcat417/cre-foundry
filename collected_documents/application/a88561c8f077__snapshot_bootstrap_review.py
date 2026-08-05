from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

PATH_KEY_PATTERN = re.compile(
    r"(?:^|_)(?:path|file|archive|artifact|output)(?:_|$)",
    re.IGNORECASE,
)

CHECKSUM_KEY_PATTERN = re.compile(
    r"(?:sha256|checksum|hash)",
    re.IGNORECASE,
)

SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


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


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _walk_paths_and_checksums(
    value: Any,
    *,
    breadcrumb: str = "$",
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
]:
    paths: list[dict[str, str]] = []
    checksums: list[dict[str, str]] = []

    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key)

            nested_breadcrumb = breadcrumb + "." + key

            is_checksum_key = bool(CHECKSUM_KEY_PATTERN.search(key))

            is_path_key = bool(PATH_KEY_PATTERN.search(key)) and not is_checksum_key

            if isinstance(nested, str) and is_path_key and nested.strip():
                paths.append(
                    {
                        "breadcrumb": nested_breadcrumb,
                        "declared_path": nested,
                    }
                )

            if (
                isinstance(nested, str)
                and is_checksum_key
                and SHA256_PATTERN.fullmatch(nested.strip())
            ):
                checksums.append(
                    {
                        "breadcrumb": nested_breadcrumb,
                        "declared_sha256": (nested.strip().lower()),
                    }
                )

            (
                nested_paths,
                nested_checksums,
            ) = _walk_paths_and_checksums(
                nested,
                breadcrumb=nested_breadcrumb,
            )

            paths.extend(nested_paths)
            checksums.extend(nested_checksums)

    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nested_breadcrumb = breadcrumb + "[" + str(index) + "]"

            (
                nested_paths,
                nested_checksums,
            ) = _walk_paths_and_checksums(
                nested,
                breadcrumb=nested_breadcrumb,
            )

            paths.extend(nested_paths)
            checksums.extend(nested_checksums)

    return (
        paths,
        checksums,
    )


def _resolve_declared_path(
    project_root: Path,
    manifest_path: Path,
    declared_path: str,
) -> tuple[
    Path,
    str,
]:
    expanded = Path(declared_path).expanduser()

    if expanded.is_absolute():
        return (
            expanded.resolve(),
            "absolute",
        )

    candidates = [
        (project_root / expanded).resolve(),
        (manifest_path.parent / expanded).resolve(),
    ]

    for candidate in candidates:
        if candidate.exists():
            return (
                candidate,
                ("project_relative" if candidate == candidates[0] else "manifest_relative"),
            )

    return (
        candidates[0],
        "unresolved_project_relative",
    )


def build_snapshot_bootstrap_review(
    project_root: Path,
    *,
    write_contract: bool = True,
    write_packets: bool = True,
) -> dict[str, Any]:
    bootstrap = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_bootstrap.json"
    )

    raw_candidates = bootstrap.get("exact_candidates")

    if not isinstance(
        raw_candidates,
        list,
    ):
        raise RuntimeError("Bootstrap contract contains no exact candidate list.")

    packet_root = project_root / "outputs" / "source_snapshot_bootstrap_review"

    if write_packets:
        packet_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    packets: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    total_referenced_bytes = 0

    for index, raw_candidate in enumerate(raw_candidates):
        if not isinstance(
            raw_candidate,
            dict,
        ):
            violations.append(
                {
                    "candidate_index": index,
                    "violation": ("candidate_not_object"),
                }
            )
            continue

        candidate: dict[str, Any] = {str(key): value for key, value in raw_candidate.items()}

        source_id = candidate.get("source_id")

        raw_manifest_path = candidate.get("path")

        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id
        ):
            violations.append(
                {
                    "candidate_index": index,
                    "violation": ("invalid_source_id"),
                }
            )
            continue

        if (
            not isinstance(
                raw_manifest_path,
                str,
            )
            or not raw_manifest_path
        ):
            violations.append(
                {
                    "candidate_index": index,
                    "source_id": source_id,
                    "violation": ("invalid_manifest_path"),
                }
            )
            continue

        manifest_path = Path(raw_manifest_path).expanduser().resolve()

        candidate_violations = []

        if not manifest_path.is_file():
            candidate_violations.append("manifest_missing")

            packet = {
                "candidate_index": index,
                "source_id": source_id,
                "manifest_path": str(manifest_path),
                "violations": (candidate_violations),
                "review_ready": False,
                "registration_permitted": False,
            }

            packets.append(packet)

            continue

        try:
            manifest = _load_object(manifest_path)

        except Exception as exception:
            candidate_violations.append("manifest_invalid_json_object")

            packet = {
                "candidate_index": index,
                "source_id": source_id,
                "manifest_path": str(manifest_path),
                "manifest_error_type": type(exception).__name__,
                "manifest_error_message": str(exception),
                "violations": (candidate_violations),
                "review_ready": False,
                "registration_permitted": False,
            }

            packets.append(packet)

            continue

        manifest_source_id = manifest.get("source_id")

        if manifest_source_id is not None and str(manifest_source_id) != source_id:
            candidate_violations.append("manifest_source_id_mismatch")

        (
            declared_paths,
            declared_checksums,
        ) = _walk_paths_and_checksums(manifest)

        artifact_records = []
        seen_paths: set[str] = set()

        for declared in declared_paths:
            declared_path = declared["declared_path"]

            resolved_path, resolution = _resolve_declared_path(
                project_root,
                manifest_path,
                declared_path,
            )

            resolved_string = str(resolved_path)

            if resolved_string in seen_paths:
                continue

            seen_paths.add(resolved_string)

            try:
                resolved_path.relative_to(project_root)

                inside_project = True

            except ValueError:
                inside_project = False

            exists = resolved_path.is_file()

            record: dict[str, Any] = {
                "breadcrumb": declared["breadcrumb"],
                "declared_path": declared_path,
                "resolved_path": (resolved_string),
                "resolution": resolution,
                "inside_project": (inside_project),
                "exists": exists,
            }

            if not inside_project:
                candidate_violations.append("referenced_artifact_outside_project")

            if exists:
                size_bytes = resolved_path.stat().st_size

                actual_sha256 = _sha256(resolved_path)

                total_referenced_bytes += size_bytes

                record.update(
                    {
                        "size_bytes": (size_bytes),
                        "actual_sha256": (actual_sha256),
                    }
                )

            else:
                candidate_violations.append("referenced_artifact_missing")

            artifact_records.append(record)

        actual_hashes = {
            str(record["actual_sha256"])
            for record in artifact_records
            if record.get("actual_sha256")
        }

        declared_hashes = {item["declared_sha256"] for item in declared_checksums}

        checksum_matches = sorted(actual_hashes & declared_hashes)

        packet = {
            "candidate_index": index,
            "source_id": source_id,
            "manifest_path": str(manifest_path),
            "manifest_size_bytes": (manifest_path.stat().st_size),
            "manifest_actual_sha256": (_sha256(manifest_path)),
            "manifest_source_id": (manifest_source_id),
            "declared_path_count": len(declared_paths),
            "referenced_artifact_count": len(artifact_records),
            "declared_checksum_count": len(declared_checksums),
            "declared_checksum_match_count": len(checksum_matches),
            "checksum_matches": (checksum_matches),
            "declared_checksums": (declared_checksums),
            "referenced_artifacts": (artifact_records),
            "violations": sorted(set(candidate_violations)),
            "review_ready": (not candidate_violations),
            "registration_permitted": False,
        }

        packets.append(packet)

        if write_packets:
            packet_name = (
                f"{index + 1:02d}_"
                + re.sub(
                    r"[^A-Za-z0-9_.-]+",
                    "_",
                    source_id,
                )
                + ".json"
            )

            packet_path = packet_root / packet_name

            _atomic_json(
                packet_path,
                packet,
            )

    for packet in packets:
        raw_packet_violations: object = packet.get(
            "violations",
            [],
        )

        if not isinstance(
            raw_packet_violations,
            list,
        ):
            raise RuntimeError("Packet violations must be a list.")

        for raw_violation in raw_packet_violations:
            if not isinstance(
                raw_violation,
                str,
            ):
                raise RuntimeError("Every packet violation must be a string.")

            violations.append(
                {
                    "candidate_index": packet["candidate_index"],
                    "source_id": packet["source_id"],
                    "violation": raw_violation,
                }
            )

    ready_count = sum(bool(packet["review_ready"]) for packet in packets)

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-snapshot-bootstrap-review-v1"),
        "candidate_count": len(raw_candidates),
        "packet_count": len(packets),
        "review_ready_count": (ready_count),
        "blocked_review_count": (len(packets) - ready_count),
        "violation_count": len(violations),
        "violations": violations,
        "total_referenced_bytes": (total_referenced_bytes),
        "packets": packets,
        "automatic_registration_performed": False,
        "registration_execution_count": 0,
        "registration_permitted": False,
        "human_approval_required": True,
        "operating_mode": "shadow",
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    if write_packets:
        report["packet_root"] = str(packet_root.relative_to(project_root))

        _atomic_json(
            packet_root / "manifest.json",
            report,
        )

    if write_contract:
        contract_path = (
            project_root / "docs" / "data_contracts" / "source_snapshot_bootstrap_review.json"
        )

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
