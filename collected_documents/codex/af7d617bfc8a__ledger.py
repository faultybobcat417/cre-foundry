"""Deterministic synthetic F9 evidence ledger and assessment projection.

This module proves synthetic state-machine and replay mechanics only. It does
not define a real F9 policy, establish label truth, estimate lift, or authorize
live use. Stage-3 records consume immutable upstream bindings and never mutate
Stage 1 or Stage 2.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from cre_foundry.contracts.thin_slice import digest_file, digest_json
from cre_foundry.vertical.shadow_slice import build_vertical_slice

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "artifacts/outcomes/synthetic_window_policy.json"
POLICY_SCHEMA_PATH = ROOT / "contracts/f9_window_policy.schema.json"
SCENARIO_PATH = ROOT / "artifacts/outcomes/scenario_matrix.json"
SCHEMA_PATH = ROOT / "contracts/f9_outcome.schema.json"
INPUT_SCHEMA_PATH = ROOT / "contracts/f9_outcome_input_ledger.schema.json"
EVALUATOR_CONTRACT_PATH = ROOT / "artifacts/outcomes/public_evaluator_contract.json"
BUILDER_VERSION = "outcomes-ledger-builder-v2"
CANONICALIZATION = "SORTED_KEYS_INTEGER_JSON_V1"
SCOPE = "SYNTHETIC_NON_INFLUENCING"
OWNER = {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"}

UNKNOWN_COMPONENTS = {
    "actor_role": "UNKNOWN", "requirement_type": "UNKNOWN", "appointment": "UNKNOWN",
    "supporting_evidence": "UNKNOWN", "adjudication": "UNKNOWN", "deduplication": "UNKNOWN",
}
NEGATIVE_COMPONENTS = {
    "actor_role": "UNKNOWN", "requirement_type": "UNKNOWN", "appointment": "NOT_OBSERVED_SYNTHETIC",
    "supporting_evidence": "ABSENT_SYNTHETIC", "adjudication": "FAIL_SYNTHETIC", "deduplication": "NO_BOOKING",
}
DOWNSTREAM_UNKNOWN = {name: "UNKNOWN" for name in [
    "attendance", "mandate", "transaction", "commission", "referral", "repeat_value",
    "predictive_validity", "incremental_lift", "net_commercial_value",
]}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_policy() -> dict[str, Any]:
    policy = _load(POLICY_PATH)
    schema = _load(POLICY_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    if next(iter(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(policy)), None) is not None:
        raise ValueError("synthetic policy schema violation")
    return policy


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    utc = parsed.astimezone(timezone.utc)
    if value != _z(utc):
        raise ValueError("noncanonical timestamp")
    return utc


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _assertion(
    unit_id: str,
    index: int,
    assertion_type: str,
    occurred_at: str,
    available_at: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    occurred = _time(occurred_at)
    available = _time(available_at)
    recorded = min(occurred + timedelta(minutes=1), available)
    ingested = min(max(recorded, occurred + timedelta(minutes=2)), available)
    validated = available
    return {
        "assertion_id": f"ASSERTION:{unit_id.removeprefix('OUTCOME_UNIT:')}:{index:02d}",
        "assertion_type": assertion_type,
        "outcome_unit_id": unit_id,
        "occurred_at": _z(occurred),
        "recorded_at": _z(recorded),
        "ingested_at": _z(ingested),
        "validation_completed_at": _z(validated),
        "available_at": _z(available),
        "payload": payload,
    }


def _f9_payload(booking_episode_id: str, confirmed_at: str, appointment_at: str) -> dict[str, Any]:
    core = {
        "source_namespace": "SYNTHETIC_CRM",
        "booking_episode_id": booking_episode_id,
        "booking_confirmed_at": confirmed_at,
        "appointment_scheduled_at": appointment_at,
        "actor_role": "RELEVANT_DECISION_MAKER",
        "requirement_type": "CURRENT_CRE_REQUIREMENT",
        "appointment": "SCHEDULED_WITH_IDENTIFIED_SENIOR_COMMERCIAL_REALTOR",
        "senior_commercial_realtor_id": "REALTOR:SYNTHETIC_SENIOR_001",
        "supporting_evidence": "INDEPENDENTLY_ADJUDICABLE_SYNTHETIC",
        "adjudication": "PASS_SYNTHETIC",
    }
    return {**core, "supporting_evidence_sha256": digest_json(core)}


def _stopper_evidence_sha256(unit_id: str, assertion_type: str, cause: str, occurred_at: str) -> str:
    return digest_json({
        "outcome_unit_id": unit_id,
        "assertion_type": assertion_type,
        "cause": cause,
        "occurred_at": occurred_at,
        "synthetic_evidence_kind": "REGISTERED_STOPPING_EVENT_FIXTURE",
    })


def _scenario_assertions(unit_id: str, scenario: dict[str, Any], route_date: str) -> list[dict[str, Any]]:
    kind = scenario["scenario"]
    booking_id = scenario.get("booking_episode_id")
    base = datetime.fromisoformat(route_date).replace(tzinfo=timezone.utc)
    assertions: list[dict[str, Any]] = []
    if kind in {"F9_UNIQUE", "F9_DEDUPE_CANONICAL", "F9_DEDUPE_COLLISION"}:
        confirmed = base + timedelta(days=1 if kind == "F9_UNIQUE" else 2, hours=11)
        assertions.append(_assertion(
            unit_id, 1, "F9_EVIDENCE", _z(confirmed), _z(confirmed + timedelta(hours=1)),
            _f9_payload(booking_id, _z(confirmed), _z(confirmed + timedelta(days=2))),
        ))
    elif kind == "MATURE_NEGATIVE":
        end = base + timedelta(days=30)
        assertions.extend([
            _assertion(unit_id, 1, "OBSERVATION_WATERMARK", _z(end), _z(end), {"observed_through_at": _z(end), "source_complete": True}),
            _assertion(unit_id, 2, "NEGATIVE_ADJUDICATION", _z(end), _z(end), {"verdict": "NO_QUALIFYING_F9_SYNTHETIC", "adjudication": "FAIL_SYNTHETIC"}),
        ])
    elif kind == "IMMATURE":
        observed = base + timedelta(days=2, hours=11)
        assertions.append(_assertion(unit_id, 1, "OBSERVATION_WATERMARK", _z(observed), _z(observed), {"observed_through_at": _z(observed), "source_complete": False}))
    elif kind == "CENSORED":
        stopped = base + timedelta(days=9, hours=11)
        occurred = _z(stopped)
        cause = "SYNTHETIC_LOSS_TO_FOLLOW_UP"
        assertions.append(_assertion(unit_id, 1, "CENSORING", occurred, _z(stopped + timedelta(hours=1)), {"cause": cause, "evidence_sha256": _stopper_evidence_sha256(unit_id, "CENSORING", cause, occurred)}))
    elif kind == "COMPETING_EVENT":
        stopped = base + timedelta(days=11, hours=11)
        occurred = _z(stopped)
        cause = "SYNTHETIC_TERMINAL_CLOSURE"
        assertions.append(_assertion(unit_id, 1, "COMPETING_EVENT", occurred, _z(stopped + timedelta(hours=1)), {"cause": cause, "evidence_sha256": _stopper_evidence_sha256(unit_id, "COMPETING_EVENT", cause, occurred), "adjudication": "PASS_SYNTHETIC"}))
    elif kind == "TIED_CONFLICT":
        tied = base + timedelta(days=4, hours=11)
        occurred = _z(tied)
        cause = "SYNTHETIC_SOURCE_OUTAGE"
        assertions.extend([
            _assertion(unit_id, 1, "F9_EVIDENCE", occurred, _z(tied + timedelta(hours=1)), _f9_payload(booking_id, occurred, _z(tied + timedelta(days=2)))),
            _assertion(unit_id, 2, "CENSORING", occurred, _z(tied + timedelta(hours=1)), {"cause": cause, "evidence_sha256": _stopper_evidence_sha256(unit_id, "CENSORING", cause, occurred)}),
        ])
    elif kind == "UNKNOWN_INPUT":
        occurred = base + timedelta(days=1)
        assertions.append(_assertion(unit_id, 1, "UNKNOWN_INPUT", _z(occurred), _z(occurred + timedelta(hours=1)), {"missing": "AUTHORIZED_POLICY_OR_BINDING"}))
    elif kind == "CORRECTED_CONFLICT_TO_F9":
        conflict_at = base + timedelta(days=2, hours=11)
        conflict = _assertion(unit_id, 1, "CONFLICT", _z(conflict_at), _z(conflict_at + timedelta(hours=1)), {"reason": "SYNTHETIC_CONFLICTING_BOOKING_EVIDENCE"})
        correction_at = base + timedelta(days=4, hours=11)
        correction = _assertion(unit_id, 2, "CORRECTION", _z(correction_at), _z(correction_at + timedelta(hours=1)), {
            "action": "RETRACT",
            "corrects_assertion_id": conflict["assertion_id"],
            "corrects_assertion_sha256": digest_json(conflict),
            "reason": "SYNTHETIC_ADJUDICATED_RETRACTION",
        })
        confirmed = base + timedelta(days=4, hours=12)
        f9 = _assertion(unit_id, 3, "F9_EVIDENCE", _z(confirmed), _z(confirmed + timedelta(hours=1)), _f9_payload(booking_id, _z(confirmed), _z(confirmed + timedelta(days=2))))
        assertions.extend([conflict, correction, f9])
    else:
        raise ValueError(f"unsupported scenario {kind}")
    return assertions


def build_input_ledger() -> dict[str, Any]:
    """Build the immutable synthetic input ledger from the validated vertical slice."""
    vertical = build_vertical_slice(10)
    route = vertical["route_manifest"]
    policy = _load_policy()
    matrix = _load(SCENARIO_PATH)
    if route is None or vertical["result"] != "ISSUE":
        raise ValueError("canonical outcome fixture requires an issued synthetic route")
    stage1 = vertical["upstream_spine"]
    units = []
    for scenario in matrix["scenarios"]:
        index = scenario["unit_sequence"] - 1
        stop = route["stops"][index]
        event = vertical["field_events"][index]
        unit_id = f"OUTCOME_UNIT:ROUTE_DAY_001:{index + 1:02d}"
        units.append({
            "outcome_unit_id": unit_id,
            "sequence_position": index + 1,
            "binding": {
                "source_snapshot_sha256": stage1["source_snapshot_sha256"],
                "candidate_snapshot_sha256": stage1["candidate_snapshot_sha256"],
                "math_decision_sha256": stage1["replay_receipt"]["math_decision_sha256"],
                "route_manifest_sha256": digest_json(route),
                "field_event_id": event["event_id"],
                "field_event_sha256": digest_json(event),
                "candidate_id": stop["candidate_id"],
                "physical_location_id": stop["physical_location_id"],
                "representative_id": route["representative_id"],
                "route_date": route["route_date"],
            },
            "scenario": scenario["scenario"],
            "assessment_cutoffs": scenario["assessment_cutoffs"],
            "assertions": _scenario_assertions(unit_id, scenario, route["route_date"]),
        })
    return {
        "document_kind": "SYNTHETIC_OUTCOME_INPUT_LEDGER",
        "schema_version": "1.0.0",
        "execution_scope": SCOPE,
        "ledger_id": "OUTCOME_LEDGER:SYNTHETIC_ROUTE_DAY_001",
        "canonicalization": CANONICALIZATION,
        "policy_sha256": digest_json(policy),
        "vertical_slice_sha256": digest_json(vertical),
        "stage1_unchanged_sha256": digest_json(stage1),
        "route_assignment": {
            "assignment_id": "ROUTE_DAY_ASSIGNMENT:SYNTHETIC_001",
            "representative_id": route["representative_id"],
            "route_date": route["route_date"],
            "assigned_at": matrix["route_assignment_at"],
            "assignment_result": vertical["result"],
            "include_in_itt": True,
        },
        "units": sorted(units, key=lambda row: row["outcome_unit_id"]),
        "owner": OWNER,
        "live_data": False,
    }


def _active_assertions(unit: dict[str, Any], cutoff: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = sorted((row for row in unit["assertions"] if _time(row["available_at"]) <= _time(cutoff)), key=lambda row: row["assertion_id"])
    retracted = {
        row["payload"]["corrects_assertion_id"]
        for row in eligible
        if row["assertion_type"] == "CORRECTION" and row["payload"].get("action") == "RETRACT"
    }
    active = [row for row in eligible if row["assertion_type"] != "CORRECTION" and row["assertion_id"] not in retracted]
    return eligible, active


def _f9_components(payload: dict[str, Any], dedupe: str) -> dict[str, Any]:
    return {
        "actor_role": payload.get("actor_role", "UNKNOWN"),
        "requirement_type": payload.get("requirement_type", "UNKNOWN"),
        "appointment": payload.get("appointment", "UNKNOWN"),
        "supporting_evidence": payload.get("supporting_evidence", "UNKNOWN"),
        "adjudication": payload.get("adjudication", "UNKNOWN"),
        "deduplication": dedupe,
    }


def _booking_groups_at(ledger: dict[str, Any], cutoff: str) -> dict[str, list[str]]:
    groups: dict[str, set[str]] = {}
    for unit in ledger["units"]:
        _, active = _active_assertions(unit, cutoff)
        for assertion in active:
            if assertion["assertion_type"] == "F9_EVIDENCE":
                booking_id = assertion["payload"]["booking_episode_id"]
                groups.setdefault(booking_id, set()).add(unit["outcome_unit_id"])
    return {key: sorted(value) for key, value in sorted(groups.items())}


def _current_booking_groups(ledger: dict[str, Any]) -> dict[str, list[str]]:
    cutoffs = {max(unit["assessment_cutoffs"], key=_time) for unit in ledger["units"]}
    if len(cutoffs) != 1:
        raise ValueError("current route-day heads require one common as-of cutoff")
    return _booking_groups_at(ledger, cutoffs.pop())


def _canonicalize_ledger(input_ledger: dict[str, Any]) -> dict[str, Any]:
    ledger = json.loads(json.dumps(input_ledger))
    canonical_units = []
    for unit in ledger["units"]:
        by_id: dict[str, dict[str, Any]] = {}
        for assertion in unit["assertions"]:
            assertion_id = assertion["assertion_id"]
            if assertion_id in by_id and by_id[assertion_id] != assertion:
                raise ValueError("conflicting duplicate assertion id")
            by_id[assertion_id] = assertion
        unit["assertions"] = [by_id[key] for key in sorted(by_id)]
        unit["assessment_cutoffs"] = sorted(set(unit["assessment_cutoffs"]))
        canonical_units.append(unit)
    ledger["units"] = sorted(canonical_units, key=lambda row: row["outcome_unit_id"])
    return ledger


def _validate_input_ledger(ledger: dict[str, Any], *, require_frozen: bool) -> None:
    schema = _load(INPUT_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if next(iter(validator.iter_errors(ledger)), None) is not None:
        raise ValueError("input ledger schema violation")
    policy = _load_policy()
    if ledger["policy_sha256"] != digest_json(policy):
        raise ValueError("policy binding mismatch")
    vertical = build_vertical_slice(10)
    route = vertical["route_manifest"]
    assignment = ledger["route_assignment"]
    assigned = _time(assignment["assigned_at"])
    first_event = min(_time(row["occurred_at"]) for row in vertical["field_events"])
    if (
        assignment["representative_id"] != route["representative_id"]
        or assignment["route_date"] != route["route_date"]
        or assigned.date().isoformat() != route["route_date"]
        or not _time(route["issued_at"]) <= assigned <= first_event
    ):
        raise ValueError("route assignment chronology mismatch")
    start = assigned
    end = start + timedelta(days=policy["horizon_days"])
    matrix = _load(SCENARIO_PATH)
    common_heads = {max(unit["assessment_cutoffs"], key=_time) for unit in ledger["units"]}
    if common_heads != {matrix["aggregate_as_of"]}:
        raise ValueError("route-day heads do not share registered aggregate as-of")
    for unit in ledger["units"]:
        if unit["outcome_unit_id"] != f"OUTCOME_UNIT:ROUTE_DAY_001:{unit['sequence_position']:02d}":
            raise ValueError("unit sequence binding mismatch")
        cutoffs = [_time(value) for value in unit["assessment_cutoffs"]]
        if cutoffs != sorted(cutoffs) or any(value < assigned for value in cutoffs):
            raise ValueError("assessment cutoff chronology mismatch")
        by_id = {row["assertion_id"]: row for row in unit["assertions"]}
        corrected: set[str] = set()
        for assertion in unit["assertions"]:
            if assertion["outcome_unit_id"] != unit["outcome_unit_id"]:
                raise ValueError("assertion unit binding mismatch")
            clocks = [_time(assertion[name]) for name in ["occurred_at", "recorded_at", "ingested_at", "validation_completed_at", "available_at"]]
            if clocks != sorted(clocks) or clocks[0] < assigned:
                raise ValueError("assertion clock chronology mismatch")
            kind = assertion["assertion_type"]
            payload = assertion["payload"]
            if kind == "F9_EVIDENCE":
                confirmed = _time(payload["booking_confirmed_at"])
                appointment = _time(payload["appointment_scheduled_at"])
                evidence_core = {key: value for key, value in payload.items() if key != "supporting_evidence_sha256"}
                if (
                    confirmed != clocks[0]
                    or confirmed > clocks[-1]
                    or appointment < confirmed
                    or not payload["senior_commercial_realtor_id"].strip()
                    or payload["supporting_evidence_sha256"] != digest_json(evidence_core)
                ):
                    raise ValueError("invalid F9 evidence semantics")
            elif kind == "OBSERVATION_WATERMARK":
                if _time(payload["observed_through_at"]) != clocks[0] or _time(payload["observed_through_at"]) > clocks[-1]:
                    raise ValueError("invalid observation watermark")
            elif kind == "NEGATIVE_ADJUDICATION":
                if clocks[0] < end:
                    raise ValueError("premature negative adjudication")
            elif kind in {"CENSORING", "COMPETING_EVENT"}:
                if not start <= clocks[0] <= end:
                    raise ValueError("stopping event outside registered window")
                if payload["evidence_sha256"] != _stopper_evidence_sha256(unit["outcome_unit_id"], kind, payload["cause"], assertion["occurred_at"]):
                    raise ValueError("invalid stopping-event evidence digest")
            elif kind == "CORRECTION":
                target_id = payload["corrects_assertion_id"]
                target = by_id.get(target_id)
                if (
                    target is None
                    or target["outcome_unit_id"] != unit["outcome_unit_id"]
                    or target["assertion_type"] == "CORRECTION"
                    or target_id in corrected
                    or payload["corrects_assertion_sha256"] != digest_json(target)
                    or _time(target["available_at"]) > clocks[0]
                ):
                    raise ValueError("invalid correction lineage")
                corrected.add(target_id)
    if require_frozen:
        expected = _canonicalize_ledger(build_input_ledger())
        if ledger != expected:
            raise ValueError("input ledger differs from frozen canonical ledger")


def _project_revision(
    unit: dict[str, Any], cutoff: str, revision: int, predecessor: dict[str, Any] | None,
    policy: dict[str, Any], ledger: dict[str, Any],
) -> dict[str, Any]:
    eligible, active = _active_assertions(unit, cutoff)
    booking_groups = _booking_groups_at(ledger, cutoff)
    start = _time(ledger["route_assignment"]["assigned_at"])
    end = start + timedelta(days=policy["horizon_days"])
    f9s = sorted((row for row in active if row["assertion_type"] == "F9_EVIDENCE"), key=lambda row: (row["payload"]["booking_confirmed_at"], row["assertion_id"]))
    stoppers = sorted((row for row in active if row["assertion_type"] in {"CENSORING", "COMPETING_EVENT"}), key=lambda row: (row["occurred_at"], row["assertion_id"]))
    watermark_rows = [row for row in active if row["assertion_type"] == "OBSERVATION_WATERMARK"]
    observed = max((_time(row["payload"]["observed_through_at"]) for row in watermark_rows), default=start)
    complete_through_end = any(
        row["payload"]["source_complete"] is True and _time(row["payload"]["observed_through_at"]) >= end
        for row in watermark_rows
    )
    unknown = any(row["assertion_type"] == "UNKNOWN_INPUT" for row in active)
    explicit_conflict = any(row["assertion_type"] == "CONFLICT" for row in active)
    negative_adjudicated = any(row["assertion_type"] == "NEGATIVE_ADJUDICATION" and row["payload"].get("adjudication") == "FAIL_SYNTHETIC" for row in active)
    f9 = f9s[0] if f9s else None
    stopper = stoppers[0] if stoppers else None
    collision = False
    canonical_unit = None
    if f9 is not None:
        booking_id = f9["payload"]["booking_episode_id"]
        canonical_unit = min(booking_groups[booking_id])
        collision = canonical_unit != unit["outcome_unit_id"]
    tied = f9 is not None and stopper is not None and _time(f9["payload"]["booking_confirmed_at"]) == _time(stopper["occurred_at"])
    f9_before_stopper = f9 is not None and (stopper is None or _time(f9["payload"]["booking_confirmed_at"]) < _time(stopper["occurred_at"]))
    in_window = f9 is not None and start <= _time(f9["payload"]["booking_confirmed_at"]) <= end
    if unknown:
        state, counted, ascertainment = "UNKNOWN", None, "UNKNOWN"
    elif explicit_conflict or collision or tied:
        state, counted, ascertainment = "CONFLICTED_UNKNOWN", None, "CONFLICTED"
    elif f9_before_stopper and in_window:
        state, counted, ascertainment = "F9_CONFIRMED_SYNTHETIC", True, "EVENT_CONFIRMED"
    elif stopper is not None and stopper["assertion_type"] == "CENSORING":
        state, counted, ascertainment = "CENSORED_UNKNOWN", None, "CENSORED"
    elif stopper is not None:
        state, counted, ascertainment = "COMPETING_EVENT_UNKNOWN", None, "COMPETING"
    elif _time(cutoff) < end or observed < end or not complete_through_end:
        state, counted, ascertainment = "IMMATURE_UNKNOWN", None, "WINDOW_OPEN"
    elif negative_adjudicated:
        state, counted, ascertainment = "MATURE_NO_F9_SYNTHETIC", False, "WINDOW_COMPLETE"
    else:
        state, counted, ascertainment = "UNKNOWN", None, "UNKNOWN"

    booking = None
    components = dict(UNKNOWN_COMPONENTS)
    stopping_event = None
    if state == "F9_CONFIRMED_SYNTHETIC":
        payload = f9["payload"]
        booking = {
            "booking_episode_id": payload["booking_episode_id"],
            "booking_dedup_key": digest_json({"source_namespace": payload["source_namespace"], "booking_episode_id": payload["booking_episode_id"]}),
            "booking_confirmed_at": payload["booking_confirmed_at"],
            "appointment_scheduled_at": payload["appointment_scheduled_at"],
            "senior_commercial_realtor_id": payload["senior_commercial_realtor_id"],
            "supporting_evidence_sha256": payload["supporting_evidence_sha256"],
            "canonical_outcome_unit_id": unit["outcome_unit_id"],
        }
        components = _f9_components(payload, "CANONICAL_BOOKING_EPISODE")
    elif state == "MATURE_NO_F9_SYNTHETIC":
        components = dict(NEGATIVE_COMPONENTS)
    elif collision:
        components["deduplication"] = "COLLISION_UNRESOLVED"
    if stopper is not None and state in {"CENSORED_UNKNOWN", "COMPETING_EVENT_UNKNOWN"}:
        stopping_event = {
            "type": "CENSORING" if stopper["assertion_type"] == "CENSORING" else "COMPETING_EVENT",
            "cause": stopper["payload"]["cause"],
            "occurred_at": stopper["occurred_at"],
            "evidence_sha256": stopper["payload"]["evidence_sha256"],
        }
    predecessor_ref = None if predecessor is None else {"assessment_id": predecessor["assessment_id"], "sha256": digest_json(predecessor)}
    return {
        "document_kind": "SYNTHETIC_F9_ASSESSMENT_REVISION",
        "schema_version": "1.0.0",
        "execution_scope": SCOPE,
        "assessment_id": f"ASSESSMENT:{unit['outcome_unit_id'].removeprefix('OUTCOME_UNIT:')}:{revision:02d}",
        "outcome_unit_id": unit["outcome_unit_id"],
        "revision": revision,
        "predecessor": predecessor_ref,
        "binding": unit["binding"],
        "window": {
            "policy_id": policy["policy_id"], "policy_version": policy["policy_version"], "policy_sha256": digest_json(policy),
            "assignment_id": ledger["route_assignment"]["assignment_id"],
            "anchor_type": policy["primary_window_anchor"], "anchor_at": _z(start), "starts_at": _z(start), "ends_at": _z(end),
            "horizon_days": policy["horizon_days"], "interval_convention": policy["interval_convention"],
            "reporting_grace_seconds": policy["reporting_grace_seconds"], "real_policy_authorized": False,
        },
        "ledger_snapshot_sha256": digest_json({"unit": unit["outcome_unit_id"], "as_of": cutoff, "eligible_assertions": eligible}),
        "dedupe_snapshot_sha256": digest_json(booking_groups),
        "eligible_assertions": [{"assertion_id": row["assertion_id"], "sha256": digest_json(row), "available_at": row["available_at"]} for row in eligible],
        "assessed_at": cutoff,
        "observed_through_at": _z(observed),
        "assessment_state": state,
        "counted_f9": counted,
        "event_ascertainment_state": ascertainment,
        "booking_episode": booking,
        "components": components,
        "stopping_event": stopping_event,
        "transition_reason": (
            "INITIAL_PROJECTION" if predecessor is None
            else "APPEND_ONLY_CORRECTION" if any(
                row["assertion_type"] == "CORRECTION"
                and row["assertion_id"] not in {prior["assertion_id"] for prior in predecessor["eligible_assertions"]}
                for row in eligible
            )
            else "LATE_AVAILABLE_EVIDENCE" if {row["assertion_id"] for row in eligible} != {prior["assertion_id"] for prior in predecessor["eligible_assertions"]}
            else "SCHEDULED_REASSESSMENT"
        ),
        "downstream_states": dict(DOWNSTREAM_UNKNOWN),
        "quality": {"synthetic_fixture": True, "real_outcome_proven": False, "window_policy_authorized": False},
        "owner": OWNER,
        "empirical_claim_authorized": False,
    }


def build_outcome_run(input_ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project all synthetic assessment revisions and the route-day lower bound."""
    ledger = _canonicalize_ledger(build_input_ledger() if input_ledger is None else input_ledger)
    _validate_input_ledger(ledger, require_frozen=True)
    policy = _load_policy()
    assessments = []
    heads = []
    for unit in sorted(ledger["units"], key=lambda row: row["outcome_unit_id"]):
        predecessor = None
        for revision, cutoff in enumerate(unit["assessment_cutoffs"], start=1):
            assessment = _project_revision(unit, cutoff, revision, predecessor, policy, ledger)
            assessments.append(assessment)
            predecessor = assessment
        heads.append(predecessor)
    assessments.sort(key=lambda row: (row["outcome_unit_id"], row["revision"]))
    heads.sort(key=lambda row: row["outcome_unit_id"])
    groups = _current_booking_groups(ledger)
    dedupe_groups = []
    for booking_id, units in groups.items():
        canonical = min(units)
        dedupe_groups.append({
            "booking_episode_id": booking_id,
            "booking_dedup_key": digest_json({"source_namespace": "SYNTHETIC_CRM", "booking_episode_id": booking_id}),
            "outcome_unit_ids": units,
            "canonical_outcome_unit_id": canonical,
            "counted_units": 1 if any(row["outcome_unit_id"] == canonical and row["counted_f9"] is True for row in heads) else 0,
        })
    state_counts: dict[str, int] = {}
    for head in heads:
        state_counts[head["assessment_state"]] = state_counts.get(head["assessment_state"], 0) + 1
    lower_bound = sum(row["counted_f9"] is True for row in heads)
    final = all(row["assessment_state"] in {"F9_CONFIRMED_SYNTHETIC", "MATURE_NO_F9_SYNTHETIC"} for row in heads)
    aggregate = {
        "assignment_id": ledger["route_assignment"]["assignment_id"],
        "representative_id": ledger["route_assignment"]["representative_id"],
        "route_date": ledger["route_assignment"]["route_date"],
        "assignment_result": ledger["route_assignment"]["assignment_result"],
        "include_in_itt": ledger["route_assignment"]["include_in_itt"],
        "outcome_unit_count": len(heads),
        "confirmed_f9_lower_bound": lower_bound,
        "final_f9_count": lower_bound if final else None,
        "route_day_ascertainment_state": "FINAL" if final else "IMMATURE_PARTIAL",
        "state_counts": dict(sorted(state_counts.items())),
    }
    correction_edges = [
        {"assessment_id": row["assessment_id"], "predecessor": row["predecessor"]}
        for row in assessments if row["predecessor"] is not None
    ]
    receipt = {
        "builder_version": BUILDER_VERSION,
        "builder_sha256": digest_file(Path(__file__)),
        "canonicalization": CANONICALIZATION,
        "input_ledger_sha256": digest_json(ledger),
        "policy_sha256": digest_json(policy),
        "policy_schema_sha256": digest_file(POLICY_SCHEMA_PATH),
        "stage1_unchanged_sha256": ledger["stage1_unchanged_sha256"],
        "schema_sha256": digest_file(SCHEMA_PATH),
        "input_ledger_schema_sha256": digest_file(INPUT_SCHEMA_PATH),
        "evaluator_contract_sha256": digest_file(EVALUATOR_CONTRACT_PATH),
        "assessment_digests": [{"assessment_id": row["assessment_id"], "sha256": digest_json(row)} for row in assessments],
        "dedupe_groups_sha256": digest_json(dedupe_groups),
        "correction_lineage_root_sha256": digest_json(correction_edges),
        "current_label_vector_sha256": digest_json([{"outcome_unit_id": row["outcome_unit_id"], "counted_f9": row["counted_f9"]} for row in heads]),
        "route_day_aggregate_sha256": digest_json(aggregate),
        "state_counts": aggregate["state_counts"],
        "proof_level": 5,
    }
    return {
        "document_kind": "SYNTHETIC_OUTCOME_CONTRACT_RUN",
        "schema_version": "1.0.0",
        "execution_scope": SCOPE,
        "run_id": "OUTCOME_RUN:SYNTHETIC_ROUTE_DAY_001",
        "canonicalization": CANONICALIZATION,
        "schema_binding": {"path": "contracts/f9_outcome.schema.json", "schema_version": "1.0.0", "sha256": digest_file(SCHEMA_PATH)},
        "policy": policy,
        "input_ledger": ledger,
        "assessments": assessments,
        "current_heads": heads,
        "dedupe_groups": dedupe_groups,
        "route_day_aggregate": aggregate,
        "replay_receipt": receipt,
        "proof": {
            "level": 5,
            "claim": "synthetic outcome-state and replay contract conformance only",
            "real_f9_outcome_proven": False,
            "authorized_maturity_policy_proven": False,
            "label_accuracy_proven": False,
            "baseline_rate_proven": False,
            "predictive_validity_proven": False,
            "incremental_lift_proven": False,
            "commercial_value_proven": False,
            "live_use_authorized": False,
        },
    }


def build_itt_inclusion_cases() -> dict[str, Any]:
    """Freeze route-day ITT inclusion independently of adherence or issuance."""
    policy = _load_policy()
    cases = [
        {"case_id": "ISSUE_ADHERENT", "assignment_result": "ISSUE", "adherence_state": "ADHERENT_SYNTHETIC", "include_in_itt": True},
        {"case_id": "ISSUE_NONADHERENT", "assignment_result": "ISSUE", "adherence_state": "NONADHERENT_SYNTHETIC", "include_in_itt": True},
        {"case_id": "ABSTAIN_ROUTE_DAY", "assignment_result": "ABSTAIN_NO_VALID_TEN", "adherence_state": "NO_ROUTE_ISSUED", "include_in_itt": True},
    ]
    return {
        "artifact_id": "OUTCOMES-001-ITT-INCLUSION-CASES",
        "schema_version": "1.0.0",
        "execution_scope": SCOPE,
        "primary_estimand_unit": policy["primary_estimand_unit"],
        "policy_sha256": digest_json(policy),
        "cases": cases,
        "outcome_count_claimed": False,
        "claim": "Assignment inclusion only; outcome maturity and counts require separately adjudicated evidence.",
    }
