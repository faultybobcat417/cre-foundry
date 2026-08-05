"""Validate the greenfield control plane and BOOTSTRAP-001 artifacts."""

from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
OS_ROOT = ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel"
OS_COMMANDS = [
    "scripts/validate_os.py",
    "scripts/validate_research_readiness.py",
    "scripts/run_level10_campaign.py",
    "scripts/probe_codex_capabilities.py",
    "scripts/select_next_task.py",
    "scripts/compile_task_context.py",
]


def load(relative: str):
    return json.loads((ROOT / relative).read_text())


def validate_dag(graph: dict) -> list[str]:
    errors: list[str] = []
    nodes = {node["task_id"]: node for node in graph["nodes"]}
    required = {"BOOTSTRAP-001", "FRONTIER-001", "RESEARCH-001", "EVAL-001", "MATH-001", "VERTICAL-001"}
    if missing := required - nodes.keys():
        errors.append(f"missing required tasks: {sorted(missing)}")
    indegree = {task_id: 0 for task_id in nodes}
    children = {task_id: [] for task_id in nodes}
    for task_id, node in nodes.items():
        for dependency in node["dependencies"]:
            if dependency not in nodes:
                errors.append(f"{task_id} has unknown dependency {dependency}")
                continue
            indegree[task_id] += 1
            children[dependency].append(task_id)
        for field in ("objective", "evaluator", "acceptance", "rollback"):
            if not node.get(field):
                errors.append(f"{task_id} missing {field}")
    ready = sorted(task_id for task_id, count in indegree.items() if count == 0)
    visited = []
    while ready:
        task_id = ready.pop(0)
        visited.append(task_id)
        for child in children[task_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(visited) != len(nodes):
        errors.append("task graph contains a cycle")
    return errors


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def replay_os_commands() -> tuple[dict[str, int], bool, list[str]]:
    exit_codes: dict[str, int] = {}
    errors: list[str] = []
    source_digest_before = tree_digest(OS_ROOT)
    with tempfile.TemporaryDirectory(prefix="cre-project-os-replay-") as temp_dir:
        replay_root = Path(temp_dir) / "launch_kernel"
        shutil.copytree(OS_ROOT, replay_root)
        for script in OS_COMMANDS:
            result = subprocess.run(
                [sys.executable, script],
                cwd=replay_root,
                check=False,
                capture_output=True,
                text=True,
            )
            exit_codes[script] = result.returncode
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip().splitlines()
                suffix = f": {detail[-1]}" if detail else ""
                errors.append(f"Project OS command failed ({script}){suffix}")
    source_unchanged = source_digest_before == tree_digest(OS_ROOT)
    if not source_unchanged:
        errors.append("Project OS source tree changed during isolated command replay")
    return exit_codes, source_unchanged, errors


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Validate the greenfield control plane and BOOTSTRAP-001 artifacts.")
    parser.add_argument("--reconcile-only", action="store_true", help="reconcile control state without OS replay or the full public suite")
    args = parser.parse_args(argv)
    errors: list[str] = []
    required_files = [
        "AGENTS.md",
        "artifacts/bootstrap/repository_inventory.json",
        "artifacts/bootstrap/capability_manifest.json",
        "artifacts/bootstrap/contradiction_register.json",
        "artifacts/bootstrap/input_classification.json",
        "control/EVALUATOR_DECISION.json",
        "control/AUTONOMOUS_FRONTIER_CONTRACT.json",
        "control/GATES.json",
        "contracts/autonomous_frontier_contract.schema.json",
        "scripts/evaluate_autonomous_frontier.py",
        "tasks/FRONTIER-001.json",
        "tasks/RESEARCH-001.json",
        "tasks/MATH-001.json",
    ]
    for relative in required_files:
        if not (ROOT / relative).is_file():
            errors.append(f"missing {relative}")
    graph = load("control/TASK_GRAPH.json")
    errors.extend(validate_dag(graph))
    nodes = {node["task_id"]: node for node in graph["nodes"]}
    state = load("control/CURRENT_STATE.json")
    current = load("control/CURRENT_TASK.json")
    if state["current_task_id"] != current["task_id"]:
        errors.append("CURRENT_STATE and CURRENT_TASK disagree")
    if current["task_id"] not in nodes:
        errors.append("CURRENT_TASK is absent from TASK_GRAPH")
    elif nodes[current["task_id"]]["status"] != current["status"]:
        errors.append("CURRENT_TASK and TASK_GRAPH status disagree")
    repository_task = load(current["task_path"])
    if repository_task["task_id"] != current["task_id"] or repository_task["status"] != current["status"]:
        errors.append("task packet, CURRENT_TASK, and TASK_GRAPH disagree")
    for completed in state["completed_tasks"]:
        if completed in nodes and nodes[completed]["status"] != "completed":
            errors.append(f"completed task {completed} is not completed in TASK_GRAPH")
    graph_completed = sorted(task_id for task_id, node in nodes.items() if node["status"] == "completed")
    gates = {gate["gate_id"]: gate for gate in load("control/GATES.json")["gates"]}
    graph_executable = sorted(
        task_id
        for task_id, node in nodes.items()
        if node["status"] in {"pending", "in_progress"}
        and all(nodes[dependency]["status"] == "completed" for dependency in node["dependencies"])
        and not any(
            str(gates.get(gate_id, {}).get("status", "")).startswith("OPEN")
            for gate_id in node["gates"]
        )
    )
    graph_blocked = sorted(task_id for task_id, node in nodes.items() if node["status"] == "blocked")
    if sorted(state["completed_tasks"]) != graph_completed:
        errors.append("CURRENT_STATE.completed_tasks does not exactly match TASK_GRAPH")
    if sorted(state["executable_tasks"]) != graph_executable:
        errors.append("CURRENT_STATE.executable_tasks does not exactly match executable TASK_GRAPH nodes")
    if sorted(state["blocked_tasks"]) != graph_blocked:
        errors.append("CURRENT_STATE.blocked_tasks does not exactly match blocked TASK_GRAPH nodes")
    for task_id, node in nodes.items():
        for gate_id in node["gates"]:
            if gate_id not in gates:
                errors.append(f"{task_id} references missing gate {gate_id}")
            elif task_id not in gates[gate_id].get("blocks", []):
                errors.append(f"gate {gate_id} does not map back to {task_id}")
        if node["status"] == "completed":
            open_direct = [
                gate_id
                for gate_id in node["gates"]
                if str(gates.get(gate_id, {}).get("status", "")).startswith("OPEN")
            ]
            if open_direct:
                errors.append(f"completed task {task_id} retains open gates {sorted(open_direct)}")
            result_path = ROOT / f"artifacts/task-results/{task_id}.json"
            if not result_path.is_file():
                errors.append(f"completed task {task_id} lacks a task-result artifact")
            else:
                result_payload = load(f"artifacts/task-results/{task_id}.json")
                if result_payload.get("task_id") != task_id or result_payload.get("status") != "completed":
                    errors.append(f"completed task {task_id} has mismatched task-result status or identity")
    for gate_id, gate in gates.items():
        for blocked in gate.get("blocks", []):
            if blocked in nodes and gate_id not in nodes[blocked]["gates"]:
                errors.append(f"{gate_id} blocks {blocked} but TASK_GRAPH does not map it")
    graph_open_gates = sorted(
        gate_id for gate_id, gate in gates.items() if gate["status"] == "OPEN_BLOCKING"
    )
    if sorted(state["open_gates"]) != graph_open_gates:
        errors.append("CURRENT_STATE.open_gates does not exactly match GATES")
    evaluator = load("control/EVALUATOR_DECISION.json")
    if evaluator["sealed_layer"]["status"] != "GATED_NOT_CLAIMED":
        errors.append("sealed evaluator must remain unclaimed until custody gate closes")
    if evaluator["external_hidden_layer"]["status"] != "GATED_NOT_CLAIMED":
        errors.append("external hidden holdout must remain unclaimed")
    Draft202012Validator.check_schema(load("contracts/route_decision.schema.json"))
    frontier_schema = load("contracts/autonomous_frontier_contract.schema.json")
    Draft202012Validator.check_schema(frontier_schema)
    errors.extend(
        f"autonomous frontier contract: {error.message}"
        for error in Draft202012Validator(frontier_schema).iter_errors(
            load("control/AUTONOMOUS_FRONTIER_CONTRACT.json")
        )
    )
    manifest = load("artifacts/evaluations/public_evaluator_manifest.json")
    for item in manifest["files"]:
        manifest_path = ROOT / item["path"]
        if not manifest_path.is_file():
            errors.append(f"missing evaluator file {item['path']}")
            continue
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            errors.append(f"evaluator hash mismatch {item['path']}")
    task_result = ROOT / "artifacts/task-results/BOOTSTRAP-001.json"
    if task_result.exists():
        schema = json.loads((OS_ROOT / "schemas/task_result.schema.json").read_text())
        result = json.loads(task_result.read_text())
        errors.extend(error.message for error in Draft202012Validator(schema).iter_errors(result))
        for artifact in result["artifacts"]:
            if not (ROOT / artifact["path"]).exists():
                errors.append(f"missing task artifact {artifact['path']}")
        for changed in result["files_changed"]:
            if not (ROOT / changed).exists():
                errors.append(f"missing changed path {changed}")
        for additional_result in sorted((ROOT / "artifacts/task-results").glob("*.json")):
            if additional_result == task_result:
                continue
            additional_payload = json.loads(additional_result.read_text())
            errors.extend(
                f"{additional_result.name}: {error.message}"
                for error in Draft202012Validator(schema).iter_errors(additional_payload)
            )
            for artifact in additional_payload["artifacts"]:
                if not (ROOT / artifact["path"]).exists():
                    errors.append(f"{additional_result.name}: missing task artifact {artifact['path']}")
            for changed in additional_payload["files_changed"]:
                if not (ROOT / changed).exists():
                    errors.append(f"{additional_result.name}: missing changed path {changed}")
    head = git("rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        errors.append("repository has no Git checkpoint commit")
    checkpoint = state["checkpoint_commit"]
    checkpoint_object = git("cat-file", "-e", f"{checkpoint}^{{commit}}")
    if checkpoint_object.returncode != 0:
        errors.append("CURRENT_STATE.checkpoint_commit does not resolve to a commit")
    elif head.returncode == 0:
        ancestor = git("merge-base", "--is-ancestor", checkpoint, "HEAD")
        if ancestor.returncode != 0:
            errors.append("CURRENT_STATE.checkpoint_commit is not an ancestor of HEAD")
    if task_result.exists():
        rollback_hashes = set(re.findall(r"\b[0-9a-f]{40}\b", result["rollback"]))
        if not rollback_hashes:
            errors.append("BOOTSTRAP-001 task-result rollback has no exact commit baseline")
        for rollback_hash in rollback_hashes:
            rollback_object = git("cat-file", "-e", f"{rollback_hash}^{{commit}}")
            if rollback_object.returncode != 0:
                errors.append(f"task-result rollback commit does not resolve: {rollback_hash}")
            elif head.returncode == 0 and git("merge-base", "--is-ancestor", rollback_hash, "HEAD").returncode != 0:
                errors.append(f"task-result rollback commit is not an ancestor of HEAD: {rollback_hash}")
        recorded_os_commands = {
            Path(command["command"].split("python ", 1)[-1]).as_posix()
            for command in result["commands"]
            if "launch_kernel" in command["command"] and "python scripts/" in command["command"]
        }
        missing_recorded_commands = set(OS_COMMANDS) - recorded_os_commands
        if missing_recorded_commands:
            errors.append(f"task result omits Project OS commands: {sorted(missing_recorded_commands)}")
    checkpoint_result = ROOT / f"artifacts/task-results/{state['last_checkpoint']}.json"
    if not checkpoint_result.is_file():
        errors.append("CURRENT_STATE.last_checkpoint has no exact task-result artifact")
    os_command_exit_codes: dict[str, int] = {}
    os_source_tree_unchanged = True
    os_errors: list[str] = []
    if not args.reconcile_only:
        os_command_exit_codes, os_source_tree_unchanged, os_errors = replay_os_commands()
    errors.extend(os_errors)
    public_tests_exit_code = 0
    if not args.reconcile_only:
        public_tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "evals/public", "-p", "test_*.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        public_tests_exit_code = public_tests.returncode
        if public_tests.returncode != 0:
            errors.append("public evaluator self-tests failed")
    if args.reconcile_only:
        print("PASS" if not errors else "FAIL")
        return 0 if not errors else 1
    payload = {
        "passed": not errors,
        "errors": errors,
        "task_count": len(graph["nodes"]),
        "public_tests_exit_code": public_tests_exit_code,
        "os_command_exit_codes": os_command_exit_codes,
        "os_source_tree_unchanged": os_source_tree_unchanged,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
