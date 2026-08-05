"""Read-only ARCHITECTURE-001 S-1 schema and registry closure checker.

Verifies the four public schemas and the three registries are recursively
closed, strictly parsed, and exactly cover the frozen evaluator contract at
artifacts/architecture/public_evaluator_contract.json. Never imports or trusts
any application builder. Prints PASS or FAIL; supports the house --known-bad
CLI contract (JSON payload) for the four S-1 registered diagnostics:
ARCH-SHAPE-INVALID, ARCH-SCHEMA-UNREGISTERED, ARCH-MODULE-REGISTRY,
ARCH-MODULE-BINDING.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_FILES: dict[str, str] = {
    "command": "contracts/architecture_command.schema.json",
    "workflow_run": "contracts/architecture_workflow_run.schema.json",
    "review_record": "contracts/architecture_review_record.schema.json",
    "accessibility": "contracts/architecture_accessibility_projection.schema.json",
}
REGISTRY_FILES: dict[str, str] = {
    "state_machine": "artifacts/architecture/state_machine_registry.json",
    "module": "artifacts/architecture/module_registry.json",
    "scenario": "artifacts/architecture/scenario_registry.json",
}
CONTRACT_PATH = "artifacts/architecture/public_evaluator_contract.json"
MATH_DECISION_SCHEMA = "contracts/math_route_decision.schema.json"

DIAG_SHAPE = "ARCH-SHAPE-INVALID"
DIAG_SCHEMA_UNREGISTERED = "ARCH-SCHEMA-UNREGISTERED"
DIAG_MODULE_REGISTRY = "ARCH-MODULE-REGISTRY"
DIAG_MODULE_BINDING = "ARCH-MODULE-BINDING"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(path: Path) -> Any:
    """Load JSON rejecting duplicate keys and open/shape-invalid documents."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def _walk_closure(node: Any, where: str, errors: list[str]) -> None:
    """Recursively require additionalProperties:false wherever an object is defined."""
    if isinstance(node, bool):
        return
    if not isinstance(node, dict):
        return
    if "properties" in node or "patternProperties" in node or node.get("type") == "object":
        if node.get("additionalProperties") is not False:
            errors.append(f"{DIAG_SHAPE}: {where} defines an object without additionalProperties:false")
    for key in ("items", "contains", "additionalProperties", "not", "if", "then", "else", "propertyNames", "unevaluatedItems", "unevaluatedProperties", "prefixItems"):
        child = node.get(key)
        if isinstance(child, (dict, list)):
            _walk_closure(child, f"{where}/{key}", errors)
    for key in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
        mapping = node.get(key)
        if isinstance(mapping, dict):
            for name, child in mapping.items():
                _walk_closure(child, f"{where}/{key}/{name}", errors)
    for key in ("allOf", "anyOf", "oneOf"):
        group = node.get(key)
        if isinstance(group, list):
            for index, child in enumerate(group):
                _walk_closure(child, f"{where}/{key}/{index}", errors)


def _check_schema_object(schema: dict[str, Any], rel: str, errors: list[str]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - any validator rejection is a schema validity failure
        errors.append(f"{DIAG_SHAPE}: {rel} is not a valid JSON Schema: {exc}")
    _walk_closure(schema, rel, errors)


def _load_schema(rel: str, errors: list[str]) -> dict[str, Any]:
    path = ROOT / rel
    try:
        return strict_load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{DIAG_SHAPE}: {rel} failed strict parse: {type(exc).__name__}")
        return {}


def _load_json(rel: str, errors: list[str]) -> dict[str, Any]:
    path = ROOT / rel
    try:
        return strict_load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{DIAG_SHAPE}: {rel} failed strict parse: {type(exc).__name__}")
        return {}


def _sets_equal(name: str, actual: list[str], expected: list[str], errors: list[str]) -> None:
    if sorted(set(actual)) != sorted(set(expected)):
        errors.append(f"ARCH-COVERAGE:{name} registered {sorted(set(actual))} expected {sorted(set(expected))}")


def _transition_command(row: dict[str, Any]) -> str:
    return row.get("command_type") or row["command"]


def _transitions_key(transitions: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return sorted((_transition_command(row), row["from"], row["to"]) for row in transitions)


def check_state_machine(reg: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    sm = contract["state_machine"]
    reachable = [row["state"] for row in reg["states"] if row["kind"] == "REACHABLE"]
    reserved = [row["state"] for row in reg["states"] if row["kind"] == "RESERVED_LIVE"]
    _sets_equal("STATES", reachable, sm["states"], errors)
    _sets_equal("RESERVED_LIVE_STATES", reserved, sm["reserved_live_states_unreachable"], errors)
    _sets_equal("TERMINAL_STATES", reg["terminal_for_generation"], sm["terminal_for_generation"], errors)
    _sets_equal("RESERVED_FIELD", reg["reserved_live_states"], sm["reserved_live_states_unreachable"], errors)
    if _transitions_key(reg["allowed_transitions"]) != _transitions_key(sm["allowed_transitions"]):
        errors.append("ARCH-COVERAGE:TRANSITIONS registered allowed_transitions differ from frozen contract")
    command_types = {_transition_command(row) for row in sm["allowed_transitions"]}
    sidecar = sm["sidecar_commands_no_aggregate_state_change"]
    registered_commands = {row["command_type"] for row in reg["commands"]}
    if registered_commands != command_types | set(sidecar):
        errors.append("ARCH-COVERAGE:COMMANDS registered commands differ from frozen command set")
    _sets_equal("SIDECAR_COMMANDS", reg["sidecar_commands"], sidecar, errors)
    _sets_equal("RESULT_STATUSES", reg["result_statuses"], contract["command_envelope"]["result_statuses"], errors)
    if reg["unknown_command_behavior"] != contract["command_envelope"]["unknown_command_behavior"]:
        errors.append("ARCH-COVERAGE:UNKNOWN_COMMAND_BEHAVIOR differs from frozen contract")
    if reg["initial_state"] not in reachable:
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: initial_state {reg['initial_state']} is not a registered reachable state")
    known_states = set(reachable)
    for transition in reg["allowed_transitions"]:
        if transition["from"] not in known_states or transition["to"] not in known_states:
            errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: transition endpoint unregistered: {transition}")
        if transition["command_type"] not in registered_commands:
            errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: transition uses unregistered command {transition['command_type']}")
    for state in reachable:
        row = next(item for item in reg["states"] if item["state"] == state)
        expected_terminal = state in set(sm["terminal_for_generation"])
        if row["terminal_for_generation"] != expected_terminal:
            errors.append(f"ARCH-COVERAGE:TERMINAL_CLASSIFICATION {state} registered {row['terminal_for_generation']} expected {expected_terminal}")
    for state in reserved:
        row = next(item for item in reg["states"] if item["state"] == state)
        if row["terminal_for_generation"] is not False:
            errors.append(f"ARCH-COVERAGE:RESERVED_TERMINAL reserved live state {state} must not be terminal")
    if set(reachable) & set(reserved):
        errors.append("ARCH-COVERAGE:STATE_OVERLAP reachable and reserved states overlap")
    review = reg["manual_review"]
    mc = contract["manual_review_contract"]
    _sets_equal("MANUAL_ALLOWED_ACTIONS", review["allowed_actions"], mc["allowed_actions"], errors)
    _sets_equal("MANUAL_FORBIDDEN_ACTIONS", review["forbidden_actions"], mc["forbidden_actions"], errors)
    if review["storage"] != mc["storage"] or review["synthetic_reviewer_role_grants_real_authority"] is not False:
        errors.append("ARCH-COVERAGE:MANUAL_REVIEW_CONTRACT differs from frozen contract")
    idem = contract["idempotency_and_atomicity"]
    if reg["idempotency"]["retry_number_participates_in_key"] is not False:
        errors.append("ARCH-COVERAGE:IDEMPOTENCY_RETRY_KEY differs from frozen contract")
    if reg["idempotency"]["fault_points"] != idem["fault_points"]:
        errors.append("ARCH-COVERAGE:FAULT_POINTS differ from frozen contract")
    if reg["idempotency"]["ambiguous_partial_state_allowed"] is not False:
        errors.append("ARCH-COVERAGE:AMBIGUOUS_PARTIAL_STATE differs from frozen contract")
    si = contract["stage_isolation"]
    if reg["stage_isolation"]["stage1_frozen_digest_immutable"] is not True:
        errors.append("ARCH-COVERAGE:STAGE1_IMMUTABLE differs from frozen contract")
    if reg["stage_isolation"]["stage2_or_stage3_can_rewrite_stage1"] is not False:
        errors.append("ARCH-COVERAGE:STAGE1_REWRITE differs from frozen contract")


def check_module_registry(reg: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    sa = contract["selected_architecture"]
    _sets_equal("MODULE_ROLES", reg["module_roles"], sa["module_roles"], errors)
    required_fields = sa["module_contract"]["required_fields"]
    if reg["module_contract"]["required_fields"] != required_fields:
        errors.append("ARCH-COVERAGE:MODULE_CONTRACT_REQUIRED_FIELDS differ from frozen contract")
    if reg["module_contract"]["exactly_one_module_per_role"] is not True or reg["module_contract"]["live_enabled"] is not False:
        errors.append("ARCH-COVERAGE:MODULE_CONTRACT differs from frozen contract")
    modules = reg["modules"]
    if len(modules) != len(sa["module_roles"]):
        errors.append(f"{DIAG_MODULE_REGISTRY}: expected one module per role ({len(sa['module_roles'])}) but registered {len(modules)}")
    roles_seen: list[str] = []
    for module in modules:
        if set(module) != set(required_fields):
            errors.append(f"{DIAG_MODULE_REGISTRY}: module {module.get('module_id')} fields differ from required fields")
        role = module.get("role")
        if role not in reg["module_roles"]:
            errors.append(f"{DIAG_MODULE_REGISTRY}: module role {role} is not a registered module role")
        if role in roles_seen:
            errors.append(f"{DIAG_MODULE_REGISTRY}: duplicate module for role {role}")
        roles_seen.append(role)
        if module.get("live_enabled") is not False:
            errors.append(f"{DIAG_MODULE_REGISTRY}: module {module.get('module_id')} must have live_enabled false")
        if module.get("interface_version") not in reg["interface_versions"]:
            errors.append(f"{DIAG_MODULE_BINDING}: module {module.get('module_id')} uses unregistered interface version {module.get('interface_version')}")
        if module.get("effect_class") not in reg["effect_classes"]:
            errors.append(f"{DIAG_MODULE_BINDING}: module {module.get('module_id')} uses unregistered effect_class {module.get('effect_class')}")
        if module.get("idempotency_mode") not in reg["idempotency_modes"]:
            errors.append(f"{DIAG_MODULE_BINDING}: module {module.get('module_id')} uses unregistered idempotency_mode {module.get('idempotency_mode')}")
    if set(roles_seen) != set(reg["module_roles"]):
        missing = sorted(set(reg["module_roles"]) - set(roles_seen))
        errors.append(f"{DIAG_MODULE_REGISTRY}: missing module role(s): {missing}")
    expected_impl_sha = digest_json(reg["module_contract"])
    for module in modules:
        if module.get("implementation_sha256") != expected_impl_sha:
            errors.append(f"{DIAG_MODULE_BINDING}: module {module.get('module_id')} implementation binding does not match module_contract digest")
    bindings = reg["interface_schema_bindings"]
    if set(bindings) != set(reg["module_roles"]):
        errors.append(f"{DIAG_MODULE_BINDING}: interface_schema_bindings must cover every module role exactly once")
    for module in sorted(modules, key=lambda row: row["role"]):
        role = module["role"]
        binding = bindings.get(role)
        if binding is None:
            errors.append(f"{DIAG_MODULE_BINDING}: module {role} has no interface_schema_binding")
            continue
        if module["input_schema_sha256"] != binding["input"]["sha256"] or module["output_schema_sha256"] != binding["output"]["sha256"]:
            errors.append(f"{DIAG_MODULE_BINDING}: module {role} schema digests differ from interface_schema_bindings")
        for direction in ("input", "output"):
            rel = binding[direction]["path"]
            if not (ROOT / rel).is_file():
                errors.append(f"{DIAG_MODULE_BINDING}: {role} {direction} schema path missing: {rel}")
                continue
            if file_sha256(ROOT / rel) != binding[direction]["sha256"]:
                errors.append(f"{DIAG_MODULE_BINDING}: {role} {direction} schema digest mismatch for {rel}")


def check_scenario_registry(reg: dict[str, Any], contract: dict[str, Any], math_schema: dict[str, Any], errors: list[str]) -> None:
    expected_diag = {row["case_id"]: row["diagnostic"] for row in contract["required_negative_controls"]}
    registered_diag = {row["case_id"]: row["diagnostic"] for row in reg["registered_diagnostics"]}
    if registered_diag != expected_diag:
        missing = sorted(set(expected_diag) - set(registered_diag))
        extra = sorted(set(registered_diag) - set(expected_diag))
        mismatch = sorted({case for case in set(expected_diag) & set(registered_diag) if expected_diag[case] != registered_diag[case]})
        errors.append(f"ARCH-COVERAGE:DIAGNOSTICS missing={missing} extra={extra} mismatch={mismatch}")
    reasons = [row["reason"] for row in reg["abstention_reasons"]]
    math_reasons = math_schema["oneOf"][1]["properties"]["reason"]["enum"]
    _sets_equal("ABSTENTION_REASONS", reasons, math_reasons, errors)
    versions = reg["supported_versions"]
    if versions["schema_version"] != ["1.0.0"] or versions["evaluator_contract_version"] != [contract["evaluator_id"]]:
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: supported versions do not match the frozen contract")
    if versions["interface_version"] != ["1.0.0"]:
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: supported interface versions must be registered")
    if versions["math_oracle_version"] != [math_schema["oneOf"][0]["properties"]["oracle_version"]["const"]]:
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: registered math oracle version does not match the pinned decision schema")


def check_schema_registry_consistency(
    schemas: dict[str, dict[str, Any]],
    regs: dict[str, dict[str, Any]],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    command = schemas["command"]
    if command.get("required") != contract["command_envelope"]["required_fields"]:
        errors.append("ARCH-COVERAGE:COMMAND_ENVELOPE_FIELDS differ from frozen contract")
    command_types = {row["command_type"] for row in regs["state_machine"]["commands"]}
    schema_command_types = set(command["$defs"]["command_type"]["enum"])
    if schema_command_types != command_types:
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: command schema command_type enum differs from registered commands")
    reasons = [row["reason"] for row in regs["scenario"]["abstention_reasons"]]
    if set(command["$defs"]["payload_decide_abstain"]["properties"]["abstain_reason"]["enum"]) != set(reasons):
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: command schema abstain reasons differ from registered reasons")
    workflow = schemas["workflow_run"]
    reachable = [row["state"] for row in regs["state_machine"]["states"] if row["kind"] == "REACHABLE"]
    if set(workflow["$defs"]["state"]["enum"]) != set(reachable):
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: workflow_run state enum differs from registered reachable states")
    if not isinstance(workflow.get("$defs", {}).get("result", {}).get("oneOf"), list) or len(workflow["$defs"]["result"]["oneOf"]) != 3:
        errors.append("ARCH-COVERAGE:RESULT_UNION must have exactly three branches")
    review = schemas["review_record"]
    allowed = regs["state_machine"]["manual_review"]["allowed_actions"]
    if set(review["$defs"]["allowed_action"]["enum"]) != set(allowed):
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: review action enum differs from registered manual review allowed actions")
    forbidden = regs["state_machine"]["manual_review"]["forbidden_actions"]
    if set(review["$defs"]["forbidden_action"]["enum"]) != set(forbidden):
        errors.append(f"{DIAG_SCHEMA_UNREGISTERED}: review forbidden_action enum differs from registered forbidden actions")
    accessibility = schemas["accessibility"]
    if accessibility.get("properties", {}).get("status", {}).get("$ref") != "#/$defs/status":
        errors.append("ARCH-COVERAGE:ACCESSIBILITY_STATUS_REF unexpected")
    status_required = accessibility["$defs"]["status"]["required"]
    if status_required != contract["programmatic_accessibility_contract"]["required_status_fields"]:
        errors.append("ARCH-COVERAGE:ACCESSIBILITY_STATUS_FIELDS differ from frozen contract")
    if accessibility.get("properties", {}).get("claims_not_established", {}).get("const") != contract["programmatic_accessibility_contract"]["claims_not_established"]:
        errors.append("ARCH-COVERAGE:ACCESSIBILITY_CLAIMS_CEILING differs from frozen contract")


def check_bindings(regs: dict[str, dict[str, Any]], errors: list[str]) -> None:
    for name in ("state_machine", "scenario"):
        binding = regs[name].get("contract_binding")
        if not isinstance(binding, dict) or binding.get("path") != CONTRACT_PATH:
            errors.append(f"ARCH-COVERAGE:CONTRACT_BINDING {name} path differs")
            continue
        if file_sha256(ROOT / CONTRACT_PATH) != binding.get("sha256"):
            errors.append(f"{DIAG_MODULE_BINDING}: {name} contract_binding sha256 mismatch")
    reason_source = regs["scenario"].get("math_decision_reason_source")
    if not isinstance(reason_source, dict) or reason_source.get("path") != MATH_DECISION_SCHEMA:
        errors.append("ARCH-COVERAGE:MATH_REASON_SOURCE path differs")
    elif file_sha256(ROOT / MATH_DECISION_SCHEMA) != reason_source.get("sha256"):
        errors.append(f"{DIAG_MODULE_BINDING}: scenario math_decision_reason_source sha256 mismatch")


def validate(load: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schemas = load["schemas"]
    regs = load["registries"]
    contract = load["contract"]
    math_schema = load["math_schema"]

    for name, rel in SCHEMA_FILES.items():
        if not schemas.get(name):
            schemas[name] = _load_schema(rel, errors)
        if schemas[name]:
            _check_schema_object(schemas[name], rel, errors)
    for name, rel in REGISTRY_FILES.items():
        if not regs.get(name):
            regs[name] = _load_json(rel, errors)
    if not contract:
        contract = _load_json(CONTRACT_PATH, errors)
    if not math_schema:
        math_schema = _load_json(MATH_DECISION_SCHEMA, errors)
    if not all(schemas.values()) or not all(regs.values()) or not contract or not math_schema:
        return errors

    check_state_machine(regs["state_machine"], contract, errors)
    check_module_registry(regs["module"], contract, errors)
    check_scenario_registry(regs["scenario"], contract, math_schema, errors)
    check_schema_registry_consistency(schemas, regs, contract, errors)
    check_bindings(regs, errors)
    return sorted(set(errors))


def load_all() -> dict[str, Any]:
    data: dict[str, Any] = {
        "schemas": {},
        "registries": {},
        "contract": None,
        "math_schema": None,
    }
    errors: list[str] = []
    for name, rel in SCHEMA_FILES.items():
        data["schemas"][name] = _load_schema(rel, errors)
    for name, rel in REGISTRY_FILES.items():
        data["registries"][name] = _load_json(rel, errors)
    data["contract"] = _load_json(CONTRACT_PATH, errors)
    data["math_schema"] = _load_json(MATH_DECISION_SCHEMA, errors)
    if errors:
        raise ValueError(errors[0])
    return data


def mutation_for(recipe: dict[str, Any], load: dict[str, Any]) -> dict[str, Any]:
    """Apply a registered S-1 mutation recipe to an in-memory copy."""
    mutated = copy.deepcopy(load)
    mutation_id = recipe["mutation_id"]
    if mutation_id == "shape_invalid":
        schema = mutated["schemas"]["command"]
        schema["$defs"]["aggregate_key"]["additionalProperties"] = True
    elif mutation_id == "schema_unregistered":
        mutated["registries"]["scenario"]["supported_versions"]["schema_version"] = ["9.9.9"]
    elif mutation_id == "module_registry":
        duplicated = copy.deepcopy(mutated["registries"]["module"]["modules"][0])
        duplicated["role"] = "candidate_port"
        duplicated["module_id"] = "module-duplicate-v1"
        mutated["registries"]["module"]["modules"].append(duplicated)
    elif mutation_id == "module_binding":
        mutated["registries"]["module"]["modules"][0]["interface_version"] = "9.9.9"
    else:
        raise ValueError("unsupported mutation recipe")
    return mutated


def _has_diagnostic(diagnostics: list[str], code: str) -> bool:
    return any(d == code or d.startswith(code + ":") for d in diagnostics)


def run_self_tests(load: dict[str, Any]) -> list[str]:
    """Mutate in-memory copies and require the exact registered diagnostic."""
    errors: list[str] = []
    shape_payload = {"mutation_id": "shape_invalid", "case_id": "duplicate-json-key-or-open-object", "expected_diagnostic": DIAG_SHAPE}
    shape_diag = validate(mutation_for(shape_payload, load))
    if not _has_diagnostic(shape_diag, DIAG_SHAPE):
        errors.append("SELF-TEST:SELF-TEST-SHAPE expected ARCH-SHAPE-INVALID")
    schema_payload = {"mutation_id": "schema_unregistered", "case_id": "unknown-schema-or-contract-version", "expected_diagnostic": DIAG_SCHEMA_UNREGISTERED}
    schema_diag = validate(mutation_for(schema_payload, load))
    if not _has_diagnostic(schema_diag, DIAG_SCHEMA_UNREGISTERED):
        errors.append("SELF-TEST:SELF-TEST-SCHEMA expected ARCH-SCHEMA-UNREGISTERED")
    module_reg_payload = {"mutation_id": "module_registry", "case_id": "missing-or-duplicate-module-role", "expected_diagnostic": DIAG_MODULE_REGISTRY}
    module_reg_diag = validate(mutation_for(module_reg_payload, load))
    if not _has_diagnostic(module_reg_diag, DIAG_MODULE_REGISTRY):
        errors.append("SELF-TEST:SELF-TEST-MODULE-REGISTRY expected ARCH-MODULE-REGISTRY")
    module_bind_payload = {"mutation_id": "module_binding", "case_id": "unsupported-interface-or-schema-digest", "expected_diagnostic": DIAG_MODULE_BINDING}
    module_bind_diag = validate(mutation_for(module_bind_payload, load))
    if not _has_diagnostic(module_bind_diag, DIAG_MODULE_BINDING):
        errors.append("SELF-TEST:SELF-TEST-MODULE-BINDING expected ARCH-MODULE-BINDING")
    return errors


def run_known_bad(path: Path) -> tuple[int, dict[str, Any]]:
    try:
        recipe = strict_load(path)
        payload_meta = {"case_id": recipe["case_id"], "expected_diagnostic": recipe["expected_diagnostic"]}
        load = load_all()
        mutated = mutation_for(recipe, load)
        diagnostics = validate(mutated)
        detected = _has_diagnostic(diagnostics, recipe["expected_diagnostic"])
        result = {
            "case_id": recipe["case_id"],
            "fixture_sha256": file_sha256(path),
            "diagnostic": recipe["expected_diagnostic"] if detected else (diagnostics[0] if diagnostics else "no diagnostic"),
            "result": "DETECTED" if detected else "SURVIVED",
        }
        return (0 if detected else 1), result
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return 1, {"case_id": "invalid", "fixture_sha256": file_sha256(path) if path.is_file() else "", "diagnostic": str(exc), "result": "SURVIVED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE-001 S-1 schema and registry closure checker")
    parser.add_argument("--known-bad", type=Path, help="run one registered S-1 mutation recipe")
    args = parser.parse_args()
    if args.known_bad:
        path = args.known_bad if args.known_bad.is_absolute() else ROOT / args.known_bad
        code, payload = run_known_bad(path)
        print(json.dumps(payload, sort_keys=True))
        return code
    try:
        load = load_all()
        errors = validate(load)
        errors.extend(run_self_tests(load))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors = [f"{DIAG_SHAPE}: validation exception {type(exc).__name__}: {exc}"]
    print("PASS" if not errors else "FAIL")
    if errors:
        for error in errors:
            print(f"  {error}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
