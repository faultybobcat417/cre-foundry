"""Bounded property-grid suite for the ARCHITECTURE-001 independent evaluator.

Every subject is built by an independent reference reducer reimplemented here
(never importing src/cre_foundry/architecture).  The suite then asserts the
evaluator either passes the canonical subject or emits the specific registered
ARCH-* diagnostics for each mutation.  It is deterministic and bounded by
construction; no live action, gate, or permission is ever touched.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:
    from evals.public.architecture_workflow_evaluator import CONTRACT_PATH, evaluate, evaluate_file, scan_source_independence
except ModuleNotFoundError:  # unittest discovery adds evals/public directly
    from architecture_workflow_evaluator import CONTRACT_PATH, evaluate, evaluate_file, scan_source_independence

try:
    from evals.public.math_oracle_evaluator import evaluate as oracle
except ModuleNotFoundError:
    from math_oracle_evaluator import evaluate as oracle

CONTRACT = json.loads((ROOT / "artifacts/architecture/public_evaluator_contract.json").read_text())
CONTRACT_SHA = hashlib.sha256((ROOT / "artifacts/architecture/public_evaluator_contract.json").read_bytes()).hexdigest()
STATE_REGISTRY = json.loads((ROOT / "artifacts/architecture/state_machine_registry.json").read_text())
MODULE_REGISTRY = json.loads((ROOT / "artifacts/architecture/module_registry.json").read_text())
SCENARIO_REGISTRY = json.loads((ROOT / "artifacts/architecture/scenario_registry.json").read_text())
TRANSITIONS = {(row["command_type"], row["from"]): row["to"] for row in STATE_REGISTRY["allowed_transitions"]}
MODULES = MODULE_REGISTRY["modules"]
SIDECAR_COMMANDS = {"RECORD_REVIEW_ANNOTATION", "REQUEST_AUTHORITATIVE_EVIDENCE"}
TERMINAL_STATES = {"ABSTAINED", "QUARANTINED", "SUPERSEDED", "VOIDED"}
PRECOMMIT_POINTS = {"BEFORE_EVENT_APPEND", "AFTER_EVENT_BEFORE_PROJECTION", "AFTER_PROJECTION_BEFORE_IDEMPOTENCY", "AFTER_IDEMPOTENCY_BEFORE_OUTBOX", "AFTER_OUTBOX_BEFORE_COMMIT"}
POSTCOMMIT_POINTS = {"AFTER_COMMIT_BEFORE_RESPONSE"}

CAPABILITY = {
    "APPEND_STAGE1": "stage1:append",
    "FREEZE_STAGE1": "stage1:freeze",
    "DECIDE_ISSUE": "decision:issue",
    "DECIDE_ABSTAIN": "decision:abstain",
    "QUARANTINE_INVALID": "decision:quarantine",
    "PREPARE_SYNTHETIC_ISSUANCE": "issuance:prepare",
    "COMMIT_SYNTHETIC_ISSUANCE": "issuance:commit",
    "APPEND_STAGE2": "stage2:append",
    "APPEND_STAGE3": "stage3:append",
    "VOID_UNDELIVERED": "issuance:void",
    "SUPERSEDE_WITH_NEW_GENERATION": "generation:supersede",
    "RECORD_REVIEW_ANNOTATION": "review:annotate",
    "REQUEST_AUTHORITATIVE_EVIDENCE": "review:request-evidence",
}

SCHEMA_BINDING_PATHS = [
    ("architecture_command", "contracts/architecture_command.schema.json"),
    ("architecture_workflow_run", "contracts/architecture_workflow_run.schema.json"),
    ("architecture_review_record", "contracts/architecture_review_record.schema.json"),
    ("architecture_accessibility_projection", "contracts/architecture_accessibility_projection.schema.json"),
]

# Stable diagnostic codes (must match the frozen scenario registry).
ARCH_SHAPE_INVALID = "ARCH-SHAPE-INVALID"
ARCH_SCHEMA_UNREGISTERED = "ARCH-SCHEMA-UNREGISTERED"
ARCH_EVALUATOR_COUPLING = "ARCH-EVALUATOR-COUPLING"
ARCH_MODULE_REGISTRY = "ARCH-MODULE-REGISTRY"
ARCH_MODULE_BINDING = "ARCH-MODULE-BINDING"
ARCH_POLICY_BYPASS = "ARCH-POLICY-BYPASS"
ARCH_AUTHORITY_ESCALATION = "ARCH-AUTHORITY-ESCALATION"
ARCH_LIVE_DENIAL = "ARCH-LIVE-DENIAL"
ARCH_EXTERNAL_EFFECT = "ARCH-EXTERNAL-EFFECT"
ARCH_EXACT_TEN = "ARCH-EXACT-TEN"
ARCH_DUPLICATE_LOCATION = "ARCH-DUPLICATE-LOCATION"
ARCH_DECISION_MISMATCH = "ARCH-DECISION-MISMATCH"
ARCH_PROTECTION_BYPASS = "ARCH-PROTECTION-BYPASS"
ARCH_ABSTAIN_HAS_EFFECTS = "ARCH-ABSTAIN-HAS-EFFECTS"
ARCH_ABSTAIN_REASON_HIDDEN = "ARCH-ABSTAIN-REASON-HIDDEN"
ARCH_ERROR_HIDDEN = "ARCH-ERROR-HIDDEN"
ARCH_MANUAL_BYPASS = "ARCH-MANUAL-BYPASS"
ARCH_STAGE1_REWRITE = "ARCH-STAGE1-REWRITE"
ARCH_ILLEGAL_TRANSITION = "ARCH-ILLEGAL-TRANSITION"
ARCH_COMMIT_WITHOUT_PREPARE = "ARCH-COMMIT-WITHOUT-PREPARE"
ARCH_DUPLICATE_ISSUANCE = "ARCH-DUPLICATE-ISSUANCE"
ARCH_IDEMPOTENCY_CONFLICT = "ARCH-IDEMPOTENCY-CONFLICT"
ARCH_ISSUANCE_SLOT_CONFLICT = "ARCH-ISSUANCE-SLOT-CONFLICT"
ARCH_PARTIAL_FAILURE_AMBIGUOUS = "ARCH-PARTIAL-FAILURE-AMBIGUOUS"
ARCH_JOURNAL_CHAIN = "ARCH-JOURNAL-CHAIN"
ARCH_LINEAGE_BINDING = "ARCH-LINEAGE-BINDING"
ARCH_DOWNSTREAM_BINDING = "ARCH-DOWNSTREAM-BINDING"
ARCH_ACCESSIBLE_ACTION = "ARCH-ACCESSIBLE-ACTION"
ARCH_ACCESSIBLE_STATUS = "ARCH-ACCESSIBLE-STATUS"
ARCH_ACCESSIBLE_NONVISUAL = "ARCH-ACCESSIBLE-NONVISUAL"
ARCH_STATUS_DISCLOSURE = "ARCH-STATUS-DISCLOSURE"
ARCH_UNKNOWN_COMMAND = "ARCH-UNKNOWN-COMMAND"
ARCH_RECONSTRUCTION_MISMATCH = "ARCH-RECONSTRUCTION-MISMATCH"
ARCH_CLAIM_CEILING = "ARCH-CLAIM-CEILING"

ALL_ARCH_CODES = {
    ARCH_SHAPE_INVALID, ARCH_SCHEMA_UNREGISTERED, ARCH_EVALUATOR_COUPLING, ARCH_MODULE_REGISTRY,
    ARCH_MODULE_BINDING, ARCH_POLICY_BYPASS, ARCH_AUTHORITY_ESCALATION, ARCH_LIVE_DENIAL,
    ARCH_EXTERNAL_EFFECT, ARCH_EXACT_TEN, ARCH_DUPLICATE_LOCATION, ARCH_DECISION_MISMATCH,
    ARCH_PROTECTION_BYPASS, ARCH_ABSTAIN_HAS_EFFECTS, ARCH_ABSTAIN_REASON_HIDDEN, ARCH_ERROR_HIDDEN,
    ARCH_MANUAL_BYPASS, ARCH_STAGE1_REWRITE, ARCH_ILLEGAL_TRANSITION, ARCH_COMMIT_WITHOUT_PREPARE,
    ARCH_DUPLICATE_ISSUANCE, ARCH_IDEMPOTENCY_CONFLICT, ARCH_ISSUANCE_SLOT_CONFLICT,
    ARCH_PARTIAL_FAILURE_AMBIGUOUS, ARCH_JOURNAL_CHAIN, ARCH_LINEAGE_BINDING, ARCH_DOWNSTREAM_BINDING,
    ARCH_ACCESSIBLE_ACTION, ARCH_ACCESSIBLE_STATUS, ARCH_ACCESSIBLE_NONVISUAL, ARCH_STATUS_DISCLOSURE,
    ARCH_UNKNOWN_COMMAND, ARCH_RECONSTRUCTION_MISMATCH, ARCH_CLAIM_CEILING,
}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def dg(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate(index, **overrides):
    row = {
        "candidate_id": f"C{index:02d}", "physical_location_id": f"L{index:02d}",
        "grain_ids": {name: None for name in ["legal_entity_id", "operating_business_id", "brand_id", "establishment_id", "unit_id", "property_id", "parcel_id", "owner_id", "occupier_id", "parent_group_id"]},
        "protection_tokens": [], "evidence_stage": 1, "observed_at": "2026-08-01T12:00:00Z",
        "gates": {name: "PASS" for name in ["evidence", "identity", "eligibility", "safety", "access", "operational"]},
        "protected_status": "CLEAR", "value_state": "REGISTERED_SYNTHETIC_PROXY", "business_value_units": 100 - index,
        "proximity_cost_units": index, "service_minutes": 10, "composition_group": None,
    }
    row.update(overrides)
    return row


def problem(rows, snapshot=None, policy=None):
    instance = {
        "schema_version": "1.0.0", "decision_scope": "SYNTHETIC_FORMAL_ONLY", "decision_id": "D-ARCH-TEST",
        "snapshot": {
            "snapshot_id": "S-ARCH-1", "snapshot_sha256": "0" * 64, "stage1_cutoff": "2026-08-01T23:59:59Z",
            "issued_at": "2026-08-01T23:59:59Z", "protected_bundle_complete": True, "protected_tokens": [],
        },
        "route_day": {"representative_id": "R-1", "route_date": "2026-08-02"},
        "policy": {
            "policy_version": "math-policy-v1", "policy_sha256": "1" * 64, "epsilon_business_value_units": 0,
            "maximum_candidates": 20, "max_total_service_minutes": 200, "composition_caps": {},
            "required_unique_grains": [], "incompatible_candidate_pairs": [], "redundancy_penalties": [],
            "interference_penalties": [],
        },
        "candidates": rows,
    }
    if snapshot is not None:
        instance["snapshot"].update(snapshot)
    if policy is not None:
        instance["policy"].update(policy)
    return instance


def aggregate_key(generation=1, representative_id="R-1"):
    return {
        "execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": representative_id,
        "route_date": "2026-08-02", "generation": generation,
    }


def command(command_id, command_type, expected_version, payload, idem_key=None, generation=1,
            principal="principal-1", submitted_at=None, actor_class="SYSTEM", capability=None,
            math_decision=None, stage1_sha=None, causation_id=None, authorization_key=None,
            representative_id="R-1"):
    if submitted_at is None:
        submitted_at = "2026-08-01T12:00:00Z"
    if idem_key is None:
        idem_key = f"IDEM:{command_type}:{command_id}"
    binding_math = dg(math_decision) if math_decision is not None else None
    envelope = {
        "command_id": command_id,
        "command_type": command_type,
        "aggregate_key": aggregate_key(generation=generation, representative_id=representative_id),
        "expected_aggregate_version": expected_version,
        "idempotency_key": {
            "key": idem_key,
            "binding": {
                "contract_version": "1.0.0", "representative_id": representative_id, "route_date": "2026-08-02",
                "generation": generation, "operation": command_type, "stage1_snapshot_sha256": stage1_sha,
                "math_decision_sha256": binding_math,
            },
        },
        "payload": payload,
        "payload_sha256": dg(payload),
        "schema_version": "1.0.0",
        "contract_sha256": CONTRACT_SHA,
        "actor_class": actor_class,
        "principal_reference": principal,
        "requested_capability": capability if capability is not None else CAPABILITY[command_type],
        "authorization_decision_sha256": authorization_key if authorization_key is not None else dg({"auth": command_id}),
        "correlation_id": f"CORR:{command_id}",
        "causation_id": causation_id,
        "submitted_at": submitted_at,
    }
    return envelope


def authorization(capability, principal="principal-1", granted_by="external-authority",
                  issued_at="2026-08-01T00:00:00Z", expires_at="2026-08-03T00:00:00Z",
                  revoked_at=None, decision="GRANTED", scope="SYNTHETIC_NON_INFLUENCING"):
    return {
        "decision": decision, "scope": scope, "capability": capability, "principal_reference": principal,
        "granted_by": granted_by, "issued_at": issued_at, "expires_at": expires_at, "revoked_at": revoked_at,
    }


def authorize_all(commands, overrides=None):
    overrides = overrides or {}
    result = {}
    for cmd in commands:
        result[cmd["authorization_decision_sha256"]] = authorization(
            cmd["requested_capability"], principal=cmd["principal_reference"], **overrides.get(cmd["command_type"], {})
        )
    return result


def reference_reduce(commands, authorizations, math_decision, fault_schedule=None):
    """Independent reduction of a canonical command stream into the expected run projection."""
    state = "COLLECTING_STAGE1"
    version = 0
    events = []
    idem_records = []
    ledger = []
    outbox = []
    responses = []
    idem_map = {}
    prepared = None
    committed = None
    genesis = dg({"genesis": True, "initial_state": "COLLECTING_STAGE1"})
    fault_index = -1
    fault_skips = False
    if isinstance(fault_schedule, dict) and fault_schedule.get("fault_point") in PRECOMMIT_POINTS and int(fault_schedule.get("retries", 0)) == 0:
        fault_index = int(fault_schedule.get("command_index", -1))
        fault_skips = True

    for index, cmd in enumerate(commands):
        ctype = cmd["command_type"]
        if ctype not in CAPABILITY:
            continue
        decision = authorizations.get(cmd["authorization_decision_sha256"])
        authorized = bool(
            decision
            and decision.get("decision") == "GRANTED"
            and decision.get("scope") == "SYNTHETIC_NON_INFLUENCING"
            and decision.get("capability") == cmd.get("requested_capability")
            and decision.get("principal_reference") == cmd.get("principal_reference")
            and decision.get("revoked_at") is None
            and cmd.get("submitted_at", "") >= (decision.get("issued_at") or "")
            and (not decision.get("expires_at") or cmd.get("submitted_at", "") <= decision.get("expires_at"))
        )
        if not authorized:
            body = {"result_status": "HELD_UNAUTHORIZED", "retry_allowed": True, "focus_target": cmd["command_id"], "announcement_intent": "ALERT"}
            responses.append({"command_id": cmd["command_id"], "status": "HELD_UNAUTHORIZED", "response_sha256": dg(body), "response": body})
            outbox.append({"outbox_entry_id": f"OUTBOX:{cmd['command_id']}", "command_id": cmd["command_id"], "status": "HELD_UNAUTHORIZED", "effect_class": "EXTERNAL_EFFECT_HELD_UNAUTHORIZED", "effect_sha256": dg({"held": cmd["command_id"]}), "delivered_at": None})
            continue
        if ctype in SIDECAR_COMMANDS:
            body = {"result_status": "APPLIED", "retry_allowed": True, "focus_target": cmd["command_id"], "announcement_intent": "POLITE"}
            responses.append({"command_id": cmd["command_id"], "status": "APPLIED", "response_sha256": dg(body), "response": body})
            continue
        if index == fault_index and fault_skips:
            continue
        scope = (cmd["aggregate_key"]["representative_id"], cmd["aggregate_key"]["route_date"], cmd["aggregate_key"]["generation"], ctype, cmd["idempotency_key"]["key"])
        prior = idem_map.get(scope)
        if prior is not None:
            if prior["payload_sha256"] == cmd["payload_sha256"]:
                responses.append({"command_id": cmd["command_id"], "status": "IDEMPOTENT_REPLAY", "response_sha256": dg(prior["response"]), "response": prior["response"]})
            else:
                body = {"result_status": "CONFLICT", "retry_allowed": False, "focus_target": cmd["command_id"], "announcement_intent": "ALERT"}
                responses.append({"command_id": cmd["command_id"], "status": "CONFLICT", "response_sha256": dg(body), "response": body})
            continue
        to_state = TRANSITIONS.get((ctype, state))
        if to_state is None:
            continue
        version += 1
        predecessor_id = events[-1]["event_id"] if events else None
        predecessor_sha = events[-1]["event_sha256"] if events else genesis
        event = {
            "event_id": f"EVT:{cmd['command_id']}", "command_id": cmd["command_id"], "command_sha256": dg(cmd),
            "aggregate_version": version, "predecessor_event_id": predecessor_id, "predecessor_event_sha256": predecessor_sha,
            "from_state": state, "to_state": to_state, "event_sha256": None, "applied_at": cmd["submitted_at"],
        }
        event["event_sha256"] = dg({
            "event_id": event["event_id"], "command_id": event["command_id"], "command_sha256": event["command_sha256"],
            "aggregate_version": event["aggregate_version"], "predecessor_event_id": event["predecessor_event_id"],
            "predecessor_event_sha256": event["predecessor_event_sha256"], "from_state": event["from_state"],
            "to_state": event["to_state"], "applied_at": event["applied_at"],
        })
        events.append(event)
        state = to_state
        body = {"result_status": "APPLIED", "retry_allowed": True, "focus_target": cmd["command_id"], "announcement_intent": "POLITE"}
        if ctype == "DECIDE_ISSUE" and math_decision is not None:
            body["result"] = "ISSUE"
        elif ctype == "DECIDE_ABSTAIN" and math_decision is not None:
            body["result"] = "ABSTAIN_NO_VALID_TEN"
            body["reason"] = math_decision.get("reason")
        responses.append({"command_id": cmd["command_id"], "status": "APPLIED", "response_sha256": dg(body), "response": body})
        idem_map[scope] = {"payload_sha256": cmd["payload_sha256"], "response": body}
        idem_records.append({
            "idempotency_key": cmd["idempotency_key"]["key"], "aggregate_key": cmd["aggregate_key"],
            "command_type": ctype, "original_command_id": cmd["command_id"], "status": "APPLIED",
            "original_response_sha256": dg(body),
        })
        if ctype == "PREPARE_SYNTHETIC_ISSUANCE":
            prepared = cmd["payload"]["prepared_route_sha256"]
        if ctype == "COMMIT_SYNTHETIC_ISSUANCE":
            committed = cmd["payload"]["route_manifest_sha256"]
            selected = math_decision.get("selected", []) if math_decision is not None and math_decision.get("decision") == "ISSUE" else []
            ledger.append({
                "issuance_slot": cmd["payload"]["issuance_slot"], "route_manifest_sha256": committed,
                "generation": cmd["aggregate_key"]["generation"], "committed_at": cmd["submitted_at"],
                "stop_count": len(selected), "selected_candidate_ids": [row["candidate_id"] for row in selected],
                "selected_physical_location_ids": [row["physical_location_id"] for row in selected],
                "external_effect_occurred": False,
            })

    result = None
    if math_decision is not None and math_decision.get("decision") == "ISSUE":
        result = {"result": "ISSUE", "selected": math_decision.get("selected", []), "route_required": True, "reason": None, "external_effect_occurred": False}
    elif math_decision is not None and math_decision.get("decision") == "ABSTAIN_NO_VALID_TEN":
        result = {"result": "ABSTAIN_NO_VALID_TEN", "selected": [], "route": None, "reason": math_decision.get("reason"), "downstream_effects_count": 0, "external_effect_occurred": False}
    elif math_decision is None and any(cmd.get("command_type") in {"DECIDE_ISSUE", "DECIDE_ABSTAIN"} for cmd in commands):
        result = {"result": "ERROR", "selected": [], "route": None, "diagnostic": "INVALID_PROBLEM", "safe_recovery_required": True, "downstream_effects_count": 0, "external_effect_occurred": False}

    return {
        "state": state,
        "is_terminal": state in TERMINAL_STATES,
        "aggregate_version": version,
        "events": events,
        "idempotency_records": idem_records,
        "issuance_ledger": ledger,
        "held_outbox": outbox,
        "responses": responses,
        "result": result,
    }


def accessibility_projection(result_kind, reason=None, selected=None):
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
        "primary_status_code": status_code, "primary_status_text": "Workflow result", "reason_code": reason,
        "reason_text": reason, "evidence_reference_ids": ["EVID:ARCH-1"], "safe_next_actions": actions,
        "retry_allowed": True, "focus_target": focus_target, "announcement_intent": announcement,
    }
    location_rows = [
        {"row_id": f"ROW-{i}", "label": f"Location {row['physical_location_id']}", "physical_location_id": row["physical_location_id"], "sequence_position": i + 1, "order": i}
        for i, row in enumerate(selected)
    ]
    return {
        "projection_id": "PROJ-ARCH-1", "document_kind": "ARCHITECTURE_ACCESSIBILITY_PROJECTION",
        "schema_version": "1.0.0", "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "claim_kind": "SYNTHETIC_PROGRAMMATIC_SEMANTICS_ONLY", "status": status, "actions": actions,
        "focus_order": ["retry", "details"], "reading_order": ["retry", "details"], "errors": [],
        "location_rows": location_rows, "visual_only": False,
        "claims_not_established": ["WCAG_CONFORMANCE", "SCREEN_READER_PERFORMANCE", "REPRESENTATIVE_USABILITY", "ACCESSIBILITY_EFFECTIVENESS", "SATISFACTION", "ADOPTION"],
    }


def make_receipt(run, accessibility):
    body = {
        "command_stream_sha256": dg(run["commands"]),
        "event_stream_sha256": dg(run["events"]),
        "aggregate_projection_sha256": dg({"aggregate_version": run["aggregate_version"], "state": run["state"], "is_terminal": run["is_terminal"]}),
        "idempotency_sha256": dg(run["idempotency_records"]),
        "issuance_ledger_sha256": dg(run["issuance_ledger"]),
        "outbox_sha256": dg(run["held_outbox"]),
        "effect_ledger_sha256": dg(run["effect_ledger"]),
        "responses_sha256": dg(run["responses"]),
        "accessibility_projection_sha256": dg(accessibility),
        "final_state": run["state"],
        "claim_ceiling": CONTRACT["claim_ceiling"],
    }
    body["final_receipt_sha256"] = dg(body)
    return body


def make_subject(problem_doc, commands, authorizations=None, modules=None, fault_schedule=None,
                 review_records=None, source_references=None, subject_overrides=None, run_overrides=None):
    math_decision = None
    try:
        math_decision = oracle(problem_doc)
    except ValueError:
        math_decision = None
    if authorizations is None:
        authorizations = authorize_all(commands)
    run = reference_reduce(commands, authorizations or {}, math_decision, fault_schedule=fault_schedule)
    assert run["result"] is not None, "a canonical subject always has a result union"
    run["document_kind"] = "ARCHITECTURE_WORKFLOW_RUN"
    run["schema_version"] = "1.0.0"
    run["execution_scope"] = "SYNTHETIC_NON_INFLUENCING"
    run["canonicalization"] = "SORTED_KEYS_INTEGER_JSON_V1"
    run["run_id"] = "RUN-ARCH-1"
    run["aggregate_key"] = commands[0]["aggregate_key"] if commands else aggregate_key()
    run["initial_state"] = "COLLECTING_STAGE1"
    run["effect_ledger"] = []
    run["commands"] = commands
    reason = run["result"].get("reason")
    selected = run["result"].get("selected") or []
    run["accessibility_projection"] = accessibility_projection(run["result"]["result"], reason=reason, selected=selected)
    run["schema_bindings"] = [
        {"name": name, "path": path, "schema_version": "1.0.0", "sha256": sha256_bytes(ROOT / path)}
        for name, path in SCHEMA_BINDING_PATHS
    ]
    run["proof"] = {
        "level": 4, "claim": "Synthetic formal-only conformance of the representative workflow surface.",
        "live_issuance_authorized": False, "external_effect_occurred": False,
        "real_usability_proven": False, "accessibility_performance_or_conformance_proven": False,
        "production_atomicity_or_reliability_proven": False, "security_proven": False,
        "real_route_feasibility_proven": False, "deployment_authorized": False, "live_workflow_authorized": False,
        "incremental_lift_proven": False, "commercial_value_proven": False,
    }
    run["owner"] = {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"}
    run["receipt"] = make_receipt(run, run["accessibility_projection"])
    if run_overrides:
        run.update(run_overrides)
        if "receipt" not in run_overrides:
            run["receipt"] = make_receipt(run, run["accessibility_projection"])

    subject = {
        "subject_kind": "ARCHITECTURE_WORKFLOW_SUBJECT",
        "schema_version": "1.0.0",
        "evaluator_id": "architecture-workflow-public-v1",
        "canonicalization": "SORTED_KEYS_INTEGER_JSON_V1",
        "problem": problem_doc,
        "authorizations": authorizations or {},
        "modules": modules if modules is not None else copy.deepcopy(MODULES),
        "fault_schedule": fault_schedule,
        "run": run,
        "review_records": review_records or [],
    }
    if source_references is not None:
        subject["source_references"] = source_references
    if subject_overrides:
        subject.update(subject_overrides)
    return subject


def issue_commands(math_decision, include_stage2=True, include_stage3=True, submitted_at="2026-08-01T12:00:00Z"):
    source_sha = "0" * 64
    route_sha = "1" * 64
    commands = [
        command("CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": source_sha, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, submitted_at=submitted_at, stage1_sha=source_sha),
        command("CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": source_sha}, submitted_at=submitted_at, stage1_sha=source_sha),
        command("CMD-DECIDE-1", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": dg(math_decision)}, submitted_at=submitted_at, math_decision=math_decision, stage1_sha=source_sha),
        command("CMD-PREPARE-1", "PREPARE_SYNTHETIC_ISSUANCE", 3, {"route_date": "2026-08-02", "prepared_route_sha256": route_sha}, submitted_at=submitted_at, math_decision=math_decision, stage1_sha=source_sha),
        command("CMD-COMMIT-1", "COMMIT_SYNTHETIC_ISSUANCE", 4, {"route_manifest_sha256": route_sha, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"}}, submitted_at=submitted_at, math_decision=math_decision, stage1_sha=source_sha),
    ]
    if include_stage2:
        commands.append(command("CMD-STAGE2-1", "APPEND_STAGE2", 5, {"route_manifest_sha256": route_sha, "field_event_ids": ["FIELD_EVENT:F1"]}, submitted_at=submitted_at, math_decision=math_decision, stage1_sha=source_sha))
    if include_stage3:
        expected_version = len(commands)
        commands.append(command("CMD-STAGE3-1", "APPEND_STAGE3", expected_version, {"field_event_id": "FIELD_EVENT:F1", "field_event_sha256": "2" * 64, "outcome_ids": ["OUT-1"]}, submitted_at=submitted_at, math_decision=math_decision, stage1_sha=source_sha))
    return commands


def abstain_commands(math_decision):
    source_sha = "0" * 64
    return [
        command("CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": source_sha, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, stage1_sha=source_sha),
        command("CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": source_sha}, stage1_sha=source_sha),
        command("CMD-DECIDE-1", "DECIDE_ABSTAIN", 2, {"math_decision_sha256": dg(math_decision), "abstain_reason": math_decision["reason"]}, math_decision=math_decision, stage1_sha=source_sha),
    ]


def issue_problem():
    return problem([candidate(i) for i in range(10)])


def no_feasible_problem():
    return problem([candidate(i) for i in range(9)])


def protected_bundle_problem():
    return problem([candidate(i) for i in range(10)], snapshot={"protected_bundle_complete": False})


def unresolved_value_problem():
    rows = [candidate(i) for i in range(10)]
    rows[-1]["value_state"] = "UNKNOWN"
    rows[-1]["business_value_units"] = None
    return problem(rows)


def invalid_problem():
    rows = [candidate(i) for i in range(10)]
    rows[1]["candidate_id"] = "C00"
    return problem(rows)


def review_record(record_id, sequence, action, annotations=None, evidence_request=None,
                  predecessor=None, grants_real_authority=False, status="ACCEPTED", forbidden_action=None,
                  successor_generation=None, accepted_evidence_rule=None):
    return {
        "record_id": record_id, "document_kind": "ARCHITECTURE_REVIEW_RECORD", "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING", "canonicalization": "SORTED_KEYS_INTEGER_JSON_V1",
        "aggregate_key": aggregate_key(), "review_sequence": sequence, "predecessor": predecessor,
        "actor_class": "MANUAL_REVIEWER", "principal_reference": "reviewer-1", "action": action,
        "annotations": annotations or [], "evidence_request": evidence_request,
        "recorded_at": "2026-08-01T13:00:00Z", "grants_real_authority": grants_real_authority,
        "status": status, "forbidden_action": forbidden_action,
    }


def chained_review_records():
    record_one = review_record("REV-1", 1, "ANNOTATE", annotations=["accepted evidence looks consistent"])
    record_two = review_record("REV-2", 2, "REQUEST_AUTHORITATIVE_EVIDENCE",
                               evidence_request={"requested_evidence_kind": "STAGE1_OBSERVATION", "reason": "confirm cutoff"},
                               predecessor={"review_id": "REV-1", "sha256": dg(record_one)})
    record_three = review_record("REV-3", 3, "ABANDON_PREISSUANCE_GENERATION",
                                 predecessor={"review_id": "REV-2", "sha256": dg(record_two)})
    return [record_one, record_two, record_three]


class ArchitectureWorkflowTestBase(unittest.TestCase):
    maxDiff = None

    def codes(self, subject):
        return set(diagnostic.split(":")[0] for diagnostic in evaluate(subject))


class TestCanonicalHappyPaths(ArchitectureWorkflowTestBase):
    def test_issue_full_run_passes(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        self.assertEqual([], evaluate(subject))

    def test_abstain_no_feasible_passes(self):
        decision = oracle(no_feasible_problem())
        subject = make_subject(no_feasible_problem(), abstain_commands(decision))
        self.assertEqual([], evaluate(subject))
        self.assertEqual("NO_FEASIBLE_TEN", subject["run"]["result"]["reason"])

    def test_abstain_protected_bundle_incomplete_passes(self):
        decision = oracle(protected_bundle_problem())
        subject = make_subject(protected_bundle_problem(), abstain_commands(decision))
        self.assertEqual([], evaluate(subject))
        self.assertEqual("PROTECTED_BUNDLE_INCOMPLETE", subject["run"]["result"]["reason"])

    def test_abstain_unresolved_value_passes(self):
        decision = oracle(unresolved_value_problem())
        subject = make_subject(unresolved_value_problem(), abstain_commands(decision))
        self.assertEqual([], evaluate(subject))
        self.assertEqual("UNRESOLVED_VALUE_COULD_DOMINATE", subject["run"]["result"]["reason"])

    def test_error_invalid_problem_passes(self):
        with self.assertRaises(ValueError):
            oracle(invalid_problem())
        subject = make_subject(invalid_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["commands"] = [
            command("CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": "0" * 64}),
            command("CMD-DECIDE-1", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": "0" * 64}),
        ]
        subject = make_subject(invalid_problem(), subject["run"]["commands"])
        self.assertEqual("ERROR", subject["run"]["result"]["result"])
        self.assertEqual("INVALID_PROBLEM", subject["run"]["result"]["diagnostic"])
        self.assertEqual([], evaluate(subject))

    def test_sidecars_do_not_change_state(self):
        decision = oracle(issue_problem())
        commands = [
            command("CMD-NOTE-1", "RECORD_REVIEW_ANNOTATION", 0, {"action": "ANNOTATE", "annotation": "note"}),
            command("CMD-REQ-1", "REQUEST_AUTHORITATIVE_EVIDENCE", 0, {"action": "REQUEST_AUTHORITATIVE_EVIDENCE", "request_reason": "verify"}),
        ]
        subject = make_subject(issue_problem(), commands)
        self.assertEqual([], evaluate(subject))
        self.assertEqual("COLLECTING_STAGE1", subject["run"]["state"])
        self.assertEqual(0, subject["run"]["aggregate_version"])

    def test_zero_commands_passes_with_issue_result(self):
        subject = make_subject(issue_problem(), [])
        self.assertEqual([], evaluate(subject))


class TestStrictParsingAndVersions(ArchitectureWorkflowTestBase):
    def test_duplicate_json_key_is_shape_invalid(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "subject.json"
            raw = json.dumps(subject, indent=2)
            raw = raw.replace('"subject_kind"', '"subject_kind", "subject_kind"', 1)
            path.write_text(raw)
            diagnostics, _ = evaluate_file(path)
            self.assertIn(ARCH_SHAPE_INVALID, set(diag.split(":")[0] for diag in diagnostics))

    def test_malformed_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "subject.json"
            path.write_text('{"subject_kind": ')
            diagnostics, _ = evaluate_file(path)
            self.assertIn(ARCH_SHAPE_INVALID, set(diag.split(":")[0] for diag in diagnostics))

    def test_unregistered_subject_version(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["schema_version"] = "9.9.9"
        self.assertIn(ARCH_SCHEMA_UNREGISTERED, self.codes(subject))

    def test_unregistered_evaluator_id(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["evaluator_id"] = "architecture-workflow-v999"
        self.assertIn(ARCH_SCHEMA_UNREGISTERED, self.codes(subject))

    def test_unregistered_run_version(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["schema_version"] = "2.0.0"
        self.assertIn(ARCH_SCHEMA_UNREGISTERED, self.codes(subject))

    def test_unregistered_command_version(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["commands"][0]["schema_version"] = "2.0.0"
        self.assertIn(ARCH_SCHEMA_UNREGISTERED, self.codes(subject))

    def test_wrong_contract_sha(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["commands"][0]["contract_sha256"] = "f" * 64
        self.assertIn(ARCH_SCHEMA_UNREGISTERED, self.codes(subject))

    def test_bad_subject_kind(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["subject_kind"] = "WRONG"
        self.assertIn(ARCH_SHAPE_INVALID, self.codes(subject))


class TestEvaluatorIndependence(ArchitectureWorkflowTestBase):
    def test_source_reference_to_builder_is_coupling(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["source_references"] = [{"import": "from cre_foundry.architecture.workflow import run_protocol"}]
        self.assertIn(ARCH_EVALUATOR_COUPLING, self.codes(subject))

    def test_evaluator_has_no_forbidden_imports(self):
        self.assertEqual([], scan_source_independence([Path(__file__).parent / "architecture_workflow_evaluator.py"]))

    def test_scanner_detects_forbidden_import(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.py"
            path.write_text("import cre_foundry.architecture.protocol\n")
            self.assertEqual([ARCH_EVALUATOR_COUPLING], [diag.split(":")[0] for diag in scan_source_independence([path])])

    def test_evaluator_does_not_import_src(self):
        source = (Path(__file__).parent / "architecture_workflow_evaluator.py").read_text()
        self.assertNotIn("cre_foundry.architecture", source)
        self.assertNotIn("import src", source)


class TestModuleRegistry(ArchitectureWorkflowTestBase):
    def test_missing_module_role(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["modules"] = [m for m in copy.deepcopy(MODULES) if m["role"] != "candidate_port"]
        self.assertIn(ARCH_MODULE_REGISTRY, self.codes(subject))

    def test_duplicate_module_role(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        modules = copy.deepcopy(MODULES)
        modules.append(copy.deepcopy(next(m for m in MODULES if m["role"] == "candidate_port")))
        subject["modules"] = modules
        self.assertIn(ARCH_MODULE_REGISTRY, self.codes(subject))

    def test_unregistered_interface_version(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["modules"] = copy.deepcopy(MODULES)
        subject["modules"][0]["interface_version"] = "0.0.0"
        self.assertIn(ARCH_MODULE_BINDING, self.codes(subject))

    def test_unregistered_effect_class(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["modules"] = copy.deepcopy(MODULES)
        subject["modules"][0]["effect_class"] = "EXTERNAL_EFFECT_FIRED"
        self.assertIn(ARCH_MODULE_BINDING, self.codes(subject))

    def test_wrong_schema_binding_digest(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["schema_bindings"][0]["sha256"] = "0" * 64
        self.assertIn(ARCH_MODULE_BINDING, self.codes(subject))

    def test_missing_schema_binding(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["schema_bindings"] = subject["run"]["schema_bindings"][1:]
        self.assertIn(ARCH_SCHEMA_UNREGISTERED, self.codes(subject))

    def test_live_enabled_module_is_live_denial(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["modules"] = copy.deepcopy(MODULES)
        subject["modules"][3]["live_enabled"] = True
        self.assertIn(ARCH_LIVE_DENIAL, self.codes(subject))


class TestStateMachineAndVersions(ArchitectureWorkflowTestBase):
    def test_legal_transitions(self):
        decision = oracle(issue_problem())
        abstain = oracle(no_feasible_problem())
        abstain_commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("C2", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": "0" * 64}),
            command("C3", "DECIDE_ABSTAIN", 2, {"math_decision_sha256": dg(abstain), "abstain_reason": abstain["reason"]}, math_decision=abstain),
        ]
        for problem_doc, commands in (
            (issue_problem(), [command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"})]),
            (issue_problem(), [command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
                               command("C2", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": "0" * 64})]),
            (no_feasible_problem(), abstain_commands),
        ):
            subject = make_subject(problem_doc, commands)
            self.assertEqual([], evaluate(subject))

    def test_illegal_skip_transition(self):
        commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("C2", "COMMIT_SYNTHETIC_ISSUANCE", 1, {"route_manifest_sha256": "1" * 64, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"}}),
        ]
        subject = make_subject(issue_problem(), commands)
        codes = self.codes(subject)
        self.assertIn(ARCH_ILLEGAL_TRANSITION, codes)
        self.assertIn(ARCH_COMMIT_WITHOUT_PREPARE, codes)

    def test_stale_aggregate_version(self):
        commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("C2", "FREEZE_STAGE1", 0, {"stage1_snapshot_sha256": "0" * 64}),
        ]
        subject = make_subject(issue_problem(), commands)
        self.assertIn(ARCH_ILLEGAL_TRANSITION, self.codes(subject))

    def test_future_aggregate_version(self):
        commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("C2", "FREEZE_STAGE1", 5, {"stage1_snapshot_sha256": "0" * 64}),
        ]
        subject = make_subject(issue_problem(), commands)
        self.assertIn(ARCH_ILLEGAL_TRANSITION, self.codes(subject))

    def test_terminal_reopen_is_illegal(self):
        decision = oracle(no_feasible_problem())
        commands = abstain_commands(decision) + [
            command("C4", "FREEZE_STAGE1", 3, {"stage1_snapshot_sha256": "0" * 64}),
        ]
        subject = make_subject(no_feasible_problem(), commands)
        self.assertIn(ARCH_ILLEGAL_TRANSITION, self.codes(subject))

    def test_unknown_command_fails_closed(self):
        unknown = dict(command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}))
        unknown["command_type"] = "DO_SOMETHING_LIVE"
        commands = [unknown]
        subject = make_subject(issue_problem(), commands)
        codes = self.codes(subject)
        self.assertIn(ARCH_UNKNOWN_COMMAND, codes)
        self.assertIn(ARCH_SHAPE_INVALID, codes)

    def test_commit_without_prepare(self):
        decision = oracle(issue_problem())
        commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("C2", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": "0" * 64}),
            command("C3", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": dg(decision)}, math_decision=decision),
            command("C4", "COMMIT_SYNTHETIC_ISSUANCE", 3, {"route_manifest_sha256": "1" * 64, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"}}, math_decision=decision),
        ]
        subject = make_subject(issue_problem(), commands)
        self.assertIn(ARCH_COMMIT_WITHOUT_PREPARE, self.codes(subject))

    def test_stage1_rewrite(self):
        decision = oracle(issue_problem())
        commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "0" * 64, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}),
            command("C2", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": "a" * 64}),
            command("C3", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": dg(decision)}, math_decision=decision),
        ]
        subject = make_subject(issue_problem(), commands)
        self.assertIn(ARCH_STAGE1_REWRITE, self.codes(subject))


class TestIdempotencyAndIssuance(ArchitectureWorkflowTestBase):
    def test_idempotent_replay_passes(self):
        decision = oracle(issue_problem())
        base = issue_commands(decision)
        replay = dict(base[0])
        replay["command_id"] = "CMD-APPEND-1-RETRY"
        replay["authorization_decision_sha256"] = dg({"auth": "CMD-APPEND-1-RETRY"})
        subject = make_subject(issue_problem(), [base[0], replay])
        self.assertEqual([], evaluate(subject))
        statuses = [response["status"] for response in subject["run"]["responses"]]
        self.assertEqual(["APPLIED", "IDEMPOTENT_REPLAY"], statuses)

    def test_idempotency_conflict(self):
        decision = oracle(issue_problem())
        base = issue_commands(decision)
        conflicting = dict(base[0])
        conflicting["command_id"] = "CMD-APPEND-1-CONFLICT"
        conflicting["authorization_decision_sha256"] = dg({"auth": "CMD-APPEND-1-CONFLICT"})
        conflicting["payload"] = {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": "b" * 64, "observation_ids": ["OBS-9"], "stage1_cutoff": "2026-08-01T23:59:59Z"}
        conflicting["payload_sha256"] = dg(conflicting["payload"])
        subject = make_subject(issue_problem(), [base[0], conflicting])
        self.assertIn(ARCH_IDEMPOTENCY_CONFLICT, self.codes(subject))

    def test_issuance_slot_conflict(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        second_commit = command("CMD-COMMIT-2", "COMMIT_SYNTHETIC_ISSUANCE", 4, {"route_manifest_sha256": "9" * 64, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"}}, math_decision=decision, idem_key="IDEM:COMMIT:2")
        subject = make_subject(issue_problem(), commands + [second_commit])
        codes = self.codes(subject)
        self.assertIn(ARCH_ISSUANCE_SLOT_CONFLICT, codes)

    def test_duplicate_issuance_in_ledger(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        entry = copy.deepcopy(subject["run"]["issuance_ledger"][0])
        subject["run"]["issuance_ledger"].append(entry)
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_DUPLICATE_ISSUANCE, self.codes(subject))


class TestAuthorization(ArchitectureWorkflowTestBase):
    def test_held_unauthorized_command_passes(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        authorizations = authorize_all(commands)
        held_command = commands[-1]
        del authorizations[held_command["authorization_decision_sha256"]]
        subject = make_subject(issue_problem(), commands, authorizations=authorizations)
        self.assertEqual([], evaluate(subject))
        self.assertIn("HELD_UNAUTHORIZED", [response["status"] for response in subject["run"]["responses"]])
        self.assertEqual(1, len(subject["run"]["held_outbox"]))
        self.assertEqual(6, len(subject["run"]["events"]))

    def test_self_granted_authority(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["authorizations"][subject["run"]["commands"][0]["authorization_decision_sha256"]]["granted_by"] = "principal-1"
        self.assertIn(ARCH_AUTHORITY_ESCALATION, self.codes(subject))

    def test_unattested_authority(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["authorizations"][subject["run"]["commands"][0]["authorization_decision_sha256"]].pop("granted_by")
        self.assertIn(ARCH_AUTHORITY_ESCALATION, self.codes(subject))

    def test_capability_escalation(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["commands"][3]["requested_capability"] = "issuance:commit"
        self.assertIn(ARCH_AUTHORITY_ESCALATION, self.codes(subject))


class TestProtectionAndExactTen(ArchitectureWorkflowTestBase):
    def test_protected_candidate_selected(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["result"]["selected"][0]["candidate_id"] = "C09"
        subject["run"]["result"]["selected"][0]["physical_location_id"] = "L09"
        subject["run"]["problem"] = None
        subject["problem"]["candidates"][9]["protected_status"] = "PROTECTED"
        self.assertIn(ARCH_PROTECTION_BYPASS, self.codes(subject))

    def test_unknown_candidate_selected(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["result"]["selected"][0]["candidate_id"] = "C99"
        subject["run"]["result"]["selected"][0]["physical_location_id"] = "L99"
        self.assertIn(ARCH_PROTECTION_BYPASS, self.codes(subject))

    def test_issue_with_nine_selected(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["result"]["selected"] = subject["run"]["result"]["selected"][:9]
        self.assertIn(ARCH_EXACT_TEN, self.codes(subject))

    def test_issue_with_eleven_selected(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        row = copy.deepcopy(subject["run"]["result"]["selected"][0])
        row["candidate_id"] = "C99"
        subject["run"]["result"]["selected"].append(row)
        self.assertIn(ARCH_EXACT_TEN, self.codes(subject))

    def test_duplicate_physical_location(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["result"]["selected"][1]["physical_location_id"] = subject["run"]["result"]["selected"][0]["physical_location_id"]
        self.assertIn(ARCH_DUPLICATE_LOCATION, self.codes(subject))

    def test_route_differs_from_math_selection(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["result"]["selected"].reverse()
        self.assertIn(ARCH_DECISION_MISMATCH, self.codes(subject))


class TestAbstainAndErrorPaths(ArchitectureWorkflowTestBase):
    def test_abstain_with_route_is_effects(self):
        decision = oracle(no_feasible_problem())
        subject = make_subject(no_feasible_problem(), abstain_commands(decision))
        subject["run"]["result"]["route"] = {"route": "made-up"}
        self.assertIn(ARCH_ABSTAIN_HAS_EFFECTS, self.codes(subject))

    def test_abstain_with_selected_stops_is_effects(self):
        decision = oracle(no_feasible_problem())
        subject = make_subject(no_feasible_problem(), abstain_commands(decision))
        subject["run"]["result"]["selected"] = [{"candidate_id": "C00", "physical_location_id": "L00"}]
        self.assertIn(ARCH_ABSTAIN_HAS_EFFECTS, self.codes(subject))

    def test_abstain_reason_hidden(self):
        decision = oracle(no_feasible_problem())
        subject = make_subject(no_feasible_problem(), abstain_commands(decision))
        subject["run"]["result"]["reason"] = ""
        subject["run"]["accessibility_projection"]["status"]["reason_code"] = ""
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        codes = self.codes(subject)
        self.assertIn(ARCH_ABSTAIN_REASON_HIDDEN, codes)
        self.assertIn(ARCH_STATUS_DISCLOSURE, codes)

    def test_abstain_decision_reason_mismatch(self):
        decision = oracle(no_feasible_problem())
        commands = abstain_commands(decision)
        commands[2]["payload"]["abstain_reason"] = "PROTECTED_BUNDLE_INCOMPLETE"
        subject = make_subject(no_feasible_problem(), commands)
        self.assertIn(ARCH_ABSTAIN_REASON_HIDDEN, self.codes(subject))

    def test_error_hidden_diagnostic(self):
        subject = make_subject(invalid_problem(), [command("C1", "DECIDE_ISSUE", 0, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": "0" * 64})])
        subject["run"]["result"]["diagnostic"] = ""
        self.assertIn(ARCH_ERROR_HIDDEN, self.codes(subject))

    def test_error_requires_safe_recovery(self):
        subject = make_subject(invalid_problem(), [command("C1", "DECIDE_ISSUE", 0, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": "0" * 64})])
        subject["run"]["result"]["safe_recovery_required"] = False
        self.assertIn(ARCH_ERROR_HIDDEN, self.codes(subject))


class TestStageIsolation(ArchitectureWorkflowTestBase):
    def test_stage2_after_abstain(self):
        decision = oracle(no_feasible_problem())
        commands = abstain_commands(decision) + [
            command("C4", "APPEND_STAGE2", 3, {"route_manifest_sha256": "1" * 64, "field_event_ids": ["FIELD_EVENT:F1"]}),
        ]
        subject = make_subject(no_feasible_problem(), commands)
        codes = self.codes(subject)
        self.assertIn(ARCH_DOWNSTREAM_BINDING, codes)
        self.assertIn(ARCH_ILLEGAL_TRANSITION, codes)

    def test_stage3_unbound_to_stage2(self):
        decision = oracle(issue_problem())
        subject = make_subject(issue_problem(), issue_commands(decision))
        subject["run"]["commands"][6]["payload"]["field_event_id"] = "FIELD_EVENT:MISSING"
        self.assertIn(ARCH_DOWNSTREAM_BINDING, self.codes(subject))

    def test_stage2_before_issuance(self):
        decision = oracle(issue_problem())
        source_sha = "0" * 64
        route_sha = "1" * 64
        commands = [
            command("C1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": source_sha, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, stage1_sha=source_sha),
            command("C2", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": source_sha}, stage1_sha=source_sha),
            command("C3", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": dg(decision)}, math_decision=decision, stage1_sha=source_sha),
            command("C4", "PREPARE_SYNTHETIC_ISSUANCE", 3, {"route_date": "2026-08-02", "prepared_route_sha256": route_sha}, math_decision=decision, stage1_sha=source_sha),
            command("C5", "APPEND_STAGE2", 4, {"route_manifest_sha256": route_sha, "field_event_ids": ["FIELD_EVENT:F1"]}, math_decision=decision, stage1_sha=source_sha),
            command("C6", "COMMIT_SYNTHETIC_ISSUANCE", 5, {"route_manifest_sha256": route_sha, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"}}, math_decision=decision, stage1_sha=source_sha),
        ]
        subject = make_subject(issue_problem(), commands)
        codes = self.codes(subject)
        self.assertIn(ARCH_ILLEGAL_TRANSITION, codes)

    def test_stage2_not_bound_to_issued_route(self):
        decision = oracle(issue_problem())
        subject = make_subject(issue_problem(), issue_commands(decision))
        subject["run"]["commands"][5]["payload"]["route_manifest_sha256"] = "9" * 64
        self.assertIn(ARCH_DOWNSTREAM_BINDING, self.codes(subject))


class TestJournalAndLineage(ArchitectureWorkflowTestBase):
    def test_journal_reordered_events(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["events"][1], subject["run"]["events"][2] = subject["run"]["events"][2], subject["run"]["events"][1]
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_JOURNAL_CHAIN, self.codes(subject))

    def test_journal_dropped_event(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["events"] = subject["run"]["events"][:-1]
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_JOURNAL_CHAIN, self.codes(subject))

    def test_journal_cycle(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        events = subject["run"]["events"]
        events[1]["predecessor_event_id"] = events[0]["event_id"]
        events[0]["predecessor_event_id"] = events[1]["event_id"]
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        codes = self.codes(subject)
        self.assertIn(ARCH_JOURNAL_CHAIN, codes)

    def test_event_sha_mismatch(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["events"][0]["event_sha256"] = "0" * 64
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_JOURNAL_CHAIN, self.codes(subject))

    def test_event_references_unknown_command(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["events"][0]["command_id"] = "CMD-GHOST"
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_LINEAGE_BINDING, self.codes(subject))

    def test_applied_command_without_event(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["events"] = subject["run"]["events"][:-1]
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        codes = self.codes(subject)
        self.assertIn(ARCH_LINEAGE_BINDING, codes)

    def test_coordinated_rehash_reconstruction_mismatch(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["events"] = subject["run"]["events"][:-1]
        subject["run"]["aggregate_version"] = 6
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        codes = self.codes(subject)
        self.assertIn(ARCH_RECONSTRUCTION_MISMATCH, codes)


class TestFaultAtomicity(ArchitectureWorkflowTestBase):
    def test_precommit_fault_no_retry_passes(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision, include_stage2=False, include_stage3=False)
        subject = make_subject(issue_problem(), commands, fault_schedule={"command_index": 4, "fault_point": "BEFORE_EVENT_APPEND", "retries": 0})
        self.assertEqual([], evaluate(subject))
        self.assertEqual("ISSUANCE_PREPARED", subject["run"]["state"])
        self.assertEqual([], subject["run"]["issuance_ledger"])

    def test_precommit_fault_retry_passes(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        subject = make_subject(issue_problem(), commands, fault_schedule={"command_index": 4, "fault_point": "AFTER_EVENT_BEFORE_PROJECTION", "retries": 1})
        self.assertEqual([], evaluate(subject))
        self.assertEqual(1, len(subject["run"]["issuance_ledger"]))

    def test_postcommit_fault_retry_passes(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        subject = make_subject(issue_problem(), commands, fault_schedule={"command_index": 4, "fault_point": "AFTER_COMMIT_BEFORE_RESPONSE", "retries": 2})
        self.assertEqual([], evaluate(subject))
        self.assertEqual(1, len(subject["run"]["issuance_ledger"]))

    def test_precommit_fault_leaves_partial_state(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision, include_stage2=False, include_stage3=False)
        subject = make_subject(issue_problem(), commands, fault_schedule={"command_index": 4, "fault_point": "BEFORE_EVENT_APPEND", "retries": 0})
        events = subject["run"]["events"]
        commit = commands[4]
        partial = {
            "event_id": "EVT:CMD-COMMIT-1",
            "command_id": "CMD-COMMIT-1",
            "command_sha256": dg(commit),
            "aggregate_version": 5,
            "predecessor_event_id": events[-1]["event_id"],
            "predecessor_event_sha256": events[-1]["event_sha256"],
            "from_state": "ISSUANCE_PREPARED",
            "to_state": "ISSUED_INTERNAL",
            "event_sha256": None,
            "applied_at": commit["submitted_at"],
        }
        partial["event_sha256"] = dg({k: v for k, v in partial.items() if k != "event_sha256"})
        events.append(partial)
        subject["run"]["aggregate_version"] = 5
        subject["run"]["state"] = "ISSUED_INTERNAL"
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_PARTIAL_FAILURE_AMBIGUOUS, self.codes(subject))

    def test_unknown_fault_point(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        subject = make_subject(issue_problem(), commands, fault_schedule={"command_index": 4, "fault_point": "BETWEEN_TWO_STATES", "retries": 0})
        self.assertIn(ARCH_PARTIAL_FAILURE_AMBIGUOUS, self.codes(subject))

    def test_all_six_fault_points(self):
        decision = oracle(issue_problem())
        for point in ["BEFORE_EVENT_APPEND", "AFTER_EVENT_BEFORE_PROJECTION", "AFTER_PROJECTION_BEFORE_IDEMPOTENCY", "AFTER_IDEMPOTENCY_BEFORE_OUTBOX", "AFTER_OUTBOX_BEFORE_COMMIT", "AFTER_COMMIT_BEFORE_RESPONSE"]:
            for retries in (0, 1, 2):
                halted = point in PRECOMMIT_POINTS and retries == 0
                commands = issue_commands(decision, include_stage2=not halted, include_stage3=not halted)
                subject = make_subject(issue_problem(), commands, fault_schedule={"command_index": 4, "fault_point": point, "retries": retries})
                self.assertEqual([], evaluate(subject), f"{point} retries={retries}")


class TestAccessibility(ArchitectureWorkflowTestBase):
    def test_visual_only_is_nonvisual(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["visual_only"] = True
        self.assertIn(ARCH_ACCESSIBLE_NONVISUAL, self.codes(subject))

    def test_missing_status_field(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["status"].pop("primary_status_code")
        self.assertIn(ARCH_ACCESSIBLE_STATUS, self.codes(subject))

    def test_missing_action_fields(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["actions"][0].pop("role")
        codes = self.codes(subject)
        self.assertIn(ARCH_ACCESSIBLE_ACTION, codes)

    def test_duplicate_action_identifiers(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["actions"][1]["action_id"] = "retry"
        self.assertIn(ARCH_ACCESSIBLE_ACTION, self.codes(subject))

    def test_duplicate_focus_order(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["focus_order"] = ["retry", "retry"]
        self.assertIn(ARCH_ACCESSIBLE_STATUS, self.codes(subject))

    def test_empty_reading_order_with_actions(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["reading_order"] = []
        self.assertIn(ARCH_ACCESSIBLE_STATUS, self.codes(subject))

    def test_abstain_reason_disclosed(self):
        decision = oracle(no_feasible_problem())
        subject = make_subject(no_feasible_problem(), abstain_commands(decision))
        subject["run"]["accessibility_projection"]["status"]["reason_code"] = None
        self.assertIn(ARCH_STATUS_DISCLOSURE, self.codes(subject))

    def test_bad_claim_kind_is_claim_ceiling(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["claim_kind"] = "WCAG_CLAIM"
        self.assertIn(ARCH_CLAIM_CEILING, self.codes(subject))

    def test_bad_claims_not_established(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["accessibility_projection"]["claims_not_established"] = ["WCAG_CONFORMANCE"]
        self.assertIn(ARCH_CLAIM_CEILING, self.codes(subject))


class TestClaimCeilingAndLiveSafety(ArchitectureWorkflowTestBase):
    def test_proof_level_ceil(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["proof"]["level"] = 8
        self.assertIn(ARCH_CLAIM_CEILING, self.codes(subject))

    def test_usability_claim_beyond_ceiling(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["proof"]["real_usability_proven"] = True
        self.assertIn(ARCH_CLAIM_CEILING, self.codes(subject))

    def test_live_workflow_authorized_denied(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["proof"]["live_workflow_authorized"] = True
        self.assertIn(ARCH_LIVE_DENIAL, self.codes(subject))

    def test_owner_authority_ceiling(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["owner"]["real_world_authority"] = "CRE_FOUNDRY_BUILDER"
        self.assertIn(ARCH_CLAIM_CEILING, self.codes(subject))

    def test_receipt_claim_ceiling_mismatch(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["receipt"]["claim_ceiling"] = "short"
        self.assertIn(ARCH_CLAIM_CEILING, self.codes(subject))

    def test_representative_actor_is_live_denial(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        commands[4]["actor_class"] = "REPRESENTATIVE"
        subject = make_subject(issue_problem(), commands)
        self.assertIn(ARCH_LIVE_DENIAL, self.codes(subject))


class TestManualReview(ArchitectureWorkflowTestBase):
    def test_allowed_review_chain_passes(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())), review_records=chained_review_records())
        self.assertEqual([], evaluate(subject))

    def test_forbidden_action_is_manual_bypass(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["review_records"] = [review_record("REV-X", 1, "EDIT_FROZEN_STAGE1")]
        codes = self.codes(subject)
        self.assertIn(ARCH_MANUAL_BYPASS, codes)

    def test_grants_real_authority_is_manual_bypass(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["review_records"] = [review_record("REV-Y", 1, "ANNOTATE", grants_real_authority=True)]
        codes = self.codes(subject)
        self.assertIn(ARCH_MANUAL_BYPASS, codes)

    def test_review_chain_break(self):
        records = chained_review_records()
        records[2]["predecessor"]["sha256"] = "0" * 64
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())), review_records=records)
        self.assertIn(ARCH_MANUAL_BYPASS, self.codes(subject))

    def test_unregistered_review_action(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["review_records"] = [review_record("REV-Z", 1, "MAKE_IT_SO")]
        codes = self.codes(subject)
        self.assertIn(ARCH_MANUAL_BYPASS, codes)


class TestReceiptReplay(ArchitectureWorkflowTestBase):
    def test_command_stream_digest_mismatch(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["receipt"]["command_stream_sha256"] = "0" * 64
        self.assertIn(ARCH_RECONSTRUCTION_MISMATCH, self.codes(subject))

    def test_final_receipt_digest_mismatch(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["receipt"]["final_receipt_sha256"] = "0" * 64
        self.assertIn(ARCH_RECONSTRUCTION_MISMATCH, self.codes(subject))

    def test_accessibility_digest_mismatch(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["receipt"]["accessibility_projection_sha256"] = "0" * 64
        self.assertIn(ARCH_RECONSTRUCTION_MISMATCH, self.codes(subject))


class TestExternalEffectsAndLiveDelivery(ArchitectureWorkflowTestBase):
    def test_external_effect_in_ledger(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["issuance_ledger"][0]["external_effect_occurred"] = True
        self.assertIn(ARCH_EXTERNAL_EFFECT, self.codes(subject))

    def test_outbox_delivered_is_live_denial(self):
        decision = oracle(issue_problem())
        commands = issue_commands(decision)
        authorizations = authorize_all(commands)
        del authorizations[commands[-1]["authorization_decision_sha256"]]
        subject = make_subject(issue_problem(), commands, authorizations=authorizations)
        subject["run"]["held_outbox"][0]["delivered_at"] = "2026-08-02T00:00:00Z"
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_LIVE_DENIAL, self.codes(subject))

    def test_unregistered_effect_kind(self):
        subject = make_subject(issue_problem(), issue_commands(oracle(issue_problem())))
        subject["run"]["effect_ledger"] = [{"effect_id": "E1", "external_effect_occurred": False, "effect_kind": "LIVE_FIRED"}]
        subject["run"]["receipt"] = make_receipt(subject["run"], subject["run"]["accessibility_projection"])
        self.assertIn(ARCH_EXTERNAL_EFFECT, self.codes(subject))


class TestDiagnosticCoverage(ArchitectureWorkflowTestBase):
    def test_all_registered_diagnostics_are_exercised(self):
        exercised = {
            ARCH_SHAPE_INVALID, ARCH_SCHEMA_UNREGISTERED, ARCH_EVALUATOR_COUPLING, ARCH_MODULE_REGISTRY,
            ARCH_MODULE_BINDING, ARCH_POLICY_BYPASS, ARCH_AUTHORITY_ESCALATION, ARCH_LIVE_DENIAL,
            ARCH_EXTERNAL_EFFECT, ARCH_EXACT_TEN, ARCH_DUPLICATE_LOCATION, ARCH_DECISION_MISMATCH,
            ARCH_PROTECTION_BYPASS, ARCH_ABSTAIN_HAS_EFFECTS, ARCH_ABSTAIN_REASON_HIDDEN, ARCH_ERROR_HIDDEN,
            ARCH_MANUAL_BYPASS, ARCH_STAGE1_REWRITE, ARCH_ILLEGAL_TRANSITION, ARCH_COMMIT_WITHOUT_PREPARE,
            ARCH_DUPLICATE_ISSUANCE, ARCH_IDEMPOTENCY_CONFLICT, ARCH_ISSUANCE_SLOT_CONFLICT,
            ARCH_PARTIAL_FAILURE_AMBIGUOUS, ARCH_JOURNAL_CHAIN, ARCH_LINEAGE_BINDING, ARCH_DOWNSTREAM_BINDING,
            ARCH_ACCESSIBLE_ACTION, ARCH_ACCESSIBLE_STATUS, ARCH_ACCESSIBLE_NONVISUAL, ARCH_STATUS_DISCLOSURE,
            ARCH_UNKNOWN_COMMAND, ARCH_RECONSTRUCTION_MISMATCH, ARCH_CLAIM_CEILING,
        }
        registered = {row["diagnostic"] for row in SCENARIO_REGISTRY["registered_diagnostics"]}
        self.assertEqual(registered, ALL_ARCH_CODES)
        self.assertEqual(registered, exercised)
        self.assertEqual(34, len(registered))


class TestOnDiskFixtures(ArchitectureWorkflowTestBase):
    def fixture_dir(self):
        return Path(__file__).parent / "fixtures" / "architecture"

    def run_evaluator(self, relative):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "evals/public/architecture_workflow_evaluator.py"), "--input", str(self.fixture_dir() / relative)],
            cwd=ROOT, text=True, capture_output=True,
        )
        payload = json.loads(proc.stdout)
        return proc.returncode, payload

    def test_issue_fixture_passes(self):
        code, payload = self.run_evaluator("architecture_issue_valid.json")
        self.assertEqual(0, code, payload)
        self.assertTrue(payload["passed"])
        self.assertEqual([], payload["errors"])

    def test_abstain_fixture_passes(self):
        for name in ("architecture_abstain_no_feasible.json", "architecture_abstain_protected_bundle.json", "architecture_abstain_unresolved_value.json"):
            code, payload = self.run_evaluator(name)
            self.assertEqual(0, code, payload)

    def test_error_fixture_passes(self):
        code, payload = self.run_evaluator("architecture_error_invalid_problem.json")
        self.assertEqual(0, code, payload)

    def test_authorization_held_fixture_passes(self):
        code, payload = self.run_evaluator("architecture_authorization_held.json")
        self.assertEqual(0, code, payload)

    def test_fault_fixture_passes(self):
        code, payload = self.run_evaluator("architecture_fault_precommit_no_retry.json")
        self.assertEqual(0, code, payload)

    def test_idempotent_replay_fixture_passes(self):
        code, payload = self.run_evaluator("architecture_idempotent_replay.json")
        self.assertEqual(0, code, payload)

    def test_known_bad_live_enabled_detected(self):
        code, payload = self.run_evaluator("known_bad_live_enabled.json")
        self.assertEqual(1, code)
        codes = {error.split(":")[0] for error in payload["errors"]}
        self.assertIn(ARCH_LIVE_DENIAL, codes)

    def test_known_bad_duplicate_location_detected(self):
        code, payload = self.run_evaluator("known_bad_duplicate_location.json")
        self.assertEqual(1, code)
        codes = {error.split(":")[0] for error in payload["errors"]}
        self.assertIn(ARCH_DUPLICATE_LOCATION, codes)

    def test_known_bad_manual_bypass_detected(self):
        code, payload = self.run_evaluator("known_bad_manual_bypass.json")
        self.assertEqual(1, code)
        codes = {error.split(":")[0] for error in payload["errors"]}
        self.assertIn(ARCH_MANUAL_BYPASS, codes)

    def test_known_bad_journal_rehash_detected(self):
        code, payload = self.run_evaluator("known_bad_journal_rehash.json")
        self.assertEqual(1, code)
        codes = {error.split(":")[0] for error in payload["errors"]}
        self.assertIn(ARCH_RECONSTRUCTION_MISMATCH, codes)


if __name__ == "__main__":
    unittest.main()
