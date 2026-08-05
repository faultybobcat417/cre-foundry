"""House tests for the ECONOMICS-001 material economics engine.

These tests are builder-side and import both the material implementation and the
frozen independent evaluator.  They prove byte-agreement, clean-subject
acceptance, registered-mutation detection by both implementations, and the
deterministic economics machinery.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from cre_foundry.economics import engine as material
from scripts import validate_economics_ecv as frozen


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class EconomicsMaterialContractTests(unittest.TestCase):
    def test_render_is_byte_identical_to_frozen_evaluator(self):
        self.assertEqual(
            _canonical(material.render_subject()),
            _canonical(frozen.build_subject()),
        )

    def test_render_is_deterministic(self):
        self.assertEqual(_canonical(material.render_subject()), _canonical(material.render_subject()))

    def test_clean_subject_accepted_by_both(self):
        subject = material.render_subject()
        self.assertEqual(frozen.diagnostics(copy.deepcopy(subject)), [])
        self.assertEqual(material.material_checks(copy.deepcopy(subject)), [])

    def test_registered_mutations_detected_by_both(self):
        registered = {
            "omitted_costs": "ECONOMICS-OMITTED-COSTS",
            "modeled_as_realized": "ECONOMICS-MODELED-AS-REALIZED",
        }
        for mutation_id, expected in registered.items():
            with self.subTest(mutation_id=mutation_id):
                subject = material.render_subject()
                frozen.apply_mutation(subject, mutation_id)
                self.assertIn(expected, frozen.diagnostics(copy.deepcopy(subject)))
                self.assertIn(expected, material.material_checks(copy.deepcopy(subject)))

    def test_material_never_imports_frozen_evaluator(self):
        import ast

        source = (ROOT / "src/cre_foundry/economics/engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                self.assertFalse(
                    any("validate_economics_ecv" in name for name in names),
                    f"material imports frozen evaluator: {names}",
                )

    def test_economic_machinery_is_deterministic(self):
        subject = material.render_subject()
        self.assertEqual(
            material.expected_net_value(copy.deepcopy(subject)),
            material.expected_net_value(copy.deepcopy(subject)),
        )
        self.assertEqual(material.sensitivity(copy.deepcopy(subject))["total_cost"], -1.0)
        self.assertEqual(material.downside_fallback(copy.deepcopy(subject))["decision"], "ABSTAIN")


if __name__ == "__main__":
    unittest.main()