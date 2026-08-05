"""CRE Foundry ARCHITECTURE-001 black-box protocol boundary.

This module is the versioned JSON command/response protocol layer of the
ARCHITECTURE-001 transactional modular monolith.  It owns the strict parse,
canonical serialization, command-envelope validation, registered schema and
contract digest checks, module-port resolution against the frozen module
registry, capability/authorization handling, and live-action denial.  It never
treats caller-supplied booleans, roles, environment, credentials, or content as
authority, and it fails closed with stable ARCH-* diagnostics.

The public evaluator is independent of this package: it never imports it, and
this package never imports the evaluator or any `evals/` module.  The MATH
decision is an external input consumed as data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

CONTRACT_PATH = ROOT / "artifacts/architecture/public_evaluator_contract.json"
STATE_REGISTRY_PATH = ROOT / "artifacts/architecture/state_machine_registry.json"
MODULE_REGISTRY_PATH = ROOT / "artifacts/architecture/module_registry.json"
SCENARIO_REGISTRY_PATH = ROOT / "artifacts/architecture/scenario_registry.json"

SCHEMA_PATHS: dict[str, Path] = {
    "architecture_command": ROOT / "contracts/architecture_command.schema.json",
    "architecture_workflow_run": ROOT / "contracts/architecture_workflow_run.schema.json",
    "architecture_review_record": ROOT / "contracts/architecture_review_record.schema.json",
    "architecture_accessibility_projection": ROOT / "contracts/architecture_accessibility_projection.schema.json",
}

EXECUTION_SCOPE = "SYNTHETIC_NON_INFLUENCING"
SCHEMA_VERSION = "1.0.0"
CANONICALIZATION = "SORTED_KEYS_INTEGER_JSON_V1"
EVALUATOR_ID = "architecture-workflow-public-v1"
INITIAL_STATE = "COLLECTING_STAGE1"
REPRESENTATIVE_ROUTE_DATE = "2026-08-02"
REPRESENTATIVE_ID = "R-1"
PRINCIPAL_REFERENCE = "principal-1"
AUTHORITY_REFERENCE = "external-authority"

CAPABILITY_BY_COMMAND: dict[str, str] = {
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

COMMAND_MODULE_ROLE: dict[str, str] = {
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
}

RESULT_STATUSES = frozenset({"APPLIED", "IDEMPOTENT_REPLAY", "REJECTED", "CONFLICT", "HELD_UNAUTHORIZED"})
SIDECAR_COMMANDS = frozenset({"RECORD_REVIEW_ANNOTATION", "REQUEST_AUTHORITATIVE_EVIDENCE"})
FAULT_POINTS = frozenset(
    {
        "BEFORE_EVENT_APPEND",
        "AFTER_EVENT_BEFORE_PROJECTION",
        "AFTER_PROJECTION_BEFORE_IDEMPOTENCY",
        "AFTER_IDEMPOTENCY_BEFORE_OUTBOX",
        "AFTER_OUTBOX_BEFORE_COMMIT",
        "AFTER_COMMIT_BEFORE_RESPONSE",
    }
)
PRECOMMIT_FAULT_POINTS = FAULT_POINTS - {"AFTER_COMMIT_BEFORE_RESPONSE"}

# Stable fail-closed diagnostics registered in the frozen scenario registry.
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

ALL_ARCH_CODES = frozenset(
    {
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
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_parse(text: str) -> Any:
    """Parse JSON rejecting duplicate keys at every object level."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def strict_load(path: Path) -> Any:
    return strict_parse(path.read_text())


class ProtocolError(RuntimeError):
    """A fail-closed protocol diagnostic raised by the boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class ProtocolContext:
    """Loads and owns the frozen contract, registries, and module map once.

    The context is read-only after construction and resolves module ports from
    the frozen module registry; it never fabricates authority or permits live
    actions.
    """

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.contract_path = root / "artifacts/architecture/public_evaluator_contract.json"
        self.state_registry_path = root / "artifacts/architecture/state_machine_registry.json"
        self.module_registry_path = root / "artifacts/architecture/module_registry.json"
        self.scenario_registry_path = root / "artifacts/architecture/scenario_registry.json"
        self.contract = strict_load(self.contract_path)
        self.state_registry = strict_load(self.state_registry_path)
        self.module_registry = strict_load(self.module_registry_path)
        self.scenario_registry = strict_load(self.scenario_registry_path)
        self.contract_sha256 = digest_file(self.contract_path)
        self.schema_shas = {name: digest_file(path) for name, path in SCHEMA_PATHS.items()}
        self.schema_bindings = [
            {
                "name": name,
                "path": str(path.relative_to(root)),
                "schema_version": SCHEMA_VERSION,
                "sha256": self.schema_shas[name],
            }
            for name, path in SCHEMA_PATHS.items()
        ]
        self._module_by_role: dict[str, dict[str, Any]] = {}
        for module in self.module_registry["modules"]:
            role = module["role"]
            if role in self._module_by_role:
                raise ProtocolError(ARCH_MODULE_REGISTRY, f"duplicate module role {role}")
            self._module_by_role[role] = module
        self._assert_registry_closure()

    def _assert_registry_closure(self) -> None:
        registered_roles = set(self.module_registry["module_roles"])
        if set(self._module_by_role) != registered_roles:
            missing = sorted(registered_roles - set(self._module_by_role))
            raise ProtocolError(ARCH_MODULE_REGISTRY, f"missing module role(s): {missing}")
        interface_versions = set(self.module_registry["interface_versions"])
        effect_classes = set(self.module_registry["effect_classes"])
        for module in self._module_by_role.values():
            if module["interface_version"] not in interface_versions:
                raise ProtocolError(ARCH_MODULE_BINDING, f"unregistered interface version {module['interface_version']}")
            if module["effect_class"] not in effect_classes:
                raise ProtocolError(ARCH_MODULE_BINDING, f"unregistered effect class {module['effect_class']}")
            if module["live_enabled"] is not False:
                raise ProtocolError(ARCH_LIVE_DENIAL, f"module {module['module_id']} must be live-disabled")

    def module_for_role(self, role: str) -> dict[str, Any]:
        module = self._module_by_role.get(role)
        if module is None:
            raise ProtocolError(ARCH_MODULE_REGISTRY, f"unregistered module role {role}")
        return module

    def module_for_command(self, command_type: str) -> dict[str, Any]:
        role = COMMAND_MODULE_ROLE.get(command_type)
        if role is None:
            raise ProtocolError(ARCH_UNKNOWN_COMMAND, f"unregistered command type {command_type}")
        return self.module_for_role(role)

    def command_digest(self, command: dict[str, Any]) -> str:
        return digest_json(command)

    def payload_digest(self, payload: Any) -> str:
        return digest_json(payload)


def authorization_is_current(decision: Any, command: dict[str, Any]) -> bool:
    """Mirror the frozen contract authority check.

    Only an externally attested, in-scope, capability-matched, unrevoked,
    time-valid GRANTED decision authorizes a command.  Caller-supplied booleans,
    roles, environment, credentials, or content never grant authority.
    """
    if not isinstance(decision, dict):
        return False
    if decision.get("decision") != "GRANTED":
        return False
    if decision.get("scope") != EXECUTION_SCOPE:
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


def check_authority_decisions(commands: list[dict[str, Any]], authorizations: dict[str, Any]) -> list[str]:
    """Verify every granted authorization is inside the synthetic scope and attested.

    Returns a list of stable ARCH-* diagnostics; empty means the authority layer
    is clean.  Self-granted, unattested, or out-of-scope grants are escalations.
    """
    errors: list[str] = []
    for command in commands:
        decision = authorizations.get(command.get("authorization_decision_sha256"))
        if not isinstance(decision, dict):
            continue
        if decision.get("decision") != "GRANTED":
            continue
        if decision.get("scope") != EXECUTION_SCOPE:
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} granted outside synthetic scope")
        if decision.get("capability") != command.get("requested_capability"):
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} capability escalation")
        granted_by = decision.get("granted_by")
        if granted_by is None:
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} authorization unattested")
        elif granted_by == command.get("principal_reference"):
            errors.append(f"{ARCH_AUTHORITY_ESCALATION}: command {command.get('command_id')} authorization self-granted")
    return errors


def validate_command_envelope(context: ProtocolContext, command: dict[str, Any], index: int) -> list[str]:
    """Fail-closed envelope checks for one command.

    Verifies schema version, frozen contract digest, command-type capability
    binding, payload digest integrity, and a registered command type.  Returns
    stable ARCH-* diagnostics; empty means the envelope is acceptable.
    """
    errors: list[str] = []
    if not isinstance(command, dict):
        return [f"{ARCH_SHAPE_INVALID}: command[{index}] must be an object"]
    command_type = command.get("command_type")
    if command.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: command[{index}] schema_version unregistered")
    if command.get("contract_sha256") != context.contract_sha256:
        errors.append(f"{ARCH_SCHEMA_UNREGISTERED}: command[{index}] contract_sha256 unregistered")
    if command_type not in CAPABILITY_BY_COMMAND:
        errors.append(f"{ARCH_UNKNOWN_COMMAND}: command[{index}] {command_type}")
        return errors
    capability = CAPABILITY_BY_COMMAND[command_type]
    if command.get("requested_capability") != capability:
        errors.append(f"{ARCH_POLICY_BYPASS}: command[{index}] {command_type} capability mismatch")
    payload = command.get("payload")
    if command.get("payload_sha256") != digest_json(payload):
        errors.append(f"{ARCH_SHAPE_INVALID}: command[{index}] payload_sha256 does not match payload content")
    return errors


def live_denial(context: ProtocolContext, request: str) -> None:
    """Fail closed: no live action, external write, or deployment is permitted."""
    if context.module_registry.get("module_contract", {}).get("live_enabled") is not False:
        raise ProtocolError(ARCH_LIVE_DENIAL, f"live_enabled must be false ({request})")
    if context.contract.get("proof", {}).get("live_workflow_authorized") is True:
        raise ProtocolError(ARCH_LIVE_DENIAL, f"live workflow must not be authorized ({request})")
    if context.contract.get("proof", {}).get("deployment_authorized") is True:
        raise ProtocolError(ARCH_LIVE_DENIAL, f"deployment must not be authorized ({request})")
