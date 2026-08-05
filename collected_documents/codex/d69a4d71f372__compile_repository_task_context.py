"""Compile a bounded repository-owned packet for the current task."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel"
OUT = ROOT / "artifacts/context"

BASE = [
    KERNEL / "kernel/MISSION.md",
    KERNEL / "kernel/INVARIANTS.json",
    KERNEL / "kernel/PROOF_POLICY.md",
    KERNEL / "kernel/CAPABILITY_BOUNDARY.md",
    KERNEL / "kernel/CAPABILITY_BOUNDARY.json",
    KERNEL / "kernel/MATH_MODELING_CONSTITUTION.md",
    KERNEL / "schemas/task_result.schema.json",
    KERNEL / "control/WORKFLOW.md",
    ROOT / "control/CURRENT_STATE.json",
    ROOT / "control/CURRENT_TASK.json",
    ROOT / "control/TASK_GRAPH.json",
    ROOT / "control/GATES.json",
    ROOT / "control/AUTONOMOUS_FRONTIER_CONTRACT.json",
    ROOT / "scripts/evaluate_autonomous_frontier.py",
]
TASK_PATHS = {
    "MATH-001": [
        ROOT / "tasks/MATH-001.json",
        KERNEL / "kernel/MATH_MODELING_CONSTITUTION.md",
        ROOT / "artifacts/research/claim_evidence_graph.json",
        ROOT / "contracts/route_decision.schema.json",
    ],
    "CONTRACT-001": [
        ROOT / "tasks/CONTRACT-001.json",
        KERNEL / "kernel/CAPABILITY_BOUNDARY.json",
        ROOT / "artifacts/research/source_feasibility_registry.json",
        ROOT / "artifacts/research/canonical_field_map.json",
        ROOT / "artifacts/math/formal_decisions.json",
        ROOT / "artifacts/math/public_evaluator_contract.json",
        ROOT / "contracts/math_decision_policy.schema.json",
        ROOT / "contracts/math_route_decision.schema.json",
    ],
    "VERTICAL-001": [
        ROOT / "tasks/VERTICAL-001.json",
        ROOT / "artifacts/vertical/VERTICAL-001-start.json",
        ROOT / "artifacts/vertical/public_evaluator_contract.json",
        ROOT / "docs/contracts/THIN_SLICE_CONTRACT.md",
        ROOT / "artifacts/contracts/contract_spine.json",
        ROOT / "artifacts/evaluations/contract_spine.json",
        ROOT / "contracts/synthetic_route_day.schema.json",
        ROOT / "contracts/synthetic_field_event.schema.json",
        ROOT / "contracts/synthetic_f9_outcome.schema.json",
        ROOT / "contracts/thin_slice_observation.schema.json",
        ROOT / "contracts/thin_slice_candidate.schema.json",
        ROOT / "contracts/math_decision_policy.schema.json",
        ROOT / "contracts/math_route_decision.schema.json",
        ROOT / "src/cre_foundry/contracts/thin_slice.py",
        ROOT / "evals/public/contract_spine_evaluator.py",
    ],
    "OUTCOMES-001": [
        ROOT / "tasks/OUTCOMES-001.json",
        ROOT / "artifacts/task-results/VERTICAL-001.json",
        ROOT / "artifacts/vertical/public_evaluator_contract.json",
        ROOT / "artifacts/vertical-slice/run_manifest.json",
        ROOT / "artifacts/evaluations/vertical_slice.json",
        ROOT / "artifacts/math/estimand_registry.json",
        ROOT / "artifacts/research/claim_evidence_graph.json",
        ROOT / "contracts/synthetic_route_day.schema.json",
        ROOT / "contracts/synthetic_field_event.schema.json",
        ROOT / "contracts/synthetic_f9_outcome.schema.json",
        ROOT / "src/cre_foundry/vertical/shadow_slice.py",
        ROOT / "evals/public/vertical_slice_evaluator.py",
    ],
    "BASELINE-001": [
        ROOT / "tasks/BASELINE-001.json",
        ROOT / "artifacts/baselines/BASELINE-001-start.json",
        ROOT / "artifacts/baselines/public_evaluator_contract.json",
        ROOT / "artifacts/task-results/OUTCOMES-001.json",
        ROOT / "artifacts/outcomes/public_evaluator_contract.json",
        ROOT / "artifacts/outcomes/synthetic_window_policy.json",
        ROOT / "artifacts/outcomes/scenario_matrix.json",
        ROOT / "artifacts/outcomes/canonical_run.json",
        ROOT / "artifacts/evaluations/outcomes_synthetic.json",
        ROOT / "artifacts/math/formal_decisions.json",
        ROOT / "artifacts/math/estimand_registry.json",
        ROOT / "artifacts/math/public_evaluator_contract.json",
        ROOT / "artifacts/vertical-slice/run_manifest.json",
        ROOT / "contracts/f9_outcome.schema.json",
        ROOT / "contracts/baseline_policy.schema.json",
        ROOT / "contracts/baseline_evaluation.schema.json",
        ROOT / "contracts/math_decision_policy.schema.json",
        ROOT / "contracts/math_route_decision.schema.json",
        ROOT / "artifacts/baselines/frozen_benchmark.json",
        ROOT / "artifacts/baselines/policy_registry.json",
        ROOT / "artifacts/baselines/capability_classification_reconciliation.json",
        ROOT / "artifacts/evaluations/baseline_framework.json",
        ROOT / "artifacts/models/model_registry.json",
        ROOT / "artifacts/evaluations/baseline_model_synthetic.json",
        ROOT / "src/cre_foundry/baselines/framework.py",
        ROOT / "src/cre_foundry/math/reference_oracle.py",
        ROOT / "src/cre_foundry/outcomes/ledger.py",
        ROOT / "evals/public/baseline_framework_evaluator.py",
        ROOT / "evals/public/test_baseline_framework.py",
        ROOT / "scripts/validate_baseline_framework.py",
        ROOT / "scripts/validate_baseline_models.py",
        ROOT / "evals/public/math_oracle_evaluator.py",
        ROOT / "evals/public/outcomes_labels_evaluator.py",
    ],
    "CALIBRATION-001": [
        ROOT / "tasks/CALIBRATION-001.json",
        ROOT / "artifacts/calibration/CALIBRATION-001-start.json",
        ROOT / "artifacts/calibration/public_evaluator_contract.json",
        ROOT / "artifacts/task-results/BASELINE-001.json",
        ROOT / "artifacts/baselines/public_evaluator_contract.json",
        ROOT / "artifacts/baselines/frozen_benchmark.json",
        ROOT / "artifacts/baselines/policy_registry.json",
        ROOT / "artifacts/evaluations/baseline_framework.json",
        ROOT / "artifacts/outcomes/public_evaluator_contract.json",
        ROOT / "artifacts/math/estimand_registry.json",
        ROOT / "artifacts/math/public_evaluator_contract.json",
        ROOT / "contracts/baseline_policy.schema.json",
        ROOT / "contracts/baseline_evaluation.schema.json",
        ROOT / "contracts/calibration_input.schema.json",
        ROOT / "contracts/calibration_evaluation.schema.json",
        ROOT / "contracts/calibration_uncertainty.schema.json",
        ROOT / "contracts/f9_outcome.schema.json",
        ROOT / "contracts/math_route_decision.schema.json",
        ROOT / "artifacts/calibration/frozen_input.json",
        ROOT / "artifacts/calibration/canonical_run.json",
        ROOT / "artifacts/evaluations/calibration_framework.json",
        ROOT / "artifacts/evaluations/calibration_synthetic.json",
        ROOT / "src/cre_foundry/baselines/framework.py",
        ROOT / "src/cre_foundry/calibration/framework.py",
        ROOT / "evals/public/baseline_framework_evaluator.py",
        ROOT / "evals/public/calibration_framework_evaluator.py",
        ROOT / "evals/public/test_calibration_framework.py",
        ROOT / "scripts/generate_calibration_artifacts.py",
        ROOT / "scripts/validate_calibration_framework.py",
        ROOT / "scripts/validate_calibration_uncertainty.py",
    ],
    "ARCHITECTURE-001": [
        ROOT / "tasks/ARCHITECTURE-001.json",
        ROOT / "artifacts/architecture/ARCHITECTURE-001-start.json",
        ROOT / "artifacts/architecture/public_evaluator_contract.json",
        ROOT / "artifacts/task-results/VERTICAL-001.json",
        ROOT / "artifacts/vertical/public_evaluator_contract.json",
        ROOT / "artifacts/vertical-slice/run_manifest.json",
        ROOT / "artifacts/evaluations/vertical_slice.json",
        ROOT / "artifacts/contracts/public_evaluator_contract.json",
        ROOT / "artifacts/contracts/contract_spine.json",
        ROOT / "artifacts/evaluations/contract_spine.json",
        ROOT / "docs/contracts/THIN_SLICE_CONTRACT.md",
        ROOT / "contracts/synthetic_route_day.schema.json",
        ROOT / "contracts/synthetic_field_event.schema.json",
        ROOT / "contracts/synthetic_f9_outcome.schema.json",
        ROOT / "contracts/thin_slice_observation.schema.json",
        ROOT / "contracts/thin_slice_candidate.schema.json",
        ROOT / "contracts/math_decision_policy.schema.json",
        ROOT / "contracts/math_route_decision.schema.json",
        ROOT / "src/cre_foundry/contracts/thin_slice.py",
        ROOT / "src/cre_foundry/vertical/shadow_slice.py",
        ROOT / "src/cre_foundry/math/reference_oracle.py",
        ROOT / "evals/public/contract_spine_evaluator.py",
        ROOT / "evals/public/vertical_slice_evaluator.py",
        ROOT / "evals/public/math_oracle_evaluator.py",
    ],
    "IDENTITY-001": [
        ROOT / "tasks/IDENTITY-001.json",
        ROOT / "artifacts/task-results/CONTRACT-001.json",
        ROOT / "artifacts/task-results/VERTICAL-001.json",
        ROOT / "artifacts/task-results/ARCHITECTURE-001.json",
        ROOT / "artifacts/contracts/contract_spine.json",
        ROOT / "artifacts/contracts/public_evaluator_contract.json",
        ROOT / "docs/contracts/THIN_SLICE_CONTRACT.md",
        ROOT / "contracts/synthetic_route_day.schema.json",
        ROOT / "contracts/synthetic_field_event.schema.json",
        ROOT / "contracts/synthetic_f9_outcome.schema.json",
        ROOT / "contracts/thin_slice_observation.schema.json",
        ROOT / "contracts/thin_slice_candidate.schema.json",
        ROOT / "contracts/math_decision_policy.schema.json",
        ROOT / "contracts/math_route_decision.schema.json",
        ROOT / "src/cre_foundry/contracts/thin_slice.py",
        ROOT / "src/cre_foundry/vertical/shadow_slice.py",
        ROOT / "src/cre_foundry/math/reference_oracle.py",
        ROOT / "evals/public/contract_spine_evaluator.py",
        ROOT / "evals/public/vertical_slice_evaluator.py",
        ROOT / "evals/public/math_oracle_evaluator.py",
        ROOT / "evals/known_bad/frontier/contract_brand_location_collapse.json",
        ROOT / "evals/known_bad/frontier/contract_protected_alias_omission.json",
        ROOT / "evals/known_bad/frontier/contract_future_observation.json",
        ROOT / "evals/known_bad/frontier/vertical_protected_stop.json",
        ROOT / "evals/known_bad/frontier/exact_ten_protected_fill.json",
    ],
}


def label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    current = json.loads((ROOT / "control/CURRENT_TASK.json").read_text())
    paths = BASE + TASK_PATHS.get(current["task_id"], [ROOT / current["task_path"]])
    sections = []
    files = []
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"missing context source: {path}")
        content = path.read_text()
        sections.append(f"===== {label(path)} =====\n{content.rstrip()}\n")
        files.append({"path": label(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    packet = "\n".join(sections)
    OUT.mkdir(parents=True, exist_ok=True)
    packet_path = OUT / "current_task_packet.md"
    packet_path.write_text(packet)
    manifest = {"task_id": current["task_id"], "files": files, "characters": len(packet), "packet_sha256": hashlib.sha256(packet.encode()).hexdigest()}
    (OUT / "current_task_packet.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
