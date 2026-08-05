"""Independent evaluator for synthetic OUTCOMES-001 contracts.

This module intentionally does not import ``cre_foundry.outcomes``. It derives
assessment, dedupe, correction, route-day aggregate, and receipt semantics from
the frozen input ledger and policy.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "artifacts/outcomes/synthetic_window_policy.json"
POLICY_SCHEMA_PATH = ROOT / "contracts/f9_window_policy.schema.json"
SCENARIO_PATH = ROOT / "artifacts/outcomes/scenario_matrix.json"
INPUT_LEDGER_PATH = ROOT / "artifacts/outcomes/synthetic_input_ledger.json"
SCHEMA_PATH = ROOT / "contracts/f9_outcome.schema.json"
INPUT_SCHEMA_PATH = ROOT / "contracts/f9_outcome_input_ledger.schema.json"
EVALUATOR_CONTRACT_PATH = ROOT / "artifacts/outcomes/public_evaluator_contract.json"
BUILDER_PATH = ROOT / "src/cre_foundry/outcomes/ledger.py"
CANONICALIZATION = "SORTED_KEYS_INTEGER_JSON_V1"
SCOPE = "SYNTHETIC_NON_INFLUENCING"
TOP_FIELDS = {
    "document_kind", "schema_version", "execution_scope", "run_id", "canonicalization",
    "schema_binding", "policy", "input_ledger", "assessments", "current_heads",
    "dedupe_groups", "route_day_aggregate", "replay_receipt", "proof",
}
EXPECTED_PROOF = {
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
}
STATE_LABELS = {
    "F9_CONFIRMED_SYNTHETIC": True,
    "MATURE_NO_F9_SYNTHETIC": False,
    "IMMATURE_UNKNOWN": None,
    "CENSORED_UNKNOWN": None,
    "COMPETING_EVENT_UNKNOWN": None,
    "CONFLICTED_UNKNOWN": None,
    "UNKNOWN": None,
}
UNKNOWN_COMPONENTS = {
    "actor_role": "UNKNOWN", "requirement_type": "UNKNOWN", "appointment": "UNKNOWN",
    "supporting_evidence": "UNKNOWN", "adjudication": "UNKNOWN", "deduplication": "UNKNOWN",
}
NEGATIVE_COMPONENTS = {
    "actor_role": "UNKNOWN", "requirement_type": "UNKNOWN", "appointment": "NOT_OBSERVED_SYNTHETIC",
    "supporting_evidence": "ABSENT_SYNTHETIC", "adjudication": "FAIL_SYNTHETIC", "deduplication": "NO_BOOKING",
}
POSITIVE_COMPONENT_KEYS = {
    "actor_role": {"RELEVANT_DECISION_MAKER", "AUTHORIZED_REPRESENTATIVE"},
    "requirement_type": {"CURRENT_CRE_REQUIREMENT", "CREDIBLE_FUTURE_CRE_REQUIREMENT"},
    "appointment": {"SCHEDULED_WITH_IDENTIFIED_SENIOR_COMMERCIAL_REALTOR"},
    "supporting_evidence": {"INDEPENDENTLY_ADJUDICABLE_SYNTHETIC"},
    "adjudication": {"PASS_SYNTHETIC"},
    "deduplication": {"CANONICAL_BOOKING_EPISODE"},
}
DOWNSTREAM_FIELDS = {
    "attendance", "mandate", "transaction", "commission", "referral", "repeat_value",
    "predictive_validity", "incremental_lift", "net_commercial_value",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stopper_evidence_sha256(unit_id: str, assertion_type: str, cause: str, occurred_at: str) -> str:
    return digest_json({
        "outcome_unit_id": unit_id,
        "assertion_type": assertion_type,
        "cause": cause,
        "occurred_at": occurred_at,
        "synthetic_evidence_kind": "REGISTERED_STOPPING_EVENT_FIXTURE",
    })


def strict_load(path: Path) -> Any:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if value != canonical:
        raise ValueError("noncanonical timestamp")
    return parsed.astimezone(timezone.utc)


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def closed_window_contains(value: str, starts_at: str, ends_at: str) -> bool:
    return _time(starts_at) <= _time(value) <= _time(ends_at)


def _active_assertions(unit: dict[str, Any], cutoff: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = sorted((row for row in unit["assertions"] if _time(row["available_at"]) <= _time(cutoff)), key=lambda row: row["assertion_id"])
    retracted = {
        row["payload"]["corrects_assertion_id"]
        for row in eligible
        if row["assertion_type"] == "CORRECTION" and row["payload"].get("action") == "RETRACT"
    }
    active = [row for row in eligible if row["assertion_type"] != "CORRECTION" and row["assertion_id"] not in retracted]
    return eligible, active


def _booking_groups_at(ledger: dict[str, Any], cutoff: str) -> dict[str, list[str]]:
    groups: dict[str, set[str]] = {}
    for unit in ledger["units"]:
        _, active = _active_assertions(unit, cutoff)
        for assertion in active:
            if assertion["assertion_type"] == "F9_EVIDENCE":
                groups.setdefault(assertion["payload"]["booking_episode_id"], set()).add(unit["outcome_unit_id"])
    return {key: sorted(value) for key, value in sorted(groups.items())}


def _current_booking_groups(ledger: dict[str, Any]) -> dict[str, list[str]]:
    cutoffs = {max(unit["assessment_cutoffs"], key=_time) for unit in ledger["units"]}
    if len(cutoffs) != 1:
        raise ValueError("current route-day heads require one common as-of cutoff")
    return _booking_groups_at(ledger, cutoffs.pop())


def _canonicalize_ledger(input_ledger: dict[str, Any]) -> dict[str, Any]:
    ledger = json.loads(json.dumps(input_ledger, allow_nan=False))
    units = []
    for unit in ledger["units"]:
        by_id: dict[str, dict[str, Any]] = {}
        for assertion in unit["assertions"]:
            assertion_id = assertion["assertion_id"]
            if assertion_id in by_id and by_id[assertion_id] != assertion:
                raise ValueError("conflicting duplicate assertion id")
            by_id[assertion_id] = assertion
        unit["assertions"] = [by_id[key] for key in sorted(by_id)]
        unit["assessment_cutoffs"] = sorted(set(unit["assessment_cutoffs"]), key=_time)
        units.append(unit)
    ledger["units"] = sorted(units, key=lambda row: row["outcome_unit_id"])
    return ledger


def _ledger_invariant_error(ledger: dict[str, Any], policy: dict[str, Any], vertical: dict[str, Any]) -> str | None:
    if ledger.get("policy_sha256") != digest_json(policy):
        return "OUTCOMES-INPUT-POLICY-BINDING"
    if (
        ledger.get("stage1_unchanged_sha256") != digest_json(vertical["upstream_spine"])
        or ledger.get("vertical_slice_sha256") != digest_json(vertical)
        or ledger.get("route_assignment", {}).get("assignment_result") != vertical["result"]
    ):
        return "OUTCOMES-STAGE1-CONTAMINATION"
    route = vertical["route_manifest"]
    assignment = ledger.get("route_assignment", {})
    try:
        assigned = _time(assignment["assigned_at"])
        first_event = min(_time(row["occurred_at"]) for row in vertical["field_events"])
        route_issued = _time(route["issued_at"])
    except (KeyError, TypeError, ValueError):
        return "OUTCOMES-ASSIGNMENT-CHRONOLOGY"
    if (
        assignment.get("representative_id") != route["representative_id"]
        or assignment.get("route_date") != route["route_date"]
        or assigned.date().isoformat() != route["route_date"]
        or not route_issued <= assigned <= first_event
    ):
        return "OUTCOMES-ASSIGNMENT-CHRONOLOGY"
    end = assigned + timedelta(days=policy["horizon_days"])
    matrix = strict_load(SCENARIO_PATH)
    try:
        common_heads = {max(unit["assessment_cutoffs"], key=_time) for unit in ledger.get("units", [])}
    except (KeyError, TypeError, ValueError):
        return "OUTCOMES-CLOCK-ORDER"
    if common_heads != {matrix["aggregate_as_of"]}:
        return "OUTCOMES-ROUTE-DAY-ASOF-MISMATCH"
    for unit in ledger.get("units", []):
        if unit.get("outcome_unit_id") != f"OUTCOME_UNIT:ROUTE_DAY_001:{unit.get('sequence_position', 0):02d}":
            return "OUTCOMES-ASSERTION-UNIT-BINDING"
        try:
            cutoffs = [_time(value) for value in unit["assessment_cutoffs"]]
        except (KeyError, TypeError, ValueError):
            return "OUTCOMES-CLOCK-ORDER"
        if cutoffs != sorted(cutoffs) or any(value < assigned for value in cutoffs):
            return "OUTCOMES-CLOCK-ORDER"
        assertions = unit.get("assertions", [])
        by_id = {row.get("assertion_id"): row for row in assertions if isinstance(row, dict)}
        corrected: set[str] = set()
        for assertion in assertions:
            if assertion.get("outcome_unit_id") != unit["outcome_unit_id"]:
                return "OUTCOMES-ASSERTION-UNIT-BINDING"
            try:
                clocks = [_time(assertion[name]) for name in ["occurred_at", "recorded_at", "ingested_at", "validation_completed_at", "available_at"]]
            except (KeyError, TypeError, ValueError):
                return "OUTCOMES-CLOCK-ORDER"
            if clocks != sorted(clocks) or clocks[0] < assigned:
                return "OUTCOMES-CLOCK-ORDER"
            kind = assertion.get("assertion_type")
            payload = assertion.get("payload", {})
            if kind == "F9_EVIDENCE":
                try:
                    confirmed = _time(payload["booking_confirmed_at"])
                    appointment = _time(payload["appointment_scheduled_at"])
                except (KeyError, TypeError, ValueError):
                    return "OUTCOMES-F9-EVENT-TIME"
                if confirmed != clocks[0] or confirmed > clocks[-1]:
                    return "OUTCOMES-F9-EVENT-TIME"
                if appointment < confirmed:
                    return "OUTCOMES-F9-APPOINTMENT-CHRONOLOGY"
                if not isinstance(payload.get("senior_commercial_realtor_id"), str) or not payload["senior_commercial_realtor_id"].strip():
                    return "OUTCOMES-F9-REALTOR-IDENTITY"
                evidence_core = {key: value for key, value in payload.items() if key != "supporting_evidence_sha256"}
                if payload.get("supporting_evidence_sha256") != digest_json(evidence_core):
                    return "OUTCOMES-F9-EVIDENCE-DIGEST"
            elif kind == "OBSERVATION_WATERMARK":
                try:
                    observed = _time(payload["observed_through_at"])
                except (KeyError, TypeError, ValueError):
                    return "OUTCOMES-WATERMARK-SEMANTICS"
                if observed != clocks[0] or observed > clocks[-1]:
                    return "OUTCOMES-WATERMARK-SEMANTICS"
            elif kind == "NEGATIVE_ADJUDICATION" and clocks[0] < end:
                return "OUTCOMES-LABEL-IMMATURE-AS-NEGATIVE"
            elif kind in {"CENSORING", "COMPETING_EVENT"} and not assigned <= clocks[0] <= end:
                return "OUTCOMES-STOPPER-OUTSIDE-WINDOW"
            elif kind in {"CENSORING", "COMPETING_EVENT"} and payload.get("evidence_sha256") != _stopper_evidence_sha256(unit["outcome_unit_id"], kind, payload.get("cause"), assertion["occurred_at"]):
                return "OUTCOMES-STOPPER-EVIDENCE-DIGEST"
            elif kind == "CORRECTION":
                target_id = payload.get("corrects_assertion_id")
                target = by_id.get(target_id)
                if (
                    target is None
                    or target.get("outcome_unit_id") != unit["outcome_unit_id"]
                    or target.get("assertion_type") == "CORRECTION"
                    or target_id in corrected
                    or payload.get("corrects_assertion_sha256") != digest_json(target)
                    or _time(target["available_at"]) > clocks[0]
                ):
                    return "OUTCOMES-CORRECTION-ASSERTION-LINEAGE"
                corrected.add(target_id)
        for cutoff in unit.get("assessment_cutoffs", []):
            _, active = _active_assertions(unit, cutoff)
            negative = any(row["assertion_type"] == "NEGATIVE_ADJUDICATION" for row in active)
            complete = any(
                row["assertion_type"] == "OBSERVATION_WATERMARK"
                and row["payload"].get("source_complete") is True
                and _time(row["payload"]["observed_through_at"]) >= end
                for row in active
            )
            if negative and _time(cutoff) >= end and not complete:
                return "OUTCOMES-MATURITY-INCOMPLETE-WATERMARK"
    return None


def _project_revision(
    unit: dict[str, Any], cutoff: str, revision: int, predecessor: dict[str, Any] | None,
    policy: dict[str, Any], ledger: dict[str, Any],
) -> dict[str, Any]:
    eligible, active = _active_assertions(unit, cutoff)
    groups = _booking_groups_at(ledger, cutoff)
    start = _time(ledger["route_assignment"]["assigned_at"])
    end = start + timedelta(days=policy["horizon_days"])
    f9s = sorted((row for row in active if row["assertion_type"] == "F9_EVIDENCE"), key=lambda row: (row["payload"]["booking_confirmed_at"], row["assertion_id"]))
    stoppers = sorted((row for row in active if row["assertion_type"] in {"CENSORING", "COMPETING_EVENT"}), key=lambda row: (row["occurred_at"], row["assertion_id"]))
    watermarks = [row for row in active if row["assertion_type"] == "OBSERVATION_WATERMARK"]
    observed = max((_time(row["payload"]["observed_through_at"]) for row in watermarks), default=start)
    complete_through_end = any(
        row["payload"]["source_complete"] is True and _time(row["payload"]["observed_through_at"]) >= end
        for row in watermarks
    )
    f9 = f9s[0] if f9s else None
    stopper = stoppers[0] if stoppers else None
    unknown = any(row["assertion_type"] == "UNKNOWN_INPUT" for row in active)
    conflict = any(row["assertion_type"] == "CONFLICT" for row in active)
    negative = any(row["assertion_type"] == "NEGATIVE_ADJUDICATION" and row["payload"].get("adjudication") == "FAIL_SYNTHETIC" for row in active)
    collision = False
    if f9 is not None:
        collision = min(groups[f9["payload"]["booking_episode_id"]]) != unit["outcome_unit_id"]
    tied = f9 is not None and stopper is not None and _time(f9["payload"]["booking_confirmed_at"]) == _time(stopper["occurred_at"])
    f9_first = f9 is not None and (stopper is None or _time(f9["payload"]["booking_confirmed_at"]) < _time(stopper["occurred_at"]))
    in_window = f9 is not None and closed_window_contains(f9["payload"]["booking_confirmed_at"], _z(start), _z(end))
    if unknown:
        state, counted, ascertainment = "UNKNOWN", None, "UNKNOWN"
    elif conflict or collision or tied:
        state, counted, ascertainment = "CONFLICTED_UNKNOWN", None, "CONFLICTED"
    elif f9_first and in_window:
        state, counted, ascertainment = "F9_CONFIRMED_SYNTHETIC", True, "EVENT_CONFIRMED"
    elif stopper is not None and stopper["assertion_type"] == "CENSORING":
        state, counted, ascertainment = "CENSORED_UNKNOWN", None, "CENSORED"
    elif stopper is not None:
        state, counted, ascertainment = "COMPETING_EVENT_UNKNOWN", None, "COMPETING"
    elif _time(cutoff) < end or observed < end or not complete_through_end:
        state, counted, ascertainment = "IMMATURE_UNKNOWN", None, "WINDOW_OPEN"
    elif negative:
        state, counted, ascertainment = "MATURE_NO_F9_SYNTHETIC", False, "WINDOW_COMPLETE"
    else:
        state, counted, ascertainment = "UNKNOWN", None, "UNKNOWN"
    components = dict(UNKNOWN_COMPONENTS)
    booking = None
    stopping_event = None
    if state == "F9_CONFIRMED_SYNTHETIC":
        payload = f9["payload"]
        components = {
            "actor_role": payload["actor_role"], "requirement_type": payload["requirement_type"],
            "appointment": payload["appointment"], "supporting_evidence": payload["supporting_evidence"],
            "adjudication": payload["adjudication"], "deduplication": "CANONICAL_BOOKING_EPISODE",
        }
        booking = {
            "booking_episode_id": payload["booking_episode_id"],
            "booking_dedup_key": digest_json({"source_namespace": payload["source_namespace"], "booking_episode_id": payload["booking_episode_id"]}),
            "booking_confirmed_at": payload["booking_confirmed_at"],
            "appointment_scheduled_at": payload["appointment_scheduled_at"],
            "senior_commercial_realtor_id": payload["senior_commercial_realtor_id"],
            "supporting_evidence_sha256": payload["supporting_evidence_sha256"],
            "canonical_outcome_unit_id": unit["outcome_unit_id"],
        }
    elif state == "MATURE_NO_F9_SYNTHETIC":
        components = dict(NEGATIVE_COMPONENTS)
    elif collision:
        components["deduplication"] = "COLLISION_UNRESOLVED"
    if stopper is not None and state in {"CENSORED_UNKNOWN", "COMPETING_EVENT_UNKNOWN"}:
        stopping_event = {
            "type": "CENSORING" if stopper["assertion_type"] == "CENSORING" else "COMPETING_EVENT",
            "cause": stopper["payload"]["cause"], "occurred_at": stopper["occurred_at"],
            "evidence_sha256": stopper["payload"]["evidence_sha256"],
        }
    predecessor_ref = None if predecessor is None else {"assessment_id": predecessor["assessment_id"], "sha256": digest_json(predecessor)}
    return {
        "document_kind": "SYNTHETIC_F9_ASSESSMENT_REVISION", "schema_version": "1.0.0", "execution_scope": SCOPE,
        "assessment_id": f"ASSESSMENT:{unit['outcome_unit_id'].removeprefix('OUTCOME_UNIT:')}:{revision:02d}",
        "outcome_unit_id": unit["outcome_unit_id"], "revision": revision, "predecessor": predecessor_ref,
        "binding": unit["binding"],
        "window": {
            "policy_id": policy["policy_id"], "policy_version": policy["policy_version"], "policy_sha256": digest_json(policy),
            "assignment_id": ledger["route_assignment"]["assignment_id"],
            "anchor_type": policy["primary_window_anchor"], "anchor_at": _z(start), "starts_at": _z(start),
            "ends_at": _z(end), "horizon_days": policy["horizon_days"], "interval_convention": policy["interval_convention"],
            "reporting_grace_seconds": policy["reporting_grace_seconds"], "real_policy_authorized": False,
        },
        "ledger_snapshot_sha256": digest_json({"unit": unit["outcome_unit_id"], "as_of": cutoff, "eligible_assertions": eligible}),
        "dedupe_snapshot_sha256": digest_json(groups),
        "eligible_assertions": [{"assertion_id": row["assertion_id"], "sha256": digest_json(row), "available_at": row["available_at"]} for row in eligible],
        "assessed_at": cutoff, "observed_through_at": _z(observed), "assessment_state": state,
        "counted_f9": counted, "event_ascertainment_state": ascertainment, "booking_episode": booking,
        "components": components, "stopping_event": stopping_event,
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
        "downstream_states": {name: "UNKNOWN" for name in sorted(DOWNSTREAM_FIELDS)},
        "quality": {"synthetic_fixture": True, "real_outcome_proven": False, "window_policy_authorized": False},
        "owner": {"system": "CRE_FOUNDRY", "real_world_authority": "UNASSIGNED_EXTERNAL_AUTHORITY"},
        "empirical_claim_authorized": False,
    }


def _reconstruct(ledger: dict[str, Any], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    assessments, heads = [], []
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
    dedupe = []
    for booking_id, units in groups.items():
        canonical = min(units)
        dedupe.append({
            "booking_episode_id": booking_id,
            "booking_dedup_key": digest_json({"source_namespace": "SYNTHETIC_CRM", "booking_episode_id": booking_id}),
            "outcome_unit_ids": units, "canonical_outcome_unit_id": canonical,
            "counted_units": 1 if any(row["outcome_unit_id"] == canonical and row["counted_f9"] is True for row in heads) else 0,
        })
    counts: dict[str, int] = {}
    for head in heads:
        counts[head["assessment_state"]] = counts.get(head["assessment_state"], 0) + 1
    lower = sum(row["counted_f9"] is True for row in heads)
    final = all(row["assessment_state"] in {"F9_CONFIRMED_SYNTHETIC", "MATURE_NO_F9_SYNTHETIC"} for row in heads)
    aggregate = {
        "assignment_id": ledger["route_assignment"]["assignment_id"],
        "representative_id": ledger["route_assignment"]["representative_id"], "route_date": ledger["route_assignment"]["route_date"],
        "assignment_result": ledger["route_assignment"]["assignment_result"], "include_in_itt": ledger["route_assignment"]["include_in_itt"],
        "outcome_unit_count": len(heads), "confirmed_f9_lower_bound": lower, "final_f9_count": lower if final else None,
        "route_day_ascertainment_state": "FINAL" if final else "IMMATURE_PARTIAL", "state_counts": dict(sorted(counts.items())),
    }
    return assessments, heads, dedupe, aggregate


def _validate_outcome_run(subject: dict[str, Any]) -> list[str]:
    if not isinstance(subject, dict) or set(subject) != TOP_FIELDS:
        return ["OUTCOMES-SHAPE"]
    if (
        subject.get("document_kind") != "SYNTHETIC_OUTCOME_CONTRACT_RUN"
        or subject.get("schema_version") != "1.0.0"
        or subject.get("execution_scope") != SCOPE
        or subject.get("run_id") != "OUTCOME_RUN:SYNTHETIC_ROUTE_DAY_001"
        or subject.get("canonicalization") != CANONICALIZATION
    ):
        return ["OUTCOMES-BOUNDARY"]
    if subject.get("proof") != EXPECTED_PROOF:
        return ["OUTCOMES-CLAIM-CEILING"]
    policy = subject.get("policy")
    ledger = subject.get("input_ledger")
    assessments = subject.get("assessments")
    heads = subject.get("current_heads")
    if not isinstance(policy, dict) or not isinstance(ledger, dict) or not isinstance(assessments, list) or not isinstance(heads, list):
        return ["OUTCOMES-SHAPE"]
    policy_schema = strict_load(POLICY_SCHEMA_PATH)
    Draft202012Validator.check_schema(policy_schema)
    if (
        next(iter(Draft202012Validator(policy_schema, format_checker=FormatChecker()).iter_errors(policy)), None) is not None
        or policy != strict_load(POLICY_PATH)
        or policy.get("real_policy_authorized") is not False
    ):
        return ["OUTCOMES-WINDOW-AUTHORITY"]

    try:
        from cre_foundry.vertical.shadow_slice import build_vertical_slice
        vertical = build_vertical_slice(10)
    except (ImportError, ValueError):
        return ["OUTCOMES-UPSTREAM-UNAVAILABLE"]
    try:
        canonical_ledger = _canonicalize_ledger(ledger)
        input_schema = strict_load(INPUT_SCHEMA_PATH)
        Draft202012Validator.check_schema(input_schema)
        input_validator = Draft202012Validator(input_schema, format_checker=FormatChecker())
    except (KeyError, TypeError, ValueError):
        return ["OUTCOMES-INPUT-LEDGER-SCHEMA"]
    if canonical_ledger != ledger or next(iter(input_validator.iter_errors(canonical_ledger)), None) is not None:
        return ["OUTCOMES-INPUT-LEDGER-SCHEMA"]
    invariant_error = _ledger_invariant_error(canonical_ledger, policy, vertical)
    if invariant_error is not None:
        return [invariant_error]
    if canonical_ledger != strict_load(INPUT_LEDGER_PATH):
        return ["OUTCOMES-INPUT-LEDGER-MISMATCH"]
    ledger = canonical_ledger
    upstream = vertical["upstream_spine"]
    route = vertical["route_manifest"]
    expected_stage1 = digest_json(upstream)
    if (
        ledger.get("stage1_unchanged_sha256") != expected_stage1
        or ledger.get("vertical_slice_sha256") != digest_json(vertical)
        or ledger.get("route_assignment", {}).get("assignment_result") != vertical["result"]
    ):
        return ["OUTCOMES-STAGE1-CONTAMINATION"]
    units = ledger.get("units")
    if not isinstance(units, list) or len(units) != 10:
        return ["OUTCOMES-LEDGER-SHAPE"]
    expected_events = {row["event_id"]: row for row in vertical["field_events"]}
    expected_pairs = [(row["candidate_id"], row["physical_location_id"]) for row in route["stops"]]
    actual_pairs = []
    assertion_ids: set[str] = set()
    for unit in units:
        binding = unit.get("binding", {})
        event = expected_events.get(binding.get("field_event_id"))
        actual_pairs.append((binding.get("candidate_id"), binding.get("physical_location_id")))
        if (
            event is None or binding.get("field_event_sha256") != digest_json(event)
            or binding.get("route_manifest_sha256") != digest_json(route)
            or binding.get("source_snapshot_sha256") != upstream["source_snapshot_sha256"]
            or binding.get("candidate_snapshot_sha256") != upstream["candidate_snapshot_sha256"]
            or binding.get("math_decision_sha256") != upstream["replay_receipt"]["math_decision_sha256"]
        ):
            return ["OUTCOMES-STAGE1-CONTAMINATION"]
        for assertion in unit.get("assertions", []):
            if assertion.get("assertion_id") in assertion_ids:
                return ["OUTCOMES-ASSERTION-DUPLICATE"]
            assertion_ids.add(assertion.get("assertion_id"))
            try:
                clocks = [_time(assertion[name]) for name in ["occurred_at", "recorded_at", "ingested_at", "validation_completed_at", "available_at"]]
            except (KeyError, TypeError, ValueError):
                return ["OUTCOMES-CLOCK-ORDER"]
            if clocks != sorted(clocks):
                return ["OUTCOMES-CLOCK-ORDER"]
    if actual_pairs != expected_pairs:
        return ["OUTCOMES-STAGE1-CONTAMINATION"]

    by_assessment = {row.get("assessment_id"): row for row in assessments if isinstance(row, dict)}
    expected_revision_count = sum(len(row["assessment_cutoffs"]) for row in strict_load(SCENARIO_PATH)["scenarios"])
    if len(by_assessment) != len(assessments) or len(assessments) != expected_revision_count:
        return ["OUTCOMES-CORRECTION-LINEAGE"]
    seen_heads = {row.get("outcome_unit_id") for row in heads if isinstance(row, dict)}
    if len(heads) != 10 or len(seen_heads) != 10:
        return ["OUTCOMES-CORRECTION-LINEAGE"]
    for assessment in assessments:
        predecessor = assessment.get("predecessor")
        if assessment.get("revision") == 1 and predecessor is not None:
            return ["OUTCOMES-CORRECTION-LINEAGE"]
        if assessment.get("revision", 0) > 1:
            if (predecessor or {}).get("assessment_id") == assessment.get("assessment_id"):
                return ["OUTCOMES-CORRECTION-LINEAGE"]
            prior = by_assessment.get((predecessor or {}).get("assessment_id"))
            if prior is None or predecessor.get("sha256") != digest_json(prior) or prior.get("outcome_unit_id") != assessment.get("outcome_unit_id") or prior.get("revision") + 1 != assessment.get("revision"):
                return ["OUTCOMES-CORRECTION-PRIOR-REWRITE"]
        try:
            assessed = _time(assessment["assessed_at"])
            observed = _time(assessment["observed_through_at"])
        except (KeyError, TypeError, ValueError):
            return ["OUTCOMES-CLOCK-ORDER"]
        if observed > assessed:
            return ["OUTCOMES-CLOCK-ORDER"]
        for ref in assessment.get("eligible_assertions", []):
            if _time(ref["available_at"]) > assessed:
                return ["OUTCOMES-ASOF-LEAKAGE"]
        state = assessment.get("assessment_state")
        counted = assessment.get("counted_f9")
        if state not in STATE_LABELS:
            return ["OUTCOMES-LABEL-STATE"]
        if counted != STATE_LABELS[state]:
            if state == "IMMATURE_UNKNOWN":
                return ["OUTCOMES-LABEL-IMMATURE-AS-NEGATIVE"]
            if state == "CENSORED_UNKNOWN":
                return ["OUTCOMES-LABEL-CENSORED-AS-NEGATIVE"]
            if state == "COMPETING_EVENT_UNKNOWN":
                return ["OUTCOMES-LABEL-COMPETING-AS-NEGATIVE"]
            return ["OUTCOMES-LABEL-STATE"]
        window = assessment.get("window", {})
        if window.get("real_policy_authorized") is not False or window.get("policy_sha256") != digest_json(policy):
            return ["OUTCOMES-WINDOW-AUTHORITY"]
        if state == "F9_CONFIRMED_SYNTHETIC":
            components = assessment.get("components", {})
            if any(components.get(key) not in allowed for key, allowed in POSITIVE_COMPONENT_KEYS.items()):
                return ["OUTCOMES-F9-MISSING-CONJUNCT"]
            booking = assessment.get("booking_episode")
            if not isinstance(booking, dict) or not _time(window["starts_at"]) <= _time(booking["booking_confirmed_at"]) <= _time(window["ends_at"]):
                return ["OUTCOMES-F9-OUTSIDE-WINDOW"]
        if state == "MATURE_NO_F9_SYNTHETIC" and (
            assessed < _time(window["ends_at"]) + timedelta(seconds=window["reporting_grace_seconds"])
            or observed < _time(window["ends_at"])
        ):
            return ["OUTCOMES-LABEL-IMMATURE-AS-NEGATIVE"]
        downstream = assessment.get("downstream_states", {})
        if set(downstream) != DOWNSTREAM_FIELDS or any(value != "UNKNOWN" for value in downstream.values()):
            return ["OUTCOMES-DOWNSTREAM-INFERENCE"]

    actual_dedupe = subject.get("dedupe_groups")
    if not isinstance(actual_dedupe, list):
        return ["OUTCOMES-SHAPE"]
    counted_by_key: dict[str, int] = {}
    for head in heads:
        booking = head.get("booking_episode")
        if head.get("counted_f9") is True and booking:
            key = booking["booking_dedup_key"]
            counted_by_key[key] = counted_by_key.get(key, 0) + 1
    if any(count > 1 for count in counted_by_key.values()):
        return ["OUTCOMES-DEDUPE-DOUBLE-COUNT"]
    aggregate = subject.get("route_day_aggregate", {})
    if aggregate.get("final_f9_count") is not None and any(head.get("assessment_state") not in {"F9_CONFIRMED_SYNTHETIC", "MATURE_NO_F9_SYNTHETIC"} for head in heads):
        return ["OUTCOMES-ROUTE-DAY-PREMATURE-FINAL"]

    schema = strict_load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for assessment in assessments:
        if next(iter(validator.iter_errors(assessment)), None) is not None:
            return ["OUTCOMES-ASSESSMENT-SCHEMA"]

    expected_assessments, expected_heads, expected_dedupe, expected_aggregate = _reconstruct(ledger, policy)
    if actual_dedupe != expected_dedupe:
        return ["OUTCOMES-REPLAY-DEDUPE-MISMATCH"]
    correction_edges = [{"assessment_id": row["assessment_id"], "predecessor": row["predecessor"]} for row in assessments if row["predecessor"] is not None]
    receipt = subject.get("replay_receipt")
    if not isinstance(receipt, dict):
        return ["OUTCOMES-REPLAY-RECEIPT-MISMATCH"]
    if receipt.get("correction_lineage_root_sha256") != digest_json(correction_edges):
        return ["OUTCOMES-REPLAY-LINEAGE-MISMATCH"]
    if assessments != expected_assessments or heads != expected_heads:
        return ["OUTCOMES-REPLAY-SEMANTIC-MISMATCH"]
    if aggregate != expected_aggregate:
        return ["OUTCOMES-ROUTE-DAY-PREMATURE-FINAL"]
    expected_receipt = {
        "builder_version": "outcomes-ledger-builder-v2",
        "builder_sha256": digest_file(BUILDER_PATH),
        "canonicalization": CANONICALIZATION,
        "input_ledger_sha256": digest_json(ledger),
        "policy_sha256": digest_json(policy),
        "policy_schema_sha256": digest_file(POLICY_SCHEMA_PATH),
        "stage1_unchanged_sha256": ledger["stage1_unchanged_sha256"],
        "schema_sha256": digest_file(SCHEMA_PATH),
        "input_ledger_schema_sha256": digest_file(INPUT_SCHEMA_PATH),
        "evaluator_contract_sha256": digest_file(EVALUATOR_CONTRACT_PATH),
        "assessment_digests": [{"assessment_id": row["assessment_id"], "sha256": digest_json(row)} for row in assessments],
        "dedupe_groups_sha256": digest_json(actual_dedupe),
        "correction_lineage_root_sha256": digest_json(correction_edges),
        "current_label_vector_sha256": digest_json([{"outcome_unit_id": row["outcome_unit_id"], "counted_f9": row["counted_f9"]} for row in heads]),
        "route_day_aggregate_sha256": digest_json(aggregate),
        "state_counts": aggregate["state_counts"],
        "proof_level": 5,
    }
    if receipt != expected_receipt:
        return ["OUTCOMES-REPLAY-RECEIPT-MISMATCH"]
    binding = subject.get("schema_binding")
    if binding != {"path": "contracts/f9_outcome.schema.json", "schema_version": "1.0.0", "sha256": digest_file(SCHEMA_PATH)}:
        return ["OUTCOMES-SCHEMA-BINDING"]
    return []


def validate_outcome_run(subject: dict[str, Any]) -> list[str]:
    try:
        return _validate_outcome_run(subject)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ["OUTCOMES-MALFORMED"]


def validate_itt_inclusion_cases(subject: dict[str, Any]) -> list[str]:
    """Independently check that assignment, not issuance/adherence, controls ITT inclusion."""
    try:
        policy = strict_load(POLICY_PATH)
        expected = {
            "artifact_id": "OUTCOMES-001-ITT-INCLUSION-CASES",
            "schema_version": "1.0.0",
            "execution_scope": SCOPE,
            "primary_estimand_unit": "REPRESENTATIVE_ROUTE_DAY_ITT",
            "policy_sha256": digest_json(policy),
            "cases": [
                {"case_id": "ISSUE_ADHERENT", "assignment_result": "ISSUE", "adherence_state": "ADHERENT_SYNTHETIC", "include_in_itt": True},
                {"case_id": "ISSUE_NONADHERENT", "assignment_result": "ISSUE", "adherence_state": "NONADHERENT_SYNTHETIC", "include_in_itt": True},
                {"case_id": "ABSTAIN_ROUTE_DAY", "assignment_result": "ABSTAIN_NO_VALID_TEN", "adherence_state": "NO_ROUTE_ISSUED", "include_in_itt": True},
            ],
            "outcome_count_claimed": False,
            "claim": "Assignment inclusion only; outcome maturity and counts require separately adjudicated evidence.",
        }
        if policy["include_abstain_assignments"] is not True or policy["include_nonadherent_assignments"] is not True:
            return ["OUTCOMES-ITT-POLICY"]
        return [] if subject == expected else ["OUTCOMES-ITT-INCLUSION"]
    except (KeyError, TypeError, ValueError):
        return ["OUTCOMES-ITT-MALFORMED"]
