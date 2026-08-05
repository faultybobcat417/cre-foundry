#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

REPO = Path("/Users/alimehdi/Documents/cre")
BASELINE = "dd44e5ee7f9195d140dfbd747b5a4812b199a81e"
EXPECTED_BRANCH = "handoff/kimi-architecture-001"
EXPECTED_HASHES = {
    "control/ONE_SHOT_READINESS.json":
        "e0fa1f1d03904d74fb948a8b7d22d028dd193a1090a6f41bcba235f11d46cbc0",
    "artifacts/identity/public_evaluator_contract.json":
        "583e7715e2af53e82309e934d6136d1b161bcda45771cebc948e9a9137525282",
    "contracts/temporal_identity.schema.json":
        "0c3b42f906063169b46cc760f9e7cf516b3c73c7c84f6293eb4cfcf826cc55ba",
}

stamp = time.strftime("%Y%m%d-%H%M%S")
OUT = Path.home() / "Desktop" / f"CRE-Post-Gemini-Audit-{stamp}"


def run(
    args: list[str],
    *,
    cwd: Path = REPO,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(*args: str, check: bool = True) -> str:
    result = run(["git", *args], check=check)
    return result.stdout


def write(name: str, content: str | bytes) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_parse_error": f"{type(exc).__name__}: {exc}"}


def head_json(relative: str) -> Any:
    result = run(
        ["git", "show", f"HEAD:{relative}"],
        check=False,
    )
    if result.returncode != 0:
        return {"_missing_in_head": True}
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        return {"_parse_error": f"{type(exc).__name__}: {exc}"}


def semantic_diff(before: Any, after: Any, prefix: str = "$") -> list[str]:
    if type(before) is not type(after):
        return [
            f"{prefix}: type {type(before).__name__} -> "
            f"{type(after).__name__}"
        ]

    if isinstance(before, dict):
        changes: list[str] = []
        keys = sorted(set(before) | set(after))
        for key in keys:
            if key not in before:
                changes.append(f"{prefix}.{key}: added")
            elif key not in after:
                changes.append(f"{prefix}.{key}: removed")
            else:
                changes.extend(
                    semantic_diff(before[key], after[key], f"{prefix}.{key}")
                )
        return changes

    if isinstance(before, list):
        if before == after:
            return []
        return [
            f"{prefix}: list changed "
            f"(length {len(before)} -> {len(after)})"
        ]

    if before != after:
        old = repr(before)
        new = repr(after)
        if len(old) > 220:
            old = old[:217] + "..."
        if len(new) > 220:
            new = new[:217] + "..."
        return [f"{prefix}: {old} -> {new}"]

    return []


def parse_z(raw: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
    ]


if not (REPO / ".git").is_dir():
    print(f"STOP: repository not found: {REPO}", file=sys.stderr)
    raise SystemExit(1)

OUT.mkdir(parents=True, exist_ok=False)

initial_head = git("rev-parse", "HEAD").strip()
initial_status = git("status", "--porcelain=v1")
branch = git("branch", "--show-current").strip()

write("branch.txt", branch + "\n")
write("head.txt", initial_head + "\n")
write("status.txt", git("status", "--short", "--branch"))
write("porcelain.txt", initial_status)
write("history.txt", git("log", "--oneline", "--decorate", "--graph", "--all", "-100"))
write("reflog.txt", git("reflog", "--date=iso", "-80"))
write("branches.txt", git("branch", "-vv"))
write("unstaged-name-status.txt", git("diff", "--name-status"))
write("staged-name-status.txt", git("diff", "--cached", "--name-status"))
write("untracked-files.txt", git("ls-files", "--others", "--exclude-standard"))
write("unstaged-stat.txt", git("diff", "--stat"))
write("staged-stat.txt", git("diff", "--cached", "--stat"))
write("unstaged.patch", git("diff", "--binary"))
write("staged.patch", git("diff", "--cached", "--binary"))

# Baseline relationship and commits after the last verified checkpoint.
baseline_exists = run(
    ["git", "cat-file", "-e", f"{BASELINE}^{{commit}}"],
    check=False,
).returncode == 0

baseline_ancestor = False
if baseline_exists:
    baseline_ancestor = run(
        ["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"],
        check=False,
    ).returncode == 0

write("baseline-exists.txt", f"{baseline_exists}\n")
write("baseline-is-ancestor.txt", f"{baseline_ancestor}\n")

if baseline_ancestor:
    write(
        "commits-after-baseline.txt",
        git("log", "--oneline", "--decorate", "--reverse", f"{BASELINE}..HEAD"),
    )
    write(
        "committed-paths-after-baseline.txt",
        git("diff", "--name-status", f"{BASELINE}..HEAD"),
    )
    write(
        "committed-stat-after-baseline.txt",
        git("diff", "--stat", f"{BASELINE}..HEAD"),
    )
else:
    write("commits-after-baseline.txt", "")
    write("committed-paths-after-baseline.txt", "")
    write("committed-stat-after-baseline.txt", "")

# Protected hashes.
protected_lines: list[str] = []
protected_results: dict[str, dict[str, str | bool]] = {}
for relative, expected in EXPECTED_HASHES.items():
    path = REPO / relative
    if not path.is_file():
        protected_lines.append(f"MISSING  {relative}")
        protected_results[relative] = {
            "expected": expected,
            "actual": "MISSING",
            "match": False,
        }
        continue
    actual = sha256(path)
    protected_lines.append(f"{actual}  {relative}")
    protected_results[relative] = {
        "expected": expected,
        "actual": actual,
        "match": actual == expected,
    }

write("protected-hashes.txt", "\n".join(protected_lines) + "\n")
write(
    "protected-hash-results.json",
    json.dumps(protected_results, indent=2, sort_keys=True) + "\n",
)

# Capture exact changed/untracked bytes.
commands = (
    ["git", "diff", "--name-only", "-z"],
    ["git", "diff", "--cached", "--name-only", "-z"],
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
)

changed_paths: set[str] = set()
for command in commands:
    result = subprocess.run(
        command,
        cwd=REPO,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    changed_paths.update(parse_z(result.stdout))

manifest: list[dict[str, object]] = []
with zipfile.ZipFile(
    OUT / "working-tree-files.zip",
    "w",
    compression=zipfile.ZIP_DEFLATED,
) as archive:
    for relative in sorted(changed_paths):
        path = REPO / relative
        if not path.exists():
            manifest.append({
                "path": relative,
                "state": "deleted_or_missing",
            })
            continue
        if not path.is_file():
            manifest.append({
                "path": relative,
                "state": "non_file",
            })
            continue
        data = path.read_bytes()
        archive.writestr(relative, data)
        manifest.append({
            "path": relative,
            "state": "captured",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

write(
    "working-tree-manifest.json",
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
)

# Semantic diff for changed JSON files.
json_report: list[str] = []
for relative in sorted(p for p in changed_paths if p.endswith(".json")):
    path = REPO / relative
    json_report.extend([
        "=" * 78,
        relative,
        "=" * 78,
    ])
    if not path.exists():
        json_report.append("MISSING IN WORKTREE")
        json_report.append("")
        continue

    before = head_json(relative)
    after = load_json(path)
    changes = semantic_diff(before, after)

    if not changes:
        json_report.append("NO SEMANTIC JSON CHANGE")
    else:
        json_report.extend(changes[:250])
        if len(changes) > 250:
            json_report.append(
                f"... {len(changes) - 250} additional changes omitted"
            )
    json_report.append("")

write("json-semantic-diff.txt", "\n".join(json_report) + "\n")

# Task/control checkpoint summary.
interesting_keys = (
    "task_id",
    "title",
    "status",
    "state",
    "phase",
    "milestone",
    "proof_level",
    "achieved_proof_level",
    "current_task_id",
    "last_checkpoint",
    "completed_tasks",
    "executable_tasks",
    "blocked_tasks",
    "dependencies",
    "gates",
    "objective",
    "next_action",
    "rollback",
)

task_paths = (
    "control/CURRENT_STATE.json",
    "control/CURRENT_TASK.json",
    "control/TASK_GRAPH.json",
    "tasks/IDENTITY-001.json",
    "tasks/ECONOMICS-001.json",
    "tasks/SECURITY-001.json",
    "artifacts/task-results/IDENTITY-001.json",
    "artifacts/task-results/ECONOMICS-001.json",
    "artifacts/task-results/SECURITY-001.json",
)

task_summary_lines: list[str] = []
for relative in task_paths:
    task_summary_lines.extend([
        "=" * 78,
        relative,
        "=" * 78,
    ])
    path = REPO / relative
    if not path.exists():
        task_summary_lines.append("MISSING")
        continue
    value = load_json(path)
    if not isinstance(value, dict):
        task_summary_lines.append(
            f"ROOT TYPE: {type(value).__name__}"
        )
        continue
    for key in interesting_keys:
        if key not in value:
            continue
        rendered = json.dumps(value[key], indent=2, sort_keys=True)
        if len(rendered) > 6000:
            rendered = rendered[:6000] + "\n[TRUNCATED]"
        task_summary_lines.append(f"{key}:")
        task_summary_lines.append(rendered)

write("task-checkpoint-summary.txt", "\n".join(task_summary_lines) + "\n")

# Read-only quality checks.
diff_check = run(["git", "diff", "--check"], check=False)
write("git-diff-check.txt", diff_check.stdout + diff_check.stderr)
write("git-diff-check-exit.txt", f"{diff_check.returncode}\n")

conflict_hits: list[str] = []
for relative in sorted(changed_paths):
    path = REPO / relative
    if not path.is_file() or path.stat().st_size > 10_000_000:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if (
            line.startswith("<<<<<<< ")
            or line == "======="
            or line.startswith(">>>>>>> ")
        ):
            conflict_hits.append(f"{relative}:{line_no}:{line[:240]}")

write(
    "conflict-marker-scan.txt",
    ("\n".join(conflict_hits) + "\n")
    if conflict_hits
    else "No conflict markers found.\n",
)

# Inventory recent Antigravity/Gemini state without modifying it.
tool_roots = [
    Path.home() / ".gemini",
    Path.home() / ".config",
    Path.home() / ".local" / "share",
]
tool_records: list[dict[str, object]] = []
cutoff = time.time() - (24 * 60 * 60)

for root in tool_roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        try:
            stat = path.stat()
        except OSError:
            continue
        lower = str(path).lower()
        if not any(term in lower for term in ("antigravity", "gemini", "agy")):
            continue
        if stat.st_mtime < cutoff:
            continue
        tool_records.append({
            "path": str(path),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "size": stat.st_size,
            "modified_epoch": stat.st_mtime,
        })

tool_records.sort(
    key=lambda item: float(item["modified_epoch"]),
    reverse=True,
)
write(
    "recent-antigravity-state.json",
    json.dumps(tool_records[:500], indent=2, sort_keys=True) + "\n",
)

# Verify this audit did not change the repository.
final_head = git("rev-parse", "HEAD").strip()
final_status = git("status", "--porcelain=v1")
source_unchanged = (
    initial_head == final_head
    and initial_status == final_status
)

commits_after = (OUT / "commits-after-baseline.txt").read_text(
    encoding="utf-8"
).strip()
status_text = (OUT / "status.txt").read_text(encoding="utf-8").rstrip()
unstaged = (OUT / "unstaged-name-status.txt").read_text(
    encoding="utf-8"
).strip()
staged = (OUT / "staged-name-status.txt").read_text(
    encoding="utf-8"
).strip()
untracked = (OUT / "untracked-files.txt").read_text(
    encoding="utf-8"
).strip()

summary = f"""CRE POST-GEMINI STATE AUDIT

Audit folder:
{OUT}

SOURCE UNCHANGED BY AUDIT
{source_unchanged}

REPOSITORY
Branch: {branch}
Expected branch: {EXPECTED_BRANCH}
HEAD: {initial_head}
Last verified checkpoint: {BASELINE}
Baseline exists: {baseline_exists}
Baseline is ancestor of HEAD: {baseline_ancestor}

PROTECTED FILES
{json.dumps(protected_results, indent=2, sort_keys=True)}

CURRENT STATUS
{status_text}

COMMITS AFTER LAST VERIFIED CHECKPOINT
{commits_after or "(none, unavailable, or history diverged)"}

UNSTAGED PATHS
{unstaged or "(none)"}

STAGED PATHS
{staged or "(none)"}

UNTRACKED PATHS
{untracked or "(none)"}

CHANGED/UNTRACKED PATH COUNT
{len(changed_paths)}

GIT DIFF CHECK EXIT
{diff_check.returncode}

CONFLICT MARKERS
{("NONE" if not conflict_hits else chr(10).join(conflict_hits))}

DETAILED TASK CHECKPOINT
See:
{OUT / "task-checkpoint-summary.txt"}

SEMANTIC JSON DIFF
See:
{OUT / "json-semantic-diff.txt"}

EXACT WORKTREE BACKUP
{OUT / "working-tree-files.zip"}
"""

write("AUDIT_SUMMARY.txt", summary)

print()
print("POST-GEMINI AUDIT COMPLETE")
print(f"Repository unchanged by audit: {source_unchanged}")
print()
print(summary)
