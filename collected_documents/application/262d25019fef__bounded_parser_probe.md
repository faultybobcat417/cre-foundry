# Bounded Parser Reconnaissance

This layer reads strictly bounded in-memory prefixes from admitted artifacts.

ZIP members are streamed directly from their archive. No member is extracted.

GZIP data is decompressed only until the configured prefix limit.

- Artifacts: `3`
- Completed probes: `3`
- Recognized artifacts: `3`
- Integrity violations: `0`

- Archive extraction: `false`
- Full decompression: `false`
- Full parsing: `false`
- Row materialization: `false`
- Snapshot registration: `false`
