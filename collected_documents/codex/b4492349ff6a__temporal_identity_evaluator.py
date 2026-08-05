"""Independent black-box IDENTITY-001 temporal identity evaluator.

This evaluator judges one frozen-schema temporal identity subject against the
frozen IDENTITY-001 public evaluator contract and the frozen
``contracts/temporal_identity.schema.json``.  It never imports
``src.cre_foundry.identity`` or any identity material-implementation module, and
it never invokes the future house validator or canonical-run generator.

The evaluator independently reconstructs every semantic identity output from the
subject document itself: it recomputes every record digest, re-derives grain
statuses from temporal assertions, re-derives the protection verdict from the
fail-closed clear conditions, re-derives alias / linked-location / former-address
coverage for protected roots, re-derives alternative resolution semantics, and
compares the reconstruction against the subject's declared outputs.  Hashes are
never trusted alone; a coordinated rehash around semantically incorrect identity
results remains detectable (IDENTITY-RECONSTRUCTION-MISMATCH).

Canonical serialization (UTF8_CANONICAL_JSON_SORTED_KEYS):
  * sorted object keys, integer numbers only, separators comma/colon, UTF-8,
    no trailing whitespace;
  * set-semantics arrays (evidence refs, aliases, coverage sets) are sorted
    before hashing by the subject builder; semantically ordered arrays (rank,
    lineage journal, protection expansion path order) keep their order;
  * every ``*_digest`` field is the canonical digest of its own record with that
    digest field removed;
  * ``candidate_snapshot_digest`` = canonical digest of the protection expansion
    array;
  * ``bundle_sha256`` = canonical digest of the bundle projection with the
    ``bundle_sha256`` field removed;
  * ``protection_decision_digest`` = canonical digest of the decision with the
    ``protection_decision_digest`` field removed;
  * lineage node digest = canonical digest of the referenced record with its own
    digest field removed;
  * journal chain: entry[0].predecessor_digest = digest of the genesis sentinel
    ``{"genesis": true}``; entry[i].predecessor_digest = digest of entry[i-1];
  * subject digest = canonical digest of the whole subject with the top-level
    ``subject_sha256`` and the replay-receipt ``subject_sha256`` removed.

Every diagnostic is emitted as the exact registered code (no message suffix) so
the evaluator output is byte-stable, machine comparable, and identical to the
frozen contract's ``expected_diagnostic`` values.  The evaluator fails closed:
any malformed, unknown, or inconsistent artifact yields a registered diagnostic
and is never blessed by a rehashed receipt.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "artifacts/identity/public_evaluator_contract.json"
SCHEMA_PATH = ROOT / "contracts/temporal_identity.schema.json"
EVALUATOR_PATH = Path(__file__).resolve()

EVALUATOR_ID = "identity-temporal-public-v1"
EVALUATOR_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
EXECUTION_SCOPE = "SYNTHETIC_NON_INFLUENCING"
CANONICAL_SERIALIZATION = "UTF8_CANONICAL_JSON_SORTED_KEYS"

# Stable foundational diagnostics (frozen contract stable_diagnostics).
IDENTITY_SHAPE_INVALID = "IDENTITY-SHAPE-INVALID"
IDENTITY_SCHEMA_UNREGISTERED = "IDENTITY-SCHEMA-UNREGISTERED"
IDENTITY_DIGEST_BINDING = "IDENTITY-DIGEST-BINDING"
IDENTITY_UNSUPPORTED_TYPE = "IDENTITY-UNSUPPORTED-TYPE"
IDENTITY_SCHEMA_FAILURE = "IDENTITY-SCHEMA-FAILURE"
IDENTITY_LIVE_DENIAL = "IDENTITY-LIVE-DENIAL"
IDENTITY_EXTERNAL_EFFECT = "IDENTITY-EXTERNAL-EFFECT"
IDENTITY_CLAIM_CEILING = "IDENTITY-CLAIM-CEILING"

# Registered mutation diagnostics (frozen contract registered_mutations).
IDENTITY_GRAIN_COLLAPSE = "IDENTITY-GRAIN-COLLAPSE"
REGISTERED_SUITE_COLLAPSE = "registered mutation detected: suite-collapse"
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
IDENTITY_FUTURE_EVIDENCE = "IDENTITY-FUTURE-EVIDENCE"
IDENTITY_STALE_BUNDLE_CLEAR = "IDENTITY-STALE-BUNDLE-CLEAR"
IDENTITY_INCOMPLETE_BUNDLE_CLEAR = "IDENTITY-INCOMPLETE-BUNDLE-CLEAR"
REGISTERED_PROTECTED_ALIAS_CLEAR = "registered mutation detected: protected-alias-clear"
IDENTITY_PROTECTION_DIGEST_DRIFT = "IDENTITY-PROTECTION-DIGEST-DRIFT"
IDENTITY_MANUAL_UNKNOWN_CLEAR = "IDENTITY-MANUAL-UNKNOWN-CLEAR"
IDENTITY_MANUAL_HISTORY_REWRITE = "IDENTITY-MANUAL-HISTORY-REWRITE"
IDENTITY_CORRECTION_DELETION = "IDENTITY-CORRECTION-DELETION"
IDENTITY_LINEAGE_BINDING = "IDENTITY-LINEAGE-BINDING"
IDENTITY_DUPLICATE_ACTIVE_TRUTH = "IDENTITY-DUPLICATE-ACTIVE-TRUTH"
IDENTITY_RECONSTRUCTION_MISMATCH = "IDENTITY-RECONSTRUCTION-MISMATCH"
IDENTITY_VALID_VS_OBSERVED = "IDENTITY-VALID-VS-OBSERVED"
IDENTITY_EVALUATOR_COUPLING = "IDENTITY-EVALUATOR-COUPLING"

GRAIN_TYPES = frozenset({
    "LEGAL_ENTITY", "PARENT", "SUBSIDIARY", "OPERATING_BUSINESS", "BRAND",
    "FRANCHISE_SYSTEM", "FRANCHISEE", "ESTABLISHMENT", "PHYSICAL_LOCATION",
    "ADDRESS", "BUILDING", "UNIT", "PARCEL", "PROPERTY", "PROPERTY_OWNER",
    "OCCUPIER", "PROTECTED_ACCOUNT", "REPRESENTATIVE_RELATIONSHIP",
})

LINK_TYPES = frozenset({
    "OWNS", "OCCUPIES", "OPERATES", "BRAND_OF", "SUBSIDIARY_OF", "PARENT_OF",
    "FRANCHISE_SYSTEM_OF", "FRANCHISEE_OF", "LOCATED_AT", "PART_OF",
    "PREDECESSOR_OF", "SUCCESSOR_OF", "ALIAS_OF", "PROTECTED_LINK",
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

RECORD_ARRAY_ORDER = [
    "grains", "temporal_assertions", "links", "alternatives", "corrections",
]

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

_FORMAT_CHECKER = FormatChecker()


# ---------------------------------------------------------------------------
# Canonical serialization and strict parsing
# ---------------------------------------------------------------------------

def canonical_json_bytes(value: Any) -> bytes:
    """UTF-8 canonical JSON: sorted keys, integer numbers, comma/colon."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_load_json(path: Path) -> Any:
    """Load JSON rejecting duplicate keys (STRICT_REJECTED) and shape-invalid text."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def _strict_load_text(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


# ---------------------------------------------------------------------------
# Clock helpers
# ---------------------------------------------------------------------------

def _ts(value: Any) -> datetime:
    """Parse an RFC3339 timestamp to a naive-UTC datetime (raises on bad input)."""
    if not isinstance(value, str) or not value:
        raise ValueError("clock must be a non-empty RFC3339 string")
    raw = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError(f"naive clock without explicit offset: {value}")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _is_rfc3339(value: Any) -> bool:
    try:
        _ts(value)
        return True
    except (TypeError, ValueError):
        return False


def _shift(ts: str, days: int) -> str:
    base = _ts(ts)
    shifted = (base + timedelta(days=days)).replace(tzinfo=timezone.utc)
    return shifted.isoformat(timespec="seconds").replace("+00:00", "Z")


def _interval_contains(effective_from: str, effective_to: str | None, when: str) -> bool:
    start = _ts(effective_from)
    at = _ts(when)
    if at < start:
        return False
    if effective_to is not None and at > _ts(effective_to):
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


# ---------------------------------------------------------------------------
# Digest conventions
# ---------------------------------------------------------------------------

def _record_digest(record: dict[str, Any], digest_field: str) -> str:
    body = {key: value for key, value in record.items() if key != digest_field}
    return digest_json(body)


def _subject_digest(subject: dict[str, Any]) -> str:
    body = copy.deepcopy(subject)
    body.pop("subject_sha256", None)
    receipt = body.get("replay_receipt")
    if isinstance(receipt, dict):
        receipt.pop("subject_sha256", None)
    return digest_json(body)


def rebind_subject_digests(subject: dict[str, Any]) -> dict[str, Any]:
    """Recompute only the subject and replay-receipt digest bindings."""
    digest = _subject_digest(subject)
    subject["subject_sha256"] = digest
    if isinstance(subject.get("replay_receipt"), dict):
        subject["replay_receipt"]["subject_sha256"] = digest
    return subject


# ---------------------------------------------------------------------------
# Subject builder (construction helper shared by the validator and the tests)
# ---------------------------------------------------------------------------

def _evidence(ref: str, etype: str = "OBSERVATION") -> dict[str, Any]:
    return {
        "evidence_ref": ref,
        "evidence_type": etype,
        "evidence_sha256": digest_json({"evidence_ref": ref, "evidence_type": etype}),
    }


def _build_grain(gid: str, gtype: str, observed: str = "2024-05-01T00:00:00Z", **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "grain_id": gid,
        "grain_type": gtype,
        "observed_at": observed,
        "published_at": observed,
        "retrieved_at": observed,
        "source_snapshot_time": observed,
        "available_at": observed,
        "effective_from": observed,
        "effective_to": None,
        "valid_from": _shift(observed, -1),
        "valid_to": None,
        "superseded_at": None,
        "correction_at": None,
        "grain_status": "ACTIVE",
        "evidence_refs": [_evidence("OBS:" + gid)],
    }
    record.update(overrides)
    return record


def _build_assertion(
    aid: str,
    subject_grain_id: str,
    assertion_type: str,
    decision_cutoff: str = "2024-06-01T00:00:00Z",
    observed: str = "2024-05-01T00:00:00Z",
    **overrides: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "assertion_id": aid,
        "subject_grain_id": subject_grain_id,
        "assertion_type": assertion_type,
        "observed_at": observed,
        "published_at": observed,
        "retrieved_at": observed,
        "source_snapshot_time": observed,
        "available_at": observed,
        "effective_from": observed,
        "effective_to": None,
        "valid_from": _shift(observed, -1),
        "valid_to": None,
        "decision_cutoff": decision_cutoff,
        "superseded_at": None,
        "correction_at": None,
        "evidence_refs": [_evidence("OBS:" + aid)],
    }
    record.update(overrides)
    return record


def _build_link(
    lid: str,
    link_type: str,
    from_gid: str,
    to_gid: str,
    support_state: str = "SUPPORTED",
    observed: str = "2024-05-01T00:00:00Z",
    **overrides: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "link_id": lid,
        "link_type": link_type,
        "from_grain_id": from_gid,
        "to_grain_id": to_gid,
        "effective_from": observed,
        "effective_to": None,
        "valid_from": _shift(observed, -1),
        "valid_to": None,
        "observed_at": observed,
        "published_at": observed,
        "retrieved_at": observed,
        "source_snapshot_time": observed,
        "available_at": observed,
        "superseded_at": None,
        "evidence_refs": [_evidence("OBS:" + lid)],
        "support_state": support_state,
    }
    record.update(overrides)
    return record


def _build_bundle() -> dict[str, Any]:
    return {
        "bundle_id": "BUNDLE:b-1",
        "bundle_version": "1.0.0",
        "bundle_sha256": "0" * 64,
        "bundle_completeness": "COMPLETE",
        "token_extraction_completeness": "COMPLETE",
        "authoritative_status": "AUTHORITATIVE",
        "valid_from": "2024-05-01T00:00:00Z",
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
        "expansion_paths": ["EXPATH:pa-1-est-1", "EXPATH:pa-1-pa-2", "EXPATH:pa-1-pl-1"],
        "candidate_snapshot_digest": "0" * 64,
        "evaluated_at": "2024-06-01T00:00:00Z",
    }


def _build_clean() -> dict[str, Any]:
    """Assemble the clean synthetic subject without any digest fields populated."""
    subject = {
        "document_kind": "TEMPORAL_IDENTITY_SYNTHETIC_SUBJECT",
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
            "created_at": "2024-06-01T00:00:00Z",
            "builder_identity": "identity-evaluator-independent-builder",
            "determinism_note": "deterministic synthetic subject; reconstruction must agree",
        },
        "route_day_decision_context": {
            "decision_cutoff": "2024-06-01T00:00:00Z",
            "stage1_frozen_at": "2024-05-30T00:00:00Z",
            "route_day": "2024-06-01",
            "generation": 0,
            "exact_ten_or_abstain_context": "synthetic route-day decision at proof level 4",
        },
        "grains": [
            _build_grain("LEGAL_ENTITY:legal-1", "LEGAL_ENTITY"),
            _build_grain("PARENT:parent-1", "PARENT"),
            _build_grain("SUBSIDIARY:sub-1", "SUBSIDIARY"),
            _build_grain("OPERATING_BUSINESS:biz-1", "OPERATING_BUSINESS"),
            _build_grain("BRAND:brand-1", "BRAND"),
            _build_grain("FRANCHISE_SYSTEM:fsys-1", "FRANCHISE_SYSTEM"),
            _build_grain("FRANCHISEE:franchisee-1", "FRANCHISEE"),
            _build_grain("ESTABLISHMENT:est-1", "ESTABLISHMENT"),
            _build_grain("ESTABLISHMENT:est-2", "ESTABLISHMENT"),
            _build_grain("PHYSICAL_LOCATION:pl-1", "PHYSICAL_LOCATION"),
            _build_grain("ADDRESS:addr-1", "ADDRESS"),
            _build_grain("BUILDING:bldg-1", "BUILDING"),
            _build_grain("UNIT:u-101", "UNIT"),
            _build_grain("UNIT:u-102", "UNIT"),
            _build_grain("PARCEL:parcel-1", "PARCEL"),
            _build_grain("PROPERTY:prop-1", "PROPERTY"),
            _build_grain("PROPERTY_OWNER:owner-1", "PROPERTY_OWNER"),
            _build_grain("OCCUPIER:occ-1", "OCCUPIER"),
            _build_grain("PROTECTED_ACCOUNT:pa-1", "PROTECTED_ACCOUNT"),
            _build_grain("PROTECTED_ACCOUNT:pa-2", "PROTECTED_ACCOUNT"),
            _build_grain("REPRESENTATIVE_RELATIONSHIP:rep-1", "REPRESENTATIVE_RELATIONSHIP"),
        ],
        "temporal_assertions": [
            _build_assertion("ASSERT:obs-1", "ESTABLISHMENT:est-1", "OBSERVED"),
            _build_assertion("ASSERT:obs-2", "ESTABLISHMENT:est-2", "OBSERVED"),
        ],
        "links": [
            _build_link("LINK:own-biz-brand", "OWNS", "OPERATING_BUSINESS:biz-1", "BRAND:brand-1"),
            _build_link("LINK:sub-legal", "SUBSIDIARY_OF", "SUBSIDIARY:sub-1", "LEGAL_ENTITY:legal-1"),
            _build_link("LINK:parent-of", "PARENT_OF", "PARENT:parent-1", "SUBSIDIARY:sub-1"),
            _build_link("LINK:brand-sys", "BRAND_OF", "BRAND:brand-1", "FRANCHISE_SYSTEM:fsys-1"),
            _build_link("LINK:franchisee-sys", "FRANCHISEE_OF", "FRANCHISEE:franchisee-1", "FRANCHISE_SYSTEM:fsys-1"),
            _build_link("LINK:est-op-1", "OPERATES", "OPERATING_BUSINESS:biz-1", "ESTABLISHMENT:est-1"),
            _build_link("LINK:est-op-2", "OPERATES", "OPERATING_BUSINESS:biz-1", "ESTABLISHMENT:est-2"),
            _build_link("LINK:est-loc-1", "LOCATED_AT", "ESTABLISHMENT:est-1", "UNIT:u-101"),
            _build_link("LINK:est-loc-2", "LOCATED_AT", "ESTABLISHMENT:est-2", "UNIT:u-102"),
            _build_link("LINK:u-pl-1", "PART_OF", "UNIT:u-101", "PHYSICAL_LOCATION:pl-1"),
            _build_link("LINK:u-pl-2", "PART_OF", "UNIT:u-102", "PHYSICAL_LOCATION:pl-1"),
            _build_link("LINK:pl-addr", "LOCATED_AT", "PHYSICAL_LOCATION:pl-1", "ADDRESS:addr-1"),
            _build_link("LINK:addr-bldg", "PART_OF", "ADDRESS:addr-1", "BUILDING:bldg-1"),
            _build_link("LINK:bldg-prop", "PART_OF", "BUILDING:bldg-1", "PROPERTY:prop-1"),
            _build_link("LINK:prop-parcel", "PART_OF", "PROPERTY:prop-1", "PARCEL:parcel-1"),
            _build_link("LINK:owner-prop", "OWNS", "PROPERTY_OWNER:owner-1", "PROPERTY:prop-1"),
            _build_link("LINK:occ-unit", "OCCUPIES", "OCCUPIER:occ-1", "UNIT:u-101"),
            _build_link("LINK:alias-pa", "ALIAS_OF", "PROTECTED_ACCOUNT:pa-1", "PROTECTED_ACCOUNT:pa-2"),
            _build_link("LINK:prot-pl", "PROTECTED_LINK", "PROTECTED_ACCOUNT:pa-1", "PHYSICAL_LOCATION:pl-1"),
            _build_link("LINK:prot-est", "PROTECTED_LINK", "PROTECTED_ACCOUNT:pa-1", "ESTABLISHMENT:est-1"),
        ],
        "alternatives": [],
        "corrections": [],
        "protection_bundle_projection": _build_bundle(),
        "protection_expansion": [
            {
                "path_id": "EXPATH:pa-1-est-1",
                "depth": 1,
                "from_grain_id": "PROTECTED_ACCOUNT:pa-1",
                "to_grain_id": "ESTABLISHMENT:est-1",
                "relationship_type": "PROTECTED_LINK",
                "evidence_refs": [_evidence("OBS:est-1")],
                "path_digest": "0" * 64,
            },
            {
                "path_id": "EXPATH:pa-1-pa-2",
                "depth": 1,
                "from_grain_id": "PROTECTED_ACCOUNT:pa-1",
                "to_grain_id": "PROTECTED_ACCOUNT:pa-2",
                "relationship_type": "ALIAS_OF",
                "evidence_refs": [_evidence("OBS:pa-2")],
                "path_digest": "0" * 64,
            },
            {
                "path_id": "EXPATH:pa-1-pl-1",
                "depth": 1,
                "from_grain_id": "PROTECTED_ACCOUNT:pa-1",
                "to_grain_id": "PHYSICAL_LOCATION:pl-1",
                "relationship_type": "PROTECTED_LINK",
                "evidence_refs": [_evidence("OBS:pl-1")],
                "path_digest": "0" * 64,
            },
        ],
        "protection_decision": {
            "decision_id": "PROT:dec-1",
            "evaluated_at": "2024-06-01T00:00:00Z",
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
            "regenerated_at": "2024-06-01T00:00:00Z",
        },
        "claims_and_limitations": {
            "claim_kind": EXECUTION_SCOPE,
            "proof_level": 4,
            "claims_not_established": list(ALL_CLAIM_NOT_ESTABLISHED),
            "live_permissions": False,
            "external_effect_occurred": False,
        },
    }
    return subject


def build_clean_subject() -> dict[str, Any]:
    """Return a fully digested, schema-conformant clean synthetic subject.

    The subject is regenerated from scratch on every call so tests and the house
    validator never share mutable state.  All digests, lineage, journal, and the
    subject/receipt bindings are computed by :func:`rebuild_digests`.
    """
    return rebuild_digests(_build_clean())


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


def _lookup_record_digest(subject: dict[str, Any], record_id: Any) -> str | None:
    if not isinstance(record_id, str):
        return None
    for array_name, digest_field in RECORD_DIGEST_FIELD.items():
        for record in subject.get(array_name, []):
            rid = record.get("grain_id", record.get("assertion_id", record.get("link_id", record.get("alternative_id", record.get("correction_id")))))
            if rid == record_id:
                return _record_digest(record, digest_field)
    return None


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
            "recorded_at": "2024-06-01T00:00:00Z",
        }
        predecessor = digest_json(entry)
        journal.append(entry)

    subject["lineage"] = {
        "lineage_id": "LINEAGE:identity-001",
        "nodes": nodes,
        "edges": edges,
        "journal": journal,
    }


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


def rebuild_digests(subject: dict[str, Any], preserve_predecessors: bool = False) -> dict[str, Any]:
    """Recompute every digest field, lineage, journal, and subject binding.

    Construction helper: makes a mutated subject self-consistent so only the
    intended semantic diagnostic fires.  ``preserve_predecessors`` keeps the
    correction predecessor digests stale so an in-place history rewrite remains
    detectable (IDENTITY-MANUAL-HISTORY-REWRITE).  It never weakens the
    evaluator -- the evaluator only verifies these conventions and independently
    reconstructs the same outputs.
    """
    _rebuild_record_digests(subject, preserve_predecessors=preserve_predecessors)
    _rebuild_protection_digests(subject)
    _rebuild_lineage(subject)
    return rebind_subject_digests(subject)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_registered(subject: dict[str, Any], errors: list[str]) -> None:
    if subject.get("document_kind") != "TEMPORAL_IDENTITY_SYNTHETIC_SUBJECT":
        errors.append(IDENTITY_SCHEMA_UNREGISTERED)
    if subject.get("schema_version") != SCHEMA_VERSION:
        errors.append(IDENTITY_SCHEMA_UNREGISTERED)
    if subject.get("execution_scope") != EXECUTION_SCOPE:
        errors.append(IDENTITY_SCHEMA_UNREGISTERED)


def _check_digest_bindings(subject: dict[str, Any], errors: list[str]) -> None:
    expected_schema = digest_bytes(SCHEMA_PATH.read_bytes())
    expected_contract = digest_bytes(CONTRACT_PATH.read_bytes())
    if subject.get("schema_sha256") != expected_schema:
        errors.append(IDENTITY_DIGEST_BINDING)
    if subject.get("contract_sha256") != expected_contract:
        errors.append(IDENTITY_DIGEST_BINDING)
    receipt = subject.get("replay_receipt")
    if not isinstance(receipt, dict):
        errors.append(IDENTITY_DIGEST_BINDING)
        return
    if receipt.get("contract_sha256") != expected_contract:
        errors.append(IDENTITY_DIGEST_BINDING)
    if receipt.get("schema_sha256") != expected_schema:
        errors.append(IDENTITY_DIGEST_BINDING)
    if receipt.get("canonical_serialization") != CANONICAL_SERIALIZATION:
        errors.append(IDENTITY_DIGEST_BINDING)
    subject_digest = _subject_digest(subject)
    if subject.get("subject_sha256") != subject_digest:
        errors.append(IDENTITY_DIGEST_BINDING)
    if receipt.get("subject_sha256") != subject_digest:
        errors.append(IDENTITY_DIGEST_BINDING)
    if receipt.get("evaluator_sha256") != digest_bytes(EVALUATOR_PATH.read_bytes()):
        errors.append(IDENTITY_DIGEST_BINDING)

    for array_name, digest_field in RECORD_DIGEST_FIELD.items():
        for record in subject.get(array_name, []):
            if not isinstance(record, dict):
                errors.append(IDENTITY_DIGEST_BINDING)
                continue
            if record.get(digest_field) != _record_digest(record, digest_field):
                errors.append(IDENTITY_DIGEST_BINDING)
    for path in subject.get("protection_expansion", []):
        if isinstance(path, dict) and path.get("path_digest") != _record_digest(path, "path_digest"):
            errors.append(IDENTITY_DIGEST_BINDING)


def _check_live_and_ceiling(subject: dict[str, Any], errors: list[str]) -> None:
    if subject.get("live_permissions") is not False:
        errors.append(IDENTITY_LIVE_DENIAL)
    if subject.get("external_effect_occurred") is not False:
        errors.append(IDENTITY_EXTERNAL_EFFECT)
    if subject.get("proof_level") != 4:
        errors.append(IDENTITY_CLAIM_CEILING)
    claims = subject.get("claims_and_limitations")
    if isinstance(claims, dict):
        if claims.get("claim_kind") != EXECUTION_SCOPE:
            errors.append(IDENTITY_CLAIM_CEILING)
        if claims.get("proof_level") != 4:
            errors.append(IDENTITY_CLAIM_CEILING)
        if claims.get("live_permissions") is not False:
            errors.append(IDENTITY_CLAIM_CEILING)
        if claims.get("external_effect_occurred") is not False:
            errors.append(IDENTITY_CLAIM_CEILING)
        not_established = claims.get("claims_not_established")
        if not isinstance(not_established, list) or not not_established:
            errors.append(IDENTITY_CLAIM_CEILING)


def _unsupported_types(subject: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for record in subject.get("grains", []):
        gid = record.get("grain_id")
        gtype = record.get("grain_type")
        if isinstance(gtype, str) and gtype not in GRAIN_TYPES:
            errors.append(IDENTITY_UNSUPPORTED_TYPE)
        if isinstance(gid, str) and gid.split(":", 1)[0] not in GRAIN_TYPES:
            errors.append(IDENTITY_UNSUPPORTED_TYPE)
    for record in subject.get("links", []):
        ltype = record.get("link_type")
        if isinstance(ltype, str) and ltype not in LINK_TYPES:
            errors.append(IDENTITY_UNSUPPORTED_TYPE)
    return sorted(set(errors))


def _check_schema(subject: dict[str, Any]) -> list[str]:
    try:
        schema = strict_load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, json.JSONDecodeError):
        return [IDENTITY_SCHEMA_FAILURE]
    validator = Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)
    errors = sorted({IDENTITY_SCHEMA_FAILURE for _ in validator.iter_errors(subject)})
    return errors


def _check_clock_formats(subject: dict[str, Any], errors: list[str]) -> None:
    clock_fields = [
        "observed_at", "published_at", "retrieved_at", "source_snapshot_time",
        "available_at", "effective_from", "effective_to", "valid_from", "valid_to",
        "superseded_at", "correction_at",
    ]
    top_context = subject.get("route_day_decision_context")
    for array_name in RECORD_ARRAY_ORDER:
        for record in subject.get(array_name, []):
            for field in clock_fields:
                value = record.get(field)
                if value is not None and not _is_rfc3339(value):
                    errors.append(IDENTITY_SHAPE_INVALID)
    if isinstance(top_context, dict):
        for field in ("decision_cutoff", "stage1_frozen_at"):
            value = top_context.get(field)
            if value is not None and not _is_rfc3339(value):
                errors.append(IDENTITY_SHAPE_INVALID)


def _decision_cutoff(subject: dict[str, Any]) -> str:
    context = subject.get("route_day_decision_context")
    if isinstance(context, dict) and isinstance(context.get("decision_cutoff"), str):
        return context["decision_cutoff"]
    return "9999-12-31T00:00:00Z"


def _check_future_evidence(subject: dict[str, Any], errors: list[str]) -> None:
    cutoff = _decision_cutoff(subject)
    for array_name in ("grains", "temporal_assertions", "links"):
        for record in subject.get(array_name, []):
            available = record.get("available_at")
            if isinstance(available, str) and _is_rfc3339(available) and _ts(available) > _ts(cutoff):
                errors.append(IDENTITY_FUTURE_EVIDENCE)
    decision = subject.get("protection_decision")
    if isinstance(decision, dict) and isinstance(decision.get("evaluated_at"), str):
        if _is_rfc3339(decision["evaluated_at"]) and _ts(decision["evaluated_at"]) > _ts(cutoff):
            errors.append(IDENTITY_FUTURE_EVIDENCE)
    bundle = subject.get("protection_bundle_projection")
    if isinstance(bundle, dict) and isinstance(bundle.get("refreshed_at"), str):
        if _is_rfc3339(bundle["refreshed_at"]) and _ts(bundle["refreshed_at"]) > _ts(cutoff):
            errors.append(IDENTITY_FUTURE_EVIDENCE)


def _check_valid_vs_observed(subject: dict[str, Any], errors: list[str]) -> None:
    for array_name in ("grains", "temporal_assertions", "links"):
        for record in subject.get(array_name, []):
            valid_from = record.get("valid_from")
            valid_to = record.get("valid_to")
            observed_at = record.get("observed_at")
            if isinstance(valid_from, str) and isinstance(valid_to, str) and _is_rfc3339(valid_from) and _is_rfc3339(valid_to):
                if _ts(valid_to) < _ts(valid_from):
                    errors.append(IDENTITY_VALID_VS_OBSERVED)
            if isinstance(valid_from, str) and isinstance(observed_at, str) and _is_rfc3339(valid_from) and _is_rfc3339(observed_at):
                if _ts(valid_from) > _ts(observed_at):
                    errors.append(IDENTITY_VALID_VS_OBSERVED)


def _check_corporate_temporal(subject: dict[str, Any], errors: list[str]) -> None:
    grain_by_id = {record.get("grain_id"): record for record in subject.get("grains", [])}
    for record in subject.get("links", []):
        if record.get("link_type") not in ("SUBSIDIARY_OF", "PARENT_OF"):
            continue
        child = record.get("to_grain_id")
        child_grain = grain_by_id.get(child)
        valid_from = record.get("valid_from")
        if child_grain is not None and isinstance(valid_from, str) and isinstance(child_grain.get("valid_from"), str):
            if _is_rfc3339(valid_from) and _is_rfc3339(child_grain["valid_from"]) and _ts(valid_from) < _ts(child_grain["valid_from"]):
                errors.append(IDENTITY_CORPORATE_TEMPORAL)


def _grain_type_of(gid: str) -> str:
    return gid.split(":", 1)[0]


def _check_grain_collapse(subject: dict[str, Any], errors: list[str]) -> None:
    seen: dict[str, str] = {}
    grain_ids = {record.get("grain_id") for record in subject.get("grains", []) if isinstance(record, dict)}
    for record in subject.get("grains", []):
        gid = record.get("grain_id")
        gtype = record.get("grain_type")
        if not isinstance(gid, str) or not isinstance(gtype, str):
            continue
        if gid.split(":", 1)[0] != gtype:
            errors.append(IDENTITY_GRAIN_COLLAPSE)
        if gid in seen and seen[gid] != gtype:
            errors.append(IDENTITY_GRAIN_COLLAPSE)
        seen.setdefault(gid, gtype)
    for record in subject.get("links", []):
        for endpoint in ("from_grain_id", "to_grain_id"):
            value = record.get(endpoint)
            if isinstance(value, str) and value not in grain_ids:
                errors.append(IDENTITY_GRAIN_COLLAPSE)


def _active_links(subject: dict[str, Any]) -> list[dict[str, Any]]:
    cutoff = _decision_cutoff(subject)
    active: list[dict[str, Any]] = []
    for record in subject.get("links", []):
        effective_from = record.get("effective_from")
        if isinstance(effective_from, str) and _is_rfc3339(effective_from):
            if _interval_contains(effective_from, record.get("effective_to"), cutoff):
                active.append(record)
    return active


def _link_occupants_at(subject: dict[str, Any], to_gid: str, link_types: set[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for link in _active_links(subject):
        if link.get("link_type") in link_types and link.get("to_grain_id") == to_gid:
            result.append(link)
    return result


def _check_suite_collapse(subject: dict[str, Any], errors: list[str]) -> None:
    occupant_types = {"ESTABLISHMENT", "OPERATING_BUSINESS"}
    location_links = {"LOCATED_AT", "OCCUPIES"}
    for unit in subject.get("grains", []):
        if unit.get("grain_type") != "UNIT":
            continue
        occupants: list[dict[str, Any]] = []
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
                    errors.append(REGISTERED_SUITE_COLLAPSE)
                    return


def _check_address_as_identity(subject: dict[str, Any], errors: list[str]) -> None:
    for record in subject.get("links", []):
        if record.get("link_type") not in IDENTITY_LINK_TYPES:
            continue
        from_gid = record.get("from_grain_id")
        if isinstance(from_gid, str) and _grain_type_of(from_gid) in LOCATION_GRAIN_TYPES:
            errors.append(IDENTITY_ADDRESS_AS_IDENTITY)


def _check_address_reuse_linked(subject: dict[str, Any], errors: list[str]) -> None:
    occupant_types = {"ESTABLISHMENT", "OPERATING_BUSINESS", "OCCUPIER"}
    for address in subject.get("grains", []):
        if address.get("grain_type") != "ADDRESS":
            continue
        occupants = _link_occupants_at(subject, address["grain_id"], {"LOCATED_AT", "OCCUPIES"})
        direct = [link for link in occupants if _grain_type_of(link["from_grain_id"]) in occupant_types]
        if len(direct) < 2:
            continue
        for i in range(len(direct)):
            for j in range(i + 1, len(direct)):
                a, b = direct[i], direct[j]
                if _intervals_overlap(a["effective_from"], a.get("effective_to"), b["effective_from"], b.get("effective_to")):
                    errors.append(IDENTITY_ADDRESS_REUSE_LINKED)
                    return


def _check_parent_not_location(subject: dict[str, Any], errors: list[str]) -> None:
    for record in subject.get("links", []):
        if record.get("link_type") not in {"LOCATED_AT", "OCCUPIES"}:
            continue
        to_gid = record.get("to_grain_id")
        if isinstance(to_gid, str) and _grain_type_of(to_gid) in {"PARENT", "SUBSIDIARY"}:
            errors.append(IDENTITY_PARENT_NOT_LOCATION)


def _check_franchise_grain(subject: dict[str, Any], errors: list[str]) -> None:
    grain_by_id = {record.get("grain_id"): record for record in subject.get("grains", [])}
    for record in subject.get("links", []):
        ltype = record.get("link_type")
        from_gid = record.get("from_grain_id")
        if ltype in {"BRAND_OF", "FRANCHISEE_OF", "FRANCHISE_SYSTEM_OF"}:
            required = {"BRAND_OF": "BRAND", "FRANCHISEE_OF": "FRANCHISEE", "FRANCHISE_SYSTEM_OF": "FRANCHISE_SYSTEM"}[ltype]
            if isinstance(from_gid, str) and _grain_type_of(from_gid) != required:
                errors.append(IDENTITY_FRANCHISE_GRAIN)
        if ltype in {"LOCATED_AT", "OCCUPIES"}:
            if isinstance(from_gid, str):
                from_record = grain_by_id.get(from_gid)
                if from_record is not None and from_record.get("grain_type") == "FRANCHISE_SYSTEM":
                    errors.append(IDENTITY_FRANCHISE_GRAIN)


def _check_multi_unit_establishment(subject: dict[str, Any], errors: list[str]) -> None:
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
            errors.append(IDENTITY_MULTI_UNIT_ESTABLISHMENT)


def _check_multi_establishment_property(subject: dict[str, Any], errors: list[str]) -> None:
    by_property: dict[str, list[dict[str, Any]]] = {}
    for link in _active_links(subject):
        if link.get("link_type") == "LOCATED_AT" and _grain_type_of(link.get("to_grain_id", "")) == "PROPERTY":
            by_property.setdefault(link["to_grain_id"], []).append(link)
    for location, links in by_property.items():
        if len(links) < 2:
            continue
        for i in range(len(links)):
            for j in range(i + 1, len(links)):
                a, b = links[i], links[j]
                if not _intervals_overlap(a["effective_from"], a.get("effective_to"), b["effective_from"], b.get("effective_to")):
                    continue
                evidence_a = {ref.get("evidence_ref") for ref in a.get("evidence_refs", []) if isinstance(ref, dict)}
                evidence_b = {ref.get("evidence_ref") for ref in b.get("evidence_refs", []) if isinstance(ref, dict)}
                if evidence_a and evidence_a == evidence_b:
                    errors.append(IDENTITY_MULTI_ESTABLISHMENT_PROPERTY)
                    return


def _check_unit_separation(subject: dict[str, Any], errors: list[str]) -> None:
    units = [record for record in subject.get("grains", []) if record.get("grain_type") == "UNIT"]
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            a, b = units[i], units[j]
            if not _intervals_overlap(a.get("valid_from", ""), a.get("valid_to"), b.get("valid_from", ""), b.get("valid_to")):
                continue
            evidence_a = {ref.get("evidence_ref") for ref in a.get("evidence_refs", []) if isinstance(ref, dict)}
            evidence_b = {ref.get("evidence_ref") for ref in b.get("evidence_refs", []) if isinstance(ref, dict)}
            if evidence_a and evidence_a == evidence_b:
                errors.append(IDENTITY_UNIT_SEPARATION)
                return


def _check_duplicate_active_truth(subject: dict[str, Any], errors: list[str]) -> None:
    active: list[dict[str, Any]] = []
    for record in subject.get("grains", []):
        if record.get("grain_type") in DUPLICATE_TRUTH_EXCLUDED:
            continue
        if record.get("grain_status") == "ACTIVE":
            active.append(record)
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            if a.get("grain_type") != b.get("grain_type"):
                continue
            if a["grain_id"] == b["grain_id"]:
                continue
            if not _intervals_overlap(a.get("valid_from", ""), a.get("valid_to"), b.get("valid_from", ""), b.get("valid_to")):
                continue
            evidence_a = {ref.get("evidence_ref") for ref in a.get("evidence_refs", []) if isinstance(ref, dict)}
            evidence_b = {ref.get("evidence_ref") for ref in b.get("evidence_refs", []) if isinstance(ref, dict)}
            if evidence_a and evidence_a == evidence_b:
                errors.append(IDENTITY_DUPLICATE_ACTIVE_TRUTH)
                return


def _check_relocation_rewrite(subject: dict[str, Any], errors: list[str]) -> None:
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
            errors.append(IDENTITY_RELOCATION_REWRITE)
            continue
        for i in range(len(location_links) - 1):
            current = location_links[i]
            following = location_links[i + 1]
            if current.get("effective_to") is None or _ts(current["effective_to"]) > _ts(following["effective_from"]):
                errors.append(IDENTITY_RELOCATION_REWRITE)
                break


def _check_closure_temporal(subject: dict[str, Any], errors: list[str]) -> None:
    permanently_closed: set[str] = set()
    for assertion in subject.get("temporal_assertions", []):
        a_type = assertion.get("assertion_type")
        if a_type == "CLOSED_PERMANENT" and assertion.get("effective_to") is not None:
            errors.append(IDENTITY_CLOSURE_TEMPORAL)
        if a_type == "CLOSED_TEMPORARY" and assertion.get("effective_to") is None:
            errors.append(IDENTITY_CLOSURE_TEMPORAL)
        if a_type == "CLOSED_PERMANENT":
            permanently_closed.add(assertion.get("subject_grain_id", ""))
    for link in _active_links(subject):
        from_gid = link.get("from_grain_id")
        if from_gid in permanently_closed:
            errors.append(IDENTITY_CLOSURE_TEMPORAL)


def _check_alias_supersede(subject: dict[str, Any], errors: list[str]) -> None:
    alias_endpoints = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "ALIAS_OF":
            alias_endpoints.add(link.get("from_grain_id"))
            alias_endpoints.add(link.get("to_grain_id"))
    for assertion in subject.get("temporal_assertions", []):
        if assertion.get("assertion_type") in {"RENAMED", "LEGAL_NAME_CHANGE"}:
            subject_gid = assertion.get("subject_grain_id")
            if subject_gid not in alias_endpoints:
                errors.append(IDENTITY_ALIAS_SUPERSEDE)


def _check_alternatives(subject: dict[str, Any], errors: list[str]) -> None:
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


def _derived_grain_status(record: dict[str, Any], assertions: list[dict[str, Any]]) -> str:
    gid = record.get("grain_id")
    if isinstance(record.get("grain_status"), str) and record["grain_status"] == "SUPERSEDED":
        return "SUPERSEDED"
    for assertion in assertions:
        if assertion.get("subject_grain_id") != gid:
            continue
        a_type = assertion.get("assertion_type")
        if a_type == "CLOSED_PERMANENT":
            return "CLOSED"
        if a_type == "CLOSED_TEMPORARY":
            return "CLOSED"
        if a_type == "FORMER_OCCUPANCY":
            return "FORMER"
    return "ACTIVE"


def _check_protection(subject: dict[str, Any], errors: list[str]) -> None:
    decision = subject.get("protection_decision")
    bundle = subject.get("protection_bundle_projection")
    if not isinstance(decision, dict) or not isinstance(bundle, dict):
        return
    result_state = decision.get("result_state")
    evaluated_at = decision.get("evaluated_at")
    if result_state != "CLEAR":
        return

    if isinstance(bundle.get("valid_to"), str) and isinstance(evaluated_at, str):
        if _is_rfc3339(bundle["valid_to"]) and _is_rfc3339(evaluated_at) and _ts(evaluated_at) > _ts(bundle["valid_to"]):
            errors.append(IDENTITY_STALE_BUNDLE_CLEAR)
    if isinstance(evaluated_at, str) and isinstance(bundle.get("valid_from"), str):
        if _is_rfc3339(evaluated_at) and _is_rfc3339(bundle["valid_from"]) and _ts(evaluated_at) < _ts(bundle["valid_from"]):
            errors.append(IDENTITY_STALE_BUNDLE_CLEAR)

    if bundle.get("bundle_completeness") != "COMPLETE" or bundle.get("token_extraction_completeness") != "COMPLETE" or bundle.get("authoritative_status") != "AUTHORITATIVE":
        errors.append(IDENTITY_INCOMPLETE_BUNDLE_CLEAR)

    if bundle.get("bundle_sha256") != _record_digest(bundle, "bundle_sha256"):
        errors.append(IDENTITY_PROTECTION_DIGEST_DRIFT)
    snapshot = digest_json(subject.get("protection_expansion", []))
    if bundle.get("candidate_snapshot_digest") != snapshot or decision.get("candidate_snapshot_digest") != snapshot:
        errors.append(IDENTITY_PROTECTION_DIGEST_DRIFT)
    if decision.get("protection_decision_digest") != _record_digest(decision, "protection_decision_digest"):
        errors.append(IDENTITY_PROTECTION_DIGEST_DRIFT)

    if decision.get("manual_review_required") is True:
        errors.append(IDENTITY_MANUAL_UNKNOWN_CLEAR)

    _check_protected_coverage(subject, errors)


def _check_protected_coverage(subject: dict[str, Any], errors: list[str]) -> None:
    bundle = subject.get("protection_bundle_projection")
    if not isinstance(bundle, dict):
        return
    root_ids = {identity for identity in bundle.get("root_protected_identities", [])}
    protected_grains = {
        record.get("grain_id")
        for record in subject.get("grains", [])
        if record.get("grain_type") == "PROTECTED_ACCOUNT"
    }
    required_aliases: set[str] = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "ALIAS_OF":
            from_gid, to_gid = link.get("from_grain_id"), link.get("to_grain_id")
            if from_gid in protected_grains and to_gid in protected_grains:
                required_aliases.add(to_gid)
                required_aliases.add(from_gid)
    required_linked_locations: set[str] = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "PROTECTED_LINK":
            to_gid = link.get("to_grain_id")
            if isinstance(to_gid, str) and _grain_type_of(to_gid) in LOCATION_GRAIN_TYPES:
                required_linked_locations.add(to_gid)
    required_former_addresses: set[str] = set()
    for assertion in subject.get("temporal_assertions", []):
        if assertion.get("assertion_type") == "FORMER_OCCUPANCY":
            if assertion.get("subject_grain_id") in protected_grains:
                for ref in assertion.get("evidence_refs", []):
                    if isinstance(ref, dict):
                        required_former_addresses.add(ref.get("evidence_ref", ""))

    expansion_endpoints = set()
    for path in subject.get("protection_expansion", []):
        expansion_endpoints.add(path.get("from_grain_id"))
        expansion_endpoints.add(path.get("to_grain_id"))
    covered = (
        set(bundle.get("aliases", []))
        | set(bundle.get("linked_locations", []))
        | set(bundle.get("former_addresses", []))
        | set(bundle.get("root_protected_identities", []))
        | {alias for alias in expansion_endpoints}
    )
    missing_aliases = {alias for alias in required_aliases if alias not in covered and alias not in root_ids}
    missing_locations = {loc for loc in required_linked_locations if loc not in covered}
    missing_addresses = {addr for addr in required_former_addresses if addr not in covered}
    if missing_aliases or missing_locations or missing_addresses:
        errors.append(REGISTERED_PROTECTED_ALIAS_CLEAR)


def _check_corrections(subject: dict[str, Any], errors: list[str]) -> None:
    present_ids = set()
    for array_name in RECORD_ARRAY_ORDER:
        for record in subject.get(array_name, []):
            rid = record.get("grain_id", record.get("assertion_id", record.get("link_id", record.get("alternative_id", record.get("correction_id", "")))))
            if rid:
                present_ids.add(rid)
    present_digests: dict[str, str] = {}
    for array_name, digest_field in RECORD_DIGEST_FIELD.items():
        for record in subject.get(array_name, []):
            rid = record.get("grain_id", record.get("assertion_id", record.get("link_id", record.get("alternative_id", record.get("correction_id", "")))))
            if rid:
                present_digests[rid] = _record_digest(record, digest_field)
    for correction in subject.get("corrections", []):
        superseded_id = correction.get("superseded_record_id")
        if superseded_id not in present_ids:
            errors.append(IDENTITY_CORRECTION_DELETION)
        elif present_digests.get(superseded_id) != correction.get("predecessor_digest"):
            errors.append(IDENTITY_MANUAL_HISTORY_REWRITE)


def _check_lineage(subject: dict[str, Any], errors: list[str]) -> None:
    lineage = subject.get("lineage")
    if not isinstance(lineage, dict):
        errors.append(IDENTITY_LINEAGE_BINDING)
        return
    nodes = lineage.get("nodes", [])
    edges = lineage.get("edges", [])
    journal = lineage.get("journal", [])
    node_ids = {node.get("node_id") for node in nodes}

    record_digest_by_id: dict[str, str] = {}
    for array_name, digest_field in RECORD_DIGEST_FIELD.items():
        for record in subject.get(array_name, []):
            rid = record.get("grain_id", record.get("assertion_id", record.get("link_id", record.get("alternative_id", record.get("correction_id", "")))))
            if rid:
                record_digest_by_id[rid] = _record_digest(record, digest_field)
    bundle = subject.get("protection_bundle_projection")
    decision = subject.get("protection_decision")
    if isinstance(bundle, dict):
        record_digest_by_id[bundle.get("bundle_id")] = _record_digest(bundle, "bundle_sha256")
    if isinstance(decision, dict):
        record_digest_by_id[decision.get("decision_id")] = _record_digest(decision, "protection_decision_digest")

    for node in nodes:
        if node.get("record_id") not in record_digest_by_id:
            errors.append(IDENTITY_LINEAGE_BINDING)
        elif node.get("node_digest") != record_digest_by_id[node["record_id"]]:
            errors.append(IDENTITY_LINEAGE_BINDING)

    for edge in edges:
        if edge.get("from_node_id") not in node_ids or edge.get("to_node_id") not in node_ids:
            errors.append(IDENTITY_LINEAGE_BINDING)

    if journal:
        expected = digest_json({"genesis": True})
        for entry in journal:
            if entry.get("predecessor_digest") != expected:
                errors.append(IDENTITY_LINEAGE_BINDING)
                break
            expected = digest_json(entry)


def _check_reconstruction(subject: dict[str, Any], errors: list[str]) -> None:
    protection_specific = {
        IDENTITY_STALE_BUNDLE_CLEAR, IDENTITY_INCOMPLETE_BUNDLE_CLEAR,
        REGISTERED_PROTECTED_ALIAS_CLEAR, IDENTITY_PROTECTION_DIGEST_DRIFT,
        IDENTITY_MANUAL_UNKNOWN_CLEAR,
    }
    protection_fired = any(
        any(error.startswith(code) for code in protection_specific)
        for error in errors
    )
    assertions = subject.get("temporal_assertions", [])
    for record in subject.get("grains", []):
        if not isinstance(record.get("grain_status"), str):
            continue
        derived = _derived_grain_status(record, assertions)
        if derived != record["grain_status"]:
            errors.append(IDENTITY_RECONSTRUCTION_MISMATCH)
            continue

    if not protection_fired:
        derived_verdict = _derive_protection_verdict(subject)
        decision = subject.get("protection_decision")
        if isinstance(decision, dict) and isinstance(decision.get("result_state"), str):
            if derived_verdict == "CLEAR" and decision["result_state"] != "CLEAR":
                errors.append(IDENTITY_RECONSTRUCTION_MISMATCH)
            elif derived_verdict != "CLEAR" and decision["result_state"] == "CLEAR":
                errors.append(IDENTITY_RECONSTRUCTION_MISMATCH)


def _derive_protection_verdict(subject: dict[str, Any]) -> str:
    decision = subject.get("protection_decision")
    bundle = subject.get("protection_bundle_projection")
    if not isinstance(decision, dict) or not isinstance(bundle, dict):
        return "BLOCK"
    if bundle.get("bundle_completeness") != "COMPLETE":
        return "BLOCK"
    if bundle.get("token_extraction_completeness") != "COMPLETE":
        return "BLOCK"
    if bundle.get("authoritative_status") != "AUTHORITATIVE":
        return "BLOCK"
    evaluated_at = decision.get("evaluated_at")
    valid_from = bundle.get("valid_from")
    valid_to = bundle.get("valid_to")
    if isinstance(evaluated_at, str) and isinstance(valid_from, str):
        if _is_rfc3339(evaluated_at) and _is_rfc3339(valid_from) and _ts(evaluated_at) < _ts(valid_from):
            return "BLOCK"
    if isinstance(evaluated_at, str) and isinstance(valid_to, str):
        if _is_rfc3339(evaluated_at) and _is_rfc3339(valid_to) and _ts(evaluated_at) > _ts(valid_to):
            return "BLOCK"
    snapshot = digest_json(subject.get("protection_expansion", []))
    if bundle.get("candidate_snapshot_digest") != snapshot or decision.get("candidate_snapshot_digest") != snapshot:
        return "BLOCK"
    if bundle.get("bundle_sha256") != _record_digest(bundle, "bundle_sha256"):
        return "BLOCK"
    if decision.get("protection_decision_digest") != _record_digest(decision, "protection_decision_digest"):
        return "BLOCK"
    return "CLEAR"


def scan_source_independence(paths: list[Path]) -> list[str]:
    """Static import-boundary scan -> IDENTITY-EVALUATOR-COUPLING.

    Only actual import statements are flagged; prose or registry text that merely
    mentions the implementation package is allowed.
    """
    errors: list[str] = []
    forbidden_tokens = ("cre_foundry." + "identity", "cre_foundry/identity")
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_number, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("import ") and not stripped.startswith("from "):
                continue
            for token in forbidden_tokens:
                if token in line:
                    errors.append(IDENTITY_EVALUATOR_COUPLING)
    return sorted(set(errors))


# ---------------------------------------------------------------------------
# Public evaluation entry points
# ---------------------------------------------------------------------------

def reconstruct_subject(subject: dict[str, Any]) -> dict[str, Any]:
    """Independent semantic reconstruction of the subject's identity outputs.

    Returns the evaluator-owned projection used for reconstruction checks:
    derived grain statuses, the derived fail-closed protection verdict, required
    protected coverage, and resolution semantics for alternatives.
    """
    assertions = subject.get("temporal_assertions", [])
    grain_statuses = {}
    for record in subject.get("grains", []):
        if isinstance(record.get("grain_id"), str):
            grain_statuses[record["grain_id"]] = _derived_grain_status(record, assertions)

    bundle = subject.get("protection_bundle_projection")
    root_ids = {identity for identity in bundle.get("root_protected_identities", [])} if isinstance(bundle, dict) else set()
    protected_grains = {
        record.get("grain_id")
        for record in subject.get("grains", [])
        if record.get("grain_type") == "PROTECTED_ACCOUNT"
    }
    required_aliases = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "ALIAS_OF":
            from_gid, to_gid = link.get("from_grain_id"), link.get("to_grain_id")
            if from_gid in protected_grains and to_gid in protected_grains:
                required_aliases.add(to_gid)
                required_aliases.add(from_gid)
    required_linked_locations = set()
    for link in subject.get("links", []):
        if link.get("link_type") == "PROTECTED_LINK" and isinstance(link.get("to_grain_id"), str):
            if _grain_type_of(link["to_grain_id"]) in LOCATION_GRAIN_TYPES:
                required_linked_locations.add(link["to_grain_id"])

    resolution_statuses = {
        alternative.get("alternative_id"): alternative.get("resolution_status")
        for alternative in subject.get("alternatives", [])
    }
    return {
        "grain_statuses": grain_statuses,
        "protection_verdict": _derive_protection_verdict(subject),
        "required_protected_aliases": sorted(required_aliases),
        "required_linked_locations": sorted(required_linked_locations),
        "root_protected_identities": sorted(root_ids),
        "resolution_statuses": resolution_statuses,
    }


def evaluate_subject(subject: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one in-memory subject; returns the deterministic result payload.

    Payload fields: passed, diagnostics (deduplicated, stably ordered),
    subject_sha256, evaluator_id, evaluator_version, proof_level,
    live_permissions, external_effect_occurred.
    """
    errors: list[str] = []
    if not isinstance(subject, dict):
        return _result_payload(subject, [IDENTITY_SHAPE_INVALID])

    _check_registered(subject, errors)
    if errors and any(error.startswith(IDENTITY_SCHEMA_UNREGISTERED) for error in errors):
        return _result_payload(subject, errors)

    _check_digest_bindings(subject, errors)
    errors.extend(scan_source_independence([EVALUATOR_PATH]))
    _check_live_and_ceiling(subject, errors)
    if any(
        error.startswith(code)
        for error in errors
        for code in (IDENTITY_LIVE_DENIAL, IDENTITY_EXTERNAL_EFFECT, IDENTITY_CLAIM_CEILING)
    ):
        return _result_payload(subject, errors)

    unsupported = _unsupported_types(subject)
    if unsupported:
        errors.extend(unsupported)
        return _result_payload(subject, errors)

    schema_errors = _check_schema(subject)
    if schema_errors:
        errors.extend(schema_errors)
        return _result_payload(subject, errors)

    _check_clock_formats(subject, errors)
    _check_future_evidence(subject, errors)
    _check_valid_vs_observed(subject, errors)
    _check_corporate_temporal(subject, errors)
    _check_grain_collapse(subject, errors)
    _check_suite_collapse(subject, errors)
    _check_address_as_identity(subject, errors)
    _check_address_reuse_linked(subject, errors)
    _check_parent_not_location(subject, errors)
    _check_franchise_grain(subject, errors)
    _check_multi_unit_establishment(subject, errors)
    _check_multi_establishment_property(subject, errors)
    _check_unit_separation(subject, errors)
    _check_duplicate_active_truth(subject, errors)
    _check_relocation_rewrite(subject, errors)
    _check_closure_temporal(subject, errors)
    _check_alias_supersede(subject, errors)
    _check_alternatives(subject, errors)
    _check_protection(subject, errors)
    _check_corrections(subject, errors)
    _check_lineage(subject, errors)
    _check_reconstruction(subject, errors)
    return _result_payload(subject, errors)


def _result_payload(subject: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    diagnostics = sorted(set(errors))
    subject_digest = ""
    if isinstance(subject, dict):
        try:
            subject_digest = _subject_digest(subject)
        except (TypeError, ValueError):
            subject_digest = ""
    return {
        "passed": not diagnostics,
        "diagnostics": diagnostics,
        "subject_sha256": subject_digest,
        "evaluator_id": EVALUATOR_ID,
        "evaluator_version": EVALUATOR_VERSION,
        "proof_level": subject.get("proof_level") if isinstance(subject, dict) else None,
        "live_permissions": subject.get("live_permissions") if isinstance(subject, dict) else None,
        "external_effect_occurred": subject.get("external_effect_occurred") if isinstance(subject, dict) else None,
    }


def evaluate_path(path: Path) -> tuple[list[str], dict[str, Any]]:
    """Strict-parse a subject file and evaluate it (black-box entry point)."""
    try:
        subject = strict_load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {
            "passed": False,
            "diagnostics": [IDENTITY_SHAPE_INVALID],
            "subject_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "",
            "evaluator_id": EVALUATOR_ID,
            "evaluator_version": EVALUATOR_VERSION,
            "proof_level": None,
            "live_permissions": None,
            "external_effect_occurred": None,
        }
        return payload["diagnostics"], payload
    result = evaluate_subject(subject)
    return result["diagnostics"], result


def evaluate_known_bad(fixture_path: Path) -> dict[str, Any]:
    """Evaluate one registered known-bad fixture under the house CLI contract.

    Returns exactly {"result","case_id","fixture_sha256","diagnostic"}.
    """
    registered = {
        "suite-collapse": REGISTERED_SUITE_COLLAPSE,
        "protected-alias-clear": REGISTERED_PROTECTED_ALIAS_CLEAR,
    }
    try:
        fixture = strict_load_json(fixture_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"result": "SURVIVED", "case_id": "unknown", "fixture_sha256": "", "diagnostic": "fixture not strictly parseable"}
    case_id = fixture.get("case_id")
    if not isinstance(case_id, str) or case_id not in registered or fixture.get("expected_diagnostic") != registered[case_id]:
        return {"result": "SURVIVED", "case_id": case_id if isinstance(case_id, str) else "unknown", "fixture_sha256": digest_bytes(fixture_path.read_bytes()), "diagnostic": "fixture semantics do not match the registered mutation"}
    try:
        base = build_clean_subject()
        mutated = copy.deepcopy(base)
        for op in fixture["recipe"]["ops"]:
            kind = op[0]
            if kind == "set":
                _set_path(mutated, op[1], op[2])
            elif kind == "del":
                _del_path(mutated, op[1])
            elif kind == "append":
                _get_path(mutated, op[1]).append(op[2])
            else:
                raise ValueError(f"unknown recipe op {kind}")
        mutated = rebuild_digests(mutated)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {"result": "SURVIVED", "case_id": case_id, "fixture_sha256": digest_bytes(fixture_path.read_bytes()), "diagnostic": "recipe application failed"}
    if digest_json(mutated) != digest_json(fixture.get("subject")):
        return {"result": "SURVIVED", "case_id": case_id, "fixture_sha256": digest_bytes(fixture_path.read_bytes()), "diagnostic": "embedded subject is not the recipe projection"}
    diagnostics = evaluate_subject(mutated)["diagnostics"]
    detected = diagnostics == [registered[case_id]]
    return {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": case_id,
        "fixture_sha256": digest_bytes(fixture_path.read_bytes()),
        "diagnostic": registered[case_id] if detected else (diagnostics[0] if diagnostics else "no diagnostic"),
    }


def _get_path(subject: dict[str, Any], path: list[str]) -> Any:
    node: Any = subject
    for part in path:
        node = node[part]
    return node


def _set_path(subject: dict[str, Any], path: list[str], value: Any) -> None:
    node: Any = subject
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


def _del_path(subject: dict[str, Any], path: list[str]) -> None:
    node: Any = subject
    for part in path[:-1]:
        node = node[part]
    del node[path[-1]]


def main() -> int:
    parser = argparse.ArgumentParser(description="IDENTITY-001 independent temporal identity evaluator")
    parser.add_argument("--input", type=Path, required=True, help="subject document path")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    path = args.input if args.input.is_absolute() else ROOT / args.input
    try:
        _, payload = evaluate_path(path)
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {
            "passed": False,
            "diagnostics": [IDENTITY_SHAPE_INVALID],
            "subject_sha256": "",
            "evaluator_id": EVALUATOR_ID,
            "evaluator_version": EVALUATOR_VERSION,
            "proof_level": None,
            "live_permissions": None,
            "external_effect_occurred": None,
        }
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
