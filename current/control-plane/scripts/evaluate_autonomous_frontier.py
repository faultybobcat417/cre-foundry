"""Evaluate the repository's autonomous-frontier contract.

Stdout is deliberately restricted to one of PASS, FAIL, or BLOCKED_EXTERNAL.
Diagnostics are available only through an optional repository-local JSON report.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "control/AUTONOMOUS_FRONTIER_CONTRACT.json"
CONTRACT_SCHEMA = ROOT / "contracts/autonomous_frontier_contract.schema.json"
ALLOWED_RESULTS = ["PASS", "FAIL", "BLOCKED_EXTERNAL"]
REQUIRED_DOMAINS = {
    "mission_integrity",
    "research_closure",
    "source_feasibility",
    "data_historical_reconstruction",
    "temporal_entity_location_correctness",
    "outcomes_labels_maturity_censoring",
    "mathematical_statistical_contracts",
    "baseline_model_framework",
    "calibration_uncertainty",
    "economics_expected_commercial_value",
    "exactly_ten_abstention",
    "routing_representative_feasibility",
    "evaluator_independence",
    "deterministic_vertical_slice",
    "application_architecture_product_workflow",
    "security_authorization_privacy",
    "observability_provenance_lineage",
    "replay_recovery_migration_safety",
    "adversarial_mutation_fault_resistance",
    "documentation_state_resumability",
    "external_evidence_preparation",
    "convergence_sweeps",
    "full_system_convergence",
}
REQUIRED_GATE_IDS = {
    "mission_integrity": "AF-MISSION-INTEGRITY-001",
    "research_closure": "AF-RESEARCH-CLOSURE-001",
    "source_feasibility": "AF-SOURCE-FEASIBILITY-001",
    "data_historical_reconstruction": "AF-DATA-HISTORY-001",
    "temporal_entity_location_correctness": "AF-IDENTITY-TEMPORAL-001",
    "outcomes_labels_maturity_censoring": "AF-OUTCOMES-LABELS-001",
    "mathematical_statistical_contracts": "AF-MATH-STATS-001",
    "baseline_model_framework": "AF-BASELINE-MODEL-001",
    "calibration_uncertainty": "AF-CALIBRATION-UNCERTAINTY-001",
    "economics_expected_commercial_value": "AF-ECONOMICS-ECV-001",
    "exactly_ten_abstention": "AF-EXACT-TEN-001",
    "routing_representative_feasibility": "AF-ROUTING-FEASIBILITY-001",
    "evaluator_independence": "AF-EVALUATOR-INDEPENDENCE-001",
    "deterministic_vertical_slice": "AF-VERTICAL-SLICE-001",
    "application_architecture_product_workflow": "AF-ARCHITECTURE-PRODUCT-001",
    "security_authorization_privacy": "AF-SECURITY-PRIVACY-001",
    "observability_provenance_lineage": "AF-OBSERVABILITY-LINEAGE-001",
    "replay_recovery_migration_safety": "AF-REPLAY-RECOVERY-001",
    "adversarial_mutation_fault_resistance": "AF-ADVERSARIAL-RESISTANCE-001",
    "documentation_state_resumability": "AF-DOCUMENTATION-STATE-001",
    "external_evidence_preparation": "AF-EXTERNAL-READINESS-001",
    "convergence_sweeps": "AF-CONVERGENCE-SWEEPS-001",
    "full_system_convergence": "AF-FULL-SYSTEM-CONVERGENCE-001",
}
MANDATORY_OBLIGATIONS = {
    "mission_integrity": ("exact-ten-or-abstain", "route-day", "proof ceilings"),
    "research_closure": ("primary evidence", "inference"),
    "source_feasibility": ("licence", "replay"),
    "data_historical_reconstruction": ("bitemporal", "future leakage"),
    "temporal_entity_location_correctness": ("protected", "ambiguity"),
    "outcomes_labels_maturity_censoring": ("f9", "censoring"),
    "mathematical_statistical_contracts": ("estimands", "exact-ten"),
    "baseline_model_framework": ("incumbent", "point-in-time"),
    "calibration_uncertainty": ("uncertainty", "subgroup"),
    "economics_expected_commercial_value": ("risk-adjusted", "realized"),
    "exactly_ten_abstention": ("ten distinct eligible", "abstention"),
    "routing_representative_feasibility": ("representative", "route-day"),
    "evaluator_independence": ("independently custodied", "hidden"),
    "deterministic_vertical_slice": ("source-to-snapshot", "replay"),
    "application_architecture_product_workflow": ("idempotency", "bypass"),
    "security_authorization_privacy": ("least privilege", "live permissions default false"),
    "observability_provenance_lineage": ("lineage", "sensitive"),
    "replay_recovery_migration_safety": ("idempotency", "migration"),
    "adversarial_mutation_fault_resistance": ("mutations", "tests or thresholds are weakened"),
    "documentation_state_resumability": ("git checkpoints", "reconcile"),
    "external_evidence_preparation": ("preregistrations", "expiry/revocation"),
    "convergence_sweeps": ("three independent", "two successive"),
    "full_system_convergence": ("randomized f9", "level-9 realized"),
}
GATE_ID = re.compile(r"^AF-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{3}$")
PYTHON_COMMAND = "python"
SELF_SCRIPT = "scripts/evaluate_autonomous_frontier.py"
ALLOWED_EVALUATOR_TYPES = {"public", "sealed", "external_hidden"}
ALLOWED_AVAILABILITY = {"autonomous", "external"}
ALLOWED_CAPABILITY_CLASSES = {
    "repository_derivable",
    "publicly_researchable",
    "access_dependent",
    "human_authoritative",
    "empirically_measurable_only",
    "externally_hidden",
}
EXTERNAL_CAPABILITY_CLASSES = {
    "access_dependent",
    "human_authoritative",
    "empirically_measurable_only",
    "externally_hidden",
}
PROOF_CEILINGS = {
    "specification": 1,
    "deterministic_test": 2,
    "differential_reference": 3,
    "mutation_fault": 4,
    "synthetic": 5,
    "real_source_sample": 5,
    "historical_point_in_time": 6,
    "prospective_shadow": 7,
    "randomized_prospective": 8,
    "production_observed": 9,
    "external_attestation": 9,
}
REQUIRED_GATE_FIELDS = {
    "gate_id",
    "domain",
    "decision_purpose",
    "dependencies",
    "pass_conditions",
    "failure_conditions",
    "required_artifacts",
    "required_evidence",
    "required_evaluator",
    "verification_commands",
    "known_bad_cases",
    "achieved_proof_level",
    "autonomous_required_proof_level",
    "required_proof_level",
    "claim_ceiling",
    "unresolved_uncertainty",
    "external_blocker",
}


def confined_path(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise ValueError(f"path must be non-empty and relative: {raw!r}")
    raw_path = Path(raw)
    cursor = root.resolve()
    for part in raw_path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink paths are forbidden: {raw}")
    candidate = (root / raw_path).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(f"path escapes repository: {raw}")
    return candidate


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    ignored = {".venv", "__pycache__", ".pytest_cache"}
    for path in sorted(path for path in root.rglob("*") if path.is_file() and not ignored.intersection(path.parts)):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def load_json_strict(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    payload = json.loads(path.read_text(), object_pairs_hook=no_duplicates)
    if not isinstance(payload, dict):
        raise ValueError("contract must be a JSON object")
    return payload


def validate_command(root: Path, command: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"command_id", "phase", "argv", "cwd", "timeout_seconds", "expected_exit_code", "expected_stdout"}
    if set(command) != required:
        return [f"verification command fields must be exactly {sorted(required)}"]
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
        return ["verification argv must be a non-empty string array"]
    if argv[0] != PYTHON_COMMAND:
        errors.append("verification executable must be the canonical python token")
    if command.get("phase") not in ALLOWED_AVAILABILITY:
        errors.append("verification phase must be autonomous or external")
    if not isinstance(command.get("timeout_seconds"), int) or not 1 <= command["timeout_seconds"] <= 120:
        errors.append("verification timeout must be 1..120 seconds")
    if command.get("expected_exit_code") != 0:
        errors.append("verification commands must require exit code zero")
    if command.get("expected_stdout") != "PASS":
        errors.append("verification commands must require exact PASS stdout")
    try:
        confined_path(root, command.get("cwd", ""))
    except ValueError as exc:
        errors.append(str(exc))
    if len(argv) < 2 or not argv[1].endswith(".py") or argv[1].startswith("-"):
        errors.append("argv[1] must be one explicit repository Python script")
        return errors
    if any(arg.endswith(".py") for arg in argv[2:]):
        errors.append("verification command may name only one Python script")
    try:
        script_path = confined_path(root, argv[1])
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    relative = script_path.relative_to(root.resolve()).as_posix()
    if not relative.startswith(("scripts/", "evals/")):
        errors.append(f"verification script outside scripts/ or evals/: {argv[1]}")
    if relative == SELF_SCRIPT:
        errors.append("frontier evaluator self-invocation is forbidden")
    if not script_path.is_file():
        errors.append(f"verification script missing: {argv[1]}")
    return errors


def run_command(root: Path, execution_root: Path, command: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    errors = validate_command(root, command)
    if errors:
        return False, {"command_id": command.get("command_id"), "errors": errors}
    cwd = confined_path(execution_root, command["cwd"])
    before = tree_digest(execution_root)
    try:
        replay_argv = [sys.executable, *command["argv"][1:]]
        result = subprocess.run(
            replay_argv,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=command["timeout_seconds"],
            env={
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "CRE_FRONTIER_COMMAND_REPLAY": "1",
                "CRE_FRONTIER_EVALUATION_DEPTH": str(int(os.environ.get("CRE_FRONTIER_EVALUATION_DEPTH", "0")) + 1),
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, {"command_id": command["command_id"], "errors": [type(exc).__name__]}
    after = tree_digest(execution_root)
    passed = result.returncode == command["expected_exit_code"] and before == after
    passed = passed and result.stdout == "PASS\n" and result.stderr == ""
    return passed, {
        "command_id": command["command_id"],
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "repository_unchanged": before == after,
        "passed": passed,
    }


def run_known_bad(
    root: Path,
    execution_root: Path,
    command: dict[str, Any],
    known_bad: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    fixture = confined_path(root, known_bad["fixture"])
    if not fixture.is_file() or fixture.is_symlink():
        return False, {"case_id": known_bad["case_id"], "errors": ["missing known-bad fixture"]}
    errors = validate_command(root, command)
    if errors:
        return False, {"case_id": known_bad["case_id"], "errors": errors}
    cwd = confined_path(execution_root, command["cwd"])
    before = tree_digest(execution_root)
    argv = [sys.executable, *command["argv"][1:], "--known-bad", known_bad["fixture"]]
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=command["timeout_seconds"],
            env={
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "CRE_FRONTIER_COMMAND_REPLAY": "1",
                "CRE_FRONTIER_EVALUATION_DEPTH": str(int(os.environ.get("CRE_FRONTIER_EVALUATION_DEPTH", "0")) + 1),
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, {"case_id": known_bad["case_id"], "errors": [type(exc).__name__]}
    after = tree_digest(execution_root)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    expected_fixture_hash = file_digest(fixture)
    passed = (
        result.returncode == 0
        and result.stderr == ""
        and before == after
        and isinstance(payload, dict)
        and set(payload) == {"result", "case_id", "fixture_sha256", "diagnostic"}
        and payload["result"] == "DETECTED"
        and payload["case_id"] == known_bad["case_id"]
        and payload["fixture_sha256"] == expected_fixture_hash
        and payload["diagnostic"] == known_bad["expected_diagnostic"]
    )
    evaluator = confined_path(root, command["argv"][1])
    return passed, {
        "case_id": known_bad["case_id"],
        "fixture_sha256": expected_fixture_hash,
        "evaluator_sha256": file_digest(evaluator),
        "exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "repository_unchanged": before == after,
        "detected": passed,
    }


def validate_artifact(root: Path, artifact: dict[str, Any]) -> tuple[bool, str | None]:
    required = {"artifact_id", "path", "availability", "evidence_type", "minimum_proof_level", "sha256"}
    if set(artifact) != required:
        return False, f"artifact fields must be exactly {sorted(required)}"
    if artifact.get("availability") not in ALLOWED_AVAILABILITY:
        return False, "artifact availability must be autonomous or external"
    if artifact.get("evidence_type") not in PROOF_CEILINGS:
        return False, "artifact evidence_type is not recognized by the proof ladder"
    if not isinstance(artifact.get("minimum_proof_level"), int) or not 0 <= artifact["minimum_proof_level"] <= 9:
        return False, "artifact minimum_proof_level must be 0..9"
    if artifact["minimum_proof_level"] > PROOF_CEILINGS[artifact["evidence_type"]]:
        return False, "artifact minimum proof exceeds its evidence-type ceiling"
    try:
        path = confined_path(root, artifact["path"])
    except (KeyError, ValueError) as exc:
        return False, str(exc)
    if not path.is_file() or path.is_symlink():
        return False, f"missing artifact: {artifact['path']}"
    expected_hash = artifact.get("sha256")
    if (
        expected_hash is None
        and artifact["availability"] == "autonomous"
        and artifact["evidence_type"] != "specification"
    ):
        return False, f"autonomous evidentiary artifact lacks sha256 binding: {artifact['path']}"
    if expected_hash is not None:
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            return False, "artifact sha256 must be null or 64 lowercase hex characters"
        if file_digest(path) != expected_hash:
            return False, f"artifact hash mismatch: {artifact['path']}"
    return True, None


def validate_evidence(root: Path, evidence: dict[str, Any]) -> tuple[bool, str | None]:
    required = {"evidence_id", "description", "availability", "minimum_proof_level", "artifact"}
    if set(evidence) != required:
        return False, f"evidence fields must be exactly {sorted(required)}"
    if evidence.get("availability") not in ALLOWED_AVAILABILITY:
        return False, "evidence availability must be autonomous or external"
    if not isinstance(evidence.get("description"), str) or not evidence["description"].strip():
        return False, "evidence description is required"
    if not isinstance(evidence.get("minimum_proof_level"), int) or not 0 <= evidence["minimum_proof_level"] <= 9:
        return False, "evidence minimum_proof_level must be 0..9"
    try:
        path = confined_path(root, evidence["artifact"])
    except (KeyError, ValueError) as exc:
        return False, str(exc)
    if not path.is_file():
        return False, f"missing evidence: {evidence['artifact']}"
    return True, None


def verify_external_attestation(
    root: Path,
    gate: dict[str, Any],
    contract_sha256: str,
) -> tuple[bool, dict[str, Any]]:
    """Require an independently controlled verifier and trust root outside the repo."""
    blocker = gate["external_blocker"]
    assert blocker is not None
    attestation = confined_path(root, blocker["evidence_artifact"])
    authority_raw = os.environ.get("CRE_FRONTIER_EXTERNAL_AUTHORITY_CONFIG")
    if not authority_raw:
        return False, {"error": "external authority configuration is required"}
    authority = Path(authority_raw)
    resolved_root = root.resolve()
    if not authority.is_absolute() or authority.is_symlink() or not authority.is_file():
        return False, {"error": "external authority config must be an absolute regular non-symlink file"}
    if authority.resolve() == resolved_root or resolved_root in authority.resolve().parents:
        return False, {"error": "external authority config must be outside the repository"}
    authority_stat = authority.stat()
    if authority_stat.st_uid == os.geteuid() or os.access(authority, os.W_OK):
        return False, {"error": "external authority config is builder-owned or builder-writable"}
    if authority_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return False, {"error": "external authority config is group/world writable"}
    try:
        authority_payload = load_json_strict(authority)
        authority_fields = {
            "authority_id",
            "owner",
            "verifier_path",
            "verifier_sha256",
            "trust_root_path",
            "trust_root_sha256",
        }
        if set(authority_payload) != authority_fields:
            return False, {"error": "external authority config fields are not exact"}
        if not all(
            isinstance(authority_payload[field], str) and authority_payload[field].strip()
            for field in authority_fields
        ):
            return False, {"error": "external authority config is incomplete"}
        verifier = Path(authority_payload["verifier_path"])
        trust_root = Path(authority_payload["trust_root_path"])
        for label, path, digest in (
            ("verifier", verifier, authority_payload["verifier_sha256"]),
            ("trust_root", trust_root, authority_payload["trust_root_sha256"]),
        ):
            if not path.is_absolute() or path.is_symlink() or not path.is_file():
                return False, {"error": f"external {label} must be an absolute regular non-symlink file"}
            resolved = path.resolve()
            file_stat = path.stat()
            if resolved == resolved_root or resolved_root in resolved.parents:
                return False, {"error": f"external {label} must be outside the repository"}
            if file_stat.st_uid != authority_stat.st_uid or os.access(path, os.W_OK):
                return False, {"error": f"external {label} does not share non-builder custody"}
            if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                return False, {"error": f"external {label} is group/world writable"}
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or file_digest(path) != digest:
                return False, {"error": f"external {label} digest mismatch"}
        if not os.access(verifier, os.X_OK):
            return False, {"error": "external verifier is not executable"}
        payload = load_json_strict(attestation)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        required = {
            "gate_id",
            "subject_commit",
            "contract_sha256",
            "evaluator_sha256",
            "issuer",
            "issued_at",
            "expires_at",
            "revocation_status",
            "signature",
        }
        if set(payload) != required:
            return False, {"error": "external attestation fields are not exact"}
        if payload["gate_id"] != gate["gate_id"] or payload["subject_commit"] != head:
            return False, {"error": "external attestation subject mismatch"}
        if payload["contract_sha256"] != contract_sha256:
            return False, {"error": "external attestation contract mismatch"}
        if not re.fullmatch(r"[0-9a-f]{64}", payload["evaluator_sha256"]):
            return False, {"error": "external evaluator digest is malformed"}
        if not all(isinstance(payload[field], str) and payload[field].strip() for field in ("issuer", "issued_at", "expires_at", "signature")):
            return False, {"error": "external attestation authority fields are incomplete"}
        expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
        if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
            return False, {"error": "external attestation is expired or timezone-free"}
        if payload["revocation_status"] != "not_revoked":
            return False, {"error": "external attestation is revoked or unknown"}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return False, {"error": f"invalid external attestation: {type(exc).__name__}"}
    try:
        result = subprocess.run(
            [
                str(verifier),
                "--trust-root",
                str(trust_root),
                "--attestation",
                str(attestation),
                "--contract-sha256",
                contract_sha256,
                "--gate-id",
                gate["gate_id"],
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, {"error": f"external verifier failed: {type(exc).__name__}"}
    passed = result.returncode == 0 and result.stdout == "PASS\n" and result.stderr == ""
    return passed, {
        "verifier_sha256": file_digest(verifier),
        "trust_root_sha256": file_digest(trust_root),
        "attestation_sha256": file_digest(attestation),
        "passed": passed,
    }


def structural_errors(contract: dict[str, Any], root: Path, required_domains: set[str]) -> list[str]:
    errors: list[str] = []
    try:
        schema = load_json_strict(root / CONTRACT_SCHEMA.relative_to(ROOT))
        Draft202012Validator.check_schema(schema)
        errors.extend(
            f"schema:{'/'.join(str(part) for part in error.absolute_path)}:{error.message}"
            for error in Draft202012Validator(schema).iter_errors(contract)
        )
    except Exception as exc:
        errors.append(f"contract schema unavailable or invalid: {type(exc).__name__}")
    required_top = {"contract_id", "version", "mission_ref", "allowed_results", "capability_classes", "result_precedence", "gates"}
    if set(contract) != required_top:
        errors.append(f"top-level fields must be exactly {sorted(required_top)}")
    if contract.get("contract_id") != "CRE-AUTONOMOUS-FRONTIER":
        errors.append("unexpected contract_id")
    if contract.get("allowed_results") != ALLOWED_RESULTS:
        errors.append("allowed_results must be PASS, FAIL, BLOCKED_EXTERNAL in that order")
    if set(contract.get("capability_classes", [])) != ALLOWED_CAPABILITY_CLASSES:
        errors.append("capability_classes do not match the required classification taxonomy")
    if contract.get("result_precedence") != ["FAIL", "BLOCKED_EXTERNAL", "PASS"]:
        errors.append("result_precedence must be FAIL, BLOCKED_EXTERNAL, PASS")
    if not isinstance(contract.get("mission_ref"), str):
        errors.append("mission_ref is required")
    else:
        try:
            if not confined_path(root, contract["mission_ref"]).is_file():
                errors.append("mission_ref is missing")
        except ValueError as exc:
            errors.append(str(exc))
    gates = contract.get("gates")
    if not isinstance(gates, list) or not gates:
        return errors + ["gates must be a non-empty array"]
    ids: set[str] = set()
    domains: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("each gate must be an object")
            continue
        missing = REQUIRED_GATE_FIELDS - set(gate)
        extra = set(gate) - REQUIRED_GATE_FIELDS
        if missing or extra:
            errors.append(f"{gate.get('gate_id')}: gate fields mismatch missing={sorted(missing)} extra={sorted(extra)}")
            continue
        gate_id = gate["gate_id"]
        if not isinstance(gate_id, str) or not GATE_ID.fullmatch(gate_id):
            errors.append(f"invalid stable gate id: {gate_id!r}")
        elif gate_id in ids:
            errors.append(f"duplicate gate id: {gate_id}")
        ids.add(gate_id)
        domain = gate["domain"]
        if domain in domains:
            errors.append(f"duplicate domain: {domain}")
        domains.add(domain)
        if REQUIRED_GATE_IDS.get(domain) != gate_id:
            errors.append(f"{gate_id}: gate id does not match mandatory stable id for {domain}")
        semantic_text = " ".join(
            [
                str(gate.get("decision_purpose", "")),
                *[str(value) for value in gate.get("pass_conditions", [])],
                *[str(value) for value in gate.get("failure_conditions", [])],
                str(gate.get("claim_ceiling", "")),
            ]
        ).lower()
        for obligation in MANDATORY_OBLIGATIONS.get(domain, ()):
            if obligation not in semantic_text:
                errors.append(f"{gate_id}: mandatory semantic obligation is absent: {obligation}")
        for field in ("decision_purpose", "claim_ceiling"):
            if not isinstance(gate[field], str) or not gate[field].strip():
                errors.append(f"{gate_id}: {field} must be non-empty")
        for field in ("dependencies", "pass_conditions", "failure_conditions", "required_artifacts", "required_evidence", "verification_commands", "known_bad_cases", "unresolved_uncertainty"):
            if not isinstance(gate[field], list):
                errors.append(f"{gate_id}: {field} must be an array")
        if not gate["pass_conditions"] or not gate["failure_conditions"] or not gate["required_artifacts"] or not gate["required_evidence"] or not gate["verification_commands"]:
            errors.append(f"{gate_id}: pass/failure/artifact/evidence/command arrays must be non-empty")
        for level_field in ("achieved_proof_level", "autonomous_required_proof_level", "required_proof_level"):
            if not isinstance(gate[level_field], int) or not 0 <= gate[level_field] <= 9:
                errors.append(f"{gate_id}: {level_field} must be 0..9")
        if gate["autonomous_required_proof_level"] > gate["required_proof_level"]:
            errors.append(f"{gate_id}: autonomous proof target exceeds final target")
        evaluator = gate["required_evaluator"]
        evaluator_fields = {"evaluator_id", "type", "owner", "independent_from_builder", "artifact"}
        if not isinstance(evaluator, dict) or set(evaluator) != evaluator_fields:
            errors.append(f"{gate_id}: malformed required_evaluator")
        else:
            if evaluator["type"] not in ALLOWED_EVALUATOR_TYPES:
                errors.append(f"{gate_id}: invalid evaluator type")
            if evaluator["type"] != "public" and not evaluator["independent_from_builder"]:
                errors.append(f"{gate_id}: sealed/external evaluator must be independent")
            if not isinstance(evaluator["owner"], str) or not evaluator["owner"].strip():
                errors.append(f"{gate_id}: evaluator owner is required")
            try:
                confined_path(root, evaluator["artifact"])
            except (KeyError, ValueError) as exc:
                errors.append(f"{gate_id}: {exc}")
        blocker = gate["external_blocker"]
        if blocker is not None:
            blocker_fields = {"gate_id", "classification", "owner", "unlock_condition", "evidence_artifact"}
            if not isinstance(blocker, dict) or set(blocker) != blocker_fields:
                errors.append(f"{gate_id}: malformed external_blocker")
            else:
                for field in ("gate_id", "classification", "owner", "unlock_condition", "evidence_artifact"):
                    if not isinstance(blocker[field], str) or not blocker[field].strip():
                        errors.append(f"{gate_id}: external blocker {field} is required")
                if blocker.get("classification") not in EXTERNAL_CAPABILITY_CLASSES:
                    errors.append(f"{gate_id}: external blocker has non-external capability class")
                if re.search(r"\b(?:TBD|UNKNOWN|UNASSIGNED)\b", blocker.get("owner", ""), re.IGNORECASE):
                    errors.append(f"{gate_id}: external blocker owner is a placeholder")
                try:
                    confined_path(root, blocker["evidence_artifact"])
                except ValueError as exc:
                    errors.append(f"{gate_id}: {exc}")
                if not any(artifact.get("availability") == "external" for artifact in gate["required_artifacts"]):
                    errors.append(f"{gate_id}: external blocker lacks an external required artifact")
                if not any(evidence.get("availability") == "external" for evidence in gate["required_evidence"]):
                    errors.append(f"{gate_id}: external blocker lacks external required evidence")
                if not any(command.get("phase") == "external" for command in gate["verification_commands"]):
                    errors.append(f"{gate_id}: external blocker lacks an external verification command")
        for artifact in gate["required_artifacts"]:
            if not isinstance(artifact, dict):
                errors.append(f"{gate_id}: artifact must be an object")
            else:
                _, error = validate_artifact_shape(root, artifact)
                if error:
                    errors.append(f"{gate_id}: {error}")
        artifact_ids = [artifact.get("artifact_id") for artifact in gate["required_artifacts"] if isinstance(artifact, dict)]
        if len(artifact_ids) != len(set(artifact_ids)):
            errors.append(f"{gate_id}: duplicate artifact_id")
        for evidence in gate["required_evidence"]:
            if not isinstance(evidence, dict):
                errors.append(f"{gate_id}: evidence must be an object")
            else:
                _, error = validate_evidence_shape(root, evidence)
                if error:
                    errors.append(f"{gate_id}: {error}")
        evidence_ids = [evidence.get("evidence_id") for evidence in gate["required_evidence"] if isinstance(evidence, dict)]
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"{gate_id}: duplicate evidence_id")
        for command in gate["verification_commands"]:
            if not isinstance(command, dict):
                errors.append(f"{gate_id}: command must be an object")
            else:
                errors.extend(f"{gate_id}: {error}" for error in validate_command_shape(root, command))
        command_ids = [command.get("command_id") for command in gate["verification_commands"] if isinstance(command, dict)]
        if len(command_ids) != len(set(command_ids)):
            errors.append(f"{gate_id}: duplicate command_id")
        command_by_id = {
            command.get("command_id"): command
            for command in gate["verification_commands"]
            if isinstance(command, dict)
        }
        for known_bad in gate["known_bad_cases"]:
            if not isinstance(known_bad, dict) or set(known_bad) != {"case_id", "description", "fixture", "verification_command_id", "expected_diagnostic"}:
                errors.append(f"{gate_id}: malformed known-bad case")
                continue
            if not isinstance(known_bad["expected_diagnostic"], str) or not known_bad["expected_diagnostic"].strip():
                errors.append(f"{gate_id}: known-bad expected_diagnostic is required")
            try:
                confined_path(root, known_bad["fixture"])
            except (KeyError, ValueError) as exc:
                errors.append(f"{gate_id}: {exc}")
            verifier = command_by_id.get(known_bad.get("verification_command_id"))
            if verifier is None:
                errors.append(f"{gate_id}: known-bad references an unknown verification command")
            elif verifier.get("phase") != "autonomous":
                errors.append(f"{gate_id}: known-bad detection must use an autonomous command")
        known_bad_ids = [case.get("case_id") for case in gate["known_bad_cases"] if isinstance(case, dict)]
        if len(known_bad_ids) != len(set(known_bad_ids)):
            errors.append(f"{gate_id}: duplicate known-bad case_id")
    if domains != required_domains:
        errors.append(f"domain coverage mismatch missing={sorted(required_domains - domains)} extra={sorted(domains - required_domains)}")
    by_id = {gate.get("gate_id"): gate for gate in gates if isinstance(gate, dict) and isinstance(gate.get("gate_id"), str)}
    indegree = {gate_id: 0 for gate_id in by_id}
    children = {gate_id: [] for gate_id in by_id}
    for gate_id, gate in by_id.items():
        for dependency in gate.get("dependencies", []):
            if dependency not in by_id:
                errors.append(f"{gate_id}: unknown dependency {dependency}")
                continue
            indegree[gate_id] += 1
            children[dependency].append(gate_id)
    ready = sorted(gate_id for gate_id, count in indegree.items() if count == 0)
    visited: list[str] = []
    while ready:
        gate_id = ready.pop(0)
        visited.append(gate_id)
        for child in children[gate_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(visited) != len(by_id):
        errors.append("gate dependencies contain a cycle")
    registered_gates_path = root / "control/GATES.json"
    if registered_gates_path.is_file():
        registered_gate_ids = {
            gate["gate_id"] for gate in load_json_strict(registered_gates_path).get("gates", [])
        }
        for gate in gates:
            blocker = gate.get("external_blocker") if isinstance(gate, dict) else None
            if blocker is not None and blocker.get("gate_id") not in registered_gate_ids:
                errors.append(f"{gate.get('gate_id')}: external blocker is absent from control/GATES.json")
    return errors


def validate_artifact_shape(root: Path, artifact: dict[str, Any]) -> tuple[bool, str | None]:
    required = {"artifact_id", "path", "availability", "evidence_type", "minimum_proof_level", "sha256"}
    if set(artifact) != required:
        return False, f"artifact fields must be exactly {sorted(required)}"
    if artifact.get("availability") not in ALLOWED_AVAILABILITY:
        return False, "artifact availability must be autonomous or external"
    if artifact.get("evidence_type") not in PROOF_CEILINGS:
        return False, "artifact evidence_type is not recognized by the proof ladder"
    if not isinstance(artifact.get("minimum_proof_level"), int) or not 0 <= artifact["minimum_proof_level"] <= 9:
        return False, "artifact minimum_proof_level must be 0..9"
    if artifact["minimum_proof_level"] > PROOF_CEILINGS[artifact["evidence_type"]]:
        return False, "artifact minimum proof exceeds its evidence-type ceiling"
    try:
        confined_path(root, artifact["path"])
    except (KeyError, ValueError) as exc:
        return False, str(exc)
    expected_hash = artifact.get("sha256")
    if expected_hash is not None and (not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)):
        return False, "artifact sha256 must be null or 64 lowercase hex characters"
    return True, None


def validate_evidence_shape(root: Path, evidence: dict[str, Any]) -> tuple[bool, str | None]:
    required = {"evidence_id", "description", "availability", "minimum_proof_level", "artifact"}
    if set(evidence) != required:
        return False, f"evidence fields must be exactly {sorted(required)}"
    if evidence.get("availability") not in ALLOWED_AVAILABILITY:
        return False, "evidence availability must be autonomous or external"
    if not isinstance(evidence.get("description"), str) or not evidence["description"].strip():
        return False, "evidence description is required"
    if not isinstance(evidence.get("minimum_proof_level"), int) or not 0 <= evidence["minimum_proof_level"] <= 9:
        return False, "evidence minimum_proof_level must be 0..9"
    try:
        confined_path(root, evidence["artifact"])
    except (KeyError, ValueError) as exc:
        return False, str(exc)
    return True, None


def validate_command_shape(root: Path, command: dict[str, Any]) -> list[str]:
    errors = validate_command(root, command)
    return [error for error in errors if not error.startswith("verification script missing:")]


def evaluate_gate(
    gate: dict[str, Any],
    root: Path,
    execution_root: Path,
    contract_sha256: str,
) -> tuple[str, dict[str, Any]]:
    errors: list[str] = []
    command_results: list[dict[str, Any]] = []
    known_bad_results: list[dict[str, Any]] = []
    blocker = gate["external_blocker"]
    external_evidence_path = None if blocker is None else confined_path(root, blocker["evidence_artifact"])
    external_evidence_present = blocker is None or (
        external_evidence_path.is_file() and not external_evidence_path.is_symlink()
    )
    external_verification: dict[str, Any] | None = None
    if blocker is not None and external_evidence_present:
        trusted, external_verification = verify_external_attestation(root, gate, contract_sha256)
        if not trusted:
            errors.append("external evidence failed independent verification")
    for artifact in gate["required_artifacts"]:
        if artifact["availability"] == "external" and not external_evidence_present:
            continue
        passed, error = validate_artifact(root, artifact)
        if not passed and error:
            errors.append(error)
    for evidence in gate["required_evidence"]:
        if evidence["availability"] == "external" and not external_evidence_present:
            continue
        passed, error = validate_evidence(root, evidence)
        if not passed and error:
            errors.append(error)
    evaluator_artifact = confined_path(root, gate["required_evaluator"]["artifact"])
    evaluator_is_external = gate["required_evaluator"]["type"] != "public"
    if not (evaluator_is_external and not external_evidence_present) and not evaluator_artifact.is_file():
        errors.append(f"missing evaluator artifact: {gate['required_evaluator']['artifact']}")
    for command in gate["verification_commands"]:
        if command["phase"] == "external" and not external_evidence_present:
            continue
        passed, result = run_command(root, execution_root, command)
        command_results.append(result)
        if not passed:
            errors.append(f"verification command failed: {command['command_id']}")
    command_ids = {command["command_id"] for command in gate["verification_commands"]}
    command_by_id = {command["command_id"]: command for command in gate["verification_commands"]}
    for known_bad in gate["known_bad_cases"]:
        try:
            fixture = confined_path(root, known_bad["fixture"])
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not fixture.is_file() or fixture.is_symlink():
            errors.append(f"missing known-bad fixture: {known_bad['fixture']}")
        if known_bad["verification_command_id"] not in command_ids:
            errors.append(f"known-bad case lacks a matching verification command: {known_bad['case_id']}")
            continue
        passed, result = run_known_bad(
            root,
            execution_root,
            command_by_id[known_bad["verification_command_id"]],
            known_bad,
        )
        known_bad_results.append(result)
        if not passed:
            errors.append(f"known-bad case survived or was not executed: {known_bad['case_id']}")
    achieved = gate["achieved_proof_level"]
    available_ceilings = [
        PROOF_CEILINGS.get(artifact["evidence_type"], -1)
        for artifact in gate["required_artifacts"]
        if confined_path(root, artifact["path"]).is_file()
    ]
    if achieved > max(available_ceilings, default=0):
        errors.append("achieved proof level exceeds available evidence-type ceiling")
    if achieved < gate["autonomous_required_proof_level"]:
        errors.append("achieved proof level is below autonomous target")
    if errors:
        return "FAIL", {
            "gate_id": gate["gate_id"],
            "result": "FAIL",
            "errors": errors,
            "commands": command_results,
            "known_bad_cases": known_bad_results,
            "external_verification": external_verification,
        }
    if blocker is not None and not external_evidence_present:
        return "BLOCKED_EXTERNAL", {
            "gate_id": gate["gate_id"],
            "result": "BLOCKED_EXTERNAL",
            "errors": [],
            "commands": command_results,
            "known_bad_cases": known_bad_results,
            "blocker": blocker,
        }
    if achieved < gate["required_proof_level"]:
        return "FAIL", {
            "gate_id": gate["gate_id"],
            "result": "FAIL",
            "errors": ["achieved proof level is below final target"],
            "commands": command_results,
            "known_bad_cases": known_bad_results,
        }
    return "PASS", {
        "gate_id": gate["gate_id"],
        "result": "PASS",
        "errors": [],
        "commands": command_results,
        "known_bad_cases": known_bad_results,
        "external_verification": external_verification,
    }


def topological_gate_order(gates: list[dict[str, Any]]) -> list[str]:
    by_id = {gate["gate_id"]: gate for gate in gates}
    remaining = {gate_id: len(gate["dependencies"]) for gate_id, gate in by_id.items()}
    children = {gate_id: [] for gate_id in by_id}
    for gate_id, gate in by_id.items():
        for dependency in gate["dependencies"]:
            children[dependency].append(gate_id)
    ready = sorted(gate_id for gate_id, count in remaining.items() if count == 0)
    order: list[str] = []
    while ready:
        gate_id = ready.pop(0)
        order.append(gate_id)
        for child in children[gate_id]:
            remaining[child] -= 1
            if remaining[child] == 0:
                ready.append(child)
                ready.sort()
    return order


def reconcile_task_state(root: Path) -> list[str]:
    errors: list[str] = []
    state = load_json_strict(root / "control/CURRENT_STATE.json")
    graph = load_json_strict(root / "control/TASK_GRAPH.json")
    gate_registry = load_json_strict(root / "control/GATES.json")
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list):
        return ["task graph nodes must be an array"]
    by_id = {node.get("task_id"): node for node in nodes if isinstance(node, dict)}
    if len(by_id) != len(nodes) or None in by_id:
        return ["task graph task identifiers are missing or duplicated"]
    statuses = {task_id: node.get("status") for task_id, node in by_id.items()}
    valid_statuses = {"pending", "in_progress", "blocked", "completed"}
    for task_id, node in by_id.items():
        if statuses[task_id] not in valid_statuses:
            errors.append(f"{task_id}: invalid task status")
        for dependency in node.get("dependencies", []):
            if dependency not in by_id:
                errors.append(f"{task_id}: unknown task dependency {dependency}")
            elif statuses[task_id] == "completed" and statuses[dependency] != "completed":
                errors.append(f"{task_id}: completed before dependency {dependency}")
    open_gate_ids = {
        gate.get("gate_id")
        for gate in gate_registry.get("gates", [])
        if isinstance(gate, dict) and str(gate.get("status", "")).startswith("OPEN")
    }
    direct_blocked = {
        task_id
        for task_id, node in by_id.items()
        if any(gate in open_gate_ids for gate in node.get("gates", []))
    }
    completed = {task_id for task_id, status in statuses.items() if status == "completed"}
    for task_id in completed:
        node = by_id[task_id]
        open_direct = [gate for gate in node.get("gates", []) if gate in open_gate_ids]
        if open_direct:
            errors.append(f"{task_id}: completed task retains open gates {sorted(open_direct)}")
        result_path = root / f"artifacts/task-results/{task_id}.json"
        if not result_path.is_file():
            errors.append(f"{task_id}: completed task lacks a task-result artifact")
        else:
            try:
                task_result = load_json_strict(result_path)
                if task_result.get("task_id") != task_id or task_result.get("status") != "completed":
                    errors.append(f"{task_id}: completed task-result status or identity mismatch")
            except (OSError, ValueError, json.JSONDecodeError):
                errors.append(f"{task_id}: completed task-result is invalid JSON")
    externally_blocked = set(direct_blocked)
    changed = True
    while changed:
        changed = False
        for task_id, node in by_id.items():
            if task_id not in externally_blocked and any(
                dependency in externally_blocked for dependency in node.get("dependencies", [])
            ):
                externally_blocked.add(task_id)
                changed = True
    executable = {
        task_id
        for task_id, node in by_id.items()
        if statuses[task_id] != "completed"
        and all(dependency in completed for dependency in node.get("dependencies", []))
        and task_id not in direct_blocked
    }
    blocked = set(by_id) - completed - executable
    for field, expected in (
        ("completed_tasks", completed),
        ("executable_tasks", executable),
        ("blocked_tasks", blocked),
    ):
        actual = state.get(field)
        if not isinstance(actual, list) or set(actual) != expected or len(actual) != len(set(actual)):
            errors.append(f"state {field} does not match recomputed task graph")
    current = state.get("current_task_id")
    if executable and current not in executable:
        errors.append("current task is not executable")
    if not executable and current is not None:
        errors.append("terminal task graph must have no current task")
    if not executable:
        stranded = (set(by_id) - completed) - externally_blocked
        if stranded:
            errors.append(f"incomplete tasks lack a transitive registered external blocker: {sorted(stranded)}")
    return errors


def evaluate_contract(
    contract: dict[str, Any],
    root: Path = ROOT,
    required_domains: set[str] = REQUIRED_DOMAINS,
    enforce_repository_state: bool = True,
) -> tuple[str, dict[str, Any]]:
    errors = structural_errors(contract, root, required_domains)
    if errors:
        return "FAIL", {"result": "FAIL", "structural_errors": errors, "gates": []}
    contract_sha256 = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    gate_results_by_id: dict[str, dict[str, Any]] = {}
    base_outcomes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="cre-frontier-evaluation-") as temp_dir:
        execution_root = Path(temp_dir) / "repository"
        shutil.copytree(
            root,
            execution_root,
            ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"),
        )
        for gate in contract["gates"]:
            outcome, detail = evaluate_gate(gate, root, execution_root, contract_sha256)
            base_outcomes[gate["gate_id"]] = outcome
            gate_results_by_id[gate["gate_id"]] = detail
    resolved: dict[str, str] = {}
    by_id = {gate["gate_id"]: gate for gate in contract["gates"]}
    for gate_id in topological_gate_order(contract["gates"]):
        base = base_outcomes[gate_id]
        dependency_outcomes = {dependency: resolved[dependency] for dependency in by_id[gate_id]["dependencies"]}
        if base == "FAIL" or "FAIL" in dependency_outcomes.values():
            resolved[gate_id] = "FAIL"
        elif base == "BLOCKED_EXTERNAL" or "BLOCKED_EXTERNAL" in dependency_outcomes.values():
            resolved[gate_id] = "BLOCKED_EXTERNAL"
        else:
            resolved[gate_id] = "PASS"
        detail = gate_results_by_id[gate_id]
        if resolved[gate_id] != base:
            detail["base_result"] = base
            detail["result"] = resolved[gate_id]
            detail["dependency_results"] = dependency_outcomes
    outcomes = list(resolved.values())
    gate_results = [gate_results_by_id[gate["gate_id"]] for gate in contract["gates"]]
    if "FAIL" in outcomes:
        result = "FAIL"
    elif "BLOCKED_EXTERNAL" in outcomes:
        result = "BLOCKED_EXTERNAL"
    else:
        result = "PASS"
    terminal_errors: list[str] = []
    if enforce_repository_state and result in {"PASS", "BLOCKED_EXTERNAL"}:
        state_path = root / "control/CURRENT_STATE.json"
        graph_path = root / "control/TASK_GRAPH.json"
        gates_path = root / "control/GATES.json"
        if not all(path.is_file() for path in (state_path, graph_path, gates_path)):
            terminal_errors.append("terminal result requires state, task graph, and gates")
        else:
            terminal_errors.extend(reconcile_task_state(root))
            state = load_json_strict(state_path)
            if state.get("executable_tasks"):
                terminal_errors.append("terminal result forbidden while recomputed executable tasks remain")
        git_status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if git_status.returncode != 0 or git_status.stdout.strip():
            terminal_errors.append("terminal result requires a clean repository")
    if terminal_errors:
        result = "FAIL"
    return result, {
        "contract_id": contract["contract_id"],
        "contract_sha256": contract_sha256,
        "result": result,
        "structural_errors": [],
        "terminal_errors": terminal_errors,
        "gate_counts": {outcome: outcomes.count(outcome) for outcome in ALLOWED_RESULTS},
        "gates": gate_results,
    }


def write_report(root: Path, raw_path: str, report: dict[str, Any]) -> None:
    path = confined_path(root, raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    contract_path = DEFAULT_CONTRACT
    report_path: str | None = None
    try:
        if int(os.environ.get("CRE_FRONTIER_EVALUATION_DEPTH", "0")) > 0:
            raise ValueError("recursive frontier evaluation is forbidden")
        while args:
            option = args.pop(0)
            if option == "--contract" and args:
                contract_path = confined_path(ROOT, args.pop(0))
            elif option == "--report" and args:
                report_path = args.pop(0)
                confined_path(ROOT, report_path)
            else:
                raise ValueError("invalid arguments")
        contract = load_json_strict(contract_path)
        result, report = evaluate_contract(contract, ROOT)
        if report_path is not None and result in {"PASS", "BLOCKED_EXTERNAL"}:
            result = "FAIL"
            report["result"] = "FAIL"
            report.setdefault("terminal_errors", []).append(
                "terminal result cannot be paired with a repository-local report write"
            )
        if report_path is not None:
            write_report(ROOT, report_path, report)
    except Exception as exc:  # fail closed without leaking diagnostics to stdout
        result = "FAIL"
        report = {"result": "FAIL", "structural_errors": [type(exc).__name__], "gates": []}
        if report_path is not None:
            try:
                write_report(ROOT, report_path, report)
            except Exception:
                pass
    print(result)
    return 0 if result in {"PASS", "BLOCKED_EXTERNAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
