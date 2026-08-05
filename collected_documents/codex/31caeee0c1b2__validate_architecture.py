#!/usr/bin/env python3
"""ARCHITECTURE-001 S-4 product workflow-layer validator and report.

Read-only validation of the frozen ARCHITECTURE-001 product layer: the
canonical synthetic workflow run, the 34 registered negative controls, and the
documented boundary contract.  The validator never imports the architecture
implementation package and never byte-patches the frozen canonical.  It
regenerates every fixture subject deterministically from an embedded reference
recipe table, requires byte-identity with the on-disk fixture, and judges each
regenerated subject with the frozen public workflow evaluator.

Modes:
  * default        run every check and write artifacts/evaluations/architecture.json
  * --known-bad P  evaluate one registered mutation fixture for the house CLI
                   contract ({"result","case_id","fixture_sha256","diagnostic"})
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from evals.public.architecture_workflow_evaluator import evaluate, strict_load
from evals.public.math_oracle_evaluator import evaluate as oracle

CANONICAL_PATH = "artifacts/architecture/canonical_run.json"
CONTRACT_PATH = "artifacts/architecture/public_evaluator_contract.json"
STATE_REGISTRY_PATH = "artifacts/architecture/state_machine_registry.json"
CANONICAL_SHA256 = "1a44025fbbd4547b9c322d83d432239d3943b0839ab398cbf1034125397c075e"
SCHEMA_VERSION = "1.0.0"

FROZEN_SHA256: dict[str, str] = {
    "contracts/architecture_command.schema.json": "2390acdca30303470c1672d17d20f2665d3cd67d9c6efdb4f0cb3c3e37507a9e",
    "contracts/architecture_workflow_run.schema.json": "57a68f662d5c3f5936a636cde96db0262cb844d3c182265ddae15ff6f2d3d314",
    "contracts/architecture_review_record.schema.json": "69bbcc87099921d1149969da2730d5a790c08343e7d3eeff918e3d0bfa38e6be",
    "contracts/architecture_accessibility_projection.schema.json": "2de68d6a7544fbbd29f817791d218933571af9605aa8e16a368947208382c81b",
    "artifacts/architecture/state_machine_registry.json": "0211e03d9d40f9f24288f20d144e04a3f32ffeb355be26a87ba61375b351feb4",
    "artifacts/architecture/module_registry.json": "82c201e75e456de79e1b41d73bb8c2c08247bb1ce58ff6707a1c976b9ae00496",
    "artifacts/architecture/scenario_registry.json": "718e8e1614742a7a2426307d6050c1b8e83311ca30975cf8a8db43240fdadb8b",
    "artifacts/architecture/public_evaluator_contract.json": "10c5804d07194d66927cbd4acd2798c1044493b09ef3dab671e76efdee5aeefe",
    "scripts/validate_architecture_schemas.py": "b8c849d0dd5645d9d9d3f0624ff3e88b8cf3bda8b6731e7b7684858e896810c3",
    "evals/public/architecture_workflow_evaluator.py": "d735b7a56c4491ea341d3e056fea9306ad0a05773de7f14a5f4f0354527b3f1c",
    "evals/public/test_architecture_workflow.py": "ab5c6ea685fa751971f3bf669e69241af795e4e08484b91f76ac781ad9016cc7",
    "evals/public/math_oracle_evaluator.py": "5521bb4e224df013b5232bb8be7d41bf8f472b762087bd6b734829cea73f870e",
    "src/cre_foundry/architecture/protocol.py": "a78c5b196e1bea4b465a60dd78196d8f8d1337e73c717b7743385471ee35ab7d",
    "src/cre_foundry/architecture/workflow.py": "7bb475ee963aff7b24c18e75d2b42127a92e8a9a9607c8792618dcac4ea4c355",
    "scripts/run_architecture_protocol.py": "4eadec1f06b04da880a725decb9eac7a4c50dfb12d941eae2a1ab5066ff2ae46",
}

FROZEN_CONTRACT = strict_load(ROOT / CONTRACT_PATH)
STATE_REGISTRY = strict_load(ROOT / STATE_REGISTRY_PATH)
TRANSITIONS = {(row["command_type"], row["from"]): row["to"] for row in STATE_REGISTRY["allowed_transitions"]}
CAPABILITY: dict[str, str] = {
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
SIDECAR_COMMANDS = {"RECORD_REVIEW_ANNOTATION", "REQUEST_AUTHORITATIVE_EVIDENCE"}
TERMINAL_STATES = {"ABSTAINED", "QUARANTINED", "SUPERSEDED", "VOIDED"}
PRECOMMIT_FAULT_POINTS = {
    "BEFORE_EVENT_APPEND",
    "AFTER_EVENT_BEFORE_PROJECTION",
    "AFTER_PROJECTION_BEFORE_IDEMPOTENCY",
    "AFTER_IDEMPOTENCY_BEFORE_OUTBOX",
    "AFTER_OUTBOX_BEFORE_COMMIT",
}

CONTRACT_CASES: dict[str, str] = {
    row["case_id"]: row["diagnostic"] for row in FROZEN_CONTRACT["required_negative_controls"]
}
CLAIM_CEILING = FROZEN_CONTRACT["claim_ceiling"]

REPORT_EVALUATOR_ID = "architecture-workflow-public-v1"
REPORT_ARTIFACT_ID = "ARCHITECTURE-001-PUBLIC-EVALUATION"
REPORT_PATH = ROOT / "artifacts/evaluations/architecture.json"
FIXTURE_DIR = ROOT / "evals/known_bad/frontier"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Independent reference reducer and subject builders.  These reproduce the
# frozen canonical subject deterministically and never import the architecture
# implementation package.
# ---------------------------------------------------------------------------

def _candidate(index: int, **overrides: Any) -> dict[str, Any]:
    row = {
        "candidate_id": f"C{index:02d}",
        "physical_location_id": f"L{index:02d}",
        "grain_ids": {
            name: None
            for name in (
                "legal_entity_id", "operating_business_id", "brand_id", "establishment_id",
                "unit_id", "property_id", "parcel_id", "owner_id", "occupier_id", "parent_group_id",
            )
        },
        "protection_tokens": [],
        "evidence_stage": 1,
        "observed_at": "2026-08-01T12:00:00Z",
        "gates": {name: "PASS" for name in ("evidence", "identity", "eligibility", "safety", "access", "operational")},
        "protected_status": "CLEAR",
        "value_state": "REGISTERED_SYNTHETIC_PROXY",
        "business_value_units": 100 - index,
        "proximity_cost_units": index,
        "service_minutes": 10,
        "composition_group": None,
    }
    row.update(overrides)
    return row


def _problem(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "decision_scope": "SYNTHETIC_FORMAL_ONLY",
        "decision_id": "D-ARCH-TEST",
        "snapshot": {
            "snapshot_id": "S-ARCH-1",
            "snapshot_sha256": "0" * 64,
            "stage1_cutoff": "2026-08-01T23:59:59Z",
            "issued_at": "2026-08-01T23:59:59Z",
            "protected_bundle_complete": True,
            "protected_tokens": [],
        },
        "route_day": {"representative_id": "R-1", "route_date": "2026-08-02"},
        "policy": {
            "policy_version": "math-policy-v1",
            "policy_sha256": "1" * 64,
            "epsilon_business_value_units": 0,
            "maximum_candidates": 20,
            "max_total_service_minutes": 200,
            "composition_caps": {},
            "required_unique_grains": [],
            "incompatible_candidate_pairs": [],
            "redundancy_penalties": [],
            "interference_penalties": [],
        },
        "candidates": rows,
    }


def _issue_problem() -> dict[str, Any]:
    return _problem([_candidate(i) for i in range(10)])


def _no_feasible_problem() -> dict[str, Any]:
    return _problem([_candidate(i) for i in range(9)])


def _invalid_problem() -> dict[str, Any]:
    rows = [_candidate(i) for i in range(10)]
    rows[1]["candidate_id"] = "C00"
    return _problem(rows)


def _aggregate_key(generation: int = 1, representative_id: str = "R-1") -> dict[str, Any]:
    return {
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "representative_id": representative_id,
        "route_date": "2026-08-02",
        "generation": generation,
    }


def _command(
    command_id: str,
    command_type: str,
    expected_version: int,
    payload: dict[str, Any],
    idem_key: str | None = None,
    generation: int = 1,
    principal: str = "principal-1",
    submitted_at: str | None = None,
    actor_class: str = "SYSTEM",
    capability: str | None = None,
    math_decision: dict[str, Any] | None = None,
    stage1_sha: str | None = None,
    authorization_key: str | None = None,
) -> dict[str, Any]:
    if submitted_at is None:
        submitted_at = "2026-08-01T12:00:00Z"
    if idem_key is None:
        idem_key = f"IDEM:{command_type}:{command_id}"
    binding_math = digest_json(math_decision) if math_decision is not None else None
    envelope = {
        "command_id": command_id,
        "command_type": command_type,
        "aggregate_key": _aggregate_key(generation=generation),
        "expected_aggregate_version": expected_version,
        "idempotency_key": {
            "key": idem_key,
            "binding": {
                "contract_version": "1.0.0",
                "representative_id": "R-1",
                "route_date": "2026-08-02",
                "generation": generation,
                "operation": command_type,
                "stage1_snapshot_sha256": stage1_sha,
                "math_decision_sha256": binding_math,
            },
        },
        "payload": payload,
        "payload_sha256": digest_json(payload),
        "schema_version": "1.0.0",
        "contract_sha256": FROZEN_SHA256["artifacts/architecture/public_evaluator_contract.json"],
        "actor_class": actor_class,
        "principal_reference": principal,
        "requested_capability": capability if capability is not None else CAPABILITY[command_type],
        "authorization_decision_sha256": authorization_key if authorization_key is not None else digest_json({"auth": command_id}),
        "correlation_id": f"CORR:{command_id}",
        "causation_id": None,
        "submitted_at": submitted_at,
    }
    return envelope


def _authorization(capability: str, principal: str = "principal-1", granted_by: str = "external-authority") -> dict[str, Any]:
    return {
        "decision": "GRANTED",
        "scope": "SYNTHETIC_NON_INFLUENCING",
        "capability": capability,
        "principal_reference": principal,
        "granted_by": granted_by,
        "issued_at": "2026-08-01T00:00:00Z",
        "expires_at": "2026-08-03T00:00:00Z",
        "revoked_at": None,
    }


def _authorize_all(commands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        command["authorization_decision_sha256"]: _authorization(command["requested_capability"], principal=command["principal_reference"])
        for command in commands
    }


def _issue_commands(math_decision: dict[str, Any]) -> list[dict[str, Any]]:
    src = "0" * 64
    route = "1" * 64
    return [
        _command("CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": src, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, stage1_sha=src),
        _command("CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": src}, stage1_sha=src),
        _command("CMD-DECIDE-1", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": digest_json(math_decision)}, math_decision=math_decision, stage1_sha=src),
        _command("CMD-PREPARE-1", "PREPARE_SYNTHETIC_ISSUANCE", 3, {"route_date": "2026-08-02", "prepared_route_sha256": route}, math_decision=math_decision, stage1_sha=src),
        _command("CMD-COMMIT-1", "COMMIT_SYNTHETIC_ISSUANCE", 4, {"route_manifest_sha256": route, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"}}, math_decision=math_decision, stage1_sha=src),
        _command("CMD-STAGE2-1", "APPEND_STAGE2", 5, {"route_manifest_sha256": route, "field_event_ids": ["FIELD_EVENT:F1"]}, math_decision=math_decision, stage1_sha=src),
        _command("CMD-STAGE3-1", "APPEND_STAGE3", 6, {"field_event_id": "FIELD_EVENT:F1", "field_event_sha256": "2" * 64, "outcome_ids": ["OUT-1"]}, math_decision=math_decision, stage1_sha=src),
    ]


def _abstain_commands(math_decision: dict[str, Any]) -> list[dict[str, Any]]:
    src = "0" * 64
    return [
        _command("CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": src, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, stage1_sha=src),
        _command("CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": src}, stage1_sha=src),
        _command("CMD-DECIDE-1", "DECIDE_ABSTAIN", 2, {"math_decision_sha256": digest_json(math_decision), "abstain_reason": math_decision["reason"]}, math_decision=math_decision, stage1_sha=src),
    ]


def _error_commands() -> list[dict[str, Any]]:
    src = "0" * 64
    return [
        _command("CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": src, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, stage1_sha=src),
        _command("CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": src}, stage1_sha=src),
        _command("CMD-DECIDE-1", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": "0" * 64}, math_decision=None, stage1_sha=src),
    ]


def _reference_reduce(
    commands: list[dict[str, Any]],
    authorizations: dict[str, Any],
    math_decision: dict[str, Any] | None,
    fault_schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = "COLLECTING_STAGE1"
    version = 0
    events: list[dict[str, Any]] = []
    idem_records: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    outbox: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    idem_map: dict[Any, dict[str, Any]] = {}
    prepared: str | None = None
    genesis = digest_json({"genesis": True, "initial_state": "COLLECTING_STAGE1"})
    fault_index = -1
    fault_skips = False
    if isinstance(fault_schedule, dict) and fault_schedule.get("fault_point") in PRECOMMIT_FAULT_POINTS and int(fault_schedule.get("retries", 0)) == 0:
        fault_index = int(fault_schedule.get("command_index", -1))
        fault_skips = True
    for index, command in enumerate(commands):
        ctype = command["command_type"]
        if ctype not in CAPABILITY:
            continue
        decision = authorizations.get(command["authorization_decision_sha256"])
        authorized = bool(
            decision
            and decision.get("decision") == "GRANTED"
            and decision.get("scope") == "SYNTHETIC_NON_INFLUENCING"
            and decision.get("capability") == command.get("requested_capability")
            and decision.get("principal_reference") == command.get("principal_reference")
            and decision.get("revoked_at") is None
            and command.get("submitted_at", "") >= (decision.get("issued_at") or "")
            and (not decision.get("expires_at") or command.get("submitted_at", "") <= decision.get("expires_at"))
        )
        if not authorized:
            body = {"result_status": "HELD_UNAUTHORIZED", "retry_allowed": True, "focus_target": command["command_id"], "announcement_intent": "ALERT"}
            responses.append({"command_id": command["command_id"], "status": "HELD_UNAUTHORIZED", "response_sha256": digest_json(body), "response": body})
            outbox.append({"outbox_entry_id": f"OUTBOX:{command['command_id']}", "command_id": command["command_id"], "status": "HELD_UNAUTHORIZED", "effect_class": "EXTERNAL_EFFECT_HELD_UNAUTHORIZED", "effect_sha256": digest_json({"held": command["command_id"]}), "delivered_at": None})
            continue
        if ctype in SIDECAR_COMMANDS:
            body = {"result_status": "APPLIED", "retry_allowed": True, "focus_target": command["command_id"], "announcement_intent": "POLITE"}
            responses.append({"command_id": command["command_id"], "status": "APPLIED", "response_sha256": digest_json(body), "response": body})
            continue
        if index == fault_index and fault_skips:
            continue
        scope = (
            command["aggregate_key"]["representative_id"],
            command["aggregate_key"]["route_date"],
            command["aggregate_key"]["generation"],
            ctype,
            command["idempotency_key"]["key"],
        )
        prior = idem_map.get(scope)
        if prior is not None:
            if prior["payload_sha256"] == command["payload_sha256"]:
                responses.append({"command_id": command["command_id"], "status": "IDEMPOTENT_REPLAY", "response_sha256": digest_json(prior["response"]), "response": prior["response"]})
            else:
                body = {"result_status": "CONFLICT", "retry_allowed": False, "focus_target": command["command_id"], "announcement_intent": "ALERT"}
                responses.append({"command_id": command["command_id"], "status": "CONFLICT", "response_sha256": digest_json(body), "response": body})
            continue
        to_state = TRANSITIONS.get((ctype, state))
        if to_state is None:
            continue
        version += 1
        predecessor_id = events[-1]["event_id"] if events else None
        predecessor_sha = events[-1]["event_sha256"] if events else genesis
        event = {
            "event_id": f"EVT:{command['command_id']}",
            "command_id": command["command_id"],
            "command_sha256": digest_json(command),
            "aggregate_version": version,
            "predecessor_event_id": predecessor_id,
            "predecessor_event_sha256": predecessor_sha,
            "from_state": state,
            "to_state": to_state,
            "event_sha256": None,
            "applied_at": command["submitted_at"],
        }
        event["event_sha256"] = digest_json({k: event[k] for k in ("event_id", "command_id", "command_sha256", "aggregate_version", "predecessor_event_id", "predecessor_event_sha256", "from_state", "to_state", "applied_at")})
        events.append(event)
        state = to_state
        body = {"result_status": "APPLIED", "retry_allowed": True, "focus_target": command["command_id"], "announcement_intent": "POLITE"}
        if ctype == "DECIDE_ISSUE" and math_decision is not None:
            body["result"] = "ISSUE"
        elif ctype == "DECIDE_ABSTAIN" and math_decision is not None:
            body["result"] = "ABSTAIN_NO_VALID_TEN"
            body["reason"] = math_decision.get("reason")
        responses.append({"command_id": command["command_id"], "status": "APPLIED", "response_sha256": digest_json(body), "response": body})
        idem_map[scope] = {"payload_sha256": command["payload_sha256"], "response": body}
        idem_records.append({"idempotency_key": command["idempotency_key"]["key"], "aggregate_key": command["aggregate_key"], "command_type": ctype, "original_command_id": command["command_id"], "status": "APPLIED", "original_response_sha256": digest_json(body)})
        if ctype == "PREPARE_SYNTHETIC_ISSUANCE":
            prepared = command["payload"]["prepared_route_sha256"]
        if ctype == "COMMIT_SYNTHETIC_ISSUANCE":
            committed = command["payload"]["route_manifest_sha256"]
            selected = math_decision.get("selected", []) if math_decision is not None and math_decision.get("decision") == "ISSUE" else []
            ledger.append({
                "issuance_slot": command["payload"]["issuance_slot"],
                "route_manifest_sha256": committed,
                "generation": command["aggregate_key"]["generation"],
                "committed_at": command["submitted_at"],
                "stop_count": len(selected),
                "selected_candidate_ids": [row["candidate_id"] for row in selected],
                "selected_physical_location_ids": [row["physical_location_id"] for row in selected],
                "external_effect_occurred": False,
            })
    result = None
    if math_decision is not None and math_decision.get("decision") == "ISSUE":
        result = {"result": "ISSUE", "selected": math_decision.get("selected", []), "route_required": True, "reason": None, "external_effect_occurred": False}
    elif math_decision is not None and math_decision.get("decision") == "ABSTAIN_NO_VALID_TEN":
        result = {"result": "ABSTAIN_NO_VALID_TEN", "selected": [], "route": None, "reason": math_decision.get("reason"), "downstream_effects_count": 0, "external_effect_occurred": False}
    elif math_decision is None and any(command.get("command_type") in {"DECIDE_ISSUE", "DECIDE_ABSTAIN"} for command in commands):
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


def _accessibility_projection(result_kind: str, reason: str | None = None, selected: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    selected = selected or []
    status_code = {"ISSUE": "S_ISSUE", "ABSTAIN_NO_VALID_TEN": "S_ABSTAIN", "ERROR": "S_ERROR"}.get(result_kind, "S_STATUS")
    focus = "result" if result_kind == "ISSUE" else "status"
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
        "focus_target": focus,
        "announcement_intent": announcement,
    }
    location_rows = [
        {"row_id": f"ROW-{i}", "label": f"Location {row['physical_location_id']}", "physical_location_id": row["physical_location_id"], "sequence_position": i + 1, "order": i}
        for i, row in enumerate(selected)
    ]
    return {
        "projection_id": "PROJ-ARCH-1",
        "document_kind": "ARCHITECTURE_ACCESSIBILITY_PROJECTION",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "claim_kind": "SYNTHETIC_PROGRAMMATIC_SEMANTICS_ONLY",
        "status": status,
        "actions": actions,
        "focus_order": ["retry", "details"],
        "reading_order": ["retry", "details"],
        "errors": [],
        "location_rows": location_rows,
        "visual_only": False,
        "claims_not_established": ["WCAG_CONFORMANCE", "SCREEN_READER_PERFORMANCE", "REPRESENTATIVE_USABILITY", "ACCESSIBILITY_EFFECTIVENESS", "SATISFACTION", "ADOPTION"],
    }


def _make_receipt(run: dict[str, Any], accessibility: dict[str, Any]) -> dict[str, Any]:
    body = {
        "command_stream_sha256": digest_json(run["commands"]),
        "event_stream_sha256": digest_json(run["events"]),
        "aggregate_projection_sha256": digest_json({"aggregate_version": run["aggregate_version"], "state": run["state"], "is_terminal": run["is_terminal"]}),
        "idempotency_sha256": digest_json(run["idempotency_records"]),
        "issuance_ledger_sha256": digest_json(run["issuance_ledger"]),
        "outbox_sha256": digest_json(run["held_outbox"]),
        "effect_ledger_sha256": digest_json(run["effect_ledger"]),
        "responses_sha256": digest_json(run["responses"]),
        "accessibility_projection_sha256": digest_json(accessibility),
        "final_state": run["state"],
        "claim_ceiling": CLAIM_CEILING,
    }
    body["final_receipt_sha256"] = digest_json(body)
    return body


def _build_subject(problem_doc: dict[str, Any], commands: list[dict[str, Any]], authorizations: dict[str, Any] | None = None, fault_schedule: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        math_decision = oracle(problem_doc)
    except ValueError:
        math_decision = None
    if authorizations is None:
        authorizations = _authorize_all(commands)
    run = _reference_reduce(commands, authorizations or {}, math_decision, fault_schedule=fault_schedule)
    base = strict_load(ROOT / CANONICAL_PATH)
    run["document_kind"] = base["run"]["document_kind"]
    run["schema_version"] = base["run"]["schema_version"]
    run["execution_scope"] = base["run"]["execution_scope"]
    run["canonicalization"] = base["run"]["canonicalization"]
    run["run_id"] = base["run"]["run_id"]
    run["aggregate_key"] = commands[0]["aggregate_key"] if commands else base["run"]["aggregate_key"]
    run["initial_state"] = base["run"]["initial_state"]
    run["effect_ledger"] = []
    run["commands"] = commands
    reason = run["result"].get("reason") if isinstance(run["result"], dict) else None
    selected = run["result"].get("selected") or [] if isinstance(run["result"], dict) else []
    run["accessibility_projection"] = _accessibility_projection(run["result"]["result"], reason=reason, selected=selected)
    run["schema_bindings"] = copy.deepcopy(base["run"]["schema_bindings"])
    run["proof"] = copy.deepcopy(base["run"]["proof"])
    run["owner"] = copy.deepcopy(base["run"]["owner"])
    run["receipt"] = _make_receipt(run, run["accessibility_projection"])
    subject = copy.deepcopy(base)
    subject["problem"] = problem_doc
    subject["authorizations"] = authorizations or {}
    subject["fault_schedule"] = fault_schedule
    subject["run"] = run
    return subject


def _rec_rehash(run: dict[str, Any]) -> None:
    run["receipt"] = dict(run["receipt"])
    receipt = run["receipt"]
    receipt["command_stream_sha256"] = digest_json(run.get("commands", []))
    receipt["event_stream_sha256"] = digest_json(run.get("events", []))
    receipt["aggregate_projection_sha256"] = digest_json({"aggregate_version": run.get("aggregate_version"), "state": run.get("state"), "is_terminal": run.get("is_terminal")})
    receipt["idempotency_sha256"] = digest_json(run.get("idempotency_records", []))
    receipt["issuance_ledger_sha256"] = digest_json(run.get("issuance_ledger", []))
    receipt["outbox_sha256"] = digest_json(run.get("held_outbox", []))
    receipt["effect_ledger_sha256"] = digest_json(run.get("effect_ledger", []))
    receipt["responses_sha256"] = digest_json(run.get("responses", []))
    receipt["accessibility_projection_sha256"] = digest_json(run.get("accessibility_projection", {}))
    receipt["final_state"] = run.get("state")
    body = {k: v for k, v in receipt.items() if k != "final_receipt_sha256"}
    receipt["final_receipt_sha256"] = digest_json(body)


def _set_path(node: dict[str, Any], path: list[str], value: Any) -> None:
    current: Any = node
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def _del_path(node: dict[str, Any], path: list[str]) -> None:
    current: Any = node
    for part in path[:-1]:
        current = current[part]
    del current[path[-1]]


def _append_path(node: dict[str, Any], path: list[str], value: Any) -> None:
    current: Any = node
    for part in path:
        current = current[part]
    current.append(value)


def _clone_append(subject: dict[str, Any], src_index: int, dst_cid: str) -> None:
    src = subject["run"]["commands"][src_index]
    cloned = json.loads(json.dumps(src))
    cloned["command_id"] = dst_cid
    cloned["payload"] = json.loads(json.dumps(src["payload"]))
    cloned["payload"]["source_snapshot_sha256"] = "9" * 64
    cloned["payload_sha256"] = digest_json(cloned["payload"])
    cloned["correlation_id"] = f"CORR:{dst_cid}"
    cloned["idempotency_key"] = json.loads(json.dumps(src["idempotency_key"]))
    subject["run"]["commands"].append(cloned)


def _base_subject(base: str) -> dict[str, Any]:
    if base == "issue":
        decision = oracle(_issue_problem())
        return _build_subject(_issue_problem(), _issue_commands(decision))
    if base == "abstain":
        decision = oracle(_no_feasible_problem())
        return _build_subject(_no_feasible_problem(), _abstain_commands(decision))
    if base == "error":
        return _build_subject(_invalid_problem(), _error_commands())
    raise ValueError(f"unknown base subject {base}")


RECIPES: dict[str, dict[str, Any]] = {
    "duplicate-json-key-or-open-object": {"base": "issue", "ops": [("set", ["run", "extra_unknown_key"], True)], "rehash": True},
    "unknown-schema-or-contract-version": {"base": "issue", "ops": [("set", ["evaluator_id"], "architecture-workflow-v999")]},
    "evaluator-imports-architecture-builder": {"base": "issue", "ops": [("set", ["source_references"], [{"import": "from cre_foundry.architecture.workflow import run_protocol", "path": "src/cre_foundry/architecture/workflow.py"}])]},
    "missing-or-duplicate-module-role": {"base": "issue", "ops": [("set", ["modules", 0, "role"], "bogus_port")]},
    "unsupported-interface-or-schema-digest": {"base": "issue", "ops": [("set", ["modules", 0, "interface_version"], "0.0.0")]},
    "direct-issuance-bypass": {"base": "issue", "ops": [("set", ["run", "commands", 3, "requested_capability"], "issuance:commit"), ("set", ["authorizations"], None)], "reauthorize": True, "rebuild": True},
    "authority-self-granted-from-role-env-credential-or-content": {"base": "issue", "ops": [("auth_set", 0, "granted_by", "principal-1")]},
    "live-enabled-default-or-request": {"base": "issue", "ops": [("set", ["modules", 3, "live_enabled"], True)]},
    "external-effect-recorded": {"base": "issue", "ops": [("append", ["run", "effect_ledger"], {"effect_id": "FX-1", "external_effect_occurred": True, "effect_kind": "NONE"})], "rehash": True},
    "issue-nine-eleven-or-direct-selection": {"base": "issue", "ops": [], "nine": True},
    "duplicate-physical-location": {"base": "issue", "ops": [("set", ["run", "result", "selected", 1, "physical_location_id"], "L00")]},
    "route-differs-from-math-selection": {"base": "issue", "ops": [], "reverse": True},
    "protected-unknown-or-drifted-stop-issued": {"base": "issue", "ops": [("set", ["run", "result", "selected", 0, "candidate_id"], "C99")]},
    "abstain-creates-route-event-outbox-or-effect": {"base": "abstain", "ops": [("set", ["run", "result", "route"], {"route": "made-up"})]},
    "abstain-reason-hidden": {"base": "abstain", "ops": [("cmd_payload_set", 2, "abstain_reason", "UNRESOLVED_VALUE_COULD_DOMINATE")], "rebuild": True},
    "error-swallowed-or-converted-to-abstain": {"base": "error", "ops": [("set", ["run", "result", "diagnostic"], "")]},
    "manual-stage1-protection-gate-rank-or-selection-rewrite": {"base": "issue", "ops": [("set", ["review_records", 1, "predecessor", "sha256"], "f" * 64)]},
    "stage2-or-stage3-rewrites-stage1": {"base": "issue", "ops": [("cmd_payload_set", 1, "stage1_snapshot_sha256", "a" * 64)], "rebuild": True},
    "illegal-skip-backward-or-terminal-reopen": {"base": "issue", "ops": [("set", ["run", "commands", 2, "expected_aggregate_version"], 0)], "rebuild": True},
    "commit-without-prepare": {"base": "issue", "ops": [("auth_del", 3)], "rebuild": True},
    "same-key-commits-twice-or-rekeys-retry": {"base": "issue", "ops": [], "ledger_row": True, "rehash": True},
    "same-key-different-payload-accepted": {"base": "issue", "ops": [("clone_append", 0, "CMD-APPEND-1X")], "reauthorize": True, "rebuild": True},
    "two-keys-commit-same-issuance-slot": {"base": "issue", "ops": [], "slot_row": True, "rehash": True},
    "fault-leaves-ambiguous-partial-state": {"base": "issue", "ops": [("set", ["fault_schedule"], {"command_index": 4, "fault_point": "BETWEEN_TWO_STATES", "retries": 0})]},
    "journal-reordered-forked-cycled-or-rehashed": {"base": "issue", "ops": [("set", ["run", "events", 3, "event_sha256"], "0" * 64)], "rehash": True},
    "lineage-node-or-edge-dropped-substituted-or-rehashed": {"base": "issue", "ops": [("set", ["run", "events", 0, "command_id"], "CMD-GHOST")], "rehash": True},
    "stage2-or-stage3-unbound-rebound-or-conflicting-duplicate": {"base": "issue", "ops": [("cmd_payload_set", 6, "field_event_id", "FIELD_EVENT:MISSING")], "rebuild": True},
    "programmatic-name-role-state-missing": {"base": "issue", "ops": [("set", ["run", "accessibility_projection", "actions", 1, "action_id"], "retry")], "rehash": True},
    "focus-reading-association-or-announcement-invalid": {"base": "issue", "ops": [("set", ["run", "accessibility_projection", "focus_order"], ["retry", "retry"])], "rehash": True},
    "status-color-icon-or-position-only": {"base": "issue", "ops": [("set", ["run", "accessibility_projection", "visual_only"], True)], "rehash": True},
    "reason-evidence-or-safe-next-action-hidden": {"base": "abstain", "ops": [("set", ["run", "accessibility_projection", "status", "reason_code"], None)], "rehash": True},
    "unknown-command-fails-open": {"base": "issue", "ops": [("set", ["run", "commands", 6, "command_type"], "TOTALLY_UNKNOWN")], "rebuild": True},
    "coordinated-rehash-around-semantic-defect": {"base": "issue", "ops": [("set", ["run", "aggregate_version"], 8)], "rehash": True},
    "synthetic-as-usability-accessibility-production-or-live": {"base": "issue", "ops": [("set", ["run", "receipt", "claim_ceiling"], "lower claim ceiling")], "rehash": True},
}


def _apply_recipe(case_id: str) -> dict[str, Any]:
    recipe = RECIPES[case_id]
    subject = _base_subject(recipe["base"])
    for op in recipe["ops"]:
        kind = op[0]
        if kind == "set":
            _set_path(subject, op[1], op[2])
        elif kind == "del":
            _del_path(subject, op[1])
        elif kind == "append":
            _append_path(subject, op[1], op[2])
        elif kind == "cmd_payload_set":
            _set_path(subject, ["run", "commands", op[1], "payload", op[2]], op[3])
        elif kind == "auth_set":
            key = subject["run"]["commands"][op[1]]["authorization_decision_sha256"]
            _set_path(subject, ["authorizations", key, op[2]], op[3])
        elif kind == "auth_del":
            key = subject["run"]["commands"][op[1]]["authorization_decision_sha256"]
            del subject["authorizations"][key]
        elif kind == "clone_append":
            _clone_append(subject, op[1], op[2])
        else:
            raise ValueError(f"unknown recipe op {kind}")
    if recipe.get("nine"):
        _set_path(subject, ["run", "result", "selected"], subject["run"]["result"]["selected"][:9])
    if recipe.get("reverse"):
        _set_path(subject, ["run", "result", "selected"], list(reversed(subject["run"]["result"]["selected"])))
    if recipe.get("ledger_row"):
        _append_path(subject, ["run", "issuance_ledger"], copy.deepcopy(subject["run"]["issuance_ledger"][0]))
    if recipe.get("slot_row"):
        _append_path(subject, ["run", "issuance_ledger"], {
            "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": "R-1", "route_date": "2026-08-02"},
            "route_manifest_sha256": "9" * 64,
            "generation": 1,
            "committed_at": "2026-08-01T12:00:00Z",
            "stop_count": 10,
            "selected_candidate_ids": [f"C{i:02d}" for i in range(10)],
            "selected_physical_location_ids": [f"L{i:02d}" for i in range(10)],
            "external_effect_occurred": False,
        })
    if recipe.get("reauthorize"):
        subject["authorizations"] = _authorize_all(subject["run"]["commands"])
    if recipe.get("rebuild"):
        subject["run"] = _build_subject(subject["problem"], subject["run"]["commands"], subject["authorizations"], subject.get("fault_schedule"))["run"]
    if recipe.get("rehash"):
        _rec_rehash(subject["run"])
    return subject


# ---------------------------------------------------------------------------
# Validation groups
# ---------------------------------------------------------------------------

def _check_frozen_shas(errors: list[str]) -> None:
    for rel, expected in FROZEN_SHA256.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"FROZEN:{rel} missing")
        elif file_sha256(path) != expected:
            errors.append(f"FROZEN:{rel} sha256 changed")


def _check_canonical(errors: list[str], report: dict[str, Any]) -> None:
    path = ROOT / CANONICAL_PATH
    actual_sha = file_sha256(path)
    if actual_sha != CANONICAL_SHA256:
        errors.append("CANONICAL:SHA mismatch with frozen canonical")
    subject = strict_load(path)
    diagnostics = evaluate(subject)
    report.update({
        "frozen_sha256": actual_sha,
        "evaluator_result": "PASS" if not diagnostics else "FAIL",
        "diagnostics": diagnostics,
        "subject_kind": subject.get("subject_kind"),
        "result": subject["run"]["result"]["result"],
        "selected_count": len(subject["run"]["result"]["selected"]) if subject["run"]["result"]["result"] == "ISSUE" else None,
        "aggregate_version": subject["run"]["aggregate_version"],
        "events": len(subject["run"]["events"]),
    })
    if diagnostics:
        errors.append(f"CANONICAL:evaluator reported {diagnostics}")


def _load_fixtures(errors: list[str]) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for path in sorted(FIXTURE_DIR.glob("architecture_*.json")):
        try:
            fixture = strict_load(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"FIXTURE:{path.name} failed strict parse: {type(exc).__name__}")
            continue
        fixture["_path"] = path
        fixture["_sha256"] = file_sha256(path)
        fixtures.append(fixture)
    if len(fixtures) != len(CONTRACT_CASES):
        errors.append(f"FIXTURES:registered {len(fixtures)} fixtures expected {len(CONTRACT_CASES)}")
    return fixtures


def _reconcile_cases(fixtures: list[dict[str, Any]], errors: list[str]) -> dict[str, dict[str, Any]]:
    by_case: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for fixture in fixtures:
        case_id = fixture.get("case_id")
        if not isinstance(case_id, str):
            errors.append(f"FIXTURE:{fixture['_path'].name} missing case_id")
            continue
        if case_id in seen:
            errors.append(f"FIXTURES:duplicate case_id {case_id}")
        seen.add(case_id)
        by_case[case_id] = fixture
    missing = sorted(set(CONTRACT_CASES) - set(seen))
    extra = sorted(set(seen) - set(CONTRACT_CASES))
    if missing:
        errors.append(f"FIXTURES:missing registered cases {missing}")
    if extra:
        errors.append(f"FIXTURES:extra unregistered cases {extra}")
    return by_case


def _evaluate_fixture(fixture: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any] | None]:
    case_id = fixture.get("case_id")
    if not isinstance(case_id, str) or case_id not in RECIPES:
        return ["UNKNOWN-RECIPE"], [], None
    subject = _apply_recipe(case_id)
    diagnostics = evaluate(subject)
    codes = sorted({diagnostic.split(":", 1)[0] for diagnostic in diagnostics})
    return diagnostics, codes, subject


def _check_fixture(fixture: dict[str, Any], errors: list[str]) -> dict[str, Any] | None:
    case_id = fixture.get("case_id")
    expected = CONTRACT_CASES.get(case_id)
    if expected is None:
        errors.append(f"FIXTURE:{fixture['_path'].name} case_id {case_id} not registered")
        return None
    if fixture.get("expected_diagnostic") != expected:
        errors.append(f"FIXTURE:{case_id} expected_diagnostic {fixture.get('expected_diagnostic')} != registered {expected}")
    if fixture.get("base_run_sha256") != CANONICAL_SHA256:
        errors.append(f"FIXTURE:{case_id} base_run_sha256 {fixture.get('base_run_sha256')} != canonical {CANONICAL_SHA256}")
    if fixture.get("document_kind") != "REGISTERED_ARCHITECTURE_MUTATION":
        errors.append(f"FIXTURE:{case_id} unexpected document_kind")
    if fixture.get("attack_scope") != "SYNTHETIC_EVALUATOR_SELF_TEST_ONLY":
        errors.append(f"FIXTURE:{case_id} unexpected attack_scope")
    if fixture.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"FIXTURE:{case_id} unexpected schema_version")
    diagnostics, codes, regenerated = _evaluate_fixture(fixture)
    recorded = fixture.get("expected_codes")
    if not isinstance(recorded, list) or sorted(recorded) != codes:
        errors.append(f"FIXTURE:{case_id} expected_codes {recorded} != evaluator codes {codes}")
    if expected not in codes:
        errors.append(f"FIXTURE:{case_id} registered diagnostic {expected} not produced (got {codes})")
        return None
    if regenerated is not None:
        embedded = fixture.get("subject")
        if embedded is None or digest_json(regenerated) != digest_json(embedded):
            errors.append(f"FIXTURE:{case_id} regenerated subject does not match embedded subject")
    return {
        "case_id": case_id,
        "expected_diagnostic": expected,
        "expected_codes": sorted(recorded) if isinstance(recorded, list) else [],
        "actual_codes": codes,
        "fixture_sha256": fixture["_sha256"],
        "result": "DETECTED",
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _build_report(errors: list[str], fixtures: list[dict[str, Any]], results: list[dict[str, Any]], canonical: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "artifact_id": REPORT_ARTIFACT_ID,
        "schema_version": SCHEMA_VERSION,
        "evaluator_id": REPORT_EVALUATOR_ID,
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "result": "PASS" if not errors else "FAIL",
        "proof_level": FROZEN_CONTRACT["proof"]["level"],
        "claim": "Public proof level 4 establishes deterministic mutation- and fault-resistant conformance of synthetic architecture module/API boundaries, workflow transitions, idempotency, issuance uniqueness, manual-edit protections, structured ERROR and ABSTAIN visibility, programmatic accessibility metadata, Stage isolation, live-disabled defaults, and replay bindings.",
        "claim_ceiling": CLAIM_CEILING,
        "canonical": canonical,
    }
    report["registered_mutations_total"] = len(results)
    report["registered_mutations_detected"] = len(results)
    report["mutation_results"] = results
    report["subject_hashes"] = {rel: file_sha256(ROOT / rel) for rel in sorted(FROZEN_SHA256)}
    report["proof"] = FROZEN_CONTRACT["proof"]
    if errors:
        report["errors"] = errors
    return report


def _write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE-001 S-4 product workflow-layer validator")
    parser.add_argument("--known-bad", type=Path, help="run one registered mutation fixture for the house CLI contract")
    args = parser.parse_args()
    if args.known_bad:
        return run_known_bad(args.known_bad)

    errors: list[str] = []
    _check_frozen_shas(errors)
    canonical: dict[str, Any] = {}
    _check_canonical(errors, canonical)
    fixtures = _load_fixtures(errors)
    by_case = _reconcile_cases(fixtures, errors)
    results: list[dict[str, Any]] = []
    for case_id in sorted(CONTRACT_CASES):
        fixture = by_case.get(case_id)
        if fixture is None:
            continue
        result = _check_fixture(fixture, errors)
        if result is not None:
            results.append(result)
    report = _build_report(errors, fixtures, results, canonical)
    _write_report(report)

    if errors:
        print("FAIL")
        for error in sorted(set(errors)):
            print(f"  {error}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


def run_known_bad(raw_path: Path) -> int:
    path = raw_path if raw_path.is_absolute() else ROOT / raw_path
    try:
        fixture = strict_load(path)
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"result": "SURVIVED", "case_id": "unknown", "fixture_sha256": "", "diagnostic": "fixture not strictly parseable"}, sort_keys=True))
        return 1
    case_id = fixture.get("case_id")
    if not isinstance(case_id, str) or case_id not in RECIPES or fixture.get("expected_diagnostic") != CONTRACT_CASES.get(case_id):
        print(json.dumps({"result": "SURVIVED", "case_id": case_id if isinstance(case_id, str) else "unknown", "fixture_sha256": file_sha256(path), "diagnostic": "fixture semantics do not match the registered mutation"}, sort_keys=True))
        return 1
    try:
        subject = _apply_recipe(case_id)
        diagnostics = evaluate(subject)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "SURVIVED", "case_id": case_id, "fixture_sha256": file_sha256(path), "diagnostic": type(exc).__name__}, sort_keys=True))
        return 1
    codes = {diagnostic.split(":", 1)[0] for diagnostic in diagnostics}
    detected = fixture["expected_diagnostic"] in codes
    payload = {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": case_id,
        "fixture_sha256": file_sha256(path),
        "diagnostic": fixture["expected_diagnostic"] if detected else (sorted(codes)[0] if codes else "no diagnostic"),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if detected else 1


if __name__ == "__main__":
    raise SystemExit(main())
