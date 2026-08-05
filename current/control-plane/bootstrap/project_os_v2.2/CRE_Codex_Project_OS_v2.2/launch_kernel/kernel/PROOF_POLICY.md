# Proof Policy

## Evidence ladder

0. unsupported;
1. formal/specification;
2. deterministic test;
3. differential/reference;
4. mutation/fault-resistant;
5. synthetic;
6. historical point-in-time;
7. prospective shadow;
8. randomized prospective;
9. production observed.

Incremental appointment lift requires level 8. Durable commercial value
requires level 9.

## Evaluator topology

### Public evaluator

Visible contracts, unit/integration/property tests, schemas, linting, replay,
baselines, and acceptance commands. The builder may read but not weaken them.

### Sealed adversarial evaluator

Protected fixtures, known-bad implementations, mutation cases, temporal
leakage cases, protected-account cases, and fault scenarios. Created or
approved before the corresponding implementation task and outside the
builder's writable scope.

### External hidden holdout

Truly hidden cases maintained outside the builder's repository/context by a
separate owner or platform. Codex cannot create this and then truthfully call
it hidden.

## Promotion

Promotion requires the public and sealed evaluators, independent review,
rollback evidence, and the empirical level required by the claim.
