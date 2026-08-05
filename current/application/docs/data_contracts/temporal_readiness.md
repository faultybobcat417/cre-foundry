# Point-in-Time Temporal Readiness

This layer prepares the data system for leakage-safe historical evaluation.

## Relation review

Every inventoried relation is reviewed for:

- temporal candidate columns;
- source and snapshot lineage;
- quality-profile ranges;
- downstream dependencies;
- future feature roles.

No temporal column or relation is approved automatically.

## Feature-definition engineering

Every primitive previously classified as `review_required` receives an empty
definition template covering:

- business definition;
- unit;
- transformation;
- as-of rule;
- missingness policy;
- validity range;
- leakage review;
- point-in-time review;
- ownership and approval.

No primitive is approved or enabled as a model feature.

## Point-in-time plan

A future dataset must enforce:

- observation and availability times before the decision time;
- source snapshots that existed before the decision;
- outcomes after the decision;
- forward-only train and validation windows;
- an approved embargo between train and validation.

## Disabled capabilities

- automatic temporal-semantic approval;
- automatic feature approval;
- source or feature snapshot registration;
- dataset materialization;
- model training;
- production opportunity ranking;
- outreach authorization and execution.
