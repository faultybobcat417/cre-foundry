from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
errors = []

required = [
    "kernel/CAPABILITY_BOUNDARY.json",
    "kernel/CAPABILITY_BOUNDARY.md",
    "kernel/MATH_MODELING_CONSTITUTION.md",
    "control/RESEARCH_COMPLETION_PROTOCOL.md",
    "control/CLAIM_PROOF_REGISTER.json",
    "control/AUTHORIZED_FALLBACK_LADDER.md",
    "context/CORE_RESEARCH_QUESTIONS.json",
]
for rel in required:
    if not (ROOT/rel).exists():
        errors.append(f"missing:{rel}")

cap = json.loads((ROOT/"kernel/CAPABILITY_BOUNDARY.json").read_text())
classes = {row["class"] for row in cap["classes"]}
expected = {
    "CODEX_DERIVABLE","PUBLICLY_RESEARCHABLE","ACCESS_DEPENDENT",
    "HUMAN_AUTHORITATIVE","EMPIRICAL_ONLY","EXTERNALLY_HIDDEN"
}
if classes != expected:
    errors.append(f"capability-classes:{sorted(classes)}")

claims = json.loads((ROOT/"control/CLAIM_PROOF_REGISTER.json").read_text())["claims"]
levels = {row["claim_id"]:row["required_proof_level"] for row in claims}
if levels.get("CLM-006") != 8 or levels.get("CLM-007") != 9:
    errors.append("causal-or-commercial-proof-level")

questions = json.loads((ROOT/"context/CORE_RESEARCH_QUESTIONS.json").read_text())["questions"]
if len(questions) < 12:
    errors.append("research-questions:expected-at-least-12")

graph = json.loads((ROOT/"control/TASK_GRAPH.json").read_text())["tasks"]
ids = {t["task_id"] for t in graph}
for task in ["RESEARCH-001","MATH-001","VERTICAL-001"]:
    if task not in ids:
        errors.append(f"task-missing:{task}")

vertical = next(t for t in graph if t["task_id"]=="VERTICAL-001")
if "MATH-001" not in vertical["dependencies"]:
    errors.append("vertical-must-depend-on-math")

prompt = (ROOT/"FINAL_CODEX_LAUNCH_PROMPT_v2.2.md").read_text().lower()
for phrase in ["capability_boundary","research-001","math-001","mathematical"]:
    if phrase not in prompt:
        errors.append(f"prompt-missing:{phrase}")

result = {
    "passed": not errors,
    "errors": errors,
    "capability_classes": len(classes),
    "claims": len(claims),
    "research_questions": len(questions),
    "tasks": len(graph),
}
out = ROOT/"artifacts"/"research_readiness_validation.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
sys.exit(0 if not errors else 1)
