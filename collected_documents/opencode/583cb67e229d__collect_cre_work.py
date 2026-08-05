from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

HOME = Path.home().resolve()
OUT_BASE = Path(os.environ["OUT_BASE"]).resolve()
PRIVATE = OUT_BASE / "PRIVATE_ARCHIVE"
PUBLIC = OUT_BASE / "PUBLIC_REPO"
REPORTS = OUT_BASE / "REPORTS"
QUARANTINE = PRIVATE / "QUARANTINE"
BUNDLES = PRIVATE / "GIT_BUNDLES"
PATCHES = PRIVATE / "UNCOMMITTED_PATCHES"
UNTRACKED = PRIVATE / "UNTRACKED_FILES"

for directory in (PRIVATE, PUBLIC, REPORTS, QUARANTINE, BUNDLES, PATCHES, UNTRACKED):
    directory.mkdir(parents=True, exist_ok=True)

ROOT_CANDIDATES = [
    HOME / "Desktop",
    HOME / "Documents",
    HOME / "Projects",
    HOME / "Downloads",
    HOME / "Developer",
    HOME / "Code",
    HOME / "Repos",
    HOME / "src",
    # Agent state is scanned for preservation/inventory, but raw sessions and
    # configuration are never copied into PUBLIC_REPO automatically.
    HOME / ".codex",
    HOME / ".kimi",
    HOME / ".opencode",
    HOME / ".config/opencode",
    HOME / ".local/share/opencode",
]

AGENT_STATE_ROOT_CANDIDATES = [
    HOME / ".codex",
    HOME / ".kimi",
    HOME / ".opencode",
    HOME / ".config/opencode",
    HOME / ".local/share/opencode",
]
AGENT_STATE_ROOTS = [p.resolve() for p in AGENT_STATE_ROOT_CANDIDATES if p.is_dir()]
AGENT_STATE_ARCHIVE = PRIVATE / "AGENT_STATE"
AGENT_STATE_ARCHIVE.mkdir(parents=True, exist_ok=True)

EXPLICIT_CANDIDATES = [
    HOME / "Projects/comfiance/cre-foundry",
    HOME / "Documents/cre",
    HOME / "Desktop/CRE-Relay-Security-Standalone",
    HOME / "Desktop/CRE-Relay-S",
    HOME / "Desktop/CRE-Relay",
]

ROOTS = []
seen_roots = set()
for path in ROOT_CANDIDATES:
    if path.is_dir():
        real = path.resolve()
        if real not in seen_roots:
            seen_roots.add(real)
            ROOTS.append(real)

PRUNE_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".cache",
    "Library",
    "Applications",
    "Movies",
    "Music",
    "Pictures",
    "dist",
    "build",
    "target",
    ".next",
    ".turbo",
    "coverage",
    "htmlcov",
}

IGNORE_FILES = {
    ".DS_Store",
    "Thumbs.db",
}

TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".py", ".pyi", ".sh", ".bash", ".zsh",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".csv", ".tsv", ".sql", ".html", ".htm", ".css", ".js", ".jsx",
    ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".go", ".rs",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".xml", ".graphql", ".gql", ".proto", ".properties", ".env.example",
}

SAFE_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
}

PRIVATE_ONLY_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt",
    ".duckdb", ".sqlite", ".sqlite3", ".db",
    ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar",
    ".bundle", ".pem", ".key", ".p12", ".pfx",
}

KEYWORDS = {
    "cre", "cre-foundry", "foundry", "comfiance", "commercial-real-estate",
    "commercial_real_estate", "brampton", "codex", "kimi", "opencode",
    "open-code", "relay", "antigravity", "security-001", "identity-001",
    "economics-001", "one-shot", "one_shot", "tip-sheet", "tip_sheet",
}

CONTENT_MARKERS = [
    "CRE Foundry",
    "Commercial Real Estate",
    "SECURITY-001",
    "IDENTITY-001",
    "ECONOMICS-001",
    "ONE_SHOT_READINESS",
    "Codex handoff",
    "Kimi",
    "OpenCode",
    "ComFiance",
    "Brampton permit",
    "ABSTAIN_NO_VALID_TEN",
    "pilot-readiness",
    "evaluator-first",
]

KNOWN_PROTECTED_PATH_PARTS = {
    "control/ONE_SHOT_READINESS.json",
}

MAX_PUBLIC_TEXT_BYTES = 12 * 1024 * 1024
MAX_PUBLIC_BINARY_BYTES = 8 * 1024 * 1024
MAX_CONTENT_SCAN_BYTES = 512 * 1024

HIGH_CONFIDENCE_SECRET_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-=]{20,}\b", re.I)),
    (
        "credential_assignment",
        re.compile(
            r"""(?ix)
            \b(password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|
            refresh[_-]?token|authorization)\b
            \s*[:=]\s*
            ["'][^"'\n]{6,}["']
            """
        ),
    ),
]

WARNING_PATTERNS = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"(?:\+?1[-. ]?)?\(?[2-9][0-9]{2}\)?[-. ][0-9]{3}[-. ][0-9]{4}")),
    ("absolute_home_path", re.compile(r"/Users/[^/\s]+")),
    ("possible_password_word", re.compile(r"\b(password|passwd|secret|token|credential)\b", re.I)),
]

@dataclass
class RepoRecord:
    source_path: str
    category: str
    slug: str
    branch: str
    head: str
    commit_date: str
    dirty: bool
    status_summary: str
    public_copy: str
    private_bundle: str
    copy_errors: int
    quarantined_files: int

@dataclass
class FileRecord:
    source_path: str
    category: str
    sha256: str
    size: int
    disposition: str
    destination: str
    reason: str

repo_records: list[RepoRecord] = []
file_records: list[FileRecord] = []
critical_findings: list[dict] = []
warning_findings: list[dict] = []
copy_errors: list[dict] = []
duplicate_sources: defaultdict[str, list[str]] = defaultdict(list)

def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )

def safe_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.name

def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    return value.strip("-") or "source"

def unique_slug(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def read_text_sample(path: Path, max_bytes: int = MAX_CONTENT_SCAN_BYTES) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes)
        if b"\x00" in raw:
            return ""
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""

def classify_origin(path: Path, sample: str = "") -> str:
    combined = f"{path.as_posix()} {sample[:100000]}".lower()
    if "opencode" in combined or "open-code" in combined:
        return "opencode"
    if "kimi" in combined:
        return "kimi"
    if "codex" in combined:
        return "codex"
    if "antigravity" in combined:
        return "antigravity"
    if "relay" in combined:
        return "relay"
    if "security-001" in combined or "identity-001" in combined or "economics-001" in combined:
        return "control-plane"
    if "cre-foundry" in combined or "comfiance" in combined or "brampton" in combined:
        return "application"
    if "commercial real estate" in combined or "cre foundry" in combined:
        return "research"
    return "unclassified"

def candidate_score(path: Path, sample: str = "") -> int:
    p = path.as_posix().lower()
    score = sum(1 for keyword in KEYWORDS if keyword in p)
    sample_lower = sample.lower()
    score += sum(2 for marker in CONTENT_MARKERS if marker.lower() in sample_lower)
    return score

def inspect_text_for_safety(path: Path, text: str) -> tuple[list[str], list[str]]:
    critical = []
    warnings = []
    normalized = path.as_posix()
    if any(part in normalized for part in KNOWN_PROTECTED_PATH_PARTS):
        critical.append("protected_control_file")
    for name, pattern in HIGH_CONFIDENCE_SECRET_PATTERNS:
        if pattern.search(text):
            critical.append(name)
    for name, pattern in WARNING_PATTERNS:
        if pattern.search(text):
            warnings.append(name)
    return sorted(set(critical)), sorted(set(warnings))

def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False

def agent_state_root_for(path: Path) -> Path | None:
    for root in AGENT_STATE_ROOTS:
        if is_under(path, root):
            return root
    return None

def preserve_agent_state_file(source: Path, root: Path) -> Path:
    rel = source.resolve().relative_to(root.resolve())
    destination = AGENT_STATE_ARCHIVE / slugify(root.as_posix()) / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination

def discover_git_repos() -> list[Path]:
    repos: set[Path] = set()

    for explicit in EXPLICIT_CANDIDATES:
        if (explicit / ".git").exists():
            repos.add(explicit.resolve())

    for root in ROOTS:
        for current, dirs, files in os.walk(root, topdown=True):
            current_path = Path(current)
            dirs[:] = [
                d for d in dirs
                if d not in PRUNE_DIRS
                and not d.startswith(".")
            ]
            if ".git" in os.listdir(current):
                repo = current_path.resolve()
                readme_sample = ""
                for name in ("README.md", "AGENTS.md", "pyproject.toml"):
                    candidate = repo / name
                    if candidate.is_file():
                        readme_sample += read_text_sample(candidate, 100000)
                if candidate_score(repo, readme_sample) > 0:
                    repos.add(repo)
                dirs[:] = []
                continue
    return sorted(repos)

def git_metadata(repo: Path) -> dict[str, str | bool]:
    branch = run(["git", "branch", "--show-current"], repo).stdout.strip() or "(detached)"
    head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    commit_date = run(["git", "show", "-s", "--format=%cI", "HEAD"], repo).stdout.strip()
    status = run(["git", "status", "--short", "--branch"], repo).stdout.strip()
    dirty_lines = [
        line for line in status.splitlines()
        if line and not line.startswith("##")
    ]
    return {
        "branch": branch,
        "head": head,
        "commit_date": commit_date,
        "status": status,
        "dirty": bool(dirty_lines),
    }

def path_is_excluded(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in PRUNE_DIRS for part in parts):
        return True
    if rel in KNOWN_PROTECTED_PATH_PARTS:
        return True
    lowered = rel.lower()
    excluded_prefixes = (
        "data/raw/", "data/private/", "data/warehouse/",
        "outputs/", "private/", "restricted/", "client_material/",
        "partial-security-work/",
    )
    if lowered.startswith(excluded_prefixes):
        return True
    if Path(rel).name in IGNORE_FILES:
        return True
    return False

def copy_public_file(source: Path, destination: Path, source_label: str) -> tuple[str, str]:
    try:
        rel_norm = destination.as_posix()
        ext = source.suffix.lower()
        size = source.stat().st_size

        agent_root = agent_state_root_for(source)
        if agent_root is not None:
            private_destination = preserve_agent_state_file(source, agent_root)
            return "private_agent_state", f"preserved_at:{private_destination}"

        if path_is_excluded(source_label):
            return "excluded", "excluded_path_policy"

        if ext in PRIVATE_ONLY_EXTENSIONS:
            return "private_only", f"private_only_extension:{ext}"

        if ext in TEXT_EXTENSIONS or source.name in {
            "README", "LICENSE", "Makefile", "Dockerfile", "Procfile", ".gitignore", ".dockerignore"
        }:
            if size > MAX_PUBLIC_TEXT_BYTES:
                return "private_only", "text_file_too_large"
            text = read_text_sample(source, MAX_PUBLIC_TEXT_BYTES + 1)
            critical, warnings = inspect_text_for_safety(source, text)
            if critical:
                qdest = QUARANTINE / source_label
                qdest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, qdest)
                critical_findings.append(
                    {"path": source_label, "findings": critical, "quarantine": str(qdest)}
                )
                return "quarantined", ",".join(critical)
            if warnings:
                warning_findings.append({"path": source_label, "findings": warnings})
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return "public", ""
        elif ext in SAFE_BINARY_EXTENSIONS:
            if size > MAX_PUBLIC_BINARY_BYTES:
                return "private_only", "binary_file_too_large"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return "public_binary", ""
        else:
            return "private_only", f"unreviewed_extension:{ext or '(none)'}"
    except Exception as exc:
        copy_errors.append({"source": str(source), "destination": str(destination), "error": repr(exc)})
        return "error", repr(exc)

def preserve_repo_private(repo: Path, slug: str) -> tuple[str, str]:
    bundle_path = BUNDLES / f"{slug}.bundle"
    patch_path = PATCHES / f"{slug}.patch"

    bundle = run(["git", "bundle", "create", str(bundle_path), "--all"], repo)
    if bundle.returncode != 0:
        bundle_path.write_text(
            f"Bundle creation failed:\n{bundle.stderr}\n",
            encoding="utf-8",
        )

    unstaged = run(["git", "diff", "--binary"], repo).stdout
    staged = run(["git", "diff", "--cached", "--binary"], repo).stdout
    patch_path.write_text(
        "# UNSTAGED\n" + unstaged + "\n# STAGED\n" + staged,
        encoding="utf-8",
    )

    untracked_result = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo)
    if untracked_result.returncode == 0:
        for rel in [x for x in untracked_result.stdout.split("\0") if x]:
            source = repo / rel
            if source.is_file():
                dest = UNTRACKED / slug / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(source, dest)
                except Exception as exc:
                    copy_errors.append({"source": str(source), "destination": str(dest), "error": repr(exc)})

    return str(bundle_path), str(patch_path)

def copy_repo_public(repo: Path, category: str, slug: str) -> tuple[Path, int, int]:
    target = PUBLIC / "sources" / category / slug
    target.mkdir(parents=True, exist_ok=True)
    errors_before = len(copy_errors)
    quarantine_before = len(critical_findings)

    for current, dirs, files in os.walk(repo, topdown=True):
        current_path = Path(current)
        rel_dir = safe_rel(current_path, repo)
        dirs[:] = [
            d for d in dirs
            if d not in PRUNE_DIRS
            and not d.startswith(".git")
            and not path_is_excluded(f"{rel_dir}/{d}".lstrip("./"))
        ]
        for name in files:
            source = current_path / name
            rel = safe_rel(source, repo)
            if path_is_excluded(rel):
                continue
            destination = target / rel
            disposition, reason = copy_public_file(source, destination, f"repos/{slug}/{rel}")
            if disposition != "public" and disposition != "public_binary":
                try:
                    digest = sha256_file(source)
                    size = source.stat().st_size
                except Exception:
                    digest = ""
                    size = 0
                file_records.append(
                    FileRecord(
                        source_path=str(source),
                        category=category,
                        sha256=digest,
                        size=size,
                        disposition=disposition,
                        destination=str(destination) if disposition.startswith("public") else "",
                        reason=reason,
                    )
                )

    return target, len(copy_errors) - errors_before, len(critical_findings) - quarantine_before

def discover_loose_files(repos: list[Path]) -> list[Path]:
    found: list[Path] = []
    repo_roots = [repo.resolve() for repo in repos]

    for root in ROOTS:
        for current, dirs, files in os.walk(root, topdown=True):
            current_path = Path(current)
            dirs[:] = [
                d for d in dirs
                if d not in PRUNE_DIRS
                and not d.startswith(".")
            ]
            if any(is_under(current_path, repo) for repo in repo_roots):
                dirs[:] = []
                continue

            for name in files:
                path = current_path / name
                if name in IGNORE_FILES:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size > MAX_PUBLIC_TEXT_BYTES:
                    continue
                ext = path.suffix.lower()
                if ext not in TEXT_EXTENSIONS and ext not in SAFE_BINARY_EXTENSIONS:
                    continue

                path_score = candidate_score(path)
                sample = ""
                if ext in TEXT_EXTENSIONS:
                    sample = read_text_sample(path)
                score = path_score + candidate_score(path, sample)

                if score > 0:
                    found.append(path.resolve())

    return sorted(set(found))

def write_csv(path: Path, rows: Iterable[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def sanitize_home(value: str) -> str:
    return value.replace(str(HOME), "~")

def generate_root_docs() -> None:
    category_counts = defaultdict(int)
    for record in repo_records:
        category_counts[record.category] += 1
    for record in file_records:
        if record.disposition.startswith("public"):
            category_counts[record.category] += 1

    repo_table = "\n".join(
        f"| `{r.slug}` | {r.category} | `{sanitize_home(r.source_path)}` | "
        f"`{r.branch}` | `{r.head[:12]}` | {'dirty' if r.dirty else 'clean'} |"
        for r in repo_records
    ) or "| None | - | - | - | - | - |"

    readme = f"""# CRE Foundry Unified Working Repository

This repository was generated from the actual Codex, Kimi, OpenCode, Relay,
Antigravity, research, checkpoint, prompt, and local repository files discovered
on the project owner's Mac.

## Truth status

This is a **consolidated snapshot**, not proof that all discovered repositories
are one integrated system. Original repositories were not modified. Previous
Git histories were preserved locally under `PRIVATE_ARCHIVE`, not imported into
this public working repository.

## Start here

1. `00_INDEX/MASTER_INDEX.md`
2. `00_INDEX/CHATGPT_READING_ORDER.md`
3. `00_INDEX/REPOSITORY_MAP.md`
4. `00_INDEX/AGENT_WORK_MAP.md`
5. `00_INDEX/PUBLICATION_BLOCKERS.md`
6. `governance/FIXED_MISSION.md`
7. `research/RESEARCH_COVERAGE_MATRIX.md`
8. `handoff/CONTINUATION_PACKET.md`

## Discovered repositories

| Repository | Category | Original path | Branch | HEAD | State |
|---|---|---|---|---|---|
{repo_table}

## Hard restraints

- No production ranking claim.
- No outreach authorization.
- No claim of proven live commercial lift.
- No hidden/private institutional knowledge claims.
- No automatic GitHub push.
- No secret, credential, private client data, or protected control file may be published.

## Generated

- UTC: {datetime.now(timezone.utc).isoformat()}
- Repository count: {len(repo_records)}
- Candidate loose-file records: {len(file_records)}
- Critical quarantines: {len(critical_findings)}
- Warning findings: {len(warning_findings)}
"""
    (PUBLIC / "README.md").write_text(readme, encoding="utf-8")

    index_dir = PUBLIC / "00_INDEX"
    index_dir.mkdir(parents=True, exist_ok=True)

    master = f"""# Master Index

## Purpose

Give ChatGPT and coding agents a fast, truthful map of all discovered project work.

## Repository counts by source family

{os.linesep.join(f"- {key}: {value}" for key, value in sorted(category_counts.items())) or "- None"}

## Key machine-generated reports

- `REPOSITORY_MAP.md`
- `AGENT_WORK_MAP.md`
- `DUPLICATES.md`
- `PUBLICATION_BLOCKERS.md`
- `../reports/REPOSITORIES.csv`
- `../reports/FILES.csv`
- `../reports/CRITICAL_FINDINGS.json`
- `../reports/WARNINGS.json`

## Source trees

All sanitized source snapshots are under `../sources/`.

Do not assume two sources are compatible merely because they concern the same mission.
Use provenance, branch, commit, task state, tests, and architecture evidence.
"""
    (index_dir / "MASTER_INDEX.md").write_text(master, encoding="utf-8")

    order = """# ChatGPT Reading Order

1. `../README.md`
2. `MASTER_INDEX.md`
3. `REPOSITORY_MAP.md`
4. `AGENT_WORK_MAP.md`
5. `PUBLICATION_BLOCKERS.md`
6. `../governance/FIXED_MISSION.md`
7. `../governance/AUTONOMY_POLICY.md`
8. `../research/RESEARCH_COVERAGE_MATRIX.md`
9. `../decisions/DECISION_LOG.md`
10. `../risks/RISK_REGISTER.md`
11. `../handoff/CONTINUATION_PACKET.md`
12. Each `SOURCE_PROVENANCE.md` under `../sources/`
13. Existing `AGENTS.md`, `README.md`, task, control, evaluator, and handoff files inside each source.

After reading, reconcile contradictions before proposing changes.
"""
    (index_dir / "CHATGPT_READING_ORDER.md").write_text(order, encoding="utf-8")

    repo_map_lines = ["# Repository Map", ""]
    for r in repo_records:
        repo_map_lines += [
            f"## {r.slug}",
            "",
            f"- Category: `{r.category}`",
            f"- Original path: `{sanitize_home(r.source_path)}`",
            f"- Branch: `{r.branch}`",
            f"- HEAD: `{r.head}`",
            f"- Commit date: `{r.commit_date}`",
            f"- Dirty at collection: `{r.dirty}`",
            f"- Public snapshot: `{sanitize_home(r.public_copy)}`",
            "",
        ]
    (index_dir / "REPOSITORY_MAP.md").write_text("\n".join(repo_map_lines), encoding="utf-8")

    agent_map = ["# Agent Work Map", ""]
    categories = sorted(set([r.category for r in repo_records] + [f.category for f in file_records]))
    for category in categories:
        repos = [r for r in repo_records if r.category == category]
        docs = [f for f in file_records if f.category == category and f.disposition.startswith("public")]
        agent_map += [
            f"## {category}",
            "",
            f"- Repositories: {len(repos)}",
            f"- Collected loose/public files: {len(docs)}",
        ]
        for r in repos:
            agent_map.append(f"- Repo: `{r.slug}` at `{r.head[:12]}`")
        agent_map.append("")
    (index_dir / "AGENT_WORK_MAP.md").write_text("\n".join(agent_map), encoding="utf-8")

    duplicate_lines = ["# Duplicate Files", ""]
    groups = [(digest, paths) for digest, paths in duplicate_sources.items() if len(paths) > 1]
    if not groups:
        duplicate_lines.append("No duplicate groups were detected among collected loose files.")
    else:
        for digest, paths in sorted(groups, key=lambda item: (-len(item[1]), item[0])):
            duplicate_lines += [f"## `{digest}`", ""]
            duplicate_lines += [f"- `{sanitize_home(p)}`" for p in paths]
            duplicate_lines.append("")
    (index_dir / "DUPLICATES.md").write_text("\n".join(duplicate_lines), encoding="utf-8")

    blockers = [
        "# Publication Blockers",
        "",
        f"- Critical quarantined files: **{len(critical_findings)}**",
        f"- Warning records requiring human review: **{len(warning_findings)}**",
        f"- Copy errors: **{len(copy_errors)}**",
        "",
    ]
    if critical_findings:
        blockers += [
            "## Critical",
            "",
            "The public repository must not be pushed until every critical finding is reviewed.",
            "",
        ]
        for item in critical_findings:
            blockers.append(f"- `{sanitize_home(item['path'])}` — {', '.join(item['findings'])}")
    else:
        blockers += ["## Critical", "", "No high-confidence secret pattern was copied into the public tree.", ""]

    if warning_findings:
        blockers += ["## Warnings", ""]
        for item in warning_findings[:500]:
            blockers.append(f"- `{sanitize_home(item['path'])}` — {', '.join(item['findings'])}")
        if len(warning_findings) > 500:
            blockers.append(f"- Additional warnings omitted here; inspect `../reports/WARNINGS.json`.")
    else:
        blockers += ["## Warnings", "", "No warning patterns were detected.", ""]

    (index_dir / "PUBLICATION_BLOCKERS.md").write_text("\n".join(blockers), encoding="utf-8")

def write_policy_docs() -> None:
    (PUBLIC / "governance").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "research").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "decisions").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "risks").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "handoff").mkdir(parents=True, exist_ok=True)

    (PUBLIC / "governance/FIXED_MISSION.md").write_text("""# Fixed Mission

Select exactly ten valid physical businesses or operating locations per representative-day to maximize:

1. incremental probability of a booked appointment with a senior commercial realtor;
2. expected commercial value;
3. useful information gained from field activity;
4. route and operating feasibility;
5. evidence quality, legality, traceability, and institutional defensibility.

If ten valid recommendations cannot be supported, issue a truthful abstention state such as `ABSTAIN_NO_VALID_TEN`.

The realtor-client outcome remains primary. Recruiter value comes from institutional-quality formulation, validation, engineering, governance, and execution—not from changing the client mission.
""", encoding="utf-8")

    (PUBLIC / "governance/AUTONOMY_POLICY.md").write_text("""# Autonomy Policy

Agents may improve research, assumptions, methods, architecture, schemas, tests, metrics, workflow, and backlog ordering when stronger evidence supports the change.

Agents may not silently change the fixed mission, fabricate evidence, erase history, approve their own material changes without independent challenge, enable live actions without authorization, expose private information, or present simulated/shadow results as live proof.

Resolve ordinary ambiguity using the least-destructive, reversible, fail-closed option and record the assumption.
""", encoding="utf-8")

    (PUBLIC / "research/RESEARCH_COVERAGE_MATRIX.md").write_text("""# Research Coverage Matrix

This file must be updated after ChatGPT reconciles the collected repositories and documents.

| Workstream | Initial status |
|---|---|
| Repository and agent-work reconciliation | IN_PROGRESS |
| Fixed objective and constraints | PARTIAL |
| Institutional frontier research | PARTIAL |
| CRE mechanisms and signals | PARTIAL |
| Ontario source landscape | PARTIAL |
| Point-in-time reconstruction | PARTIAL |
| Entity resolution and temporal ontology | PARTIAL |
| Baseline model tournament | NOT_STARTED |
| Survival and event timing | NOT_STARTED |
| Causal uplift and experiments | NOT_STARTED |
| Sequential learning | NOT_STARTED |
| Exactly-ten optimization | PARTIAL |
| Uncertainty and abstention | PARTIAL |
| Agentic research and evaluation | PARTIAL |
| MLOps, security and model governance | NEEDS_RECONCILIATION |
| Coding-agent handoff | PARTIAL |
| Live field validation | NOT_STARTED |
""", encoding="utf-8")

    (PUBLIC / "decisions/DECISION_LOG.md").write_text("""# Decision Log

## DEC-0001 — Consolidate without modifying originals

The generated repository is a sanitized snapshot. Source repositories and files remain untouched.

## DEC-0002 — Preserve provenance

Every discovered Git repository retains branch, commit, status, and source-path provenance. Histories are preserved locally as bundles.

## DEC-0003 — Do not silently merge architectures

Codex, Kimi, OpenCode, Relay, control-plane, and application work may overlap or conflict. ChatGPT must reconcile them before choosing an authoritative architecture.

## DEC-0004 — Public publication requires review

No automatic GitHub push. Critical files are quarantined and warning findings require human review.
""", encoding="utf-8")

    (PUBLIC / "risks/RISK_REGISTER.md").write_text("""# Risk Register

| Risk | Severity | Control |
|---|---|---|
| Secret or credential publication | Critical | High-confidence scan and quarantine |
| Client/private data publication | Critical | Warnings, exclusions, human review |
| Conflicting agent architectures treated as unified | High | Provenance and reconciliation |
| Uncommitted work lost | High | Local bundles, patches, and untracked preservation |
| Old history contains sensitive content | High | New public Git history only |
| Shadow/simulated results overstated | High | Evidence-class requirement |
| Protected control file published | Critical | Explicit exclusion and quarantine |
""", encoding="utf-8")

    (PUBLIC / "handoff/CONTINUATION_PACKET.md").write_text(f"""# Continuation Packet

## Generated

{datetime.now(timezone.utc).isoformat()}

## Current phase

Consolidate and reconcile actual Codex, Kimi, OpenCode, Relay, Antigravity, research, prompt, checkpoint, and repository work from the owner's Mac.

## Completed

- Discovered relevant Git repositories.
- Preserved source histories in local private bundles.
- Preserved uncommitted diffs and untracked files locally.
- Copied sanitized current source trees.
- Collected relevant loose text/code files.
- Generated repository, agent, duplicate, and safety maps.
- Quarantined high-confidence sensitive files.

## Next exact action

1. Read `00_INDEX/PUBLICATION_BLOCKERS.md`.
2. Review all critical and warning findings.
3. Inspect every source provenance record.
4. Resolve duplicate or conflicting repositories.
5. Run each source repository's own tests at its recorded commit/state.
6. Update the research coverage matrix.
7. Only then create and push a public GitHub repository.
8. Give ChatGPT the public URL and order it to reconcile before researching.
""", encoding="utf-8")

def write_source_provenance(target: Path, repo: Path, metadata: dict) -> None:
    provenance = f"""# Source Provenance

- Original path: `{sanitize_home(str(repo))}`
- Category: `{classify_origin(repo)}`
- Branch: `{metadata['branch']}`
- HEAD: `{metadata['head']}`
- Commit date: `{metadata['commit_date']}`
- Dirty at collection: `{metadata['dirty']}`

## Git status at collection

```text
{metadata['status']}
```

This is a sanitized current-tree snapshot. Original Git history is preserved only in the local private archive.
"""
    (target / "SOURCE_PROVENANCE.md").write_text(provenance, encoding="utf-8")

def collect() -> int:
    print("Discovering relevant Git repositories...", flush=True)
    repos = discover_git_repos()
    print(f"Discovered {len(repos)} repositories.", flush=True)

    used_slugs: set[str] = set()

    for index, repo in enumerate(repos, start=1):
        print(f"[repo {index}/{len(repos)}] {repo}", flush=True)
        try:
            metadata = git_metadata(repo)
        except Exception as exc:
            copy_errors.append({"source": str(repo), "destination": "", "error": f"metadata: {exc!r}"})
            continue

        sample = ""
        for name in ("README.md", "AGENTS.md", "pyproject.toml"):
            candidate = repo / name
            if candidate.is_file():
                sample += read_text_sample(candidate, 100000)

        category = classify_origin(repo, sample)
        slug = unique_slug(slugify(repo.name), used_slugs)

        bundle_path, patch_path = preserve_repo_private(repo, slug)
        target, error_count, quarantine_count = copy_repo_public(repo, category, slug)
        write_source_provenance(target, repo, metadata)

        repo_records.append(
            RepoRecord(
                source_path=str(repo),
                category=category,
                slug=slug,
                branch=str(metadata["branch"]),
                head=str(metadata["head"]),
                commit_date=str(metadata["commit_date"]),
                dirty=bool(metadata["dirty"]),
                status_summary=str(metadata["status"]),
                public_copy=str(target),
                private_bundle=bundle_path,
                copy_errors=error_count,
                quarantined_files=quarantine_count,
            )
        )

    print("Discovering relevant loose files...", flush=True)
    loose_files = discover_loose_files(repos)
    print(f"Discovered {len(loose_files)} loose candidate files.", flush=True)

    copied_digests: dict[str, Path] = {}
    for index, source in enumerate(loose_files, start=1):
        if index % 100 == 0:
            print(f"[loose {index}/{len(loose_files)}]", flush=True)

        try:
            digest = sha256_file(source)
            size = source.stat().st_size
        except Exception as exc:
            copy_errors.append({"source": str(source), "destination": "", "error": repr(exc)})
            continue

        duplicate_sources[digest].append(str(source))
        sample = read_text_sample(source) if source.suffix.lower() in TEXT_EXTENSIONS else ""
        category = classify_origin(source, sample)

        if digest in copied_digests:
            file_records.append(
                FileRecord(
                    source_path=str(source),
                    category=category,
                    sha256=digest,
                    size=size,
                    disposition="duplicate",
                    destination=str(copied_digests[digest]),
                    reason="same_sha256",
                )
            )
            continue

        destination = PUBLIC / "collected_documents" / category / f"{digest[:12]}__{slugify(source.name)}"
        disposition, reason = copy_public_file(
            source,
            destination,
            f"loose/{category}/{digest[:12]}__{source.name}",
        )

        if disposition.startswith("public"):
            copied_digests[digest] = destination

        file_records.append(
            FileRecord(
                source_path=str(source),
                category=category,
                sha256=digest,
                size=size,
                disposition=disposition,
                destination=str(destination) if disposition.startswith("public") else "",
                reason=reason,
            )
        )

    write_policy_docs()
    generate_root_docs()

    reports_target = PUBLIC / "reports"
    reports_target.mkdir(parents=True, exist_ok=True)

    write_csv(
        reports_target / "REPOSITORIES.csv",
        [asdict(record) for record in repo_records],
        list(RepoRecord.__dataclass_fields__.keys()),
    )
    write_csv(
        reports_target / "FILES.csv",
        [asdict(record) for record in file_records],
        list(FileRecord.__dataclass_fields__.keys()),
    )

    for path, payload in [
        (reports_target / "CRITICAL_FINDINGS.json", critical_findings),
        (reports_target / "WARNINGS.json", warning_findings),
        (reports_target / "COPY_ERRORS.json", copy_errors),
    ]:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    private_manifest = {
        "schema": "cre-foundry-private-consolidation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots_searched": [sanitize_home(str(root)) for root in ROOTS],
        "repo_count": len(repo_records),
        "loose_file_count": len(file_records),
        "critical_findings": len(critical_findings),
        "warnings": len(warning_findings),
        "copy_errors": len(copy_errors),
        "repositories": [asdict(record) for record in repo_records],
    }
    (REPORTS / "MASTER_MANIFEST.json").write_text(
        json.dumps(private_manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    # Final public critical scan over copied text files.
    copied_critical = []
    for current, dirs, files in os.walk(PUBLIC):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() not in TEXT_EXTENSIONS and name not in {
                "README.md", "AGENTS.md", "Makefile", ".gitignore"
            }:
                continue
            text = read_text_sample(path, MAX_PUBLIC_TEXT_BYTES + 1)
            critical, _ = inspect_text_for_safety(path, text)
            if critical:
                copied_critical.append({"path": str(path), "findings": critical})

    (reports_target / "FINAL_PUBLIC_SCAN.json").write_text(
        json.dumps(copied_critical, indent=2) + "\n",
        encoding="utf-8",
    )

    if copied_critical:
        print("\nFINAL PUBLIC SCAN FAILED.", file=sys.stderr)
        print(f"{len(copied_critical)} critical finding(s) remain in PUBLIC_REPO.", file=sys.stderr)
        print(f"Review: {reports_target / 'FINAL_PUBLIC_SCAN.json'}", file=sys.stderr)
        return 1

    # Create a fresh Git repository only after critical scan passes.
    run(["git", "init"], PUBLIC)
    run(["git", "add", "."], PUBLIC)

    # Commit may fail when Git identity is not configured; organization is still valid.
    commit = run(["git", "commit", "-m", "Consolidate CRE Foundry agent work"], PUBLIC)
    if commit.returncode != 0:
        (REPORTS / "GIT_COMMIT_NOTE.txt").write_text(
            "Fresh Git repository was initialized and files were staged, but the local "
            "commit failed. Configure git user.name and user.email, then commit manually.\n\n"
            + commit.stderr,
            encoding="utf-8",
        )

    print("\nCRE FOUNDRY CONSOLIDATION COMPLETE")
    print(f"Output:          {OUT_BASE}")
    print(f"Public repo:     {PUBLIC}")
    print(f"Private archive: {PRIVATE}")
    print(f"Reports:         {REPORTS}")
    print(f"Repositories:    {len(repo_records)}")
    print(f"Loose records:   {len(file_records)}")
    print(f"Quarantined:     {len(critical_findings)}")
    print(f"Warnings:        {len(warning_findings)}")
    print("\nNothing was pushed. Original files and repositories were not modified.")
    print(f"\nREAD FIRST:\n  {PUBLIC / '00_INDEX/PUBLICATION_BLOCKERS.md'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(collect())
