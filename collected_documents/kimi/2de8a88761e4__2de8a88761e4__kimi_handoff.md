# CRE Foundry — Kimi Handoff Snapshot

- Repository: `/Users/alimehdi/Documents/cre`
- Branch: `main`
- HEAD: `aecb0fd68f2a0c722a781edd1a08cff9f59709e4`
- Working tree dirty: `True`
- Active tasks detected: `none detected`
- Completed task count: `0`

## Required Kimi posture

- Treat the repository and Git history as the system of record.
- Do not rerun or replace completed tasks without evaluator evidence.
- Inspect and reconcile all uncommitted ARCHITECTURE-001 work first.
- Preserve synthetic versus empirical proof boundaries.
- Run evaluators before crediting implementation.
- Use parallel agents for read-heavy research and review.
- Use one designated integrator for overlapping writable files.
- Commit only coherent, independently verified checkpoints.

## Snapshot contents

- `backup/repository.bundle`: all committed Git refs and history.
- `backup/working-tree.tar.gz`: current working tree excluding Git metadata and caches.
- `patches/unstaged.patch`: unstaged tracked changes.
- `patches/staged.patch`: staged tracked changes.
- `state/untracked-files.txt`: untracked paths.
- `state/REPO_STATE.json`: machine-readable handoff state.
- `key-files/`: copied control and architecture artifacts.
