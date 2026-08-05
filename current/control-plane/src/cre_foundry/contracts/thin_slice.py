"""Deterministic synthetic observation-to-decision contract spine.

This module proves an interface only.  It does not acquire source data, resolve
real entities, clear real protected accounts, estimate commercial value, or
authorize live issuance.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from cre_foundry.math.reference_oracle import decide

ROOT = Path(__file__).resolve().parents[3]
SCOPE = "SYNTHETIC_FORMAL_ONLY"
SCHEMA_VERSION = "1.0.0"
ADAPTER_VERSION = "thin-spine-adapter-v1"
NORMALIZER_VERSION = "lower-ascii-hyphen-v1"
LOCATION_METHOD_VERSION = "synthetic-address-unit-v1"


def canonical_bytes(value: Any) -> bytes:
    """Return the contract's deterministic integer-only JSON encoding."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not token:
        raise ValueError("normalized token must not be empty")
    return token


def physical_location_id(normalized_address: str, normalized_unit: str | None) -> str:
    basis = {
        "method_version": LOCATION_METHOD_VERSION,
        "normalized_address": normalized_address,
        "normalized_unit": normalized_unit,
    }
    return f"LOCATION:{digest_json(basis)[:24]}"


def _adapter_sha256() -> str:
    return digest_file(Path(__file__))


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must contain a timezone")
    return parsed.astimezone(timezone.utc)


def build_fixture_observations(count: int = 10) -> list[dict[str, Any]]:
    """Build a bounded synthetic batch; each document remains source-grain only."""
    if count < 1 or count > 20:
        raise ValueError("fixture count must be between 1 and 20")
    raw_rows: list[dict[str, Any]] = []
    for index in range(count):
        raw_rows.append({
            "address_raw": f"{100 + index} Example Avenue, Toronto, ON A1A 1A{index % 10}",
            "unit_raw": f"UNIT {index + 1}",
            "operating_name_raw": f"Example Works {index + 1}",
            "legal_name_raw": f"Example Holdings {index + 1} Inc",
            "licence_number_raw": f"SYN-{index + 1:04d}",
        })
    raw_blobs = [canonical_bytes(row) for row in raw_rows]
    raw_hashes = [hashlib.sha256(blob).hexdigest() for blob in raw_blobs]
    source_snapshot_sha256 = digest_json({
        "contract_scope": SCOPE,
        "snapshot_id": "SYNTHETIC-SOURCE-SNAPSHOT-001",
        "raw_record_sha256": sorted(raw_hashes),
    })
    source_registry_sha256 = digest_file(ROOT / "artifacts/research/source_feasibility_registry.json")
    field_map_sha256 = digest_file(ROOT / "artifacts/research/canonical_field_map.json")
    observations: list[dict[str, Any]] = []
    for index, (row, blob, raw_sha) in enumerate(zip(raw_rows, raw_blobs, raw_hashes)):
        second = f"{index:02d}"
        aliases = sorted({
            normalize_token(row["operating_name_raw"]),
            normalize_token(row["legal_name_raw"]),
            normalize_token(row["licence_number_raw"]),
        })
        observations.append({
            "document_kind": "THIN_SLICE_OBSERVATION",
            "schema_version": SCHEMA_VERSION,
            "decision_scope": SCOPE,
            "observation_id": f"OBS:SYN_{index + 1:04d}",
            "origin": {
                "mode": "SYNTHETIC_FIXTURE",
                "source_definition_id": "ON-SELECT",
                "dataset_id": "SYNTHETIC-ON-SELECT",
                "resource_id": "SYNTHETIC-LICENCE-RESOURCE",
                "source_snapshot_id": "SYNTHETIC-SOURCE-SNAPSHOT-001",
                "source_snapshot_sha256": source_snapshot_sha256,
                "source_registry_version": "2.0.0",
                "source_registry_sha256": source_registry_sha256,
                "canonical_field_map_version": "2.0.0",
                "canonical_field_map_sha256": field_map_sha256,
            },
            "native_identity": {
                "native_grain": "source_record",
                "native_key": row["licence_number_raw"],
                "native_key_sha256": digest_json({"licence_number_raw": row["licence_number_raw"]}),
            },
            "raw_record": {
                "media_type": "application/json",
                "bytes_base64": base64.b64encode(blob).decode("ascii"),
                "bytes_sha256": raw_sha,
                **row,
            },
            "clocks": {
                "event": {"state": "UNKNOWN", "at": None, "raw": None},
                "publisher_effective": {"state": "UNKNOWN", "at": None, "raw": None},
                "published": {"state": "UNKNOWN", "at": None, "raw": None},
                "retrieved_at": f"2026-07-31T12:00:{second}Z",
                "observed_at": f"2026-07-31T12:01:{second}Z",
                "ingested_at": f"2026-07-31T12:02:{second}Z",
                "validation_completed_at": f"2026-07-31T12:03:{second}Z",
                "available_at": f"2026-07-31T12:03:{second}Z",
                "stage1_cutoff": "2026-07-31T23:00:00Z",
            },
            "normalized_alias_tokens": aliases,
            "evidence_stage": 1,
            "lineage": {"input_classification": "CODEX_DERIVABLE", "fixture_builder_version": "contract-fixture-builder-v1"},
            "quality": {"synthetic_fixture": True, "identity_claim": "SOURCE_RECORD_ONLY"},
            "owner": {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"},
            "live_authority_granted": False,
        })
    return observations


def build_candidate(observation: dict[str, Any], protected_tokens: list[str], bundle_complete: bool = True) -> dict[str, Any]:
    """Create one explicit synthetic identity assertion and MATH projection."""
    raw = observation["raw_record"]
    normalized_address = normalize_token(raw["address_raw"])
    normalized_unit = normalize_token(raw["unit_raw"]) if raw["unit_raw"] else None
    location_id = physical_location_id(normalized_address, normalized_unit)
    local = observation["observation_id"].removeprefix("OBS:")
    available_at = observation["clocks"]["available_at"]
    aliases = sorted(observation["normalized_alias_tokens"])
    protected_set = set(protected_tokens)
    matches = sorted(set(aliases) & protected_set)
    protection_status = "UNKNOWN" if not bundle_complete else "PROTECTED" if matches else "CLEAR"
    evaluation_state = "PASS" if bundle_complete else "UNKNOWN"
    grain_ids = {
        "legal_entity_id": f"LEGAL:{local}",
        "operating_business_id": f"BUSINESS:{local}",
        "brand_id": f"BRAND:{normalize_token(raw['operating_name_raw'])}",
        "establishment_id": f"ESTABLISHMENT:{local}",
        "unit_id": f"UNIT:{local}",
        "property_id": None,
        "parcel_id": None,
        "owner_id": None,
        "occupier_id": f"OCCUPIER:{local}",
        "parent_group_id": None,
    }
    gates = {name: evaluation_state for name in ["evidence", "identity", "eligibility", "safety", "access", "operational"]}
    bundle_sha = digest_json({"bundle_id": "SYNTHETIC-PROTECTED-BUNDLE", "complete": bundle_complete, "tokens": sorted(protected_tokens)})
    score_units = 1000 - int(local.split("_")[-1])
    math_candidate = {
        "candidate_id": f"CAND:{local}",
        "physical_location_id": location_id,
        "grain_ids": grain_ids,
        "protection_tokens": aliases,
        "evidence_stage": 1,
        "observed_at": available_at,
        "gates": gates,
        "protected_status": protection_status,
        "value_state": "REGISTERED_SYNTHETIC_PROXY",
        "business_value_units": score_units,
        "proximity_cost_units": int(local.split("_")[-1]),
        "service_minutes": 10,
        "composition_group": None,
    }
    return {
        "document_kind": "THIN_SLICE_CANDIDATE",
        "schema_version": SCHEMA_VERSION,
        "decision_scope": SCOPE,
        "candidate_id": math_candidate["candidate_id"],
        "lineage": {
            "observation_id": observation["observation_id"],
            "observation_sha256": digest_json(observation),
            "source_snapshot_sha256": observation["origin"]["source_snapshot_sha256"],
            "adapter_version": ADAPTER_VERSION,
            "adapter_sha256": _adapter_sha256(),
        },
        "identity": {
            "mode": "SYNTHETIC_IDENTITY_ASSERTION",
            "assertion_id": f"IDENT:{local}",
            "resolved_at": available_at,
            "physical_location_basis": {
                "method_version": LOCATION_METHOD_VERSION,
                "normalized_address": normalized_address,
                "normalized_unit": normalized_unit,
            },
            "physical_location_id": location_id,
            "alias_tokens": aliases,
            "grain_ids": grain_ids,
        },
        "protection": {
            "bundle_id": "SYNTHETIC-PROTECTED-BUNDLE",
            "bundle_sha256": bundle_sha,
            "bundle_complete": bundle_complete,
            "token_extraction_complete": True,
            "evaluated_at": available_at,
            "candidate_tokens": aliases,
            "matched_tokens": matches,
            "status": protection_status,
        },
        "evaluations": {name: {"state": state, "evaluated_at": available_at} for name, state in gates.items()},
        "score": {
            "state": "REGISTERED_SYNTHETIC_PROXY",
            "policy_version": "synthetic-score-v1",
            "policy_sha256": digest_json({"policy_version": "synthetic-score-v1", "meaning": "fixture ordinal only"}),
            "computed_at": available_at,
            "business_value_units": score_units,
            "proximity_cost_units": int(local.split("_")[-1]),
            "service_minutes": 10,
            "composition_group": None,
        },
        "available_at": available_at,
        "stage1_cutoff": observation["clocks"]["stage1_cutoff"],
        "math_candidate": math_candidate,
        "quality": {"synthetic_fixture": True, "identity_claim": "SYNTHETIC_ONLY_NOT_REAL_ENTITY_TRUTH"},
        "owner": {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"},
        "live_issuance_authorized": False,
    }


def build_spine_from_observations(source_observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay the downstream spine from supplied synthetic observations."""
    observations = sorted(source_observations, key=lambda row: row["observation_id"])
    if not observations or len(observations) > 20:
        raise ValueError("observation count must be between 1 and 20")
    protected_tokens: list[str] = []
    candidates = sorted((build_candidate(row, protected_tokens) for row in observations), key=lambda row: row["candidate_id"])
    candidate_snapshot_sha256 = digest_json({
        "contract_version": SCHEMA_VERSION,
        "stage1_cutoff": "2026-07-31T23:00:00Z",
        "source_snapshot_sha256": observations[0]["origin"]["source_snapshot_sha256"],
        "adapter_version": ADAPTER_VERSION,
        "adapter_sha256": _adapter_sha256(),
        "candidates": [[row["candidate_id"], digest_json(row)] for row in candidates],
    })
    policy = {
        "policy_version": "math-policy-v1",
        "policy_sha256": "",
        "epsilon_business_value_units": 0,
        "maximum_candidates": 20,
        "max_total_service_minutes": 200,
        "composition_caps": {},
        "required_unique_grains": [],
        "incompatible_candidate_pairs": [],
        "redundancy_penalties": [],
        "interference_penalties": [],
    }
    policy["policy_sha256"] = digest_json({key: value for key, value in policy.items() if key != "policy_sha256"})
    problem = {
        "schema_version": "1.0.0",
        "decision_scope": SCOPE,
        "decision_id": "DECISION:SYNTHETIC_ROUTE_DAY_001",
        "snapshot": {
            "snapshot_id": "CANDIDATE-SNAPSHOT-001",
            "snapshot_sha256": candidate_snapshot_sha256,
            "stage1_cutoff": "2026-07-31T23:00:00Z",
            "issued_at": "2026-07-31T23:30:00Z",
            "protected_bundle_complete": True,
            "protected_tokens": protected_tokens,
        },
        "route_day": {"representative_id": "REP:SYNTHETIC_001", "route_date": "2026-08-01"},
        "policy": policy,
        "candidates": [row["math_candidate"] for row in candidates],
    }
    decision = decide(problem)
    schema_paths = {
        "observation": "contracts/thin_slice_observation.schema.json",
        "candidate": "contracts/thin_slice_candidate.schema.json",
        "math_problem": "contracts/math_decision_policy.schema.json",
        "math_decision": "contracts/math_route_decision.schema.json",
    }
    schema_bindings = {name: {"path": path, "schema_version": "1.0.0", "sha256": digest_file(ROOT / path)} for name, path in schema_paths.items()}
    return {
        "document_kind": "THIN_SLICE_SPINE",
        "schema_version": SCHEMA_VERSION,
        "decision_scope": SCOPE,
        "contract_id": "CONTRACT-001-SPINE-V1",
        "canonicalization": "SORTED_KEYS_INTEGER_JSON_V1",
        "normalizer_version": NORMALIZER_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "adapter_sha256": _adapter_sha256(),
        "supported_version_transition": {"observation": "1.0.0", "candidate": "1.0.0", "math_problem": "1.0.0", "math_decision": "1.0.0"},
        "schema_bindings": schema_bindings,
        "source_snapshot_sha256": observations[0]["origin"]["source_snapshot_sha256"],
        "candidate_snapshot_sha256": candidate_snapshot_sha256,
        "protected_bundle": {"bundle_id": "SYNTHETIC-PROTECTED-BUNDLE", "complete": True, "tokens": protected_tokens},
        "observations": observations,
        "candidates": candidates,
        "math_problem": problem,
        "math_decision": decision,
        "replay_receipt": {
            "source_snapshot_sha256": observations[0]["origin"]["source_snapshot_sha256"],
            "candidate_snapshot_sha256": candidate_snapshot_sha256,
            "math_problem_sha256": digest_json(problem),
            "math_decision_sha256": digest_json(decision),
            "policy_sha256": policy["policy_sha256"],
            "selected_candidate_ids": [row["candidate_id"] for row in decision["selected"]],
            "result": decision["decision"],
        },
        "proof": {
            "level": 4,
            "claim": "synthetic contract conformance only",
            "focal_observation_id": observations[0]["observation_id"],
            "real_world_identity_proven": False,
            "live_issuance_authorized": False,
        },
    }


def build_spine(count: int = 10) -> dict[str, Any]:
    return build_spine_from_observations(build_fixture_observations(count))
