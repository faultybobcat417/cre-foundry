# Decision Log

## DEC-0001 — Consolidate without modifying originals

The generated repository is a sanitized snapshot. Source repositories and files remain untouched.

## DEC-0002 — Preserve provenance

Every discovered Git repository retains branch, commit, status, and source-path provenance. Histories are preserved locally as bundles.

## DEC-0003 — Do not silently merge architectures

Codex, Kimi, OpenCode, Relay, control-plane, and application work may overlap or conflict. ChatGPT must reconcile them before choosing an authoritative architecture.

## DEC-0004 — Public publication requires review

No automatic GitHub push. Critical files are quarantined and warning findings require human review.
