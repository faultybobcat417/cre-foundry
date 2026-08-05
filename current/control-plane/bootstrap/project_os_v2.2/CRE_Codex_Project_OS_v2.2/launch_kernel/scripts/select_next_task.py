from __future__ import annotations
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
graph = json.loads((ROOT / "control/TASK_GRAPH.json").read_text())
state = json.loads((ROOT / "control/CURRENT_STATE.json").read_text())
completed = set(state["completed_tasks"])
open_gates = set(state["open_gates"])

def score(task: dict) -> float:
    p = task.get("priority", {})
    numerator = (
        p.get("mission_impact", 1)
        * p.get("success_probability", 1)
        * p.get("dependency_unlock", 1)
        * p.get("information_gain", 1)
        * p.get("reusability", 1)
    )
    denominator = max(
        1,
        p.get("cost", 1)
        * p.get("risk", 1)
        * p.get("irreversibility", 1)
        * p.get("coordination_burden", 1),
    )
    return numerator / denominator

executable = []
for task in graph["tasks"]:
    if task["status"] not in {"ready", "queued"}:
        continue
    if not set(task.get("dependencies", [])) <= completed:
        continue
    if set(task.get("gates", [])) & open_gates:
        continue
    executable.append((score(task), task))

if executable:
    executable.sort(key=lambda item: (-item[0], item[1]["task_id"]))
    selected = executable[0][1]
    result = {
        "selected_task_id": selected["task_id"],
        "score": executable[0][0],
        "reason": "highest executable task after dependency/gate filtering",
    }
else:
    current = next(
        (task for task in graph["tasks"] if task["task_id"] == state["current_task_id"]),
        None,
    )
    result = {
        "selected_task_id": state["current_task_id"] if current else None,
        "score": None,
        "reason": "no new executable queued task; preserve current task or gates",
    }

output = ROOT / "artifacts" / "selected_task.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
