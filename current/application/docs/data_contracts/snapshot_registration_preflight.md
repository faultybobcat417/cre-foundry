# Snapshot Registration Preflight

The authoritative operations database is opened read-only.

When the actual schema can be mapped, inserts are attempted only in a disposable database clone and are rolled back.

- Status: `transactionally_verified_on_ephemeral_clone`
- Selected source: `brampton_building_permits`
- Authoritative DB unchanged: `True`
- Ephemeral transaction verified: `True`

- Authoritative registrations: `0`
- Authoritative event insertions: `0`
