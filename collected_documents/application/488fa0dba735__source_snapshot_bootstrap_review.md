# Source Snapshot Bootstrap Review

This layer validates exact existing bronze manifests before any immutable
snapshot registration.

For each exact bootstrap candidate it verifies:

- manifest existence;
- valid JSON-object structure;
- source-ID consistency;
- referenced artifact paths;
- project-boundary containment;
- referenced artifact existence;
- artifact byte size;
- SHA-256 checksums;
- declared checksum matches where available.

Review packets are written to ignored runtime output storage.

No snapshot registration is performed. Human approval and a separate explicit
registration command remain required.
