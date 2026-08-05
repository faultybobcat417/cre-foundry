from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only_inputs_required": True,
    "human_completion_required": True,
    "approval_invention_forbidden": True,
    "client_value_invention_forbidden": True,
    "executable_command_generation_enabled": False,
    "archive_generation_enabled": False,
    "database_access_enabled": False,
    "database_write_enabled": False,
    "snapshot_registration_enabled": False,
    "source_schedule_activation_enabled": False,
    "automatic_acquisition_enabled": False,
    "persistent_outcome_ledger_enabled": False,
    "outcome_event_insertion_enabled": False,
    "point_in_time_materialization_enabled": False,
    "model_training_enabled": False,
    "backtest_execution_enabled": False,
    "pilot_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
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


def _object_list(
    value: object,
    *,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(f"{label} must be a list.")

    result: list[dict[str, Any]] = []

    for index, raw_item in enumerate(value):
        if not isinstance(
            raw_item,
            dict,
        ):
            raise RuntimeError(f"{label}[{index}] must be an object.")

        result.append({str(key): item_value for key, item_value in raw_item.items()})

    return result


def _string_list(
    value: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(f"{label} must be a list.")

    result: list[str] = []

    for index, raw_item in enumerate(value):
        if not isinstance(
            raw_item,
            str,
        ):
            raise RuntimeError(f"{label}[{index}] must be a string.")

        result.append(raw_item)

    return result


def _index_unique(
    rows: list[dict[str, Any]],
    *,
    key_name: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for row in rows:
        raw_key = row.get(key_name)

        if not isinstance(
            raw_key,
            str,
        ):
            raise RuntimeError(f"{label} lacks {key_name}.")

        if raw_key in result:
            raise RuntimeError(f"Duplicate {label}: {raw_key}")

        result[raw_key] = row

    return result


def _stable_digest(
    value: object,
) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(canonical).hexdigest()


def _file_digest(
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


def _is_complete(
    row: dict[str, Any] | None,
    *,
    field: str,
) -> bool:
    return bool(row and row.get(field) is True)


def build_human_input_workbench(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "human_input_workbench.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Workbench policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Workbench policy mismatch.")

    review_source_id = str(config["review_source_id"])

    decision_bundle_path = str(config["decision_bundle_path"])

    client_input_order = _string_list(
        config.get("client_input_order"),
        label="client_input_order",
    )

    codex_contract_artifacts = _string_list(
        config.get("codex_contract_artifacts"),
        label="codex_contract_artifacts",
    )

    contract_root = project_root / "docs" / "data_contracts"

    packets = _load_object(contract_root / "governance_approval_packet_template.json")

    questionnaire = _load_object(contract_root / "client_input_questionnaire.json")

    decision_validation = _load_object(contract_root / "manual_decision_validation.json")

    activation_summary = _load_object(contract_root / "manual_activation_envelope_summary.json")

    historical_envelope = _load_object(
        contract_root / "historical_registration_execution_envelope.json"
    )

    outcome_envelope = _load_object(contract_root / "outcome_ledger_bootstrap_envelope.json")

    codex_gate_graph = _load_object(contract_root / "codex_handoff_gate_graph.json")

    decision_bundle = _load_object(project_root / decision_bundle_path)

    packet_rows = _object_list(
        packets.get("packets"),
        label="governance packets",
    )

    questionnaire_rows = _object_list(
        questionnaire.get("sections"),
        label="questionnaire sections",
    )

    source_result_rows = _object_list(
        decision_validation.get("source_results"),
        label="source validation results",
    )

    client_result_rows = _object_list(
        decision_validation.get("client_results"),
        label="client validation results",
    )

    source_decision_rows = _object_list(
        decision_bundle.get("source_decisions"),
        label="source decisions",
    )

    client_input_rows = _object_list(
        decision_bundle.get("client_inputs"),
        label="client inputs",
    )

    packet_by_source = _index_unique(
        packet_rows,
        key_name="source_id",
        label="governance packet",
    )

    source_result_by_source = _index_unique(
        source_result_rows,
        key_name="source_id",
        label="source validation result",
    )

    source_decision_by_source = _index_unique(
        source_decision_rows,
        key_name="source_id",
        label="source decision",
    )

    questionnaire_by_id = _index_unique(
        questionnaire_rows,
        key_name="input_id",
        label="questionnaire section",
    )

    client_result_by_id = _index_unique(
        client_result_rows,
        key_name="input_id",
        label="client validation result",
    )

    client_input_by_id = _index_unique(
        client_input_rows,
        key_name="input_id",
        label="client input",
    )

    if review_source_id not in packet_by_source:
        raise RuntimeError("Review source lacks a governance packet.")

    review_packet = packet_by_source[review_source_id]

    source_validation = source_result_by_source.get(review_source_id)

    current_source_decision = source_decision_by_source.get(review_source_id)

    evidence = review_packet.get("evidence")

    if not isinstance(
        evidence,
        dict,
    ):
        raise RuntimeError("Review packet evidence must be an object.")

    normalized_evidence = {str(key): value for key, value in evidence.items()}

    evidence_digest = review_packet.get("evidence_bundle_digest")

    if (
        not isinstance(
            evidence_digest,
            str,
        )
        or len(evidence_digest) != 64
    ):
        raise RuntimeError("Review packet evidence digest is invalid.")

    candidate_record_keys = _string_list(
        normalized_evidence.get(
            "candidate_record_keys",
            [],
        ),
        label="candidate_record_keys",
    )

    candidate_temporal_fields = _string_list(
        normalized_evidence.get(
            "candidate_temporal_fields",
            [],
        ),
        label="candidate_temporal_fields",
    )

    source_blockers: list[str] = []

    if source_validation:
        source_blockers = _string_list(
            source_validation.get(
                "blockers",
                [],
            ),
            label="review source blockers",
        )

    review_workbook: dict[str, Any] = {
        "model_version": ("cre-foundry-brampton-permit-review-workbook-v1"),
        "source_id": review_source_id,
        "evidence_bundle_digest": evidence_digest,
        "evidence": normalized_evidence,
        "candidate_record_keys": (candidate_record_keys),
        "candidate_temporal_fields": (candidate_temporal_fields),
        "review_questions": [
            {
                "decision_id": ("parser_contract_approved"),
                "question": ("Does the parser reproduce the exact artifact deterministically?"),
                "current_value": (
                    None
                    if current_source_decision is None
                    else current_source_decision.get("parser_contract_approved")
                ),
            },
            {
                "decision_id": ("schema_contract_approved"),
                "question": (
                    "Does the observed field set match the intended permit dataset semantics?"
                ),
                "current_value": (
                    None
                    if current_source_decision is None
                    else current_source_decision.get("schema_contract_approved")
                ),
            },
            {
                "decision_id": ("approved_record_key"),
                "question": (
                    "Which reviewed candidate uniquely and stably identifies a permit record?"
                ),
                "candidate_values": (candidate_record_keys),
                "current_value": (
                    None
                    if current_source_decision is None
                    else current_source_decision.get("approved_record_key")
                ),
            },
            {
                "decision_id": ("approved_temporal_fields"),
                "question": (
                    "Which fields are valid event or source timestamps for point-in-time use?"
                ),
                "candidate_values": (candidate_temporal_fields),
                "current_value": (
                    []
                    if current_source_decision is None
                    else current_source_decision.get(
                        "approved_temporal_fields",
                        [],
                    )
                ),
            },
            {
                "decision_id": ("capture_policy_approved"),
                "question": (
                    "Is the proposed publication-aligned capture policy operationally valid?"
                ),
                "current_value": (
                    None
                    if current_source_decision is None
                    else current_source_decision.get("capture_policy_approved")
                ),
            },
            {
                "decision_id": ("change_contract_approved"),
                "question": (
                    "Are the permitted change types and future-information protections correct?"
                ),
                "current_value": (
                    None
                    if current_source_decision is None
                    else current_source_decision.get("change_contract_approved")
                ),
            },
            {
                "decision_id": ("registration_approved"),
                "question": (
                    "May one checksum-pinned snapshot proceed to the separately authorized dry run?"
                ),
                "current_value": (
                    None
                    if current_source_decision is None
                    else current_source_decision.get("registration_approved")
                ),
            },
        ],
        "reviewer_attribution_required": ["reviewer_id", "reviewed_at", "evidence_reference"],
        "current_decision": (current_source_decision),
        "decision_complete": _is_complete(
            source_validation,
            field="decision_complete",
        ),
        "current_blockers": source_blockers,
        "automatic_approval": False,
        "registration_execution_enabled": False,
    }

    client_sections: list[dict[str, Any]] = []

    for input_id in client_input_order:
        definition = questionnaire_by_id.get(input_id)

        if definition is None:
            raise RuntimeError(f"Missing questionnaire section: {input_id}")

        required_fields = _string_list(
            definition.get("required_fields"),
            label=(f"{input_id}.required_fields"),
        )

        current_input = client_input_by_id.get(input_id)

        validation_result = client_result_by_id.get(input_id)

        answer_template = {required_field: None for required_field in required_fields}

        missing_required_fields = list(required_fields)

        blockers: list[str] = []

        input_complete = False

        if validation_result:
            missing_required_fields = _string_list(
                validation_result.get(
                    "missing_required_fields",
                    required_fields,
                ),
                label=(f"{input_id}.missing_required_fields"),
            )

            blockers = _string_list(
                validation_result.get(
                    "blockers",
                    [],
                ),
                label=(f"{input_id}.blockers"),
            )

            input_complete = bool(validation_result.get("input_complete") is True)

        client_sections.append(
            {
                "input_id": input_id,
                "question": definition.get("question"),
                "required_fields": (required_fields),
                "answer_template": (answer_template),
                "current_input": current_input,
                "missing_required_fields": (missing_required_fields),
                "blockers": blockers,
                "input_complete": input_complete,
                "human_confirmation_required": True,
            }
        )

    client_workbook: dict[str, Any] = {
        "model_version": ("cre-foundry-client-answer-workbook-v1"),
        "questionnaire_digest": (questionnaire.get("questionnaire_digest")),
        "section_count": len(client_sections),
        "completed_section_count": sum(
            bool(section["input_complete"]) for section in client_sections
        ),
        "sections": client_sections,
        "confirmation_fields": ["confirmed", "confirmed_by", "confirmed_at", "evidence_reference"],
        "automatic_completion": False,
        "client_value_invention": False,
    }

    source_diffs: list[dict[str, Any]] = []

    for source_id in sorted(packet_by_source):
        packet = packet_by_source[source_id]

        decision = source_decision_by_source.get(source_id)

        validation_result = source_result_by_source.get(source_id)

        expected_digest = packet.get("evidence_bundle_digest")

        supplied_digest = None if decision is None else decision.get("evidence_bundle_digest")

        source_diffs.append(
            {
                "source_id": source_id,
                "decision_present": (decision is not None),
                "evidence_digest_match": bool(expected_digest == supplied_digest),
                "decision_complete": _is_complete(
                    validation_result,
                    field="decision_complete",
                ),
                "stale_evidence": bool(
                    validation_result and validation_result.get("stale_evidence") is True
                ),
                "blockers": (
                    []
                    if validation_result is None
                    else validation_result.get(
                        "blockers",
                        [],
                    )
                ),
            }
        )

    client_diffs = [
        {
            "input_id": section["input_id"],
            "input_complete": section["input_complete"],
            "missing_required_fields": section["missing_required_fields"],
            "blockers": section["blockers"],
        }
        for section in client_sections
    ]

    decision_diff: dict[str, Any] = {
        "model_version": ("cre-foundry-governance-decision-diff-v1"),
        "decision_bundle_digest": (_stable_digest(decision_bundle)),
        "source_decision_count": len(source_diffs),
        "source_decision_complete_count": sum(
            bool(row["decision_complete"]) for row in source_diffs
        ),
        "stale_source_decision_count": sum(bool(row["stale_evidence"]) for row in source_diffs),
        "client_input_count": len(client_diffs),
        "client_input_complete_count": sum(bool(row["input_complete"]) for row in client_diffs),
        "source_diffs": source_diffs,
        "client_diffs": client_diffs,
        "mutation_performed": False,
    }

    historical_ready = bool(historical_envelope.get("dry_run_ready") is True)

    outcome_ready = bool(outcome_envelope.get("ephemeral_bootstrap_ready") is True)

    codex_contract_ready = bool(codex_gate_graph.get("codex_contract_handoff_ready") is True)

    codex_final_ready = bool(codex_gate_graph.get("codex_final_product_handoff_ready") is True)

    command_templates: dict[str, Any] = {
        "model_version": ("cre-foundry-gate-driven-command-templates-v1"),
        "commands": [
            {
                "command_id": ("validate_governance_decisions"),
                "purpose": (
                    "Rebuild the manual activation state after reviewed inputs are recorded."
                ),
                "argv": ["uv", "run", "cre-foundry", "build-manual-activation-envelopes"],
                "implementation_present": True,
                "generation_ready": True,
                "execution_enabled": False,
            },
            {
                "command_id": ("first_historical_registration_dry_run"),
                "purpose": (
                    "Future one-source, one-snapshot dry-run registration after named approval."
                ),
                "argv": [],
                "implementation_present": False,
                "generation_ready": historical_ready,
                "execution_enabled": False,
                "blockers": historical_envelope.get(
                    "execution_blockers",
                    [],
                ),
            },
            {
                "command_id": ("outcome_ledger_ephemeral_bootstrap"),
                "purpose": ("Future disposable outcome-ledger bootstrap after all client inputs."),
                "argv": [],
                "implementation_present": False,
                "generation_ready": outcome_ready,
                "execution_enabled": False,
                "blockers": outcome_envelope.get(
                    "execution_blockers",
                    [],
                ),
            },
            {
                "command_id": ("codex_contract_bundle"),
                "purpose": ("Future contract-only Codex handoff after the five client inputs."),
                "argv": [],
                "implementation_present": False,
                "generation_ready": (codex_contract_ready),
                "execution_enabled": False,
            },
        ],
        "executable_script_created": False,
        "subprocess_execution_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
    }

    artifact_rows: list[dict[str, Any]] = []

    for relative_path in codex_contract_artifacts:
        artifact_path = project_root / relative_path

        artifact_rows.append(
            {
                "path": relative_path,
                "exists": artifact_path.is_file(),
                "sha256": (_file_digest(artifact_path) if artifact_path.is_file() else None),
            }
        )

    codex_manifest: dict[str, Any] = {
        "model_version": ("cre-foundry-codex-contract-bundle-manifest-v1"),
        "artifact_count": len(artifact_rows),
        "present_artifact_count": sum(bool(row["exists"]) for row in artifact_rows),
        "artifacts": artifact_rows,
        "contract_handoff_ready": (codex_contract_ready),
        "final_product_handoff_ready": (codex_final_ready),
        "bundle_archive_created": False,
        "archive_generation_enabled": False,
        "archive_path": None,
        "archive_sha256": None,
    }

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-human-input-workbench-v1"),
        "review_source_id": review_source_id,
        "review_source_decision_complete": (review_workbook["decision_complete"]),
        "review_source_blocker_count": len(source_blockers),
        "client_section_count": (client_workbook["section_count"]),
        "client_section_complete_count": (client_workbook["completed_section_count"]),
        "source_decision_complete_count": (decision_diff["source_decision_complete_count"]),
        "stale_source_decision_count": (decision_diff["stale_source_decision_count"]),
        "historical_dry_run_generation_ready": (historical_ready),
        "outcome_bootstrap_generation_ready": (outcome_ready),
        "codex_contract_handoff_ready": (codex_contract_ready),
        "codex_final_product_handoff_ready": (codex_final_ready),
        "decision_bundle_digest": (decision_diff["decision_bundle_digest"]),
        "decision_bundle_mutation_count": 0,
        "automatic_approval_count": 0,
        "client_value_invention_count": 0,
        "executable_script_creation_count": 0,
        "archive_creation_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "outcome_event_insertion_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "policy": EXPECTED_POLICY,
        "activation_summary_digest": (_stable_digest(activation_summary)),
    }

    if write_contracts:
        _atomic_json(
            contract_root / "brampton_permit_review_workbook.json",
            review_workbook,
        )

        review_lines = [
            "# Brampton Permit Source Review",
            "",
            (
                "This packet must be reviewed by an "
                "identified person. No decision is "
                "automatically approved."
            ),
            "",
            (f"- Source: `{review_source_id}`"),
            (f"- Evidence digest: `{evidence_digest}`"),
            (f"- Decision complete: `{str(review_workbook['decision_complete']).lower()}`"),
            "",
            "## Candidate record keys",
            "",
        ]

        review_lines.extend(f"- `{value}`" for value in candidate_record_keys)

        review_lines.extend(
            [
                "",
                "## Candidate temporal fields",
                "",
            ]
        )

        review_lines.extend(f"- `{value}`" for value in candidate_temporal_fields)

        review_lines.extend(
            [
                "",
                "## Required decisions",
                "",
            ]
        )

        for question in review_workbook["review_questions"]:
            review_lines.extend(
                [
                    (f"### {question['decision_id']}"),
                    "",
                    str(question["question"]),
                    "",
                    (f"- Current value: `{question.get('current_value')}`"),
                    "",
                ]
            )

        review_lines.extend(
            [
                "## Current blockers",
                "",
            ]
        )

        review_lines.extend(f"- `{value}`" for value in source_blockers)

        review_lines.extend(
            [
                "",
                "- Automatic approval: `false`",
                "- Registration execution: `false`",
                "",
            ]
        )

        _atomic_text(
            contract_root / "brampton_permit_review_workbook.md",
            "\n".join(review_lines),
        )

        _atomic_json(
            contract_root / "client_answer_workbook.json",
            client_workbook,
        )

        client_lines = [
            "# Client Answer Workbook",
            "",
            (
                "Each section requires an authoritative "
                "value, named confirmer, timestamp and "
                "evidence reference."
            ),
            "",
        ]

        for index, section in enumerate(
            client_sections,
            start=1,
        ):
            client_lines.extend(
                [
                    (f"## {index}. {section['input_id']}"),
                    "",
                    str(section["question"]),
                    "",
                    "Required fields:",
                    "",
                ]
            )

            client_lines.extend(f"- `{field}`" for field in section["required_fields"])

            client_lines.extend(
                [
                    "",
                    (f"- Complete: `{str(section['input_complete']).lower()}`"),
                    (f"- Missing fields: `{section['missing_required_fields']}`"),
                    (f"- Blockers: `{section['blockers']}`"),
                    "",
                ]
            )

        _atomic_text(
            contract_root / "client_answer_workbook.md",
            "\n".join(client_lines),
        )

        _atomic_json(
            contract_root / "governance_decision_diff.json",
            decision_diff,
        )

        _atomic_json(
            contract_root / "gate_driven_command_templates.json",
            command_templates,
        )

        _atomic_json(
            contract_root / "codex_contract_bundle_manifest.json",
            codex_manifest,
        )

        _atomic_json(
            contract_root / "human_input_workbench_summary.json",
            summary,
        )

        _atomic_text(
            contract_root / "human_input_workbench.md",
            "\n".join(
                [
                    "# Human Input Workbench",
                    "",
                    (
                        "This workbench operationalizes the "
                        "remaining reviewer and client decisions "
                        "without granting approval or execution."
                    ),
                    "",
                    (f"- Review source: `{review_source_id}`"),
                    (
                        "- Review decision complete: "
                        f"`{str(summary['review_source_decision_complete']).lower()}`"
                    ),
                    (
                        "- Completed source decisions: "
                        f"`{summary['source_decision_complete_count']}`"
                    ),
                    (f"- Completed client sections: `{summary['client_section_complete_count']}`"),
                    (f"- Historical generation ready: `{str(historical_ready).lower()}`"),
                    (f"- Outcome generation ready: `{str(outcome_ready).lower()}`"),
                    (f"- Codex contract handoff ready: `{str(codex_contract_ready).lower()}`"),
                    (f"- Codex final handoff ready: `{str(codex_final_ready).lower()}`"),
                    "",
                    "- Automatic approvals: `0`",
                    "- Invented client values: `0`",
                    "- Executable scripts created: `0`",
                    "- Archives created: `0`",
                    "- Database accesses: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Model training executions: `0`",
                    "- Outreach executions: `0`",
                    "",
                ]
            ),
        )

    return {
        "summary": summary,
        "review_workbook": review_workbook,
        "client_workbook": client_workbook,
        "decision_diff": decision_diff,
        "command_templates": command_templates,
        "codex_manifest": codex_manifest,
    }
