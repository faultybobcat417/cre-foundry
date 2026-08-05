from __future__ import annotations
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
prompt = (ROOT / "FINAL_CODEX_LAUNCH_PROMPT_v2.2.md").read_text()
normalized = " ".join(prompt.lower().replace("–", "-").replace("—", "-").split())

checks = {
    "mission": all(x in normalized for x in ["exactly 10", "f9", "abstain_no_valid_ten"]),
    "repository_truth": "inspect" in normalized and "repository" in normalized,
    "depth_first_vertical_slice": "thin end-to-end" in normalized,
    "evaluator_topology": all(x in normalized for x in ["sealed adversarial", "external hidden holdout"]),
    "best_of_n": "best-of-n" in normalized,
    "progressive_context": "compiled task context" in normalized,
    "role_relevance": "classify relevant expertise" in normalized,
    "state_resume": all(x in normalized for x in ["checkpoint", "resume from state"]),
    "three_modes": all(x in normalized for x in ["interactive/goal", "headless", "tracker-orchestrated"]),
    "security": all(x in normalized for x in ["do not invent or self-grant", "sandboxing", "approval"]),
    "claim_integrity": "claims may not exceed" in normalized,
    "no_endless_turn_claim": "context window ending is a checkpoint" in normalized,
}
score = sum(1 for passed in checks.values() if passed) / len(checks) * 100
result = {
    "passed": all(checks.values()),
    "score": score,
    "checks": checks,
    "words": len(re.findall(r"\b\w+\b", prompt)),
    "characters": len(prompt),
}
output = ROOT / "artifacts" / "prompt_audit.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["passed"] else 1)
