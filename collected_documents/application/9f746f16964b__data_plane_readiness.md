# CRE Foundry Data-Plane Readiness

The governed data plane coordinates source acquisition, deterministic
transformations and control-state projection without introducing opportunity
ranking or outreach authorization.

## Brampton operational dependency order

1. Permit classification rules
2. Brampton permit acquisition
3. Permit lifecycle classification
4. Permit silver normalization
5. Permit-to-historical-entity bridge
6. Brampton Business Directory acquisition
7. Business Directory silver normalization
8. Permit-to-current-directory bridge
9. Cross-source reconciliation
10. Unified opportunity evidence
11. Verification plan
12. Verification ledger initialization
13. Verification state projection

Acquisition stages are disabled by default. A normal transform-only run rebuilds
derived data from already persisted source snapshots.

## Runner guarantees

The runner provides:

- automatic discovery of installed source commands;
- deterministic dependency ordering;
- an exclusive local process lock;
- fail-fast execution;
- bounded stage timeouts;
- retries for acquisition stages only;
- per-stage logs;
- atomic run manifests;
- pre-run and post-run database fingerprints;
- post-run readiness auditing;
- free-disk preflight;
- warehouse table and freshness inventory;
- SQLite control-plane inventory.

## Freshness reporting

The readiness report identifies timestamp-like columns and reports the newest
observable timestamp and its age in days.

The first version deliberately does not invent universal business freshness
thresholds. Source-specific service-level expectations must be attached later
to documented acquisition cadences.

## Safety boundaries

The data plane does not:

- create analyst evidence;
- complete verification tasks automatically;
- infer occupants from addresses;
- infer requirements from permits;
- rank opportunities;
- authorize contact;
- initiate outreach.

All executions preserve shadow mode and fail if an existing contract enables
ranking or outreach.
## Command binding policy

Execution stages use a static stage-to-command registry validated against the
actual Typer CLI. The runner does not select executable commands using fuzzy
names, token similarity or best-match scoring.

`inspect-brampton-permits` is an explicit validation stage. It validates the
persisted permit snapshot and lifecycle/status interpretation before downstream
silver and bridge models are rebuilt.

If a required static command is missing, renamed or registered more than once,
the pipeline fails before execution.
