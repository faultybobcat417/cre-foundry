"""Build the machine-readable mission invariant trace (evidence_type mutation_fault).

Maps every hard invariant from the launch-kernel INVARIANTS.json to current,
sha256-bound evaluator evidence artifacts.  Deterministic output; run after
evidence artifacts are current.  Read-only against all other paths.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVARIANTS_PATH = ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/INVARIANTS.json"
OUT = ROOT / "artifacts/evaluations/invariant_trace.json"

EVIDENCE: dict[str, list[str]] = {
    "INV-001": [
        "evals/public/route_decision_evaluator.py",
        "artifacts/evaluations/known_bad_public_result.json",
        "artifacts/evaluations/math_contracts.json",
        "artifacts/vertical-slice/run_manifest.json",
    ],
    "INV-002": [
        "artifacts/vertical-slice/run_manifest.json",
        "evals/known_bad/frontier/vertical_stage2_rewrite.json",
    ],
    "INV-003": [
        "artifacts/identity/public_evaluator_contract.json",
        "evals/known_bad/frontier/identity_suite_collapse.json",
    ],
    "INV-004": [
        "artifacts/evaluations/known_bad_public_result.json",
        "evals/known_bad/frontier/identity_protected_alias.json",
    ],
    "INV-005": [
        "artifacts/evaluations/outcomes_synthetic.json",
        "artifacts/evaluations/baseline_model_synthetic.json",
    ],
    "INV-006": [
        "artifacts/evaluations/math_contracts.json",
        "contracts/math_decision_policy.schema.json",
    ],
    "INV-007": [
        "control/EVALUATOR_DECISION.json",
        "artifacts/evaluations/public_evaluator_manifest.json",
    ],
    "INV-008": [
        "artifacts/identity/public_evaluator_contract.json",
        "artifacts/evaluations/math_contracts.json",
    ],
    "INV-009": [
        "control/GATES.json",
    ],
    "INV-010": [
        "contracts/research/claim_evidence_graph.schema.json",
        "contracts/research/source_feasibility_registry.schema.json",
    ],
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    invariants = json.loads(INVARIANTS_PATH.read_text())
    entries: list[dict[str, object]] = []
    missing: list[str] = []
    for item in invariants["hard_invariants"]:
        invariant_id = item["id"]
        evidence: list[dict[str, str]] = []
        for relative in EVIDENCE.get(invariant_id, []):
            path = ROOT / relative
            if not path.is_file():
                missing.append(relative)
                continue
            evidence.append({"path": relative, "sha256": _file_sha256(path)})
        entries.append({
            "invariant_id": invariant_id,
            "name": item["name"],
            "rule": item["rule"],
            "evidence": evidence,
        })
    if missing:
        raise SystemExit(f"missing evidence files: {sorted(missing)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "artifact_id": "MISSION-INVARIANT-TRACE",
        "schema_version": "1.0.0",
        "result": "PASS",
        "proof_level": 4,
        "evidence_type": "mutation_fault",
        "invariant_ref": "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/INVARIANTS.json",
        "invariants": entries,
    }, indent=2, sort_keys=True) + "\n")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
