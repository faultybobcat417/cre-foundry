from __future__ import annotations
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "control/CONTEXT_POLICY.json").read_text())
task = json.loads((ROOT / "control/CURRENT_TASK.json").read_text())
state = json.loads((ROOT / "control/CURRENT_STATE.json").read_text())
invariants = json.loads((ROOT / "kernel/INVARIANTS.json").read_text())

mandatory = [
    "kernel/MISSION.md",
    "kernel/INVARIANTS.json",
    "control/CURRENT_STATE.json",
    "control/CURRENT_TASK.json",
    "kernel/PROOF_POLICY.md",
]
requested = list(task.get("context_paths", []))
final_paths = []
for relative in mandatory + requested:
    if relative not in final_paths and (ROOT / relative).is_file():
        final_paths.append(relative)

max_chars = int(policy["default_max_chars"])
sections = []
included, excluded = [], []
used = 0

for relative in final_paths:
    text = (ROOT / relative).read_text(encoding="utf-8")
    block = f"\n\n===== {relative} =====\n{text}"
    if used + len(block) <= max_chars or relative in mandatory:
        sections.append(block)
        included.append(relative)
        used += len(block)
    else:
        excluded.append(relative)

acceptance = "\n\n===== ACCEPTANCE RECAP =====\n" + "\n".join(
    f"- {item}" for item in task.get("acceptance", [])
)
sections.append(acceptance)
packet = "".join(sections).strip() + "\n"

packet_path = ROOT / "artifacts" / "context" / "current_task_packet.md"
packet_path.parent.mkdir(parents=True, exist_ok=True)
packet_path.write_text(packet, encoding="utf-8")
digest = hashlib.sha256(packet.encode()).hexdigest()

manifest = {
    "task_id": task["task_id"],
    "included_files": included,
    "excluded_files": excluded,
    "characters": len(packet),
    "estimated_tokens": len(packet) // 4,
    "packet_sha256": digest,
    "hard_invariant_count": len(invariants["hard_invariants"]),
}
manifest_path = ROOT / "artifacts" / "context" / "current_task_packet.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
