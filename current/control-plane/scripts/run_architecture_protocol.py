"""ARCHITECTURE-001 black-box protocol driver.

Reads a canonical command stream (or generates the deterministic canonical run)
and produces the versioned JSON workflow-run subject for the frozen public
evaluator.  The driver invokes only the public protocol/workflow interface in
src/cre_foundry/architecture; it never imports the evaluator, any evals module,
or the MATH oracle.  The MATH decision is consumed as external data.  Output is
byte-deterministic canonical JSON; the driver exits nonzero on any fail-closed
protocol or workflow diagnostic.  No live action, external write, deployment,
or network access is ever performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cre_foundry.architecture import protocol as protocol_mod
from cre_foundry.architecture import workflow as workflow_mod
from cre_foundry.architecture.protocol import ProtocolContext, ProtocolError

# --- Canonical synthetic problem and pinned MATH decision --------------------

REPRESENTATIVE_ID = "R-1"
ROUTE_DATE = "2026-08-02"
SUBMITTED_AT = "2026-08-01T12:00:00Z"
SOURCE_SNAPSHOT_SHA = "0" * 64
ROUTE_MANIFEST_SHA = "1" * 64
FIELD_EVENT_SHA = "2" * 64

# Pinned digest of the external MATH oracle decision for the canonical problem.
PINNED_MATH_DECISION_SHA256 = "2047b3b68cfc7545078676107e1e9a1848d6f8e694da23c8889ab146f31d3f58"


def _grain_ids() -> dict[str, Any]:
    return {
        name: None
        for name in ["legal_entity_id", "operating_business_id", "brand_id", "establishment_id", "unit_id", "property_id", "parcel_id", "owner_id", "occupier_id", "parent_group_id"]
    }


def _candidate(index: int) -> dict[str, Any]:
    return {
        "candidate_id": f"C{index:02d}",
        "physical_location_id": f"L{index:02d}",
        "grain_ids": _grain_ids(),
        "protection_tokens": [],
        "evidence_stage": 1,
        "observed_at": "2026-08-01T12:00:00Z",
        "gates": {name: "PASS" for name in ["evidence", "identity", "eligibility", "safety", "access", "operational"]},
        "protected_status": "CLEAR",
        "value_state": "REGISTERED_SYNTHETIC_PROXY",
        "business_value_units": 100 - index,
        "proximity_cost_units": index,
        "service_minutes": 10,
        "composition_group": None,
    }


def canonical_problem() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "decision_scope": "SYNTHETIC_FORMAL_ONLY",
        "decision_id": "D-ARCH-001",
        "snapshot": {
            "snapshot_id": "S-ARCH-001",
            "snapshot_sha256": SOURCE_SNAPSHOT_SHA,
            "stage1_cutoff": "2026-08-01T23:59:59Z",
            "issued_at": "2026-08-01T23:59:59Z",
            "protected_bundle_complete": True,
            "protected_tokens": [],
        },
        "route_day": {"representative_id": REPRESENTATIVE_ID, "route_date": ROUTE_DATE},
        "policy": {
            "policy_version": "math-policy-v1",
            "policy_sha256": "1" * 64,
            "epsilon_business_value_units": 0,
            "maximum_candidates": 20,
            "max_total_service_minutes": 200,
            "composition_caps": {},
            "required_unique_grains": [],
            "incompatible_candidate_pairs": [],
            "redundancy_penalties": [],
            "interference_penalties": [],
        },
        "candidates": [_candidate(index) for index in range(10)],
    }


def pinned_math_decision() -> dict[str, Any]:
    """The externally-produced MATH oracle decision consumed as data.

    The decision document is pinned: the driver asserts its canonical digest
    matches the known oracle output so it can never drift from the oracle.
    """
    decision = {
        "schema_version": "1.0.0",
        "decision_scope": "SYNTHETIC_FORMAL_ONLY",
        "oracle_version": "bounded-exhaustive-v1",
        "decision_id": "D-ARCH-001",
        "snapshot_sha256": SOURCE_SNAPSHOT_SHA,
        "policy_version": "math-policy-v1",
        "policy_sha256": "1" * 64,
        "decision": "ISSUE",
        "selected": [{"candidate_id": f"C{index:02d}", "physical_location_id": f"L{index:02d}"} for index in range(10)],
        "certificate": {
            "gross_business_value_units": 955,
            "redundancy_penalty_units": 0,
            "interference_penalty_units": 0,
            "business_value_units": 955,
            "proximity_cost_units": 45,
            "total_service_minutes": 100,
            "feasible_sets_evaluated": 1,
            "canonical_order_not_route_order": True,
        },
    }
    digest = protocol_mod.digest_json(decision)
    if digest != PINNED_MATH_DECISION_SHA256:
        raise RuntimeError(f"pinned MATH decision digest mismatch: got {digest}")
    return decision


def _aggregate_key(generation: int = 1) -> dict[str, Any]:
    return {
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "representative_id": REPRESENTATIVE_ID,
        "route_date": ROUTE_DATE,
        "generation": generation,
    }


def make_command(
    context: ProtocolContext,
    command_id: str,
    command_type: str,
    expected_version: int,
    payload: dict[str, Any],
    math_decision: dict[str, Any] | None,
    stage1_sha: str | None = None,
    idem_key: str | None = None,
) -> dict[str, Any]:
    if idem_key is None:
        idem_key = f"IDEM:{command_type}:{command_id}"
    binding_math = protocol_mod.digest_json(math_decision) if math_decision is not None else None
    return {
        "command_id": command_id,
        "command_type": command_type,
        "aggregate_key": _aggregate_key(generation=1),
        "expected_aggregate_version": expected_version,
        "idempotency_key": {
            "key": idem_key,
            "binding": {
                "contract_version": "1.0.0",
                "representative_id": REPRESENTATIVE_ID,
                "route_date": ROUTE_DATE,
                "generation": 1,
                "operation": command_type,
                "stage1_snapshot_sha256": stage1_sha,
                "math_decision_sha256": binding_math,
            },
        },
        "payload": payload,
        "payload_sha256": protocol_mod.digest_json(payload),
        "schema_version": "1.0.0",
        "contract_sha256": context.contract_sha256,
        "actor_class": "SYSTEM",
        "principal_reference": "principal-1",
        "requested_capability": protocol_mod.CAPABILITY_BY_COMMAND[command_type],
        "authorization_decision_sha256": protocol_mod.digest_json({"auth": command_id}),
        "correlation_id": f"CORR:{command_id}",
        "causation_id": None,
        "submitted_at": SUBMITTED_AT,
    }


def _authorization(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "GRANTED",
        "scope": "SYNTHETIC_NON_INFLUENCING",
        "capability": decision["requested_capability"],
        "principal_reference": decision["principal_reference"],
        "granted_by": "external-authority",
        "issued_at": "2026-08-01T00:00:00Z",
        "expires_at": "2026-08-03T00:00:00Z",
        "revoked_at": None,
    }


def authorize_all(commands: list[dict[str, Any]]) -> dict[str, Any]:
    return {command["authorization_decision_sha256"]: _authorization(command) for command in commands}


def canonical_commands(context: ProtocolContext, decision: dict[str, Any]) -> list[dict[str, Any]]:
    source = SOURCE_SNAPSHOT_SHA
    route = ROUTE_MANIFEST_SHA
    return [
        make_command(context, "CMD-APPEND-1", "APPEND_STAGE1", 0, {"evidence_kind": "STAGE1_OBSERVATION", "source_snapshot_sha256": source, "observation_ids": ["OBS-1"], "stage1_cutoff": "2026-08-01T23:59:59Z"}, None, stage1_sha=source),
        make_command(context, "CMD-FREEZE-1", "FREEZE_STAGE1", 1, {"stage1_snapshot_sha256": source}, None, stage1_sha=source),
        make_command(context, "CMD-DECIDE-1", "DECIDE_ISSUE", 2, {"decision_scope": "SYNTHETIC_FORMAL_ONLY", "math_decision_sha256": protocol_mod.digest_json(decision)}, decision, stage1_sha=source),
        make_command(context, "CMD-PREPARE-1", "PREPARE_SYNTHETIC_ISSUANCE", 3, {"route_date": ROUTE_DATE, "prepared_route_sha256": route}, decision, stage1_sha=source),
        make_command(context, "CMD-COMMIT-1", "COMMIT_SYNTHETIC_ISSUANCE", 4, {"route_manifest_sha256": route, "issuance_slot": {"execution_scope": "SYNTHETIC_NON_INFLUENCING", "representative_id": REPRESENTATIVE_ID, "route_date": ROUTE_DATE}}, decision, stage1_sha=source),
        make_command(context, "CMD-STAGE2-1", "APPEND_STAGE2", 5, {"route_manifest_sha256": route, "field_event_ids": ["FIELD_EVENT:F1"]}, decision, stage1_sha=source),
        make_command(context, "CMD-STAGE3-1", "APPEND_STAGE3", 6, {"field_event_id": "FIELD_EVENT:F1", "field_event_sha256": FIELD_EVENT_SHA, "outcome_ids": ["OUT-1"]}, decision, stage1_sha=source),
    ]


def review_record(record_id: str, sequence: int, action: str, annotations: list[str] | None = None, evidence_request: dict[str, Any] | None = None, predecessor: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "document_kind": "ARCHITECTURE_REVIEW_RECORD",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "canonicalization": "SORTED_KEYS_INTEGER_JSON_V1",
        "aggregate_key": _aggregate_key(generation=1),
        "review_sequence": sequence,
        "predecessor": predecessor,
        "actor_class": "MANUAL_REVIEWER",
        "principal_reference": "reviewer-1",
        "action": action,
        "annotations": annotations or [],
        "evidence_request": evidence_request,
        "recorded_at": "2026-08-01T13:00:00Z",
        "grants_real_authority": False,
        "status": "ACCEPTED",
        "forbidden_action": None,
    }


def canonical_review_records() -> list[dict[str, Any]]:
    record_one = review_record("REV-1", 1, "ANNOTATE", annotations=["accepted evidence looks consistent"])
    record_two = review_record(
        "REV-2", 2, "REQUEST_AUTHORITATIVE_EVIDENCE",
        evidence_request={"requested_evidence_kind": "STAGE1_OBSERVATION", "reason": "confirm cutoff"},
        predecessor={"review_id": "REV-1", "sha256": protocol_mod.digest_json(record_one)},
    )
    record_three = review_record(
        "REV-3", 3, "ABANDON_PREISSUANCE_GENERATION",
        predecessor={"review_id": "REV-2", "sha256": protocol_mod.digest_json(record_two)},
    )
    return [record_one, record_two, record_three]


def build_subject(
    context: ProtocolContext,
    problem: dict[str, Any],
    commands: list[dict[str, Any]],
    authorizations: dict[str, Any],
    decision: dict[str, Any],
    fault_schedule: Any = None,
    review_records: list[dict[str, Any]] | None = None,
    run_id: str = "RUN-ARCH-001",
) -> dict[str, Any]:
    """Validate the stream through the public protocol surface and assemble the subject."""
    protocol_mod.live_denial(context, "driver run")

    errors: list[str] = []
    for index, command in enumerate(commands):
        errors.extend(protocol_mod.validate_command_envelope(context, command, index))
    errors.extend(protocol_mod.check_authority_decisions(commands, authorizations))
    if errors:
        raise ProtocolError(errors[0].split(":", 1)[0], errors[0].split(":", 1)[1].strip())

    subject, errors = workflow_mod.assemble_subject(
        context,
        problem,
        commands,
        authorizations,
        decision,
        fault_schedule=fault_schedule,
        review_records=review_records,
        run_id=run_id,
    )
    if errors:
        raise ProtocolError(errors[0].split(":", 1)[0], errors[0].split(":", 1)[1].strip())
    return subject


def canonical_subject(context: ProtocolContext) -> dict[str, Any]:
    problem = canonical_problem()
    decision = pinned_math_decision()
    commands = canonical_commands(context, decision)
    authorizations = authorize_all(commands)
    return build_subject(
        context,
        problem,
        commands,
        authorizations,
        decision,
        fault_schedule=None,
        review_records=canonical_review_records(),
        run_id="RUN-ARCH-001",
    )


def write_subject(subject: dict[str, Any], path: Path | None) -> str:
    text = json.dumps(subject, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        sys.stdout.write(text)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCHITECTURE-001 black-box protocol driver")
    parser.add_argument("--command-stream", type=Path, help="command-stream JSON document")
    parser.add_argument("--canonical", action="store_true", help="generate the deterministic canonical run")
    parser.add_argument("--output", type=Path, help="output subject path (default: artifacts/architecture/canonical_run.json)")
    args = parser.parse_args()

    if args.canonical == args.command_stream is not None:
        parser.error("choose exactly one of --canonical or --command-stream")

    context = ProtocolContext(ROOT)
    try:
        if args.canonical:
            subject = canonical_subject(context)
            output = args.output or (ROOT / "artifacts/architecture/canonical_run.json")
        else:
            stream = protocol_mod.strict_load(args.command_stream)
            if not isinstance(stream, dict):
                raise ProtocolError("ARCH-SHAPE-INVALID", "command stream must be an object")
            if "problem" not in stream or "commands" not in stream:
                raise ProtocolError("ARCH-SHAPE-INVALID", "command stream requires problem and commands")
            if "math_decision" not in stream:
                raise ProtocolError("ARCH-DECISION-MISMATCH", "command stream requires the external MATH decision")
            subject = build_subject(
                context,
                stream["problem"],
                stream["commands"],
                stream.get("authorizations", {}),
                stream["math_decision"],
                fault_schedule=stream.get("fault_schedule"),
                review_records=stream.get("review_records"),
                run_id=stream.get("run_id", "RUN-ARCH-001"),
            )
            output = args.output
    except ProtocolError as exc:
        print(json.dumps({"passed": False, "errors": [f"{exc.code}: {exc.message}"], "exit": 1}, indent=2))
        return 1

    digest = write_subject(subject, output)
    print(json.dumps({"passed": True, "errors": [], "output": str(output) if output else "<stdout>", "subject_sha256": digest, "exit": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
