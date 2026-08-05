"""Material synthetic temporal identity graph: renderer and semantic checks.

Two implementations must agree on the same canonical document: this material
graph and the frozen independent evaluator.  This module constructs the subject
from a compact declarative seed and independently binds every digest, the
protection snapshot, the lineage/journal chain, and the subject receipt using
the documented ``UTF8_CANONICAL_JSON_SORTED_KEYS`` conventions.  It also
implements the semantic primitives the IDENTITY-001 task requires (temporal
identity, alternative-link resolution, relocation, closure, unit separation,
franchise grain, fail-closed protected-account coverage, distinct entity
grains) as standalone checks that emit the frozen registered diagnostic codes.

This module must never import ``evals.public.temporal_identity_evaluator`` and
never import ``cre_foundry`` identity-adjacent packages.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "artifacts/identity/public_evaluator_contract.json"
SCHEMA_PATH = ROOT / "contracts/temporal_identity.schema.json"
EVALUATOR_PATH = ROOT / "evals/public/temporal_identity_evaluator.py"

DOCUMENT_KIND = "TEMPORAL_IDENTITY_SYNTHETIC_SUBJECT"
SCHEMA_VERSION = "1.0.0"
EXECUTION_SCOPE = "SYNTHETIC_NON_INFLUENCING"
CANONICAL_SERIALIZATION = "UTF8_CANONICAL_JSON_SORTED_KEYS"
MATERIAL_BUILDER_IDENTITY = "identity-material-graph-v1"

# Registered diagnostic vocabulary (shared frozen contract strings).
IDENTITY_GRAIN_COLLAPSE = "IDENTITY-GRAIN-COLLAPSE"
IDENTITY_ADDRESS_AS_IDENTITY = "IDENTITY-ADDRESS-AS-IDENTITY"
IDENTITY_ADDRESS_REUSE_LINKED = "IDENTITY-ADDRESS-REUSE-LINKED"
IDENTITY_RELOCATION_REWRITE = "IDENTITY-RELOCATION-REWRITE"
IDENTITY_CLOSURE_TEMPORAL = "IDENTITY-CLOSURE-TEMPORAL"
IDENTITY_UNIT_SEPARATION = "IDENTITY-UNIT-SEPARATION"
IDENTITY_MULTI_UNIT_ESTABLISHMENT = "IDENTITY-MULTI-UNIT-ESTABLISHMENT"
IDENTITY_MULTI_ESTABLISHMENT_PROPERTY = "IDENTITY-MULTI-ESTABLISHMENT-PROPERTY"
IDENTITY_FRANCHISE_GRAIN = "IDENTITY-FRANCHISE-GRAIN"
IDENTITY_PARENT_NOT_LOCATION = "IDENTITY-PARENT-NOT-LOCATION"
IDENTITY_CORPORATE_TEMPORAL = "IDENTITY-CORPORATE-TEMPORAL"
IDENTITY_ALIAS_SUPERSEDE = "IDENTITY-ALIAS-SUPERSEDE"
IDENTITY_AMBIGUITY_BLOCKED = "IDENTITY-AMBIGUITY-BLOCKED"
IDENTITY_CONFLICT_BLOCKED = "IDENTITY-CONFLICT-BLOCKED"
IDENTITY_DUPLICATE_ACTIVE_TRUTH = "IDENTITY-DUPLICATE-ACTIVE-TRUTH"
REGISTERED_SUITE_COLLAPSE = "registered mutation detected: suite-collapse"
REGISTERED_PROTECTED_ALIAS_CLEAR = "registered mutation detected: protected-alias-clear"

GRAIN_TYPES = frozenset({
    "LEGAL_ENTITY", "PARENT", "SUBSIDIARY", "OPERATING_BUSINESS", "BRAND",
    "FRANCHISE_SYSTEM", "FRANCHISEE", "ESTABLISHMENT", "PHYSICAL_LOCATION",
    "ADDRESS", "BUILDING", "UNIT", "PARCEL", "PROPERTY", "PROPERTY_OWNER",
    "OCCUPIER", "PROTECTED_ACCOUNT", "REPRESENTATIVE_RELATIONSHIP",
})

IDENTITY_LINK_TYPES = frozenset({
    "OWNS", "OPERATES", "BRAND_OF", "SUBSIDIARY_OF", "PARENT_OF",
    "FRANCHISE_SYSTEM_OF", "FRANCHISEE_OF", "PREDECESSOR_OF", "SUCCESSOR_OF",
    "ALIAS_OF",
})

LOCATION_GRAIN_TYPES = frozenset({
    "PHYSICAL_LOCATION", "ADDRESS", "BUILDING", "UNIT", "PARCEL", "PROPERTY",
})

DUPLICATE_TRUTH_EXCLUDED = frozenset({"UNIT", "ESTABLISHMENT"})

RECORD_DIGEST_FIELD = {
    "grains": "grain_digest",
    "temporal_assertions": "assertion_digest",
    "links": "link_digest",
    "alternatives": "rank_digest",
    "corrections": "correction_digest",
}

ALL_CLAIM_NOT_ESTABLISHED = [
    "real-entity-resolution-accuracy",
    "real-precision-recall",
    "real-protected-account-completeness",
    "measured-zero-false-clears-on-production",
    "representative-usability",
    "production-readiness",
    "deployment-readiness",
    "field-effectiveness",
    "commercial-lift",
    "sealed-evaluator-independence",
    "hidden-holdout-performance",
]


# ---------------------------------------------------------------------------
# Canonical serialization (frozen contract conventions)
# ---------------------------------------------------------------------------

def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ts(value: Any) -> datetime:
    raw = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError(f"naive clock without explicit offset: {value}")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _shift(ts: str, days: int) -> str:
    base = _ts(ts)
    shifted = (base + timedelta(days=days)).replace(tzinfo=timezone.utc)
    return shifted.isoformat(timespec="seconds").replace("+00:00", "Z")


def _evidence(ref: str, etype: str = "OBSERVATION") -> dict[str, Any]:
    return {
        "evidence_ref": ref,
        "evidence_type": etype,
        "evidence_sha256": digest_json({"evidence_ref": ref, "evidence_type": etype}),
    }


def _record_digest(record: dict[str, Any], digest_field: str) -> str:
    body = {key: value for key, value in record.items() if key != digest_field}
    return digest_json(body)


def _subject_digest(subject: dict[str, Any]) -> str:
    body = json.loads(json.dumps(subject))
    body.pop("subject_sha256", None)
    receipt = body.get("replay_receipt")
    if isinstance(receipt, dict):
        receipt.pop("subject_sha256", None)
    return digest_json(body)


# ---------------------------------------------------------------------------
# Declarative canonical seed (public IDENTITY-001 fixture facts)
# ---------------------------------------------------------------------------

_OBSERVED = "2024-05-01T00:00:00Z"
_VALID_FROM = _shift(_OBSERVED, -1)
_CUTOFF = "2024-06-01T00:00:00Z"

GRAIN_CATALOG: list[tuple[str, str]] = [
    ("LEGAL_ENTITY:legal-1", "LEGAL_ENTITY"),
    ("PARENT:parent-1", "PARENT"),
    ("SUBSIDIARY:sub-1", "SUBSIDIARY"),
    ("OPERATING_BUSINESS:biz-1", "OPERATING_BUSINESS"),
    ("BRAND:brand-1", "BRAND"),
    ("FRANCHISE_SYSTEM:fsys-1", "FRANCHISE_SYSTEM"),
    ("FRANCHISEE:franchisee-1", "FRANCHISEE"),
    ("ESTABLISHMENT:est-1", "ESTABLISHMENT"),
    ("ESTABLISHMENT:est-2", "ESTABLISHMENT"),
    ("PHYSICAL_LOCATION:pl-1", "PHYSICAL_LOCATION"),
    ("ADDRESS:addr-1", "ADDRESS"),
    ("BUILDING:bldg-1", "BUILDING"),
    ("UNIT:u-101", "UNIT"),
    ("UNIT:u-102", "UNIT"),
    ("PARCEL:parcel-1", "PARCEL"),
    ("PROPERTY:prop-1", "PROPERTY"),
    ("PROPERTY_OWNER:owner-1", "PROPERTY_OWNER"),
    ("OCCUPIER:occ-1", "OCCUPIER"),
    ("PROTECTED_ACCOUNT:pa-1", "PROTECTED_ACCOUNT"),
    ("PROTECTED_ACCOUNT:pa-2", "PROTECTED_ACCOUNT"),
    ("REPRESENTATIVE_RELATIONSHIP:rep-1", "REPRESENTATIVE_RELATIONSHIP"),
]

ASSERTION_CATALOG: list[tuple[str, str, str]] = [
    ("ASSERT:obs-1", "ESTABLISHMENT:est-1", "OBSERVED"),
    ("ASSERT:obs-2", "ESTABLISHMENT:est-2", "OBSERVED"),
]

LINK_CATALOG: list[tuple[str, str, str, str]] = [
    ("LINK:own-biz-brand", "OWNS", "OPERATING_BUSINESS:biz-1", "BRAND:brand-1"),
    ("LINK:sub-legal", "SUBSIDIARY_OF", "SUBSIDIARY:sub-1", "LEGAL_ENTITY:legal-1"),
    ("LINK:parent-of", "PARENT_OF", "PARENT:parent-1", "SUBSIDIARY:sub-1"),
    ("LINK:brand-sys", "BRAND_OF", "BRAND:brand-1", "FRANCHISE_SYSTEM:fsys-1"),
    ("LINK:franchisee-sys", "FRANCHISEE_OF", "FRANCHISEE:franchisee-1", "FRANCHISE_SYSTEM:fsys-1"),
    ("LINK:est-op-1", "OPERATES", "OPERATING_BUSINESS:biz-1", "ESTABLISHMENT:est-1"),
    ("LINK:est-op-2", "OPERATES", "OPERATING_BUSINESS:biz-1", "ESTABLISHMENT:est-2"),
    ("LINK:est-loc-1", "LOCATED_AT", "ESTABLISHMENT:est-1", "UNIT:u-101"),
    ("LINK:est-loc-2", "LOCATED_AT", "ESTABLISHMENT:est-2", "UNIT:u-102"),
    ("LINK:u-pl-1", "PART_OF", "UNIT:u-101", "PHYSICAL_LOCATION:pl-1"),
    ("LINK:u-pl-2", "PART_OF", "UNIT:u-102", "PHYSICAL_LOCATION:pl-1"),
    ("LINK:pl-addr", "LOCATED_AT", "PHYSICAL_LOCATION:pl-1", "ADDRESS:addr-1"),
    ("LINK:addr-bldg", "PART_OF", "ADDRESS:addr-1", "BUILDING:bldg-1"),
    ("LINK:bldg-prop", "PART_OF", "BUILDING:bldg-1", "PROPERTY:prop-1"),
    ("LINK:prop-parcel", "PART_OF", "PROPERTY:prop-1", "PARCEL:parcel-1"),
    ("LINK:owner-prop", "OWNS", "PROPERTY_OWNER:owner-1", "PROPERTY:prop-1"),
    ("LINK:occ-unit", "OCCUPIES", "OCCUPIER:occ-1", "UNIT:u-101"),
    ("LINK:alias-pa", "ALIAS_OF", "PROTECTED_ACCOUNT:pa-1", "PROTECTED_ACCOUNT:pa-2"),
    ("LINK:prot-pl", "PROTECTED_LINK", "PROTECTED_ACCOUNT:pa-1", "PHYSICAL_LOCATION:pl-1"),
    ("LINK:prot-est", "PROTECTED_LINK", "PROTECTED_ACCOUNT:pa-1", "ESTABLISHMENT:est-1"),
]

EXPANSION_CATALOG: list[tuple[str, int, str, str, str, str]] = [
    ("EXPATH:pa-1-est-1", 1, "PROTECTED_ACCOUNT:pa-1", "ESTABLISHMENT:est-1", "PROTECTED_LINK", "est-1"),
    ("EXPATH:pa-1-pa-2", 1, "PROTECTED_ACCOUNT:pa-1", "PROTECTED_ACCOUNT:pa-2", "ALIAS_OF", "pa-2"),
    ("EXPATH:pa-1-pl-1", 1, "PROTECTED_ACCOUNT:pa-1", "PHYSICAL_LOCATION:pl-1", "PROTECTED_LINK", "pl-1"),
]


def _bundle_seed() -> dict[str, Any]:
    return {
        "bundle_id": "BUNDLE:b-1",
        "bundle_version": "1.0.0",
        "bundle_completeness": "COMPLETE",
        "token_extraction_completeness": "COMPLETE",
        "authoritative_status": "AUTHORITATIVE",
        "valid_from": _OBSERVED,
        "valid_to": None,
        "refreshed_at": "2024-05-31T00:00:00Z",
        "expansion_policy_id": "POLICY-IDENTITY-EXPAND-V1",
        "expansion_policy_version": "1.0.0",
        "maximum_relationship_depth": 1,
        "root_protected_identities": ["PROTECTED_ACCOUNT:pa-1"],
        "aliases": ["PROTECTED_ACCOUNT:pa-2"],
        "related_entities": ["ESTABLISHMENT:est-1"],
        "former_addresses": [],
        "linked_locations": ["PHYSICAL_LOCATION:pl-1"],
        "expansion_paths": [path[0] for path in EXPANSION_CATALOG],
        "evaluated_at": _CUTOFF,
    }


# ---------------------------------------------------------------------------
# Record builders (material conventions; independent of the evaluator)
# ---------------------------------------------------------------------------

def _build_grain(gid: str, gtype: str) -> dict[str, Any]:
    return {
        "grain_id": gid,
        "grain_type": gtype,
        "observed_at": _OBSERVED,
        "published_at": _OBSERVED,
        "retrieved_at": _OBSERVED,
        "source_snapshot_time": _OBSERVED,
        "available_at": _OBSERVED,
        "effective_from": _OBSERVED,
        "effective_to": None,
        "valid_from": _VALID_FROM,
        "valid_to": None,
        "superseded_at": None,
        "correction_at": None,
        "grain_status": "ACTIVE",
        "evidence_refs": [_evidence("OBS:" + gid)],
    }


def _build_assertion(aid: str, subject_gid: str, a_type: str) -> dict[str, Any]:
    return {
        "assertion_id": aid,
        "subject_grain_id": subject_gid,
        "assertion_type": a_type,
        "observed_at": _OBSERVED,
        "published_at": _OBSERVED,
        "retrieved_at": _OBSERVED,
        "source_snapshot_time": _OBSERVED,
        "available_at": _OBSERVED,
        "effective_from": _OBSERVED,
        "effective_to": None,
        "valid_from": _VALID_FROM,
        "valid_to": None,
        "decision_cutoff": _CUTOFF,
        "superseded_at": None,
        "correction_at": None,
        "evidence_refs": [_evidence("OBS:" + aid)],
    }


def _build_link(lid: str, ltype: str, from_gid: str, to_gid: str) -> dict[str, Any]:
    return {
        "link_id": lid,
        "link_type": ltype,
        "from_grain_id": from_gid,
        "to_grain_id": to_gid,
        "effective_from": _OBSERVED,
        "effective_to": None,
        "valid_from": _VALID_FROM,
        "valid_to": None,
        "observed_at": _OBSERVED,
        "published_at": _OBSERVED,
        "retrieved_at": _OBSERVED,
        "source_snapshot_time": _OBSERVED,
        "available_at": _OBSERVED,
        "superseded_at": None,
        "evidence_refs": [_evidence("OBS:" + lid)],
        "support_state": "SUPPORTED",
    }


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def _build_subject_undigested() -> dict[str, Any]:
    return {
        "document_kind": DOCUMENT_KIND,
        "schema_version": SCHEMA_VERSION,
        "schema_sha256": digest_bytes(SCHEMA_PATH.read_bytes()),
        "contract_sha256": digest_bytes(CONTRACT_PATH.read_bytes()),
        "execution_scope": EXECUTION_SCOPE,
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "subject_id": "subject-identity-001",
        "subject_sha256": "0" * 64,
        "metadata": {
            "subject_label": "synthetic temporal identity subject v1",
            "created_at": _CUTOFF,
            "builder_identity": MATERIAL_BUILDER_IDENTITY,
            "determinism_note": "deterministic material graph render; independent reconstruction must agree",
        },
        "route_day_decision_context": {
            "decision_cutoff": _CUTOFF,
            "stage1_frozen_at": "2024-05-30T00:00:00Z",
            "route_day": "2024-06-01",
            "generation": 0,
            "exact_ten_or_abstain_context": "synthetic route-day decision at proof level 4",
        },
        "grains": [_build_grain(gid, gtype) for gid, gtype in GRAIN_CATALOG],
        "temporal_assertions": [_build_assertion(aid, sgid, atype) for aid, sgid, atype in ASSERTION_CATALOG],
        "links": [_build_link(lid, ltype, from_gid, to_gid) for lid, ltype, from_gid, to_gid in LINK_CATALOG],
        "alternatives": [],
        "corrections": [],
        "protection_bundle_projection": _bundle_seed(),
        "protection_expansion": [
            {
                "path_id": path_id,
                "depth": depth,
                "from_grain_id": from_gid,
                "to_grain_id": to_gid,
                "relationship_type": rel_type,
                "evidence_refs": [_evidence("OBS:" + local)],
            }
            for path_id, depth, from_gid, to_gid, rel_type, local in EXPANSION_CATALOG
        ],
        "protection_decision": {
            "decision_id": "PROT:dec-1",
            "evaluated_at": _CUTOFF,
            "bundle_id": "BUNDLE:b-1",
            "candidate_snapshot_digest": "0" * 64,
            "matched_tokens": [],
            "matched_identities": [],
            "result_state": "CLEAR",
            "evidence_refs": [_evidence("BUNDLE:b-1", "PROTECTION_BUNDLE")],
            "manual_review_required": False,
            "manual_review_can_clear": False,
            "protection_decision_digest": "0" * 64,
        },
        "lineage": {
            "lineage_id": "LINEAGE:identity-001",
            "nodes": [],
            "edges": [],
            "journal": [],
        },
        "replay_receipt": {
            "receipt_id": "RECEIPT:r-1",
            "contract_sha256": digest_bytes(CONTRACT_PATH.read_bytes()),
            "schema_sha256": digest_bytes(SCHEMA_PATH.read_bytes()),
            "subject_sha256": "0" * 64,
            "evaluator_sha256": digest_bytes(EVALUATOR_PATH.read_bytes()),
            "canonical_serialization": CANONICAL_SERIALIZATION,
            "regenerated_at": _CUTOFF,
        },
        "claims_and_limitations": {
            "claim_kind": EXECUTION_SCOPE,
            "proof_level": 4,
            "claims_not_established": list(ALL_CLAIM_NOT_ESTABLISHED),
            "live_permissions": False,
            "external_effect_occurred": False,
        },
    }


def _lookup_record_digest(subject: dict[str, Any], record_id: Any) -> str | None:
    if not isinstance(record_id, str):
        return None
    for array_name, digest_field in RECORD_DIGEST_FIELD.items():
        for record in subject.get(array_name, []):
            rid = record.get(
                "grain_id", record.get("assertion_id", record.get(
                    "link_id", record.get("alternative_id", record.get("correction_id"))))
            )
            if rid == record_id:
                return _record_digest(record, digest_field)
    return None


def _rebuild_record_digests(subject: dict[str, Any], preserve_predecessors: bool = False) -> None:
    for array_name, digest_field in RECORD_DIGEST_FIELD.items():
        for record in subject.get(array_name, []):
            record[digest_field] = _record_digest(record, digest_field)
    if not preserve_predecessors:
        for correction in subject.get("corrections", []):
            superseded_id = correction.get("superseded_record_id")
            predecessor = _lookup_record_digest(subject, superseded_id)
            if predecessor is not None:
                correction["predecessor_digest"] = predecessor
            replacement = _lookup_record_digest(subject, correction.get("corrected_grain_id"))
            if replacement is not None:
                correction["replacement_digest"] = replacement
    for path in subject.get("protection_expansion", []):
        path["path_digest"] = _record_digest(path, "path_digest")


def _rebuild_protection_digests(subject: dict[str, Any]) -> None:
    expansion = subject.get("protection_expansion", [])
    snapshot_digest = digest_json(expansion)
    bundle = subject.get("protection_bundle_projection")
    decision = subject.get("protection_decision")
    if isinstance(bundle, dict):
        bundle["candidate_snapshot_digest"] = snapshot_digest
        bundle["bundle_sha256"] = _record_digest(bundle, "bundle_sha256")
    if isinstance(decision, dict):
        decision["candidate_snapshot_digest"] = snapshot_digest
        decision["protection_decision_digest"] = _record_digest(decision, "protection_decision_digest")


def _rebuild_lineage(subject: dict[str, Any]) -> None:
    nodes: list[dict[str, Any]] = []
    order: list[tuple[str, str]] = []

    def add_node(nid: str, record_type: str, record_id: str, node_digest: str) -> None:
        nodes.append({
            "node_id": nid,
            "record_type": record_type,
            "record_id": record_id,
            "node_digest": node_digest,
        })
        order.append((nid, record_id))

    for index, record in enumerate(subject.get("grains", [])):
        add_node(f"NODE:g-{index}", "OBSERVATION", record["grain_id"], _record_digest(record, "grain_digest"))
    for index, record in enumerate(subject.get("temporal_assertions", [])):
        add_node(f"NODE:a-{index}", "ASSERTION", record["assertion_id"], _record_digest(record, "assertion_digest"))
    for index, record in enumerate(subject.get("links", [])):
        add_node(f"NODE:l-{index}", "LINK", record["link_id"], _record_digest(record, "link_digest"))
    for index, record in enumerate(subject.get("alternatives", [])):
        add_node(f"NODE:alt-{index}", "ALTERNATIVE", record["alternative_id"], _record_digest(record, "rank_digest"))
    for index, record in enumerate(subject.get("corrections", [])):
        add_node(f"NODE:c-{index}", "CORRECTION", record["correction_id"], _record_digest(record, "correction_digest"))

    bundle = subject.get("protection_bundle_projection")
    decision = subject.get("protection_decision")
    if isinstance(bundle, dict):
        add_node("NODE:bundle", "PROTECTION_BUNDLE", bundle["bundle_id"], _record_digest(bundle, "bundle_sha256"))
    if isinstance(decision, dict):
        add_node("NODE:decision", "PROTECTION_DECISION", decision["decision_id"], _record_digest(decision, "protection_decision_digest"))

    edges: list[dict[str, Any]] = []
    node_by_record = {node["record_id"]: node["node_id"] for node in nodes}
    node_ids = {node["node_id"] for node in nodes}
    edge_index = 0
    for assertion in subject.get("temporal_assertions", []):
        subject_node = node_by_record.get(assertion.get("subject_grain_id"))
        assertion_node = node_by_record.get(assertion.get("assertion_id"))
        if subject_node and assertion_node:
            edges.append({
                "edge_id": f"EDGE:e-{edge_index}",
                "from_node_id": assertion_node,
                "to_node_id": subject_node,
                "edge_type": "SUPPORTS",
            })
            edge_index += 1
    if "NODE:decision" in node_ids and "NODE:bundle" in node_ids:
        edges.append({
            "edge_id": f"EDGE:e-{edge_index}",
            "from_node_id": "NODE:decision",
            "to_node_id": "NODE:bundle",
            "edge_type": "DERIVES",
        })
        edge_index += 1
    if isinstance(bundle, dict):
        for protected_root in bundle.get("root_protected_identities", []):
            root_node = node_by_record.get(protected_root)
            if root_node and "NODE:bundle" in node_ids:
                edges.append({
                    "edge_id": f"EDGE:e-{edge_index}",
                    "from_node_id": "NODE:bundle",
                    "to_node_id": root_node,
                    "edge_type": "EVIDENCES",
                })
                edge_index += 1

    journal: list[dict[str, Any]] = []
    predecessor = digest_json({"genesis": True})
    for index, (node_id, record_id) in enumerate(order):
        entry = {
            "entry_id": f"JRNL:j-{index}",
            "journal_index": index,
            "record_id": record_id,
            "predecessor_digest": predecessor,
            "recorded_at": _CUTOFF,
        }
        predecessor = digest_json(entry)
        journal.append(entry)

    subject["lineage"] = {
        "lineage_id": "LINEAGE:identity-001",
        "nodes": nodes,
        "edges": edges,
        "journal": journal,
    }


def render_subject() -> dict[str, Any]:
    """Render the canonical material subject from the declarative seed."""
    subject = _build_subject_undigested()
    _rebuild_record_digests(subject)
    _rebuild_protection_digests(subject)
    _rebuild_lineage(subject)
    digest = _subject_digest(subject)
    subject["subject_sha256"] = digest
    subject["replay_receipt"]["subject_sha256"] = digest
    return subject


def rebind_digests(subject: dict[str, Any], preserve_predecessors: bool = False) -> dict[str, Any]:
    """Recompute every digest, protection snapshot, lineage, and binding.

    Material construction helper for mutated subjects so only the intended
    semantic diagnostic fires.  Never weakens the independent evaluator, which
    recomputes the same conventions on its own.
    """
    _rebuild_record_digests(subject, preserve_predecessors=preserve_predecessors)
    _rebuild_protection_digests(subject)
    _rebuild_lineage(subject)
    digest = _subject_digest(subject)
    subject["subject_sha256"] = digest
    subject["replay_receipt"]["subject_sha256"] = digest
    return subject


def subject_canonical_digest(subject: dict[str, Any]) -> str:
    """Canonical subject digest using the frozen contract's serialization."""
    return _subject_digest(subject)


# ---------------------------------------------------------------------------
# Independent semantic checks (material primitives)
# ---------------------------------------------------------------------------

def _cutoff(subject: dict[str, Any]) -> str:
    context = subject.get("route_day_decision_context")
    if isinstance(context, dict) and isinstance(context.get("decision_cutoff"), str):
        return context["decision_cutoff"]
    return "9999-12-31T00:00:00Z"


def _interval_contains(effective_from: str, effective_to: str | None, when: str) -> bool:
    if _ts(when) < _ts(effective_from):
        return False
    if effective_to is not None and _ts(when) > _ts(effective_to):
        return False
    return True


def _intervals_overlap(a1: str, b1: str | None, a2: str, b2: str | None) -> bool:
    s1, e1 = _ts(a1), _ts(b1) if b1 else None
    s2, e2 = _ts(a2), _ts(b2) if b2 else None
    if e2 is not None and not (s1 < e2):
        return False
    if e1 is not None and not (s2 < e1):
        return False
    return True


def _grain_type_of(gid: Any) -> str:
    if not isinstance(gid, str):
        return ""
    return gid.split(":", 1)[0]


def _active_links(subject: dict[str, Any]) -> list[dict[str, Any]]:
    cutoff = _cutoff(subject)
    return [
        record
        for record in subject.get("links", [])
        if isinstance(record.get("effective_from"), str)
        and _interval_contains(record["effective_from"], record.get("effective_to"), cutoff)
    ]


def _grain_status_by_id(subject: dict[str, Any]) -> dict[str, str]:
    by_id: dict[str, str] = {}
    for record in subject.get("grains", []):
        by_id[record.get("grain_id")] = record.get("grain_type", "")
    return by_id


def check_suite_collapse(subject: dict[str, Any]) -> bool:
    occupant_types = {"ESTABLISHMENT", "OPERATING_BUSINESS"}
    location_links = {"LOCATED_AT", "OCCUPIES"}
    for unit in subject.get("grains", []):
        if unit.get("grain_type") != "UNIT":
            continue
        occupants = []
        for link in _active_links(subject):
            if link.get("link_type") in location_links and link.get("to_grain_id") == unit.get("grain_id"):
                from_grain = link.get("from_grain_id")
                if isinstance(from_grain, str) and _grain_type_of(from_grain) in occupant_types:
                    occupants.append(link)
        if len(occupants) < 2:
            continue
        for i in range(len(occupants)):
            for j in range(i + 1, len(occupants)):
                a, b = occupants[i], occupants[j]
                if _intervals_overlap(a["effective_from"], a.get("effective_to"), b["effective_from"], b.get("effective_to")):
                    return True
    return False


def check_protected_alias_clear(subject: dict[str, Any]) -> bool:
    decision = subject.get("protection_decision")
    bundle = subject.get("protection_bundle_projection")
    if not isinstance(decision, dict) or not isinstance(bundle, dict):
        return False
    if decision.get("result_state") != "CLEAR":
        return False
    protected_grains = {
        record.get("grain_id")
        for record in subject.get("grains", [])
        if record.get("grain_type") == "PROTECTED_ACCOUNT"
    }
    root_ids = {identity for identity in bundle.get("root_protected_identities", [])}
    required_aliases: set[str] = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "ALIAS_OF":
            from_gid, to_gid = link.get("from_grain_id"), link.get("to_grain_id")
            if from_gid in protected_grains and to_gid in protected_grains:
                required_aliases.add(from_gid)
                required_aliases.add(to_gid)
    required_linked_locations: set[str] = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "PROTECTED_LINK":
            to_gid = link.get("to_grain_id")
            if isinstance(to_gid, str) and _grain_type_of(to_gid) in LOCATION_GRAIN_TYPES:
                required_linked_locations.add(to_gid)
    expansion_endpoints: set[str] = set()
    for path in subject.get("protection_expansion", []):
        expansion_endpoints.add(path.get("from_grain_id"))
        expansion_endpoints.add(path.get("to_grain_id"))
    covered = (
        set(bundle.get("aliases", []))
        | set(bundle.get("linked_locations", []))
        | set(bundle.get("former_addresses", []))
        | root_ids
        | expansion_endpoints
    )
    missing_aliases = {alias for alias in required_aliases if alias not in covered and alias not in root_ids}
    missing_locations = {loc for loc in required_linked_locations if loc not in covered}
    return bool(missing_aliases or missing_locations)


def check_grain_collapse(subject: dict[str, Any]) -> bool:
    seen: dict[str, str] = {}
    grain_ids = {record.get("grain_id") for record in subject.get("grains", []) if isinstance(record, dict)}
    for record in subject.get("grains", []):
        gid = record.get("grain_id")
        gtype = record.get("grain_type")
        if not isinstance(gid, str) or not isinstance(gtype, str):
            continue
        if gid.split(":", 1)[0] != gtype:
            return True
        if gid in seen and seen[gid] != gtype:
            return True
        seen.setdefault(gid, gtype)
    for record in subject.get("links", []):
        for endpoint in ("from_grain_id", "to_grain_id"):
            value = record.get(endpoint)
            if isinstance(value, str) and value not in grain_ids:
                return True
    return False


def check_address_as_identity(subject: dict[str, Any]) -> bool:
    for record in subject.get("links", []):
        if record.get("link_type") not in IDENTITY_LINK_TYPES:
            continue
        from_gid = record.get("from_grain_id")
        if isinstance(from_gid, str) and _grain_type_of(from_gid) in LOCATION_GRAIN_TYPES:
            return True
    return False


def check_relocation_rewrite(subject: dict[str, Any]) -> bool:
    relocated: dict[str, int] = {}
    for assertion in subject.get("temporal_assertions", []):
        if assertion.get("assertion_type") == "RELOCATED":
            subject_gid = assertion.get("subject_grain_id")
            relocated[subject_gid] = relocated.get(subject_gid, 0) + 1
    for business, relocations in relocated.items():
        location_links = [
            link for link in subject.get("links", [])
            if link.get("from_grain_id") == business and link.get("link_type") == "LOCATED_AT"
        ]
        location_links.sort(key=lambda link: _ts(link["effective_from"]))
        if len(location_links) != relocations + 1:
            return True
        for i in range(len(location_links) - 1):
            current = location_links[i]
            following = location_links[i + 1]
            if current.get("effective_to") is None or _ts(current["effective_to"]) > _ts(following["effective_from"]):
                return True
    return False


def check_closure_temporal(subject: dict[str, Any]) -> bool:
    permanently_closed: set[str] = set()
    for assertion in subject.get("temporal_assertions", []):
        a_type = assertion.get("assertion_type")
        if a_type == "CLOSED_PERMANENT" and assertion.get("effective_to") is not None:
            return True
        if a_type == "CLOSED_TEMPORARY" and assertion.get("effective_to") is None:
            return True
        if a_type == "CLOSED_PERMANENT":
            permanently_closed.add(assertion.get("subject_grain_id", ""))
    for link in _active_links(subject):
        if link.get("from_grain_id") in permanently_closed:
            return True
    return False


def check_alias_supersede(subject: dict[str, Any]) -> bool:
    alias_endpoints: set[str] = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "ALIAS_OF":
            alias_endpoints.add(link.get("from_grain_id"))
            alias_endpoints.add(link.get("to_grain_id"))
    for assertion in subject.get("temporal_assertions", []):
        if assertion.get("assertion_type") in {"RENAMED", "LEGAL_NAME_CHANGE"}:
            if assertion.get("subject_grain_id") not in alias_endpoints:
                return True
    return False


def check_alternatives_blocked(subject: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    by_reference: dict[str, list[dict[str, Any]]] = {}
    for alternative in subject.get("alternatives", []):
        by_reference.setdefault(alternative.get("resolution_reference", ""), []).append(alternative)
    for reference, alternatives in by_reference.items():
        if len(alternatives) < 2:
            continue
        statuses = {alternative.get("resolution_status") for alternative in alternatives}
        if {"AMBIGUOUS", "UNKNOWN"}.intersection(statuses):
            errors.append(IDENTITY_AMBIGUITY_BLOCKED)
        if "CONFLICTED" in statuses:
            errors.append(IDENTITY_CONFLICT_BLOCKED)
    return errors


def check_unit_separation(subject: dict[str, Any]) -> bool:
    units = [record for record in subject.get("grains", []) if record.get("grain_type") == "UNIT"]
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            a, b = units[i], units[j]
            if not _intervals_overlap(a.get("valid_from", ""), a.get("valid_to"), b.get("valid_from", ""), b.get("valid_to")):
                continue
            evidence_a = {ref.get("evidence_ref") for ref in a.get("evidence_refs", []) if isinstance(ref, dict)}
            evidence_b = {ref.get("evidence_ref") for ref in b.get("evidence_refs", []) if isinstance(ref, dict)}
            if evidence_a and evidence_a == evidence_b:
                return True
    return False


def check_multi_unit_establishment(subject: dict[str, Any]) -> bool:
    unit_location: dict[str, str] = {}
    for link in subject.get("links", []):
        if link.get("link_type") == "PART_OF" and _grain_type_of(link.get("from_grain_id", "")) == "UNIT":
            unit_location.setdefault(link["from_grain_id"], link.get("to_grain_id", ""))
    for record in subject.get("grains", []):
        if record.get("grain_type") != "ESTABLISHMENT":
            continue
        units = [
            link.get("to_grain_id")
            for link in _active_links(subject)
            if link.get("link_type") == "LOCATED_AT"
            and link.get("from_grain_id") == record.get("grain_id")
            and _grain_type_of(link.get("to_grain_id", "")) == "UNIT"
        ]
        if len(units) < 2:
            continue
        locations = {unit_location.get(unit) for unit in units if unit_location.get(unit)}
        if len(locations) > 1:
            return True
    return False


def check_duplicate_active_truth(subject: dict[str, Any]) -> bool:
    active = [
        record for record in subject.get("grains", [])
        if record.get("grain_type") not in DUPLICATE_TRUTH_EXCLUDED
        and record.get("grain_status") == "ACTIVE"
    ]
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            if a.get("grain_type") != b.get("grain_type"):
                continue
            if a.get("grain_id") == b.get("grain_id"):
                continue
            if not _intervals_overlap(a.get("valid_from", ""), a.get("valid_to"), b.get("valid_from", ""), b.get("valid_to")):
                continue
            evidence_a = {ref.get("evidence_ref") for ref in a.get("evidence_refs", []) if isinstance(ref, dict)}
            evidence_b = {ref.get("evidence_ref") for ref in b.get("evidence_refs", []) if isinstance(ref, dict)}
            if evidence_a and evidence_a == evidence_b:
                return True
    return False


def material_checks(subject: dict[str, Any]) -> list[str]:
    """Material semantic verdict: emit frozen registered codes, stable order."""
    errors: list[str] = []
    if check_suite_collapse(subject):
        errors.append(REGISTERED_SUITE_COLLAPSE)
    if check_protected_alias_clear(subject):
        errors.append(REGISTERED_PROTECTED_ALIAS_CLEAR)
    if check_grain_collapse(subject):
        errors.append(IDENTITY_GRAIN_COLLAPSE)
    if check_address_as_identity(subject):
        errors.append(IDENTITY_ADDRESS_AS_IDENTITY)
    if check_relocation_rewrite(subject):
        errors.append(IDENTITY_RELOCATION_REWRITE)
    if check_closure_temporal(subject):
        errors.append(IDENTITY_CLOSURE_TEMPORAL)
    if check_alias_supersede(subject):
        errors.append(IDENTITY_ALIAS_SUPERSEDE)
    errors.extend(check_alternatives_blocked(subject))
    if check_unit_separation(subject):
        errors.append(IDENTITY_UNIT_SEPARATION)
    if check_multi_unit_establishment(subject):
        errors.append(IDENTITY_MULTI_UNIT_ESTABLISHMENT)
    if check_duplicate_active_truth(subject):
        errors.append(IDENTITY_DUPLICATE_ACTIVE_TRUTH)
    return sorted(set(errors))
