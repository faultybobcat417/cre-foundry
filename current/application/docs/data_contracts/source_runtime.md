# Source Runtime

The source-runtime layer plans acquisition work without automatically executing
it.

## Exact adapters

Each source is bound to one exact CLI acquisition command. Runtime planning
fails if a configured command is absent from the current CLI.

No fuzzy or best-match command selection is permitted.

## Runtime state

The mutable state table records:

- consecutive failures;
- circuit state;
- circuit-open deadline;
- next due time;
- latest start and completion times;
- latest result;
- latest snapshot;
- whether the latest source content changed.

Runtime and schedule event tables are append-only.

## Acquisition planning

A source may be planned as:

- disabled;
- blocked because authorization is missing;
- blocked because its command is unavailable;
- blocked because cadence is unconfigured;
- blocked by an open circuit;
- not yet due;
- due for a manual authorized run.

Automatic execution remains disabled.

## Bootstrap discovery

Existing artifacts are considered bootstrap candidates only when:

- the source ID is explicitly present in `source_runs`;
- the artifact path is explicitly stored in `source_runs`;
- the file exists;
- the source is already configured.

Directory-name or filename similarity is not enough to register an immutable
snapshot.

## Safety

The source runtime remains in shadow mode and cannot:

- run acquisition commands automatically;
- execute a browser;
- execute computer vision;
- create analyst conclusions;
- rank opportunities;
- authorize outreach.
