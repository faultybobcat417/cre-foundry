from __future__ import annotations

import csv
import hashlib
import json
import os
import shlex
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path

GATE_CHECKLISTS: dict[str, list[str]] = {
    "evidence_resolution": [
        "Identify every business associated with the permit address and unit.",
        "Resolve conflicting, ambiguous or missing identity evidence.",
        "Record an authoritative source for the selected identity.",
        "Leave the task unresolved when the evidence remains insufficient.",
    ],
    "identity_verification": [
        "Verify the current legal or operating business name.",
        "Confirm the identity is linked to the permit address and unit.",
        "Record identifiers, source date and alternate operating names.",
    ],
    "permit_occupancy_verification": [
        "Determine whether the business is the applicant or intended occupant.",
        "Exclude contractors, landlords and unrelated address occupants.",
        "Record evidence supporting the occupancy relationship.",
    ],
    "commercial_requirement_verification": [
        "Verify a current or credible future real-estate requirement.",
        "Record requirement type, geography, timing and supporting evidence.",
        "Do not treat a permit alone as proof of a brokerage opportunity.",
    ],
    "decision_maker_verification": [
        "Identify the person responsible for the verified requirement.",
        "Verify their current role and relevant authority.",
        "Record the source without authorizing contact.",
    ],
    "existing_client_exclusion": [
        "Search current client and affiliated-account records.",
        "Record whether the account is an existing client.",
        "Escalate uncertain account matches for internal review.",
    ],
    "protected_relationship_check": [
        "Check protected, reserved and broker-owned relationship records.",
        "Record the relationship owner and applicable restriction.",
    ],
    "active_assignment_conflict_check": [
        "Search active mandates, listings and assignment records.",
        "Record any active or recent conflict that restricts action.",
    ],
    "territory_restriction_check": [
        "Check geographic, specialization and representative restrictions.",
        "Record the permitted territory or restriction.",
    ],
    "relationship_owner_check": [
        "Identify the internal owner of any existing relationship.",
        "Record whether internal approval would be required.",
    ],
    "do_not_contact_check": [
        "Search do-not-contact and legal restriction records.",
        "Record the result, source and effective date.",
    ],
}


GATE_SOURCE_TYPES: dict[str, list[str]] = {
    "evidence_resolution": [
        "official_registry",
        "municipal_record",
        "company_website",
        "property_record",
    ],
    "identity_verification": [
        "official_registry",
        "company_website",
        "municipal_record",
    ],
    "permit_occupancy_verification": [
        "permit_document",
        "applicant_confirmation",
        "property_record",
    ],
    "commercial_requirement_verification": [
        "decision_maker_confirmation",
        "public_company_disclosure",
        "verified_assignment_document",
    ],
    "decision_maker_verification": [
        "company_website",
        "professional_profile",
        "direct_confirmation",
    ],
    "existing_client_exclusion": [
        "internal_crm",
        "internal_account_registry",
    ],
    "protected_relationship_check": [
        "internal_relationship_registry",
        "internal_crm",
    ],
    "active_assignment_conflict_check": [
        "internal_assignment_registry",
        "internal_crm",
    ],
    "territory_restriction_check": [
        "internal_territory_policy",
        "representative_assignment_registry",
    ],
    "relationship_owner_check": [
        "internal_relationship_registry",
        "internal_crm",
    ],
    "do_not_contact_check": [
        "internal_do_not_contact_registry",
        "legal_restriction_registry",
    ],
}


def _iso_timestamp(
    value: datetime,
) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_value(
    value: Any,
) -> Any:
    if isinstance(
        value,
        datetime,
    ):
        return _iso_timestamp(value)

    return value


def _parse_name_list(
    value: Any,
) -> list[str]:
    if value in {
        None,
        "",
    }:
        return []

    parsed = json.loads(str(value))

    if not isinstance(
        parsed,
        list,
    ):
        raise RuntimeError("Candidate names must be a JSON list.")

    return [str(item) for item in parsed]


def _packet_hash(
    packet: dict[str, Any],
) -> str:
    canonical = json.dumps(
        packet,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _packet_basename(
    priority: int,
    permit_number: str,
    gate_id: str,
    task_id: str,
) -> str:
    safe_permit = "".join(
        character if character.isalnum() else "-" for character in permit_number
    ).strip("-")

    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:10]

    return f"{priority:03d}_{safe_permit}_{gate_id}_{digest}"


def _write_text_atomic(
    path: Path,
    text: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _command_templates(
    task_id: str,
) -> dict[str, str]:
    base = f"uv run cre-foundry source record-brampton-verification-event {shlex.quote(task_id)}"

    return {
        "start": (f"{base} task_started --reviewer '<reviewer>'"),
        "add_evidence": (
            f"{base} evidence_added "
            "--reviewer '<reviewer>' "
            "--evidence-source-type '<source_type>' "
            "--evidence-reference '<reference>' "
            "--notes '<findings>'"
        ),
        "pass": (f"{base} task_passed --reviewer '<reviewer>' --notes '<conclusion>'"),
        "fail": (f"{base} task_failed --reviewer '<reviewer>' --notes '<conclusion>'"),
    }


def _render_markdown(
    packet: dict[str, Any],
) -> str:
    permit = packet["permit"]
    gate = packet["gate"]
    state = packet["task_state"]
    evidence = packet["opportunity_evidence"]
    commands = packet["event_command_templates"]

    checklist = "\n".join(f"- [ ] {item}" for item in packet["analyst_checklist"])

    historical_names = ", ".join(evidence["historical_candidate_names"]) or "None"

    current_names = ", ".join(evidence["current_candidate_names"]) or "None"

    source_types = ", ".join(packet["suggested_evidence_source_types"])

    return f"""# Verification Review Packet

## Queue

- Priority: {packet["queue_priority"]}
- Task ID: {packet["verification_task_id"]}
- Status: {state["task_status"]}
- Result: {state["verification_result"]}
- Ready: {state["task_ready"]}

## Permit

- Permit: {permit["permit_number"]}
- Application time: {permit["application_at_utc"]}
- Event: {permit["event_type"]}
- Signal strength: {permit["signal_strength"]}
- Address: {permit["address_raw"]}

## Gate

- Gate: {gate["gate_id"]}
- Category: {gate["category"]}
- Instruction: {gate["instruction"]}
- Prerequisite: {gate["prerequisite_gate_id"]}
- Prerequisite passed: {gate["prerequisite_passed"]}

## Opportunity Evidence

- Evidence status: {evidence["evidence_status"]}
- Reconciliation class: {evidence["reconciliation_class"]}
- Reconciliation state: {evidence["reconciliation_state"]}
- Provisional business: {evidence["provisional_business_name"]}
- Provisional source: {evidence["provisional_business_source"]}
- Historical candidates: {historical_names}
- Current candidates: {current_names}
- Name similarity: {evidence["name_similarity"]}
- Directory global ID: {evidence["directory_global_id"]}
- Directory NAICS 2: {evidence["current_directory_naics_2"]}
- Employee group: {evidence["current_directory_employee_group"]}
- Phone present: {evidence["current_directory_phone_present"]}
- Website present: {evidence["current_directory_website_present"]}

## Analyst Checklist

{checklist}

## Evidence Record

Suggested source types: {source_types}

- Reviewer:
- Evidence source type:
- Evidence reference:
- Evidence date:
- Findings:
- Contradictory evidence:
- Remaining uncertainty:
- Proposed result:

## Event Commands

Start task:

    {commands["start"]}

Add evidence:

    {commands["add_evidence"]}

Pass after evidence is recorded:

    {commands["pass"]}

Fail after evidence is recorded:

    {commands["fail"]}

## Safety

This packet is verification work, not an opportunity ranking or contact
authorization.

- Operating mode: {packet["policy"]["operating_mode"]}
- Opportunity ranked: {packet["policy"]["opportunity_ranked"]}
- Authorization required:
  {packet["policy"]["outreach_authorization_required"]}
- Outreach eligible: {packet["policy"]["outreach_eligible"]}
- Automatic conclusion allowed:
  {packet["policy"]["automatic_conclusion_allowed"]}

Packet SHA-256: {packet["packet_sha256"]}
"""


def build_brampton_verification_review_packets(
    project_root: Path,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(UTC)

    generated_text = _iso_timestamp(generated)

    snapshot_id = generated.strftime("%Y%m%dT%H%M%S%fZ")

    output_root = project_root / "outputs" / "brampton_verification_review_packets" / snapshot_id

    packet_directory = output_root / "packets"

    connection = duckdb.connect(
        str(warehouse_path(project_root)),
        read_only=True,
    )

    try:
        cursor = connection.execute(
            """
            SELECT
                queue.verification_task_id,
                queue.opportunity_evidence_id,
                queue.permit_source_record_id,
                queue.permit_number,
                queue.application_at_utc,
                queue.permit_event_type,
                queue.signal_strength,
                queue.address_raw,
                queue.evidence_status,
                queue.provisional_business_name,
                queue.provisional_business_source,
                queue.gate_id,
                queue.task_order,
                queue.gate_category,
                queue.task_instruction,
                queue.prerequisite_gate_id,
                queue.prerequisite_task_id,
                queue.prerequisite_passed,
                queue.required,
                queue.blocking,
                queue.queue_priority,
                queue.workflow_priority_only,
                queue.task_status,
                queue.verification_result,
                queue.gate_cleared,
                queue.evidence_count_total,
                queue.evidence_count_since_reset,
                queue.task_ready,
                queue.outreach_authorization_required,
                queue.opportunity_ranked,
                queue.outreach_eligible,
                queue.operating_mode,
                opportunity.reconciliation_class,
                opportunity.reconciliation_state,
                opportunity.historical_candidate_names_json,
                opportunity.current_candidate_names_json,
                opportunity.name_similarity,
                opportunity.directory_global_id,
                opportunity.current_directory_naics_2,
                opportunity.current_directory_naics_6,
                opportunity.current_directory_employee_group,
                opportunity.current_directory_phone_present,
                opportunity.current_directory_website_present,
                opportunity.high_information_review_required,
                opportunity.unresolved_research_required,
                opportunity.manual_resolution_required
            FROM
                control.brampton_verification_active_queue
                    AS queue
            INNER JOIN
                silver.brampton_permit_opportunity_evidence
                    AS opportunity
            ON
                queue.opportunity_evidence_id
                =
                opportunity.opportunity_evidence_id
            ORDER BY
                queue.queue_priority,
                queue.application_at_utc DESC,
                queue.permit_number,
                queue.task_order
            """
        )

        description = cursor.description

        if description is None:
            raise RuntimeError("Review-packet query returned no column description.")

        columns = [str(column[0]) for column in description]

        source_rows = [
            dict(
                zip(
                    columns,
                    row,
                    strict=True,
                )
            )
            for row in cursor.fetchall()
        ]

        count_row = connection.execute(
            """
            SELECT count(*)
            FROM
                control.brampton_verification_active_queue
            """
        ).fetchone()

        event_count_row = connection.execute(
            """
            SELECT count(*)
            FROM
                control.brampton_verification_events
            """
        ).fetchone()

    finally:
        connection.close()

    if count_row is None:
        raise RuntimeError("Active queue count returned no row.")

    if event_count_row is None:
        raise RuntimeError("Projected event count returned no row.")

    active_queue_count = int(count_row[0])

    projected_event_count = int(event_count_row[0])

    if len(source_rows) != active_queue_count:
        raise RuntimeError("Review-packet join lost active tasks.")

    packet_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    manifest_packets: list[dict[str, Any]] = []

    csv_rows: list[dict[str, Any]] = []

    gate_distribution: Counter[str] = Counter()

    strength_distribution: Counter[str] = Counter()

    evidence_distribution: Counter[str] = Counter()

    safety_violation_count = 0

    for source_row in source_rows:
        task_id = str(source_row["verification_task_id"])

        gate_id = str(source_row["gate_id"])

        checklist = GATE_CHECKLISTS.get(gate_id)

        if checklist is None:
            raise RuntimeError(f"No checklist exists for {gate_id}.")

        packet: dict[str, Any] = {
            "packet_version": ("brampton-verification-review-packet-v1"),
            "generated_at": generated_text,
            "verification_task_id": task_id,
            "opportunity_evidence_id": str(source_row["opportunity_evidence_id"]),
            "permit_source_record_id": str(source_row["permit_source_record_id"]),
            "queue_priority": int(source_row["queue_priority"]),
            "permit": {
                "permit_number": str(source_row["permit_number"]),
                "application_at_utc": (_json_value(source_row["application_at_utc"])),
                "event_type": str(source_row["permit_event_type"]),
                "signal_strength": str(source_row["signal_strength"]),
                "address_raw": str(source_row["address_raw"]),
            },
            "gate": {
                "gate_id": gate_id,
                "task_order": int(source_row["task_order"]),
                "category": str(source_row["gate_category"]),
                "instruction": str(source_row["task_instruction"]),
                "prerequisite_gate_id": (source_row["prerequisite_gate_id"]),
                "prerequisite_task_id": (source_row["prerequisite_task_id"]),
                "prerequisite_passed": bool(source_row["prerequisite_passed"]),
                "required": bool(source_row["required"]),
                "blocking": bool(source_row["blocking"]),
            },
            "task_state": {
                "task_status": str(source_row["task_status"]),
                "verification_result": str(source_row["verification_result"]),
                "gate_cleared": bool(source_row["gate_cleared"]),
                "evidence_count_total": int(source_row["evidence_count_total"]),
                "evidence_count_since_reset": int(source_row["evidence_count_since_reset"]),
                "task_ready": bool(source_row["task_ready"]),
            },
            "opportunity_evidence": {
                "evidence_status": str(source_row["evidence_status"]),
                "reconciliation_class": str(source_row["reconciliation_class"]),
                "reconciliation_state": str(source_row["reconciliation_state"]),
                "provisional_business_name": (source_row["provisional_business_name"]),
                "provisional_business_source": (source_row["provisional_business_source"]),
                "historical_candidate_names": (
                    _parse_name_list(source_row["historical_candidate_names_json"])
                ),
                "current_candidate_names": (
                    _parse_name_list(source_row["current_candidate_names_json"])
                ),
                "name_similarity": (source_row["name_similarity"]),
                "directory_global_id": (source_row["directory_global_id"]),
                "current_directory_naics_2": (source_row["current_directory_naics_2"]),
                "current_directory_naics_6": (source_row["current_directory_naics_6"]),
                "current_directory_employee_group": (
                    source_row["current_directory_employee_group"]
                ),
                "current_directory_phone_present": bool(
                    source_row["current_directory_phone_present"]
                ),
                "current_directory_website_present": bool(
                    source_row["current_directory_website_present"]
                ),
                "high_information_review_required": bool(
                    source_row["high_information_review_required"]
                ),
                "unresolved_research_required": bool(source_row["unresolved_research_required"]),
                "manual_resolution_required": bool(source_row["manual_resolution_required"]),
            },
            "analyst_checklist": checklist,
            "required_evidence_fields": [
                "reviewer",
                "evidence_source_type",
                "evidence_reference",
                "evidence_date",
                "findings",
                "remaining_uncertainty",
                "proposed_result",
            ],
            "suggested_evidence_source_types": (GATE_SOURCE_TYPES[gate_id]),
            "event_command_templates": (_command_templates(task_id)),
            "policy": {
                "workflow_priority_only": bool(source_row["workflow_priority_only"]),
                "automatic_conclusion_allowed": False,
                "opportunity_ranked": bool(source_row["opportunity_ranked"]),
                "outreach_authorization_required": bool(
                    source_row["outreach_authorization_required"]
                ),
                "outreach_eligible": bool(source_row["outreach_eligible"]),
                "operating_mode": str(source_row["operating_mode"]),
            },
        }

        policy = packet["policy"]
        task_state = packet["task_state"]

        if (
            policy["opportunity_ranked"]
            or policy["outreach_eligible"]
            or not policy["outreach_authorization_required"]
            or policy["operating_mode"] != "shadow"
            or task_state["gate_cleared"]
            or task_state["verification_result"] != "unknown"
        ):
            safety_violation_count += 1

        packet["packet_sha256"] = _packet_hash(packet)

        permit_number = str(packet["permit"]["permit_number"])

        priority = int(packet["queue_priority"])

        basename = _packet_basename(
            priority,
            permit_number,
            gate_id,
            task_id,
        )

        json_path = packet_directory / f"{basename}.json"

        markdown_path = packet_directory / f"{basename}.md"

        write_json_atomic(
            json_path,
            packet,
        )

        _write_text_atomic(
            markdown_path,
            _render_markdown(packet),
        )

        relative_json = str(json_path.relative_to(output_root))

        relative_markdown = str(markdown_path.relative_to(output_root))

        manifest_packets.append(
            {
                "verification_task_id": task_id,
                "permit_number": permit_number,
                "gate_id": gate_id,
                "queue_priority": priority,
                "packet_sha256": (packet["packet_sha256"]),
                "json_path": relative_json,
                "markdown_path": (relative_markdown),
            }
        )

        csv_rows.append(
            {
                "queue_priority": priority,
                "permit_number": permit_number,
                "signal_strength": (packet["permit"]["signal_strength"]),
                "event_type": (packet["permit"]["event_type"]),
                "evidence_status": (packet["opportunity_evidence"]["evidence_status"]),
                "provisional_business_name": (
                    packet["opportunity_evidence"]["provisional_business_name"] or ""
                ),
                "gate_id": gate_id,
                "task_status": (task_state["task_status"]),
                "verification_result": (task_state["verification_result"]),
                "json_path": relative_json,
                "markdown_path": (relative_markdown),
                "outreach_eligible": False,
            }
        )

        gate_distribution[gate_id] += 1

        strength_distribution[str(packet["permit"]["signal_strength"])] += 1

        evidence_distribution[str(packet["opportunity_evidence"]["evidence_status"])] += 1

    if safety_violation_count != 0:
        raise RuntimeError("Review packets violated safety policy.")

    manifest = {
        "manifest_version": ("brampton-verification-review-manifest-v1"),
        "generated_at": generated_text,
        "snapshot_id": snapshot_id,
        "projected_event_count": (projected_event_count),
        "packet_count": len(manifest_packets),
        "gate_distribution": dict(sorted(gate_distribution.items())),
        "signal_strength_distribution": dict(sorted(strength_distribution.items())),
        "evidence_status_distribution": dict(sorted(evidence_distribution.items())),
        "safety_violation_count": (safety_violation_count),
        "packets": manifest_packets,
        "policy": {
            "analyst_conclusions_included": False,
            "task_state_modified": False,
            "opportunity_ranked": False,
            "outreach_authorization_required": True,
            "outreach_eligible": False,
            "operating_mode": "shadow",
        },
    }

    manifest_path = output_root / "manifest.json"

    write_json_atomic(
        manifest_path,
        manifest,
    )

    csv_path = output_root / "queue.csv"

    temporary_csv = output_root / ".queue.csv.tmp"

    fieldnames = [
        "queue_priority",
        "permit_number",
        "signal_strength",
        "event_type",
        "evidence_status",
        "provisional_business_name",
        "gate_id",
        "task_status",
        "verification_result",
        "json_path",
        "markdown_path",
        "outreach_eligible",
    ]

    with temporary_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(csv_rows)

        stream.flush()
        os.fsync(stream.fileno())

    temporary_csv.replace(csv_path)

    report: dict[str, Any] = {
        "model_version": ("brampton-verification-review-packets-v1"),
        "generated_at": generated_text,
        "snapshot_id": snapshot_id,
        "projected_event_count": (projected_event_count),
        "active_queue_count": (active_queue_count),
        "packet_count": len(manifest_packets),
        "json_packet_count": len(list(packet_directory.glob("*.json"))),
        "markdown_packet_count": len(list(packet_directory.glob("*.md"))),
        "safety_violation_count": (safety_violation_count),
        "gate_distribution": dict(sorted(gate_distribution.items())),
        "signal_strength_distribution": dict(sorted(strength_distribution.items())),
        "evidence_status_distribution": dict(sorted(evidence_distribution.items())),
        "output_root": str(output_root.relative_to(project_root)),
        "manifest_path": str(manifest_path.relative_to(project_root)),
        "queue_csv_path": str(csv_path.relative_to(project_root)),
        "policy": manifest["policy"],
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "brampton_verification_review_packets.json"
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
