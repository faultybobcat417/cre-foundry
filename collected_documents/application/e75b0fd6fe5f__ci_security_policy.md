# CI Security Policy

## Permissions

Every workflow and job must declare explicit permissions. The default
security workflow grants only `contents: read`. Write permissions, broad
tokens and implicit privilege inheritance are forbidden.

## Action pinning

Every third-party action must be pinned to a complete immutable commit SHA.
Mutable version tags and branch names are not acceptable execution
references. Human-readable release comments may accompany the SHA.

## Checkout

Repository checkout must disable credential persistence. Full history is
required only for the governed Git-history secret scan.

## Dependency installation

CI must use the committed lock file:

    uv sync --locked --all-groups

Unpinned dependency installation and lock-file mutation are forbidden.

## Security enforcement

CI runs:

    ./scripts/security_scan.sh --enforce

Scanner execution failures, invalid suppressions, SBOM drift, CI-policy
violations and unresolved blocking findings fail the job.

## Claims boundary

A passing CI security job does not establish production readiness,
certification, regulatory compliance, model validity or positive ROI.

## Temporary open-finding ratchet

While the reviewed B608 baseline is being remediated, CI performs three
separate operations:

    ./scripts/security_scan.sh
    ./scripts/sql_safety_inventory.sh
    ./scripts/security_ratchet.sh

This is not a suppression or risk acceptance. Every blocker remains visible.
CI rejects any new or changed blocker identity, while allowing reviewed
blockers to disappear as they are fixed.

When zero blockers remain, CI must return to:

    ./scripts/security_scan.sh --enforce

## SQL-safety primitive gate

Before collecting repository security findings, CI validates the strict
identifier contract and parameterized Parquet-path behaviour:

    ./scripts/sql_safety_primitives_check.sh

This check does not suppress existing B608 findings. It establishes the
shared primitive required to remediate them consistently.

## Semantic SQL migration planner

Before enforcing the temporary blocker ratchet, CI builds the exact
parameter-aware migration queue:

    ./scripts/sql_safety_wave1a_plan.sh

The planner is read-only. It does not rewrite SQL, suppress findings, accept
risk, access application databases or execute production actions.

## SQL Wave 1A canary gate

After scanning, rebuilding the SQL inventory, rebuilding the migration queue
and enforcing the semantic blocker ratchet, CI runs:

    ./scripts/sql_safety_wave1a_canary_check.sh

The gate proves that the original dynamic `directory_rows` insert remains
absent, the replacement query remains a fixed 48-parameter string constant,
the in-memory DuckDB equivalence tests pass and no new semantic blocker has
appeared.
