# Replaceable Reference Architecture

Start with a contract-first modular monolith and transactional outbox unless
repository evidence proves a stronger replacement.

Reference components:

- Python/SQL correctness path;
- PostgreSQL/PostGIS operational state and temporal identity;
- immutable object storage for raw bytes and artifacts;
- DuckDB/Parquet for reproducible historical analytics;
- batch-first features and model registry;
- OpenAPI and CloudEvents/AsyncAPI-compatible interfaces;
- OpenTelemetry-compatible telemetry;
- OpenLineage-compatible lineage;
- replaceable route-matrix and optimization providers.

Evidence-triggered options include microservices, a broker, graph database,
online feature store, distributed warehouse, Kubernetes, Rust, or C++.

Every canonical product has one owner, versioned schema, clocks, content hash,
quality state, lineage, and replay path.
