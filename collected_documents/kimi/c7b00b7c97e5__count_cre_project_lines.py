#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO = Path("/Users/alimehdi/Documents/cre")
OUTPUT_ROOT = Path.home() / "Desktop"

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".jsonl": "JSONL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".conf": "Config",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".xml": "XML",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hpp": "C/C++ Header",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
}

CODE_LANGUAGES = {
    "Python", "JavaScript", "TypeScript", "Shell", "SQL", "HTML", "CSS",
    "SCSS", "GraphQL", "Protocol Buffers", "C", "C++", "C/C++ Header",
    "Rust", "Go", "Java", "Kotlin", "Swift", "Ruby", "PHP",
}


@dataclass
class FileStat:
    path: str
    category: str
    language: str
    bytes: int
    physical_lines: int
    blank_lines: int
    nonblank_lines: int
    tracked: bool


def run_git(*args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
    )
    return result.stdout


def parse_z(raw: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
    ]


def category_for(path: str) -> str:
    first = path.split("/", 1)[0]
    mapping = {
        "src": "Product source",
        "scripts": "Scripts and validators",
        "evals": "Evaluators, tests, fixtures",
        "tests": "Tests",
        "contracts": "Contracts and schemas",
        "control": "Control plane",
        "tasks": "Task specifications",
        "docs": "Documentation",
        "artifacts": "Artifacts and evidence",
        "bootstrap": "Bootstrap / imported project OS",
        "config": "Configuration",
        ".github": "Repository automation",
    }
    return mapping.get(first, "Other project files")


def language_for(path: Path) -> str:
    name = path.name.lower()
    if name in {"dockerfile", "makefile", "justfile"}:
        return name.capitalize()
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "Other text")


def is_probably_binary(data: bytes) -> bool:
    if b"\x00" in data[:8192]:
        return True
    try:
        data.decode("utf-8")
        return False
    except UnicodeDecodeError:
        try:
            data.decode("latin-1")
            return False
        except UnicodeDecodeError:
            return True


def count_lines(data: bytes) -> tuple[int, int, int]:
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    physical = len(lines)
    blank = sum(1 for line in lines if not line.strip())
    return physical, blank, physical - blank


def fmt_int(value: int) -> str:
    return f"{value:,}"


if not (REPO / ".git").is_dir():
    print(f"Repository not found: {REPO}", file=sys.stderr)
    raise SystemExit(1)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
out_dir = OUTPUT_ROOT / f"CRE-Line-Count-{stamp}"
out_dir.mkdir(parents=True, exist_ok=False)

tracked = set(parse_z(run_git("ls-files", "-z", binary=True)))
untracked = set(
    parse_z(
        run_git(
            "ls-files", "--others", "--exclude-standard", "-z", binary=True
        )
    )
)
all_paths = sorted(tracked | untracked)

stats: list[FileStat] = []
binary_paths: list[str] = []
missing_paths: list[str] = []

for relative in all_paths:
    path = REPO / relative

    if not path.is_file():
        missing_paths.append(relative)
        continue

    data = path.read_bytes()

    if is_probably_binary(data):
        binary_paths.append(relative)
        continue

    physical, blank, nonblank = count_lines(data)
    stats.append(
        FileStat(
            path=relative,
            category=category_for(relative),
            language=language_for(path),
            bytes=len(data),
            physical_lines=physical,
            blank_lines=blank,
            nonblank_lines=nonblank,
            tracked=relative in tracked,
        )
    )

category_totals: dict[str, dict[str, int]] = defaultdict(
    lambda: defaultdict(int)
)
language_totals: dict[str, dict[str, int]] = defaultdict(
    lambda: defaultdict(int)
)

for item in stats:
    for group, key in (
        (category_totals, item.category),
        (language_totals, item.language),
    ):
        group[key]["files"] += 1
        group[key]["bytes"] += item.bytes
        group[key]["physical"] += item.physical_lines
        group[key]["blank"] += item.blank_lines
        group[key]["nonblank"] += item.nonblank_lines

current_totals = {
    "files": len(stats),
    "bytes": sum(item.bytes for item in stats),
    "physical": sum(item.physical_lines for item in stats),
    "blank": sum(item.blank_lines for item in stats),
    "nonblank": sum(item.nonblank_lines for item in stats),
}

code_stats = [item for item in stats if item.language in CODE_LANGUAGES]
core_engineering_categories = {
    "Product source",
    "Scripts and validators",
    "Evaluators, tests, fixtures",
    "Tests",
    "Contracts and schemas",
    "Control plane",
}
core_stats = [
    item for item in stats if item.category in core_engineering_categories
]

def aggregate(items: list[FileStat]) -> dict[str, int]:
    return {
        "files": len(items),
        "bytes": sum(item.bytes for item in items),
        "physical": sum(item.physical_lines for item in items),
        "blank": sum(item.blank_lines for item in items),
        "nonblank": sum(item.nonblank_lines for item in items),
    }

code_totals = aggregate(code_stats)
core_totals = aggregate(core_stats)

# Git history/churn is different from current LOC but useful context.
commit_count = int(run_git("rev-list", "--count", "HEAD").strip())
numstat = run_git("log", "--numstat", "--format=").splitlines()
historical_additions = 0
historical_deletions = 0

for line in numstat:
    parts = line.split("\t")
    if len(parts) < 3:
        continue
    added, deleted = parts[0], parts[1]
    if added.isdigit():
        historical_additions += int(added)
    if deleted.isdigit():
        historical_deletions += int(deleted)

head = run_git("rev-parse", "HEAD").strip()
branch = run_git("branch", "--show-current").strip()
status = run_git("status", "--short", "--branch").rstrip()

with (out_dir / "files.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow([
        "path", "category", "language", "tracked", "bytes",
        "physical_lines", "blank_lines", "nonblank_lines",
    ])
    for item in sorted(stats, key=lambda x: x.path):
        writer.writerow([
            item.path,
            item.category,
            item.language,
            "yes" if item.tracked else "no",
            item.bytes,
            item.physical_lines,
            item.blank_lines,
            item.nonblank_lines,
        ])

def markdown_table(
    totals: dict[str, dict[str, int]],
    first_column: str,
) -> str:
    rows = [
        f"| {first_column} | Files | Physical lines | Nonblank lines | Blank lines |",
        "|---|---:|---:|---:|---:|",
    ]
    ordered = sorted(
        totals.items(),
        key=lambda item: item[1]["physical"],
        reverse=True,
    )
    for name, values in ordered:
        rows.append(
            f"| {name} | {fmt_int(values['files'])} | "
            f"{fmt_int(values['physical'])} | "
            f"{fmt_int(values['nonblank'])} | "
            f"{fmt_int(values['blank'])} |"
        )
    return "\n".join(rows)

report = f"""# CRE Foundry Line Count

Generated: {datetime.now().isoformat(timespec="seconds")}

## Repository checkpoint

- Repository: `{REPO}`
- Branch: `{branch}`
- HEAD: `{head}`
- Git commits: {fmt_int(commit_count)}

```text
{status}
```

## Headline totals

| Measure | Files | Physical lines | Nonblank lines | Blank lines |
|---|---:|---:|---:|---:|
| Entire current project text | {fmt_int(current_totals['files'])} | {fmt_int(current_totals['physical'])} | {fmt_int(current_totals['nonblank'])} | {fmt_int(current_totals['blank'])} |
| Code-language files only | {fmt_int(code_totals['files'])} | {fmt_int(code_totals['physical'])} | {fmt_int(code_totals['nonblank'])} | {fmt_int(code_totals['blank'])} |
| Core engineering areas | {fmt_int(core_totals['files'])} | {fmt_int(core_totals['physical'])} | {fmt_int(core_totals['nonblank'])} | {fmt_int(core_totals['blank'])} |

Definitions:

- **Physical lines**: every line, including comments and blank lines.
- **Nonblank lines**: physical lines minus blank lines; comments are still included.
- **Code-language files**: recognized programming-language files only.
- **Core engineering areas**: `src`, `scripts`, `evals`, `tests`, `contracts`,
  and `control`.
- **Entire current project text**: every Git-tracked and non-ignored untracked
  text file in the current working tree, including documentation, JSON,
  schemas, task specifications, evidence, and bootstrap material.

## By project area

{markdown_table(category_totals, "Project area")}

## By language/file format

{markdown_table(language_totals, "Language or format")}

## Git history activity

| Historical measure | Count |
|---|---:|
| Commits | {fmt_int(commit_count)} |
| Cumulative added lines across Git history | {fmt_int(historical_additions)} |
| Cumulative deleted lines across Git history | {fmt_int(historical_deletions)} |
| Net historical additions minus deletions | {fmt_int(historical_additions - historical_deletions)} |

Historical additions/deletions measure **development churn**, not current
project size. A line modified several times can be counted repeatedly.

## Important interpretation

This report measures the combined repository output regardless of whether a
line was produced through Codex, Kimi, DeepSeek, Gemini, or manual work.

Reliable per-model attribution is generally not possible unless each model's
changes were isolated into dedicated commits or branches with consistent
metadata. Git records commits and authors, not the AI system that generated
each individual line.

## Exclusions

- `.git` internal objects
- Git-ignored environments and caches such as virtual environments,
  `node_modules`, and `__pycache__`
- Binary files
- Recovery folders and exported agent sessions stored outside the repository

Binary files skipped: {fmt_int(len(binary_paths))}
Missing/non-file Git paths skipped: {fmt_int(len(missing_paths))}
"""

(out_dir / "LINE_COUNT_REPORT.md").write_text(report, encoding="utf-8")
(out_dir / "summary.json").write_text(
    json.dumps(
        {
            "repository": str(REPO),
            "branch": branch,
            "head": head,
            "commit_count": commit_count,
            "entire_project": current_totals,
            "code_language_files": code_totals,
            "core_engineering_areas": core_totals,
            "historical_additions": historical_additions,
            "historical_deletions": historical_deletions,
            "binary_files_skipped": binary_paths,
            "missing_paths": missing_paths,
        },
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)

print("CRE LINE COUNT COMPLETE")
print()
print(f"Report: {out_dir / 'LINE_COUNT_REPORT.md'}")
print(f"File details: {out_dir / 'files.csv'}")
print()
print("HEADLINE TOTALS")
print(
    f"Entire project: {fmt_int(current_totals['physical'])} physical lines "
    f"across {fmt_int(current_totals['files'])} text files"
)
print(
    f"Code languages: {fmt_int(code_totals['physical'])} physical lines "
    f"across {fmt_int(code_totals['files'])} files"
)
print(
    f"Core engineering: {fmt_int(core_totals['physical'])} physical lines "
    f"across {fmt_int(core_totals['files'])} files"
)
print(
    f"Git history: {fmt_int(commit_count)} commits, "
    f"{fmt_int(historical_additions)} additions, "
    f"{fmt_int(historical_deletions)} deletions"
)
