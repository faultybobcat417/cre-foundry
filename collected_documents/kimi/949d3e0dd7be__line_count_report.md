# CRE Foundry Line Count

Generated: 2026-08-03T18:48:23

## Repository checkpoint

- Repository: `/Users/alimehdi/Documents/cre`
- Branch: `handoff/kimi-architecture-001`
- HEAD: `f47e87defbfff9384d49e6d23c5494c0bdafcf68`
- Git commits: 68

```text
## handoff/kimi-architecture-001
?? control/ONE_SHOT_READINESS.json
```

## Headline totals

| Measure | Files | Physical lines | Nonblank lines | Blank lines |
|---|---:|---:|---:|---:|
| Entire current project text | 671 | 268,440 | 263,886 | 4,554 |
| Code-language files only | 115 | 27,651 | 24,303 | 3,348 |
| Core engineering areas | 385 | 103,360 | 100,685 | 2,675 |

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

| Project area | Files | Physical lines | Nonblank lines | Blank lines |
|---|---:|---:|---:|---:|
| Artifacts and evidence | 131 | 146,005 | 145,168 | 837 |
| Evaluators, tests, fixtures | 274 | 79,352 | 78,215 | 1,137 |
| Bootstrap / imported project OS | 130 | 17,779 | 16,914 | 865 |
| Scripts and validators | 48 | 9,209 | 8,164 | 1,045 |
| Contracts and schemas | 36 | 6,422 | 6,422 | 0 |
| Product source | 19 | 4,564 | 4,081 | 483 |
| Control plane | 8 | 3,813 | 3,803 | 10 |
| Documentation | 8 | 637 | 496 | 141 |
| Other project files | 5 | 362 | 326 | 36 |
| Task specifications | 12 | 297 | 297 | 0 |

## By language/file format

| Language or format | Files | Physical lines | Nonblank lines | Blank lines |
|---|---:|---:|---:|---:|
| JSON | 484 | 229,150 | 229,126 | 24 |
| Python | 110 | 24,807 | 22,085 | 2,722 |
| Markdown | 59 | 11,169 | 10,008 | 1,161 |
| HTML | 4 | 2,806 | 2,186 | 620 |
| Other text | 4 | 378 | 360 | 18 |
| TOML | 9 | 92 | 89 | 3 |
| Shell | 1 | 38 | 32 | 6 |

## Git history activity

| Historical measure | Count |
|---|---:|
| Commits | 68 |
| Cumulative added lines across Git history | 330,076 |
| Cumulative deleted lines across Git history | 61,825 |
| Net historical additions minus deletions | 268,251 |

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

Binary files skipped: 0
Missing/non-file Git paths skipped: 0
