# Brampton Permit Source Review

This packet must be reviewed by an identified person. No decision is automatically approved.

- Source: `brampton_building_permits`
- Evidence digest: `714a1be5231393f4a1e397820519ae62844563caeb5db5189b5013212badbaa4`
- Decision complete: `false`

## Candidate record keys

- `PERMITNUMBER`
- `OBJECTID`
- `GIS_ID`

## Candidate temporal fields

- `INDATE`
- `ISSUEDATE`
- `PROCESSDATE`
- `EXPIRYDATE`

## Required decisions

### parser_contract_approved

Does the parser reproduce the exact artifact deterministically?

- Current value: `False`

### schema_contract_approved

Does the observed field set match the intended permit dataset semantics?

- Current value: `False`

### approved_record_key

Which reviewed candidate uniquely and stably identifies a permit record?

- Current value: `None`

### approved_temporal_fields

Which fields are valid event or source timestamps for point-in-time use?

- Current value: `[]`

### capture_policy_approved

Is the proposed publication-aligned capture policy operationally valid?

- Current value: `False`

### change_contract_approved

Are the permitted change types and future-information protections correct?

- Current value: `False`

### registration_approved

May one checksum-pinned snapshot proceed to the separately authorized dry run?

- Current value: `False`

## Current blockers

- `approved_record_key_invalid_or_missing`
- `approved_temporal_fields_missing`
- `capture_policy_approved_false`
- `change_contract_approved_false`
- `evidence_reference_missing`
- `parser_contract_approved_false`
- `registration_approved_false`
- `reviewed_at_missing_or_invalid`
- `reviewer_id_missing`
- `schema_contract_approved_false`

- Automatic approval: `false`
- Registration execution: `false`
