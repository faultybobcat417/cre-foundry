"""Independent black-box ARCHITECTURE-001 workflow evaluator.

This evaluator judges one architecture workflow subject against the frozen
public evaluator contract and the frozen S-1 schemas and registries.  It never
imports the architecture implementation package and never invokes
implementation-private functions.  It reconstructs the entire expected workflow
from the canonical command stream, the pinned public MATH oracle, the
state-machine registry and the module registry, then compares every claimed
artifact against that reconstruction.

A subject is an evaluator-owned document:

    {
      "subject_kind": "ARCHITECTURE_WORKFLOW_SUBJECT",
      "schema_version": "1.0.0",
      "evaluator_id": "architecture-workflow-public-v1",
      "canonicalization": "SORTED_KEYS_INTEGER_JSON_V1",
      "problem": <math_decision_policy problem>,
      "authorizations": { "<sha256>": <authorization decision> },
      "modules": [ <module registry entries> ],
      "fault_schedule": null | {"command_index": int, "fault_point": str, "retries": int},
      "run": <architecture_workflow_run document>,
      "review_records": [ <architecture_review_record documents> ]
    }

Canonical digest convention (SORTED_KEYS_INTEGER_JSON_V1):
  * command_sha256 of an event  = digest of the command envelope.
  * event_sha256                = digest of the event fields excluding
                                  event_sha256 itself.
  * genesis predecessor         = digest of the sentinel object
                                  {"genesis": true, "initial_state": "COLLECTING_STAGE1"}.
  * response_sha256             = digest of the response body object.
  * receipt per-section digests = canonical digest of the corresponding array
                                  or object; final_receipt_sha256 is the digest
                                  of the whole receipt excluding that field.
  * math_decision_sha256        = digest of the pinned MATH oracle decision.

Diagnostics are stable ARCH-* codes registered in the frozen scenario registry.
The evaluator fails closed: any malformed, unknown, or inconsistent artifact
yields one or more ARCH-* codes and never trusts hashes alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[2]

CONTRACT_PATH = ROOT / "artifacts/architecture/public_evaluator_contract.json"
STATE_REGISTRY_PATH = ROOT / "artifacts/architecture/state_machine_registry.json"
MODULE_REGISTRY_PATH = ROOT / "artifacts/architecture/module_registry.json"
SCENARIO_REGISTRY_PATH = ROOT / "artifacts/architecture/scenario_registry.json"

SCHEMA_PATHS = {
    "command": ROOT / "contracts/architecture_command.schema.json",
    "workflow_run": ROOT / "contracts/architecture_workflow_run.schema.json",
    "review_record": ROOT / "contracts/architecture_review_record.schema.json",
    "accessibility": ROOT / "contracts/architecture_accessibility_projection.schema.json",
}
MATH_DECISION_SCHEMA_PATH = ROOT / "contracts/math_route_decision.schema.json"
MATH_POLICY_SCHEMA_PATH = ROOT / "contracts/math_decision_policy.schema.json"

# Stable diagnostics registered in the frozen scenario registry.
ARCH_EVALUATOR_COUPLING = "ARCH-EVALUATOR-COUPLING"
ARCH_JOURNAL_CHAIN = "ARCH-JOURNAL-CHAIN"
ARCH_LINEAGE_BINDING = "ARCH-LINEAGE-BINDING"
ARCH_UNKNOWN_COMMAND = "ARCH-UNKNOWN-COMMAND"
ARCH_RECONSTRUCTION_MISMATCH = "ARCH-RECONSTRUCTION-MISMATCH"
ARCH_DOWNSTREAM_BINDING = "ARCH-DOWNSTREAM-BINDING"
ARCH_SHAPE_INVALID = "ARCH-SHAPE-INVALID"
ARCH_SCHEMA_UNREGISTERED = "ARCH-SCHEMA-UNREGISTERED"
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
ARCH_ACCESSIBLE_ACTION = "ARCH-ACCESSIBLE-ACTION"
ARCH_ACCESSIBLE_STATUS = "ARCH-ACCESSIBLE-STATUS"
ARCH_ACCESSIBLE_NONVISUAL = "ARCH-ACCESSIBLE-NONVISUAL"
ARCH_STATUS_DISCLOSURE = "ARCH-STATUS-DISCLOSURE"
ARCH_CLAIM_CEILING = "ARCH-CLAIM-CEILING"

INITIAL_STATE = "COLLECTING_STAGE1"
TERMINAL_STATES = {"ABSTAINED", "QUARANTINED", "SUPERSEDED", "VOIDED"}
RESERVED_LIVE_STATES = {"DELIVERY_PENDING", "DELIVERED", "RECALL_REQUIRED"}
SIDECAR_COMMANDS = {"RECORD_REVIEW_ANNOTATION", "REQUEST_AUTHORITATIVE_EVIDENCE"}
RESULT_STATUSES = {"APPLIED", "IDEMPOTENT_REPLAY", "REJECTED", "CONFLICT", "HELD_UNAUTHORIZED"}
FAULT_POINTS = {
    "BEFORE_EVENT_APPEND",
    "AFTER_EVENT_BEFORE_PROJECTION",
    "AFTER_PROJECTION_BEFORE_IDEMPOTENCY",
    "AFTER_IDEMPOTENCY_BEFORE_OUTBOX",
    "AFTER_OUTBOX_BEFORE_COMMIT",
    "AFTER_COMMIT_BEFORE_RESPONSE",
}
PRECOMMIT_FAULT_POINTS = {
    "BEFORE_EVENT_APPEND",
    "AFTER_EVENT_BEFORE_PROJECTION",
    "AFTER_PROJECTION_BEFORE_IDEMPOTENCY",
    "AFTER_IDEMPOTENCY_BEFORE_OUTBOX",
    "AFTER_OUTBOX_BEFORE_COMMIT",
}
CAPABILITY_BY_COMMAND = {
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
# Write-like commands must be authorized; review sidecars are also gated.
EFFECTFUL_MODULE_ROLES = {"issuance_port", "field_event_port", "outcome_port"}

_JSON_FORMAT_CHECKER = FormatChecker()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(path: Path) -> Any:
    """Load JSON rejecting duplicate keys and shape-invalid documents."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def _load_strict_json(path: Path, errors: list[str]) -> Any:
    try:
        return strict_load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{ARCH_SHAPE_INVALID}: {path.name} failed strict parse: {type(exc).__name__}")
        return None


def _time_iso(value: Any) -> str:
    return str(value)


def _frozen_artifacts(errors: list[str]) -> dict[str, Any]:
    contract = _load_strict_json(CONTRACT_PATH, errors)
    state = _load_strict_json(STATE_REGISTRY_PATH, errors)
    modules = _load_strict_json(MODULE_REGISTRY_PATH, errors)
    scenarios = _load_strict_json(SCENARIO_REGISTRY_PATH, errors)
    schemas = {name: _load_strict_json(path, errors) for name, path in SCHEMA_PATHS.items()}
    return {
        "contract": contract,
        "state": state,
        "modules": modules,
        "scenarios": scenarios,
        "schemas": schemas,
    }


def _schema_validators(schemas: dict[str, Any]) -> dict[str, Draft202012Validator]:
    """Build closed validators whose cross-schema $refs resolve in-process.

    The workflow-run schema references the command and accessibility schemas by
    relative name; the referencing registry below resolves those names to the
    absolute $id namespace so validation never falls back to network fetch.
    """
    registry: Registry = Registry()
    aliases = {
        "command": "https://cre-foundry.local/schemas/architecture_command.schema.json",
        "workflow_run": "https://cre-foundry.local/schemas/architecture_workflow_run.schema.json",
        "review_record": "https://cre-foundry.local/schemas/architecture_review_record.schema.json",
        "accessibility": "https://cre-foundry.local/schemas/architecture_accessibility_projection.schema.json",
    }
    for name, schema in schemas.items():
        if not schema:
            continue
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        schema_id = schema.get("$id")
        if schema_id:
            registry = registry.with_resource(schema_id, resource)
        if name in aliases:
            registry = registry.with_resource(aliases[name], resource)
    return {name: Draft202012Validator(schema, format_checker=_JSON_FORMAT_CHECKER, registry=registry) for name, schema in schemas.items() if schema}


def _first_schema_error(validator: Draft202012Validator, document: Any) -> str | None:
    errors = sorted(validator.iter_errors(document), key=lambda error: (list(error.absolute_path), error.message))
    return errors[0].message if errors else None


def _allowed_transitions(state_registry: dict[str, Any]) -> list[dict[str, str]]:
    return state_registry.get("allowed_transitions", [])


def _find_transition(state_registry: dict[str, Any], command: str, from_state: str) -> dict[str, str] | None:
    for row in _allowed_transitions(state_registry):
        if row["command_type"] == command and row["from"] == from_state:
            return row
    return None


def _command_capability(command_type: str) -> str | None:
    return CAPABILITY_BY_COMMAND.get(command_type)


def _authorization_is_current(decision: Any, command: dict[str, Any]) -> bool:
    if not isinstance(decision, dict):
        return False
    if decision.get("decision") != "GRANTED":
        return False
    if decision.get("scope") != "SYNTHETIC_NON_INFLUENCING":
        return False
    if decision.get("capability") != command.get("requested_capability"):
        return False
    if decision.get("principal_reference") != command.get("principal_reference"):
        return False
    if decision.get("revoked_at") is not None:
        return False
    now = command.get("submitted_at", "")
    issued = decision.get("issued_at")
    expires = decision.get("expires_at")
    if issued and now < issued:
        return False
    if expires and now > expires:
        return False
    return True


def _module_role_of(command_type: str) -> str | None:
    return {
        "APPEND_STAGE1": "observation_port",
        "FREEZE_STAGE1": "observation_port",
        "DECIDE_ISSUE": "decision_port",
        "DECIDE_ABSTAIN": "decision_port",
        "QUARANTINE_INVALID": "decision_port",
        "PREPARE_SYNTHETIC_ISSUANCE": "issuance_port",
        "COMMIT_SYNTHETIC_ISSUANCE": "issuance_port",
        "APPEND_STAGE2": "field_event_port",
        "APPEND_STAGE3": "outcome_port",
        "VOID_UNDELIVERED": "issuance_port",
        "SUPERSEDE_WITH_NEW_GENERATION": "workflow_query_port",
        "RECORD_REVIEW_ANNOTATION": "workflow_query_port",
        "REQUEST_AUTHORITATIVE_EVIDENCE": "workflow_query_port",
    }.get(command_type)


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


GENESIS_DIGEST = ""


def _genesis_predecessor() -> str:
    return digest_json({"genesis": True, "initial_state": INITIAL_STATE})


def _receipt_digest(receipt: dict[str, Any]) -> str:
    body = {key: value for key, value in receipt.items() if key != "final_receipt_sha256"}
    return digest_json(body)


def _build_validators() -> dict[str, Draft202012Validator]:
    errors: list[str] = []
    frozen = _frozen_artifacts(errors)
    return _schema_validators(frozen["schemas"])


VALIDATORS = _build_validators()


def _expects_schema_version(schema: dict[str, Any]) -> str | None:
    prop = schema.get("properties", {}).get("schema_version")
    if isinstance(prop, dict) and "const" in prop:
        return prop["const"]
    return None


def _reconstruct(
    subject: dict[str, Any],
    frozen: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """Reconstruct the expected workflow from the canonical command stream."""
    contract = frozen["contract"]
    state_registry = frozen["state"]
    command_schema = frozen["schemas"]["command"]
    command_validator = VALIDATORS["command"]

    run = subject.get("run")
    commands = run.get("commands", []) if isinstance(run, dict) else []
    modules = subject.get("modules", [])
    authorizations = subject.get("authorizations", {})
    problem = subject.get("problem")

    fault = subject.get("fault_schedule")
    if not isinstance(fault, dict):
        fault = None
    fault_index = int(fault.get("command_index", -1)) if fault else -1
    fault_point = fault.get("fault_point") if fault else None
    fault_retries = int(fault.get("retries", 0)) if fault else 0
    fault_skips = fault_point in PRECOMMIT_FAULT_POINTS and fault_retries == 0

    state = INITIAL_STATE
    aggregate_version = 0
    genesis = _genesis_predecessor()
    events: list[dict[str, Any]] = []
    idempotency_map: dict[str, dict[str, Any]] = {}
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
    math_decision = None

    if isinstance(problem, dict):
        try:
            from evals.public.math_oracle_evaluator import evaluate as math_oracle_evaluate
        except ModuleNotFoundError:  # unittest discovery adds evals/public directly
            from math_oracle_evaluator import evaluate as math_oracle_evaluate
        try:
            math_decision = math_oracle_evaluate(problem)
        except (ValueError, KeyError, TypeError):
            math_decision = None

    for index, command in enumerate(commands):
        command_type = command.get("command_type")
        schema_error = _first_schema_error(command_validator, command)
        if schema_error is not None:
            errors.append(f"{ARCH_SHAPE_INVALID}: command[{index}] {schema_error}")
        command_sha = digest_json(command)

        capability = _command_capability(command_type)
        if capability is not None and command.get("requested_capability") != capability:
            errors.append(f"{ARCH_POLICY_BYPASS}: command[{index}] {command_type} capability mismatch")

        if command_type not in CAPABILITY_BY_COMMAND:
            errors.append(f"{ARCH_UNKNOWN_COMMAND}: command[{index}] {command_type}")
            continue

        decision = authorizations.get(command.get("authorization_decision_sha256"))
        authorized = _authorization_is_current(decision, command)
        if not authorized:
            status = "HELD_UNAUTHORIZED"
            response = {
                "result_status": status,
                "retry_allowed": True,
                "focus_target": command.get("command_id"),
                "announcement_intent": "ALERT",
            }
            responses.append(
                {"command_id": command.get("command_id"), "status": status, "response_sha256": digest_json(response), "response": response}
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
            response = {
                "result_status": "APPLIED",
                "retry_allowed": True,
                "focus_target": command.get("command_id"),
                "announcement_intent": "POLITE",
            }
            responses.append(
                {"command_id": command.get("command_id"), "status": "APPLIED", "response_sha256": digest_json(response), "response": response}
            )
            continue

        if index == fault_index and fault_skips:
            continue

        idem_key = command.get("idempotency_key", {}).get("key")
        scope = (command.get("aggregate_key", {}).get("representative_id"), command.get("aggregate_key", {}).get("route_date"), command.get("aggregate_key", {}).get("generation"), command_type, idem_key)
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
                response = {"result_status": "CONFLICT", "retry_allowed": False, "focus_target": command.get("command_id"), "announcement_intent": "ALERT"}
                responses.append(
                    {"command_id": command.get("command_id"), "status": "CONFLICT", "response_sha256": digest_json(response), "response": response}
                )
            continue

        expected_version = command.get("expected_aggregate_version")
        if expected_version != aggregate_version:
            errors.append(f"{ARCH_ILLEGAL_TRANSITION}: command[{index}] expected aggregate version {expected_version} but current is {aggregate_version}")

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

        transition = _find_transition(state_registry, command_type, state)
        if transition is None:
            errors.append(f"{ARCH_ILLEGAL_TRANSITION}: command[{index}] {command_type} from {state} is not an allowed transition")
            continue
        to_state = transition["to"]

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

        if command_type in {"APPEND_STAGE1", "FREEZE_STAGE1", "DECIDE_ISSUE", "DECIDE_ABSTAIN", "QUARANTINE_INVALID", "PREPARE_SYNTHETIC_ISSUANCE", "COMMIT_SYNTHETIC_ISSUANCE", "APPEND_STAGE2", "APPEND_STAGE3", "VOID_UNDELIVERED", "SUPERSEDE_WITH_NEW_GENERATION"}:
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
            response_body = {"result_status": "APPLIED", "retry_allowed": True, "focus_target": command.get("command_id"), "announcement_intent": "POLITE"}
            if command_type == "DECIDE_ISSUE" and math_decision is not None:
                response_body["result"] = "ISSUE"
            elif command_type == "DECIDE_ABSTAIN" and math_decision is not None:
                response_body["result"] = "ABSTAIN_NO_VALID_TEN"
                response_body["reason"] = math_decision.get("reason")
            responses.append(
                {"command_id": command.get("command_id"), "status": "APPLIED", "response_sha256": digest_json(response_body), "response": response_body}
            )
            idempotency_map[scope] = {"payload_sha256": payload_sha, "response": response_body}
            idempotency_records.append(
                {
                    "idempotency_key": idem_key,
                    "aggregate_key": command.get("aggregate_key"),
                    "command_type": command_type,
                    "original_command_id": command.get("command_id"),
                    "status": "APPLIED",
                    "original_response_sha256": digest_json(response_body),
                }
            )
            if command_type == "PREPARE_SYNTHETIC_ISSUANCE":
                prepared_route_sha = command.get("payload", {}).get("prepared_route_sha256")
            if command_type == "COMMIT_SYNTHETIC_ISSUANCE":
                committed_route_sha = command.get("payload", {}).get("route_manifest_sha256")
                selected_candidate_ids = []
                selected_physical_location_ids = []
                if math_decision is not None and math_decision.get("decision") == "ISSUE":
                    selected_candidate_ids = [row["candidate_id"] for row in math_decision.get("selected", [])]
                    selected_physical_location_ids = [row["physical_location_id"] for row in math_decision.get("selected", [])]
                    issued_stop_pairs = [(row["candidate_id"], row["physical_location_id"]) for row in math_decision.get("selected", [])]
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
        selected = math_decision.get("selected", [])
        result = {
            "result": "ISSUE",
            "selected": selected,
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
        result = {"result": "ERROR", "selected": [], "route": None, "diagnostic": "INVALID_PROBLEM", "safe_recovery_required": True, "downstream_effects_count": 0, "external_effect_occurred": False}

    return {
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
        "math_decision": math_decision,
    }


def _compare_artifacts(run: dict[str, Any], expected: dict[str, Any], errors: list[str]) -> None:
    if run.get("state") != expected["state"]:
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: final state {run.get('state')} expected {expected['state']}")
    if run.get("is_terminal") != expected["is_terminal"]:
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: terminal flag mismatch")
    if run.get("aggregate_version") != expected["aggregate_version"]:
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: aggregate version {run.get('aggregate_version')} expected {expected['aggregate_version']}")

    claimed_events = run.get("events", [])
    if len(claimed_events) != len(expected["events"]):
        errors.append(f"{ARCH_JOURNAL_CHAIN}: event count {len(claimed_events)} expected {len(expected['events'])}")
    for index, (claimed, wanted) in enumerate(zip(claimed_events, expected["events"])):
        for field in ("event_id", "command_id", "command_sha256", "aggregate_version", "predecessor_event_id", "predecessor_event_sha256", "from_state", "to_state", "applied_at"):
            if claimed.get(field) != wanted[field]:
                errors.append(f"{ARCH_JOURNAL_CHAIN}: event[{index}] {field} differs")
        if claimed.get("event_sha256") != _event_digest(claimed):
            errors.append(f"{ARCH_JOURNAL_CHAIN}: event[{index}] event_sha256 does not match its content")

    claimed_idem = run.get("idempotency_records", [])
    if len(claimed_idem) != len(expected["idempotency_records"]):
        errors.append(f"{ARCH_JOURNAL_CHAIN}: idempotency record count mismatch")

    claimed_ledger = run.get("issuance_ledger", [])
    if len(claimed_ledger) != len(expected["issuance_ledger"]):
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: issuance ledger count {len(claimed_ledger)} expected {len(expected['issuance_ledger'])}")

    claimed_outbox = run.get("held_outbox", [])
    if len(claimed_outbox) != len(expected["held_outbox"]):
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: held outbox count {len(claimed_outbox)} expected {len(expected['held_outbox'])}")

    claimed_responses = run.get("responses", [])
    if len(claimed_responses) != len(expected["responses"]):
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: response count {len(claimed_responses)} expected {len(expected['responses'])}")
    for index, (claimed, wanted) in enumerate(zip(claimed_responses, expected["responses"])):
        for field in ("command_id", "status", "response_sha256"):
            if claimed.get(field) != wanted[field]:
                errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: response[{index}] {field} differs")
        if claimed.get("response_sha256") and claimed.get("response") is not None:
            if digest_json(claimed["response"]) != claimed.get("response_sha256"):
                errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: response[{index}] response_sha256 does not match its content")

    claimed_result = run.get("result")
    expected_result = expected["result"]
    if claimed_result is None and expected_result is not None:
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: result missing")
    elif claimed_result is not None and expected_result is not None:
        if claimed_result.get("result") != expected_result.get("result"):
            errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: result {claimed_result.get('result')} expected {expected_result.get('result')}")
        if expected_result.get("result") == "ISSUE":
            selected = claimed_result.get("selected", [])
            candidate_ids = [row.get("candidate_id") for row in selected]
            physical_ids = [row.get("physical_location_id") for row in selected]
            if len(selected) != 10 or len(set(candidate_ids)) != 10:
                errors.append(f"{ARCH_EXACT_TEN}: ISSUE must select exactly ten distinct candidates")
            if len(selected) != 10 or len(set(physical_ids)) != 10:
                errors.append(f"{ARCH_DUPLICATE_LOCATION}: ISSUE must select exactly ten distinct physical locations")
            if claimed_result.get("reason") is not None:
                errors.append(f"{ARCH_DECISION_MISMATCH}: ISSUE reason must be null")
            if claimed_result.get("external_effect_occurred") is not False:
                errors.append(f"{ARCH_EXTERNAL_EFFECT}: ISSUE must not record an external effect")
        elif expected_result.get("result") == "ABSTAIN_NO_VALID_TEN":
            if claimed_result.get("selected") not in ([], None):
                errors.append(f"{ARCH_ABSTAIN_HAS_EFFECTS}: abstain must not select stops")
            if claimed_result.get("route") is not None:
                errors.append(f"{ARCH_ABSTAIN_HAS_EFFECTS}: abstain must not create a route")
            if claimed_result.get("reason") in (None, ""):
                errors.append(f"{ARCH_ABSTAIN_REASON_HIDDEN}: abstain reason hidden")
            if claimed_result.get("downstream_effects_count") not in (0, None):
                errors.append(f"{ARCH_ABSTAIN_HAS_EFFECTS}: abstain must have no downstream effects")
            if claimed_result.get("external_effect_occurred") is not False:
                errors.append(f"{ARCH_EXTERNAL_EFFECT}: abstain must not record an external effect")
        elif expected_result.get("result") == "ERROR":
            if claimed_result.get("selected") not in ([], None):
                errors.append(f"{ARCH_ERROR_HIDDEN}: ERROR must not select stops")
            if claimed_result.get("route") is not None:
                errors.append(f"{ARCH_ERROR_HIDDEN}: ERROR must not create a route")
            if not claimed_result.get("diagnostic"):
                errors.append(f"{ARCH_ERROR_HIDDEN}: ERROR must expose a diagnostic")
            if claimed_result.get("safe_recovery_required") is not True:
                errors.append(f"{ARCH_ERROR_HIDDEN}: ERROR must require safe recovery")


def _check_result_union_and_decisions(subject: dict[str, Any], expected: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    claimed_result = run.get("result")
    math_decision = expected.get("math_decision")
    if math_decision is None:
        return
    if math_decision.get("decision") == "ISSUE" and claimed_result is not None and claimed_result.get("result") == "ABSTAIN_NO_VALID_TEN":
        errors.append(f"{ARCH_DECISION_MISMATCH}: claimed abstain but MATH oracle issues")
    if math_decision.get("decision") == "ABSTAIN_NO_VALID_TEN" and claimed_result is not None and claimed_result.get("result") == "ISSUE":
        errors.append(f"{ARCH_DECISION_MISMATCH}: claimed ISSUE but MATH oracle abstains")
    claimed_selected = claimed_result.get("selected", []) if isinstance(claimed_result, dict) else []
    expected_pairs = expected.get("issued_stop_pairs", [])
    claimed_pairs = [(row.get("candidate_id"), row.get("physical_location_id")) for row in claimed_selected]
    if math_decision.get("decision") == "ISSUE" and expected_pairs and claimed_pairs and claimed_pairs != expected_pairs:
        errors.append(f"{ARCH_DECISION_MISMATCH}: route differs from MATH selection")


def _check_journal_lineage(run: dict[str, Any], errors: list[str]) -> None:
    events = run.get("events", [])
    event_ids = [event.get("event_id") for event in events]
    if len(event_ids) != len(set(event_ids)):
        errors.append(f"{ARCH_JOURNAL_CHAIN}: duplicate event ids")
    seen: set[str] = set()
    for event in events:
        event_id = event.get("event_id")
        if event_id in seen:
            errors.append(f"{ARCH_JOURNAL_CHAIN}: cycle in event chain")
            break
        seen.add(event_id)
    for index, event in enumerate(events):
        if event.get("predecessor_event_id") is not None and event.get("predecessor_event_id") not in set(event_ids) - {event.get("event_id")}:
            errors.append(f"{ARCH_JOURNAL_CHAIN}: event[{index}] predecessor id does not resolve")
    expected_genesis = _genesis_predecessor()
    if events and events[0].get("predecessor_event_sha256") != expected_genesis:
        errors.append(f"{ARCH_JOURNAL_CHAIN}: genesis predecessor digest mismatch")
    for index in range(1, len(events)):
        if events[index].get("predecessor_event_id") != events[index - 1].get("event_id"):
            errors.append(f"{ARCH_JOURNAL_CHAIN}: event[{index}] predecessor id not the previous event")
        if events[index].get("predecessor_event_sha256") != events[index - 1].get("event_sha256"):
            errors.append(f"{ARCH_JOURNAL_CHAIN}: event[{index}] predecessor digest mismatch")


def _check_lineage_bindings(subject: dict[str, Any], expected: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    commands = run.get("commands", [])
    events = run.get("events", [])
    event_command_ids = {event.get("command_id") for event in events}
    applied_command_ids = {response.get("command_id") for response in run.get("responses", []) if response.get("status") == "APPLIED"}
    command_ids = {command.get("command_id") for command in commands}
    for event in events:
        if event.get("command_id") not in command_ids:
            errors.append(f"{ARCH_LINEAGE_BINDING}: event references unknown command {event.get('command_id')}")
    for command in commands:
        command_type = command.get("command_type")
        if command.get("command_id") not in applied_command_ids:
            continue
        if command_type in SIDECAR_COMMANDS or command_type == "APPEND_STAGE1":
            continue
        if command.get("command_id") not in event_command_ids:
            errors.append(f"{ARCH_LINEAGE_BINDING}: applied command {command.get('command_id')} has no journal event")


def _check_stage_isolation(subject: dict[str, Any], expected: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    commands = run.get("commands", [])
    state = expected.get("state")
    for command in commands:
        command_type = command.get("command_type")
        if command_type in {"APPEND_STAGE2", "APPEND_STAGE3"} and state == "ABSTAINED":
            errors.append(f"{ARCH_DOWNSTREAM_BINDING}: {command_type} after abstention")


def _check_accessibility(subject: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    projection = run.get("accessibility_projection")
    if not isinstance(projection, dict):
        errors.append(f"{ARCH_ACCESSIBLE_ACTION}: accessibility projection missing")
        return
    validator = VALIDATORS.get("accessibility")
    if validator is not None:
        schema_error = _first_schema_error(validator, projection)
        if schema_error is not None:
            errors.append(f"{ARCH_SHAPE_INVALID}: accessibility projection {schema_error}")
    if projection.get("visual_only") is True:
        errors.append(f"{ARCH_ACCESSIBLE_NONVISUAL}: status must not be communicated visually only")
    if projection.get("claim_kind") != "SYNTHETIC_PROGRAMMATIC_SEMANTICS_ONLY":
        errors.append(f"{ARCH_CLAIM_CEILING}: accessibility claim_kind out of bounds")
    claims = projection.get("claims_not_established")
    expected_claims = ["WCAG_CONFORMANCE", "SCREEN_READER_PERFORMANCE", "REPRESENTATIVE_USABILITY", "ACCESSIBILITY_EFFECTIVENESS", "SATISFACTION", "ADOPTION"]
    if claims != expected_claims:
        errors.append(f"{ARCH_CLAIM_CEILING}: accessibility claims_not_established out of bounds")

    status = projection.get("status", {})
    required_status = ["primary_status_code", "primary_status_text", "reason_code", "reason_text", "evidence_reference_ids", "safe_next_actions", "retry_allowed", "focus_target", "announcement_intent"]
    for field in required_status:
        if field not in status:
            errors.append(f"{ARCH_ACCESSIBLE_STATUS}: status missing {field}")

    actions = projection.get("actions", [])
    action_ids = [action.get("action_id") for action in actions]
    if len(action_ids) != len(set(action_ids)):
        errors.append(f"{ARCH_ACCESSIBLE_ACTION}: duplicate action identifiers")
    for action in actions:
        for field in ("action_id", "name", "role", "state"):
            if not action.get(field):
                errors.append(f"{ARCH_ACCESSIBLE_ACTION}: action missing {field}")
        if not isinstance(action.get("focus_order"), int) or not isinstance(action.get("reading_order"), int):
            errors.append(f"{ARCH_ACCESSIBLE_ACTION}: action order fields must be integers")
    focus_order = projection.get("focus_order", [])
    reading_order = projection.get("reading_order", [])
    if len(focus_order) != len(set(focus_order)) or len(reading_order) != len(set(reading_order)):
        errors.append(f"{ARCH_ACCESSIBLE_STATUS}: focus/reading order must be acyclic and deterministic")
    run_result = subject.get("run", {}).get("result", {})
    result_kind = run_result.get("result") if isinstance(run_result, dict) else None
    if result_kind in {"ISSUE", "ABSTAIN_NO_VALID_TEN", "ERROR", "CONFLICT"}:
        if not status.get("focus_target") or not status.get("announcement_intent"):
            errors.append(f"{ARCH_ACCESSIBLE_STATUS}: {result_kind} requires deterministic focus target and announcement intent")
        if result_kind in {"ABSTAIN_NO_VALID_TEN", "ERROR", "CONFLICT"} and not status.get("reason_code"):
            errors.append(f"{ARCH_STATUS_DISCLOSURE}: {result_kind} reason must be disclosed")
    location_rows = projection.get("location_rows", [])
    for row in location_rows:
        for field in ("row_id", "label", "physical_location_id"):
            if not row.get(field):
                errors.append(f"{ARCH_ACCESSIBLE_STATUS}: location row missing {field}")
    if not projection.get("reading_order") and actions:
        errors.append(f"{ARCH_ACCESSIBLE_STATUS}: reading order must be nonempty when actions exist")


def _check_claim_ceiling(subject: dict[str, Any], frozen: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    contract = frozen["contract"]
    proof = run.get("proof", {})
    if proof.get("level") != 4:
        errors.append(f"{ARCH_CLAIM_CEILING}: proof level must be 4")
    for flag in ("real_usability_proven", "accessibility_performance_or_conformance_proven", "production_atomicity_or_reliability_proven", "security_proven", "real_route_feasibility_proven", "deployment_authorized", "incremental_lift_proven", "commercial_value_proven"):
        if proof.get(flag) is True:
            errors.append(f"{ARCH_CLAIM_CEILING}: proof flag {flag} must be false")
    if proof.get("live_issuance_authorized") is True:
        errors.append(f"{ARCH_LIVE_DENIAL}: live issuance must not be authorized")
    if proof.get("live_workflow_authorized") is True:
        errors.append(f"{ARCH_LIVE_DENIAL}: live workflow must not be authorized")
    owner = run.get("owner", {})
    if owner.get("real_world_authority") != "UNASSIGNED_EXTERNAL_AUTHORITY":
        errors.append(f"{ARCH_CLAIM_CEILING}: real-world authority must be unassigned")
    receipt = run.get("receipt", {})
    if contract is not None and receipt.get("claim_ceiling") != contract.get("claim_ceiling"):
        errors.append(f"{ARCH_CLAIM_CEILING}: receipt claim_ceiling must match the frozen contract")


def _check_receipt(subject: dict[str, Any], expected: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    receipt = run.get("receipt", {})
    expected_digests = {
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
        "accessibility_projection_sha256": digest_json(run.get("accessibility_projection", {})),
    }
    for field, wanted in expected_digests.items():
        if receipt.get(field) != wanted:
            errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: receipt {field} does not match reconstructed content")
    if receipt.get("final_state") != run.get("state"):
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: receipt final_state mismatch")
    if receipt.get("final_receipt_sha256") != _receipt_digest(receipt):
        errors.append(f"{ARCH_RECONSTRUCTION_MISMATCH}: final_receipt_sha256 does not match receipt content")


def _check_modules(subject: dict[str, Any], frozen: dict[str, Any], errors: list[str]) -> None:
    modules_registry = frozen["modules"]
    modules = subject.get("modules", [])
    roles = modules_registry.get("module_roles", [])
    seen_roles: list[str] = []
    for module in modules:
        role = module.get("role")
        if role not in roles:
            errors.append(f"{ARCH_MODULE_REGISTRY}: module role {role} not registered")
        if role in seen_roles:
            errors.append(f"{ARCH_MODULE_REGISTRY}: duplicate module for role {role}")
        seen_roles.append(role)
        if module.get("live_enabled") is not False:
            errors.append(f"{ARCH_LIVE_DENIAL}: module {module.get('module_id')} must be live-disabled")
        if module.get("interface_version") not in modules_registry.get("interface_versions", []):
            errors.append(f"{ARCH_MODULE_BINDING}: module {module.get('module_id')} unregistered interface version")
        if module.get("effect_class") not in modules_registry.get("effect_classes", []):
            errors.append(f"{ARCH_MODULE_BINDING}: module {module.get('module_id')} unregistered effect class")
    if set(seen_roles) != set(roles):
        missing = sorted(set(roles) - set(seen_roles))
        errors.append(f"{ARCH_MODULE_REGISTRY}: missing module role(s): {missing}")
    run = subject.get("run", {})
    bindings = run.get("schema_bindings", [])
    bound_paths = {binding.get("path") for binding in bindings}
    for name, path in SCHEMA_PATHS.items():
        rel = str(path.relative_to(ROOT))
        if rel not in bound_paths:
            errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: schema binding missing {rel}")
        else:
            binding = next(row for row in bindings if row.get("path") == rel)
            if binding.get("sha256") != digest_file(path):
                errors.append(f"{ARCH_MODULE_BINDING}: schema binding digest mismatch for {rel}")


def _check_manual_review(subject: dict[str, Any], frozen: dict[str, Any], errors: list[str]) -> None:
    review_records = subject.get("review_records", [])
    contract = frozen["contract"]
    allowed = set(contract.get("manual_review_contract", {}).get("allowed_actions", []))
    forbidden = set(contract.get("manual_review_contract", {}).get("forbidden_actions", []))
    seen: set[str] = set()
    previous_digest = _genesis_predecessor()
    for index, record in enumerate(review_records):
        if record.get("record_id") in seen:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] duplicate id")
        seen.add(record.get("record_id"))
        action = record.get("action")
        if action in forbidden:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] forbidden action {action}")
        elif action not in allowed:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] unregistered action {action}")
        if record.get("grants_real_authority") is not False:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] must not grant real authority")
        predecessor = record.get("predecessor")
        if predecessor is None:
            if record.get("review_sequence") != 1:
                errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] first record must have sequence 1")
        elif predecessor.get("sha256") != previous_digest:
            errors.append(f"{ARCH_MANUAL_BYPASS}: review record[{index}] predecessor digest mismatch")
        record_digest = digest_json(record)
        previous_digest = record_digest
    validator = VALIDATORS.get("review_record")
    if validator is not None:
        for index, record in enumerate(review_records):
            schema_error = _first_schema_error(validator, record)
            if schema_error is not None:
                errors.append(f"{ARCH_SHAPE_INVALID}: review record[{index}] {schema_error}")


def _check_versions(subject: dict[str, Any], frozen: dict[str, Any], errors: list[str]) -> None:
    contract = frozen["contract"]
    run = subject.get("run", {})
    if run.get("schema_version") != "1.0.0":
        errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: workflow run schema_version unregistered")
    if contract is not None and run.get("schema_version") and contract.get("schema_version") != "1.0.0":
        errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: contract schema_version unregistered")
    evaluator_id = subject.get("evaluator_id")
    if evaluator_id != "architecture-workflow-public-v1":
        errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: evaluator_id unregistered")
    for command in run.get("commands", []):
        if command.get("schema_version") != "1.0.0":
            errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: command schema_version unregistered")
        if contract is not None and command.get("contract_sha256") != digest_file(CONTRACT_PATH):
            errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: command contract_sha256 unregistered")


def _check_effects(run: dict[str, Any], errors: list[str]) -> None:
    effect_ledger = run.get("effect_ledger", [])
    for effect in effect_ledger:
        if effect.get("external_effect_occurred") is not False:
            errors.append(f"{ARCH_EXTERNAL_EFFECT}: external effect recorded")
        if effect.get("effect_kind") not in {"NONE", "HELD_OUTBOX_ONLY"}:
            errors.append(f"{ARCH_EXTERNAL_EFFECT}: unregistered effect kind")
    outbox = run.get("held_outbox", [])
    for entry in outbox:
        if entry.get("delivered_at") is not None:
            errors.append(f"{ARCH_LIVE_DENIAL}: outbox entry delivered")
    for entry in run.get("issuance_ledger", []):
        if entry.get("external_effect_occurred") is not False:
            errors.append(f"{ARCH_EXTERNAL_EFFECT}: issuance recorded an external effect")


def _check_duplicate_issuance(run: dict[str, Any], errors: list[str]) -> None:
    ledger = run.get("issuance_ledger", [])
    slots: list[str] = []
    keys: list[str] = []
    for entry in ledger:
        slot = entry.get("issuance_slot", {})
        slots.append(digest_json(slot))
        keys.append(entry.get("route_manifest_sha256"))
    if len(slots) != len(set(slots)):
        errors.append(f"{ARCH_ISSUANCE_SLOT_CONFLICT}: duplicate issuance slot committed")
    if len(keys) != len(set(keys)):
        errors.append(f"{ARCH_DUPLICATE_ISSUANCE}: duplicate issuance committed")


def _check_faults(subject: dict[str, Any], expected: dict[str, Any], errors: list[str]) -> None:
    schedule = subject.get("fault_schedule")
    if not isinstance(schedule, dict):
        return
    point = schedule.get("fault_point")
    if point not in FAULT_POINTS:
        errors.append(f"{ARCH_PARTIAL_FAILURE_AMBIGUOUS}: unknown fault point {point}")
        return
    run = subject.get("run", {})
    commands = run.get("commands", [])
    index = int(schedule.get("command_index", 0))
    retries = int(schedule.get("retries", 0))
    if not (0 <= index < len(commands)):
        errors.append(f"{ARCH_PARTIAL_FAILURE_AMBIGUOUS}: fault command_index out of range")
        return
    faulted_command_id = commands[index].get("command_id")
    event_command_ids = {event.get("command_id") for event in run.get("events", [])}
    idem_command_ids = {record.get("original_command_id") for record in run.get("idempotency_records", [])}
    applied = faulted_command_id in event_command_ids or faulted_command_id in idem_command_ids
    if point in PRECOMMIT_FAULT_POINTS:
        if retries == 0:
            if applied:
                errors.append(f"{ARCH_PARTIAL_FAILURE_AMBIGUOUS}: precommit fault with no retry must leave no partial state")
        else:
            if not applied:
                errors.append(f"{ARCH_PARTIAL_FAILURE_AMBIGUOUS}: precommit fault retry must reach the committed state")
    else:
        if run.get("aggregate_version") != expected["aggregate_version"]:
            errors.append(f"{ARCH_PARTIAL_FAILURE_AMBIGUOUS}: postcommit fault must reach the committed state")
        if not applied:
            errors.append(f"{ARCH_PARTIAL_FAILURE_AMBIGUOUS}: postcommit fault commit must be present")


def _check_authority(subject: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    authorizations = subject.get("authorizations", {})
    for command in run.get("commands", []):
        decision = authorizations.get(command.get("authorization_decision_sha256"))
        if not isinstance(decision, dict):
            continue
        if decision.get("decision") != "GRANTED":
            continue
        if decision.get("scope") != "SYNTHETIC_NON_INFLUENCING":
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} granted outside synthetic scope")
        if decision.get("capability") != command.get("requested_capability"):
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} capability escalation")
        granted_by = decision.get("granted_by")
        if granted_by is None:
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} authorization unattested")
        elif granted_by == command.get("principal_reference"):
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} authorization self-granted")


def _check_protection(subject: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    result = run.get("result", {})
    if not isinstance(result, dict) or result.get("result") != "ISSUE":
        return
    problem = subject.get("problem", {})
    candidates = {row.get("candidate_id"): row for row in problem.get("candidates", []) if isinstance(row, dict)}
    protected_tokens = set(problem.get("snapshot", {}).get("protected_tokens", []))
    for row in result.get("selected", []):
        candidate_id = row.get("candidate_id")
        source = candidates.get(candidate_id)
        if source is None:
            errors.append(f"{ARCH_PROTECTION_BYPASS}: selected unknown candidate {candidate_id}")
            continue
        if source.get("protected_status") != "CLEAR":
            errors.append(f"{ARCH_PROTECTION_BYPASS}: selected protected candidate {candidate_id}")
        if set(source.get("protection_tokens", [])) & protected_tokens:
            errors.append(f"{ARCH_PROTECTION_BYPASS}: selected candidate {candidate_id} carries a protected token")
        if source.get("evidence_stage") != 1:
            errors.append(f"{ARCH_PROTECTION_BYPASS}: selected candidate {candidate_id} is not Stage-1 evidence")
        if source.get("physical_location_id") != row.get("physical_location_id"):
            errors.append(f"{ARCH_PROTECTION_BYPASS}: selected location drifted for candidate {candidate_id}")


def _check_live_safety(subject: dict[str, Any], errors: list[str]) -> None:
    run = subject.get("run", {})
    if run.get("state") in RESERVED_LIVE_STATES:
        errors.append(f"{ARCH_LIVE_DENIAL}: final state {run.get('state')} is a reserved live state")
    for command in run.get("commands", []):
        if command.get("actor_class") == "REPRESENTATIVE":
            errors.append(f"{ARCH_LIVE_DENIAL}: live representative actor in a synthetic workflow")
    for response in run.get("responses", []):
        body = response.get("response", {})
        if body.get("announcement_intent") == "ASSERTIVE":
            errors.append(f"{ARCH_LIVE_DENIAL}: assertive announcement in a synthetic workflow")


def _check_independence(subject: dict[str, Any], errors: list[str]) -> None:
    references = subject.get("source_references", [])
    if references:
        for reference in references:
            if "cre_foundry." + "architecture" in str(reference.get("import", "")):
                errors.append(f"{ARCH_EVALUATOR_COUPLING}: subject references architecture implementation import")


def evaluate(subject: Any) -> list[str]:
    """Return a sorted list of stable ARCH-* diagnostics; empty means PASS."""
    errors: list[str] = []
    if not isinstance(subject, dict):
        return [f"{ARCH_SHAPE_INVALID}: subject must be an object"]
    if subject.get("subject_kind") != "ARCHITECTURE_WORKFLOW_SUBJECT":
        errors.append(f"{ARCH_SHAPE_INVALID}: subject_kind must be ARCHITECTURE_WORKFLOW_SUBJECT")
    if subject.get("schema_version") != "1.0.0":
        errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: subject schema_version unregistered")

    frozen = _frozen_artifacts(errors)
    run = subject.get("run")
    if not isinstance(run, dict):
        errors.append(f"{ARCH_SHAPE_INVALID}: run must be an object")
        return sorted(set(errors))

    workflow_validator = VALIDATORS.get("workflow_run")
    if workflow_validator is not None:
        schema_error = _first_schema_error(workflow_validator, run)
        if schema_error is not None:
            errors.append(f"{ARCH_SHAPE_INVALID}: workflow run {schema_error}")

    _check_versions(subject, frozen, errors)
    _check_independence(subject, errors)
    _check_modules(subject, frozen, errors)
    _check_authority(subject, errors)
    _check_live_safety(subject, errors)

    expected = _reconstruct(subject, frozen, errors)
    if expected is None:
        return sorted(set(errors))

    _compare_artifacts(run, expected, errors)
    _check_result_union_and_decisions(subject, expected, errors)
    _check_journal_lineage(run, errors)
    _check_lineage_bindings(subject, expected, errors)
    _check_stage_isolation(subject, expected, errors)
    _check_protection(subject, errors)
    _check_accessibility(subject, errors)
    _check_claim_ceiling(subject, frozen, errors)
    _check_receipt(subject, expected, errors)
    _check_effects(run, errors)
    _check_duplicate_issuance(run, errors)
    _check_faults(subject, expected, errors)
    _check_manual_review(subject, frozen, errors)
    return sorted(set(errors))


def evaluate_file(path: Path) -> tuple[list[str], dict[str, Any]]:
    """Strict-parse a subject file and evaluate it."""
    errors: list[str] = []
    subject = _load_strict_json(path, errors)
    if subject is None:
        return sorted(set(errors)), {"passed": False, "errors": sorted(set(errors)), "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    diagnostics = evaluate(subject)
    payload = {
        "passed": not diagnostics,
        "errors": diagnostics,
        "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return diagnostics, payload


def scan_source_independence(paths: list[Path]) -> list[str]:
    """Static scan for architecture implementation imports -> ARCH-EVALUATOR-COUPLING.

    Only actual import statements are flagged; prose and evaluator-internal
    registry checks that merely mention the package name are allowed.
    """
    errors: list[str] = []
    forbidden_tokens = ("cre_foundry." + "architecture", "cre_foundry/architecture")
    for path in paths:
        try:
            source = path.read_text()
        except OSError:
            continue
        for line_number, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("import ") and not stripped.startswith("from "):
                continue
            for token in forbidden_tokens:
                if token in line:
                    errors.append(f"{ARCH_EVALUATOR_COUPLING}: {path.name}:{line_number} references forbidden import {token}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE-001 independent workflow evaluator")
    parser.add_argument("--input", type=Path, required=True, help="subject document path")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    path = args.input if args.input.is_absolute() else ROOT / args.input
    try:
        diagnostics, payload = evaluate_file(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"passed": False, "errors": [f"{ARCH_SHAPE_INVALID}: {type(exc).__name__}: {exc}"], "fixture_sha256": ""}
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
