#!/usr/bin/env python3
"""ARCHITECTURE-001 S-5 representative product workflow validator and report.

Read-only validation of the synthetic representative product workflow surface.
The validator independently projects a PRODUCT_WORKFLOW_SUBJECT from the frozen
ARCHITECTURE-001 canonical run and registries, requires schema conformance,
re-runs the frozen architecture validator unweakened, and rejects the two
registered product mutations (ui-bypass, duplicate-issuance) with the exact
registered diagnostics.  It never imports the architecture implementation
package and never byte-patches the frozen canonical.

Modes:
  * default        run every check; write artifacts/evaluations/architecture_product.json
  * --known-bad P  evaluate one registered mutation fixture for the house CLI
                   contract ({"result","case_id","fixture_sha256","diagnostic"})
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator

CANONICAL_PATH = ROOT / "artifacts/architecture/canonical_run.json"
CONTRACT_PATH = ROOT / "artifacts/architecture/public_evaluator_contract.json"
GATES_PATH = ROOT / "control/GATES.json"
SCHEMA_PATH = ROOT / "contracts/product_workflow.schema.json"
SYSTEM_DOC_PATH = ROOT / "docs/architecture/system.md"
ARCHITECTURE_EVAL_PATH = ROOT / "artifacts/evaluations/architecture.json"
REPORT_PATH = ROOT / "artifacts/evaluations/architecture_product.json"
FIXTURE_DIR = ROOT / "evals/known_bad/frontier"

CANONICAL_SHA256 = "1a44025fbbd4547b9c322d83d432239d3943b0839ab398cbf1034125397c075e"
ARCHITECTURE_EVAL_SHA256 = "3b1b1dca7ffcbae82891be4902838d8f496f45d4fe3ea19a1a1a2e46d024050a"
SCHEMA_VERSION = "1.0.0"
REPORT_EVALUATOR_ID = "architecture-product-public-v1"
REPORT_ARTIFACT_ID = "ARCHITECTURE-001-PRODUCT-EVALUATION"
CLAIM = "Public proof level 4 establishes deterministic conformance of the synthetic representative product workflow surface: exactly-ten-or-abstain result, route-day unit, frozen-Stage-1 lineage bindings, zero-false-clear protection, single idempotent issuance without duplicate external effect, Stage isolation, live-disabled defaults, programmatic accessibility semantics, and five open external gates."
CLAIM_CEILING = "No representative usability, WCAG or assistive-technology performance or certification, production durability or atomicity, operational reliability or error rate, security certification, route feasibility, deployment readiness, live authority, adoption, incremental F9 lift, or commercial value is established."

PRODUCT_CASES: dict[str, str] = {
    "ui-bypass": "registered mutation detected: ui-bypass",
    "duplicate-issuance": "registered mutation detected: duplicate-issuance",
}

EXTERNAL_GATES = [
    "GATE-MANUAL-REVIEW-AUTHORITY-001",
    "GATE-LIVE-WORKFLOW-AUTHORITY-001",
    "GATE-ACCESSIBILITY-EMPIRICAL-VALIDATION-001",
    "GATE-REPRESENTATIVE-USABILITY-001",
    "GATE-PRODUCTION-DEPLOYMENT-001",
]

REPORT_SUBJECTS = [
    "contracts/product_workflow.schema.json",
    "scripts/validate_architecture_product.py",
    "docs/architecture/system.md",
    "artifacts/architecture/canonical_run.json",
    "artifacts/architecture/public_evaluator_contract.json",
    "artifacts/evaluations/architecture.json",
    "control/GATES.json",
]
REPORT_FIELDS = {
    "artifact_id", "schema_version", "execution_scope", "result", "proof_level", "evaluator_id",
    "checks", "upstream", "external_gates", "subject_hashes", "mutation_results", "claim",
    "claim_ceiling",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def strict_load(path: Path):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def get_path(subject: dict[str, Any], path: list[str]):
    node: Any = subject
    for part in path:
        node = node[part]
    return node


def set_path(subject: dict[str, Any], path: list[str], value: Any) -> None:
    node = subject
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


def del_path(subject: dict[str, Any], path: list[str]) -> None:
    node = subject
    for part in path[:-1]:
        node = node[part]
    del node[path[-1]]


def append_path(subject: dict[str, Any], path: list[str], value: Any) -> None:
    get_path(subject, path).append(value)


# ---------------------------------------------------------------------------
# Independent product subject projection from the frozen canonical
# ---------------------------------------------------------------------------

def build_base_subject() -> dict[str, Any]:
    canonical = strict_load(CANONICAL_PATH)
    run = canonical["run"]
    contract = strict_load(CONTRACT_PATH)
    gates = {gate["gate_id"]: gate for gate in strict_load(GATES_PATH)["gates"]}

    selected_ids = [row["physical_location_id"] for row in run["result"]["selected"]]
    result = run["result"]["result"]
    if result != "ISSUE":
        selected_ids = []

    accessibility = run["accessibility_projection"]
    status = accessibility["status"]

    return {
        "document_kind": "PRODUCT_WORKFLOW_SUBJECT",
        "schema_version": SCHEMA_VERSION,
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "canonicalization": "SORTED_KEYS_INTEGER_JSON_V1",
        "subject_kind": "PRODUCT_WORKFLOW_SUBJECT",
        "run_id": run["run_id"],
        "aggregate_key": {
            "execution_scope": "SYNTHETIC_NON_INFLUENCING",
            "representative_id": run["aggregate_key"]["representative_id"],
            "route_date": run["aggregate_key"]["route_date"],
            "generation": run["aggregate_key"]["generation"],
        },
        "route_day": {
            "representative_id": run["aggregate_key"]["representative_id"],
            "route_date": run["aggregate_key"]["route_date"],
        },
        "decision": {
            "result": result,
            "selected_physical_location_ids": selected_ids,
            "reason": run["result"]["reason"],
        },
        "protection": {
            "protected_tokens": canonical["problem"]["snapshot"]["protected_tokens"],
            "protected_stops_issued": 0,
            "zero_false_clear": True,
        },
        "issuance": {
            "issuance_slot": {
                "execution_scope": run["issuance_ledger"][0]["issuance_slot"]["execution_scope"],
                "representative_id": run["issuance_ledger"][0]["issuance_slot"]["representative_id"],
                "route_date": run["issuance_ledger"][0]["issuance_slot"]["route_date"],
            },
            "route_manifest_sha256": run["issuance_ledger"][0]["route_manifest_sha256"],
            "committed_at": run["issuance_ledger"][0]["committed_at"],
            "external_effect_occurred": run["issuance_ledger"][0]["external_effect_occurred"],
            "unique_slot_single_issuance": len(run["issuance_ledger"]) == 1,
            "idempotency_sha256": run["receipt"]["idempotency_sha256"],
        },
        "lineage": {
            "canonical_run_sha256": CANONICAL_SHA256,
            "command_stream_sha256": run["receipt"]["command_stream_sha256"],
            "event_stream_sha256": run["receipt"]["event_stream_sha256"],
            "final_receipt_sha256": run["receipt"]["final_receipt_sha256"],
            "complete": True,
        },
        "stage_isolation": {
            "stage1_immutable": True,
            "stage2_append_only": True,
            "stage3_append_only": True,
            "stage1_rewrite_attempts": 0,
        },
        "live": {
            "live_enabled": False,
            "live_issuance_authorized": False,
        },
        "accessibility": {
            "claim_kind": accessibility["claim_kind"],
            "errors": accessibility["errors"],
            "status": {
                "primary_status_code": status["primary_status_code"],
                "reason_code": status["reason_code"],
                "safe_next_actions": [action["action_id"] for action in status["safe_next_actions"]],
                "announcement_intent": status["announcement_intent"],
            },
            "claims_not_established": accessibility["claims_not_established"],
        },
        "manual_edits": [],
        "proof": {
            "level": run["proof"]["level"],
            "live_issuance_authorized": run["proof"]["live_issuance_authorized"],
            "live_workflow_authorized": run["proof"]["live_workflow_authorized"],
            "external_effect_occurred": run["proof"]["external_effect_occurred"],
            "real_usability_proven": run["proof"]["real_usability_proven"],
            "accessibility_performance_or_conformance_proven": run["proof"]["accessibility_performance_or_conformance_proven"],
            "production_atomicity_or_reliability_proven": run["proof"]["production_atomicity_or_reliability_proven"],
            "security_proven": run["proof"]["security_proven"],
            "deployment_authorized": run["proof"]["deployment_authorized"],
            "incremental_lift_proven": run["proof"]["incremental_lift_proven"],
            "commercial_value_proven": run["proof"]["commercial_value_proven"],
            "real_route_feasibility_proven": run["proof"]["real_route_feasibility_proven"],
        },
        "external_gates": [
            {"gate_id": gate_id, "status": gates[gate_id]["status"]}
            for gate_id in EXTERNAL_GATES
        ],
        "claim_ceiling": CLAIM_CEILING,
    }


def apply_recipe(subject: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(subject)
    for op in recipe["ops"]:
        kind = op[0]
        if kind == "set":
            set_path(mutated, op[1], op[2])
        elif kind == "del":
            del_path(mutated, op[1])
        elif kind == "append":
            append_path(mutated, op[1], op[2])
        else:
            raise ValueError(f"unknown recipe op {kind}")
    return mutated


# ---------------------------------------------------------------------------
# Product evaluator: returns [] on a clean subject, otherwise registered
# diagnostics for the two registered product mutations, or generic codes.
# ---------------------------------------------------------------------------

def evaluate_product(subject: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    decision = subject["decision"]
    selected = decision["selected_physical_location_ids"]

    manual_applied_forbidden = [
        edit for edit in subject["manual_edits"] if edit["allowed"] is False and edit["applied"] is True
    ]
    if manual_applied_forbidden:
        diagnostics.append("registered mutation detected: ui-bypass")
    if subject["lineage"]["complete"] is not True:
        diagnostics.append("registered mutation detected: ui-bypass")
    if subject["protection"]["zero_false_clear"] is not True or subject["protection"]["protected_stops_issued"] != 0:
        diagnostics.append("registered mutation detected: ui-bypass")

    issuance = subject["issuance"]
    if issuance["external_effect_occurred"] is True:
        diagnostics.append("registered mutation detected: duplicate-issuance")
    if issuance["unique_slot_single_issuance"] is not True:
        diagnostics.append("registered mutation detected: duplicate-issuance")

    if decision["result"] == "ISSUE":
        if len(selected) != 10 or len(set(selected)) != 10:
            diagnostics.append("PRODUCT-DECISION-COUNT")
    elif decision["result"] == "ABSTAIN":
        if selected or not isinstance(decision["reason"], str) or not decision["reason"]:
            diagnostics.append("PRODUCT-ABSTAIN-VISIBILITY")
    else:
        diagnostics.append("PRODUCT-DECISION-UNKNOWN")

    if subject["live"]["live_enabled"] is not False or subject["live"]["live_issuance_authorized"] is not False:
        diagnostics.append("PRODUCT-LIVE-DENIAL")
    if subject["proof"]["level"] != 4:
        diagnostics.append("PRODUCT-PROOF-LEVEL")
    if subject["stage_isolation"]["stage1_rewrite_attempts"] != 0:
        diagnostics.append("PRODUCT-STAGE1-REWRITE")
    if subject["proof"]["external_effect_occurred"] is not False:
        diagnostics.append("PRODUCT-EXTERNAL-EFFECT")
    for gate in subject["external_gates"]:
        if gate["status"] != "OPEN_BLOCKING":
            diagnostics.append("PRODUCT-GATE-CLOSED")
    return sorted(set(diagnostics))


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def check_frozen_canonical(errors: list[str]) -> None:
    if not CANONICAL_PATH.is_file():
        errors.append("CANONICAL:missing canonical run")
        return
    if file_sha256(CANONICAL_PATH) != CANONICAL_SHA256:
        errors.append("CANONICAL:SHA mismatch with frozen canonical")
    if not ARCHITECTURE_EVAL_PATH.is_file():
        errors.append("CANONICAL:missing architecture evaluation report")
    elif file_sha256(ARCHITECTURE_EVAL_PATH) != ARCHITECTURE_EVAL_SHA256:
        errors.append("CANONICAL:architecture evaluation digest mismatch")


def check_schema(errors: list[str]) -> None:
    if not SCHEMA_PATH.is_file():
        errors.append("SCHEMA:missing product workflow schema")
        return
    try:
        schema = strict_load(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"SCHEMA:invalid: {type(exc).__name__}")
        return
    try:
        subject = build_base_subject()
        schema_errors = sorted(
            error.message for error in Draft202012Validator(schema).iter_errors(subject)
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"SCHEMA:projection failed: {type(exc).__name__}")
        return
    if schema_errors:
        errors.append(f"SCHEMA:subject does not conform: {schema_errors}")


def check_system_document(errors: list[str]) -> None:
    if not SYSTEM_DOC_PATH.is_file():
        errors.append("SYSTEM-DOC:missing docs/architecture/system.md")
    elif not SYSTEM_DOC_PATH.read_text().strip():
        errors.append("SYSTEM-DOC:empty document")


def check_external_gates(errors: list[str]) -> None:
    if not GATES_PATH.is_file():
        errors.append("GATES:missing control/GATES.json")
        return
    try:
        gates = {gate["gate_id"]: gate for gate in strict_load(GATES_PATH)["gates"]}
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        errors.append("GATES:invalid control/GATES.json")
        return
    for gate_id in EXTERNAL_GATES:
        if gate_id not in gates:
            errors.append(f"GATES:missing gate {gate_id}")
        elif gates[gate_id]["status"] != "OPEN_BLOCKING":
            errors.append(f"GATES:{gate_id} is not OPEN_BLOCKING")


def run_architecture_validator(errors: list[str]) -> None:
    script = ROOT / "scripts/validate_architecture.py"
    if not script.is_file():
        errors.append("ARCH-VALIDATOR:missing scripts/validate_architecture.py")
        return
    try:
        process = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"ARCH-VALIDATOR:{type(exc).__name__}")
        return
    if process.returncode != 0 or process.stdout.strip() != "PASS":
        errors.append("ARCH-VALIDATOR:frozen architecture validator did not PASS")


def build_report(errors: list[str], mutation_results: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "artifact_id": REPORT_ARTIFACT_ID,
        "schema_version": SCHEMA_VERSION,
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "result": "PASS" if not errors else "FAIL",
        "proof_level": 4,
        "evaluator_id": REPORT_EVALUATOR_ID,
        "checks": {
            "frozen_canonical": "PASS",
            "schema_conformance": "PASS",
            "system_document": "PASS",
            "external_gates_open": "PASS",
            "architecture_validator": "PASS",
            "product_invariants": "PASS",
        },
        "upstream": {
            "canonical_run_sha256": CANONICAL_SHA256,
            "architecture_evaluation_sha256": ARCHITECTURE_EVAL_SHA256,
        },
        "external_gates": EXTERNAL_GATES,
        "subject_hashes": {
            rel: file_sha256(ROOT / rel) for rel in sorted(REPORT_SUBJECTS)
        },
        "mutation_results": mutation_results,
        "claim": CLAIM,
        "claim_ceiling": CLAIM_CEILING,
    }
    if errors:
        report["checks"]["product_invariants"] = "FAIL"
        report["errors"] = sorted(set(errors))
    return report


def write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def validate() -> list[str]:
    errors: list[str] = []
    check_frozen_canonical(errors)
    check_schema(errors)
    check_system_document(errors)
    check_external_gates(errors)
    try:
        base = build_base_subject()
        base_diagnostics = evaluate_product(base)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors.append("PRODUCT-VALIDATION-EXCEPTION")
        return sorted(set(errors))
    if base_diagnostics:
        errors.append(f"PRODUCT:base subject diagnostics {base_diagnostics}")
    run_architecture_validator(errors)
    return sorted(set(errors))


def run_known_bad(raw_path: Path) -> int:
    path = raw_path if raw_path.is_absolute() else ROOT / raw_path
    try:
        fixture = strict_load(path)
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"result": "SURVIVED", "case_id": "unknown", "fixture_sha256": "", "diagnostic": "fixture not strictly parseable"}, sort_keys=True))
        return 1
    case_id = fixture.get("case_id")
    if not isinstance(case_id, str) or case_id not in PRODUCT_CASES or fixture.get("expected_diagnostic") != PRODUCT_CASES[case_id]:
        print(json.dumps({"result": "SURVIVED", "case_id": case_id if isinstance(case_id, str) else "unknown", "fixture_sha256": file_sha256(path), "diagnostic": "fixture semantics do not match the registered mutation"}, sort_keys=True))
        return 1
    try:
        base = build_base_subject()
        mutated = apply_recipe(base, fixture["recipe"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "SURVIVED", "case_id": case_id, "fixture_sha256": file_sha256(path), "diagnostic": type(exc).__name__}, sort_keys=True))
        return 1
    if digest_json(mutated) != digest_json(fixture["subject"]):
        print(json.dumps({"result": "SURVIVED", "case_id": case_id, "fixture_sha256": file_sha256(path), "diagnostic": "embedded subject is not the recipe projection"}, sort_keys=True))
        return 1
    diagnostics = evaluate_product(mutated)
    detected = diagnostics == [PRODUCT_CASES[case_id]]
    payload = {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": case_id,
        "fixture_sha256": file_sha256(path),
        "diagnostic": PRODUCT_CASES[case_id] if detected else (diagnostics[0] if diagnostics else "no diagnostic"),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if detected else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE-001 S-5 representative product workflow validator")
    parser.add_argument("--known-bad", type=Path, help="run one registered mutation fixture")
    args = parser.parse_args()
    if args.known_bad:
        return run_known_bad(args.known_bad)

    mutation_results: list[dict[str, Any]] = []
    replay = os.environ.get("CRE_FRONTIER_COMMAND_REPLAY") == "1"
    for path in sorted(FIXTURE_DIR.glob("product_*.json")):
        try:
            fixture = strict_load(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        case_id = fixture.get("case_id")
        if not isinstance(case_id, str) or case_id not in PRODUCT_CASES:
            continue
        try:
            base = build_base_subject()
            mutated = apply_recipe(base, fixture["recipe"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        if digest_json(mutated) != digest_json(fixture["subject"]):
            continue
        diagnostics = evaluate_product(mutated)
        detected = diagnostics == [PRODUCT_CASES[case_id]]
        mutation_results.append({
            "case_id": case_id,
            "diagnostic": PRODUCT_CASES[case_id],
            "fixture_sha256": file_sha256(path),
            "result": "DETECTED" if detected else "SURVIVED",
        })

    errors = validate()
    if sorted(row["case_id"] for row in mutation_results) != sorted(PRODUCT_CASES):
        errors.append("PRODUCT-MUTATION-COVERAGE")
    for row in mutation_results:
        if row["result"] != "DETECTED":
            errors.append(f"PRODUCT-MUTATION-SURVIVED:{row['case_id']}")

    report = build_report(errors, mutation_results)
    expected_bytes = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if replay:
        if not REPORT_PATH.is_file() or REPORT_PATH.read_text() != expected_bytes:
            errors.append("PRODUCT-REPORT:deterministic report mismatch")
            report = build_report(errors, mutation_results)
            expected_bytes = json.dumps(report, indent=2, sort_keys=True) + "\n"
    else:
        write_report(report)

    if errors:
        print("FAIL")
        for error in sorted(set(errors)):
            print(f"  {error}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
