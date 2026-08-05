"""Bounded mutation and reconstruction suite for the IDENTITY-001 evaluator.

Every subject is built in memory from :func:`build_clean_subject`, a
deterministic construction helper owned by the independent evaluator (never
importing ``src.cre_foundry.identity``).  Each registered mutation and each
stable foundational diagnostic is asserted to produce exactly its frozen
registered code, and the clean subject must pass with zero diagnostics.  The
suite is deterministic, bounded, and never touches a live action, gate, or
permission.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:
    from evals.public.temporal_identity_evaluator import (
        build_clean_subject, rebuild_digests, rebind_subject_digests,
        reconstruct_subject, evaluate_subject, evaluate_path, evaluate_known_bad,
        scan_source_independence, strict_load_json, canonical_json_bytes,
        digest_json, EVALUATOR_ID, EVALUATOR_VERSION, EXECUTION_SCOPE,
        CONTRACT_PATH, SCHEMA_PATH, IDENTITY_SHAPE_INVALID,
        IDENTITY_SCHEMA_UNREGISTERED, IDENTITY_DIGEST_BINDING,
        IDENTITY_UNSUPPORTED_TYPE, IDENTITY_SCHEMA_FAILURE, IDENTITY_LIVE_DENIAL,
        IDENTITY_EXTERNAL_EFFECT, IDENTITY_CLAIM_CEILING,
        IDENTITY_GRAIN_COLLAPSE, REGISTERED_SUITE_COLLAPSE,
        IDENTITY_ADDRESS_AS_IDENTITY, IDENTITY_ADDRESS_REUSE_LINKED,
        IDENTITY_RELOCATION_REWRITE, IDENTITY_CLOSURE_TEMPORAL,
        IDENTITY_UNIT_SEPARATION, IDENTITY_MULTI_UNIT_ESTABLISHMENT,
        IDENTITY_MULTI_ESTABLISHMENT_PROPERTY, IDENTITY_FRANCHISE_GRAIN,
        IDENTITY_PARENT_NOT_LOCATION, IDENTITY_CORPORATE_TEMPORAL,
        IDENTITY_ALIAS_SUPERSEDE, IDENTITY_AMBIGUITY_BLOCKED,
        IDENTITY_CONFLICT_BLOCKED, IDENTITY_FUTURE_EVIDENCE,
        IDENTITY_STALE_BUNDLE_CLEAR, IDENTITY_INCOMPLETE_BUNDLE_CLEAR,
        REGISTERED_PROTECTED_ALIAS_CLEAR, IDENTITY_PROTECTION_DIGEST_DRIFT,
        IDENTITY_MANUAL_UNKNOWN_CLEAR, IDENTITY_MANUAL_HISTORY_REWRITE,
        IDENTITY_CORRECTION_DELETION, IDENTITY_LINEAGE_BINDING,
        IDENTITY_DUPLICATE_ACTIVE_TRUTH, IDENTITY_RECONSTRUCTION_MISMATCH,
        IDENTITY_VALID_VS_OBSERVED, IDENTITY_EVALUATOR_COUPLING,
        _build_grain, _build_assertion, _build_link, _evidence,
    )
except ModuleNotFoundError:  # unittest discovery adds evals/public directly
    from temporal_identity_evaluator import (
        build_clean_subject, rebuild_digests, rebind_subject_digests,
        reconstruct_subject, evaluate_subject, evaluate_path, evaluate_known_bad,
        scan_source_independence, strict_load_json, canonical_json_bytes,
        digest_json, EVALUATOR_ID, EVALUATOR_VERSION, EXECUTION_SCOPE,
        CONTRACT_PATH, SCHEMA_PATH, IDENTITY_SHAPE_INVALID,
        IDENTITY_SCHEMA_UNREGISTERED, IDENTITY_DIGEST_BINDING,
        IDENTITY_UNSUPPORTED_TYPE, IDENTITY_SCHEMA_FAILURE, IDENTITY_LIVE_DENIAL,
        IDENTITY_EXTERNAL_EFFECT, IDENTITY_CLAIM_CEILING,
        IDENTITY_GRAIN_COLLAPSE, REGISTERED_SUITE_COLLAPSE,
        IDENTITY_ADDRESS_AS_IDENTITY, IDENTITY_ADDRESS_REUSE_LINKED,
        IDENTITY_RELOCATION_REWRITE, IDENTITY_CLOSURE_TEMPORAL,
        IDENTITY_UNIT_SEPARATION, IDENTITY_MULTI_UNIT_ESTABLISHMENT,
        IDENTITY_MULTI_ESTABLISHMENT_PROPERTY, IDENTITY_FRANCHISE_GRAIN,
        IDENTITY_PARENT_NOT_LOCATION, IDENTITY_CORPORATE_TEMPORAL,
        IDENTITY_ALIAS_SUPERSEDE, IDENTITY_AMBIGUITY_BLOCKED,
        IDENTITY_CONFLICT_BLOCKED, IDENTITY_FUTURE_EVIDENCE,
        IDENTITY_STALE_BUNDLE_CLEAR, IDENTITY_INCOMPLETE_BUNDLE_CLEAR,
        REGISTERED_PROTECTED_ALIAS_CLEAR, IDENTITY_PROTECTION_DIGEST_DRIFT,
        IDENTITY_MANUAL_UNKNOWN_CLEAR, IDENTITY_MANUAL_HISTORY_REWRITE,
        IDENTITY_CORRECTION_DELETION, IDENTITY_LINEAGE_BINDING,
        IDENTITY_DUPLICATE_ACTIVE_TRUTH, IDENTITY_RECONSTRUCTION_MISMATCH,
        IDENTITY_VALID_VS_OBSERVED, IDENTITY_EVALUATOR_COUPLING,
        _build_grain, _build_assertion, _build_link, _evidence,
    )

SCHEMA = json.loads(SCHEMA_PATH.read_text())


def _ev(subject: dict) -> list[str]:
    return evaluate_subject(subject)["diagnostics"]


def _by_id(subject: dict, prefix: str) -> dict:
    for grain in subject["grains"]:
        if grain["grain_id"].startswith(prefix + ":"):
            return grain
    raise AssertionError(f"no grain with prefix {prefix}")


def _link(subject: dict, link_id: str) -> dict:
    for link in subject["links"]:
        if link["link_id"] == link_id:
            return link
    raise AssertionError(f"no link {link_id}")


class TestCleanSubject(unittest.TestCase):
    def test_clean_subject_passes_with_zero_diagnostics(self):
        subject = build_clean_subject()
        result = evaluate_subject(subject)
        self.assertTrue(result["passed"])
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(result["evaluator_id"], EVALUATOR_ID)
        self.assertEqual(result["evaluator_version"], EVALUATOR_VERSION)

    def test_clean_subject_is_deterministic(self):
        first = build_clean_subject()
        second = build_clean_subject()
        self.assertEqual(first["subject_sha256"], second["subject_sha256"])
        self.assertEqual(digest_json(first), digest_json(second))

    def test_clean_subject_schema_conformant(self):
        from jsonschema import Draft202012Validator, FormatChecker
        validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(build_clean_subject())), [])

    def test_clean_subject_binds_schema_and_contract_digests(self):
        subject = build_clean_subject()
        self.assertEqual(subject["schema_sha256"], hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest())
        self.assertEqual(subject["contract_sha256"], hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest())
        receipt = subject["replay_receipt"]
        self.assertEqual(receipt["schema_sha256"], subject["schema_sha256"])
        self.assertEqual(receipt["contract_sha256"], subject["contract_sha256"])
        self.assertEqual(receipt["subject_sha256"], subject["subject_sha256"])
        self.assertEqual(receipt["canonical_serialization"], "UTF8_CANONICAL_JSON_SORTED_KEYS")

    def test_clean_subject_execution_scope_and_ceiling(self):
        subject = build_clean_subject()
        self.assertEqual(subject["execution_scope"], EXECUTION_SCOPE)
        self.assertEqual(subject["proof_level"], 4)
        self.assertIs(subject["live_permissions"], False)
        self.assertIs(subject["external_effect_occurred"], False)
        claims = subject["claims_and_limitations"]
        self.assertEqual(claims["claim_kind"], EXECUTION_SCOPE)
        self.assertEqual(claims["proof_level"], 4)

    def test_reconstruction_matches_clean_subject(self):
        subject = build_clean_subject()
        rebuilt = reconstruct_subject(subject)
        self.assertEqual(rebuilt["protection_verdict"], "CLEAR")
        self.assertEqual(len(rebuilt["grain_statuses"]), len(subject["grains"]))
        self.assertTrue(all(status == "ACTIVE" for status in rebuilt["grain_statuses"].values()))
        self.assertEqual(rebuilt["required_protected_aliases"],
                         ["PROTECTED_ACCOUNT:pa-1", "PROTECTED_ACCOUNT:pa-2"])
        self.assertEqual(rebuilt["required_linked_locations"], ["PHYSICAL_LOCATION:pl-1"])
        self.assertEqual(rebuilt["root_protected_identities"], ["PROTECTED_ACCOUNT:pa-1"])
        self.assertEqual(rebuilt["resolution_statuses"], {})

    def test_evaluate_subject_never_mutates_input(self):
        subject = build_clean_subject()
        before = digest_json(subject)
        evaluate_subject(subject)
        self.assertEqual(digest_json(subject), before)

    def test_canonical_serialization_is_sorted_utf8(self):
        encoded = canonical_json_bytes({"b": 1, "a": [2, 1]})
        self.assertEqual(encoded, b'{"a":[2,1],"b":1}')

    def test_strict_load_json_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "dup.json"
            path.write_text('{"x": 1, "x": 2}')
            with self.assertRaises(ValueError):
                strict_load_json(path)


class TestStableDiagnostics(unittest.TestCase):
    def test_shape_invalid_non_dict_subject(self):
        self.assertEqual(_ev("not-a-subject"), [IDENTITY_SHAPE_INVALID])

    def test_shape_invalid_duplicate_key_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "dup.json"
            path.write_text('{"y": 1, "y": 2}')
            diagnostics, _ = evaluate_path(path)
        self.assertEqual(diagnostics, [IDENTITY_SHAPE_INVALID])

    def test_schema_unregistered_document_kind(self):
        subject = build_clean_subject()
        subject["document_kind"] = "SOMETHING_ELSE"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_SCHEMA_UNREGISTERED])

    def test_digest_binding_stale_subject_sha256(self):
        subject = build_clean_subject()
        subject["grains"][0]["grain_status"] = "CLOSED"
        result = evaluate_subject(subject)
        self.assertIn(IDENTITY_DIGEST_BINDING, result["diagnostics"])
        self.assertFalse(result["passed"])

    def test_unsupported_link_type(self):
        subject = build_clean_subject()
        subject["links"][0]["link_type"] = "WARP"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_UNSUPPORTED_TYPE])

    def test_schema_failure_unknown_nested_field(self):
        subject = build_clean_subject()
        subject["grains"][0]["nonsense_field"] = 1
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_SCHEMA_FAILURE])

    def test_live_denial(self):
        subject = build_clean_subject()
        subject["live_permissions"] = True
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_LIVE_DENIAL])

    def test_external_effect_recorded(self):
        subject = build_clean_subject()
        subject["external_effect_occurred"] = True
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_EXTERNAL_EFFECT])

    def test_claim_ceiling_proof_level_5(self):
        subject = build_clean_subject()
        subject["proof_level"] = 5
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_CLAIM_CEILING])


class TestRegisteredMutations(unittest.TestCase):
    def test_01_grain_collapse(self):
        subject = build_clean_subject()
        _by_id(subject, "OPERATING_BUSINESS")["grain_type"] = "ESTABLISHMENT"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_GRAIN_COLLAPSE])

    def test_02_suite_collapse(self):
        subject = build_clean_subject()
        subject["links"].append(_build_link(
            "LINK:est-loc-2b", "LOCATED_AT", "ESTABLISHMENT:est-2", "UNIT:u-101",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [REGISTERED_SUITE_COLLAPSE])

    def test_03_address_as_identity(self):
        subject = build_clean_subject()
        subject["links"].append(_build_link(
            "LINK:addr-owns", "OWNS", "ADDRESS:addr-1", "PARCEL:parcel-1",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_ADDRESS_AS_IDENTITY])

    def test_04_address_reuse_linked(self):
        subject = build_clean_subject()
        _link(subject, "LINK:est-loc-1")["to_grain_id"] = "ADDRESS:addr-1"
        _link(subject, "LINK:est-loc-2")["to_grain_id"] = "ADDRESS:addr-1"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_ADDRESS_REUSE_LINKED])

    def test_05_relocation_rewrite(self):
        subject = build_clean_subject()
        subject["grains"].append(_build_grain("OPERATING_BUSINESS:biz-rel", "OPERATING_BUSINESS"))
        subject["links"].append(_build_link(
            "LINK:rel-orig", "LOCATED_AT", "OPERATING_BUSINESS:biz-rel", "PHYSICAL_LOCATION:pl-1",
            effective_from="2024-05-01T00:00:00Z", effective_to="2024-05-15T00:00:00Z",
        ))
        subject["links"].append(_build_link(
            "LINK:rel-now", "LOCATED_AT", "OPERATING_BUSINESS:biz-rel", "PHYSICAL_LOCATION:pl-1",
            effective_from="2024-05-16T00:00:00Z", effective_to=None,
        ))
        subject["temporal_assertions"].append(_build_assertion(
            "ASSERT:rel-1", "OPERATING_BUSINESS:biz-rel", "RELOCATED",
            observed="2024-05-16T00:00:00Z",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [])
        subject["links"] = [link for link in subject["links"] if link["link_id"] != "LINK:rel-orig"]
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_RELOCATION_REWRITE])

    def test_06_closure_temporal(self):
        subject = build_clean_subject()
        _by_id(subject, "ESTABLISHMENT")["grain_status"] = "CLOSED"
        subject["temporal_assertions"].append(_build_assertion(
            "ASSERT:close-1", "ESTABLISHMENT:est-1", "CLOSED_PERMANENT",
            observed="2024-05-20T00:00:00Z", effective_to="2024-05-25T00:00:00Z",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_CLOSURE_TEMPORAL])

    def test_07_unit_separation(self):
        subject = build_clean_subject()
        duplicate = copy.deepcopy(_by_id(subject, "UNIT"))
        duplicate["grain_id"] = "UNIT:u-101b"
        subject["grains"].append(duplicate)
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_UNIT_SEPARATION])

    def test_08_multi_unit_establishment(self):
        subject = build_clean_subject()
        subject["grains"].append(_build_grain("PHYSICAL_LOCATION:pl-2", "PHYSICAL_LOCATION"))
        _link(subject, "LINK:u-pl-2")["to_grain_id"] = "PHYSICAL_LOCATION:pl-2"
        subject["links"].append(_build_link(
            "LINK:est-loc-1b", "LOCATED_AT", "ESTABLISHMENT:est-1", "UNIT:u-102",
        ))
        _link(subject, "LINK:est-loc-2")["to_grain_id"] = "PHYSICAL_LOCATION:pl-1"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_MULTI_UNIT_ESTABLISHMENT])

    def test_09_multi_establishment_property(self):
        subject = build_clean_subject()
        _link(subject, "LINK:est-loc-1")["to_grain_id"] = "PROPERTY:prop-1"
        _link(subject, "LINK:est-loc-2")["to_grain_id"] = "PROPERTY:prop-1"
        _link(subject, "LINK:est-loc-2")["evidence_refs"] = copy.deepcopy(_link(subject, "LINK:est-loc-1")["evidence_refs"])
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_MULTI_ESTABLISHMENT_PROPERTY])

    def test_10_franchise_grain(self):
        subject = build_clean_subject()
        subject["links"].append(_build_link(
            "LINK:fsys-loc", "LOCATED_AT", "FRANCHISE_SYSTEM:fsys-1", "UNIT:u-101",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_FRANCHISE_GRAIN])

    def test_11_parent_not_location(self):
        subject = build_clean_subject()
        subject["links"].append(_build_link(
            "LINK:parent-loc", "LOCATED_AT", "OPERATING_BUSINESS:biz-1", "PARENT:parent-1",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_PARENT_NOT_LOCATION])

    def test_12_corporate_temporal(self):
        subject = build_clean_subject()
        _link(subject, "LINK:sub-legal")["valid_from"] = "2024-01-01T00:00:00Z"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_CORPORATE_TEMPORAL])

    def test_13_alias_supersede(self):
        subject = build_clean_subject()
        subject["temporal_assertions"].append(_build_assertion(
            "ASSERT:rename-1", "BRAND:brand-1", "RENAMED",
            observed="2024-05-20T00:00:00Z",
        ))
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_ALIAS_SUPERSEDE])

    def _alternative(self, aid, reference, rank, status):
        return {
            "alternative_id": aid,
            "resolution_kind": "LINK",
            "resolution_reference": reference,
            "evidence_refs": [_evidence("OBS:" + aid)],
            "deterministic_rank": rank,
            "rank_basis": "evidence-weight",
            "rank_version": "1.0.0",
            "resolution_status": status,
        }

    def test_14_ambiguity_blocked(self):
        subject = build_clean_subject()
        subject["alternatives"] = [
            self._alternative("ALT:a-1", "ESTABLISHMENT:est-1", 1, "AMBIGUOUS"),
            self._alternative("ALT:a-2", "ESTABLISHMENT:est-1", 2, "AMBIGUOUS"),
        ]
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_AMBIGUITY_BLOCKED])

    def test_15_conflict_blocked(self):
        subject = build_clean_subject()
        subject["alternatives"] = [
            self._alternative("ALT:c-1", "ESTABLISHMENT:est-1", 1, "CONFLICTED"),
            self._alternative("ALT:c-2", "ESTABLISHMENT:est-1", 2, "SUPPORTED"),
        ]
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_CONFLICT_BLOCKED])

    def test_16_future_evidence(self):
        subject = build_clean_subject()
        _link(subject, "LINK:est-loc-1")["available_at"] = "2024-07-01T00:00:00Z"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_FUTURE_EVIDENCE])

    def test_17_stale_bundle_clear(self):
        subject = build_clean_subject()
        subject["protection_bundle_projection"]["valid_to"] = "2024-05-15T00:00:00Z"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_STALE_BUNDLE_CLEAR])

    def test_18_incomplete_bundle_clear(self):
        subject = build_clean_subject()
        subject["protection_bundle_projection"]["bundle_completeness"] = "INCOMPLETE"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_INCOMPLETE_BUNDLE_CLEAR])

    def test_19_protected_alias_clear(self):
        subject = build_clean_subject()
        subject["protection_bundle_projection"]["aliases"] = []
        subject["protection_bundle_projection"]["expansion_paths"] = ["EXPATH:pa-1-est-1", "EXPATH:pa-1-pl-1"]
        subject["protection_expansion"] = [
            path for path in subject["protection_expansion"]
            if path["path_id"] != "EXPATH:pa-1-pa-2"
        ]
        self.assertEqual(_ev(rebuild_digests(subject)), [REGISTERED_PROTECTED_ALIAS_CLEAR])

    def test_20_protection_digest_drift(self):
        subject = build_clean_subject()
        subject = rebuild_digests(subject)
        subject["protection_expansion"] = list(reversed(subject["protection_expansion"]))
        subject = rebind_subject_digests(subject)
        self.assertEqual(_ev(subject), [IDENTITY_PROTECTION_DIGEST_DRIFT])

    def test_21_manual_unknown_clear(self):
        subject = build_clean_subject()
        subject["protection_decision"]["manual_review_required"] = True
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_MANUAL_UNKNOWN_CLEAR])

    def test_22_manual_history_rewrite(self):
        subject = build_clean_subject()
        subject["corrections"].append({
            "correction_id": "CORR:c-1",
            "superseded_record_id": "LEGAL_ENTITY:legal-1",
            "corrected_grain_id": "LEGAL_ENTITY:legal-1",
            "correction_at": "2024-05-25T00:00:00Z",
            "evidence_refs": [_evidence("OBS:c-1")],
        })
        subject = rebuild_digests(subject)
        _by_id(subject, "LEGAL_ENTITY")["grain_status"] = "SUPERSEDED"
        subject = rebuild_digests(subject, preserve_predecessors=True)
        self.assertEqual(_ev(subject), [IDENTITY_MANUAL_HISTORY_REWRITE])

    def test_23_correction_deletion(self):
        subject = build_clean_subject()
        subject["corrections"].append({
            "correction_id": "CORR:c-2",
            "superseded_record_id": "BRAND:brand-1",
            "corrected_grain_id": "BRAND:brand-1",
            "correction_at": "2024-05-25T00:00:00Z",
            "evidence_refs": [_evidence("OBS:c-2")],
        })
        subject = rebuild_digests(subject)
        subject["grains"] = [grain for grain in subject["grains"] if grain["grain_id"] != "BRAND:brand-1"]
        subject["links"] = [
            link for link in subject["links"]
            if link["link_id"] not in ("LINK:brand-sys", "LINK:own-biz-brand")
        ]
        subject = rebuild_digests(subject)
        self.assertEqual(_ev(subject), [IDENTITY_CORRECTION_DELETION])

    def test_24_lineage_binding(self):
        subject = build_clean_subject()
        subject = rebuild_digests(subject)
        subject["lineage"]["nodes"][0]["node_digest"] = "f" * 64
        subject = rebind_subject_digests(subject)
        self.assertEqual(_ev(subject), [IDENTITY_LINEAGE_BINDING])

    def test_25_duplicate_active_truth(self):
        subject = build_clean_subject()
        duplicate = copy.deepcopy(_by_id(subject, "OPERATING_BUSINESS"))
        duplicate["grain_id"] = "OPERATING_BUSINESS:biz-dup"
        subject["grains"].append(duplicate)
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_DUPLICATE_ACTIVE_TRUTH])

    def test_26_reconstruction_mismatch(self):
        subject = build_clean_subject()
        _by_id(subject, "ESTABLISHMENT")["grain_status"] = "CLOSED"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_RECONSTRUCTION_MISMATCH])

    def test_27_valid_vs_observed(self):
        subject = build_clean_subject()
        _by_id(subject, "UNIT")["valid_to"] = "2024-01-01T00:00:00Z"
        self.assertEqual(_ev(rebuild_digests(subject)), [IDENTITY_VALID_VS_OBSERVED])

    def test_28_evaluator_coupling_scan(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.py"
            bad.write_text("import src.cre_foundry.identity\n")
            self.assertEqual(scan_source_independence([bad]), [IDENTITY_EVALUATOR_COUPLING])

    def test_evaluator_coupling_scan_allows_prose_mention(self):
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "good.py"
            good.write_text("# prose: never import src.cre_foundry.identity\nx = 1\n")
            self.assertEqual(scan_source_independence([good]), [])


class TestIndependenceAndReconstruction(unittest.TestCase):
    def test_evaluator_does_not_import_material_implementation(self):
        source = (ROOT / "evals/public/temporal_identity_evaluator.py").read_text()
        for line in source.splitlines():
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                self.assertNotIn("src.cre_foundry.identity", line)
                self.assertNotIn("cre_foundry.identity", line)

    def test_own_source_scan_is_clean(self):
        self.assertEqual(scan_source_independence([ROOT / "evals/public/temporal_identity_evaluator.py"]), [])

    def test_coordinated_rehash_still_detected(self):
        subject = build_clean_subject()
        _by_id(subject, "ESTABLISHMENT")["grain_status"] = "CLOSED"
        subject = rebuild_digests(subject)
        result = evaluate_subject(subject)
        self.assertIn(IDENTITY_RECONSTRUCTION_MISMATCH, result["diagnostics"])
        self.assertFalse(result["passed"])

    def test_coordinated_rehash_around_bad_clear_detected(self):
        subject = build_clean_subject()
        subject["protection_bundle_projection"]["bundle_completeness"] = "INCOMPLETE"
        subject["protection_decision"]["result_state"] = "CLEAR"
        subject = rebuild_digests(subject)
        result = evaluate_subject(subject)
        self.assertIn(IDENTITY_INCOMPLETE_BUNDLE_CLEAR, result["diagnostics"])
        self.assertFalse(result["passed"])

    def test_diagnostics_are_sorted_deduplicated(self):
        subject = build_clean_subject()
        subject["external_effect_occurred"] = True
        subject["proof_level"] = 5
        subject["live_permissions"] = True
        diagnostics = _ev(rebuild_digests(subject))
        self.assertEqual(diagnostics, sorted(set(diagnostics)))
        self.assertEqual(
            diagnostics,
            [IDENTITY_CLAIM_CEILING, IDENTITY_EXTERNAL_EFFECT, IDENTITY_LIVE_DENIAL],
        )

    def test_evaluation_is_deterministic_across_calls(self):
        subject = build_clean_subject()
        first = evaluate_subject(subject)
        second = evaluate_subject(subject)
        self.assertEqual(first, second)


class TestKnownBadFixtures(unittest.TestCase):
    def test_suite_collapse_fixture_detected(self):
        path = ROOT / "evals/known_bad/frontier/identity_suite_collapse.json"
        result = evaluate_known_bad(path)
        self.assertEqual(result["result"], "DETECTED")
        self.assertEqual(result["case_id"], "suite-collapse")
        self.assertEqual(result["diagnostic"], REGISTERED_SUITE_COLLAPSE)

    def test_protected_alias_fixture_detected(self):
        path = ROOT / "evals/known_bad/frontier/identity_protected_alias.json"
        result = evaluate_known_bad(path)
        self.assertEqual(result["result"], "DETECTED")
        self.assertEqual(result["case_id"], "protected-alias-clear")
        self.assertEqual(result["diagnostic"], REGISTERED_PROTECTED_ALIAS_CLEAR)

    def test_known_bad_is_stable_across_replays(self):
        path = ROOT / "evals/known_bad/frontier/identity_suite_collapse.json"
        first = evaluate_known_bad(path)
        second = evaluate_known_bad(path)
        self.assertEqual(first, second)

    def test_altered_expected_diagnostic_rejected(self):
        path = ROOT / "evals/known_bad/frontier/identity_suite_collapse.json"
        fixture = json.loads(path.read_text())
        fixture["expected_diagnostic"] = "registered mutation detected: something-else"
        with tempfile.TemporaryDirectory() as td:
            tampered = Path(td) / "tampered.json"
            tampered.write_text(json.dumps(fixture))
            result = evaluate_known_bad(tampered)
        self.assertEqual(result["result"], "SURVIVED")

    def test_altered_embedded_subject_without_binding_rejected(self):
        path = ROOT / "evals/known_bad/frontier/identity_protected_alias.json"
        fixture = json.loads(path.read_text())
        fixture["subject"]["protection_bundle_projection"]["aliases"] = ["PROTECTED_ACCOUNT:pa-2"]
        with tempfile.TemporaryDirectory() as td:
            tampered = Path(td) / "tampered.json"
            tampered.write_text(json.dumps(fixture))
            result = evaluate_known_bad(tampered)
        self.assertEqual(result["result"], "SURVIVED")

    def test_unknown_case_id_rejected(self):
        path = ROOT / "evals/known_bad/frontier/identity_suite_collapse.json"
        fixture = json.loads(path.read_text())
        fixture["case_id"] = "not-a-registered-mutation"
        with tempfile.TemporaryDirectory() as td:
            tampered = Path(td) / "tampered.json"
            tampered.write_text(json.dumps(fixture))
            result = evaluate_known_bad(tampered)
        self.assertEqual(result["result"], "SURVIVED")


if __name__ == "__main__":
    unittest.main()
