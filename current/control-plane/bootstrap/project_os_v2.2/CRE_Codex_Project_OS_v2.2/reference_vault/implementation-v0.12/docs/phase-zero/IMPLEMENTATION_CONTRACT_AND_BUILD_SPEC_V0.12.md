# CRE Tip Sheet Implementation Contract and Build Specification v0.12

## Purpose

The v0.11 blueprint defines the commercial and quantitative system. This
document defines the engineering constitution Codex must implement.

It replaces architectural guesswork with bounded contexts, canonical data
products, versioned interfaces, state machines, lineage, SLOs and milestone
acceptance evidence.

## 1. Initial architecture

Build a **contract-first modular monolith with a transactional outbox**.

This is not a prototype shortcut. It is the smallest architecture that provides:

- transactionally consistent state and domain events;
- strict logical module ownership;
- deterministic replay;
- testable interfaces;
- deployable isolation later;
- fewer distributed failure modes during the pilot.

A context may be split into a separate service only after a measured trigger
shows a real isolation, scale, release-cadence or availability requirement.

## 2. Reference technology profile

### Pilot reference

- Python and SQL reference implementation;
- PostgreSQL/PostGIS for authoritative operational state;
- immutable S3-compatible object storage for raw source bytes and artifacts;
- DuckDB/Parquet for local and historical analytics;
- database job queue and transactional outbox;
- OpenAPI synchronous interface;
- AsyncAPI/CloudEvents-compatible internal events;
- OpenTelemetry telemetry;
- OpenLineage-compatible lineage;
- OR-Tools or equivalent replaceable route solver;
- optional MLflow-compatible model registry.

### Explicitly not required initially

- microservice deployment;
- Kafka;
- Neo4j;
- a separate online feature store;
- a C++ or Rust core;
- Kubernetes;
- real-time inference.

These remain valid escalation options, but each requires measured evidence and
a rollback-compatible migration.

## 3. Twelve bounded contexts

1. Source Acquisition
2. Evidence Normalization and Lineage
3. Entity and Location Resolution
4. Candidate Universe and Protection
5. Point-in-Time Features and Labels
6. Models, Baselines and Calibration
7. Economic Ranking and Daily-List Policy
8. Spatial Pods, Matrices and Routing
9. Field Operations
10. Appointments, Outcomes and Economics
11. Authorization, Security and Promotion
12. Lineage, Telemetry, Evaluation and Replay

Each context owns its authoritative writes. Cross-context communication occurs
only through a versioned data product or interface contract.

## 4. Twenty-one canonical data products

The registry covers the complete chain:

```text
RawSourceSnapshot
→ NormalizedSourceRecord
→ EntityResolutionDecision
→ EntityGraphSnapshot
→ CandidateUniverseSnapshot
→ FeatureDefinition / FeatureSnapshot / LabelSnapshot
→ TrainingDatasetManifest
→ ModelArtifact / ScoreSnapshot
→ RankedCandidateSnapshot
→ DailyListPlan
→ RouteMatrixSnapshot / RouteManifest
→ FieldVisitEvent
→ OutcomeEvent / EconomicReconciliation
→ AuthorizationDecision
→ EvaluationResult / ReplayBundle
```

Every instance has:

- immutable schema version;
- event and system clocks;
- producer version;
- content hash;
- correlation and causation IDs;
- lineage parents;
- quality state;
- minimum necessary privacy classification.

## 5. APIs and events

### OpenAPI

The internal HTTP contract includes health, source snapshots, entity jobs,
candidate universes, score snapshots, daily-list planning, route issuance,
field visits, outcomes, replay and authorization.

Every mutation requires an `Idempotency-Key`.

### AsyncAPI and CloudEvents

Internal events use a CloudEvents-compatible envelope with:

- globally unique stable event ID;
- event type and subject;
- time and schema;
- correlation and causation IDs;
- idempotency key;
- producer and version;
- trace context;
- domain payload.

Delivery is at least once. Consumers must be idempotent.

## 6. Lifecycle state machines

Five machine authorities cover:

- source snapshot;
- candidate;
- route day;
- model version;
- Codex task.

Invalid and out-of-order transitions fail closed. Terminal-state corrections
use explicit compensating transitions instead of rewriting history.

## 7. Data quality and lineage

Critical products cannot promote unless:

- schema validation passes;
- counts and critical-field checks pass;
- quality state is valid;
- lineage parents resolve;
- point-in-time cutoff is recorded;
- replay reproduces the product;
- no future knowledge enters the simulated decision.

Source failure, valid zero, suspect zero, partial snapshot and deletion remain
different states.

## 8. ML lifecycle

Start in daily-batch mode.

A feature registry is required. An online store is not.

Every model version records:

- training dataset;
- feature versions;
- code and environment;
- temporal split;
- baselines;
- calibration and uncertainty;
- subgroup results;
- model card;
- rollback.

Use candidate, challenger, champion, suspended and retired aliases.

Compiled performance kernels are permitted only after profiling and must remain
differentially equivalent to the Python/SQL reference path.

## 9. Reliability and observability

Use OpenTelemetry-compatible traces, metrics and logs and OpenLineage-compatible
job/run/dataset metadata.

Zero-error-budget objectives include:

- authorization correctness;
- protected accounts;
- idempotent external effects;
- exact-ten route manifests;
- event deduplication;
- schema compatibility;
- lineage closure;
- feature replay and parity;
- critical trace completeness.

High-cardinality business IDs belong in traces or structured logs, not metric
labels.

## 10. Deployment profiles

### Research

Local immutable files, DuckDB and optional PostgreSQL. No live effects.

### Pilot shadow

Containerized modular application, PostgreSQL/PostGIS, object storage,
scheduled workers, outbox and telemetry.

### Pilot live

Adds delegation verification, protected-account service, route adapter, field
application, emergency stop and immutable audit.

### Scaled production

Adds horizontal workers and managed stores. Broker, online feature store, graph
database and compiled kernels remain optional evidence-triggered components.

## 11. Migrations and backfills

Use:

```text
expand → migrate → verify → contract
```

Every migration requires dry run, forward verification, rollback verification
and semantic reconciliation.

Backfills never overwrite prior observed truth. Backfilled historical facts are
tagged and may not leak into an earlier simulated decision.

## 12. Codex milestones

Fourteen evidence-bound milestones run from repository truth inventory through
production promotion.

Every milestone requires:

- manifest;
- tests;
- independent sweep;
- rollback evidence;
- no unresolved critical finding;
- current traceability;
- immutable next-step inputs.

Codex may not mark its own milestone successful by changing the evaluator.

## 13. Deterministic failure audit

Twelve adversarial scenarios now pass:

- duplicate event retry;
- out-of-order candidate transition;
- partial-snapshot deletion attempt;
- breaking schema change;
- missing lineage;
- protected candidate;
- feature mismatch;
- nine-location route;
- emergency-stop precedence;
- historical backfill leakage;
- migration without rollback;
- milestone missing evidence.

## 14. What remains before the final prompt

- PZ-025 real raw-source and historical/entity proof;
- PZ-026 real spatial and representative calibration;
- firm economics, services, territories and exclusions;
- actual repository truth inventory;
- repository-specific hidden evaluator.

The build specification is now planning-complete. Empirical and external
authority inputs remain deliberately unresolved.
