"""Validate the strict RESEARCH-001 bundle; stored PASS labels are never trusted."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "artifacts/research"
SCHEMAS = ROOT / "contracts/research"
FILES = [
    "claim_evidence_graph.json",
    "counterevidence_register.json",
    "source_feasibility_registry.json",
    "canonical_field_map.json",
    "source_reproduction_report.json",
]

DIAGNOSTICS = {
    "metadata": "R001_METADATA_AS_ACCESS: metadata and schema reproduction cannot establish authorized immutable row acquisition or handling",
    "inference": "R001_INFERENCE_AS_FACT: CLM-004 lacks point-in-time fact-grade predictive evidence",
    "brand": "R001_BRAND_AS_LOCATION: brand, licence, legal entity, and physical establishment must remain distinct grains",
    "history": "R001_CURRENT_AS_HISTORICAL: current annual partitions do not prove contemporaneous historical availability",
    "authority": "R001_RETRIEVED_AS_AUTHORITY: retrieved public content cannot grant source, spending, handling, or live-use authority",
    "ontario": "R001_ON_MULTI_ADDRESS_COLLAPSE: ON-SELECT licence key cannot identify a location; observed multiplicity witness requires address-bearing identity",
    "toronto": "R001_TOR_SYS_ID_3209741_CONFLICT: TOR-COA SYS_ID 3209741 has materially non-equivalent cross-partition observations and requires resource-scoped retention plus adjudication",
    "licence": "R001_UNSPECIFIED_LICENCE: a source with unspecified terms cannot be marked Stage-1 ready",
}


def load_json(path: Path):
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def by_id(rows: list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


def validate_bundle(bundle: Path, validate_report: bool = True) -> list[str]:
    errors: list[str] = []
    docs: dict[str, object] = {}
    for filename in FILES:
        try:
            docs[filename] = load_json(bundle / filename)
            schema = load_json(SCHEMAS / filename.replace(".json", ".schema.json"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"R001_PARSE: {filename}: {exc}")
            continue
        validation_errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(docs[filename]),
            key=lambda e: (list(e.absolute_path), e.message),
        )
        errors.extend(f"R001_SCHEMA: {filename}:{e.json_path}: {e.message}" for e in validation_errors)
    if errors:
        return errors

    graph = docs["claim_evidence_graph.json"]
    registry = docs["source_feasibility_registry.json"]
    mapping = docs["canonical_field_map.json"]
    counter = docs["counterevidence_register.json"]
    reproduction = docs["source_reproduction_report.json"]

    keyed_collections = [
        (graph["research_questions"], "question_id", "research_questions"),
        (graph["claims"], "claim_id", "claims"),
        (registry["sources"], "source_id", "sources"),
        (mapping["maps"], "source_id", "maps"),
        (mapping["canonical_fields"], "field_id", "canonical_fields"),
        (counter["entries"], "counterevidence_id", "counterevidence"),
        (reproduction["probes"], "probe_id", "probes"),
        (reproduction["witnesses"], "witness_id", "witnesses"),
    ]
    for rows, key, label in keyed_collections:
        values = [row[key] for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"R001_DUPLICATE_ID: {label}")
    for source_map in mapping["maps"]:
        key_ids = [row["key_id"] for row in source_map["candidate_keys"]]
        if len(key_ids) != len(set(key_ids)):
            errors.append(f"R001_DUPLICATE_ID: {source_map['source_id']}.candidate_keys")

    authoritative_questions = load_json(ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/CORE_RESEARCH_QUESTIONS.json")["questions"]
    authoritative_claims = load_json(ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/CLAIM_PROOF_REGISTER.json")["claims"]
    questions = by_id(graph["research_questions"], "question_id")
    claims = by_id(graph["claims"], "claim_id")
    if set(questions) != {q["id"] for q in authoritative_questions}:
        errors.append("R001_RQ_COVERAGE: claim graph must contain exactly RQ-001..RQ-012")
    for q in authoritative_questions:
        actual = questions.get(q["id"], {})
        for field, source_field in (("question", "question"), ("information_class", "information_class"), ("decision_lane", "decision_lane")):
            if actual.get(field) != q[source_field]:
                errors.append(f"R001_RQ_AUTHORITY: {q['id']} {field} differs from CORE_RESEARCH_QUESTIONS")
    if set(claims) != {c["claim_id"] for c in authoritative_claims}:
        errors.append("R001_CLAIM_COVERAGE: claim graph must contain exactly CLM-001..CLM-007")
    for c in authoritative_claims:
        actual = claims.get(c["claim_id"], {})
        for field in ("claim", "required_proof_level", "minimum_evidence", "current_status"):
            if actual.get(field) != c[field]:
                errors.append(f"R001_CLAIM_AUTHORITY: {c['claim_id']} {field} differs from CLAIM_PROOF_REGISTER")

    sources = by_id(registry["sources"], "source_id")
    maps = by_id(mapping["maps"], "source_id")
    counters = by_id(counter["entries"], "counterevidence_id")
    probes = by_id(reproduction["probes"], "probe_id")
    witnesses = by_id(reproduction["witnesses"], "witness_id")
    known_gates = set(registry["external_gates"])
    control_gates = {gate["gate_id"] for gate in load_json(ROOT / "control/GATES.json")["gates"]}
    if not known_gates <= control_gates:
        errors.append(f"R001_UNREGISTERED_GATE: {sorted(known_gates - control_gates)}")
    ref_sets = {
        "source": set(sources), "probe": set(probes) | set(witnesses),
        "counterevidence": set(counters), "gate": known_gates,
        "experiment": {row["gate_or_experiment_id"] for row in graph["research_questions"] if row.get("disposition") == "experiment"} | {r["ref_id"] for c in graph["claims"] for r in c["evidence_refs"] if r["ref_type"] == "experiment"},
    }
    for row in [*graph["research_questions"], *graph["claims"]]:
        row_id = row.get("question_id", row.get("claim_id"))
        for evidence_ref in row["evidence_refs"]:
            if evidence_ref["ref_id"] not in ref_sets[evidence_ref["ref_type"]]:
                errors.append(f"R001_DANGLING_REF: {row_id} -> {evidence_ref['ref_type']}:{evidence_ref['ref_id']}")
        for counter_id in row["counterevidence_ids"]:
            if counter_id not in counters:
                errors.append(f"R001_DANGLING_COUNTEREVIDENCE: {row_id} -> {counter_id}")
        if row["classification"] == "fact" and row_id != "CLM-004" and not any(r["ref_type"] in {"source", "probe"} for r in row["evidence_refs"]):
            errors.append(f"R001_FACT_WITHOUT_PRIMARY_EVIDENCE: {row_id}")
        if row["classification"] == "unknown" and not any(r["ref_type"] == "gate" for r in row["evidence_refs"]):
            errors.append(f"R001_UNKNOWN_WITHOUT_GATE: {row_id}")
        if row["classification"] == "hypothesis" and not any(r["ref_type"] == "experiment" for r in row["evidence_refs"]):
            errors.append(f"R001_HYPOTHESIS_WITHOUT_EXPERIMENT: {row_id}")

    counter_ref_ids = set(probes) | set(witnesses) | known_gates
    try:
        counter_ref_ids |= {entry["evidence_id"] for entry in load_json(bundle / "raw/manifest.json")["evidence"]}
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    for entry in counter["entries"]:
        for evidence_id in entry["evidence_refs"]:
            if evidence_id not in counter_ref_ids:
                errors.append(f"R001_DANGLING_COUNTEREVIDENCE_REF: {entry['counterevidence_id']} -> {evidence_id}")

    if any(source["access"]["rows"] == "acquired_authorized" for source in sources.values()) and not any(probe["acquisition_level"] == "current_rows" and any(run["rows_acquired"] for run in probe["runs"]) for probe in probes.values()):
        errors.append(DIAGNOSTICS["metadata"])
    if any(source["terms"]["status"] != "verified" for source in sources.values()):
        errors.append(DIAGNOSTICS["licence"])
    clm4 = claims["CLM-004"]
    if clm4["classification"] == "fact" or clm4["disposition"] == "accept_bounded":
        errors.append(DIAGNOSTICS["inference"])

    on_map = maps["ON-SELECT"]
    on_keys = by_id(on_map["candidate_keys"], "key_id")
    location_components = on_keys.get("location", {}).get("components", [])
    if "normalized_address" not in location_components:
        errors.append(DIAGNOSTICS["ontario"])
    prohibited_brand = any(k["status"] == "prohibited" and "operating_name_raw" in k["components"] for k in on_map["candidate_keys"])
    if not prohibited_brand or any(k["grain"] == "physical_establishment" and k["status"] != "prohibited" for k in on_map["candidate_keys"]):
        errors.append(DIAGNOSTICS["brand"])

    if any(source["history_status"] not in {"current_only_not_replayable", "annual_labels_not_publication_history"} for source in sources.values()):
        errors.append(DIAGNOSTICS["history"])
    if any(source["terms"]["repository_authority_granted"] for source in sources.values()) or "approved_source_envelope" not in known_gates:
        errors.append(DIAGNOSTICS["authority"])

    tor_map = maps["TOR-COA"]
    conflict_text = tor_map["conflict_policy"].lower()
    observation = set(tor_map["observation_key"])
    if not {"resource_id", "snapshot_sha256", "sys_id_raw"} <= observation or "adjudication" not in conflict_text or "retain" not in conflict_text:
        errors.append(DIAGNOSTICS["toronto"])
    on_witness = witnesses.get("WITNESS-ON-LICENCE-MULTIPLICITY", {})
    if (on_witness.get("reported_total_rows"), on_witness.get("reported_distinct_licences"), on_witness.get("reported_distinct_addresses_for_witness_licence")) != (681, 375, 175) or on_witness.get("query_evidence_id") != "ON-LICENCE-4716137-DISTINCT-ADDRESS":
        errors.append("R001_ON_WITNESS_INVALID: Ontario multiplicity witness was removed or altered")
    tor_witness = witnesses.get("WITNESS-TOR-3209741", {})
    if set(tor_witness.get("resource_ids", [])) != {"9c97254e-5460-4799-896f-c7823413c81c", "b3876c3c-c706-442f-80f6-4ad3e12839c1"} or "materially non-equivalent" not in tor_witness.get("conflict_summary", ""):
        errors.append("R001_TOR_WITNESS_INVALID: Toronto 3209741 conflict witness was removed or altered")

    canonical_ids = {f["field_id"] for f in mapping["canonical_fields"]}
    for source_map in maps.values():
        mapped = source_map["field_mappings"]
        if len({(m["source_field"], m["source_type"]) for m in mapped}) != len(mapped):
            errors.append(f"R001_DUPLICATE_MAPPING: {source_map['source_id']}")
        for item in mapped:
            if item["canonical_field_id"] not in canonical_ids:
                errors.append(f"R001_UNKNOWN_CANONICAL_FIELD: {source_map['source_id']}:{item['source_field']}")
    expected_on = {(f["id"], f["type"]) for f in load_json(bundle / "raw/on_select_schema.json")["result"]["fields"]}
    expected_tor = set()
    for filename in ("tor_coa_active_schema.json", "tor_coa_closed_schema.json", "tor_coa_2016_schema.json", "tor_coa_2001_schema.json"):
        expected_tor |= {(f["id"], f["type"]) for f in load_json(bundle / f"raw/{filename}")["result"]["fields"]}
    for source_id, expected in (("ON-SELECT", expected_on), ("TOR-COA", expected_tor)):
        actual = {(m["source_field"], m["source_type"]) for m in maps[source_id]["field_mappings"]}
        if actual != expected:
            errors.append(f"R001_INCOMPLETE_FIELD_MAP: {source_id}")

    raw_manifest = load_json(bundle / "raw/manifest.json")
    raw_evidence = {entry["evidence_id"]: entry for entry in raw_manifest["evidence"]}
    for entry in raw_manifest["evidence"]:
        if entry.get("status") == "captured":
            path = bundle / Path(entry["path"]).relative_to("artifacts/research")
            if not path.is_file() or sha256(path) != entry["sha256"]:
                errors.append(f"R001_RAW_HASH_MISMATCH: {entry['evidence_id']}")
    independent_capture = load_json(bundle / "raw/independent/capture_manifest.json")
    for entry in independent_capture["captures"]:
        path = bundle.parent.parent / entry["path"] if bundle == DEFAULT_BUNDLE else bundle / Path(entry["path"]).relative_to("artifacts/research")
        if not path.is_file() or sha256(path) != entry["sha256"] or path.stat().st_size != entry["byte_length"]:
            errors.append(f"R001_INDEPENDENT_RAW_HASH_MISMATCH: {entry['evidence_id']}")
    row_capture = load_json(bundle / "raw/row_witness/capture_manifest.json")
    row_entries = {entry["evidence_id"]: entry for entry in row_capture["captures"]}
    for entry in row_entries.values():
        path = bundle.parent.parent / entry["path"] if bundle == DEFAULT_BUNDLE else bundle / Path(entry["path"]).relative_to("artifacts/research")
        if not path.is_file() or sha256(path) != entry["sha256"] or path.stat().st_size != entry["byte_length"]:
            errors.append(f"R001_ROW_WITNESS_HASH_MISMATCH: {entry['evidence_id']}")
    expected_row_totals = {"ON-TOTAL-LIMIT0": 681, "ON-DISTINCT-LICENCE-LIMIT0": 375, "ON-LICENCE-4716137-COUNT": 175, "ON-LICENCE-4716137-DISTINCT-ADDRESS": 175, "TOR-CLOSED-3209741": 1, "TOR-2016-3209741": 1}
    for evidence_id, expected_total in expected_row_totals.items():
        if row_entries.get(evidence_id, {}).get("http_status") != 200 or row_entries.get(evidence_id, {}).get("reported_total") != expected_total:
            errors.append(f"R001_ROW_WITNESS_VALUE: {evidence_id}")
    for source in sources.values():
        terms_evidence = raw_evidence.get(source["terms"]["evidence_ref"])
        if not terms_evidence or terms_evidence.get("status") != "captured":
            errors.append(f"R001_TERMS_PROVENANCE: {source['source_id']}")
        elif terms_evidence["retrieved_at"] != source["terms"]["observed_at"]:
            errors.append(f"R001_TERMS_CLOCK_MISMATCH: {source['source_id']}")
    for probe in probes.values():
        roles = {run["role"] for run in probe["runs"] if run["success"]}
        if roles != {"builder", "independent_reviewer"}:
            errors.append(f"R001_REPRODUCTION_ROLES: {probe['probe_id']}")
        modes = {run["review_mode"] for run in probe["runs"] if run["success"]}
        if modes != {"canonicalized_semantic_review", "exact_http_capture"}:
            errors.append(f"R001_REPRODUCTION_MODES: {probe['probe_id']}")
        captured = next((entry for entry in raw_manifest["evidence"] if entry.get("url") == probe["request"]["url"] and entry.get("status") == "captured"), None)
        independent = next((entry for entry in independent_capture["captures"] if entry["evidence_id"] == next((raw["evidence_id"] for raw in raw_manifest["evidence"] if raw.get("url") == probe["request"]["url"]), None)), None)
        builder_run = next((run for run in probe["runs"] if run["role"] == "builder"), None)
        reviewer_run = next((run for run in probe["runs"] if run["role"] == "independent_reviewer"), None)
        if not captured or not independent or not builder_run or not reviewer_run or builder_run["response_sha256"] != captured["sha256"] or reviewer_run["response_sha256"] != independent["sha256"]:
            errors.append(f"R001_REPRODUCTION_HASH: {probe['probe_id']}")
        if any(run["rows_acquired"] for run in probe["runs"]) and probe["acquisition_level"] != "current_rows":
            errors.append(f"R001_ROW_ACQUISITION_MISMATCH: {probe['probe_id']}")
        if probe["observations"]["history_proven"]:
            errors.append(DIAGNOSTICS["history"])
        if probe["observations"]["authority_granted"]:
            errors.append(DIAGNOSTICS["authority"])

    bundle_manifest = load_json(bundle / "bundle_manifest.json")
    for item in bundle_manifest.get("files", []):
        relative = Path(item["path"])
        if relative.parts[:2] == ("artifacts", "research"):
            path = bundle / Path(*relative.parts[2:])
        else:
            path = ROOT / relative
        if not path.is_file() or sha256(path) != item["sha256"]:
            errors.append(f"R001_BUNDLE_HASH_MISMATCH: {item['path']}")
    if validate_report:
        try:
            completion = load_json(bundle / "research_completion_report.json")
            if set(completion.get("open_gates", [])) != known_gates:
                errors.append("R001_COMPLETION_GATE_MISMATCH: completion report gates differ from source registry")
            if completion.get("result") != ("PASS" if not errors else "FAIL"):
                errors.append("R001_COMPLETION_RESULT_MISMATCH: stored result differs from computed validation")
            unresolved = " ".join(completion.get("unresolved_evidence", [])).lower()
            if "narrow" not in unresolved or "operational" not in unresolved:
                errors.append("R001_COMPLETION_SCOPE_MISMATCH: completion report must distinguish narrow evidence from operational acquisition")
        except (OSError, json.JSONDecodeError):
            errors.append("R001_COMPLETION_REPORT_MISSING: completion report is required")

    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate_bundle(args.bundle.resolve())
    if args.json:
        print(json.dumps({"result": "PASS" if not errors else "FAIL", "diagnostics": errors}, sort_keys=True))
    else:
        print("PASS" if not errors else "FAIL")
        for error in errors:
            print(error)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
