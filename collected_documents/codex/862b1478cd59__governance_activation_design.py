from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "templates_only": True,
    "evidence_digest_required": True,
    "manual_source_approval_required": True,
    "manual_client_confirmation_required": True,
    "manual_registration_approval_required": True,
    "manual_outcome_ledger_activation_required": True,
    "approval_invention_forbidden": True,
    "automatic_approval_enabled": False,
    "source_schedule_activation_enabled": False,
    "automatic_acquisition_enabled": False,
    "historical_registration_enabled": False,
    "persistent_outcome_ledger_enabled": False,
    "point_in_time_materialization_enabled": False,
    "model_training_enabled": False,
    "backtest_execution_enabled": False,
    "pilot_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
    "codex_final_handoff_enabled": False,
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

    for index, item in enumerate(value):
        if not isinstance(
            item,
            dict,
        ):
            raise RuntimeError(f"{label}[{index}] must be an object.")

        result.append({str(key): item_value for key, item_value in item.items()})

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

    for index, item in enumerate(value):
        if not isinstance(
            item,
            str,
        ):
            raise RuntimeError(f"{label}[{index}] must be a string.")

        result.append(item)

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


def _index_by_source(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for row in rows:
        source_id = row.get("source_id")

        if not isinstance(
            source_id,
            str,
        ):
            continue

        result[source_id] = row

    return result


def _build_decision_schema() -> dict[str, Any]:
    return {
        "$schema": ("https://json-schema.org/draft/2020-12/schema"),
        "$id": ("cre-foundry-governance-decisions-v1"),
        "title": ("CRE Foundry Governance Decisions"),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "decision_bundle_version",
            "source_decisions",
            "client_inputs",
        ],
        "properties": {
            "decision_bundle_version": {"const": ("cre-foundry-governance-decisions-v1")},
            "source_decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "source_id",
                        "evidence_bundle_digest",
                        "parser_contract_approved",
                        "schema_contract_approved",
                        "approved_record_key",
                        "approved_temporal_fields",
                        "capture_policy_approved",
                        "change_contract_approved",
                        "registration_approved",
                        "reviewer_id",
                        "reviewed_at",
                        "evidence_reference",
                    ],
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "evidence_bundle_digest": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                        "parser_contract_approved": {"type": "boolean"},
                        "schema_contract_approved": {"type": "boolean"},
                        "approved_record_key": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                        "approved_temporal_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "capture_policy_approved": {"type": "boolean"},
                        "change_contract_approved": {"type": "boolean"},
                        "registration_approved": {"type": "boolean"},
                        "reviewer_id": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                        "reviewed_at": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                        "evidence_reference": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                    },
                },
            },
            "client_inputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "input_id",
                        "authoritative_value",
                        "confirmed",
                        "confirmed_by",
                        "confirmed_at",
                        "evidence_reference",
                    ],
                    "properties": {
                        "input_id": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "authoritative_value": {},
                        "confirmed": {"type": "boolean"},
                        "confirmed_by": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                        "confirmed_at": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                        "evidence_reference": {
                            "type": [
                                "string",
                                "null",
                            ]
                        },
                    },
                },
            },
        },
    }


def build_governance_activation_design(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "governance_activation_design.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Governance policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Governance policy mismatch.")

    source_order = _string_list(
        config.get("source_order"),
        label="source_order",
    )

    required_source_decisions = _string_list(
        config.get("required_source_decisions"),
        label="required_source_decisions",
    )

    client_input_definitions = _object_list(
        config.get("client_input_definitions"),
        label="client_input_definitions",
    )

    recommended_source_id = str(config["recommended_first_registration_source_id"])

    recommended_reason = str(config["recommended_first_registration_reason"])

    historical_defaults = config.get("historical_registration_defaults")

    outcome_defaults = config.get("outcome_ledger_activation_defaults")

    if not isinstance(
        historical_defaults,
        dict,
    ):
        raise RuntimeError("Historical defaults must be an object.")

    if not isinstance(
        outcome_defaults,
        dict,
    ):
        raise RuntimeError("Outcome defaults must be an object.")

    contract_root = project_root / "docs" / "data_contracts"

    parser_validation = _load_object(contract_root / "source_parser_contract_validation.json")

    parser_approval_template = _load_object(
        contract_root / "source_parser_contract_approval_template.json"
    )

    longitudinal_plan = _load_object(contract_root / "longitudinal_collection_plan.json")

    coverage_requirements = _load_object(contract_root / "historical_coverage_requirements.json")

    change_contracts = _load_object(contract_root / "source_change_detection_contracts.json")

    current_client_template = _load_object(contract_root / "client_input_capture_template.json")

    learning_summary = _load_object(contract_root / "learning_capture_design_summary.json")

    outcome_contract = _load_object(contract_root / "outcome_collection_contract.json")

    experiment_contract = _load_object(contract_root / "pilot_experiment_design.json")

    validation_rows = _object_list(
        parser_validation.get("validations"),
        label="parser validations",
    )

    parser_approval_rows = _object_list(
        parser_approval_template.get("approvals"),
        label="parser approvals",
    )

    source_plan_rows = _object_list(
        longitudinal_plan.get("source_plans"),
        label="source plans",
    )

    coverage_rows = _object_list(
        coverage_requirements.get("requirements"),
        label="coverage requirements",
    )

    change_rows = _object_list(
        change_contracts.get("contracts"),
        label="change contracts",
    )

    current_client_rows = _object_list(
        current_client_template.get("sections"),
        label="client sections",
    )

    validation_by_source = _index_by_source(validation_rows)

    parser_approval_by_source = _index_by_source(parser_approval_rows)

    plan_by_source = _index_by_source(source_plan_rows)

    coverage_by_source = _index_by_source(coverage_rows)

    change_by_source = _index_by_source(change_rows)

    current_client_by_id: dict[str, dict[str, Any]] = {}

    for current_row in current_client_rows:
        input_id = current_row.get("input_id")

        if isinstance(
            input_id,
            str,
        ):
            current_client_by_id[input_id] = current_row

    source_packets: list[dict[str, Any]] = []

    evidence_complete_packet_count = 0

    for source_id in source_order:
        validation = validation_by_source.get(source_id)

        parser_approval = parser_approval_by_source.get(source_id)

        source_plan = plan_by_source.get(source_id)

        coverage = coverage_by_source.get(source_id)

        change_contract = change_by_source.get(source_id)

        validation_complete = bool(validation and validation.get("validation_complete") is True)

        parser_evidence_available = bool(parser_approval)

        candidate_record_keys: list[str] = []

        candidate_temporal_fields: list[str] = []

        if parser_approval:
            raw_record_keys = parser_approval.get(
                "candidate_record_keys",
                [],
            )

            raw_temporal_fields = parser_approval.get(
                "candidate_temporal_fields",
                [],
            )

            candidate_record_keys = _string_list(
                raw_record_keys,
                label=(f"{source_id}.candidate_record_keys"),
            )

            candidate_temporal_fields = _string_list(
                raw_temporal_fields,
                label=(f"{source_id}.candidate_temporal_fields"),
            )

        first_run: dict[str, Any] = {}

        if validation:
            raw_first_run = validation.get("first_run")

            if isinstance(
                raw_first_run,
                dict,
            ):
                first_run = {str(key): value for key, value in raw_first_run.items()}

        evidence_payload: dict[str, Any] = {
            "source_id": source_id,
            "parser_validation_complete": (validation_complete),
            "reproducibility_match": (
                bool(validation and validation.get("reproducibility_match") is True)
            ),
            "artifact_path": first_run.get("artifact_path"),
            "artifact_sha256": first_run.get("artifact_sha256"),
            "parser_type": first_run.get("parser_type"),
            "record_count": first_run.get("record_count"),
            "field_count": first_run.get("field_count"),
            "schema_fingerprint": (first_run.get("schema_fingerprint")),
            "dataset_digest": first_run.get("dataset_digest"),
            "candidate_record_keys": (candidate_record_keys),
            "candidate_temporal_fields": (candidate_temporal_fields),
            "source_plan": source_plan,
            "historical_coverage": coverage,
            "change_contract": change_contract,
        }

        evidence_bundle_digest = _stable_digest(evidence_payload)

        evidence_complete = bool(
            validation_complete
            and parser_evidence_available
            and candidate_record_keys
            and source_plan
            and coverage
            and change_contract
        )

        if evidence_complete:
            evidence_complete_packet_count += 1

        approval_blockers: list[str] = []

        if not validation_complete:
            approval_blockers.append("parser_validation_incomplete")

        if not parser_evidence_available:
            approval_blockers.append("parser_evidence_unavailable")

        if not candidate_record_keys:
            approval_blockers.append("record_key_candidates_unavailable")

        if not source_plan:
            approval_blockers.append("longitudinal_plan_unavailable")

        if not coverage:
            approval_blockers.append("historical_coverage_contract_unavailable")

        if not change_contract:
            approval_blockers.append("change_contract_unavailable")

        if not candidate_temporal_fields:
            approval_blockers.append("temporal_semantics_manual_resolution_required")

        approval_blockers.extend(
            [
                "parser_contract_not_approved",
                "schema_contract_not_approved",
                "record_key_not_approved",
                "temporal_semantics_not_approved",
                "capture_policy_not_approved",
                "change_contract_not_approved",
                "registration_not_approved",
            ]
        )

        source_packets.append(
            {
                "source_id": source_id,
                "recommended_first_registration_candidate": (source_id == recommended_source_id),
                "evidence_complete": (evidence_complete),
                "evidence_bundle_digest": (evidence_bundle_digest),
                "evidence": evidence_payload,
                "required_decisions": (required_source_decisions),
                "decision_template": {
                    "source_id": source_id,
                    "evidence_bundle_digest": (evidence_bundle_digest),
                    "parser_contract_approved": False,
                    "schema_contract_approved": False,
                    "approved_record_key": None,
                    "approved_temporal_fields": [],
                    "capture_policy_approved": False,
                    "change_contract_approved": False,
                    "registration_approved": False,
                    "reviewer_id": None,
                    "reviewed_at": None,
                    "evidence_reference": None,
                    "review_notes": None,
                },
                "approval_blockers": sorted(set(approval_blockers)),
                "approval_complete": False,
                "registration_eligible": False,
            }
        )

    source_packets.sort(key=lambda row: source_order.index(str(row["source_id"])))

    questionnaire_rows: list[dict[str, Any]] = []

    for definition in client_input_definitions:
        input_id = str(definition["input_id"])

        question = str(definition["question"])

        required_fields = _string_list(
            definition.get("required_fields"),
            label=(f"{input_id}.required_fields"),
        )

        current = current_client_by_id.get(
            input_id,
            {},
        )

        questionnaire_rows.append(
            {
                "input_id": input_id,
                "question": question,
                "required_fields": required_fields,
                "authoritative_value": None,
                "confirmed": False,
                "confirmed_by": None,
                "confirmed_at": None,
                "evidence_reference": None,
                "current_template_confirmed": bool(current.get("confirmed") is True),
                "current_template_value": (current.get("authoritative_value")),
            }
        )

    questionnaire_digest = _stable_digest(
        {
            "definitions": questionnaire_rows,
            "version": ("cre-foundry-client-questionnaire-v1"),
        }
    )

    source_packet_by_id = {str(packet["source_id"]): packet for packet in source_packets}

    recommended_packet = source_packet_by_id.get(recommended_source_id)

    if recommended_packet is None:
        raise RuntimeError("Recommended first-registration source is not present in source_order.")

    historical_registration_template: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-historical-registration-request-v1"),
        "request_id": None,
        "source_id": recommended_source_id,
        "recommendation_only": True,
        "recommendation_reason": (recommended_reason),
        "expected_evidence_bundle_digest": (recommended_packet["evidence_bundle_digest"]),
        "artifact_sha256": (recommended_packet["evidence"].get("artifact_sha256")),
        "dataset_digest": (recommended_packet["evidence"].get("dataset_digest")),
        "parser_contract_approval_reference": None,
        "schema_contract_approval_reference": None,
        "record_key_approval_reference": None,
        "temporal_semantics_approval_reference": None,
        "capture_policy_approval_reference": None,
        "change_contract_approval_reference": None,
        "registration_approval_reference": None,
        "operator_id": None,
        "requested_at": None,
        "enabled": False,
        "dry_run_only": True,
        "maximum_source_count": int(historical_defaults["maximum_source_count"]),
        "maximum_snapshot_count": int(historical_defaults["maximum_snapshot_count"]),
        "automatic_retry_enabled": False,
        "schedule_activation_enabled": False,
        "automatic_acquisition_enabled": False,
        "registration_permitted": False,
        "registration_execution_count": 0,
        "snapshot_event_insertion_count": 0,
    }

    outcome_activation_template: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-outcome-ledger-activation-request-v1"),
        "request_id": None,
        "outcome_schema_fingerprint": (outcome_contract.get("schema_fingerprint")),
        "client_questionnaire_digest": (questionnaire_digest),
        "required_confirmed_client_input_count": (len(questionnaire_rows)),
        "confirmed_client_input_count": 0,
        "primary_outcome_approval_reference": None,
        "transaction_economics_approval_reference": None,
        "representative_capacity_approval_reference": None,
        "exclusion_approval_reference": None,
        "operating_environment_approval_reference": None,
        "storage_path": None,
        "backup_policy_reference": None,
        "operator_id": None,
        "requested_at": None,
        "enabled": False,
        "ephemeral_validation_only": True,
        "persistent_database_creation_enabled": False,
        "event_insertion_enabled": False,
        "label_materialization_enabled": False,
        "activation_permitted": False,
        "persistent_database_creation_count": 0,
        "event_insertion_count": 0,
        "label_materialization_count": 0,
    }

    source_approval_count = 0
    client_confirmation_count = 0

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-governance-activation-design-v1"),
        "source_packet_count": len(source_packets),
        "evidence_complete_source_packet_count": (evidence_complete_packet_count),
        "source_approval_complete_count": (source_approval_count),
        "client_input_section_count": len(questionnaire_rows),
        "client_input_confirmed_count": (client_confirmation_count),
        "recommended_first_registration_source_id": (recommended_source_id),
        "recommended_first_registration_evidence_digest": (
            recommended_packet["evidence_bundle_digest"]
        ),
        "primary_outcome_confirmed": False,
        "transaction_economics_confirmed": False,
        "representative_capacity_confirmed": False,
        "protected_accounts_confirmed": False,
        "operating_environment_confirmed": False,
        "first_historical_registration_ready": False,
        "repeated_snapshot_collection_ready": False,
        "change_detection_ready": False,
        "persistent_outcome_ledger_ready": False,
        "point_in_time_dataset_ready": False,
        "model_training_ready": False,
        "temporal_backtesting_ready": False,
        "probability_calibration_ready": False,
        "shadow_pilot_ready": False,
        "controlled_pilot_ready": False,
        "incremental_roi_proven": False,
        "production_ranking_ready": False,
        "outreach_ready": False,
        "codex_final_handoff_ready": False,
        "automatic_approval_count": 0,
        "source_schedule_activation_count": 0,
        "automatic_acquisition_execution_count": 0,
        "historical_registration_execution_count": 0,
        "snapshot_event_insertion_count": 0,
        "persistent_outcome_database_creation_count": 0,
        "outcome_event_insertion_count": 0,
        "label_materialization_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "learning_capture_summary_digest": (_stable_digest(learning_summary)),
        "pilot_experiment_contract_digest": (_stable_digest(experiment_contract)),
        "client_questionnaire_digest": (questionnaire_digest),
        "policy": EXPECTED_POLICY,
    }

    decision_schema = _build_decision_schema()

    source_packet_template: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-source-approval-packets-v1"),
        "packet_count": len(source_packets),
        "evidence_complete_packet_count": (evidence_complete_packet_count),
        "approval_complete_packet_count": 0,
        "packets": source_packets,
        "automatic_approval": False,
        "registration_permitted_count": 0,
    }

    questionnaire: dict[str, Any] = {
        "model_version": ("cre-foundry-client-questionnaire-v1"),
        "questionnaire_digest": (questionnaire_digest),
        "section_count": len(questionnaire_rows),
        "confirmed_section_count": 0,
        "sections": questionnaire_rows,
        "invention_permitted": False,
        "registration_permitted": False,
        "outcome_ledger_activation_permitted": False,
        "model_training_permitted": False,
        "pilot_execution_permitted": False,
        "production_ranking_permitted": False,
        "outreach_permitted": False,
    }

    if write_contracts:
        _atomic_json(
            contract_root / "governance_gate_summary.json",
            summary,
        )

        _atomic_json(
            contract_root / "governance_approval_packet_template.json",
            source_packet_template,
        )

        _atomic_json(
            contract_root / "governance_decision_schema.json",
            decision_schema,
        )

        _atomic_json(
            contract_root / "client_input_questionnaire.json",
            questionnaire,
        )

        questionnaire_lines = [
            "# Authoritative Client Input Questionnaire",
            "",
            (
                "No response is treated as confirmed until "
                "an identified client authority supplies the "
                "value and an evidence reference."
            ),
            "",
        ]

        for index, section in enumerate(
            questionnaire_rows,
            start=1,
        ):
            questionnaire_lines.extend(
                [
                    (f"## {index}. {section['input_id']}"),
                    "",
                    str(section["question"]),
                    "",
                    "Required fields:",
                    "",
                ]
            )

            questionnaire_lines.extend(f"- `{field}`" for field in section["required_fields"])

            questionnaire_lines.extend(
                [
                    "",
                    "- Authoritative answer: `unconfirmed`",
                    "- Confirmed by: `unconfirmed`",
                    "- Evidence reference: `unconfirmed`",
                    "",
                ]
            )

        _atomic_text(
            contract_root / "client_input_questionnaire.md",
            "\n".join(questionnaire_lines),
        )

        _atomic_json(
            contract_root / "historical_registration_request_template.json",
            historical_registration_template,
        )

        _atomic_json(
            contract_root / "outcome_ledger_activation_request_template.json",
            outcome_activation_template,
        )

        _atomic_text(
            contract_root / "governance_activation_design.md",
            "\n".join(
                [
                    "# Governance and Activation Design",
                    "",
                    (
                        "This layer converts unresolved human "
                        "decisions into checksum-bound approval "
                        "packets and disabled execution requests."
                    ),
                    "",
                    (f"- Source approval packets: `{summary['source_packet_count']}`"),
                    (
                        f"- Evidence-complete packets: "
                        f"`{summary['evidence_complete_source_packet_count']}`"
                    ),
                    (
                        f"- Completed source approvals: "
                        f"`{summary['source_approval_complete_count']}`"
                    ),
                    (f"- Client-input sections: `{summary['client_input_section_count']}`"),
                    (f"- Confirmed client inputs: `{summary['client_input_confirmed_count']}`"),
                    "",
                    ("- First historical registration ready: `false`"),
                    ("- Persistent outcome ledger ready: `false`"),
                    ("- Point-in-time dataset ready: `false`"),
                    ("- Model training ready: `false`"),
                    ("- Final Codex handoff ready: `false`"),
                    "",
                    "- Automatic approvals: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Outcome events: `0`",
                    "- Model training executions: `0`",
                    "- Production rankings: `0`",
                    "- Outreach executions: `0`",
                    "",
                ]
            ),
        )

    return {
        "summary": summary,
        "source_packets": (source_packet_template),
        "questionnaire": questionnaire,
        "decision_schema": (decision_schema),
        "historical_registration_template": (historical_registration_template),
        "outcome_activation_template": (outcome_activation_template),
    }
