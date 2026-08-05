# Primitive Quality Profile

This layer profiles the actual values represented by the schema-driven
primitive inventory.

## Read-only profiling

DuckDB and SQLite are opened in read-only mode. The profiler does not sample or
export business values.

For each real column, it may calculate:

- row and non-null counts;
- null ratio;
- approximate distinct count in DuckDB;
- distinct count in SQLite;
- numeric or temporal minimum and maximum;
- maximum text length;
- true and false counts for booleans.

Distinct values are read only for governed safety-control fields.

## Effective semantic roles

Schema names and native data types are combined to improve structural role
detection. Native date, time and timestamp types are temporal even where the
column-name heuristic did not identify them.

## Safety audit

The live values of fields such as `opportunity_ranked`,
`outreach_eligible`, automatic-execution controls and `operating_mode` are
audited.

Any prohibited true value or non-shadow operating mode is a critical failure.

## Remediation queue

The remediation queue orders data-engineering defects only. It is not an
account, opportunity, prospect or commercial ranking.

Examples include:

- nonempty relations without temporal primitives;
- nonempty relations without lineage primitives;
- all-null identity, temporal, lineage, geography or verification fields;
- materially incomplete important fields;
- relation-profile query failures.

## Disabled capabilities

The quality layer cannot activate acquisition, register snapshots, execute
browser/CV agents, generate conclusions, rank opportunities or authorize
outreach.
