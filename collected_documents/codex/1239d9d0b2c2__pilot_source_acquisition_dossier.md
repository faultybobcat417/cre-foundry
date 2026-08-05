# Pilot Source Acquisition Dossier v0.10

Machine authorities:

- `../../contracts/source_access_proof_registry.json`
- `../../contracts/immutable_source_snapshot_contract.json`
- `../../contracts/pilot_cross_source_join_contract.json`
- `../../contracts/pilot_historical_sample_protocol.json`

## What is now proven

Ten high-priority source families have official endpoints or resource records,
observed fields, access modes, update behavior, point-in-time risks, admissible
roles and explicit remaining proofs.

## What is not proven

No raw row-level sample was downloaded inside this runtime. The ordinary
container/Python network could not resolve external hosts. The package therefore
records metadata access as proven and raw acquisition as pending instead of
substituting invented rows or claiming PZ-025 completion.

## Minimum portfolio

1. Brampton permits
2. Mississauga permits
3. Mississauga 2019/2024/2025 business directories
4. Job Bank monthly postings
5. positive LMIA quarterly files
6. CanadaBuys contract history
7. federal grants and contributions
8. Health Canada MDEL establishments
9. Health Canada product/device APIs as corroboration
10. Toronto permits as historical reference

## Most important discoveries

### Own snapshots are mandatory

Brampton and Mississauga permit layers are queryable but non-versioned and do
not support historical-moment queries. Current status, issue and completion
fields can therefore contain information unavailable at an earlier decision
date.

### Mississauga provides a longitudinal opportunity

Separate public services exist for 2019, 2024 and 2025 business-directory
vintages. They can support establishment lineage and candidate-universe
research, but voluntary participation means appearance and disappearance are
not business birth and death.

The 2025 metadata exposes a reconciliation problem: one source reports 13,651
geometry objects while a catalogue reports 14,637 rows. The first acquisition
test must explain the difference.

### Federal sources require schema-vintage handling

Job Bank is monthly. LMIA is quarterly but has changed from CSV/NOC 2011 to
XLSX/NOC 2021 and some old resources fail portal validation. CanadaBuys changed
its CSV structure in March–April 2026 and continuously amends old contracts.
Grants are a very large quarterly consolidated file with recipient geography
that does not necessarily identify the funded operating site.

### Regulatory data are not interchangeable

MDEL is an active establishment listing and exposes an unnecessary senior
official field that must be excluded. Product and device APIs do not prove a
physical manufacturing or distribution site.

## First executable proof sequence

1. archive licence/terms and metadata;
2. retrieve immutable raw bytes;
3. generate manifest and schema fingerprint;
4. reconcile counts and pagination;
5. map canonical primitives;
6. test empty/failure/deletion states;
7. run address and establishment joins;
8. dual-review the 500-record historical sample;
9. reject sources or mechanisms that miss thresholds;
10. recalculate pilot event rates and experiment size.
