# Brampton Permit-to-Directory Bridge

This bridge connects active industrial permit signals to operational
records in the licensed Brampton Business Directory.

Outputs:

- `silver.brampton_permit_directory_resolution`
- `silver.brampton_permit_directory_match_candidates`
- `silver.brampton_permit_directory_unique_address_links`

## Match order

1. Exact normalized full address.
2. Exact normalized base address only when no full-address match exists.
3. Unmatched.

A permit with one directory candidate is classified `unique`. A permit
with multiple candidates is retained as `ambiguous`. No fuzzy match is
promoted.

## Meaning of a unique link

A unique link means one operational directory record matched the permit
address under the deterministic rules. It does not prove that the listed
business is the permit applicant, tenant, owner or intended occupant.

## Safety

All outputs retain:

- `permit_occupant_verified = false`
- `commercial_requirement_verified = false`
- `decision_maker_verified = false`
- `outreach_eligible = false`
