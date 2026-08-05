#!/usr/bin/env python3
"""Generate the frozen synthetic BASELINE-001 subjects and mutation registry."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.baselines.framework import digest_json, write_artifacts
from evals.public.baseline_framework_evaluator import MUTATION_DIAGNOSTICS


def main() -> int:
    run = write_artifacts()
    mutation_root = ROOT / "evals/known_bad/frontier"
    mutation_root.mkdir(parents=True, exist_ok=True)
    for stale in mutation_root.glob("baseline_*.json"):
        stale.unlink()
    base_sha = digest_json(run)
    for case_id, diagnostic in sorted(MUTATION_DIAGNOSTICS.items()):
        fixture = {
            "document_kind": "REGISTERED_BASELINE_MUTATION",
            "schema_version": "1.0.0",
            "case_id": case_id,
            "expected_diagnostic": diagnostic,
            "base_run_sha256": base_sha,
            "attack_scope": "SYNTHETIC_EVALUATOR_SELF_TEST_ONLY",
        }
        path = mutation_root / f"baseline_{case_id.replace('-', '_')}.json"
        path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    compatibility_cases = {
        "model_missing_baselines.json": ("missing-baselines", "registered mutation detected: missing-baselines"),
        "model_future_feature.json": ("future-feature", "registered mutation detected: future-feature"),
    }
    for name, (case_id, diagnostic) in compatibility_cases.items():
        fixture = {"document_kind": "FRONTIER_BASELINE_MUTATION", "schema_version": "1.0.0", "case_id": case_id, "expected_diagnostic": diagnostic, "base_run_sha256": base_sha}
        (mutation_root / name).write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    model_root = ROOT / "artifacts/models"
    model_root.mkdir(parents=True, exist_ok=True)
    (model_root / "model_registry.json").write_text(json.dumps({"artifact_id": "BASELINE-001-MODEL-REGISTRY-COMPATIBILITY", "proof_level": 5, "execution_scope": "SYNTHETIC_NON_INFLUENCING", "policy_registry": json.loads((ROOT / "artifacts/baselines/policy_registry.json").read_text())}, indent=2, sort_keys=True) + "\n")
    print(f"generated baseline run and {len(MUTATION_DIAGNOSTICS)} mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
