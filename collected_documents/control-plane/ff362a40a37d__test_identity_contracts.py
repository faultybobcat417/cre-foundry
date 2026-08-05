"""Bounded material-layer tests for the IDENTITY-001 identity graph.

These tests exercise the independent material implementation in
``src.cre_foundry.identity.graph`` and cross-check it against the frozen
independent evaluator without mutating any shared fixture.  The material
implementation must render the canonical subject deterministically, must be
accepted by the frozen evaluator with zero diagnostics, and must agree with the
frozen evaluator on every registered known-bad mutation.
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

from cre_foundry.identity import graph as material

from evals.public.temporal_identity_evaluator import (
    evaluate_subject, reconstruct_subject, EVALUATOR_ID,
)
from jsonschema import Draft202012Validator, FormatChecker

FORMAT_CHECKER = FormatChecker()


def _load_schema(name: str) -> dict:
    return json_load(ROOT / "contracts" / name)


def json_load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_recipe(subject: dict, ops: list) -> None:
    for op in ops:
        kind = op[0]
        node = subject
        for part in op[1][:-1]:
            node = node[part]
        if kind == "set":
            node[op[1][-1]] = op[2]
        elif kind == "del":
            del node[op[1][-1]]
        elif kind == "append":
            node[op[1][-1]].append(op[2])
        else:
            raise ValueError(f"unknown op {kind}")


class MaterialIdentityGraphTests(unittest.TestCase):
    def test_material_render_is_deterministic(self) -> None:
        a = material.render_subject()
        b = material.render_subject()
        self.assertEqual(a["subject_sha256"], b["subject_sha256"])
        self.assertEqual(a, b)

    def test_material_subject_passes_frozen_evaluator(self) -> None:
        subject = material.render_subject()
        result = evaluate_subject(copy.deepcopy(subject))
        self.assertTrue(result["passed"], result["diagnostics"])
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(result["evaluator_id"], EVALUATOR_ID)
        self.assertEqual(result["subject_sha256"], subject["subject_sha256"])

    def test_material_subject_is_schema_conformant(self) -> None:
        schema = _load_schema("temporal_identity.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
        errors = list(validator.iter_errors(material.render_subject()))
        self.assertEqual(errors, [])

    def test_material_checks_agree_on_reconstruction(self) -> None:
        subject = material.render_subject()
        reconstruction = reconstruct_subject(copy.deepcopy(subject))
        self.assertEqual(reconstruction["protection_verdict"], "CLEAR")
        self.assertEqual(material.material_checks(copy.deepcopy(subject)), [])

    def test_registered_mutations_detected_by_both(self) -> None:
        registered = {
            "identity_suite_collapse.json": "registered mutation detected: suite-collapse",
            "identity_protected_alias.json": "registered mutation detected: protected-alias-clear",
        }
        for name, expected in registered.items():
            with self.subTest(fixture=name):
                fixture = json_load(ROOT / "evals/known_bad/frontier" / name)
                mutated = copy.deepcopy(material.render_subject())
                _apply_recipe(mutated, fixture["recipe"]["ops"])
                mutated = material.rebind_digests(mutated)
                frozen_diag = set(evaluate_subject(copy.deepcopy(mutated))["diagnostics"])
                material_diag = set(material.material_checks(copy.deepcopy(mutated)))
                self.assertIn(expected, frozen_diag)
                self.assertIn(expected, material_diag)
                self.assertEqual(frozen_diag - {expected}, set())
                self.assertEqual(material_diag - {expected}, set())


if __name__ == "__main__":
    unittest.main()
