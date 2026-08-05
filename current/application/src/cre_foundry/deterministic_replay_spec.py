from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "metadata_only": True,
    "canonical_json_required": True,
    "checksum_pin_required": True,
    "relative_paths_required": True,
    "parser_contract_approval_required": True,
    "temporal_approval_required": True,
    "registration_approval_required": True,
    "artifact_copy_enabled": False,
    "parser_execution_enabled": False,
    "row_materialization_enabled": False,
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

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _stable_hash(
    payload: object,
) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _load_config(
    project_root: Path,
) -> None:
    config = _load_object(project_root / "config" / "deterministic_replay_spec.json")

    raw_policy = config.get("policy")

    if not isinstance(raw_policy, dict):
        raise RuntimeError("Replay policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Replay policy mismatch.")


def build_deterministic_replay_spec(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    _load_config(project_root)

    admission = _load_object(
        project_root / "docs" / "data_contracts" / "source_snapshot_admission.json"
    )

    review = _load_object(
        project_root / "docs" / "data_contracts" / "snapshot_registration_review.json"
    )

    probe = _load_object(project_root / "docs" / "data_contracts" / "bounded_parser_probe.json")

    raw_packets = admission.get("packets")

    raw_candidates = review.get("candidates")

    raw_probe_entries = probe.get("entries")

    if not isinstance(raw_packets, list):
        raise RuntimeError("Admission packets must be a list.")

    if not isinstance(raw_candidates, list):
        raise RuntimeError("Registration candidates must be a list.")

    if not isinstance(
        raw_probe_entries,
        list,
    ):
        raise RuntimeError("Probe entries must be a list.")

    packet_by_source: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_packet in raw_packets:
        if not isinstance(raw_packet, dict):
            raise RuntimeError("Admission packet must be an object.")

        source_id = raw_packet.get("source_id")

        if not isinstance(source_id, str):
            raise RuntimeError("Admission packet lacks source_id.")

        packet_by_source[source_id] = {str(key): value for key, value in raw_packet.items()}

    probe_by_artifact: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_entry in raw_probe_entries:
        if not isinstance(raw_entry, dict):
            raise RuntimeError("Probe entry must be an object.")

        artifact_path = raw_entry.get("artifact_path")

        if not isinstance(
            artifact_path,
            str,
        ):
            raise RuntimeError("Probe entry lacks artifact_path.")

        probe_by_artifact[artifact_path] = {str(key): value for key, value in raw_entry.items()}

    specifications: list[dict[str, Any]] = []

    for raw_candidate in raw_candidates:
        if not isinstance(
            raw_candidate,
            dict,
        ):
            raise RuntimeError("Registration candidate must be an object.")

        candidate = {str(key): value for key, value in raw_candidate.items()}

        source_id = candidate.get("source_id")

        if not isinstance(
            source_id,
            str,
        ):
            raise RuntimeError("Registration candidate lacks source_id.")

        packet = packet_by_source.get(source_id)

        if packet is None:
            raise RuntimeError(f"No admission packet for {source_id}.")

        raw_artifacts = candidate.get("artifacts")

        if not isinstance(raw_artifacts, list):
            raise RuntimeError("Candidate artifacts must be a list.")

        artifact_specs: list[dict[str, Any]] = []

        replay_blockers = set(
            str(value)
            for value in candidate.get(
                "execution_blockers",
                [],
            )
            if isinstance(value, str)
        )

        for raw_artifact in raw_artifacts:
            if not isinstance(
                raw_artifact,
                dict,
            ):
                raise RuntimeError("Candidate artifact must be an object.")

            artifact_path = raw_artifact.get("artifact_path")

            artifact_sha256 = raw_artifact.get("artifact_sha256")

            if not isinstance(
                artifact_path,
                str,
            ):
                raise RuntimeError("Candidate artifact lacks path.")

            if not isinstance(
                artifact_sha256,
                str,
            ):
                raise RuntimeError("Candidate artifact lacks SHA-256.")

            if Path(artifact_path).is_absolute():
                raise RuntimeError("Replay artifact path must be relative.")

            probe_entry = probe_by_artifact.get(artifact_path)

            if probe_entry is None:
                replay_blockers.add("bounded_probe_missing")

                recognized_formats: list[str] = []
                probe_digest = None
                probe_completed = False

            else:
                raw_formats = probe_entry.get("recognized_formats")

                recognized_formats = (
                    [str(value) for value in raw_formats]
                    if isinstance(
                        raw_formats,
                        list,
                    )
                    else []
                )

                probe_digest = _stable_hash(probe_entry.get("probe_result"))

                probe_completed = bool(probe_entry.get("probe_completed"))

                if not probe_completed:
                    replay_blockers.add("bounded_probe_incomplete")

            artifact_specs.append(
                {
                    "artifact_path": (artifact_path),
                    "artifact_sha256": (artifact_sha256),
                    "container_type": (raw_artifact.get("container_type")),
                    "recognized_formats": (recognized_formats),
                    "bounded_probe_digest": (probe_digest),
                    "bounded_probe_completed": (probe_completed),
                    "parser_contract_approved": False,
                    "parser_execution_permitted": False,
                }
            )

        logical_spec = {
            "source_id": source_id,
            "registration_request_id": (candidate.get("registration_request_id")),
            "bundle_sha256": (candidate.get("bundle_sha256")),
            "manifest_path": (candidate.get("manifest_path")),
            "manifest_sha256": (
                packet.get(
                    "manifest_probe",
                    {},
                ).get("actual_sha256")
                if isinstance(
                    packet.get("manifest_probe"),
                    dict,
                )
                else None
            ),
            "temporal_evidence_status": (candidate.get("temporal_evidence_status")),
            "timestamp_candidates": (candidate.get("timestamp_candidates")),
            "artifacts": artifact_specs,
            "pipeline_stages": [
                {
                    "stage": ("integrity_revalidation"),
                    "mode": "required",
                    "execution_enabled": False,
                },
                {
                    "stage": ("container_open"),
                    "mode": "bounded_read_only",
                    "execution_enabled": False,
                },
                {
                    "stage": ("bounded_parser_probe"),
                    "mode": "bounded_read_only",
                    "execution_enabled": False,
                },
                {
                    "stage": ("parser_contract_gate"),
                    "mode": "manual_approval",
                    "execution_enabled": False,
                },
                {
                    "stage": ("temporal_semantics_gate"),
                    "mode": "manual_approval",
                    "execution_enabled": False,
                },
                {
                    "stage": ("ephemeral_transaction_preflight"),
                    "mode": "disposable_clone",
                    "execution_enabled": False,
                },
                {
                    "stage": ("registration_approval_gate"),
                    "mode": "manual_approval",
                    "execution_enabled": False,
                },
                {
                    "stage": ("authoritative_registration"),
                    "mode": "disabled",
                    "execution_enabled": False,
                },
            ],
            "expected_invariants": {
                "artifact_checksum_unchanged": True,
                "manifest_checksum_unchanged": True,
                "source_identity_unchanged": True,
                "artifact_count_unchanged": True,
                "authoritative_database_unchanged": True,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
        }

        replay_id = "replay_" + _stable_hash(logical_spec)[:24]

        replay_ready = bool(candidate.get("ready_for_human_review")) and all(
            bool(artifact["bounded_probe_completed"]) for artifact in artifact_specs
        )

        specifications.append(
            {
                "replay_id": replay_id,
                "source_id": source_id,
                "logical_specification": (logical_spec),
                "specification_sha256": (_stable_hash(logical_spec)),
                "replay_ready": (replay_ready),
                "execution_blockers": (sorted(replay_blockers)),
                "artifact_copy_performed": False,
                "parser_execution_performed": False,
                "row_materialization_performed": False,
                "snapshot_registration_performed": False,
            }
        )

    specifications.sort(key=lambda item: str(item["source_id"]))

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-deterministic-replay-spec-v1"),
        "specification_count": len(specifications),
        "replay_ready_count": sum(
            bool(specification["replay_ready"]) for specification in specifications
        ),
        "blocked_count": sum(
            not bool(specification["replay_ready"]) for specification in specifications
        ),
        "specifications": specifications,
        "duplicate_replay_id_count": (
            len(specifications)
            - len({specification["replay_id"] for specification in specifications})
        ),
        "artifact_copy_execution_count": 0,
        "parser_execution_count": 0,
        "row_materialization_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "automatic_acquisition_execution_count": 0,
        "browser_execution_count": 0,
        "computer_vision_execution_count": 0,
        "opportunity_ranked": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        report_path = contract_root / "deterministic_replay_spec.json"

        markdown_path = contract_root / "deterministic_replay_spec.md"

        _atomic_json(
            report_path,
            report,
        )

        _atomic_text(
            markdown_path,
            "\n".join(
                [
                    "# Deterministic Replay Specifications",
                    "",
                    (
                        "Every source bundle is pinned to exact "
                        "manifest, artifact and probe checksums."
                    ),
                    "",
                    (f"- Specifications: `{report['specification_count']}`"),
                    (f"- Replay-ready metadata: `{report['replay_ready_count']}`"),
                    (f"- Duplicate replay IDs: `{report['duplicate_replay_id_count']}`"),
                    "",
                    "- Artifact copying: `false`",
                    "- Parser execution: `false`",
                    "- Row materialization: `false`",
                    "- Snapshot registration: `false`",
                    "",
                ]
            ),
        )

    return report
