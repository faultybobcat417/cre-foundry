# Schema-Driven Primitive Inventory

This inventory is generated directly from the active DuckDB warehouse and
SQLite control database.

It does not assume that a useful field exists. Every primitive corresponds to
an actual relation and column currently present in storage.

## Primitive identity

Primitive IDs use:

- `duckdb:<schema>.<relation>.<column>`
- `sqlite:main.<relation>.<column>`

## Deterministic classifications

Column-name classifications identify candidates for:

- identity;
- observation/effective time;
- lineage;
- geography;
- verification;
- safety controls.

These flags are structural hints, not analyst conclusions and not model
features.

## Gap detection

The contract explicitly lists relations without detected temporal columns and
relations without detected lineage columns. These are engineering-review
queues, not claims that the relation is unusable.

## Read-only guarantees

The inventory opens DuckDB and SQLite in read-only mode. It does not:

- acquire sources;
- modify source-runtime state;
- register snapshots;
- create analyst events;
- rank opportunities;
- authorize outreach;
- execute browser or computer-vision workers.
