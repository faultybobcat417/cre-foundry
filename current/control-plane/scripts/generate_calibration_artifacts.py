#!/usr/bin/env python3
"""Generate CALIBRATION-001 subjects and registered mutation fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.calibration.framework import digest_json, write_artifacts


def main() -> int:
    run = write_artifacts()
    from evals.public.calibration_framework_evaluator import MUTATION_DIAGNOSTICS, MUTATION_RECIPES
    mutation_root = ROOT / "evals/known_bad/frontier"
    mutation_root.mkdir(parents=True, exist_ok=True)
    for stale in mutation_root.glob("calibration_*.json"):
        stale.unlink()
    base_sha = digest_json(run)
    for case_id, diagnostic in sorted(MUTATION_DIAGNOSTICS.items()):
        fixture = {"document_kind": "REGISTERED_CALIBRATION_MUTATION", "schema_version": "1.0.0", "case_id": case_id, "expected_diagnostic": diagnostic, "base_run_sha256": base_sha, "attack_scope": "SYNTHETIC_EVALUATOR_SELF_TEST_ONLY", "patch": MUTATION_RECIPES[case_id]}
        (mutation_root / f"calibration_{case_id.replace('-', '_')}.json").write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    compatibility = {
        "calibration_subgroup_hidden.json": ("aggregate-hides-subgroup", "registered mutation detected: aggregate-hides-subgroup"),
        "calibration_point_only.json": ("point-estimate-only", "registered mutation detected: point-estimate-only"),
    }
    for name, (case_id, diagnostic) in compatibility.items():
        fixture = {"document_kind": "FRONTIER_CALIBRATION_MUTATION", "schema_version": "1.0.0", "case_id": case_id, "expected_diagnostic": diagnostic, "base_run_sha256": base_sha}
        (mutation_root / name).write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(f"generated calibration run and {len(MUTATION_DIAGNOSTICS)} mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
