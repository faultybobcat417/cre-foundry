# Brampton Permit Verification Plan

This model converts each permit opportunity-evidence row into a deterministic
verification plan.

Outputs:

- `silver.brampton_permit_verification_tasks`
- `silver.brampton_permit_verification_workflow`
- `silver.brampton_permit_verification_queue`
- `silver.brampton_permit_verification_summary`

## Required standard gates

Every permit receives ten blocking gates:

1. Identity verification.
2. Permit-occupancy verification.
3. Commercial-requirement verification.
4. Decision-maker verification.
5. Existing-client exclusion.
6. Protected-relationship check.
7. Active-assignment conflict check.
8. Territory-restriction check.
9. Relationship-owner check.
10. Do-not-contact check.

Permits with conflicts, ambiguities or missing identity evidence receive an
additional `evidence_resolution` task before identity verification.

## Initial queue

Exactly one task is initially ready for each permit:

- `evidence_resolution` when manual resolution is required;
- otherwise `identity_verification`.

All later tasks remain blocked by their prerequisites.

`queue_priority` orders verification work. It is not an opportunity score,
recommendation, prospect rank or contact authorization.

## Safety

The initial plan contains no completed or passed tasks. It cannot automatically
clear gates.

All tasks and workflows remain:

- `operating_mode = 'shadow'`
- `opportunity_ranked = false`
- `outreach_eligible = false`
