"""Independent semantic evaluator for the synthetic VERTICAL-001 slice."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATHS = {
    "route_day": "contracts/synthetic_route_day.schema.json",
    "field_event": "contracts/synthetic_field_event.schema.json",
    "f9_outcome": "contracts/synthetic_f9_outcome.schema.json",
}
TOP_FIELDS = {
    "document_kind", "schema_version", "execution_scope", "slice_id", "canonicalization",
    "schema_bindings", "upstream_spine", "result", "route_manifest", "field_events",
    "f9_outcomes", "replay_receipt", "proof",
}
EXPECTED_PROOF = {
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
}
POSITIVE_COMPONENTS = {
    "decision_maker": "CONFIRMED_SYNTHETIC",
    "cre_requirement": "CONFIRMED_SYNTHETIC",
    "appointment": "SCHEDULED_WITH_SENIOR_REALTOR_SYNTHETIC",
    "supporting_evidence": "ADJUDICABLE_SYNTHETIC_FIXTURE",
    "adjudication": "PASS_SYNTHETIC",
    "deduplication": "UNIQUE_SYNTHETIC",
}
UNKNOWN_COMPONENTS = {
    "decision_maker": "UNKNOWN",
    "cre_requirement": "UNKNOWN",
    "appointment": "UNKNOWN",
    "supporting_evidence": "UNKNOWN",
    "adjudication": "UNKNOWN",
    "deduplication": "UNKNOWN",
}
MATURE_NEGATIVE_COMPONENTS = {
    "decision_maker": "UNKNOWN",
    "cre_requirement": "UNKNOWN",
    "appointment": "NOT_OBSERVED_SYNTHETIC",
    "supporting_evidence": "ABSENT_SYNTHETIC",
    "adjudication": "FAIL_SYNTHETIC",
    "deduplication": "UNIQUE_SYNTHETIC",
}
REQUIRED_GATES = {"evidence", "identity", "eligibility", "safety", "access", "operational"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    return parsed.astimezone(timezone.utc)


def _schemas() -> tuple[dict[str, Any], dict[str, Draft202012Validator]]:
    schemas = {name: strict_load(ROOT / path) for name, path in SCHEMA_PATHS.items()}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    validators = {name: Draft202012Validator(schema, format_checker=FormatChecker()) for name, schema in schemas.items()}
    return schemas, validators


def _first_schema_error(validator: Draft202012Validator, document: Any) -> str | None:
    errors = sorted(validator.iter_errors(document), key=lambda error: (list(error.absolute_path), error.message))
    return errors[0].message if errors else None


def validate_outcome_state(outcome: dict[str, Any], event: dict[str, Any]) -> list[str]:
    """Validate F9 maturity semantics independently of canonical fixture replay."""
    try:
        occurred = _time(event["occurred_at"])
        available = _time(event["available_at"])
        starts = _time(outcome["window"]["starts_at"])
        ends = _time(outcome["window"]["ends_at"])
        assessed = _time(outcome["assessed_at"])
    except (KeyError, TypeError, ValueError):
        return ["VERTICAL-OUTCOME-CHRONOLOGY"]
    if starts != occurred or ends != starts + timedelta(days=30) or assessed < available:
        return ["VERTICAL-OUTCOME-CHRONOLOGY"]
    state = outcome.get("outcome_state")
    counted = outcome.get("counted_f9")
    ascertainment = outcome.get("window", {}).get("ascertainment_state")
    if state == "F9_CONFIRMED_SYNTHETIC":
        try:
            booking = _time(outcome["booking_at"])
        except (TypeError, ValueError):
            return ["VERTICAL-F9-CONJUNCTS"]
        if (
            counted is not True
            or outcome.get("components") != POSITIVE_COMPONENTS
            or outcome.get("qualification_evidence_sha256") != digest_json({
                "outcome": "F9", "event_id": event["event_id"], "components": POSITIVE_COMPONENTS,
            })
            or not starts <= booking <= ends
            or booking > assessed
            or ascertainment != "COMPLETE_SYNTHETIC"
            or outcome.get("censored_at") is not None
            or outcome.get("censor_reason") is not None
        ):
            return ["VERTICAL-F9-CONJUNCTS"]
    elif state == "MATURE_NO_F9_SYNTHETIC":
        if (
            counted is not False
            or assessed < ends
            or ascertainment != "COMPLETE_SYNTHETIC"
            or outcome.get("booking_at") is not None
            or outcome.get("qualification_evidence_sha256") is not None
            or outcome.get("censored_at") is not None
            or outcome.get("censor_reason") is not None
            or outcome.get("components") != MATURE_NEGATIVE_COMPONENTS
        ):
            return ["VERTICAL-F9-MATURE-NEGATIVE"]
    elif state == "IMMATURE_UNKNOWN":
        if (
            counted is not None
            or assessed >= ends
            or ascertainment != "IMMATURE"
            or outcome.get("booking_at") is not None
            or outcome.get("qualification_evidence_sha256") is not None
            or outcome.get("censored_at") is not None
            or outcome.get("censor_reason") is not None
            or outcome.get("components") != UNKNOWN_COMPONENTS
        ):
            return ["VERTICAL-F9-IMMATURE-RELABELED"]
    elif state == "CENSORED_UNKNOWN":
        try:
            censored = _time(outcome["censored_at"])
        except (TypeError, ValueError):
            return ["VERTICAL-F9-CENSORING"]
        if (
            counted is not None
            or ascertainment != "CENSORED"
            or not occurred <= censored < ends
            or assessed < censored
            or not outcome.get("censor_reason")
            or outcome.get("booking_at") is not None
            or outcome.get("qualification_evidence_sha256") is not None
            or outcome.get("components") != UNKNOWN_COMPONENTS
        ):
            return ["VERTICAL-F9-CENSORING"]
    elif state in {"CONFLICTED_UNKNOWN", "UNKNOWN"}:
        expected_ascertainment = "CONFLICTED" if state == "CONFLICTED_UNKNOWN" else "UNKNOWN"
        if (
            counted is not None
            or ascertainment != expected_ascertainment
            or outcome.get("booking_at") is not None
            or outcome.get("qualification_evidence_sha256") is not None
            or outcome.get("censored_at") is not None
            or outcome.get("censor_reason") is not None
            or outcome.get("components") != UNKNOWN_COMPONENTS
        ):
            return ["VERTICAL-F9-UNKNOWN-RELABELED"]
    else:
        return ["VERTICAL-F9-STATE"]
    return []


def _validate_vertical_slice(subject: dict[str, Any]) -> list[str]:
    """Return stable diagnostics without importing or trusting the vertical builder."""
    if not isinstance(subject, dict) or set(subject) != TOP_FIELDS:
        return ["VERTICAL-SLICE-SHAPE"]
    if (
        subject.get("document_kind") != "SYNTHETIC_VERTICAL_SLICE"
        or subject.get("schema_version") != "1.0.0"
        or subject.get("execution_scope") != "SYNTHETIC_NON_INFLUENCING"
        or subject.get("slice_id") != "VERTICAL:SHADOW_SLICE_001"
        or subject.get("canonicalization") != "SORTED_KEYS_INTEGER_JSON_V1"
    ):
        return ["VERTICAL-SLICE-BOUNDARY"]
    if subject.get("proof") != EXPECTED_PROOF:
        return ["VERTICAL-CLAIM-CEILING"]

    spine = subject.get("upstream_spine")
    decision = spine.get("math_decision", {}) if isinstance(spine, dict) else {}
    problem = spine.get("math_problem", {}) if isinstance(spine, dict) else {}
    route = subject.get("route_manifest")
    events = subject.get("field_events")
    outcomes = subject.get("f9_outcomes")
    if not isinstance(events, list) or not isinstance(outcomes, list):
        return ["VERTICAL-SLICE-CARDINALITY"]
    result = decision.get("decision")
    if subject.get("result") != result or result not in {"ISSUE", "ABSTAIN_NO_VALID_TEN"}:
        return ["VERTICAL-UPSTREAM-RESULT"]

    if result == "ABSTAIN_NO_VALID_TEN":
        if route is not None or events or outcomes:
            return ["VERTICAL-ABSTAIN-HAS-EFFECTS"]
    else:
        if not isinstance(route, dict):
            return ["VERTICAL-ISSUE-NO-ROUTE"]
        if (
            route.get("route_manifest_id") != "ROUTE:SYNTHETIC_ROUTE_DAY_001"
            or route.get("issued_at") != "2026-07-31T23:45:00Z"
        ):
            return ["VERTICAL-REPLAY-NONCANONICAL"]
        stops = route.get("stops", [])
        if not isinstance(stops, list) or len(stops) != 10:
            return ["VERTICAL-ROUTE-CARDINALITY"]
        candidate_ids = [row.get("candidate_id") for row in stops if isinstance(row, dict)]
        location_ids = [row.get("physical_location_id") for row in stops if isinstance(row, dict)]
        if len(candidate_ids) != 10 or len(set(candidate_ids)) != 10 or len(set(location_ids)) != 10:
            return ["VERTICAL-ROUTE-DUPLICATE-LOCATION"]
        by_candidate = {row.get("candidate_id"): row for row in spine.get("candidates", []) if isinstance(row, dict)}
        for candidate_id in candidate_ids:
            candidate = by_candidate.get(candidate_id, {})
            if candidate.get("protection", {}).get("status") != "CLEAR" or candidate.get("math_candidate", {}).get("protected_status") != "CLEAR":
                return ["VERTICAL-ROUTE-PROTECTED-STOP"]
        selected_pairs = [(row.get("candidate_id"), row.get("physical_location_id")) for row in decision.get("selected", [])]
        stop_pairs = [(row.get("candidate_id"), row.get("physical_location_id")) for row in stops]
        if stop_pairs != selected_pairs:
            return ["VERTICAL-ROUTE-SELECTION-MISMATCH"]
        if [row.get("sequence_position") for row in stops] != list(range(1, 11)):
            return ["VERTICAL-ROUTE-ORDER"]
        for index, stop in enumerate(stops):
            candidate = by_candidate.get(stop.get("candidate_id"), {})
            math_candidate = candidate.get("math_candidate", {})
            if (
                stop.get("physical_location_id") != math_candidate.get("physical_location_id")
                or set(math_candidate.get("gates", {})) != REQUIRED_GATES
                or any(state != "PASS" for state in math_candidate.get("gates", {}).values())
                or stop.get("synthetic_service_minutes") != math_candidate.get("service_minutes")
                or stop.get("synthetic_travel_minutes_from_previous") != (0 if index == 0 else 5)
                or stop.get("stop_feasibility_state") != "SYNTHETIC_FIXTURE_PASS"
            ):
                return ["VERTICAL-ROUTE-STOP-FIDELITY"]

        try:
            issued = _time(route["issued_at"])
            math_issued = _time(problem["snapshot"]["issued_at"])
            cutoff = _time(problem["snapshot"]["stage1_cutoff"])
            route_day_start = datetime.fromisoformat(problem["route_day"]["route_date"]).replace(tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError):
            return ["VERTICAL-ROUTE-CHRONOLOGY"]
        if not cutoff <= math_issued <= issued < route_day_start:
            return ["VERTICAL-ROUTE-CHRONOLOGY"]

        if len(events) != 10 or len(outcomes) != 10:
            return ["VERTICAL-EVENT-OUTCOME-CARDINALITY"]
        by_stop = {(row["candidate_id"], row["physical_location_id"]): row for row in stops}
        event_ids = [row.get("event_id") for row in events if isinstance(row, dict)]
        if len(event_ids) != 10 or len(set(event_ids)) != 10:
            return ["VERTICAL-FIELD-EVENT-DUPLICATE"]
        event_pairs = [
            (row.get("stop", {}).get("candidate_id"), row.get("stop", {}).get("physical_location_id"))
            for row in events if isinstance(row, dict)
        ]
        if event_pairs != stop_pairs or event_ids != [f"FIELD_EVENT:SYN_{index:04d}" for index in range(1, 11)]:
            return ["VERTICAL-FIELD-COVERAGE"]
        route_sha = digest_json(route)
        field_start = route_day_start + timedelta(hours=10)
        for index, event in enumerate(events):
            stop = event.get("stop", {})
            pair = (stop.get("candidate_id"), stop.get("physical_location_id"))
            if pair not in by_stop or stop.get("sequence_position") != by_stop[pair]["sequence_position"]:
                return ["VERTICAL-FIELD-UNSELECTED-STOP"]
            try:
                times = [_time(event[name]) for name in ["occurred_at", "recorded_at", "ingested_at", "validation_completed_at"]]
                available = _time(event["available_at"])
            except (KeyError, TypeError, ValueError):
                return ["VERTICAL-FIELD-EVENT-CHRONOLOGY"]
            if times[0] < issued:
                return ["VERTICAL-FIELD-BEFORE-ISSUANCE"]
            if times != sorted(times) or available != times[-1] or times[0].date().isoformat() != route["route_date"]:
                return ["VERTICAL-FIELD-EVENT-CHRONOLOGY"]
            expected_occurred = field_start + timedelta(minutes=20 * index)
            expected_result = "CONTACT_MADE_SYNTHETIC" if index == 0 else "CONTACT_ATTEMPTED_SYNTHETIC" if index % 2 else "NO_CONTACT_SYNTHETIC"
            if (
                times != [expected_occurred + timedelta(minutes=offset) for offset in range(4)]
                or event.get("event_result") != expected_result
            ):
                return ["VERTICAL-REPLAY-NONCANONICAL"]
            binding = event.get("route_binding", {})
            if (
                binding.get("route_manifest_id") != route["route_manifest_id"]
                or binding.get("route_manifest_sha256") != route_sha
                or binding.get("candidate_snapshot_sha256") != spine.get("candidate_snapshot_sha256")
                or binding.get("math_decision_sha256") != digest_json(decision)
                or event.get("representative_id") != route["representative_id"]
                or event.get("route_date") != route["route_date"]
            ):
                return ["VERTICAL-FIELD-EVENT-BINDING"]
            expected_evidence = digest_json({
                "event_id": event.get("event_id"),
                "candidate_id": stop.get("candidate_id"),
                "event_result": event.get("event_result"),
            })
            if event.get("evidence") != {"mode": "SYNTHETIC_FIXTURE", "payload_sha256": expected_evidence}:
                return ["VERTICAL-FIELD-EVIDENCE-BINDING"]

        by_event = {row["event_id"]: row for row in events}
        outcome_ids = [row.get("outcome_id") for row in outcomes if isinstance(row, dict)]
        if len(outcome_ids) != 10 or len(set(outcome_ids)) != 10:
            return ["VERTICAL-OUTCOME-DUPLICATE"]
        outcome_event_ids = [row.get("field_event_binding", {}).get("event_id") for row in outcomes if isinstance(row, dict)]
        if outcome_event_ids != event_ids or outcome_ids != [f"OUTCOME:SYN_{index:04d}" for index in range(1, 11)]:
            return ["VERTICAL-OUTCOME-COVERAGE"]
        for index, outcome in enumerate(outcomes):
            binding = outcome.get("field_event_binding", {})
            event = by_event.get(binding.get("event_id"))
            if event is None:
                return ["VERTICAL-OUTCOME-EVENT-BINDING"]
            if (
                binding.get("field_event_sha256") != digest_json(event)
                or binding.get("route_manifest_sha256") != route_sha
                or binding.get("candidate_snapshot_sha256") != spine.get("candidate_snapshot_sha256")
                or binding.get("math_decision_sha256") != digest_json(decision)
                or outcome.get("candidate_id") != event["stop"]["candidate_id"]
                or outcome.get("physical_location_id") != event["stop"]["physical_location_id"]
                or outcome.get("representative_id") != route["representative_id"]
                or outcome.get("route_date") != route["route_date"]
            ):
                return ["VERTICAL-OUTCOME-EVENT-BINDING"]
            outcome_errors = validate_outcome_state(outcome, event)
            if outcome_errors:
                return outcome_errors
            occurred = _time(event["occurred_at"])
            expected_state = "F9_CONFIRMED_SYNTHETIC" if index == 0 else "IMMATURE_UNKNOWN"
            expected_assessed = occurred + (timedelta(hours=2) if index == 0 else timedelta(days=1))
            expected_booking = occurred + timedelta(hours=1) if index == 0 else None
            if (
                outcome.get("outcome_state") != expected_state
                or _time(outcome["assessed_at"]) != expected_assessed
                or (_time(outcome["booking_at"]) if outcome.get("booking_at") else None) != expected_booking
            ):
                return ["VERTICAL-REPLAY-NONCANONICAL"]

    try:
        schemas, validators = _schemas()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"VERTICAL-SCHEMA-UNAVAILABLE:{type(exc).__name__}"]
    bindings = subject.get("schema_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(SCHEMA_PATHS):
        return ["VERTICAL-SCHEMA-BINDING-COVERAGE"]
    for name, path in SCHEMA_PATHS.items():
        binding = bindings[name]
        if binding != {"path": path, "schema_version": "1.0.0", "sha256": digest_file(ROOT / path)}:
            return [f"VERTICAL-SCHEMA-BINDING:{name}"]
    if route is not None:
        error = _first_schema_error(validators["route_day"], route)
        if error:
            return [f"VERTICAL-ROUTE-SCHEMA:{error}"]
    for event in events:
        error = _first_schema_error(validators["field_event"], event)
        if error:
            return [f"VERTICAL-FIELD-SCHEMA:{error}"]
    for outcome in outcomes:
        error = _first_schema_error(validators["f9_outcome"], outcome)
        if error:
            return [f"VERTICAL-OUTCOME-SCHEMA:{error}"]

    try:
        from evals.public.contract_spine_evaluator import validate_spine
    except ModuleNotFoundError:
        from contract_spine_evaluator import validate_spine
    upstream_errors = validate_spine(spine, check_replay=True) if isinstance(spine, dict) else ["invalid"]
    if upstream_errors:
        return ["VERTICAL-STAGE1-REWRITE"]

    if route is not None:
        upstream = route["upstream_binding"]
        receipt = spine["replay_receipt"]
        expected_upstream = {
            "source_snapshot_sha256": spine["source_snapshot_sha256"],
            "candidate_snapshot_sha256": spine["candidate_snapshot_sha256"],
            "math_problem_sha256": receipt["math_problem_sha256"],
            "math_decision_sha256": receipt["math_decision_sha256"],
            "decision_id": problem["decision_id"],
            "policy_version": problem["policy"]["policy_version"],
            "policy_sha256": problem["policy"]["policy_sha256"],
            "upstream_decision_scope": problem["decision_scope"],
        }
        if upstream != expected_upstream or route["representative_id"] != problem["route_day"]["representative_id"] or route["route_date"] != problem["route_day"]["route_date"]:
            return ["VERTICAL-ROUTE-UPSTREAM-BINDING"]

    receipt = subject.get("replay_receipt")
    if not isinstance(receipt, dict):
        return ["VERTICAL-REPLAY-RECEIPT-MISMATCH"]
    expected_receipt = {
        "builder_version": "vertical-shadow-builder-v1",
        "builder_sha256": digest_file(ROOT / "src/cre_foundry/vertical/shadow_slice.py"),
        "contract_artifact_sha256": digest_file(ROOT / "artifacts/contracts/contract_spine.json"),
        "upstream_spine_sha256": digest_json(spine),
        "source_snapshot_sha256": spine["source_snapshot_sha256"],
        "candidate_snapshot_sha256": spine["candidate_snapshot_sha256"],
        "math_problem_sha256": spine["replay_receipt"]["math_problem_sha256"],
        "math_decision_sha256": spine["replay_receipt"]["math_decision_sha256"],
        "policy_sha256": spine["replay_receipt"]["policy_sha256"],
        "result": decision["decision"],
        "abstain_reason": decision.get("reason"),
        "route_manifest_sha256": digest_json(route),
        "field_event_digests": [{"event_id": row["event_id"], "sha256": digest_json(row)} for row in sorted(events, key=lambda row: row["event_id"])],
        "outcome_digests": [{"outcome_id": row["outcome_id"], "sha256": digest_json(row)} for row in sorted(outcomes, key=lambda row: row["outcome_id"])],
        "selected_candidate_ids": [row["candidate_id"] for row in decision.get("selected", [])],
        "schema_sha256": {name: digest_file(ROOT / path) for name, path in sorted(SCHEMA_PATHS.items())},
    }
    if receipt != expected_receipt:
        return ["VERTICAL-REPLAY-RECEIPT-MISMATCH"]
    return []


def validate_vertical_slice(subject: dict[str, Any]) -> list[str]:
    """Fail closed with a stable diagnostic for malformed adversarial subjects."""
    try:
        return _validate_vertical_slice(subject)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return ["VERTICAL-SLICE-MALFORMED"]
