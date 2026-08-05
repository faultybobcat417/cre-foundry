# RESEARCH-001 source-feasibility checkpoint

Status: in progress. As of 2026-08-01.

The exact final structured artifacts now exist: `claim_evidence_graph.json`, `counterevidence_register.json`, `source_feasibility_registry.json`, and `canonical_field_map.json`. Their public evaluator and five semantic negative controls pass; independent completion/convergence review remains before task closure.

## Decision

Treat the current official-source set as complementary evidence, not as a single candidate universe. The reviewed set contains broad aggregate counts, a stale/incomplete experimental named database, legal-entity records, partial regulated-category licence feeds, and property/event sources. None of these can currently justify a complete, current, one-row-per-physical-operating-establishment claim.

That conclusion is bounded to the reviewed sources. It is not a universal non-existence claim.

## Grain contract implied by the evidence

Keep these objects distinct and join them through typed, temporal evidence:

- legal organization and registered business name;
- registered/head office;
- brand;
- licence or registration;
- permit or planning application;
- parcel/property and registered owner;
- occupier or tenant;
- physical operating establishment;
- route candidate.

A common name, address, or owner is evidence for a possible link, not authority to collapse records.

## Clock contract implied by the evidence

Every source adapter must distinguish at least:

- event or effective time;
- public-availability/publication time;
- observation time, when applicable;
- retrieval time;
- source version or immutable byte hash.

This is necessary to prevent future leakage and to replay what could actually have been known on a historical route day.

## Source roles

Statistics Canada Business Register products can support aggregate denominators and stratification, not a named candidate feed. The Open Database of Businesses can support exploratory schema and recall work, but its 2022 collection window and stated incompleteness prevent current-universe use. Ontario Business Registry evidence is legal-entity/registered-office corroboration, not operating-location truth.

Ontario and municipal licence feeds are plausible high-precision seeds inside their covered regulated categories. Permit, planning, zoning, parcel, land-registry, and assessment products are event/property context. They do not identify the current occupier without separate evidence.

## Reproduction sample

The Toronto CKAN API reproduced machine-readable package metadata and a schema-only datastore response for the municipal business-licence package without acquiring row records. The datastore reported 159,459 rows and fields including licence number, operating name, client name, address, issue date, cancellation date, and last record update.

This test also strengthened the gate. The CKAN package reports `License not specified`, despite the portal's separate general Open Government Licence page. Its datastore-active resource reports a 2022 last-modified value while other package resources and package metadata report 2026 updates. Neither the governing dataset-specific terms nor data freshness should be inferred from the portal page or row count. The exact metadata, fields, URLs, and commands are recorded in `artifacts/research/toronto_business_licences_metadata_probe.v0.json`.

## Rejected shortcuts

- Do not equate registered office, land owner, permit applicant, or licence holder with a current physical operating establishment.
- Do not infer current operation from an old named record or an unexpired administrative record without measuring closure and publication lag.
- Do not assign predictive weight to permits or planning events before an out-of-time ablation against meaningful baselines.
- Do not treat public discoverability as permission for automated acquisition, retention, redistribution, or commercial use.

## Gate and next tests

`approved_source_envelope` remains open and blocks `SOURCE-PILOT-001`. Closing it requires a firm-approved pilot geography, dataset-by-dataset terms and handling review, approved fields and source identifiers, spending/access authority where applicable, and a reproducible immutable acquisition method.

Research can continue without that authority by enumerating source definitions, testing downloadable public packages where terms are clear, and defining measurement protocols. Once a geography and source envelope are approved, the next empirical work is a publication-lag/history audit, a grain/duplicate/conflict audit, and then out-of-time signal-value tests.

The structured source records, evidence dispositions, counterevidence, and official URLs are in `artifacts/research/source_feasibility_registry.v0.json`.

## Reproduced Ontario and Toronto schema boundaries

Ontario Select Licence package metadata identifies OGL-ON-1.0, monthly refresh, `current_as_of` 2026-07-01, and a current English business datastore with 681 rows. Licence number is a licence key, not a location key: observed licences can span multiple address rows. Raw `N/A` sentinels and status/category spellings remain unnormalized evidence.

Toronto Committee of Adjustment currently exposes three incompatible schema families: annual legacy (`SYS_ID` float, `REFERENCE_FILE`, text dates), modern closed (`SYS_ID` text, `REFERENCE_FILE#`, typed dates, ward number/name and added final/community/contact fields), and active modern (single `WARD`, without closed-only fields). Resource labels and current modification timestamps are publication metadata, not proof of contemporaneous historical availability. Cross-partition observations remain distinct until conflict-aware reconciliation.
