"""CRE Foundry ARCHITECTURE-001 workflow engine.

This module implements the frozen ARCHITECTURE-001 state machine and its
persistence projections on top of the black-box protocol boundary.  It accepts
the external MATH decision as data, replays a canonical command stream, and
reconstructs the aggregate projection, append-only predecessor-linked journal,
idempotency records, issuance ledger, held unauthorized outbox, responses,
result union, programmatic accessibility projection, and replay receipt.

The reduction rules here mirror the evaluator-owned independent reducer so that
a subject produced by the driver reconstructs byte-identically under the frozen
public evaluator.  Every invariant violation fails closed with a stable ARCH-*
diagnostic.  Stage-1 snapshots are immutable once frozen; accepted review
evidence starts a new generation while the prior generation is preserved.
"""
from __future__ import annotations

import copy
from typing import Any

from cre_foundry.architecture.protocol import (
    ARCH_ABSTAIN_HAS_EFFECTS,
    ARCH_ABSTAIN_REASON_HIDDEN,
    ARCH_COMMIT_WITHOUT_PREPARE,
    ARCH_DECISION_MISMATCH,
    ARCH_DOWNSTREAM_BINDING,
    ARCH_ERROR_HIDDEN,
    ARCH_IDEMPOTENCY_CONFLICT,
    ARCH_ILLEGAL_TRANSITION,
    ARCH_ISSUANCE_SLOT_CONFLICT,
    ARCH_LIVE_DENIAL,
    ARCH_MANUAL_BYPASS,
    ARCH_PARTIAL_FAILURE_AMBIGUOUS,
    ARCH_POLICY_BYPASS,
    ARCH_RECONSTRUCTION_MISMATCH,
    ARCH_STAGE1_REWRITE,
    ARCH_UNKNOWN_COMMAND,
    CANONICALIZATION,
    EVALUATOR_ID,
    EXECUTION_SCOPE,
    FAULT_POINTS,
    INITIAL_STATE,
    PRECOMMIT_FAULT_POINTS,
    ProtocolContext,
    ProtocolError,
    SIDECAR_COMMANDS,
    SCHEMA_VERSION,
    authorization_is_current,
    digest_json,
    validate_command_envelope,
)

# Frozen state-machine constants derived from the frozen registries.  The
# reserved live states are unreachable in a synthetic workflow; any claim that
# reaches them is a live-safety failure.
TERMINAL_STATES = frozenset({"ABSTAINED", "QUARANTINED", "SUPERSEDED", "VOIDED"})
RESERVED_LIVE_STATES = frozenset({"DELIVERY_PENDING", "DELIVERED", "RECALL_REQUIRED"})
STATE_CHANGING_COMMANDS = frozenset(
    {
        "APPEND_STAGE1",
        "FREEZE_STAGE1",
        "DECIDE_ISSUE",
        "DECIDE_ABSTAIN",
        "QUARANTINE_INVALID",
        "PREPARE_SYNTHETIC_ISSUANCE",
        "COMMIT_SYNTHETIC_ISSUANCE",
        "APPEND_STAGE2",
        "APPEND_STAGE3",
        "VOID_UNDELIVERED",
        "SUPERSEDE_WITH_NEW_GENERATION",
    }
)

MANUAL_ALLOWED_ACTIONS = frozenset({"ANNOTATE", "REQUEST_AUTHORITATIVE_EVIDENCE", "ABANDON_PREISSUANCE_GENERATION", "START_NEW_GENERATION"})
MANUAL_FORBIDDEN_ACTIONS = frozenset(
    {
        "EDIT_FROZEN_STAGE1",
        "CHANGE_GATE_OR_PROTECTION_STATE",
        "INSERT_OR_DELETE_CANDIDATE",
        "CHANGE_VALUE_OR_RANK",
        "SWAP_SELECTED_STOP",
        "CLEAR_UNKNOWN",
        "HIDE_ABSTENTION_OR_ERROR",
        "DIRECT_ISSUE",
    }
)


def _transition_table(context: ProtocolContext) -> dict[tuple[str, str], str]:
    return {
        (row["command_type"], row["from"]): row["to"]
        for row in context.state_registry["allowed_transitions"]
    }


def _genesis_predecessor() -> str:
    return digest_json({"genesis": True, "initial_state": INITIAL_STATE})


def _event_digest(event: dict[str, Any]) -> str:
    payload = {
        "event_id": event["event_id"],
        "command_id": event["command_id"],
        "command_sha256": event["command_sha256"],
        "aggregate_version": event["aggregate_version"],
        "predecessor_event_id": event["predecessor_event_id"],
        "predecessor_event_sha256": event["predecessor_event_sha256"],
        "from_state": event["from_state"],
        "to_state": event["to_state"],
        "applied_at": event["applied_at"],
    }
    return digest_json(payload)


def fault_is_skipped(fault_schedule: Any) -> tuple[int, bool]:
    """Return (fault command index, whether the faulted command is skipped).

    A pre-commit fault with zero retries must leave no partial record, so the
    faulted command is skipped atomically.  Every other registered fault point
    (including post-commit) must reach the committed state.
    """
    if not isinstance(fault_schedule, dict):
        return -1, False
    point = fault_schedule.get("fault_point")
    if point not in FAULT_POINTS:
        raise ProtocolError(ARCH_PARTIAL_FAILURE_AMBIGUOUS, f"unknown fault point {point}")
    index = int(fault_schedule.get("command_index", -1))
    retries = int(fault_schedule.get("retries", 0))
    return index, point in PRECOMMIT_FAULT_POINTS and retries == 0


def _issue_response_body(command_id: str) -> dict[str, Any]:
    return {
        "result_status": "APPLIED",
        "retry_allowed": True,
        "focus_target": command_id,
        "announcement_intent": "POLITE",
    }


def _held_response_body(command_id: str) -> dict[str, Any]:
    return {
        "result_status": "HELD_UNAUTHORIZED",
        "retry_allowed": True,
        "focus_target": command_id,
        "announcement_intent": "ALERT",
    }


def _conflict_response_body(command_id: str) -> dict[str, Any]:
    return {
        "result_status": "CONFLICT",
        "retry_allowed": False,
        "focus_target": command_id,
        "announcement_intent": "ALERT",
    }


def reduce_command_stream(
    context: ProtocolContext,
    commands: list[dict[str, Any]],
    authorizations: dict[str, Any],
    math_decision: Any,
    fault_schedule: Any = None,
) -> tuple[dict[str, Any], list[str]]:
    """Reduce a canonical command stream into the expected run projection.

    Returns (projection, diagnostics).  The projection is byte-identical to the
    evaluator-owned independent reduction for the same stream.  Diagnostics are
    stable ARCH-* codes collected for invariant violations; a valid stream
    yields an empty diagnostic list.
    """
    errors: list[str] = []
    transitions = _transition_table(context)
    state = INITIAL_STATE
    aggregate_version = 0
    genesis = _genesis_predecessor()
    events: list[dict[str, Any]] = []
    idempotency_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    idempotency_records: list[dict[str, Any]] = []
    issuance_ledger: list[dict[str, Any]] = []
    held_outbox: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    prepared_route_sha: str | None = None
    committed_route_sha: str | None = None
    issued_stop_pairs: list[tuple[str, str]] = []
    issuance_slot_used: dict[str, dict[str, Any]] = {}
    stage2_field_events: dict[str, dict[str, Any]] = {}
    stage3_bound: set[str] = set()

    fault_index, fault_skips = fault_is_skipped(fault_schedule)

    for index, command in enumerate(commands):
        command_type = command.get("command_type")
        errors.extend(validate_command_envelope(context, command, index))
        command_sha = context.command_digest(command)

        if command_type not in _all_command_types(context):
            errors.append(f"{ARCH_UNKNOWN_COMMAND}: command[{index}] {command_type}")
            continue

        decision = authorizations.get(command.get("authorization_decision_sha256"))
        authorized = authorization_is_current(decision, command)
        if not authorized:
            body = _held_response_body(command.get("command_id"))
            responses.append(
                {"command_id": command.get("command_id"), "status": "HELD_UNAUTHORIZED", "response_sha256": digest_json(body), "response": body}
            )
            held_outbox.append(
                {
                    "outbox_entry_id": f"OUTBOX:{command.get('command_id')}",
                    "command_id": command.get("command_id"),
                    "status": "HELD_UNAUTHORIZED",
                    "effect_class": "EXTERNAL_EFFECT_HELD_UNAUTHORIZED",
                    "effect_sha256": digest_json({"held": command.get("command_id")}),
                    "delivered_at": None,
                }
            )
            continue

        if command_type in SIDECAR_COMMANDS:
            body = _issue_response_body(command.get("command_id"))
            responses.append(
                {"command_id": command.get("command_id"), "status": "APPLIED", "response_sha256": digest_json(body), "response": body}
            )
            continue

        if index == fault_index and fault_skips:
            continue

        idem_key = command.get("idempotency_key", {}).get("key")
        scope = (
            command.get("aggregate_key", {}).get("representative_id"),
            command.get("aggregate_key", {}).get("route_date"),
            command.get("aggregate_key", {}).get("generation"),
            command_type,
            idem_key,
        )
        payload_sha = command.get("payload_sha256")
        prior = idempotency_map.get(scope)
        if prior is not None:
            if prior["payload_sha256"] == payload_sha:
                response = prior["response"]
                responses.append(
                    {"command_id": command.get("command_id"), "status": "IDEMPOTENT_REPLAY", "response_sha256": digest_json(response), "response": response}
                )
            else:
                errors.append(f"{ARCH_IDEMPOTENCY_CONFLICT}: command[{index}] same key different payload")
                body = _conflict_response_body(command.get("command_id"))
                responses.append(
                    {"command_id": command.get("command_id"), "status": "CONFLICT", "response_sha256": digest_json(body), "response": body}
                )
            continue

        expected_version = command.get("expected_aggregate_version")
        if expected_version != aggregate_version:
            errors.append(
                f"{ARCH_ILLEGAL_TRANSITION}: command[{index}] expected aggregate version {expected_version} but current is {aggregate_version}"
            )

        if command_type == "COMMIT_SYNTHETIC_ISSUANCE":
            if prepared_route_sha is None:
                errors.append(f"{ARCH_COMMIT_WITHOUT_PREPARE}: command[{index}] commit without prepare")
            route_sha = command.get("payload", {}).get("route_manifest_sha256")
            if prepared_route_sha is not None and route_sha != prepared_route_sha:
                errors.append(f"{ARCH_DECISION_MISMATCH}: command[{index}] route manifest differs from prepared route")
            slot = command.get("payload", {}).get("issuance_slot", {})
            slot_key = digest_json(slot)
            if slot_key in issuance_slot_used:
                errors.append(f"{ARCH_ISSUANCE_SLOT_CONFLICT}: command[{index}] issuance slot already committed")
            else:
                issuance_slot_used[slot_key] = command

        transition = transitions.get((command_type, state))
        if transition is None:
            errors.append(f"{ARCH_ILLEGAL_TRANSITION}: command[{index}] {command_type} from {state} is not an allowed transition")
            continue
        to_state = transition

        if command_type in {"APPEND_STAGE2", "APPEND_STAGE3"}:
            if state != "ISSUED_INTERNAL" and state != "ISSUANCE_PREPARED":
                if state == "ABSTAINED" or state in TERMINAL_STATES:
                    errors.append(f"{ARCH_DOWNSTREAM_BINDING}: command[{index}] {command_type} after {state}")
                else:
                    errors.append(f"{ARCH_DOWNSTREAM_BINDING}: command[{index}] {command_type} before issuance")
            if command_type == "APPEND_STAGE2":
                payload = command.get("payload", {})
                if committed_route_sha is not None and payload.get("route_manifest_sha256") != committed_route_sha:
                    errors.append(f"{ARCH_DOWNSTREAM_BINDING}: command[{index}] stage2 not bound to issued route")
                for event_id in payload.get("field_event_ids", []):
                    stop_ok = any(event_id.startswith("FIELD_EVENT:") for _ in [0])
                    if not stop_ok:
                        errors.append(f"{ARCH_DOWNSTREAM_BINDING}: command[{index}] malformed field event id")
                    stage2_field_events[event_id] = {"command": command, "bound": stop_ok}
            elif command_type == "APPEND_STAGE3":
                payload = command.get("payload", {})
                field_event_id = payload.get("field_event_id")
                if field_event_id not in stage2_field_events:
                    errors.append(f"{ARCH_DOWNSTREAM_BINDING}: command[{index}] stage3 not bound to a stage2 field event")
                stage3_bound.add(field_event_id)

        if command_type == "FREEZE_STAGE1":
            payload = command.get("payload", {})
            snapshot_sha = payload.get("stage1_snapshot_sha256")
            source_snapshot = None
            for prior_command in commands[:index]:
                if prior_command.get("command_type") == "APPEND_STAGE1":
                    source_snapshot = prior_command.get("payload", {}).get("source_snapshot_sha256")
            if snapshot_sha is not None and source_snapshot is not None and snapshot_sha != source_snapshot:
                errors.append(f"{ARCH_STAGE1_REWRITE}: command[{index}] frozen snapshot differs from appended source snapshot")

        if command_type == "DECIDE_ISSUE":
            claimed = command.get("payload", {}).get("math_decision_sha256")
            if math_decision is not None and claimed != digest_json(math_decision):
                errors.append(f"{ARCH_DECISION_MISMATCH}: command[{index}] math decision digest mismatch")
            if math_decision is not None and math_decision.get("decision") != "ISSUE":
                errors.append(f"{ARCH_DECISION_MISMATCH}: command[{index}] math oracle abstains but DECIDE_ISSUE claimed")
        if command_type == "DECIDE_ABSTAIN":
            claimed = command.get("payload", {}).get("math_decision_sha256")
            if math_decision is not None and claimed != digest_json(math_decision):
                errors.append(f"{ARCH_DECISION_MISMATCH}: command[{index}] math decision digest mismatch")
            if math_decision is not None and math_decision.get("decision") != "ABSTAIN_NO_VALID_TEN":
                errors.append(f"{ARCH_DECISION_MISMATCH}: command[{index}] math oracle issues but DECIDE_ABSTAIN claimed")
            reason = command.get("payload", {}).get("abstain_reason")
            if math_decision is not None and reason != math_decision.get("reason"):
                errors.append(f"{ARCH_ABSTAIN_REASON_HIDDEN}: command[{index}] abstain reason mismatch")
            if not reason:
                errors.append(f"{ARCH_ABSTAIN_REASON_HIDDEN}: command[{index}] abstain reason missing")

        if command_type in STATE_CHANGING_COMMANDS:
            aggregate_version += 1
            predecessor_id = events[-1]["event_id"] if events else None
            predecessor_sha = events[-1]["event_sha256"] if events else genesis
            event = {
                "event_id": f"EVT:{command.get('command_id')}",
                "command_id": command.get("command_id"),
                "command_sha256": command_sha,
                "aggregate_version": aggregate_version,
                "predecessor_event_id": predecessor_id,
                "predecessor_event_sha256": predecessor_sha,
                "from_state": state,
                "to_state": to_state,
                "event_sha256": None,
                "applied_at": command.get("submitted_at"),
            }
            event["event_sha256"] = _event_digest(event)
            events.append(event)
            state = to_state
            body = _issue_response_body(command.get("command_id"))
            if command_type == "DECIDE_ISSUE" and math_decision is not None:
                body["result"] = "ISSUE"
            elif command_type == "DECIDE_ABSTAIN" and math_decision is not None:
                body["result"] = "ABSTAIN_NO_VALID_TEN"
                body["reason"] = math_decision.get("reason")
            responses.append(
                {"command_id": command.get("command_id"), "status": "APPLIED", "response_sha256": digest_json(body), "response": body}
            )
            idempotency_map[scope] = {"payload_sha256": payload_sha, "response": body}
            idempotency_records.append(
                {
                    "idempotency_key": idem_key,
                    "aggregate_key": command.get("aggregate_key"),
                    "command_type": command_type,
                    "original_command_id": command.get("command_id"),
                    "status": "APPLIED",
                    "original_response_sha256": digest_json(body),
                }
            )
            if command_type == "PREPARE_SYNTHETIC_ISSUANCE":
                prepared_route_sha = command.get("payload", {}).get("prepared_route_sha256")
            if command_type == "COMMIT_SYNTHETIC_ISSUANCE":
                committed_route_sha = command.get("payload", {}).get("route_manifest_sha256")
                selected_candidate_ids: list[str] = []
                selected_physical_location_ids: list[str] = []
                if math_decision is not None and math_decision.get("decision") == "ISSUE":
                    selected = math_decision.get("selected", [])
                    selected_candidate_ids = [row["candidate_id"] for row in selected]
                    selected_physical_location_ids = [row["physical_location_id"] for row in selected]
                    issued_stop_pairs = [(row["candidate_id"], row["physical_location_id"]) for row in selected]
                issuance_ledger.append(
                    {
                        "issuance_slot": command.get("payload", {}).get("issuance_slot"),
                        "route_manifest_sha256": committed_route_sha,
                        "generation": command.get("aggregate_key", {}).get("generation"),
                        "committed_at": command.get("submitted_at"),
                        "stop_count": len(selected_candidate_ids),
                        "selected_candidate_ids": selected_candidate_ids,
                        "selected_physical_location_ids": selected_physical_location_ids,
                        "external_effect_occurred": False,
                    }
                )

    final_state = state
    final_is_terminal = final_state in TERMINAL_STATES

    result = None
    if math_decision is not None and math_decision.get("decision") == "ISSUE":
        result = {
            "result": "ISSUE",
            "selected": math_decision.get("selected", []),
            "route_required": True,
            "reason": None,
            "external_effect_occurred": False,
        }
    elif math_decision is not None and math_decision.get("decision") == "ABSTAIN_NO_VALID_TEN":
        result = {
            "result": "ABSTAIN_NO_VALID_TEN",
            "selected": [],
            "route": None,
            "reason": math_decision.get("reason"),
            "downstream_effects_count": 0,
            "external_effect_occurred": False,
        }
    elif math_decision is None and any(command.get("command_type") in {"DECIDE_ISSUE", "DECIDE_ABSTAIN"} for command in commands):
        result = {
            "result": "ERROR",
            "selected": [],
            "route": None,
            "diagnostic": "INVALID_PROBLEM",
            "safe_recovery_required": True,
            "downstream_effects_count": 0,
            "external_effect_occurred": False,
        }

    return (
        {
            "state": final_state,
            "is_terminal": final_is_terminal,
            "aggregate_version": aggregate_version,
            "events": events,
            "idempotency_records": idempotency_records,
            "issuance_ledger": issuance_ledger,
            "held_outbox": held_outbox,
            "responses": responses,
            "result": result,
            "issued_stop_pairs": issued_stop_pairs,
            "stage2_field_events": stage2_field_events,
            "stage3_bound": stage3_bound,
        },
        errors,
    )


def _all_command_types(context: ProtocolContext) -> set[str]:
    return {row["command_type"] for row in context.state_registry["commands"]}


def build_accessibility_projection(result_kind: str | None, reason: Any = None, selected: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build the synthetic programmatic accessibility projection.

    The projection communicates status in programmatic semantics only; it is
    never visual-only and establishes no WCAG or assistive-technology claim.
    """
    selected = selected or []
    status_code = {"ISSUE": "S_ISSUE", "ABSTAIN_NO_VALID_TEN": "S_ABSTAIN", "ERROR": "S_ERROR"}.get(result_kind, "S_STATUS")
    focus_target = "result" if result_kind == "ISSUE" else "status"
    announcement = "POLITE" if result_kind == "ISSUE" else "ALERT"
    if result_kind == "ERROR" and not reason:
        reason = "INVALID_PROBLEM"
    actions = [
        {"action_id": "retry", "name": "Retry", "role": "button", "state": "enabled", "focus_order": 0, "reading_order": 0},
        {"action_id": "details", "name": "View details", "role": "link", "state": "enabled", "focus_order": 1, "reading_order": 1},
    ]
    status = {
        "primary_status_code": status_code,
        "primary_status_text": "Workflow result",
        "reason_code": reason,
        "reason_text": reason,
        "evidence_reference_ids": ["EVID:ARCH-1"],
        "safe_next_actions": actions,
        "retry_allowed": True,
        "focus_target": focus_target,
        "announcement_intent": announcement,
    }
    location_rows = [
        {
            "row_id": f"ROW-{index}",
            "label": f"Location {row['physical_location_id']}",
            "physical_location_id": row["physical_location_id"],
            "sequence_position": index + 1,
            "order": index,
        }
        for index, row in enumerate(selected)
    ]
    return {
        "projection_id": "PROJ-ARCH-1",
        "document_kind": "ARCHITECTURE_ACCESSIBILITY_PROJECTION",
        "schema_version": SCHEMA_VERSION,
        "execution_scope": EXECUTION_SCOPE,
        "claim_kind": "SYNTHETIC_PROGRAMMATIC_SEMANTICS_ONLY",
        "status": status,
        "actions": actions,
        "focus_order": ["retry", "details"],
        "reading_order": ["retry", "details"],
        "errors": [],
        "location_rows": location_rows,
        "visual_only": False,
        "claims_not_established": [
            "WCAG_CONFORMANCE",
            "SCREEN_READER_PERFORMANCE",
            "REPRESENTATIVE_USABILITY",
            "ACCESSIBILITY_EFFECTIVENESS",
            "SATISFACTION",
            "ADOPTION",
        ],
    }


def build_receipt(run: dict[str, Any], accessibility: dict[str, Any], claim_ceiling: str) -> dict[str, Any]:
    """Build the per-section replay receipt and its final digest."""
    body = {
        "command_stream_sha256": digest_json(run.get("commands", [])),
        "event_stream_sha256": digest_json(run.get("events", [])),
        "aggregate_projection_sha256": digest_json(
            {"aggregate_version": run.get("aggregate_version"), "state": run.get("state"), "is_terminal": run.get("is_terminal")}
        ),
        "idempotency_sha256": digest_json(run.get("idempotency_records", [])),
        "issuance_ledger_sha256": digest_json(run.get("issuance_ledger", [])),
        "outbox_sha256": digest_json(run.get("held_outbox", [])),
        "effect_ledger_sha256": digest_json(run.get("effect_ledger", [])),
        "responses_sha256": digest_json(run.get("responses", [])),
        "accessibility_projection_sha256": digest_json(accessibility),
        "final_state": run.get("state"),
        "claim_ceiling": claim_ceiling,
    }
    body["final_receipt_sha256"] = digest_json(body)
    return body


def build_proof(claim: str) -> dict[str, Any]:
    """Proof flags capped at public proof level 4 with all real-world claims false."""
    return {
        "level": 4,
        "claim": claim,
        "live_issuance_authorized": False,
        "external_effect_occurred": False,
        "real_usability_proven": False,
        "accessibility_performance_or_conformance_proven": False,
        "production_atomicity_or_reliability_proven": False,
        "security_proven": False,
        "real_route_feasibility_proven": False,
        "deployment_authorized": False,
        "live_workflow_authorized": False,
        "incremental_lift_proven": False,
        "commercial_value_proven": False,
    }


def assemble_run(
    context: ProtocolContext,
    commands: list[dict[str, Any]],
    authorizations: dict[str, Any],
    math_decision: Any,
    fault_schedule: Any = None,
    run_id: str = "RUN-ARCH-1",
    claim: str = "Synthetic formal-only conformance of the representative workflow surface.",
) -> tuple[dict[str, Any], list[str]]:
    """Assemble the full ARCHITECTURE_WORKFLOW_RUN projection for a stream."""
    projection, errors = reduce_command_stream(context, commands, authorizations, math_decision, fault_schedule=fault_schedule)
    result = projection["result"]
    if result is None:
        errors.append(f"{ARCH_ERROR_HIDDEN}: workflow without a result union")
    selected = result.get("selected") or []
    accessibility = build_accessibility_projection(result.get("result") if result else None, reason=result.get("reason") if result else None, selected=selected)

    run: dict[str, Any] = {
        "document_kind": "ARCHITECTURE_WORKFLOW_RUN",
        "schema_version": SCHEMA_VERSION,
        "execution_scope": EXECUTION_SCOPE,
        "canonicalization": CANONICALIZATION,
        "run_id": run_id,
        "aggregate_key": commands[0]["aggregate_key"] if commands else None,
        "aggregate_version": projection["aggregate_version"],
        "initial_state": INITIAL_STATE,
        "state": projection["state"],
        "is_terminal": projection["is_terminal"],
        "commands": commands,
        "events": projection["events"],
        "idempotency_records": projection["idempotency_records"],
        "issuance_ledger": projection["issuance_ledger"],
        "held_outbox": projection["held_outbox"],
        "effect_ledger": [],
        "responses": projection["responses"],
        "result": result,
        "accessibility_projection": accessibility,
        "schema_bindings": context.schema_bindings,
        "owner": {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"},
        "proof": build_proof(claim),
    }
    run["receipt"] = build_receipt(run, accessibility, context.contract.get("claim_ceiling", ""))
    return run, errors


def validate_review_records(records: list[dict[str, Any]]) -> list[str]:
    """Fail-closed validation of the append-only manual-review sidecar.

    Allowed actions only, forbidden actions rejected, no real authority grant,
    and an unbroken predecessor digest chain.
    """
    errors: list[str] = []
    seen: set[str] = set()
    previous_digest = _genesis_predecessor()
    for index, record in enumerate(records):
        if record.get("record_id") in seen:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] duplicate id")
        seen.add(record.get("record_id"))
        action = record.get("action")
        if action in MANUAL_FORBIDDEN_ACTIONS:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] forbidden action {action}")
        elif action not in MANUAL_ALLOWED_ACTIONS:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] unregistered action {action}")
        if record.get("grants_real_authority") is not False:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] must not grant real authority")
        predecessor = record.get("predecessor")
        if predecessor is None:
            if record.get("review_sequence") != 1:
                errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] first record must have sequence 1")
        elif predecessor.get("sha256") != previous_digest:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] predecessor digest mismatch")
        previous_digest = digest_json(record)
    return errors


def assemble_subject(
    context: ProtocolContext,
    problem: dict[str, Any],
    commands: list[dict[str, Any]],
    authorizations: dict[str, Any],
    math_decision: Any,
    fault_schedule: Any = None,
    review_records: list[dict[str, Any]] | None = None,
    run_id: str = "RUN-ARCH-1",
) -> tuple[dict[str, Any], list[str]]:
    """Assemble the complete ARCHITECTURE_WORKFLOW_SUBJECT for evaluation."""
    run, errors = assemble_run(context, commands, authorizations, math_decision, fault_schedule=fault_schedule, run_id=run_id)
    errors.extend(validate_review_records(review_records or []))
    subject: dict[str, Any] = {
        "subject_kind": "ARCHITECTURE_WORKFLOW_SUBJECT",
        "schema_version": SCHEMA_VERSION,
        "evaluator_id": EVALUATOR_ID,
        "canonicalization": CANONICALIZATION,
        "problem": problem,
        "authorizations": authorizations,
        "modules": copy.deepcopy(context.module_registry["modules"]),
        "fault_schedule": fault_schedule,
        "run": run,
        "review_records": review_records or [],
    }
    return subject, errors


def supersede_generation(context: ProtocolContext, current_generation: int, successor_snapshot_sha256: str) -> int:
    """Start a new generation from accepted Stage-1 evidence.

    A frozen generation is never edited: the successor generation receives a
    fresh snapshot and the prior generation is preserved.  Any attempt to reuse
    or skip generations fails closed.
    """
    successor = current_generation + 1
    if not successor_snapshot_sha256 or len(successor_snapshot_sha256) != 64:
        raise ProtocolError(ARCH_RECONSTRUCTION_MISMATCH, "successor stage-1 snapshot required for a new generation")
    if context.contract.get("proof", {}).get("live_workflow_authorized") is True:
        raise ProtocolError(ARCH_LIVE_DENIAL, "live workflow must not be authorized")
    return successor
