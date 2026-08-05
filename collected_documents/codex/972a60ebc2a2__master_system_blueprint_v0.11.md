# CRE Tip Sheet Master System Blueprint v0.11

## 1. Product mission

Produce exactly ten feasible physical business locations for each standardized
representative-day. The list should increase the incremental probability of a
qualifying booked conversation with a senior commercial realtor and maximize
risk-adjusted net commercial value.

When ten locations cannot pass every required gate, return:

`ABSTAIN_NO_VALID_TEN`.

## 2. Qualifying outcome

The primary outcome is a decision-maker-confirmed and scheduled commercial-real-
estate conversation with the senior realtor under the registered F9 definition.

Tentative interest, generic friendliness, unavailable decision makers, post-hoc
calendar entries and self-reported future possibilities are not equivalent.

Downstream outcomes remain separate:

- attended appointment;
- qualified requirement;
- mandate;
- listing;
- transaction;
- realized commission;
- repeat or referral value.

## 3. Information boundary

### Stage 1 — pre-visit

Only evidence available before route issuance may affect candidate selection.

### Stage 2 — field contact

Visit observations, corrections, decision-maker information and direct
requirements are captured after assignment.

### Stage 3 — downstream

Appointments, attendance, mandates and transactions mature on their own clocks.

Stage 2 or 3 information never rewrites the Stage-1 snapshot.

## 4. Pilot market

Provisional first market:

- Brampton;
- Mississauga;
- industrial, warehouse, flex and light manufacturing;
- manufacturing, logistics, wholesale/import distribution, food processing and
  regulated health-product businesses.

Toronto is the historical/transportability reference. Hamilton is a later
specialized transfer market.

This segment remains rejectable based on real universe coverage, event rates,
entity accuracy, source authority and field feasibility.

## 5. Candidate universe

A candidate is a visitable business establishment at a physical location—not
merely:

- a legal corporation;
- a mailing address;
- a property;
- a permit applicant;
- a supplier;
- a grant recipient;
- a product licence holder;
- an online brand.

The universe combines approved current establishment sources, longitudinal
directory vintages, operating licences and verified entity/location evidence.

Every candidate stores:

- legal entity;
- operating business;
- brand;
- establishment;
- location;
- address and unit;
- building/property/parcel;
- owner and occupier where known;
- valid-time lineage;
- source provenance;
- protected-account state;
- visitability state.

## 6. Source architecture

The source atlas has sixty classes. Ten priority access packets define the
minimum pilot portfolio.

Every accepted source requires:

- retained terms and purpose;
- immutable raw bytes;
- retrieval manifest;
- schema fingerprint;
- page/count reconciliation;
- publication/effective/observed/retrieval clocks;
- correction and tombstone history;
- source-health state;
- entity-grain audit;
- deterministic replay.

A public endpoint is not automatically a production source.

## 7. Entity resolution

Join sequence:

1. address normalization;
2. establishment identity;
3. permit-to-location attribution;
4. federal entity/location attribution;
5. temporal lineage.

Address equality alone never proves business identity. Builder, contractor,
supplier and grant-recipient geography never prove occupier or operating site.

Fuzzy-only matches remain research-only. Protected-account false-clear
tolerance is zero.

## 8. CRE mechanism system

Forty-two complete chains cover:

- expansion and capacity;
- relocation and renewal;
- formation and entry;
- contraction and consolidation;
- redevelopment and displacement;
- infrastructure and property-use friction;
- ownership and succession;
- financial pressure;
- supply-chain/network changes;
- specialized regulated facilities.

Every chain includes:

```text
mechanism
→ observable precursor
→ authorized source
→ durable primitive
→ point-in-time feature
→ alternative explanations
→ falsification test
→ field action
→ measurable result
```

## 9. Historical label factory

Research unit:

`business_location × prediction_date`.

The system preserves:

- event effective time;
- event announcement time;
- publication time;
- first observation;
- retrieval time;
- label adjudication time.

Labels include positive confidence states, mature negatives, censoring,
unlabelled, conflicted and unknown states.

Two blind reviewers and an adjudicator handle the first 500-record feasibility
sample.

## 10. Models and baselines

The system must outperform meaningful alternatives:

- incumbent representative selection;
- stratified random eligible locations;
- simple transparent rules;
- recency-only signals;
- source-family heuristics;
- calibrated regularized models;
- survival/competing-risk models;
- gradient boosting only after valid history exists.

Prediction is not ranking. Ranking is not routing. Routing is not causal proof.

Every model must have:

- temporal splits;
- source-family ablation;
- leakage tests;
- calibration;
- uncertainty;
- subgroup and municipality analysis;
- reproducibility;
- retirement conditions.

## 11. Economic objective

Candidate value separates:

- incremental appointment probability;
- attendance probability;
- conditional mandate probability;
- conditional transaction probability;
- expected commission/value;
- representative labour;
- travel/service time;
- acquisition and system cost;
- uncertainty and downside.

Company vehicle energy and depreciation costs have zero initial ranking weight.

Representative time and completion probability remain operational constraints.

## 12. Daily list selection

Decision order:

1. protection and eligibility;
2. expected incremental business value;
3. business-value retention floor;
4. list composition;
5. spatial compactness;
6. sequence and robustness;
7. manifest and replay.

Default research composition:

- seven exploitation;
- two independent diversity;
- one exploration.

The system compares that arm against value-only, compactness, single-pod,
incumbent and random baselines.

## 13. Proximity and routing

H3 or a data-driven connected spatial graph creates candidate pods.

Proximity is optimized after preserving at least 95% of the best admissible
business value. There is no arbitrary kilometre cap; all ten must fit the shift
under service, access and uncertainty assumptions.

One exceptional distant candidate may remain when its incremental value is
material.

Route matrices are abstracted behind cached, Google Routes, self-hosted OSRM and
haversine providers.

## 14. Representatives and territories

Persistent pods support:

- local familiarity;
- correction quality;
- relationship continuity;
- lower operational friction;
- clearer experimental blocking.

Each pod has a primary and backup representative. Reassignment is logged and
cannot occur to cherry-pick outcomes.

Final assignments require real representative starting locations, capacity,
specialties and protected relationships.

## 15. Field product

The representative receives:

- exactly ten ordered primary locations;
- reason and evidence summary;
- visit objective;
- mechanism-specific field questions;
- access/safety notes;
- protected-account status;
- route map;
- correction and outcome form.

A hidden reserve pool of five supports pre-contact substitution. It is not an
eleven-to-fifteen-location Tip Sheet.

## 16. Causal experiment

Primary treatment unit:

`representative route-day`.

Block by:

- representative;
- weekday;
- spatial pod;
- municipality.

Arms include incumbent, random, simple-rule and model/list policies.

Intention-to-treat is primary. Adherence, substitutions and actual visits are
secondary process measures.

Spatial interference is represented through shared entity, property, landlord,
industrial-complex, H3-neighbour and representative-exposure edges.

Thirty route-days are instrumentation—not lift proof. Confirmatory size follows
observed base rates, clustering and variance.

## 17. Monitoring and learning

Monitor:

- source health and latency;
- schema drift;
- entity conflicts;
- candidate coverage;
- calibration;
- route completion;
- access failure;
- substitution;
- representative adherence;
- appointment outcomes;
- source-family lift;
- spatial performance;
- economic reconciliation;
- policy decay.

Critical error-budget exhaustion freezes ordinary promotion.

## 18. Production autonomy

Codex may design, build, test, simulate and shadow every production capability.

Live action requires:

- signed standing delegation;
- policy hash match;
- approved source and purpose;
- budget and economic authority;
- protected-account clearance;
- active adapter;
- emergency-stop clearance;
- evidence-bound promotion.

Codex cannot sign its own authority or change the evaluator that judges its
work.

## 19. Security and compliance

No passwords, cookies, tokens or private signing keys belong in planning files.

Source collection follows approved terms and purpose. Published contact details
do not equal outreach consent. Personal information not required for the
decision is excluded or quarantined.

External writes are idempotent, least-privilege, reversible and logged.

## 20. Codex implementation sequence

Before implementation:

1. acquire authorized immutable source samples;
2. reconcile counts, pages and schemas;
3. execute entity and historical feasibility audits;
4. recalculate universe/event/power assumptions;
5. freeze the final domain dossier;
6. bootstrap the real repository;
7. inventory existing capabilities;
8. seal a repository-specific hidden evaluator;
9. begin autonomous implementation.

Codex receives objectives, contracts, evaluators and authority—not thousands of
unprioritized suggestions.

## 21. Remaining blockers

### User or firm

- services and priorities;
- economics;
- territories;
- representatives;
- protected accounts;
- source approvals;
- operating and signing authority.

### Empirical

- raw source samples;
- candidate-universe coverage;
- entity accuracy;
- historical event labels;
- travel/service distributions;
- adherence;
- randomized appointment lift;
- long-cycle commercial value.

### Repository

- current implementation tree;
- security remediation;
- installed Codex compatibility;
- repository hidden evaluator;
- production adapters and credentials.

## 22. Final-planning rule

The plan is considered ready for final Codex-prompt drafting when every domain
is:

- planning verified;
- delegated to Codex with an immutable evaluator;
- or blocked by a named user/empirical gate that Codex cannot responsibly infer.

No plan is called perfect or mistake-free. The target is explicit uncertainty,
fail-closed behavior, independent verification and rapid correction.
