"""Independent public semantic evaluator for CONTRACT-001."""
from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
OBSERVATION_SCHEMA = ROOT / "contracts/thin_slice_observation.schema.json"
CANDIDATE_SCHEMA = ROOT / "contracts/thin_slice_candidate.schema.json"
SUPPORTED = {
    "THIN_SLICE_OBSERVATION": "1.0.0",
    "THIN_SLICE_CANDIDATE": "1.0.0",
    "THIN_SLICE_SPINE": "1.0.0",
}
SPINE_FIELDS = {
    "document_kind", "schema_version", "decision_scope", "contract_id", "canonicalization",
    "normalizer_version", "adapter_version", "adapter_sha256", "supported_version_transition",
    "schema_bindings", "source_snapshot_sha256", "candidate_snapshot_sha256", "protected_bundle",
    "observations", "candidates", "math_problem", "math_decision", "replay_receipt", "proof",
}
EXPECTED_TRANSITION = {"observation": "1.0.0", "candidate": "1.0.0", "math_problem": "1.0.0", "math_decision": "1.0.0"}
EXPECTED_SCHEMA_PATHS = {
    "observation": "contracts/thin_slice_observation.schema.json",
    "candidate": "contracts/thin_slice_candidate.schema.json",
    "math_problem": "contracts/math_decision_policy.schema.json",
    "math_decision": "contracts/math_route_decision.schema.json",
}
EXPECTED_PROOF = {
    "level": 4,
    "claim": "synthetic contract conformance only",
    "focal_observation_id": "OBS:SYN_0001",
    "real_world_identity_proven": False,
    "live_issuance_authorized": False,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_load(path: Path) -> Any:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=no_duplicates)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _location_id(basis: dict[str, Any]) -> str:
    return f"LOCATION:{digest_json(basis)[:24]}"


def _object_schemas_are_closed(schema: Any) -> bool:
    if isinstance(schema, dict):
        if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
            return False
        return all(_object_schemas_are_closed(value) for value in schema.values())
    if isinstance(schema, list):
        return all(_object_schemas_are_closed(value) for value in schema)
    return True


def _schema_errors(schema: dict[str, Any], document: Any) -> list[str]:
    return [error.message for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)]


def validate_spine(spine: dict[str, Any], *, check_replay: bool = False) -> list[str]:
    """Return stable diagnostics; targeted mutation checks intentionally run first."""
    documents = [spine, *spine.get("observations", []), *spine.get("candidates", [])]
    for document in documents:
        kind = document.get("document_kind", "UNKNOWN") if isinstance(document, dict) else "UNKNOWN"
        version = document.get("schema_version") if isinstance(document, dict) else None
        if kind in SUPPORTED and version != SUPPORTED[kind]:
            return [f"CONTRACT-UNREGISTERED-SCHEMA-VERSION:{kind}:{version}"]
    for candidate in spine.get("candidates", []):
        identity = candidate.get("identity", {}) if isinstance(candidate, dict) else {}
        location_id = identity.get("physical_location_id")
        grain_ids = identity.get("grain_ids", {})
        if location_id is not None and isinstance(grain_ids, dict) and location_id in {value for value in grain_ids.values() if value is not None}:
            return ["CONTRACT-IDENTITY-GRAIN-COLLAPSE"]
    if set(spine) != SPINE_FIELDS:
        return ["CONTRACT-SPINE-SHAPE"]
    if (
        spine.get("document_kind") != "THIN_SLICE_SPINE"
        or spine.get("schema_version") != "1.0.0"
        or spine.get("decision_scope") != "SYNTHETIC_FORMAL_ONLY"
        or spine.get("contract_id") != "CONTRACT-001-SPINE-V1"
        or spine.get("canonicalization") != "SORTED_KEYS_INTEGER_JSON_V1"
        or spine.get("normalizer_version") != "lower-ascii-hyphen-v1"
        or spine.get("adapter_version") != "thin-spine-adapter-v1"
    ):
        return ["CONTRACT-SPINE-BOUNDARY"]
    if spine.get("supported_version_transition") != EXPECTED_TRANSITION:
        return ["CONTRACT-UNREGISTERED-VERSION-TRANSITION"]
    bindings = spine.get("schema_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(EXPECTED_SCHEMA_PATHS):
        return ["CONTRACT-SCHEMA-BINDING-COVERAGE"]
    for name, expected_path in EXPECTED_SCHEMA_PATHS.items():
        if set(bindings[name]) != {"path", "schema_version", "sha256"} or bindings[name].get("path") != expected_path or bindings[name].get("schema_version") != "1.0.0":
            return [f"CONTRACT-SCHEMA-BINDING:{name}"]
    if spine.get("proof") != EXPECTED_PROOF:
        return ["CONTRACT-CLAIM-CEILING"]
    protected_bundle = spine.get("protected_bundle")
    if not isinstance(protected_bundle, dict) or set(protected_bundle) != {"bundle_id", "complete", "tokens"} or protected_bundle.get("bundle_id") != "SYNTHETIC-PROTECTED-BUNDLE" or not isinstance(protected_bundle.get("complete"), bool) or not isinstance(protected_bundle.get("tokens"), list) or protected_bundle["tokens"] != sorted(set(protected_bundle["tokens"])):
        return ["CONTRACT-PROTECTION-BUNDLE-BOUNDARY"]

    try:
        observation_schema = strict_load(OBSERVATION_SCHEMA)
        candidate_schema = strict_load(CANDIDATE_SCHEMA)
        Draft202012Validator.check_schema(observation_schema)
        Draft202012Validator.check_schema(candidate_schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"CONTRACT-SCHEMA-UNAVAILABLE:{type(exc).__name__}"]
    if not _object_schemas_are_closed(observation_schema) or not _object_schemas_are_closed(candidate_schema):
        return ["CONTRACT-SCHEMA-OPEN-OBJECT"]
    for observation in spine.get("observations", []):
        errors = _schema_errors(observation_schema, observation)
        if errors:
            return [f"CONTRACT-OBSERVATION-SCHEMA:{observation.get('observation_id')}:{errors[0]}"]
    for candidate in spine.get("candidates", []):
        errors = _schema_errors(candidate_schema, candidate)
        if errors:
            return [f"CONTRACT-CANDIDATE-SCHEMA:{candidate.get('candidate_id')}:{errors[0]}"]

    observations = spine.get("observations", [])
    candidates = spine.get("candidates", [])
    if not observations or len(observations) > 20 or len(candidates) != len(observations):
        return ["CONTRACT-BOUNDED-CARDINALITY"]
    observation_ids = [row["observation_id"] for row in observations]
    candidate_ids = [row["candidate_id"] for row in candidates]
    if len(set(observation_ids)) != len(observation_ids) or len(set(candidate_ids)) != len(candidate_ids):
        return ["CONTRACT-DUPLICATE-ID"]
    by_observation = {row["observation_id"]: row for row in observations}
    registered_cutoff = spine.get("math_problem", {}).get("snapshot", {}).get("stage1_cutoff")
    try:
        _time(registered_cutoff)
    except (TypeError, ValueError):
        return ["CONTRACT-STAGE1-CUTOFF-BINDING"]

    for observation in observations:
        try:
            clocks = observation["clocks"]
            ordered = [_time(clocks[name]) for name in ["retrieved_at", "observed_at", "ingested_at", "validation_completed_at"]]
            cutoff = _time(clocks["stage1_cutoff"])
            available = _time(clocks["available_at"])
        except (KeyError, TypeError, ValueError):
            return [f"CONTRACT-CLOCK-INVALID:{observation.get('observation_id')}"]
        if clocks["stage1_cutoff"] != registered_cutoff:
            return ["CONTRACT-STAGE1-CUTOFF-BINDING"]
        if available > cutoff:
            return ["CONTRACT-STAGE1-FUTURE-OBSERVATION"]
        if ordered != sorted(ordered) or available != ordered[-1]:
            return [f"CONTRACT-CLOCK-ORDER:{observation['observation_id']}"]
        for name in ["event", "publisher_effective", "published"]:
            clock = clocks[name]
            if (clock["state"] == "KNOWN") != (clock["at"] is not None):
                return [f"CONTRACT-CLOCK-STATE:{observation['observation_id']}:{name}"]
        if clocks["published"]["state"] == "KNOWN" and _time(clocks["published"]["at"]) > cutoff:
            return ["CONTRACT-STAGE1-FUTURE-OBSERVATION"]
        if clocks["published"]["state"] == "KNOWN" and _time(clocks["published"]["at"]) > ordered[0]:
            return ["CONTRACT-CLOCK-ORDER-PUBLICATION"]
        if observation["normalized_alias_tokens"] != sorted(observation["normalized_alias_tokens"]):
            return ["CONTRACT-NONCANONICAL-SET"]

    for candidate in candidates:
        identity = candidate["identity"]
        location_id = identity["physical_location_id"]
        grain_ids = identity["grain_ids"]
        if location_id != _location_id(identity["physical_location_basis"]):
            return ["CONTRACT-IDENTITY-GRAIN-COLLAPSE"]
        observation = by_observation.get(candidate["lineage"]["observation_id"])
        if observation is None:
            return ["CONTRACT-DANGLING-OBSERVATION"]
        if candidate["stage1_cutoff"] != registered_cutoff:
            return ["CONTRACT-STAGE1-CUTOFF-BINDING"]
        aliases = sorted(observation["normalized_alias_tokens"])
        if candidate["identity"]["alias_tokens"] != sorted(candidate["identity"]["alias_tokens"]) or candidate["protection"]["candidate_tokens"] != sorted(candidate["protection"]["candidate_tokens"]) or candidate["protection"]["matched_tokens"] != sorted(candidate["protection"]["matched_tokens"]):
            return ["CONTRACT-NONCANONICAL-SET"]
        if sorted(candidate["identity"]["alias_tokens"]) != aliases or sorted(candidate["protection"]["candidate_tokens"]) != aliases:
            return ["CONTRACT-PROTECTED-ALIAS-OMITTED"]

    receipt = spine.get("replay_receipt", {})
    if receipt.get("math_decision_sha256") != digest_json(spine.get("math_decision")):
        return ["CONTRACT-DECISION-DIGEST-MISMATCH"]

    errors: list[str] = []
    source_snapshot_values = {row["origin"]["source_snapshot_sha256"] for row in observations}
    if len(source_snapshot_values) != 1 or source_snapshot_values != {spine.get("source_snapshot_sha256")}:
        errors.append("CONTRACT-SOURCE-SNAPSHOT-BINDING")
    raw_hashes = []
    for observation in observations:
        origin = observation["origin"]
        expected_origin = {
            "mode": "SYNTHETIC_FIXTURE",
            "source_definition_id": "ON-SELECT",
            "dataset_id": "SYNTHETIC-ON-SELECT",
            "resource_id": "SYNTHETIC-LICENCE-RESOURCE",
            "source_snapshot_id": "SYNTHETIC-SOURCE-SNAPSHOT-001",
            "source_registry_version": "2.0.0",
            "canonical_field_map_version": "2.0.0",
        }
        if any(origin.get(name) != value for name, value in expected_origin.items()):
            errors.append(f"CONTRACT-SOURCE-DEFINITION:{observation['observation_id']}")
        if origin["source_registry_sha256"] != digest_file(ROOT / "artifacts/research/source_feasibility_registry.json") or origin["canonical_field_map_sha256"] != digest_file(ROOT / "artifacts/research/canonical_field_map.json"):
            errors.append(f"CONTRACT-RESEARCH-BINDING:{observation['observation_id']}")
        raw = observation["raw_record"]
        try:
            raw_bytes = base64.b64decode(raw["bytes_base64"], validate=True)
        except (ValueError, TypeError):
            errors.append(f"CONTRACT-RAW-BYTES:{observation['observation_id']}")
            continue
        raw_hashes.append(raw["bytes_sha256"])
        if hashlib.sha256(raw_bytes).hexdigest() != raw["bytes_sha256"]:
            errors.append(f"CONTRACT-RAW-DIGEST:{observation['observation_id']}")
        expected_raw = {name: raw[name] for name in ["address_raw", "unit_raw", "operating_name_raw", "legal_name_raw", "licence_number_raw"]}
        if raw_bytes != canonical_bytes(expected_raw):
            errors.append(f"CONTRACT-RAW-PROJECTION:{observation['observation_id']}")
        expected_aliases = sorted({_normalize(raw[name]) for name in ["operating_name_raw", "legal_name_raw", "licence_number_raw"] if raw[name]})
        if observation["normalized_alias_tokens"] != expected_aliases:
            errors.append(f"CONTRACT-ALIAS-NORMALIZATION:{observation['observation_id']}")
        if observation["native_identity"]["native_key_sha256"] != digest_json({"licence_number_raw": observation["native_identity"]["native_key"]}):
            errors.append(f"CONTRACT-NATIVE-KEY-DIGEST:{observation['observation_id']}")
        if observation["native_identity"]["native_key"] != raw["licence_number_raw"]:
            errors.append(f"CONTRACT-NATIVE-KEY-PROJECTION:{observation['observation_id']}")
    expected_source_snapshot = digest_json({
        "contract_scope": "SYNTHETIC_FORMAL_ONLY",
        "snapshot_id": "SYNTHETIC-SOURCE-SNAPSHOT-001",
        "raw_record_sha256": sorted(raw_hashes),
    })
    if spine.get("source_snapshot_sha256") != expected_source_snapshot:
        errors.append("CONTRACT-SOURCE-SNAPSHOT-DIGEST")

    adapter_path = ROOT / "src/cre_foundry/contracts/thin_slice.py"
    actual_adapter_sha = digest_file(adapter_path)
    protected_tokens = set(spine.get("protected_bundle", {}).get("tokens", []))
    bundle_complete = spine.get("protected_bundle", {}).get("complete") is True
    expected_bundle_sha = digest_json({"bundle_id": "SYNTHETIC-PROTECTED-BUNDLE", "complete": bundle_complete, "tokens": sorted(protected_tokens)})
    for candidate in candidates:
        observation = by_observation[candidate["lineage"]["observation_id"]]
        cid = candidate["candidate_id"]
        if candidate["lineage"]["observation_sha256"] != digest_json(observation):
            errors.append(f"CONTRACT-OBSERVATION-DIGEST:{cid}")
        if candidate["lineage"]["source_snapshot_sha256"] != expected_source_snapshot:
            errors.append(f"CONTRACT-CANDIDATE-SNAPSHOT-BINDING:{cid}")
        if candidate["lineage"]["adapter_sha256"] != actual_adapter_sha or candidate["lineage"]["adapter_sha256"] != spine.get("adapter_sha256"):
            errors.append(f"CONTRACT-ADAPTER-DIGEST:{cid}")
        basis = candidate["identity"]["physical_location_basis"]
        raw = observation["raw_record"]
        expected_basis = {"method_version": "synthetic-address-unit-v1", "normalized_address": _normalize(raw["address_raw"]), "normalized_unit": _normalize(raw["unit_raw"]) if raw["unit_raw"] else None}
        if basis != expected_basis:
            errors.append(f"CONTRACT-LOCATION-BASIS:{cid}")
        protection = candidate["protection"]
        if protection["bundle_sha256"] != expected_bundle_sha or protection["bundle_complete"] is not bundle_complete:
            errors.append(f"CONTRACT-PROTECTION-BUNDLE-BINDING:{cid}")
        matches = sorted(set(protection["candidate_tokens"]) & protected_tokens)
        expected_status = "UNKNOWN" if not bundle_complete or not protection["token_extraction_complete"] else "PROTECTED" if matches else "CLEAR"
        if protection["matched_tokens"] != matches or protection["status"] != expected_status:
            errors.append(f"CONTRACT-PROTECTION-DERIVATION:{cid}")
        load_times = [_time(observation["clocks"]["available_at"]), _time(candidate["identity"]["resolved_at"]), _time(protection["evaluated_at"]), _time(candidate["score"]["computed_at"])]
        load_times.extend(_time(row["evaluated_at"]) for row in candidate["evaluations"].values())
        if _time(candidate["available_at"]) != max(load_times) or _time(candidate["available_at"]) > _time(candidate["stage1_cutoff"]):
            errors.append(f"CONTRACT-CANDIDATE-AVAILABILITY:{cid}")
        expected_math = {
            "candidate_id": cid,
            "physical_location_id": candidate["identity"]["physical_location_id"],
            "grain_ids": candidate["identity"]["grain_ids"],
            "protection_tokens": candidate["identity"]["alias_tokens"],
            "evidence_stage": 1,
            "observed_at": candidate["available_at"],
            "gates": {name: row["state"] for name, row in candidate["evaluations"].items()},
            "protected_status": protection["status"],
            "value_state": candidate["score"]["state"],
            "business_value_units": candidate["score"]["business_value_units"],
            "proximity_cost_units": candidate["score"]["proximity_cost_units"],
            "service_minutes": candidate["score"]["service_minutes"],
            "composition_group": candidate["score"]["composition_group"],
        }
        if candidate["math_candidate"] != expected_math:
            errors.append(f"CONTRACT-MATH-PROJECTION:{cid}")

    expected_candidate_snapshot = digest_json({
        "contract_version": "1.0.0",
        "stage1_cutoff": "2026-07-31T23:00:00Z",
        "source_snapshot_sha256": expected_source_snapshot,
        "adapter_version": "thin-spine-adapter-v1",
        "adapter_sha256": actual_adapter_sha,
        "candidates": [[row["candidate_id"], digest_json(row)] for row in sorted(candidates, key=lambda item: item["candidate_id"])],
    })
    if spine.get("candidate_snapshot_sha256") != expected_candidate_snapshot:
        errors.append("CONTRACT-CANDIDATE-SNAPSHOT-DIGEST")
    problem = spine.get("math_problem", {})
    if problem.get("candidates") != [row["math_candidate"] for row in sorted(candidates, key=lambda item: item["candidate_id"])] or problem.get("snapshot", {}).get("snapshot_sha256") != expected_candidate_snapshot:
        errors.append("CONTRACT-MATH-PROBLEM-BINDING")
    policy = problem.get("policy", {})
    if policy.get("policy_sha256") != digest_json({key: value for key, value in policy.items() if key != "policy_sha256"}):
        errors.append("CONTRACT-POLICY-DIGEST")

    try:
        from evals.public.math_oracle_evaluator import evaluate, validate_route_decision
    except ModuleNotFoundError:
        from math_oracle_evaluator import evaluate, validate_route_decision
    decision = spine.get("math_decision", {})
    try:
        independently_expected = evaluate(problem)
        semantic_errors = validate_route_decision(problem, decision)
    except Exception as exc:  # malformed subjects must fail, never crash the validator
        errors.append(f"CONTRACT-MATH-EVALUATOR:{type(exc).__name__}")
    else:
        if semantic_errors or decision != independently_expected:
            errors.append("CONTRACT-MATH-DECISION")
    expected_receipt_fields = {"source_snapshot_sha256", "candidate_snapshot_sha256", "math_problem_sha256", "math_decision_sha256", "policy_sha256", "selected_candidate_ids", "result"}
    if set(receipt) != expected_receipt_fields or receipt.get("math_problem_sha256") != digest_json(problem) or receipt.get("candidate_snapshot_sha256") != expected_candidate_snapshot or receipt.get("source_snapshot_sha256") != expected_source_snapshot or receipt.get("policy_sha256") != policy.get("policy_sha256") or receipt.get("result") != decision.get("decision"):
        errors.append("CONTRACT-RECEIPT-BINDING")
    expected_selected_ids = [row["candidate_id"] for row in decision.get("selected", [])]
    if receipt.get("selected_candidate_ids") != expected_selected_ids:
        errors.append("CONTRACT-RECEIPT-SELECTION")
    if decision.get("decision") == "ISSUE" and len(decision.get("selected", [])) != 10:
        errors.append("CONTRACT-EXACT-TEN-RECEIPT")
    for name, binding in spine["schema_bindings"].items():
        path = binding.get("path", "")
        if not path or Path(path).is_absolute() or ".." in Path(path).parts or not (ROOT / path).is_file() or binding.get("sha256") != digest_file(ROOT / path):
            errors.append(f"CONTRACT-SCHEMA-BINDING:{name}")
    if check_replay and not errors:
        from cre_foundry.contracts.thin_slice import build_spine_from_observations
        replayed = build_spine_from_observations(copy.deepcopy(observations))
        normalized_subject = copy.deepcopy(spine)
        normalized_subject["observations"] = sorted(normalized_subject["observations"], key=lambda row: row["observation_id"])
        normalized_subject["candidates"] = sorted(normalized_subject["candidates"], key=lambda row: row["candidate_id"])
        if canonical_bytes(normalized_subject) != canonical_bytes(replayed):
            errors.append("CONTRACT-SUPPLIED-REPLAY-MISMATCH")
    return sorted(set(errors))
