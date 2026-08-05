# Decisions

## DEC-BOOT-001 — retain the Project OS under bootstrap

The verified all-in-one archive is retained under `bootstrap/project_os_v2.2`
as the repository-owned launch authority and reference vault. Application code
and evidence live at repository root, preventing packaged synthetic artifacts
from being mistaken for application proof.

Rollback: restore the archive using its recorded SHA-256.

## DEC-RUNTIME-001 — Python 3.12 control-plane baseline

The host default is unpinned Anaconda Python 3.9.12, while multiple modern
interpreters are installed. The initial repository commands use `uv` and Python
3.12. This is reversible and does not freeze the eventual database or service
architecture.

Alternatives considered: inherit global Python 3.9 (rejected as unpinned and
stale), use Python 3.14 (rejected as a compatibility-leading edge), or start
polyglot (rejected before a measured need).

## DEC-EVAL-001 — split evaluator topology

Best-of-N compared an encrypted in-repository capsule, a separate evaluator
repository, and a black-box evaluator service. A custodian-owned separate
repository is the strongest practical greenfield choice. The local public
evaluator is installed now; sealed custody and the external hidden holdout are
separate open gates and are not claimed.

## DEC-TASK-001 — select RESEARCH-001

EVAL-001 is correctly blocked until an independent custodian and external
sealed path exist. RESEARCH-001 has no external gate and can close public
source/mechanism questions while preserving all claim ceilings. MATH-001 is
instantiated but waits for accepted research and sealed evaluator custody.
