# Brampton Permit-to-Entity Bridge

This bridge connects active Brampton industrial permit signals to the
historical ODBus entity baseline using deterministic address evidence.

## Resolution outputs

- `silver.brampton_permit_entity_resolution`
- `silver.brampton_permit_entity_match_candidates`
- `silver.brampton_permit_entity_unique_links`

## Matching order

1. Exact normalized full address.
2. Exact normalized base address with unit removed.
3. Unmatched.

A single candidate is marked `unique`. Multiple candidates are retained
as `ambiguous`. No fuzzy match is promoted by this version.

## Safety

ODBus is a historical entity-resolution baseline and does not verify the
current occupant, ownership, operating status or commercial requirement.

Every bridge record remains `outreach_eligible = false`.
