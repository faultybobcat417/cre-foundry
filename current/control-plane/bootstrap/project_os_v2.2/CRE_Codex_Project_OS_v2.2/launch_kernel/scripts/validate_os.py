from __future__ import annotations
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

required = [
    "AGENTS.md",
    "README_START_HERE.md",
    "FINAL_CODEX_LAUNCH_PROMPT_v2.2.md",
    "kernel/MISSION.md",
    "kernel/INVARIANTS.json",
    "kernel/AUTHORITY.md",
    "kernel/PROOF_POLICY.md",
    "kernel/STOP_POLICY.md",
    "control/WORKFLOW.md",
    "control/EXECUTION_MODES.md",
    "control/SYMPHONY_WORKFLOW.md",
    "control/TASK_SELECTION_POLICY.json",
    "control/ROLE_ACTIVATION_POLICY.json",
    "control/CONTEXT_POLICY.json",
    "control/MILESTONES.json",
    "control/TASK_GRAPH.json",
    "control/CURRENT_STATE.json",
    "control/CURRENT_TASK.json",
    "context/PRODUCT_BRIEF.md",
    "context/REFERENCE_ARCHITECTURE.md",
    "context/AGENT_DATA_PRIMITIVES.json",
    "context/EXPERTISE_MAP.json",
    "schemas/task_result.schema.json",
]
for relative in required:
    if not (ROOT / relative).exists():
        errors.append(f"missing:{relative}")

def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))

try:
    invariants = load("kernel/INVARIANTS.json")["hard_invariants"]
    if len(invariants) != 10:
        errors.append("hard-invariants:expected-10")
    if len({row["id"] for row in invariants}) != len(invariants):
        errors.append("hard-invariants:duplicate-id")
except Exception as exc:
    errors.append(f"invariants:{exc}")

try:
    milestones = load("control/MILESTONES.json")["milestones"]
    by_id = {row["id"]: row for row in milestones}
    if len(by_id) != 14:
        errors.append("milestones:expected-14")
    visiting, visited = set(), set()
    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError(f"cycle:{node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in by_id[node]["depends_on"]:
            if dependency not in by_id:
                raise ValueError(f"unknown:{dependency}")
            visit(dependency)
        visiting.remove(node)
        visited.add(node)
    for node in by_id:
        visit(node)
except Exception as exc:
    errors.append(f"milestones:{exc}")

try:
    tasks = load("control/TASK_GRAPH.json")["tasks"]
    task_ids = {row["task_id"] for row in tasks}
    if "BOOTSTRAP-001" not in task_ids or "VERTICAL-001" not in task_ids:
        errors.append("tasks:bootstrap-or-vertical-missing")
    for task in tasks:
        unknown = set(task.get("dependencies", [])) - task_ids
        if unknown:
            errors.append(f"task:{task['task_id']}:unknown-dependencies:{sorted(unknown)}")
except Exception as exc:
    errors.append(f"tasks:{exc}")

prompt = (ROOT / "FINAL_CODEX_LAUNCH_PROMPT_v2.2.md").read_text(encoding="utf-8").lower()
for phrase in [
    "exactly 10",
    "abstain_no_valid_ten",
    "bootstrap-001",
    "thin end-to-end",
    "best-of-n",
    "external hidden holdout",
    "resume from state",
    "do not invent or self-grant",
]:
    if phrase not in prompt:
        errors.append(f"prompt-missing:{phrase}")

agents = list((ROOT / ".codex" / "agents").glob("*.toml"))
skills = list((ROOT / "skills").glob("*/SKILL.md"))
if len(agents) < 7:
    errors.append("agents:expected-at-least-7")
if len(skills) < 10:
    errors.append("skills:expected-at-least-10")
if (ROOT / "AGENTS.md").stat().st_size > 32768:
    errors.append("agents-md:over-default-budget")

result = {
    "passed": not errors,
    "errors": errors,
    "files": sum(1 for path in ROOT.rglob("*") if path.is_file()),
    "agents": len(agents),
    "skills": len(skills),
    "hard_invariants": 10,
    "milestones": 14,
    "sha256": hashlib.sha256(
        (ROOT / "FINAL_CODEX_LAUNCH_PROMPT_v2.2.md").read_bytes()
    ).hexdigest(),
}
output = ROOT / "artifacts" / "os_validation.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
sys.exit(0 if result["passed"] else 1)
