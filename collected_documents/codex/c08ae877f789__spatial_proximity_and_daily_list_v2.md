# Spatial Proximity and Daily List Design v2

Machine authorities:

- `../../contracts/spatial_proximity_policy.json`
- `../../contracts/daily_list_composition_policy.json`
- `../../contracts/representative_spatial_assignment_policy.json`
- `../../contracts/spatial_experiment_interference_policy.json`
- `../../contracts/backup_substitution_policy.json`

## Corrected operating assumption

Representatives use company vehicles. Fuel, charging and vehicle depreciation
therefore do not drive candidate ranking.

Distance is still not irrelevant. A dispersed list consumes representative
time, increases access uncertainty, reduces the probability of completing all
ten visits, weakens local market learning and complicates causal experiments.

Accordingly, proximity is a **secondary constrained objective**.

## Lexicographic decision

For candidate set \(S\), where \(|S|=10\):

1. pass eligibility, protection, point-in-time and exact-ten gates;
2. maximize expected incremental business value \(V(S)\);
3. require \(V(S) \geq 0.95 V(S^*)\), where \(S^*\) is the best admissible
   business-value list under the same composition constraints;
4. satisfy mechanism, business-family, parent, property, exploration and
   experiment constraints;
5. minimize spatial dispersion \(D(S)\);
6. sequence the chosen ten using a route-time matrix.

The initial 95% floor is a research default. It is calibrated or replaced after
historical and field evidence.

## Why not combine everything into one weighted score

A single score such as:

```text
value - distance penalty
```

can silently choose low-value nearby locations when the scale or units change.

The epsilon-constrained design preserves a transparent business-value floor,
then optimizes proximity only among near-equivalent lists.

## Spatial compactness metrics

The system records:

- total route duration;
- approximate route distance;
- maximum single leg;
- mean and maximum distance from the route medoid;
- median pairwise distance;
- H3 cell count;
- industrial-cluster count;
- completion probability under observed service/travel distributions.

No single compactness metric is authoritative. A list can have low mean
distance but one extreme outlier, or low straight-line distance but a difficult
road network.

## Provider architecture

### Offline planning

Use haversine distance and H3 neighbour queries for:

- fast candidate-pool partitioning;
- synthetic tests;
- source coverage;
- pod construction;
- fail-closed fallback.

### Route-time matrices

Provider interface:

1. cached authorized matrix;
2. Google Routes `Compute Route Matrix`;
3. self-hosted OSRM table service;
4. haversine approximation.

The selected provider, request parameters, response hash, traffic setting,
timestamp and fallback state must be stored in the decision manifest.

### Solver

Use an exact or certified small-set solver when feasible. OR-Tools is an
acceptable initial implementation for time, distance and visit constraints.
The solver is replaceable and never owns business-policy authority.

## Daily list composition

The initial research arm is:

```text
7 high-confidence exploitation
2 independent mechanism or business-family diversification
1 bounded exploration
```

This is an experimental composition—not a permanent production rule.

Hard defaults:

- one location per parent/legal group;
- no more than two locations at one property;
- no more than four in one industrial complex;
- at least two mechanism families;
- at least two business families;
- no unreviewed probabilistic identity links;
- no more than one high-uncertainty exploration location.

These rules prevent a route from looking efficient because it repeatedly
targets one landlord, corporate group or property.

## Exceptional distant candidate

One distant location may remain when:

- it has materially higher incremental value;
- the value gain exceeds the registered practical threshold;
- the route remains feasible;
- the outlier does not destroy treatment integrity;
- the reason is recorded.

This prevents proximity from eliminating a genuine whale opportunity.

## Reserve pool

The representative receives exactly ten primary locations.

A separate five-location reserve pool is not presented as additional primary
visits. It exists only for logged pre-contact replacement when a primary
location is closed, inaccessible, unsafe, wrong, protected or disrupted.

Every replacement creates a new manifest. Intention-to-treat analysis retains
the original assignment; per-protocol analysis records the actual visit.

## Representative spatial consistency

Each stable spatial pod has:

- one primary representative;
- one backup;
- a registered operating/experiment period;
- specialty and protected-relationship overlays.

Daily random reassignment is prohibited. Consistency supports local correction,
relationship continuity and accumulation of corridor knowledge, but it cannot
override randomization, conflicts or capacity balancing.

## Spatial interference

Nearby businesses can share:

- parent companies;
- owners or landlords;
- buildings;
- industrial complexes;
- referral networks;
- exposure to the same representative.

The experiment therefore stores an interference graph and blocks by
representative, weekday, pod and municipality.

The same business, property or parent cannot appear in multiple arms without an
approved interference design.

## Synthetic planning result

Registered scenarios passed:

- dense equal-value clusters;
- one exceptional distant high-value candidate;
- same-property concentration pressure;
- sparse but valid candidates;
- fewer than ten valid candidates;
- reserve substitution.

The dense-cluster scenario retained 96.3% of estimated business value while
reducing the approximate route by 51.9%. This verifies policy behavior in a
constructed geometry only.
