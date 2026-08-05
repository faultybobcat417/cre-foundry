import copy
import json
import random
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cre_foundry.contracts.thin_slice import build_candidate, build_fixture_observations, build_spine, build_spine_from_observations, canonical_bytes
try:
    from evals.public.contract_spine_evaluator import validate_spine
except ModuleNotFoundError:
    from contract_spine_evaluator import validate_spine


class ContractSpineTests(unittest.TestCase):
    def test_schemas_are_valid_and_strict(self):
        for name in ["thin_slice_observation.schema.json", "thin_slice_candidate.schema.json"]:
            schema = json.loads((ROOT / "contracts" / name).read_text())
            Draft202012Validator.check_schema(schema)
        observation = build_fixture_observations(1)[0]
        candidate = build_candidate(observation, [])
        observation["unexpected"] = True
        candidate["identity"]["unexpected"] = True
        self.assertTrue(list(Draft202012Validator(json.loads((ROOT / "contracts/thin_slice_observation.schema.json").read_text())).iter_errors(observation)))
        self.assertTrue(list(Draft202012Validator(json.loads((ROOT / "contracts/thin_slice_candidate.schema.json").read_text())).iter_errors(candidate)))

    def test_focal_observation_and_exact_ten_replay(self):
        first = build_spine()
        second = build_spine()
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        self.assertEqual([], validate_spine(first, check_replay=True))
        focal = first["proof"]["focal_observation_id"]
        candidate = next(row for row in first["candidates"] if row["lineage"]["observation_id"] == focal)
        self.assertEqual(first["source_snapshot_sha256"], candidate["lineage"]["source_snapshot_sha256"])
        self.assertEqual("ISSUE", first["math_decision"]["decision"])
        self.assertEqual(10, len(first["math_decision"]["selected"]))
        one_observation = build_spine(1)
        self.assertEqual([], validate_spine(one_observation))
        self.assertEqual("ABSTAIN_NO_VALID_TEN", one_observation["math_decision"]["decision"])

    def test_source_order_does_not_change_transform_set(self):
        observations = build_fixture_observations(10)
        forward = sorted((build_candidate(row, []) for row in observations), key=lambda row: row["candidate_id"])
        random.Random(20260801).shuffle(observations)
        reverse = sorted((build_candidate(row, []) for row in observations), key=lambda row: row["candidate_id"])
        self.assertEqual(canonical_bytes(forward), canonical_bytes(reverse))

    def test_registered_mutations_fail_exactly(self):
        mutations = []
        future = copy.deepcopy(build_spine())
        future["observations"][0]["clocks"]["available_at"] = "2026-08-01T00:00:00Z"
        mutations.append((future, "CONTRACT-STAGE1-FUTURE-OBSERVATION"))
        grain = copy.deepcopy(build_spine())
        grain["candidates"][0]["identity"]["grain_ids"]["brand_id"] = grain["candidates"][0]["identity"]["physical_location_id"]
        mutations.append((grain, "CONTRACT-IDENTITY-GRAIN-COLLAPSE"))
        alias = copy.deepcopy(build_spine())
        alias["candidates"][0]["protection"]["candidate_tokens"] = alias["candidates"][0]["protection"]["candidate_tokens"][:-1]
        mutations.append((alias, "CONTRACT-PROTECTED-ALIAS-OMITTED"))
        digest = copy.deepcopy(build_spine())
        digest["replay_receipt"]["math_decision_sha256"] = "0" * 64
        mutations.append((digest, "CONTRACT-DECISION-DIGEST-MISMATCH"))
        version = copy.deepcopy(build_spine())
        version["observations"][0]["schema_version"] = "9.9.9"
        mutations.append((version, "CONTRACT-UNREGISTERED-SCHEMA-VERSION:THIN_SLICE_OBSERVATION:9.9.9"))
        for subject, expected in mutations:
            with self.subTest(expected=expected):
                self.assertEqual([expected], validate_spine(subject))

    def test_rebound_manifest_and_semantic_survivors_are_rejected(self):
        mutations = []
        claim = copy.deepcopy(build_spine())
        claim["proof"]["level"] = 9
        claim["proof"]["claim"] = "production proven"
        mutations.append(claim)
        scope = copy.deepcopy(build_spine())
        scope["decision_scope"] = "LIVE"
        mutations.append(scope)
        transition = copy.deepcopy(build_spine())
        transition["supported_version_transition"]["candidate"] = "9.9.9"
        mutations.append(transition)
        missing_binding = copy.deepcopy(build_spine())
        del missing_binding["schema_bindings"]["candidate"]
        mutations.append(missing_binding)
        source = copy.deepcopy(build_spine())
        source["observations"][0]["origin"]["source_registry_sha256"] = "0" * 64
        mutations.append(source)
        source_kind = copy.deepcopy(build_spine())
        source_kind["observations"][0]["origin"]["source_definition_id"] = "TOR-COA"
        mutations.append(source_kind)
        publication = copy.deepcopy(build_spine())
        publication["observations"][0]["clocks"]["published"] = {"state": "KNOWN", "at": "2026-08-01T00:00:00Z", "raw": "future"}
        mutations.append(publication)
        grains = copy.deepcopy(build_spine())
        grains["candidates"][0]["identity"]["grain_ids"]["brand_id"] = grains["candidates"][0]["identity"]["grain_ids"]["operating_business_id"]
        mutations.append(grains)
        protection = copy.deepcopy(build_spine())
        protection["candidates"][0]["protection"]["bundle_complete"] = False
        mutations.append(protection)
        ordering = copy.deepcopy(build_spine())
        ordering["observations"][0]["normalized_alias_tokens"].reverse()
        mutations.append(ordering)
        receipt = copy.deepcopy(build_spine())
        receipt["replay_receipt"]["result"] = "ABSTAIN_NO_VALID_TEN"
        mutations.append(receipt)
        bundle = copy.deepcopy(build_spine())
        bundle["protected_bundle"]["bundle_id"] = "UNREGISTERED"
        mutations.append(bundle)
        cutoff = copy.deepcopy(build_spine())
        cutoff["observations"][0]["clocks"]["stage1_cutoff"] = "2027-01-01T00:00:00Z"
        mutations.append(cutoff)
        rebound_observations = copy.deepcopy(build_spine()["observations"])
        rebound_observations[0]["clocks"].update({
            "retrieved_at": "2026-08-01T00:00:00Z",
            "observed_at": "2026-08-01T00:01:00Z",
            "ingested_at": "2026-08-01T00:02:00Z",
            "validation_completed_at": "2026-08-01T00:03:00Z",
            "available_at": "2026-08-01T00:03:00Z",
            "stage1_cutoff": "2027-01-01T00:00:00Z",
        })
        mutations.append(build_spine_from_observations(rebound_observations))
        kind = copy.deepcopy(build_spine())
        kind["document_kind"] = "UNKNOWN_SPINE"
        mutations.append(kind)
        abstain_receipt = build_spine(1)
        abstain_receipt["replay_receipt"]["selected_candidate_ids"] = ["CAND:FORGED"]
        mutations.append(abstain_receipt)
        for subject in mutations:
            with self.subTest(subject=subject):
                self.assertTrue(validate_spine(subject, check_replay=True))


if __name__ == "__main__":
    unittest.main()
