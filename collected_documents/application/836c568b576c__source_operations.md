# Source Operations

The source-operations layer governs immutable source snapshots before they
enter bronze or downstream transformation models.

## Storage model

Snapshots are content addressed by SHA-256 and stored under:

`data/snapshots/<source>/<prefix>/<sha256>.blob`

The control database records:

- source policy;
- snapshot identity;
- content checksum;
- artifact path;
- byte size and content type;
- observation and acquisition timestamps;
- acquisition method;
- parser and schema versions;
- append-only snapshot events;
- append-only quarantine events;
- append-only replay events.

## Deduplication

A source may have only one snapshot for a given SHA-256 digest. Repeated
observations append a duplicate-observed event without inserting another
snapshot or artifact.

## Replay

Replay plans verify the immutable artifact and checksum. Replay never
reacquires the source. Downstream replay execution will be connected to the
governed data plane in a later checkpoint.

## Freshness

The schema supports source-specific freshness targets and maximum staleness.
Those values remain unconfigured until each source owner and acquisition
cadence are verified.

## Safety

The source-operations layer:

- does not infer analyst conclusions;
- does not rank opportunities;
- does not authorize outreach;
- does not bypass access restrictions;
- remains in shadow mode.
