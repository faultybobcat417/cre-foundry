# Dependency-Aware Data Health

This layer converts raw primitive-quality findings into deterministic
data-engineering work.

## Baseline fingerprints

Every actual relation receives:

- a schema fingerprint;
- a quality fingerprint;
- row and primitive counts;
- issue counts by type and severity;
- strict downstream view-reference counts.

The audit compares current fingerprints with the committed baseline. It does
not update the baseline automatically.

## Dependency graph

Dependencies are extracted conservatively from exact schema-qualified
references in DuckDB view definitions. Missing edges are possible; speculative
edges are not created.

## Remediation work

The remediation plan groups quality findings by relation and assigns an
engineering priority based only on issue severity. Downstream relation counts
are shown separately.

This is not opportunity, account, prospect or representative ranking.

## Safety

This layer cannot:

- alter schemas;
- backfill data;
- activate acquisition;
- produce analyst conclusions;
- rank opportunities;
- authorize outreach.
