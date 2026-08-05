# Source Parser Isolation

The source parser is statically and dynamically isolated from authoritative SQLite and DuckDB connections.

- Static isolation: `true`
- Artifact boundary isolation: `true`
- Guarded parser runs: `6`
- Validated contracts: `3`

- Database connections: `0`
- Database writes: `0`
- Snapshot registrations: `0`
- Automatic approvals: `0`
