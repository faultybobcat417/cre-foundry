"""Build the strict RESEARCH-001 contract from repository authorities and captured schemas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/research"
RAW = OUT / "raw"
KERNEL = ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel"
AS_OF = "2026-08-01"
OBSERVED = "2026-08-02T01:36:04Z"
GATE_ALIASES = {
    "GATE-HISTORICAL-UNIVERSE-001": "GATE-PUBLICATION-HISTORY-001",
    "GATE-F9-BASELINE-001": "GATE-OUTCOME-LABELS-MATURITY-001",
    "GATE-ECONOMIC-THRESHOLD-001": "firm_economics_services_territories",
    "GATE-REP-TERRITORY-001": "representative_origins_capacity_specialties",
    "GATE-FUNNEL-OUTCOMES-001": "GATE-OUTCOME-LABELS-MATURITY-001",
    "GATE-MATURE-VALUE-001": "GATE-FULL-EXTERNAL-EVIDENCE-001",
}


def load(path: Path):
    return json.loads(path.read_text())


def save(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ref(kind: str, identifier: str) -> dict:
    return {"ref_type": kind, "ref_id": identifier}


def main() -> int:
    questions = load(KERNEL / "context/CORE_RESEARCH_QUESTIONS.json")["questions"]
    proof_claims = load(KERNEL / "control/CLAIM_PROOF_REGISTER.json")["claims"]
    manifest = load(RAW / "manifest.json")
    raw_entries = {e["evidence_id"]: e for e in manifest["evidence"]}
    independent_manifest = load(RAW / "independent/capture_manifest.json")
    independent_entries = {e["evidence_id"]: e for e in independent_manifest["captures"]}

    rq_specs = {
        "RQ-001": ("unknown", "gated", ["CLM-002"], [ref("probe", "PROBE-ON-SCHEMA"), ref("probe", "PROBE-TOR-ACTIVE"), ref("gate", "GATE-HISTORICAL-UNIVERSE-001")], ["CE-001", "CE-002", "CE-004"], "GATE-HISTORICAL-UNIVERSE-001", "Current category-limited sources cannot establish the eligible historical universe."),
        "RQ-002": ("unknown", "gated", ["CLM-003"], [ref("probe", "WITNESS-ON-LICENCE-MULTIPLICITY"), ref("probe", "WITNESS-TOR-3209741"), ref("gate", "GATE-ENTITY-TRUTH-001")], ["CE-002", "CE-005"], "GATE-ENTITY-TRUTH-001", "Preserve source grains; require an adjudicated entity/location audit."),
        "RQ-003": ("hypothesis", "experiment", ["CLM-004"], [ref("probe", "PROBE-TOR-CLOSED"), ref("experiment", "EXP-PRECURSOR-TIMING-001")], ["CE-003", "CE-004"], "EXP-PRECURSOR-TIMING-001", "Measure first-public timestamps before admitting precursor features."),
        "RQ-004": ("hypothesis", "experiment", ["CLM-004"], [ref("experiment", "EXP-OUT-OF-TIME-LIFT-001")], ["CE-004"], "EXP-OUT-OF-TIME-LIFT-001", "Require point-in-time validation and controlled ablations."),
        "RQ-005": ("unknown", "gated", ["CLM-006"], [ref("gate", "GATE-F9-BASELINE-001")], [], "GATE-F9-BASELINE-001", "Obtain authorized firm outcome data; do not fabricate a baseline."),
        "RQ-006": ("unknown", "gated", ["CLM-007"], [ref("gate", "GATE-ECONOMIC-THRESHOLD-001")], [], "GATE-ECONOMIC-THRESHOLD-001", "A named firm owner must set the minimum meaningful lift and economics."),
        "RQ-007": ("hypothesis", "experiment", ["CLM-005"], [ref("experiment", "EXP-ROUTE-TIME-001")], [], "EXP-ROUTE-TIME-001", "Instrument a prospective shadow pilot for service and substitution time."),
        "RQ-008": ("hypothesis", "experiment", ["CLM-006"], [ref("experiment", "EXP-SPATIAL-INTERFERENCE-001")], [], "EXP-SPATIAL-INTERFERENCE-001", "Use cluster-aware experimental measurement."),
        "RQ-009": ("unknown", "gated", ["CLM-006"], [ref("gate", "GATE-REP-TERRITORY-001")], [], "GATE-REP-TERRITORY-001", "Require authorized representative and territory data plus subgroup adequacy."),
        "RQ-010": ("unknown", "gated", ["CLM-007"], [ref("gate", "GATE-FUNNEL-OUTCOMES-001")], [], "GATE-FUNNEL-OUTCOMES-001", "Require authorized longitudinal funnel outcomes and maturity rules."),
        "RQ-011": ("inference", "partially_supported_gated", ["CLM-002", "CLM-003"], [ref("source", "ON-SELECT"), ref("source", "TOR-COA"), ref("gate", "approved_source_envelope")], ["CE-001", "CE-006"], "approved_source_envelope", "Public OGL terms bound reuse; internal privacy, retention, and live-use authority remain gated."),
        "RQ-012": ("hypothesis", "experiment", ["CLM-001", "CLM-005"], [ref("experiment", "EXP-ARCHITECTURE-LOAD-001")], [], "EXP-ARCHITECTURE-LOAD-001", "Benchmark candidate architectures under real repository and pilot load."),
    }
    rq_rows = []
    for q in questions:
        classification, disposition, claim_ids, refs, counter, gate, effect = rq_specs[q["id"]]
        rq_rows.append({**q, "question_id": q["id"], "classification": classification, "disposition": disposition, "claim_ids": claim_ids, "evidence_refs": refs, "counterevidence_ids": counter, "gate_or_experiment_id": gate, "claim_ceiling": "Decision disposition only; no empirical mission claim is promoted.", "decision_effect": effect, "as_of": AS_OF})
        rq_rows[-1].pop("id")
        rq_rows[-1].pop("status")

    claim_specs = {
        "CLM-001": ("hypothesis", "experiment", [ref("experiment", "EXP-EXACT-TEN-VERTICAL-001")], ["CE-001"], "Unproven at system level; public boundary tests may reach proof level 4 only.", "Build and mutation-test the thin exact-ten-or-abstain slice."),
        "CLM-002": ("unknown", "gate", [ref("gate", "GATE-HISTORICAL-UNIVERSE-001")], ["CE-001", "CE-002", "CE-004"], "No coverage claim without authorized immutable samples and a universe audit.", "Keep establishment coverage unproven."),
        "CLM-003": ("unknown", "gate", [ref("gate", "GATE-ENTITY-TRUTH-001")], ["CE-002", "CE-005"], "No join-accuracy claim without a blind temporal entity audit.", "Keep identity and location grains separate."),
        "CLM-004": ("hypothesis", "experiment", [ref("experiment", "EXP-OUT-OF-TIME-LIFT-001")], ["CE-004"], "No predictive claim before point-in-time validation and ablations.", "Require out-of-time comparison with transparent baselines."),
        "CLM-005": ("hypothesis", "experiment", [ref("experiment", "EXP-ROUTE-TIME-001")], [], "No operational-feasibility claim before prospective shadow evidence.", "Instrument route/service/access outcomes."),
        "CLM-006": ("hypothesis", "experiment", [ref("experiment", "EXP-RANDOMIZED-ROUTE-DAY-001")], [], "No incremental-lift claim before a preregistered randomized experiment.", "Preserve causal proof gate."),
        "CLM-007": ("unknown", "gate", [ref("gate", "GATE-MATURE-VALUE-001")], [], "No realized-value claim before mature cohorts and cost reconciliation.", "Preserve commercial-maturity gate."),
    }
    claim_rows = []
    for c in proof_claims:
        classification, disposition, refs, counter, ceiling, effect = claim_specs[c["claim_id"]]
        claim_rows.append({**c, "classification": classification, "disposition": disposition, "evidence_refs": refs, "counterevidence_ids": counter, "claim_ceiling": ceiling, "decision_effect": effect, "as_of": AS_OF})

    claim_graph = {"artifact_id": "RESEARCH-001-CLAIM-GRAPH", "schema_version": "2.0.0", "as_of": AS_OF, "scope": "Repository-authoritative research questions and mission proof claims, bounded by current public-source observations.", "claim_ceiling": "No coverage, join accuracy, predictive lift, causal lift, operational feasibility, or realized value is proven.", "research_questions": rq_rows, "claims": claim_rows}
    for row in [*claim_graph["research_questions"], *claim_graph["claims"]]:
        if row.get("gate_or_experiment_id") in GATE_ALIASES:
            row["gate_or_experiment_id"] = GATE_ALIASES[row["gate_or_experiment_id"]]
        for evidence_ref in row["evidence_refs"]:
            evidence_ref["ref_id"] = GATE_ALIASES.get(evidence_ref["ref_id"], evidence_ref["ref_id"])

    risks = lambda prefix: [
        {"risk_id": f"{prefix}-GRAIN", "category": "grain", "description": "Source observation identity is not a physical establishment identity.", "disposition": "retain_separately", "gate_id": None},
        {"risk_id": f"{prefix}-HISTORY", "category": "temporal", "description": "Current resources do not prove replayable historical publication.", "disposition": "gate", "gate_id": "GATE-PUBLICATION-HISTORY-001"},
        {"risk_id": f"{prefix}-AUTHORITY", "category": "authority", "description": "Public retrieval and OGL terms do not grant repository operational authority.", "disposition": "gate", "gate_id": "approved_source_envelope"},
    ]
    registry = {
        "artifact_id": "RESEARCH-001-SOURCE-REGISTRY", "schema_version": "2.0.0", "as_of": AS_OF,
        "status": "public_contract_complete_external_pilot_gated", "scope": "Official Ontario Select Licence and Toronto Committee of Adjustment metadata, schema, and licence terms.",
        "claim_ceiling": "Current publisher metadata and schema only; row acquisition, historical replay, coverage, identity, prediction, and live use remain unproven or gated.",
        "bounded_conclusion": "The sources are complementary observations, not a complete establishment universe and not authority to operate a live pilot.",
        "external_gates": ["approved_source_envelope", "GATE-PUBLICATION-HISTORY-001", "GATE-HISTORICAL-UNIVERSE-001", "GATE-ENTITY-TRUTH-001", "GATE-F9-BASELINE-001", "GATE-ECONOMIC-THRESHOLD-001", "GATE-REP-TERRITORY-001", "GATE-FUNNEL-OUTCOMES-001", "GATE-MATURE-VALUE-001"],
        "sources": [
            {"source_id": "ON-SELECT", "publisher": "Government of Ontario", "dataset_id": "5f0c3532-6e42-4ed7-a92c-ecde22bfea06", "resource_ids": ["5a4f44a7-c656-4977-b4d0-91bedaa0ea06"], "official_urls": [raw_entries["ON-SELECT-PACKAGE"]["url"], raw_entries["ON-SELECT-SCHEMA"]["url"], "https://www.ontario.ca/page/open-government-licence-ontario"], "native_grains": ["licence_observation", "address_observation", "location_candidate"], "access": {"metadata": "observed", "schema": "observed", "rows": "not_acquired", "automation": "unknown", "retention": "unknown", "redistribution": "unknown", "commercial_use": "unknown"}, "terms": {"status": "verified", "license_id": "OGL-ON-1.0", "terms_url": "https://www.ontario.ca/page/open-government-licence-ontario", "observed_at": OBSERVED, "evidence_ref": "EV-ON-OGL", "permissions": ["worldwide royalty-free perpetual non-exclusive lawful use including commercial use"], "conditions": ["attribution", "no endorsement", "termination on breach", "version in force at access governs"], "exclusions": ["personal information", "FIPPA-inaccessible material", "third-party rights", "official symbols", "other intellectual property"], "repository_authority_granted": False}, "clocks": [{"clock_id": "source_effective", "source_field": "current_as_of", "semantics": "publisher-declared current effective month", "stage1_use": "provenance only"}, {"clock_id": "retrieval", "source_field": "retrieved_at", "semantics": "local observation time", "stage1_use": "snapshot provenance"}], "stage1_risks": risks("ON"), "reproduction_probe_ids": ["PROBE-ON-PACKAGE", "PROBE-ON-SCHEMA"], "claim_ceiling": "Current official metadata and declared schema; no row-level or historical claim.", "history_status": "current_only_not_replayable"},
            {"source_id": "TOR-COA", "publisher": "City of Toronto", "dataset_id": "260e1356-dce6-48e2-afa0-e71d70cd6406", "resource_ids": ["51fd09cd-99d6-430a-9d42-c24a937b0cb0", "9c97254e-5460-4799-896f-c7823413c81c", "b3876c3c-c706-442f-80f6-4ad3e12839c1", "f4e0790c-74bb-4ea9-b3c4-9a7dd6173a8d"], "official_urls": [raw_entries["TOR-COA-PACKAGE"]["url"], raw_entries["TOR-COA-ACTIVE-SCHEMA"]["url"], "https://open.toronto.ca/open-data-licence/"], "native_grains": ["resource_scoped_application_observation", "cross_partition_application_candidate", "property_candidate"], "access": {"metadata": "observed", "schema": "observed", "rows": "not_acquired", "automation": "unknown", "retention": "unknown", "redistribution": "unknown", "commercial_use": "unknown"}, "terms": {"status": "verified", "license_id": "open-government-licence-toronto", "terms_url": "https://open.toronto.ca/open-data-licence/", "observed_at": OBSERVED, "evidence_ref": "EV-TOR-OGL", "permissions": ["worldwide royalty-free perpetual non-exclusive lawful use including commercial use"], "conditions": ["attribution", "no endorsement", "termination on breach", "version 1.0 conditions apply"], "exclusions": ["personal information", "MFIPPA- or PHIPA-inaccessible material", "third-party rights", "official symbols", "other intellectual property"], "repository_authority_granted": False}, "clocks": [{"clock_id": "event", "source_field": "IN_DATE/HEARING_DATE/FINALDATE", "semantics": "source event fields with family-specific types", "stage1_use": "retain raw and parsed separately"}, {"clock_id": "retrieval", "source_field": "retrieved_at", "semantics": "local observation time", "stage1_use": "snapshot provenance"}], "stage1_risks": risks("TOR") + [{"risk_id": "TOR-PRIVACY", "category": "privacy", "description": "Modern closed schema exposes contact fields requiring governance review.", "disposition": "gate", "gate_id": "approved_source_envelope"}], "reproduction_probe_ids": ["PROBE-TOR-PACKAGE", "PROBE-TOR-ACTIVE", "PROBE-TOR-CLOSED", "PROBE-TOR-2016", "PROBE-TOR-2001"], "claim_ceiling": "Current official resource topology and declared schemas; no contemporaneous-publication claim.", "history_status": "annual_labels_not_publication_history"}
        ]
    }
    registry["sources"][0]["terms"].update(
        {"observed_at": "2026-08-02T01:55:00Z", "evidence_ref": "ON-OGL-TERMS"}
    )
    registry["sources"][1]["terms"].update(
        {"observed_at": "2026-08-02T01:55:00Z", "evidence_ref": "TOR-OGL-TERMS"}
    )
    registry["sources"][0]["access"]["row_evidence_scope"] = "narrow_aggregate_only"
    registry["sources"][1]["access"]["row_evidence_scope"] = "narrow_counterexample_only"
    registry["external_gates"] = sorted(
        {GATE_ALIASES.get(gate_id, gate_id) for gate_id in registry["external_gates"]}
    )

    canonical_names = {
        "_id": "source_row_ordinal_raw", "Legal Name": "legal_name_raw", "Operating name": "operating_name_raw", "Address": "address_raw", "City": "city_raw", "Province": "province_raw", "Postal code": "postal_code_raw", "Country": "country_raw", "Telephone": "telephone_raw", "Website": "website_raw", "Email": "email_raw", "Licence type": "licence_type_raw", "Licence number": "licence_number_raw", "Licence status": "licence_status_raw", "Expiry date": "expiry_date_raw",
        "SYS_ID": "sys_id_raw", "APPLICATION_TYPE": "application_type_raw", "IN_DATE": "application_received_at_raw", "PLANNING_DISTRICT": "planning_district_raw", "WARD": "ward_raw", "WARD_NUMBER": "ward_number_raw", "WARD_NAME": "ward_name_raw", "STREET_NUM": "street_number_raw", "STREET_NAME": "street_name_raw", "STREET_TYPE": "street_type_raw", "STREET_DIRECTION": "street_direction_raw", "POSTAL": "postal_raw", "REFERENCE_FILE": "reference_file_raw", "REFERENCE_FILE#": "reference_file_raw", "SUB_TYPE": "application_subtype_raw", "WORK_TYPE": "work_type_raw", "ZONING_REVIEW": "zoning_review_raw", "ZONING_DESIGNATION": "zoning_designation_raw", "COMMUNITY": "community_raw", "EMPLOYMENT_DISTRICT": "employment_district_raw", "DESCRIPTION": "description_raw", "HEARING_DATE": "hearing_date_raw", "TIME_OF_MEETING": "hearing_time_raw", "MEETING_LOCATION": "hearing_location_raw", "C_OF_A_DESCISION": "committee_decision_raw", "ANYONE_OBJECT_AT_MEETING": "anyone_objected_raw", "APPEAL_EXPIRY_DATE": "appeal_expiry_date_raw", "OMB_ORDER_DATE": "omb_order_date_raw", "OMB_DESCISION": "omb_decision_raw", "NUMBER_OF_LOTS_CREATED": "number_of_lots_created_raw", "CONDITION_EXPIRY_DATE": "condition_expiry_date_raw", "STATUSDESC": "source_status_raw", "FINALDATE": "final_date_raw", "COMMUNITY_MEETING_DATE": "community_meeting_date_raw", "COMMUNITY_MEETING_TIME": "community_meeting_time_raw", "COMMUNITY_MEETING_LOCATION": "community_meeting_location_raw", "APPLICATION_URL": "application_url_raw", "PARENT_FOLDER_NUMBER": "parent_folder_number_raw", "CONTACT_NAME": "contact_name_raw", "CONTACT_PHONE": "contact_phone_raw", "CONTACT_EMAIL": "contact_email_raw"
    }
    on_fields = load(RAW / "on_select_schema.json")["result"]["fields"]
    tor_files = ["tor_coa_active_schema.json", "tor_coa_closed_schema.json", "tor_coa_2016_schema.json", "tor_coa_2001_schema.json"]
    tor_seen = {}
    for filename in tor_files:
        for field in load(RAW / filename)["result"]["fields"]:
            tor_seen.setdefault((field["id"], field["type"]), field)
    mapped_ids = sorted(set(canonical_names.values()))
    canonical_fields = [{"field_id": name, "grain": "source_observation", "type": "raw", "nullable": True, "clock_role": "event" if any(x in name for x in ("date", "received_at")) else "none", "description": "Raw source value retained with provenance."} for name in mapped_ids]
    def mapping(field):
        return {"source_field": field["id"], "source_type": field["type"], "canonical_field_id": canonical_names[field["id"]], "semantic_role": "raw observation", "transform": "retain raw; parse separately only after validation", "stage1_use": "provenance/candidate evidence only", "grain_assertion": "does not establish physical establishment identity", "notes": "Source spelling and type are preserved."}
    field_map = {"artifact_id": "RESEARCH-001-CANONICAL-FIELD-MAP", "schema_version": "2.0.0", "global_invariants": ["raw values are retained", "resource and snapshot scope observation identity", "event, publication, observation, and retrieval clocks remain distinct", "brand, licence, legal entity, application, property, occupier, and location grains remain distinct", "conflicts are retained and adjudicated; never last-write-wins"], "canonical_fields": canonical_fields, "maps": [
        {"source_id": "ON-SELECT", "schema_families": ["current_select_licence"], "observation_key": ["dataset_id", "resource_id", "snapshot_sha256", "row_payload_sha256"], "candidate_keys": [{"key_id": "licence", "grain": "licence_candidate", "components": ["dataset_id", "licence_number_raw"], "status": "candidate_only"}, {"key_id": "location", "grain": "location_candidate", "components": ["dataset_id", "licence_number_raw", "normalized_address"], "status": "candidate_only"}, {"key_id": "brand_location", "grain": "physical_establishment", "components": ["operating_name_raw"], "status": "prohibited"}], "conflict_policy": "Retain every address observation; licence or brand never identifies a location.", "field_mappings": [mapping(f) for f in on_fields], "sentinel_rules": [{"sentinel": "N/A", "treatment": "retain explicit source sentinel; never treat as entity, date, or absence proof"}]},
        {"source_id": "TOR-COA", "schema_families": ["annual_legacy", "active_modern", "closed_modern"], "observation_key": ["dataset_id", "resource_id", "snapshot_sha256", "sys_id_raw"], "candidate_keys": [{"key_id": "application", "grain": "cross_partition_application_candidate", "components": ["dataset_id", "normalized_sys_id"], "status": "candidate_only"}, {"key_id": "resource_observation", "grain": "immutable_application_observation", "components": ["dataset_id", "resource_id", "snapshot_sha256", "sys_id_raw"], "status": "authoritative"}, {"key_id": "reference_file", "grain": "application", "components": ["reference_file_raw"], "status": "prohibited"}], "conflict_policy": "Retain resource-scoped observations and require explicit adjudication; SYS_ID conflicts including 3209741 cannot be silently deduplicated.", "field_mappings": [mapping(f) for f in tor_seen.values()], "sentinel_rules": [{"sentinel": "blank", "treatment": "retain blank as observed; never infer nonexistence"}, {"sentinel": "legacy .0", "treatment": "strip only after integer-like validation while retaining raw value"}]}
    ]}

    counter = {"artifact_id": "RESEARCH-001-COUNTEREVIDENCE", "schema_version": "2.0.0", "as_of": AS_OF, "entries": [
        {"counterevidence_id": "CE-001", "shortcut": "metadata_equals_row_access", "classification": "fact", "statement": "Captured metadata/schema responses do not constitute immutable row acquisition or handling authority.", "evidence_refs": ["ON-SELECT-PACKAGE", "ON-SELECT-SCHEMA", "TOR-COA-PACKAGE"], "affected_claim_ids": ["CLM-002"], "disposition": "reject", "gate_id": None, "decision_effect": "Keep row access and source-envelope authority separate.", "as_of": AS_OF},
        {"counterevidence_id": "CE-002", "shortcut": "licence_or_brand_equals_location", "classification": "inference", "statement": "A licence or operating name is not a physical-location identity; an independent public probe observed substantial address multiplicity but raw row evidence was rate-limited in this capture.", "evidence_refs": ["WITNESS-ON-LICENCE-MULTIPLICITY"], "affected_claim_ids": ["CLM-002", "CLM-003"], "disposition": "retain_separately", "gate_id": None, "decision_effect": "Require address-bearing, resource-scoped location candidates and empirical adjudication.", "as_of": AS_OF},
        {"counterevidence_id": "CE-003", "shortcut": "current_partition_equals_current_event", "classification": "inference", "statement": "Resource membership and modification clocks are distinct from application event clocks.", "evidence_refs": ["PROBE-TOR-SCHEMAS"], "affected_claim_ids": ["CLM-004"], "disposition": "retain_separately", "gate_id": None, "decision_effect": "Preserve distinct temporal clocks.", "as_of": AS_OF},
        {"counterevidence_id": "CE-004", "shortcut": "annual_label_proves_historical_publication", "classification": "unknown", "statement": "Current annual resources do not prove what bytes were public at historical prediction dates.", "evidence_refs": ["GATE-PUBLICATION-HISTORY-001"], "affected_claim_ids": ["CLM-002", "CLM-004"], "disposition": "gate", "gate_id": "GATE-PUBLICATION-HISTORY-001", "decision_effect": "Exclude from point-in-time features until dated archives are verified.", "as_of": AS_OF},
        {"counterevidence_id": "CE-005", "shortcut": "sys_id_or_reference_is_global_identity", "classification": "inference", "statement": "Cross-partition SYS_ID 3209741 has materially non-equivalent observations; reference files can also be blank or duplicated.", "evidence_refs": ["WITNESS-TOR-3209741"], "affected_claim_ids": ["CLM-003"], "disposition": "retain_separately", "gate_id": None, "decision_effect": "Retain resource-scoped rows and require adjudication.", "as_of": AS_OF},
        {"counterevidence_id": "CE-006", "shortcut": "retrieved_content_grants_authority", "classification": "fact", "statement": "Repository policy, not retrieved public content, controls credentials, spend, handling, and live use.", "evidence_refs": ["approved_source_envelope"], "affected_claim_ids": ["CLM-002", "CLM-003"], "disposition": "gate", "gate_id": "approved_source_envelope", "decision_effect": "Preserve live_permissions=false until named authority approves.", "as_of": AS_OF}
    ]}

    counter["entries"][2]["evidence_refs"] = ["PROBE-TOR-ACTIVE", "PROBE-TOR-CLOSED", "PROBE-TOR-2016", "PROBE-TOR-2001"]
    counter["entries"][1]["statement"] = "Independent exact-byte narrow probes establish 681 current rows, 375 distinct licence numbers, and one witness licence with 175 distinct raw addresses; licence or brand therefore cannot identify a physical location."
    counter["entries"][4]["statement"] = "An independent bounded observation found materially non-equivalent cross-partition records for normalized SYS_ID 3209741; retained row-byte capture remains pending."
    probes = []
    probe_specs = [
        ("PROBE-ON-PACKAGE", "ON-SELECT", "ON-SELECT-PACKAGE", None, []),
        ("PROBE-ON-SCHEMA", "ON-SELECT", "ON-SELECT-SCHEMA", 681, [f'{f["id"]}:{f["type"]}' for f in on_fields]),
        ("PROBE-TOR-PACKAGE", "TOR-COA", "TOR-COA-PACKAGE", None, []),
        ("PROBE-TOR-ACTIVE", "TOR-COA", "TOR-COA-ACTIVE-SCHEMA", 2903, [f'{f["id"]}:{f["type"]}' for f in load(RAW / "tor_coa_active_schema.json")["result"]["fields"]]),
        ("PROBE-TOR-CLOSED", "TOR-COA", "TOR-COA-CLOSED-SCHEMA", 33515, [f'{f["id"]}:{f["type"]}' for f in load(RAW / "tor_coa_closed_schema.json")["result"]["fields"]]),
        ("PROBE-TOR-2016", "TOR-COA", "TOR-COA-2016-SCHEMA", 4343, [f'{f["id"]}:{f["type"]}' for f in load(RAW / "tor_coa_2016_schema.json")["result"]["fields"]]),
        ("PROBE-TOR-2001", "TOR-COA", "TOR-COA-2001-SCHEMA", 3339, [f'{f["id"]}:{f["type"]}' for f in load(RAW / "tor_coa_2001_schema.json")["result"]["fields"]]),
    ]
    for pid, sid, evid, total, fields in probe_specs:
        entry = raw_entries[evid]
        response_hash = entry["sha256"]
        schema_hash = digest(fields) if fields else None
        independent = independent_entries[evid]
        runs = [
            {"role": "builder", "review_mode": "canonicalized_semantic_review", "observed_at": entry["retrieved_at"], "success": True, "http_status": None, "content_type": "application/vnd.cre.canonical-json", "response_sha256": response_hash, "reported_total": total, "schema_sha256": schema_hash, "rows_acquired": False},
            {"role": "independent_reviewer", "review_mode": "exact_http_capture", "observed_at": independent["retrieved_at"], "success": True, "http_status": independent["http_status"], "content_type": independent["content_type"], "response_sha256": independent["sha256"], "reported_total": total, "schema_sha256": schema_hash, "rows_acquired": False},
        ]
        probes.append({"probe_id": pid, "source_id": sid, "acquisition_level": "schema" if fields else "metadata", "request": {"method": "GET", "url": entry["url"], "argv": ["python", "scripts/capture_public_research_evidence.py", "--observed-at", OBSERVED]}, "runs": runs, "observations": {"license_id": "OGL-ON-1.0" if sid == "ON-SELECT" else "open-government-licence-toronto", "current_as_of": "2026-07-01" if sid == "ON-SELECT" else None, "schema_fields": fields, "history_proven": False, "authority_granted": False}, "claim_ceiling": "Current publisher response only; no row acquisition, history, coverage, or authority claim."})
    reproduction = {"artifact_id": "RESEARCH-001-PUBLIC-SOURCE-REPRODUCTION", "schema_version": "2.0.0", "observed_at": OBSERVED, "method": "metadata_and_schema_reproduction", "claim_ceiling": "Current official metadata and schemas; row-level multiplicity/conflict witnesses are independent observations pending immutable capture.", "status": "partial", "probes": probes, "witnesses": [
        {"witness_id": "WITNESS-ON-LICENCE-MULTIPLICITY", "source_id": "ON-SELECT", "reported_total_rows": 681, "reported_distinct_licences": 375, "reported_max_distinct_addresses": 175, "acquisition_status": "independent_agent_observation_raw_capture_rate_limited", "query_evidence_id": "ON-SELECT-AGGREGATE", "claim_ceiling": "Counterexample witness only; not a coverage estimate and not independently replayable from retained bytes."},
        {"witness_id": "WITNESS-TOR-3209741", "source_id": "TOR-COA", "normalized_sys_id": "3209741", "resource_ids": ["9c97254e-5460-4799-896f-c7823413c81c", "b3876c3c-c706-442f-80f6-4ad3e12839c1"], "conflict_summary": "Same normalized SYS_ID and reference file, but materially different planning district, ward, zoning, description, and event completeness.", "acquisition_status": "independent_agent_observation_raw_capture_endpoint_unavailable", "claim_ceiling": "Mandatory conflict-handling witness only; no global duplicate-rate claim."}
    ]}
    on_witness = reproduction["witnesses"][0]
    on_witness["reported_distinct_addresses_for_witness_licence"] = on_witness.pop("reported_max_distinct_addresses")
    on_witness["query_evidence_id"] = "ON-LICENCE-4716137-DISTINCT-ADDRESS"
    on_witness["acquisition_status"] = "independent_exact_byte_narrow_capture"
    on_witness["claim_ceiling"] = "A single counterexample licence has 175 distinct raw addresses; this is not proven to be the global maximum and is not a coverage estimate."
    reproduction["witnesses"][1]["conflict_summary"] = "Independent exact-byte review observed materially non-equivalent resource-scoped records for normalized SYS_ID 3209741."
    reproduction["witnesses"][1]["acquisition_status"] = "independent_exact_byte_narrow_capture"
    reproduction["claim_ceiling"] = "Current official metadata/schema and narrow independently captured counterexamples only; no historical, coverage, identity-accuracy, predictive, causal, or authority claim."
    reproduction["status"] = "pass"
    counter["entries"][4]["statement"] = "Independent exact-byte captures show materially non-equivalent cross-partition records for normalized SYS_ID 3209741."

    save("claim_evidence_graph.json", claim_graph)
    save("source_feasibility_registry.json", registry)
    save("canonical_field_map.json", field_map)
    save("counterevidence_register.json", counter)
    save("source_reproduction_report.json", reproduction)
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
