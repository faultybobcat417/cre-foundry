# SOURCE_INTELLIGENCE_ATLAS.md

Machine authority: `../../contracts/source_intelligence_registry.json`.  
Access-proof authority: `../../contracts/source_access_proof_registry.json`.  
Evidence authority: `../../contracts/research_evidence_registry.json`.

## Current state

The original 25-item discovery seed is preserved as provenance. The current
atlas contains **60 distinct source classes**.

Inspection states:

```text
{'inspected': 42, 'requires_inspection': 17, 'inspected_restricted': 1}
```

The sixtieth class is the Health Canada product/device API layer. It is kept
separate from regulated site licences because a product/company licence does
not prove a physical operating establishment.

## Source-acceptance rule

A source is not promoted merely because it is public or queryable. It requires:

1. authorized purpose and retained terms/licence record;
2. immutable raw bytes and checksum;
3. complete pagination/count reconciliation;
4. schema fingerprint and drift policy;
5. publication, effective, observed and retrieval clocks;
6. correction, deletion and failure semantics;
7. entity-grain and physical-location audit;
8. measured source latency and coverage;
9. replay from raw bytes to primitives;
10. an admissible role no broader than its evidence supports.

## High-consequence restrictions

- Nonversioned permit services require our own recurring snapshots.
- Voluntary directory disappearance is not business closure.
- Published contact details are not outreach consent.
- LMIA approval is not proof of hiring.
- Contract supplier geography is not delivery-site proof.
- Grant recipient geography is not funded-site proof.
- Product/device licences are not establishment licences.
- Active-only regulatory listings need repeated snapshots to reconstruct exits.
- Source failure and a valid zero-record result are separate states.

## Complete atlas

| ID | Source | Jurisdiction | Grain | Access | Admissible role | Status | Next proof |
| --- | --- | --- | --- | --- | --- | --- | --- |
| toronto_active_permits | Toronto Active Building Permits | Toronto | permit_address | open_data_api | prospective_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_cleared_permits | Toronto Cleared Building Permits | Toronto | permit_address | open_data_download | label_and_history | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_development_applications | Toronto Application Information Centre | Toronto | planning_application_property | public_search_and_documents | context_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_development_pipeline | Toronto Development Pipeline | Toronto | development_project | open_data_download | context_only | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_business_licences | Toronto Business Licences and Permits | Toronto | licensed_business_location | open_data_or_lookup | entity_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_employment_survey | Toronto Employment Survey | Toronto | aggregate_geography_sector | public_aggregate_reports | aggregate_context_only | inspected | Acquire lawful aggregate tables and test denominator/sector-context value only. |
| toronto_capital_pipeline | Toronto Capital Projects Pipeline | Toronto | municipal_project | open_data_download | experimental_context | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_address_points | Toronto Address Points | Toronto | address | open_data_api | entity_only | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_zoning_property | Toronto Zoning and Property Layers | Toronto | parcel_property | open_data_or_public_map | constraint | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| toronto_dinesafe | Toronto Food Premises Inspections | Toronto | food_business_location | open_data_api | entity_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_business_directory | Mississauga Employment Survey Business Directory | Mississauga | consenting_business_location | download | candidate_and_history | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_employment_reports | Mississauga Employment Survey Reports | Mississauga | sector_geography | public_reports | context_only | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_building_permits | Mississauga Building Permits | Mississauga | permit_property | catalog_or_public_map | prospective_predictor | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| mississauga_development_apps | Mississauga Development Applications | Mississauga | planning_application_property | public_map_and_records | context_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_site_plans | Mississauga Site Plan Applications | Mississauga | site_plan_property | public_gis_service | prospective_and_context | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_committee_adjustment | Mississauga Committee of Adjustment Applications | Mississauga | application_property | public_gis_service | experimental_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_parcel_zoning | Mississauga Parcel and Zoning Maps | Mississauga | parcel_property | public_map_api | entity_and_constraint | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| mississauga_road_events | Mississauga Road Construction and Closures | Mississauga | road_event | open_data_catalog | operational_only | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| brampton_building_permits | Brampton Building Permits FeatureServer | Brampton | permit_address | public_arcgis_feature_service | prospective_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| brampton_permit_activity | Brampton Permit Activity Table | Brampton | permit_activity | public_arcgis_table | prospective_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| brampton_upcoming_inspections | Brampton Upcoming Inspections | Brampton | inspection_permit | public_arcgis_table | label_only | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| brampton_development_apps | Brampton Development Applications Map | Brampton | planning_application_property | public_map | context_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| brampton_business_licences | Brampton Stationary Business Licences | Brampton | licensed_business_location | public_lookup_or_request | entity_and_event | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| brampton_geohub_property | Brampton GeoHub Property and Basic Permit Data | Brampton | property_address | public_map | entity_and_context | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| brampton_zoning | Brampton Zoning and Parcel Layers | Brampton | parcel_property | public_map_api | constraint | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| brampton_road_events | Brampton Road Closures and Construction | Brampton | road_event | open_data_or_map | operational_only | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| hamilton_building_permits | Hamilton Building Permits and Inspections | Hamilton | permit_property | public_portal | requires_acquisition_proof | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| hamilton_development_apps | Hamilton Planning and Development Applications | Hamilton | planning_application_property | public_portal_or_map | requires_acquisition_proof | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| hamilton_business_licences | Hamilton Business Licences | Hamilton | licensed_business_location | public_portal_or_lookup | requires_acquisition_proof | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| hamilton_open_data_catalog | Hamilton Open Data Catalogue | Hamilton | mixed | open_data_catalog | discovery_only | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| federal_corporations | Federal Corporations Active and Inactive | Canada | legal_entity | csv_and_api | entity_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| ontario_business_registry | Ontario Business Registry | Ontario | legal_entity | free_basic_search_and_paid_record_products | targeted_entity_verification | inspected | Test a small targeted entity-verification sample and document per-record cost and permitted retention. |
| statcan_business_counts | Canadian Business Counts | Canada | aggregate_establishment_counts | download | aggregate_baseline | inspected | Use as denominator/context with release-methodology flags, never as establishment-level labels. |
| statcan_odbus | Open Database of Businesses | Canada | business_location | download | entity_seed_and_coverage_audit | inspected | Measure municipal/sector coverage, staleness and address accuracy against approved current sources. |
| positive_lmia | Positive LMIA Employers | Canada | employer_business_location | download_csv_xlsx | prospective_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| job_bank_postings | Job Bank Job Postings and Feed | Canada | posting_employer_location | monthly_open_data_csv | prospective_predictor | inspected | Download two immutable monthly files and measure employer match, duplicate, agency, remote and multi-location error. |
| canadian_importers | Canadian Importers Database | Canada | importer_city_postal | interactive_database | context_and_candidate | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| canadabuys_contracts | CanadaBuys Federal Contract History | Canada | supplier_contract | download_csv_ocds | prospective_or_context | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| federal_grants | Federal Grants and Contributions | Canada | recipient_agreement | search_and_download | prospective_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| osb_insolvency | OSB Insolvency Records and Statistics | Canada | legal_entity_case | search_or_paid_records | competing_risk | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| ccaa_records | CCAA Records | Canada | legal_entity_case | public_case_records | specialized_competing_risk | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| ontario_eca_easr | Ontario ECA and EASR Permissions | Ontario | regulated_facility | open_data_and_map | prospective_predictor | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| environmental_registry | Environmental Registry of Ontario Notices | Ontario | proposal_decision_site | public_search_feed | context_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| natural_health_site_licences | Natural Health Product Site Licence Holders | Canada | regulated_site | daily_search_csv | entity_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| medical_device_establishments | Medical Device Establishment Licence Listing | Canada | licensed_establishment | public_search | entity_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| drug_establishment_licences | Drug Establishment Licences | Canada | licensed_building | public_database_or_documents | entity_and_event | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| cfia_food_registry | CFIA Food Licence and Export Establishment Lists | Canada | food_establishment | public_registry_and_lists | entity_and_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| cannabis_licence_holders | Cannabis Licence Holders | Canada | licensed_site_or_holder | public_registry | specialized_event | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| cipo_trademarks | CIPO Trademark Bulk Data | Canada | legal_entity_ip_application | bulk_zip | experimental_context | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| ontario_tenders | Ontario Tenders Portal Awards | Ontario | supplier_award | public_search | requires_acquisition_proof | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| municipal_procurement_awards | Municipal Procurement Awards | GTA | supplier_award | public_portals | experimental_context | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| agco_licences | AGCO Licence Notices and Lookups | Ontario | licensed_business_location | public_search_and_notices | specialized_event | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| peel_food_inspections | Peel Food Premises Inspections | Peel | food_business_location | public_search_or_open_data | entity_and_event | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| health_canada_inspections | Health Canada Drug and Device Inspection Records | Canada | regulated_site_inspection | public_search | context_and_competing_risk | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| cfia_enforcement | CFIA Suspensions and Cancellations | Canada | licensed_business | public_notices | competing_risk | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| commercial_market_reports | Brokerage Industrial Market Reports | GTA | submarket_quarter | public_reports | context_only | inspected | Create immutable sample snapshot and measure source latency, coverage and entity-match precision. |
| onland | OnLand Land Registry | Ontario | parcel_instrument | record_by_record_paid_search | manual_specialized_due_diligence | inspected_restricted | Obtain written licence terms permitting the intended integration or keep outside automated acquisition and ranking. |
| mpac | MPAC Property Data | Ontario | property_assessment | licensed_paid | paid_specialized | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| commercial_listings | Commercial Listings and Availability Feeds | GTA | property_listing | licensed_or_public_search | context_and_outcome | requires_inspection | Create immutable sample snapshot, field dictionary, licence record, latency test and entity-match sample. |
| health_product_apis | Health Canada Drug and Health Product APIs | Canada | product_licence_and_company | public_json_xml_api | corroboration_only | inspected | Retrieve selected API pages, measure company-ID stability and link only through independently verified establishments. |
