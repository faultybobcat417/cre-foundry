from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "validation_only": True,
    "exact_evidence_digest_required": True,
    "stale_approval_rejection_required": True,
    "complete_reviewer_attribution_required": True,
    "complete_client_attribution_required": True,
    "automatic_approval_enabled": False,
    "automatic_value_invention_enabled": False,
    "historical_registration_execution_enabled": False,
    "persistent_outcome_ledger_enabled": False,
    "source_schedule_activation_enabled": False,
    "automatic_acquisition_enabled": False,
    "point_in_time_materialization_enabled": False,
    "model_training_enabled": False,
    "backtest_execution_enabled": False,
    "pilot_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
    "codex_final_handoff_enabled": False,
}


SOURCE_DECISION_FIELDS = {
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
}


CLIENT_INPUT_FIELDS = {
    "input_id",
    "authoritative_value",
    "confirmed",
    "confirmed_by",
    "confirmed_at",
    "evidence_reference",
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

    rows: list[dict[str, Any]] = []

    for index, raw_row in enumerate(value):
        if not isinstance(
            raw_row,
            dict,
        ):
            raise RuntimeError(f"{label}[{index}] must be an object.")

        rows.append({str(key): row_value for key, row_value in raw_row.items()})

    return rows


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

    values: list[str] = []

    for index, raw_value in enumerate(value):
        if not isinstance(
            raw_value,
            str,
        ):
            raise RuntimeError(f"{label}[{index}] must be a string.")

        values.append(raw_value)

    return values


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


def _meaningful(
    value: object,
) -> bool:
    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return bool(value.strip())

    if isinstance(
        value,
        list,
    ):
        return bool(value)

    if isinstance(
        value,
        dict,
    ):
        return bool(value)

    return True


def _valid_timestamp(
    value: object,
) -> bool:
    if not isinstance(
        value,
        str,
    ):
        return False

    normalized = value.strip()

    if not normalized:
        return False

    try:
        datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:
        return False

    return True


def _index_unique(
    rows: list[dict[str, Any]],
    *,
    key_name: str,
    label: str,
) -> tuple[
    dict[str, dict[str, Any]],
    list[str],
]:
    indexed: dict[str, dict[str, Any]] = {}

    duplicates: list[str] = []

    for row in rows:
        raw_key = row.get(key_name)

        if not isinstance(
            raw_key,
            str,
        ):
            raise RuntimeError(f"{label} lacks {key_name}.")

        if raw_key in indexed:
            duplicates.append(raw_key)

        indexed[raw_key] = row

    return (
        indexed,
        sorted(set(duplicates)),
    )


def _validate_bundle_shape(
    bundle: dict[str, Any],
) -> None:
    expected_top_level = {
        "decision_bundle_version",
        "source_decisions",
        "client_inputs",
    }

    actual_top_level = set(bundle)

    if actual_top_level != expected_top_level:
        raise RuntimeError(
            "Decision bundle top-level fields mismatch. "
            f"Expected={sorted(expected_top_level)}, "
            f"actual={sorted(actual_top_level)}"
        )

    if bundle["decision_bundle_version"] != "cre-foundry-governance-decisions-v1":
        raise RuntimeError("Unsupported governance decision version.")

    source_rows = _object_list(
        bundle["source_decisions"],
        label="source_decisions",
    )

    client_rows = _object_list(
        bundle["client_inputs"],
        label="client_inputs",
    )

    for index, row in enumerate(source_rows):
        fields = set(row)

        if fields != SOURCE_DECISION_FIELDS:
            raise RuntimeError(
                "Source decision fields mismatch at "
                f"index {index}. "
                f"Expected={sorted(SOURCE_DECISION_FIELDS)}, "
                f"actual={sorted(fields)}"
            )

    for index, row in enumerate(client_rows):
        fields = set(row)

        if fields != CLIENT_INPUT_FIELDS:
            raise RuntimeError(
                "Client input fields mismatch at "
                f"index {index}. "
                f"Expected={sorted(CLIENT_INPUT_FIELDS)}, "
                f"actual={sorted(fields)}"
            )


def build_manual_activation_envelopes(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "manual_activation_envelopes.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Manual-activation policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Manual-activation policy mismatch.")

    decision_bundle_path = str(config["decision_bundle_path"])

    recommended_source_id = str(config["recommended_first_registration_source_id"])

    raw_registration_limits = config.get("historical_registration_limits")

    raw_codex_policy = config.get("codex_handoff_policy")

    if not isinstance(
        raw_registration_limits,
        dict,
    ):
        raise RuntimeError("Registration limits must be an object.")

    if not isinstance(
        raw_codex_policy,
        dict,
    ):
        raise RuntimeError("Codex handoff policy must be an object.")

    contract_root = project_root / "docs" / "data_contracts"

    packets = _load_object(contract_root / "governance_approval_packet_template.json")

    questionnaire = _load_object(contract_root / "client_input_questionnaire.json")

    historical_template = _load_object(
        contract_root / "historical_registration_request_template.json"
    )

    outcome_template = _load_object(
        contract_root / "outcome_ledger_activation_request_template.json"
    )

    outcome_contract = _load_object(contract_root / "outcome_collection_contract.json")

    template_schema_fingerprint = outcome_template.get("outcome_schema_fingerprint")

    contract_schema_fingerprint = outcome_contract.get("schema_fingerprint")

    template_questionnaire_digest = outcome_template.get("client_questionnaire_digest")

    current_questionnaire_digest = questionnaire.get("questionnaire_digest")

    outcome_activation_template_stale = bool(
        template_schema_fingerprint != contract_schema_fingerprint
        or template_questionnaire_digest != current_questionnaire_digest
    )

    decision_bundle = _load_object(project_root / decision_bundle_path)

    _validate_bundle_shape(decision_bundle)

    packet_rows = _object_list(
        packets.get("packets"),
        label="governance packets",
    )

    questionnaire_rows = _object_list(
        questionnaire.get("sections"),
        label="questionnaire sections",
    )

    source_decision_rows = _object_list(
        decision_bundle.get("source_decisions"),
        label="source decisions",
    )

    client_input_rows = _object_list(
        decision_bundle.get("client_inputs"),
        label="client inputs",
    )

    packet_by_source, packet_duplicates = _index_unique(
        packet_rows,
        key_name="source_id",
        label="governance packet",
    )

    decision_by_source, decision_duplicates = _index_unique(
        source_decision_rows,
        key_name="source_id",
        label="source decision",
    )

    questionnaire_by_id, questionnaire_duplicates = _index_unique(
        questionnaire_rows,
        key_name="input_id",
        label="questionnaire section",
    )

    client_by_id, client_duplicates = _index_unique(
        client_input_rows,
        key_name="input_id",
        label="client input",
    )

    expected_sources = set(packet_by_source)

    actual_sources = set(decision_by_source)

    expected_client_inputs = set(questionnaire_by_id)

    actual_client_inputs = set(client_by_id)

    source_set_mismatch = bool(expected_sources != actual_sources)

    client_set_mismatch = bool(expected_client_inputs != actual_client_inputs)

    source_results: list[dict[str, Any]] = []

    source_complete_count = 0
    stale_source_decision_count = 0

    for source_id in sorted(expected_sources):
        packet = packet_by_source[source_id]

        decision = decision_by_source.get(source_id)

        blockers: list[str] = []

        if decision is None:
            source_results.append(
                {
                    "source_id": source_id,
                    "decision_present": False,
                    "decision_complete": False,
                    "stale_evidence": False,
                    "blockers": ["source_decision_missing"],
                }
            )
            continue

        expected_digest = packet.get("evidence_bundle_digest")

        supplied_digest = decision.get("evidence_bundle_digest")

        digest_match = bool(
            isinstance(
                expected_digest,
                str,
            )
            and supplied_digest == expected_digest
        )

        stale_evidence = not digest_match

        if stale_evidence:
            stale_source_decision_count += 1
            blockers.append("evidence_bundle_digest_mismatch")

        evidence = packet.get("evidence")

        if not isinstance(
            evidence,
            dict,
        ):
            evidence = {}

        raw_candidate_record_keys = evidence.get(
            "candidate_record_keys",
            [],
        )

        raw_candidate_temporal_fields = evidence.get(
            "candidate_temporal_fields",
            [],
        )

        candidate_record_keys = _string_list(
            raw_candidate_record_keys,
            label=(f"{source_id}.candidate_record_keys"),
        )

        candidate_temporal_fields = _string_list(
            raw_candidate_temporal_fields,
            label=(f"{source_id}.candidate_temporal_fields"),
        )

        approved_record_key = decision.get("approved_record_key")

        record_key_valid = bool(
            isinstance(
                approved_record_key,
                str,
            )
            and approved_record_key in candidate_record_keys
        )

        if not record_key_valid:
            blockers.append("approved_record_key_invalid_or_missing")

        approved_temporal_fields = _string_list(
            decision.get("approved_temporal_fields"),
            label=(f"{source_id}.approved_temporal_fields"),
        )

        temporal_subset_valid = set(approved_temporal_fields).issubset(
            set(candidate_temporal_fields)
        )

        temporal_selection_complete = bool(approved_temporal_fields)

        if not temporal_subset_valid:
            blockers.append("approved_temporal_fields_not_candidates")

        if not temporal_selection_complete:
            if candidate_temporal_fields:
                blockers.append("approved_temporal_fields_missing")

            else:
                blockers.append("manual_temporal_semantics_extension_required")

        approval_fields = (
            "parser_contract_approved",
            "schema_contract_approved",
            "capture_policy_approved",
            "change_contract_approved",
            "registration_approved",
        )

        for field in approval_fields:
            if decision.get(field) is not True:
                blockers.append(f"{field}_false")

        reviewer_id_valid = _meaningful(decision.get("reviewer_id"))

        reviewed_at_valid = _valid_timestamp(decision.get("reviewed_at"))

        evidence_reference_valid = _meaningful(decision.get("evidence_reference"))

        if not reviewer_id_valid:
            blockers.append("reviewer_id_missing")

        if not reviewed_at_valid:
            blockers.append("reviewed_at_missing_or_invalid")

        if not evidence_reference_valid:
            blockers.append("evidence_reference_missing")

        decision_complete = not blockers

        if decision_complete:
            source_complete_count += 1

        source_results.append(
            {
                "source_id": source_id,
                "decision_present": True,
                "expected_evidence_bundle_digest": (expected_digest),
                "supplied_evidence_bundle_digest": (supplied_digest),
                "evidence_digest_match": (digest_match),
                "stale_evidence": stale_evidence,
                "candidate_record_keys": (candidate_record_keys),
                "approved_record_key": (approved_record_key),
                "record_key_valid": (record_key_valid),
                "candidate_temporal_fields": (candidate_temporal_fields),
                "approved_temporal_fields": (approved_temporal_fields),
                "temporal_subset_valid": (temporal_subset_valid),
                "temporal_selection_complete": (temporal_selection_complete),
                "reviewer_attribution_complete": (
                    reviewer_id_valid and reviewed_at_valid and evidence_reference_valid
                ),
                "decision_complete": (decision_complete),
                "blockers": sorted(set(blockers)),
            }
        )

    client_results: list[dict[str, Any]] = []

    client_complete_count = 0

    for input_id in sorted(expected_client_inputs):
        definition = questionnaire_by_id[input_id]

        supplied = client_by_id.get(input_id)

        blockers = []

        if supplied is None:
            client_results.append(
                {
                    "input_id": input_id,
                    "input_present": False,
                    "input_complete": False,
                    "blockers": ["client_input_missing"],
                }
            )
            continue

        required_fields = _string_list(
            definition.get("required_fields"),
            label=(f"{input_id}.required_fields"),
        )

        authoritative_value = supplied.get("authoritative_value")

        authoritative_value_object: dict[str, Any] | None = None

        if isinstance(
            authoritative_value,
            dict,
        ):
            authoritative_value_object = {
                str(key): item_value for key, item_value in authoritative_value.items()
            }

        value_is_object = authoritative_value_object is not None

        missing_required_fields: list[str] = []

        if authoritative_value_object is not None:
            for required_field in required_fields:
                if required_field not in authoritative_value_object or not _meaningful(
                    authoritative_value_object[required_field]
                ):
                    missing_required_fields.append(required_field)

        else:
            missing_required_fields = list(required_fields)

        if missing_required_fields:
            blockers.append("required_authoritative_fields_missing")

        if supplied.get("confirmed") is not True:
            blockers.append("client_confirmation_false")

        confirmed_by_valid = _meaningful(supplied.get("confirmed_by"))

        confirmed_at_valid = _valid_timestamp(supplied.get("confirmed_at"))

        evidence_reference_valid = _meaningful(supplied.get("evidence_reference"))

        if not confirmed_by_valid:
            blockers.append("confirmed_by_missing")

        if not confirmed_at_valid:
            blockers.append("confirmed_at_missing_or_invalid")

        if not evidence_reference_valid:
            blockers.append("client_evidence_reference_missing")

        input_complete = not blockers

        if input_complete:
            client_complete_count += 1

        client_results.append(
            {
                "input_id": input_id,
                "input_present": True,
                "required_fields": required_fields,
                "missing_required_fields": sorted(missing_required_fields),
                "authoritative_value_is_object": (value_is_object),
                "confirmation_attribution_complete": (
                    confirmed_by_valid and confirmed_at_valid and evidence_reference_valid
                ),
                "input_complete": input_complete,
                "blockers": sorted(set(blockers)),
            }
        )

    source_result_by_id = {str(result["source_id"]): result for result in source_results}

    recommended_source_result = source_result_by_id.get(recommended_source_id)

    if recommended_source_result is None:
        raise RuntimeError("Recommended source is absent from the governance packets.")

    recommended_source_approval_ready = bool(
        recommended_source_result.get("decision_complete") is True
    )

    all_client_inputs_complete = bool(
        client_complete_count == len(expected_client_inputs) and expected_client_inputs
    )

    historical_dry_run_ready = bool(
        recommended_source_approval_ready
        and historical_template.get("source_id") == recommended_source_id
        and historical_template.get("expected_evidence_bundle_digest")
        == recommended_source_result.get("expected_evidence_bundle_digest")
    )

    historical_envelope: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-historical-registration-envelope-v1"),
        "source_id": recommended_source_id,
        "source_decision_complete": (recommended_source_approval_ready),
        "evidence_digest_match": bool(
            recommended_source_result.get("evidence_digest_match") is True
        ),
        "expected_evidence_bundle_digest": (
            recommended_source_result.get("expected_evidence_bundle_digest")
        ),
        "artifact_sha256": historical_template.get("artifact_sha256"),
        "dataset_digest": historical_template.get("dataset_digest"),
        "maximum_source_count": int(raw_registration_limits["maximum_source_count"]),
        "maximum_snapshot_count": int(raw_registration_limits["maximum_snapshot_count"]),
        "approval_ready": (recommended_source_approval_ready),
        "dry_run_ready": (historical_dry_run_ready),
        "dry_run_only": True,
        "execution_command_generated": False,
        "command_generation_permitted": False,
        "authoritative_execution_enabled": False,
        "automatic_retry_enabled": False,
        "schedule_activation_enabled": False,
        "automatic_acquisition_enabled": False,
        "registration_execution_count": 0,
        "snapshot_event_insertion_count": 0,
        "execution_blockers": (
            []
            if historical_dry_run_ready
            else list(
                recommended_source_result.get(
                    "blockers",
                    [],
                )
            )
        ),
    }

    outcome_schema_fingerprint = outcome_contract.get("schema_fingerprint")

    outcome_bootstrap_ready = bool(
        all_client_inputs_complete
        and _meaningful(outcome_schema_fingerprint)
        and not outcome_activation_template_stale
    )

    outcome_envelope: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-outcome-ledger-bootstrap-envelope-v1"),
        "outcome_schema_fingerprint": (outcome_schema_fingerprint),
        "required_client_input_count": len(expected_client_inputs),
        "confirmed_client_input_count": (client_complete_count),
        "all_client_inputs_complete": (all_client_inputs_complete),
        "approval_ready": (all_client_inputs_complete),
        "ephemeral_bootstrap_ready": (outcome_bootstrap_ready),
        "persistent_database_path": None,
        "persistent_database_creation_enabled": False,
        "event_insertion_enabled": False,
        "label_materialization_enabled": False,
        "activation_command_generated": False,
        "activation_permitted": False,
        "persistent_database_creation_count": 0,
        "event_insertion_count": 0,
        "label_materialization_count": 0,
        "execution_blockers": [
            result["input_id"] for result in client_results if not result["input_complete"]
        ],
    }

    client_result_by_id = {str(result["input_id"]): result for result in client_results}

    operating_environment_complete = bool(
        client_result_by_id.get(
            "operating_environment",
            {},
        ).get("input_complete")
        is True
    )

    primary_success_complete = bool(
        client_result_by_id.get(
            "primary_success_event",
            {},
        ).get("input_complete")
        is True
    )

    transaction_economics_complete = bool(
        client_result_by_id.get(
            "transaction_economics",
            {},
        ).get("input_complete")
        is True
    )

    representative_capacity_complete = bool(
        client_result_by_id.get(
            "pilot_representatives_and_capacity",
            {},
        ).get("input_complete")
        is True
    )

    exclusions_complete = bool(
        client_result_by_id.get(
            "protected_accounts_and_exclusions",
            {},
        ).get("input_complete")
        is True
    )

    codex_contract_handoff_ready = bool(
        all_client_inputs_complete
        and operating_environment_complete
        and primary_success_complete
        and transaction_economics_complete
        and representative_capacity_complete
        and exclusions_complete
        and not outcome_activation_template_stale
    )

    gate_nodes = [
        {
            "gate_id": "recommended_source_approval",
            "ready": (recommended_source_approval_ready),
            "prerequisites": [],
        },
        {
            "gate_id": "historical_registration_dry_run",
            "ready": (historical_dry_run_ready),
            "prerequisites": ["recommended_source_approval"],
        },
        {
            "gate_id": "first_authoritative_snapshot",
            "ready": False,
            "prerequisites": [
                "historical_registration_dry_run",
                "separate_execution_authorization",
            ],
        },
        {
            "gate_id": "repeated_snapshot_collection",
            "ready": False,
            "prerequisites": [
                "first_authoritative_snapshot",
                "schedule_approval",
                "acquisition_approval",
            ],
        },
        {
            "gate_id": "change_detection_execution",
            "ready": False,
            "prerequisites": ["repeated_snapshot_collection", "approved_change_contract"],
        },
        {
            "gate_id": "all_client_inputs",
            "ready": (all_client_inputs_complete),
            "prerequisites": [],
        },
        {
            "gate_id": "outcome_ledger_ephemeral_bootstrap",
            "ready": (outcome_bootstrap_ready),
            "prerequisites": ["all_client_inputs"],
        },
        {
            "gate_id": "persistent_outcome_ledger",
            "ready": False,
            "prerequisites": [
                "outcome_ledger_ephemeral_bootstrap",
                "separate_activation_authorization",
            ],
        },
        {
            "gate_id": "real_outcome_labels",
            "ready": False,
            "prerequisites": [
                "persistent_outcome_ledger",
                "pilot_actions",
                "completed_observation_windows",
            ],
        },
        {
            "gate_id": "point_in_time_dataset",
            "ready": False,
            "prerequisites": [
                "repeated_snapshot_collection",
                "change_detection_execution",
                "real_outcome_labels",
            ],
        },
        {
            "gate_id": "baseline_model_training",
            "ready": False,
            "prerequisites": ["point_in_time_dataset"],
        },
        {
            "gate_id": "temporal_backtesting",
            "ready": False,
            "prerequisites": ["baseline_model_training", "sufficient_historical_folds"],
        },
        {
            "gate_id": "probability_calibration",
            "ready": False,
            "prerequisites": ["temporal_backtesting", "held_out_calibration_window"],
        },
        {
            "gate_id": "shadow_pilot",
            "ready": False,
            "prerequisites": ["probability_calibration", "all_client_inputs"],
        },
        {
            "gate_id": "controlled_pilot",
            "ready": False,
            "prerequisites": ["shadow_pilot", "client_pilot_authorization"],
        },
        {
            "gate_id": "incremental_roi_proof",
            "ready": False,
            "prerequisites": ["controlled_pilot", "transaction_economics"],
        },
        {
            "gate_id": "codex_contract_handoff",
            "ready": (codex_contract_handoff_ready),
            "prerequisites": ["all_client_inputs", "operating_environment"],
            "meaning": (
                "Codex may build the application shell, interfaces and stable contract adapters."
            ),
        },
        {
            "gate_id": "codex_final_product_handoff",
            "ready": False,
            "prerequisites": [
                "codex_contract_handoff",
                "incremental_roi_proof",
                "production_governance",
            ],
            "meaning": (
                "Codex may complete the production product "
                "only after the quant system has evidence."
            ),
        },
    ]

    gate_graph: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-codex-handoff-gate-graph-v1"),
        "node_count": len(gate_nodes),
        "nodes": gate_nodes,
        "codex_contract_handoff_ready": (codex_contract_handoff_ready),
        "codex_final_product_handoff_ready": False,
        "controlled_pilot_complete": False,
        "incremental_roi_proven": False,
        "production_governance_ready": False,
    }

    validation_report: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-manual-decision-validation-v1"),
        "decision_bundle_path": (decision_bundle_path),
        "decision_bundle_digest": (_stable_digest(decision_bundle)),
        "source_packet_count": len(expected_sources),
        "source_decision_count": len(actual_sources),
        "source_set_mismatch": (source_set_mismatch),
        "source_packet_duplicate_count": len(packet_duplicates),
        "source_decision_duplicate_count": len(decision_duplicates),
        "source_decision_complete_count": (source_complete_count),
        "stale_source_decision_count": (stale_source_decision_count),
        "source_results": source_results,
        "client_input_definition_count": len(expected_client_inputs),
        "client_input_count": len(actual_client_inputs),
        "client_set_mismatch": (client_set_mismatch),
        "questionnaire_duplicate_count": len(questionnaire_duplicates),
        "client_input_duplicate_count": len(client_duplicates),
        "client_input_complete_count": (client_complete_count),
        "client_results": client_results,
        "recommended_source_id": (recommended_source_id),
        "recommended_source_approval_ready": (recommended_source_approval_ready),
        "all_client_inputs_complete": (all_client_inputs_complete),
        "historical_dry_run_ready": (historical_dry_run_ready),
        "outcome_ephemeral_bootstrap_ready": (outcome_bootstrap_ready),
        "codex_contract_handoff_ready": (codex_contract_handoff_ready),
        "codex_final_product_handoff_ready": False,
        "automatic_approval_count": 0,
        "historical_registration_execution_count": 0,
        "snapshot_event_insertion_count": 0,
        "persistent_database_creation_count": 0,
        "outcome_event_insertion_count": 0,
        "label_materialization_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "policy": EXPECTED_POLICY,
    }

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-manual-activation-envelope-summary-v1"),
        "source_decision_complete_count": (source_complete_count),
        "source_decision_required_count": len(expected_sources),
        "stale_source_decision_count": (stale_source_decision_count),
        "client_input_complete_count": (client_complete_count),
        "client_input_required_count": len(expected_client_inputs),
        "recommended_source_approval_ready": (recommended_source_approval_ready),
        "historical_registration_dry_run_ready": (historical_dry_run_ready),
        "historical_registration_execution_enabled": False,
        "outcome_ledger_ephemeral_bootstrap_ready": (outcome_bootstrap_ready),
        "persistent_outcome_ledger_enabled": False,
        "codex_contract_handoff_ready": (codex_contract_handoff_ready),
        "codex_final_product_handoff_ready": False,
        "model_training_ready": False,
        "production_ranking_ready": False,
        "outreach_ready": False,
        "automatic_approval_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "outcome_event_insertion_count": 0,
        "model_training_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    if write_contracts:
        _atomic_json(
            contract_root / "manual_decision_validation.json",
            validation_report,
        )

        _atomic_json(
            contract_root / "historical_registration_execution_envelope.json",
            historical_envelope,
        )

        _atomic_json(
            contract_root / "outcome_ledger_bootstrap_envelope.json",
            outcome_envelope,
        )

        _atomic_json(
            contract_root / "codex_handoff_gate_graph.json",
            gate_graph,
        )

        _atomic_json(
            contract_root / "manual_activation_envelope_summary.json",
            summary,
        )

        _atomic_text(
            contract_root / "manual_activation_envelopes.md",
            "\n".join(
                [
                    "# Manual Activation Envelopes",
                    "",
                    (
                        "Human decisions are validated against "
                        "current evidence digests before any "
                        "execution layer may be prepared."
                    ),
                    "",
                    (f"- Completed source decisions: `{source_complete_count}`"),
                    (f"- Stale source decisions: `{stale_source_decision_count}`"),
                    (f"- Completed client inputs: `{client_complete_count}`"),
                    (f"- Historical dry run ready: `{str(historical_dry_run_ready).lower()}`"),
                    (
                        "- Outcome-ledger ephemeral bootstrap ready: "
                        f"`{str(outcome_bootstrap_ready).lower()}`"
                    ),
                    (
                        "- Codex contract handoff ready: "
                        f"`{str(codex_contract_handoff_ready).lower()}`"
                    ),
                    ("- Codex final product handoff ready: `false`"),
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
        "validation": validation_report,
        "historical_envelope": historical_envelope,
        "outcome_envelope": outcome_envelope,
        "gate_graph": gate_graph,
    }
