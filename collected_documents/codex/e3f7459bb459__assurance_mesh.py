from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from collections import deque
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only_input_validation": True,
    "deterministic_double_build_required": True,
    "artifact_digest_continuity_required": True,
    "dependency_dag_required": True,
    "adversarial_scenario_matrix_required": True,
    "state_aware_invariants_required": True,
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


REQUIRED_ARTIFACT_IDS = {
    "governance_decisions",
    "governance_approval_packets",
    "client_questionnaire",
    "manual_decision_validation",
    "manual_activation_summary",
    "historical_envelope",
    "outcome_envelope",
    "codex_gate_graph",
    "outcome_activation_template",
    "outcome_contract",
    "codex_manifest",
    "human_workbench_summary",
    "permit_review_workbook",
    "client_answer_workbook",
    "gate_command_templates",
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


def _topological_order(
    node_ids: set[str],
    edges: list[dict[str, Any]],
) -> tuple[
    list[str],
    list[str],
    list[str],
]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}

    indegree: dict[str, int] = {node_id: 0 for node_id in node_ids}

    invalid_edges: list[str] = []

    for edge in edges:
        raw_source = edge.get("from")

        raw_target = edge.get("to")

        if not isinstance(
            raw_source,
            str,
        ) or not isinstance(
            raw_target,
            str,
        ):
            invalid_edges.append("malformed_edge")
            continue

        if raw_source not in node_ids or raw_target not in node_ids:
            invalid_edges.append(f"{raw_source}->{raw_target}")
            continue

        if raw_target not in adjacency[raw_source]:
            adjacency[raw_source].add(raw_target)

            indegree[raw_target] += 1

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))

    order: list[str] = []

    while queue:
        node_id = queue.popleft()
        order.append(node_id)

        for target in sorted(adjacency[node_id]):
            indegree[target] -= 1

            if indegree[target] == 0:
                queue.append(target)

    cycle_nodes = sorted(node_id for node_id, degree in indegree.items() if degree > 0)

    return (
        order,
        cycle_nodes,
        sorted(set(invalid_edges)),
    )


def _evaluate_state(
    *,
    packets: dict[str, dict[str, Any]],
    questionnaire: dict[str, dict[str, Any]],
    source_decisions: list[dict[str, Any]],
    client_inputs: list[dict[str, Any]],
    recommended_source_id: str,
    outcome_template_continuity: bool,
) -> dict[str, Any]:
    source_decision_by_id = _index_unique(
        source_decisions,
        key_name="source_id",
        label="scenario source decision",
    )

    client_input_by_id = _index_unique(
        client_inputs,
        key_name="input_id",
        label="scenario client input",
    )

    source_complete_count = 0
    source_results: dict[str, bool] = {}

    for source_id, packet in packets.items():
        decision = source_decision_by_id.get(source_id)

        evidence = packet.get("evidence")

        if not isinstance(
            evidence,
            dict,
        ):
            source_results[source_id] = False
            continue

        candidate_record_keys = _string_list(
            evidence.get(
                "candidate_record_keys",
                [],
            ),
            label=(f"{source_id}.candidate_record_keys"),
        )

        candidate_temporal_fields = _string_list(
            evidence.get(
                "candidate_temporal_fields",
                [],
            ),
            label=(f"{source_id}.candidate_temporal_fields"),
        )

        complete = False

        if decision is not None:
            approved_temporal_fields = _string_list(
                decision.get(
                    "approved_temporal_fields",
                    [],
                ),
                label=(f"{source_id}.approved_temporal_fields"),
            )

            approved_record_key = decision.get("approved_record_key")

            expected_digest = packet.get("evidence_bundle_digest")

            complete = bool(
                decision.get("evidence_bundle_digest") == expected_digest
                and decision.get("parser_contract_approved") is True
                and decision.get("schema_contract_approved") is True
                and isinstance(
                    approved_record_key,
                    str,
                )
                and approved_record_key in candidate_record_keys
                and approved_temporal_fields
                and set(approved_temporal_fields).issubset(set(candidate_temporal_fields))
                and decision.get("capture_policy_approved") is True
                and decision.get("change_contract_approved") is True
                and decision.get("registration_approved") is True
                and _meaningful(decision.get("reviewer_id"))
                and _meaningful(decision.get("reviewed_at"))
                and _meaningful(decision.get("evidence_reference"))
            )

        source_results[source_id] = complete

        if complete:
            source_complete_count += 1

    client_complete_count = 0
    client_results: dict[str, bool] = {}

    for input_id, definition in questionnaire.items():
        supplied = client_input_by_id.get(input_id)

        required_fields = _string_list(
            definition.get(
                "required_fields",
                [],
            ),
            label=(f"{input_id}.required_fields"),
        )

        complete = False

        if supplied is not None:
            authoritative_value = supplied.get("authoritative_value")

            normalized_value: dict[str, Any] | None = None

            if isinstance(
                authoritative_value,
                dict,
            ):
                normalized_value = {
                    str(key): item_value for key, item_value in authoritative_value.items()
                }

            complete = bool(
                normalized_value is not None
                and all(
                    required_field in normalized_value
                    and _meaningful(normalized_value[required_field])
                    for required_field in required_fields
                )
                and supplied.get("confirmed") is True
                and _meaningful(supplied.get("confirmed_by"))
                and _meaningful(supplied.get("confirmed_at"))
                and _meaningful(supplied.get("evidence_reference"))
            )

        client_results[input_id] = complete

        if complete:
            client_complete_count += 1

    recommended_source_complete = bool(
        source_results.get(
            recommended_source_id,
            False,
        )
    )

    all_client_inputs_complete = bool(client_results and all(client_results.values()))

    historical_dry_run_ready = recommended_source_complete

    outcome_bootstrap_ready = bool(all_client_inputs_complete and outcome_template_continuity)

    codex_contract_handoff_ready = bool(all_client_inputs_complete and outcome_template_continuity)

    return {
        "source_complete_count": (source_complete_count),
        "client_complete_count": (client_complete_count),
        "recommended_source_complete": (recommended_source_complete),
        "all_client_inputs_complete": (all_client_inputs_complete),
        "historical_dry_run_ready": (historical_dry_run_ready),
        "outcome_bootstrap_ready": (outcome_bootstrap_ready),
        "codex_contract_handoff_ready": (codex_contract_handoff_ready),
        "codex_final_product_handoff_ready": False,
        "authoritative_registration_enabled": False,
        "persistent_outcome_ledger_enabled": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
    }


def _complete_source_decision(
    *,
    packet: dict[str, Any],
    current_decision: dict[str, Any],
) -> dict[str, Any]:
    completed = copy.deepcopy(current_decision)

    evidence = packet.get("evidence")

    if not isinstance(
        evidence,
        dict,
    ):
        raise RuntimeError("Scenario packet evidence is malformed.")

    candidate_record_keys = _string_list(
        evidence.get(
            "candidate_record_keys",
            [],
        ),
        label="scenario candidate record keys",
    )

    candidate_temporal_fields = _string_list(
        evidence.get(
            "candidate_temporal_fields",
            [],
        ),
        label="scenario candidate temporal fields",
    )

    if not candidate_record_keys:
        raise RuntimeError("Scenario source has no record-key candidate.")

    if not candidate_temporal_fields:
        raise RuntimeError("Scenario source has no temporal candidate.")

    completed.update(
        {
            "evidence_bundle_digest": packet["evidence_bundle_digest"],
            "parser_contract_approved": True,
            "schema_contract_approved": True,
            "approved_record_key": (candidate_record_keys[0]),
            "approved_temporal_fields": [candidate_temporal_fields[0]],
            "capture_policy_approved": True,
            "change_contract_approved": True,
            "registration_approved": True,
            "reviewer_id": ("assurance-scenario-reviewer"),
            "reviewed_at": ("2026-07-27T12:00:00-04:00"),
            "evidence_reference": ("assurance-scenario-evidence"),
        }
    )

    return completed


def _complete_client_input(
    *,
    definition: dict[str, Any],
    current_input: dict[str, Any],
) -> dict[str, Any]:
    completed = copy.deepcopy(current_input)

    required_fields = _string_list(
        definition.get(
            "required_fields",
            [],
        ),
        label="scenario required client fields",
    )

    completed.update(
        {
            "authoritative_value": {
                required_field: ("assurance-scenario-value") for required_field in required_fields
            },
            "confirmed": True,
            "confirmed_by": ("assurance-scenario-client-authority"),
            "confirmed_at": ("2026-07-27T12:00:00-04:00"),
            "evidence_reference": ("assurance-scenario-client-evidence"),
        }
    )

    return completed


def _scenario_result(
    *,
    scenario_id: str,
    description: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    compared = {key: actual.get(key) for key in expected}

    passed = compared == expected

    return {
        "scenario_id": scenario_id,
        "description": description,
        "expected": expected,
        "actual": compared,
        "passed": passed,
        "authoritative_execution_count": 0,
        "persistent_database_creation_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }


def _build_payloads(
    project_root: Path,
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    artifact_rows = _object_list(
        config.get("artifact_nodes"),
        label="artifact_nodes",
    )

    edge_rows = _object_list(
        config.get("dependency_edges"),
        label="dependency_edges",
    )

    node_by_id = _index_unique(
        artifact_rows,
        key_name="artifact_id",
        label="artifact node",
    )

    node_ids = set(node_by_id)

    missing_required_ids = sorted(REQUIRED_ARTIFACT_IDS - node_ids)

    if missing_required_ids:
        raise RuntimeError(f"Assurance config lacks required nodes: {missing_required_ids}")

    recommended_source_id = str(config["recommended_source_id"])

    inventory_rows: list[dict[str, Any]] = []

    missing_required_paths: list[str] = []

    for artifact_id in sorted(node_by_id):
        node = node_by_id[artifact_id]

        relative_path = node.get("path")

        if not isinstance(
            relative_path,
            str,
        ):
            raise RuntimeError(f"Artifact path is invalid: {artifact_id}")

        path = project_root / relative_path

        exists = path.is_file()
        required = bool(node.get("required") is True)

        if required and not exists:
            missing_required_paths.append(relative_path)

        inventory_rows.append(
            {
                "artifact_id": artifact_id,
                "path": relative_path,
                "role": node.get("role"),
                "required": required,
                "exists": exists,
                "size_bytes": (path.stat().st_size if exists else None),
                "sha256": (_file_digest(path) if exists else None),
            }
        )

    inventory_report: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-artifact-inventory-v1"),
        "artifact_count": len(inventory_rows),
        "present_artifact_count": sum(bool(row["exists"]) for row in inventory_rows),
        "required_artifact_count": sum(bool(row["required"]) for row in inventory_rows),
        "missing_required_artifact_count": len(missing_required_paths),
        "missing_required_paths": (missing_required_paths),
        "artifacts": inventory_rows,
    }

    (
        topological_order,
        cycle_nodes,
        invalid_edges,
    ) = _topological_order(
        node_ids,
        edge_rows,
    )

    dependency_report: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-dependency-graph-v1"),
        "node_count": len(node_ids),
        "edge_count": len(edge_rows),
        "topological_order": (topological_order),
        "cycle_node_count": len(cycle_nodes),
        "cycle_nodes": cycle_nodes,
        "invalid_edge_count": len(invalid_edges),
        "invalid_edges": invalid_edges,
        "acyclic": (
            not cycle_nodes and not invalid_edges and len(topological_order) == len(node_ids)
        ),
        "edges": edge_rows,
    }

    def load_artifact(
        artifact_id: str,
    ) -> dict[str, Any]:
        node = node_by_id[artifact_id]

        relative_path = node.get("path")

        if not isinstance(
            relative_path,
            str,
        ):
            raise RuntimeError(f"Invalid artifact path: {artifact_id}")

        return _load_object(project_root / relative_path)

    governance_decisions = load_artifact("governance_decisions")

    approval_packets = load_artifact("governance_approval_packets")

    client_questionnaire = load_artifact("client_questionnaire")

    manual_activation_summary = load_artifact("manual_activation_summary")

    historical_envelope = load_artifact("historical_envelope")

    outcome_envelope = load_artifact("outcome_envelope")

    codex_gate_graph = load_artifact("codex_gate_graph")

    outcome_activation_template = load_artifact("outcome_activation_template")

    outcome_contract = load_artifact("outcome_contract")

    codex_manifest = load_artifact("codex_manifest")

    human_workbench_summary = load_artifact("human_workbench_summary")

    packet_rows = _object_list(
        approval_packets.get("packets"),
        label="approval packets",
    )

    questionnaire_rows = _object_list(
        client_questionnaire.get("sections"),
        label="questionnaire sections",
    )

    source_decision_rows = _object_list(
        governance_decisions.get("source_decisions"),
        label="source decisions",
    )

    client_input_rows = _object_list(
        governance_decisions.get("client_inputs"),
        label="client inputs",
    )

    packet_by_source = _index_unique(
        packet_rows,
        key_name="source_id",
        label="approval packet",
    )

    questionnaire_by_id = _index_unique(
        questionnaire_rows,
        key_name="input_id",
        label="questionnaire section",
    )

    source_decision_by_id = _index_unique(
        source_decision_rows,
        key_name="source_id",
        label="source decision",
    )

    client_input_by_id = _index_unique(
        client_input_rows,
        key_name="input_id",
        label="client input",
    )

    current_decision_digest = _stable_digest(governance_decisions)

    expected_decision_digest = human_workbench_summary.get("decision_bundle_digest")

    current_activation_digest = _stable_digest(manual_activation_summary)

    expected_activation_digest = human_workbench_summary.get("activation_summary_digest")

    template_schema_fingerprint = outcome_activation_template.get("outcome_schema_fingerprint")

    current_schema_fingerprint = outcome_contract.get("schema_fingerprint")

    template_questionnaire_digest = outcome_activation_template.get("client_questionnaire_digest")

    current_questionnaire_digest = client_questionnaire.get("questionnaire_digest")

    outcome_template_continuity = bool(
        template_schema_fingerprint == current_schema_fingerprint
        and template_questionnaire_digest == current_questionnaire_digest
    )

    manifest_rows = _object_list(
        codex_manifest.get("artifacts"),
        label="Codex manifest artifacts",
    )

    manifest_results: list[dict[str, Any]] = []

    for row in manifest_rows:
        relative_path = row.get("path")

        expected_sha256 = row.get("sha256")

        if not isinstance(
            relative_path,
            str,
        ):
            raise RuntimeError("Codex manifest path is invalid.")

        path = project_root / relative_path

        actual_sha256 = _file_digest(path) if path.is_file() else None

        manifest_results.append(
            {
                "path": relative_path,
                "exists": path.is_file(),
                "expected_sha256": (expected_sha256),
                "actual_sha256": (actual_sha256),
                "digest_match": bool(actual_sha256 == expected_sha256),
            }
        )

    stale_source_rows: list[dict[str, Any]] = []

    for source_id, packet in packet_by_source.items():
        decision = source_decision_by_id.get(source_id)

        expected_digest = packet.get("evidence_bundle_digest")

        supplied_digest = None if decision is None else decision.get("evidence_bundle_digest")

        stale_source_rows.append(
            {
                "source_id": source_id,
                "expected_digest": (expected_digest),
                "supplied_digest": (supplied_digest),
                "digest_match": bool(expected_digest == supplied_digest),
            }
        )

    drift_report: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-drift-report-v1"),
        "decision_bundle_digest_match": bool(current_decision_digest == expected_decision_digest),
        "current_decision_bundle_digest": (current_decision_digest),
        "expected_decision_bundle_digest": (expected_decision_digest),
        "activation_summary_digest_match": bool(
            current_activation_digest == expected_activation_digest
        ),
        "current_activation_summary_digest": (current_activation_digest),
        "expected_activation_summary_digest": (expected_activation_digest),
        "outcome_template_continuity": (outcome_template_continuity),
        "source_evidence_row_count": len(stale_source_rows),
        "stale_source_evidence_count": sum(
            not bool(row["digest_match"]) for row in stale_source_rows
        ),
        "source_evidence_results": (stale_source_rows),
        "codex_manifest_artifact_count": len(manifest_results),
        "codex_manifest_drift_count": sum(
            not bool(row["digest_match"]) for row in manifest_results
        ),
        "codex_manifest_results": (manifest_results),
    }

    baseline_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=source_decision_rows,
        client_inputs=client_input_rows,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=(outcome_template_continuity),
    )

    baseline_expected = {
        "recommended_source_complete": bool(
            manual_activation_summary.get("recommended_source_approval_ready") is True
        ),
        "historical_dry_run_ready": bool(
            manual_activation_summary.get("historical_registration_dry_run_ready") is True
        ),
        "outcome_bootstrap_ready": bool(
            manual_activation_summary.get("outcome_ledger_ephemeral_bootstrap_ready") is True
        ),
        "codex_contract_handoff_ready": bool(
            manual_activation_summary.get("codex_contract_handoff_ready") is True
        ),
        "codex_final_product_handoff_ready": bool(
            manual_activation_summary.get("codex_final_product_handoff_ready") is True
        ),
    }

    scenarios: list[dict[str, Any]] = []

    scenarios.append(
        _scenario_result(
            scenario_id="baseline_current_state",
            description=("Current decisions must reproduce the committed activation summary."),
            actual=baseline_actual,
            expected=baseline_expected,
        )
    )

    stale_source_decisions = copy.deepcopy(source_decision_rows)

    for decision in stale_source_decisions:
        if decision.get("source_id") == recommended_source_id:
            decision["evidence_bundle_digest"] = "0" * 64

    stale_source_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=(stale_source_decisions),
        client_inputs=client_input_rows,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=(outcome_template_continuity),
    )

    scenarios.append(
        _scenario_result(
            scenario_id="stale_source_digest",
            description=(
                "A stale evidence digest must block the recommended source and historical gate."
            ),
            actual=stale_source_actual,
            expected={
                "recommended_source_complete": False,
                "historical_dry_run_ready": False,
                "authoritative_registration_enabled": False,
            },
        )
    )

    partial_source_decisions = copy.deepcopy(source_decision_rows)

    for decision in partial_source_decisions:
        if decision.get("source_id") == recommended_source_id:
            decision.update(
                {
                    "parser_contract_approved": True,
                    "schema_contract_approved": True,
                    "capture_policy_approved": True,
                    "change_contract_approved": True,
                    "registration_approved": True,
                }
            )

    partial_source_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=(partial_source_decisions),
        client_inputs=client_input_rows,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=(outcome_template_continuity),
    )

    scenarios.append(
        _scenario_result(
            scenario_id="partial_source_approval",
            description=(
                "Boolean approvals without record identity, "
                "temporal semantics and reviewer attribution "
                "must remain incomplete."
            ),
            actual=partial_source_actual,
            expected={
                "recommended_source_complete": False,
                "historical_dry_run_ready": False,
            },
        )
    )

    complete_source_decisions = copy.deepcopy(source_decision_rows)

    recommended_packet = packet_by_source.get(recommended_source_id)

    recommended_decision = source_decision_by_id.get(recommended_source_id)

    if recommended_packet is None:
        raise RuntimeError("Recommended source packet is missing.")

    if recommended_decision is None:
        raise RuntimeError("Recommended source decision is missing.")

    completed_source = _complete_source_decision(
        packet=recommended_packet,
        current_decision=(recommended_decision),
    )

    complete_source_decisions = [
        (completed_source if decision.get("source_id") == recommended_source_id else decision)
        for decision in complete_source_decisions
    ]

    complete_source_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=(complete_source_decisions),
        client_inputs=client_input_rows,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=(outcome_template_continuity),
    )

    scenarios.append(
        _scenario_result(
            scenario_id="complete_source_review",
            description=(
                "A complete named source review may open only the dry-run readiness gate."
            ),
            actual=complete_source_actual,
            expected={
                "recommended_source_complete": True,
                "historical_dry_run_ready": True,
                "authoritative_registration_enabled": False,
                "codex_final_product_handoff_ready": False,
            },
        )
    )

    complete_client_inputs = [
        _complete_client_input(
            definition=questionnaire_by_id[str(client_input["input_id"])],
            current_input=client_input,
        )
        for client_input in client_input_rows
    ]

    missing_economics_inputs = [
        (
            client_input_by_id["transaction_economics"]
            if completed_input.get("input_id") == "transaction_economics"
            else completed_input
        )
        for completed_input in complete_client_inputs
    ]

    missing_economics_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=source_decision_rows,
        client_inputs=missing_economics_inputs,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=(outcome_template_continuity),
    )

    scenarios.append(
        _scenario_result(
            scenario_id="missing_transaction_economics",
            description=(
                "Four complete client inputs without "
                "transaction economics must not open "
                "outcome or Codex contract gates."
            ),
            actual=missing_economics_actual,
            expected={
                "client_complete_count": 4,
                "all_client_inputs_complete": False,
                "outcome_bootstrap_ready": False,
                "codex_contract_handoff_ready": False,
            },
        )
    )

    stale_outcome_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=source_decision_rows,
        client_inputs=complete_client_inputs,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=False,
    )

    scenarios.append(
        _scenario_result(
            scenario_id="stale_outcome_template",
            description=(
                "Complete client inputs cannot bypass a stale schema or questionnaire digest."
            ),
            actual=stale_outcome_actual,
            expected={
                "all_client_inputs_complete": True,
                "outcome_bootstrap_ready": False,
                "codex_contract_handoff_ready": False,
                "codex_final_product_handoff_ready": False,
            },
        )
    )

    complete_clients_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=source_decision_rows,
        client_inputs=complete_client_inputs,
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=True,
    )

    scenarios.append(
        _scenario_result(
            scenario_id="complete_client_inputs",
            description=(
                "Complete current client inputs may open "
                "ephemeral outcome and contract handoff "
                "readiness, but never final product handoff."
            ),
            actual=complete_clients_actual,
            expected={
                "all_client_inputs_complete": True,
                "outcome_bootstrap_ready": True,
                "codex_contract_handoff_ready": True,
                "codex_final_product_handoff_ready": False,
                "persistent_outcome_ledger_enabled": False,
            },
        )
    )

    complete_preconditions_actual = _evaluate_state(
        packets=packet_by_source,
        questionnaire=questionnaire_by_id,
        source_decisions=(complete_source_decisions),
        client_inputs=(complete_client_inputs),
        recommended_source_id=(recommended_source_id),
        outcome_template_continuity=True,
    )

    scenarios.append(
        _scenario_result(
            scenario_id="complete_pre_execution_inputs",
            description=(
                "Complete reviewer and client inputs open "
                "readiness only; authoritative execution, "
                "final handoff, ranking and outreach remain "
                "separately disabled."
            ),
            actual=complete_preconditions_actual,
            expected={
                "recommended_source_complete": True,
                "historical_dry_run_ready": True,
                "outcome_bootstrap_ready": True,
                "codex_contract_handoff_ready": True,
                "codex_final_product_handoff_ready": False,
                "authoritative_registration_enabled": False,
                "persistent_outcome_ledger_enabled": False,
                "production_ranking_enabled": False,
                "outreach_enabled": False,
            },
        )
    )

    scenario_report: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-scenario-matrix-v1"),
        "scenario_count": len(scenarios),
        "passed_scenario_count": sum(bool(scenario["passed"]) for scenario in scenarios),
        "failed_scenario_count": sum(not bool(scenario["passed"]) for scenario in scenarios),
        "scenarios": scenarios,
        "database_access_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "outcome_event_insertion_count": 0,
        "model_training_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    recommended_ready = bool(
        manual_activation_summary.get("recommended_source_approval_ready") is True
    )

    historical_ready = bool(historical_envelope.get("dry_run_ready") is True)

    client_complete_count = int(
        manual_activation_summary.get(
            "client_input_complete_count",
            0,
        )
    )

    client_required_count = int(
        manual_activation_summary.get(
            "client_input_required_count",
            0,
        )
    )

    outcome_ready = bool(outcome_envelope.get("ephemeral_bootstrap_ready") is True)

    codex_contract_ready = bool(codex_gate_graph.get("codex_contract_handoff_ready") is True)

    codex_final_ready = bool(codex_gate_graph.get("codex_final_product_handoff_ready") is True)

    controlled_pilot_complete = bool(codex_gate_graph.get("controlled_pilot_complete") is True)

    incremental_roi_proven = bool(codex_gate_graph.get("incremental_roi_proven") is True)

    production_governance_ready = bool(codex_gate_graph.get("production_governance_ready") is True)

    execution_counter_fields = (
        "database_write_count",
        "snapshot_registration_count",
        "outcome_event_insertion_count",
        "model_training_execution_count",
        "pilot_execution_count",
        "production_ranking_execution_count",
        "outreach_execution_count",
    )

    execution_counters_zero = all(
        int(
            human_workbench_summary.get(
                field,
                0,
            )
        )
        == 0
        for field in execution_counter_fields
    )

    invariant_results = [
        {
            "invariant_id": ("required_artifacts_present"),
            "description": ("Every required assurance input exists."),
            "passed": (inventory_report["missing_required_artifact_count"] == 0),
        },
        {
            "invariant_id": ("dependency_graph_acyclic"),
            "description": ("The contract dependency graph is a DAG."),
            "passed": bool(dependency_report["acyclic"]),
        },
        {
            "invariant_id": ("decision_digest_continuity"),
            "description": ("The current decision bundle matches the workbench continuity digest."),
            "passed": bool(drift_report["decision_bundle_digest_match"]),
        },
        {
            "invariant_id": ("activation_digest_continuity"),
            "description": (
                "The current activation summary matches the workbench continuity digest."
            ),
            "passed": bool(drift_report["activation_summary_digest_match"]),
        },
        {
            "invariant_id": ("source_evidence_continuity"),
            "description": ("Every source decision references its current evidence bundle digest."),
            "passed": (drift_report["stale_source_evidence_count"] == 0),
        },
        {
            "invariant_id": ("codex_manifest_continuity"),
            "description": ("Every Codex manifest artifact matches its recorded checksum."),
            "passed": (drift_report["codex_manifest_drift_count"] == 0),
        },
        {
            "invariant_id": ("historical_gate_implication"),
            "description": (
                "Historical dry-run readiness cannot be true "
                "without a complete recommended-source review."
            ),
            "passed": bool(not historical_ready or recommended_ready),
        },
        {
            "invariant_id": ("outcome_gate_implication"),
            "description": (
                "Outcome bootstrap cannot be ready until all client inputs are complete."
            ),
            "passed": bool(not outcome_ready or client_complete_count == client_required_count),
        },
        {
            "invariant_id": ("codex_contract_gate_implication"),
            "description": (
                "Codex contract handoff cannot be ready until all client inputs are complete."
            ),
            "passed": bool(
                not codex_contract_ready or client_complete_count == client_required_count
            ),
        },
        {
            "invariant_id": ("codex_final_gate_implication"),
            "description": (
                "Final product handoff requires a controlled "
                "pilot, incremental ROI and production "
                "governance."
            ),
            "passed": bool(
                not codex_final_ready
                or (
                    controlled_pilot_complete
                    and incremental_roi_proven
                    and production_governance_ready
                )
            ),
        },
        {
            "invariant_id": ("execution_counters_zero"),
            "description": ("The assurance layer performs no execution."),
            "passed": (execution_counters_zero),
        },
        {
            "invariant_id": ("adversarial_scenarios_pass"),
            "description": (
                "Every adversarial gate scenario produces the expected fail-closed result."
            ),
            "passed": (scenario_report["failed_scenario_count"] == 0),
        },
    ]

    invariant_report: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-invariant-results-v1"),
        "invariant_count": len(invariant_results),
        "passed_invariant_count": sum(bool(result["passed"]) for result in invariant_results),
        "failed_invariant_count": sum(not bool(result["passed"]) for result in invariant_results),
        "results": invariant_results,
    }

    recovery_rows = [
        {
            "gate_id": ("recommended_source_review"),
            "current_ready": (recommended_ready),
            "required_artifacts": [
                ("docs/data_contracts/brampton_permit_review_workbook.md"),
                ("config/governance_decisions.json"),
            ],
            "required_actions": [
                "Review the checksum-bound permit evidence.",
                "Select an approved record key.",
                "Select valid temporal fields.",
                "Record named reviewer attribution.",
                "Record explicit source approvals.",
            ],
        },
        {
            "gate_id": ("historical_registration_dry_run"),
            "current_ready": (historical_ready),
            "required_artifacts": [
                ("docs/data_contracts/historical_registration_execution_envelope.json")
            ],
            "required_actions": [
                ("Complete the recommended-source review."),
                ("Rebuild manual activation envelopes."),
                ("Generate a separate non-authoritative dry-run implementation."),
            ],
        },
        {
            "gate_id": ("all_client_inputs"),
            "current_ready": bool(
                client_complete_count == client_required_count and client_required_count > 0
            ),
            "required_artifacts": [
                ("docs/data_contracts/client_answer_workbook.md"),
                ("config/governance_decisions.json"),
            ],
            "required_actions": [
                "Complete all five authoritative answers.",
                "Record named client confirmation.",
                "Record confirmation timestamps.",
                "Attach evidence references.",
            ],
        },
        {
            "gate_id": ("outcome_ledger_ephemeral_bootstrap"),
            "current_ready": (outcome_ready),
            "required_artifacts": [
                ("docs/data_contracts/outcome_ledger_bootstrap_envelope.json"),
                ("docs/data_contracts/outcome_collection_schema.sql"),
            ],
            "required_actions": [
                "Complete all client inputs.",
                "Revalidate schema continuity.",
                ("Run only a disposable bootstrap before any persistent database is created."),
            ],
        },
        {
            "gate_id": ("codex_contract_handoff"),
            "current_ready": (codex_contract_ready),
            "required_artifacts": [("docs/data_contracts/codex_contract_bundle_manifest.json")],
            "required_actions": [
                "Complete all five client inputs.",
                "Recompute all contract artifact checksums.",
                ("Limit Codex to application shell and stable contract adapters."),
            ],
        },
        {
            "gate_id": ("codex_final_product_handoff"),
            "current_ready": (codex_final_ready),
            "required_artifacts": [("docs/data_contracts/codex_handoff_gate_graph.json")],
            "required_actions": [
                "Collect repeated historical snapshots.",
                "Collect real censored outcome labels.",
                "Build a leakage-safe point-in-time dataset.",
                "Train transparent baseline models.",
                "Complete temporal backtesting.",
                "Complete calibration.",
                "Complete shadow and controlled pilots.",
                "Prove incremental ROI.",
                "Complete production governance.",
            ],
        },
    ]

    recovery_report: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-recovery-map-v1"),
        "gate_count": len(recovery_rows),
        "ready_gate_count": sum(bool(row["current_ready"]) for row in recovery_rows),
        "blocked_gate_count": sum(not bool(row["current_ready"]) for row in recovery_rows),
        "gates": recovery_rows,
        "automatic_execution_enabled": False,
    }

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-assurance-mesh-v1"),
        "assurance_layer_count": 8,
        "artifact_count": (inventory_report["artifact_count"]),
        "missing_required_artifact_count": (inventory_report["missing_required_artifact_count"]),
        "dependency_node_count": (dependency_report["node_count"]),
        "dependency_edge_count": (dependency_report["edge_count"]),
        "dependency_graph_acyclic": (dependency_report["acyclic"]),
        "decision_bundle_digest_match": (drift_report["decision_bundle_digest_match"]),
        "activation_summary_digest_match": (drift_report["activation_summary_digest_match"]),
        "stale_source_evidence_count": (drift_report["stale_source_evidence_count"]),
        "codex_manifest_drift_count": (drift_report["codex_manifest_drift_count"]),
        "scenario_count": (scenario_report["scenario_count"]),
        "passed_scenario_count": (scenario_report["passed_scenario_count"]),
        "failed_scenario_count": (scenario_report["failed_scenario_count"]),
        "invariant_count": (invariant_report["invariant_count"]),
        "passed_invariant_count": (invariant_report["passed_invariant_count"]),
        "failed_invariant_count": (invariant_report["failed_invariant_count"]),
        "recommended_source_ready": (recommended_ready),
        "client_input_complete_count": (client_complete_count),
        "client_input_required_count": (client_required_count),
        "historical_dry_run_ready": (historical_ready),
        "outcome_bootstrap_ready": (outcome_ready),
        "codex_contract_handoff_ready": (codex_contract_ready),
        "codex_final_product_handoff_ready": (codex_final_ready),
        "automatic_approval_count": 0,
        "client_value_invention_count": 0,
        "decision_bundle_mutation_count": 0,
        "executable_command_creation_count": 0,
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
    }

    return {
        "inventory": inventory_report,
        "dependency_graph": (dependency_report),
        "drift": drift_report,
        "scenarios": scenario_report,
        "invariants": invariant_report,
        "recovery": recovery_report,
        "summary": summary,
    }


def build_assurance_mesh(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "assurance_mesh.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Assurance policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Assurance policy mismatch.")

    first = _build_payloads(
        project_root,
        config,
    )

    second = _build_payloads(
        project_root,
        config,
    )

    first_digest = _stable_digest(first)

    second_digest = _stable_digest(second)

    reproducibility_match = bool(first_digest == second_digest)

    reproducibility_report: dict[
        str,
        Any,
    ] = {
        "model_version": ("cre-foundry-assurance-reproducibility-v1"),
        "first_build_digest": (first_digest),
        "second_build_digest": (second_digest),
        "reproducibility_match": (reproducibility_match),
        "build_count": 2,
        "input_mutation_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
    }

    result = first

    invariant_report = result["invariants"]

    raw_results = invariant_report.get("results")

    invariant_rows = _object_list(
        raw_results,
        label="assurance invariant results",
    )

    invariant_rows.append(
        {
            "invariant_id": ("deterministic_double_build"),
            "description": (
                "Two complete assurance builds over the same inputs produce identical digests."
            ),
            "passed": (reproducibility_match),
        }
    )

    invariant_report["results"] = invariant_rows

    invariant_report["invariant_count"] = len(invariant_rows)

    invariant_report["passed_invariant_count"] = sum(bool(row["passed"]) for row in invariant_rows)

    invariant_report["failed_invariant_count"] = sum(
        not bool(row["passed"]) for row in invariant_rows
    )

    summary = result["summary"]

    summary["reproducibility_match"] = reproducibility_match

    summary["invariant_count"] = invariant_report["invariant_count"]

    summary["passed_invariant_count"] = invariant_report["passed_invariant_count"]

    summary["failed_invariant_count"] = invariant_report["failed_invariant_count"]

    result["reproducibility"] = reproducibility_report

    if write_contracts:
        root = project_root / "docs" / "data_contracts"

        _atomic_json(
            root / "assurance_artifact_inventory.json",
            result["inventory"],
        )

        _atomic_json(
            root / "assurance_dependency_graph.json",
            result["dependency_graph"],
        )

        _atomic_json(
            root / "assurance_drift_report.json",
            result["drift"],
        )

        _atomic_json(
            root / "assurance_scenario_matrix.json",
            result["scenarios"],
        )

        _atomic_json(
            root / "assurance_invariant_results.json",
            result["invariants"],
        )

        _atomic_json(
            root / "assurance_reproducibility_report.json",
            reproducibility_report,
        )

        _atomic_json(
            root / "assurance_recovery_map.json",
            result["recovery"],
        )

        _atomic_json(
            root / "assurance_mesh_summary.json",
            summary,
        )

        _atomic_text(
            root / "assurance_mesh.md",
            "\n".join(
                [
                    "# Assurance Mesh",
                    "",
                    (
                        "The assurance mesh validates artifact "
                        "lineage, digests, dependencies, gate "
                        "logic, adversarial scenarios and "
                        "deterministic reproducibility."
                    ),
                    "",
                    (f"- Assurance layers: `{summary['assurance_layer_count']}`"),
                    (f"- Artifacts: `{summary['artifact_count']}`"),
                    (
                        f"- Missing required artifacts: "
                        f"`{summary['missing_required_artifact_count']}`"
                    ),
                    (
                        "- Dependency graph acyclic: "
                        f"`{str(summary['dependency_graph_acyclic']).lower()}`"
                    ),
                    (f"- Adversarial scenarios: `{summary['scenario_count']}`"),
                    (f"- Passed scenarios: `{summary['passed_scenario_count']}`"),
                    (f"- Invariants: `{summary['invariant_count']}`"),
                    (f"- Passed invariants: `{summary['passed_invariant_count']}`"),
                    (
                        "- Deterministic double build: "
                        f"`{str(summary['reproducibility_match']).lower()}`"
                    ),
                    "",
                    (
                        "- Historical dry-run ready: "
                        f"`{str(summary['historical_dry_run_ready']).lower()}`"
                    ),
                    (
                        "- Outcome bootstrap ready: "
                        f"`{str(summary['outcome_bootstrap_ready']).lower()}`"
                    ),
                    (
                        "- Codex contract handoff ready: "
                        f"`{str(summary['codex_contract_handoff_ready']).lower()}`"
                    ),
                    (
                        "- Codex final handoff ready: "
                        f"`{str(summary['codex_final_product_handoff_ready']).lower()}`"
                    ),
                    "",
                    "- Automatic approvals: `0`",
                    "- Invented client values: `0`",
                    "- Input mutations: `0`",
                    "- Executable commands created: `0`",
                    "- Archives created: `0`",
                    "- Database accesses: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Model training executions: `0`",
                    "- Pilot executions: `0`",
                    "- Production rankings: `0`",
                    "- Outreach executions: `0`",
                    "",
                ]
            ),
        )

    return result
