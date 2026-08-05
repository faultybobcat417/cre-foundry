import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/validate_research_completion.py"
RUNNER = ROOT / "scripts/run_research_mutation.py"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("research_*.json"))


class ResearchCompletionTests(unittest.TestCase):
    def run_mutation(self, fixture: Path):
        return subprocess.run([sys.executable, str(RUNNER), "--known-bad", str(fixture)], cwd=ROOT, text=True, capture_output=True)

    def test_pristine_bundle_passes(self):
        result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual((result.returncode, result.stdout), (0, "PASS\n"))

    def test_all_registered_mutations_are_real_and_detected(self):
        self.assertGreaterEqual(len(FIXTURES), 7)
        for fixture in FIXTURES:
            with self.subTest(fixture=fixture.name):
                result = self.run_mutation(fixture)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["result"], "DETECTED")

    def test_recipe_rename_does_not_change_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            renamed = Path(temp) / "unrecognized-name.json"
            renamed.write_bytes(FIXTURES[0].read_bytes())
            result = self.run_mutation(renamed)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_registered_name_with_altered_semantics_survives(self):
        recipe = json.loads(FIXTURES[0].read_text())
        recipe["expected_before"] = "wrong-preimage"
        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / FIXTURES[0].name
            altered.write_text(json.dumps(recipe))
            result = self.run_mutation(altered)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["result"], "SURVIVED")

    def test_expected_diagnostic_is_not_echo_accepted(self):
        recipe = json.loads(FIXTURES[0].read_text())
        recipe["expected_diagnostic"] = "attacker-controlled echo"
        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / "echo.json"
            altered.write_text(json.dumps(recipe))
            result = self.run_mutation(altered)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["result"], "SURVIVED")

    def test_case_id_is_not_load_bearing(self):
        recipe = json.loads(FIXTURES[0].read_text())
        recipe["case_id"] = "renamed-case"
        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / "renamed-case.json"
            altered.write_text(json.dumps(recipe))
            result = self.run_mutation(altered)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["case_id"], "renamed-case")

    def validate_mutated_bundle(self, mutate):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "research"
            shutil.copytree(ROOT / "artifacts/research", bundle)
            mutate(bundle)
            return subprocess.run([sys.executable, str(VALIDATOR), "--bundle", str(bundle), "--json"], cwd=ROOT, text=True, capture_output=True)

    def test_duplicate_location_key_fails(self):
        def mutate(bundle):
            path = bundle / "canonical_field_map.json"
            doc = json.loads(path.read_text())
            on = next(row for row in doc["maps"] if row["source_id"] == "ON-SELECT")
            location = next(row for row in on["candidate_keys"] if row["key_id"] == "location")
            damaged = dict(location, components=["dataset_id", "licence_number_raw"])
            on["candidate_keys"].insert(0, damaged)
            path.write_text(json.dumps(doc))
        result = self.validate_mutated_bundle(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R001_DUPLICATE_ID: ON-SELECT.candidate_keys", result.stdout)

    def test_dangling_counterevidence_reference_fails(self):
        def mutate(bundle):
            path = bundle / "counterevidence_register.json"
            doc = json.loads(path.read_text())
            doc["entries"][0]["evidence_refs"] = ["NONEXISTENT"]
            path.write_text(json.dumps(doc))
        result = self.validate_mutated_bundle(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R001_DANGLING_COUNTEREVIDENCE_REF", result.stdout)

    def test_witness_tampering_fails(self):
        def mutate(bundle):
            path = bundle / "source_reproduction_report.json"
            doc = json.loads(path.read_text())
            doc["witnesses"][0]["reported_distinct_addresses_for_witness_licence"] = 2
            path.write_text(json.dumps(doc))
        result = self.validate_mutated_bundle(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R001_ON_WITNESS_INVALID", result.stdout)

    def test_raw_manifest_self_rebind_without_bundle_rebind_fails(self):
        def mutate(bundle):
            import hashlib
            path = bundle / "raw/on_select_package.json"
            path.write_text(path.read_text().replace("Select Licence", "Altered Licence", 1))
            manifest_path = bundle / "raw/manifest.json"
            manifest = json.loads(manifest_path.read_text())
            entry = next(row for row in manifest["evidence"] if row["evidence_id"] == "ON-SELECT-PACKAGE")
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
        result = self.validate_mutated_bundle(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R001_BUNDLE_HASH_MISMATCH: artifacts/research/raw/manifest.json", result.stdout)


if __name__ == "__main__":
    unittest.main()
