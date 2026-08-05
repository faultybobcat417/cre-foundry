# Fail-Closed Shadow Learning

This subsystem prepares CRE Foundry for future temporal validation without
recording outcomes, creating feature snapshots, training models or ranking
opportunities.

## Isolated database

Shadow-learning control structures are stored in:

`data/control/shadow_learning.sqlite3`

The existing DuckDB warehouse and operations ledger remain unchanged.

## Empty governed ledgers

The database defines:

- outcome events;
- point-in-time feature snapshots;
- evaluation runs.

Each table has insert, update and delete blockers. Infrastructure exists, but
recording and execution remain disabled.

## Primitive feature review

Every actual primitive is assigned one conservative future role:

- safety control;
- possible outcome leakage;
- join key only;
- point-in-time metadata;
- lineage metadata;
- no observed values;
- manual feature review required.

No primitive is approved or enabled as a model feature.

## Temporal evaluation

Future evaluation must use:

- forward-chaining splits;
- point-in-time features;
- an approved prediction horizon;
- an approved embargo;
- approved positive and negative event definitions;
- approved minimum sample sizes.

## Client inputs

The generated five-section bundle covers:

- exact pilot success event;
- transaction economics;
- pilot representatives;
- protected accounts and exclusions;
- approved operating environment.

No client input becomes active automatically.

## Disabled capabilities

- outcome recording;
- feature snapshot registration;
- evaluation execution;
- model training;
- automatic conclusions;
- opportunity ranking;
- outreach authorization;
- outreach execution.
