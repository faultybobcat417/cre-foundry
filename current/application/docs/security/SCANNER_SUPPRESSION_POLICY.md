# Scanner Suppression Policy

A scanner result is never silently discarded.

Every suppression must contain:

- an exact scanner identifier;
- an exact deterministic finding fingerprint;
- a concrete technical rationale;
- an accountable owner;
- an independent approver;
- creation and expiration timestamps;
- an evidence reference.

Wildcard suppressions and expired suppressions are invalid. Critical
credential findings and Git-history credential findings are not
suppressible. Inline `nosec` or secret-allowlist directives require a
matching governed suppression record.

Suppressions reduce noise only after review. They do not erase the original
finding, its fingerprint, its scanner source or its evidence trail.

## Generated scanner evidence

Machine-generated JSON reports under `docs/security/` are excluded from the
worktree secret detector to prevent reports from scanning their own hashes,
fingerprints and advisory identifiers. These artifacts remain protected by
deterministic generation, checksum reconciliation, repository review and the
Git-history scanner's raw-secret prohibition.

The exclusion does not apply to source code, configuration, workflows,
scripts or human-authored security policy documents.
