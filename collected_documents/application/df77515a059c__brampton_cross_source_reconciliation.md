# Brampton Cross-Source Permit Reconciliation

This model compares two independent address-evidence systems for each
active Brampton industrial permit:

1. Historical ODBus entity candidates.
2. Current licensed Brampton Business Directory candidates.

Outputs:

- `silver.brampton_permit_cross_source_reconciliation`
- `silver.brampton_permit_cross_source_review_queue`
- `silver.brampton_permit_cross_source_agreement`
- `silver.brampton_permit_cross_source_summary`

## Classification

The model distinguishes:

- exact or near cross-source name agreement;
- cross-source name conflict;
- current-only or historical-only address evidence;
- current or historical address ambiguity;
- unresolved permits.

Normalized name similarity is diagnostic evidence only. It never promotes
a candidate to a verified occupant.

## Review queue

Records requiring human or stronger-source review include conflicts,
single-source-only matches and address ambiguities.

`both_unmatched` records remain unresolved but are not automatically
promoted into the high-information review queue.

## Safety

Every reconciliation row retains:

- `automatic_identity_promotion = false`
- `permit_occupant_verified = false`
- `commercial_requirement_verified = false`
- `decision_maker_verified = false`
- `outreach_eligible = false`
