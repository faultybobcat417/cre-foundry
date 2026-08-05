"""Deterministic synthetic route-day, field-event, and F9 outcome slice.

No document produced here describes real source data, real identity, real
protected-account clearance, real travel feasibility, real outreach, or an
empirical outcome. Stage-2 and Stage-3 documents append to the immutable
Stage-1 spine and never feed back into it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cre_foundry.contracts.thin_slice import (
    build_fixture_observations,
    build_spine_from_observations,
    digest_file,
    digest_json,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "1.0.0"
EXECUTION_SCOPE = "SYNTHETIC_NON_INFLUENCING"
CANONICALIZATION = "SORTED_KEYS_INTEGER_JSON_V1"
BUILDER_VERSION = "vertical-shadow-builder-v1"
OWNER = {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"}


def _builder_sha256() -> str:
    return digest_file(Path(__file__))


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must contain timezone")
    return parsed.astimezone(timezone.utc)


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _schema_bindings() -> dict[str, dict[str, str]]:
    paths = {
        "route_day": "contracts/synthetic_route_day.schema.json",
        "field_event": "contracts/synthetic_field_event.schema.json",
        "f9_outcome": "contracts/synthetic_f9_outcome.schema.json",
    }
    return {
        name: {"path": path, "schema_version": SCHEMA_VERSION, "sha256": digest_file(ROOT / path)}
        for name, path in paths.items()
    }


def _route_manifest(spine: dict[str, Any]) -> dict[str, Any]:
    decision = spine["math_decision"]
    problem = spine["math_problem"]
    receipt = spine["replay_receipt"]
    candidates = {row["candidate_id"]: row for row in spine["candidates"]}
    stops = []
    for index, selected in enumerate(decision["selected"], start=1):
        candidate = candidates[selected["candidate_id"]]
        stops.append({
            "sequence_position": index,
            "candidate_id": selected["candidate_id"],
            "physical_location_id": selected["physical_location_id"],
            "synthetic_service_minutes": candidate["math_candidate"]["service_minutes"],
            "synthetic_travel_minutes_from_previous": 0 if index == 1 else 5,
            "stop_feasibility_state": "SYNTHETIC_FIXTURE_PASS",
        })
    return {
        "document_kind": "SYNTHETIC_ROUTE_DAY",
        "schema_version": SCHEMA_VERSION,
        "execution_scope": EXECUTION_SCOPE,
        "route_manifest_id": "ROUTE:SYNTHETIC_ROUTE_DAY_001",
        "upstream_binding": {
            "source_snapshot_sha256": spine["source_snapshot_sha256"],
            "candidate_snapshot_sha256": spine["candidate_snapshot_sha256"],
            "math_problem_sha256": receipt["math_problem_sha256"],
            "math_decision_sha256": receipt["math_decision_sha256"],
            "decision_id": problem["decision_id"],
            "policy_version": problem["policy"]["policy_version"],
            "policy_sha256": problem["policy"]["policy_sha256"],
            "upstream_decision_scope": problem["decision_scope"],
        },
        "representative_id": problem["route_day"]["representative_id"],
        "route_date": problem["route_day"]["route_date"],
        "issued_at": "2026-07-31T23:45:00Z",
        "route_status": "ISSUED_SYNTHETIC",
        "stop_count": 10,
        "route_order_state": "CANONICAL_SYNTHETIC_NOT_TRAVEL_OPTIMIZED",
        "feasibility_claim": "SYNTHETIC_FIXTURE_ONLY",
        "stops": stops,
        "quality": {"synthetic_fixture": True, "real_route_feasibility_proven": False},
        "owner": OWNER,
        "live_issuance_authorized": False,
    }


def _field_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    route_sha = digest_json(route)
    issued = _time(route["issued_at"])
    route_start = datetime.fromisoformat(route["route_date"]).replace(tzinfo=timezone.utc) + timedelta(hours=10)
    if route_start <= issued:
        raise ValueError("synthetic route day must begin after issuance")
    events = []
    for index, stop in enumerate(route["stops"]):
        occurred = route_start + timedelta(minutes=20 * index)
        recorded = occurred + timedelta(minutes=1)
        ingested = occurred + timedelta(minutes=2)
        validated = occurred + timedelta(minutes=3)
        event_id = f"FIELD_EVENT:SYN_{index + 1:04d}"
        result = "CONTACT_MADE_SYNTHETIC" if index == 0 else "CONTACT_ATTEMPTED_SYNTHETIC" if index % 2 else "NO_CONTACT_SYNTHETIC"
        payload_sha = digest_json({"event_id": event_id, "candidate_id": stop["candidate_id"], "event_result": result})
        events.append({
            "document_kind": "SYNTHETIC_FIELD_EVENT",
            "schema_version": SCHEMA_VERSION,
            "execution_scope": EXECUTION_SCOPE,
            "evidence_stage": 2,
            "event_id": event_id,
            "route_binding": {
                "route_manifest_id": route["route_manifest_id"],
                "route_manifest_sha256": route_sha,
                "candidate_snapshot_sha256": route["upstream_binding"]["candidate_snapshot_sha256"],
                "math_decision_sha256": route["upstream_binding"]["math_decision_sha256"],
            },
            "representative_id": route["representative_id"],
            "route_date": route["route_date"],
            "stop": {
                "sequence_position": stop["sequence_position"],
                "candidate_id": stop["candidate_id"],
                "physical_location_id": stop["physical_location_id"],
            },
            "event_type": "FIRST_TOUCH_VISIT",
            "event_result": result,
            "occurred_at": _z(occurred),
            "recorded_at": _z(recorded),
            "ingested_at": _z(ingested),
            "validation_completed_at": _z(validated),
            "available_at": _z(validated),
            "evidence": {"mode": "SYNTHETIC_FIXTURE", "payload_sha256": payload_sha},
            "quality": {"synthetic_fixture": True, "real_visit_proven": False},
            "owner": OWNER,
            "live_outreach_occurred": False,
        })
    return events


def _outcomes(route: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    route_sha = digest_json(route)
    outcomes = []
    downstream = {name: "UNKNOWN" for name in ["attendance", "mandate", "transaction", "commission", "referral", "repeat_value"]}
    for index, event in enumerate(events):
        started = _time(event["occurred_at"])
        ended = started + timedelta(days=30)
        positive = index == 0
        assessed = started + timedelta(hours=2) if positive else started + timedelta(days=1)
        if positive:
            booking_at = started + timedelta(hours=1)
            components = {
                "decision_maker": "CONFIRMED_SYNTHETIC",
                "cre_requirement": "CONFIRMED_SYNTHETIC",
                "appointment": "SCHEDULED_WITH_SENIOR_REALTOR_SYNTHETIC",
                "supporting_evidence": "ADJUDICABLE_SYNTHETIC_FIXTURE",
                "adjudication": "PASS_SYNTHETIC",
                "deduplication": "UNIQUE_SYNTHETIC",
            }
            state = "F9_CONFIRMED_SYNTHETIC"
            counted: bool | None = True
            ascertainment = "COMPLETE_SYNTHETIC"
            evidence_sha: str | None = digest_json({"outcome": "F9", "event_id": event["event_id"], "components": components})
        else:
            booking_at = None
            components = {
                "decision_maker": "UNKNOWN",
                "cre_requirement": "UNKNOWN",
                "appointment": "UNKNOWN",
                "supporting_evidence": "UNKNOWN",
                "adjudication": "UNKNOWN",
                "deduplication": "UNKNOWN",
            }
            state = "IMMATURE_UNKNOWN"
            counted = None
            ascertainment = "IMMATURE"
            evidence_sha = None
        outcomes.append({
            "document_kind": "SYNTHETIC_F9_OUTCOME",
            "schema_version": SCHEMA_VERSION,
            "execution_scope": EXECUTION_SCOPE,
            "evidence_stage": 3,
            "outcome_id": f"OUTCOME:SYN_{index + 1:04d}",
            "field_event_binding": {
                "event_id": event["event_id"],
                "field_event_sha256": digest_json(event),
                "route_manifest_sha256": route_sha,
                "candidate_snapshot_sha256": route["upstream_binding"]["candidate_snapshot_sha256"],
                "math_decision_sha256": route["upstream_binding"]["math_decision_sha256"],
            },
            "representative_id": route["representative_id"],
            "route_date": route["route_date"],
            "candidate_id": event["stop"]["candidate_id"],
            "physical_location_id": event["stop"]["physical_location_id"],
            "window": {
                "policy_version": "synthetic-f9-window-v1",
                "horizon_days": 30,
                "starts_at": event["occurred_at"],
                "ends_at": _z(ended),
                "ascertainment_state": ascertainment,
            },
            "assessed_at": _z(assessed),
            "booking_at": _z(booking_at) if booking_at else None,
            "qualification_evidence_sha256": evidence_sha,
            "censored_at": None,
            "censor_reason": None,
            "outcome_state": state,
            "counted_f9": counted,
            "components": components,
            "downstream_states": downstream,
            "quality": {"synthetic_fixture": True, "real_outcome_proven": False},
            "owner": OWNER,
            "empirical_claim_authorized": False,
        })
    return outcomes


def build_vertical_from_observations(source_observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay the connected vertical slice from supplied synthetic observations."""
    spine = build_spine_from_observations(source_observations)
    decision = spine["math_decision"]
    if decision["decision"] == "ISSUE":
        route = _route_manifest(spine)
        events = _field_events(route)
        outcomes = _outcomes(route, events)
    else:
        route, events, outcomes = None, [], []
    schema_bindings = _schema_bindings()
    route_sha = digest_json(route)
    receipt = {
        "builder_version": BUILDER_VERSION,
        "builder_sha256": _builder_sha256(),
        "contract_artifact_sha256": digest_file(ROOT / "artifacts/contracts/contract_spine.json"),
        "upstream_spine_sha256": digest_json(spine),
        "source_snapshot_sha256": spine["source_snapshot_sha256"],
        "candidate_snapshot_sha256": spine["candidate_snapshot_sha256"],
        "math_problem_sha256": spine["replay_receipt"]["math_problem_sha256"],
        "math_decision_sha256": spine["replay_receipt"]["math_decision_sha256"],
        "policy_sha256": spine["replay_receipt"]["policy_sha256"],
        "result": decision["decision"],
        "abstain_reason": decision.get("reason"),
        "route_manifest_sha256": route_sha,
        "field_event_digests": [{"event_id": row["event_id"], "sha256": digest_json(row)} for row in sorted(events, key=lambda row: row["event_id"])],
        "outcome_digests": [{"outcome_id": row["outcome_id"], "sha256": digest_json(row)} for row in sorted(outcomes, key=lambda row: row["outcome_id"])],
        "selected_candidate_ids": [row["candidate_id"] for row in decision["selected"]],
        "schema_sha256": {name: row["sha256"] for name, row in sorted(schema_bindings.items())},
    }
    return {
        "document_kind": "SYNTHETIC_VERTICAL_SLICE",
        "schema_version": SCHEMA_VERSION,
        "execution_scope": EXECUTION_SCOPE,
        "slice_id": "VERTICAL:SHADOW_SLICE_001",
        "canonicalization": CANONICALIZATION,
        "schema_bindings": schema_bindings,
        "upstream_spine": spine,
        "result": decision["decision"],
        "route_manifest": route,
        "field_events": events,
        "f9_outcomes": outcomes,
        "replay_receipt": receipt,
        "proof": {
            "level": 5,
            "claim": "deterministic synthetic source-to-route-to-field-outcome fixture conformance only",
            "real_source_proven": False,
            "real_identity_proven": False,
            "real_protection_clearance_proven": False,
            "real_route_feasibility_proven": False,
            "representative_usability_proven": False,
            "real_f9_outcome_proven": False,
            "incremental_lift_proven": False,
            "commercial_value_proven": False,
            "live_issuance_authorized": False,
            "fixture_horizon_is_authorized_policy": False,
        },
    }


def build_vertical_slice(count: int = 10) -> dict[str, Any]:
    return build_vertical_from_observations(build_fixture_observations(count))
