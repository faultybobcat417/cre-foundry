# Brampton Permit Opportunity Evidence

This model creates exactly one conservative evidence record for each active
Brampton industrial permit.

Outputs:

- `silver.brampton_permit_opportunity_evidence`
- `silver.brampton_permit_opportunity_review_queue`
- `silver.brampton_permit_opportunity_unresolved`
- `silver.brampton_permit_opportunity_summary`

## Purpose

The table combines:

- permit event type and signal strength;
- historical ODBus address evidence;
- current Brampton Business Directory address evidence;
- cross-source reconciliation state;
- provisional current-directory business attributes;
- explicit unresolved verification and exclusion gates.

The model does not rank permits and does not decide which businesses should
be contacted.

## Provisional business identity

`provisional_business_name` is evidence attached to the permit address. It
does not establish that the business is:

- the permit applicant;
- the property owner;
- the tenant undertaking the work;
- the future occupant;
- a decision-maker;
- experiencing a commercial real-estate requirement.

Current directory information takes precedence over historical ODBus
information only as the displayed provisional record. Conflicts remain
explicitly flagged.

## Required gates

Every row requires:

- identity verification;
- permit-occupancy verification;
- commercial-requirement verification;
- decision-maker verification;
- existing-client and active-assignment checks;
- protected-relationship and relationship-owner checks;
- territory and do-not-contact checks.

## Safety

All rows remain:

- `operating_mode = 'shadow'`
- `ranked = false`
- `opportunity_score = null`
- `opportunity_rank = null`
- `identity_verified = false`
- `permit_occupant_verified = false`
- `commercial_requirement_verified = false`
- `decision_maker_verified = false`
- `exclusions_cleared = false`
- `outreach_eligible = false`
