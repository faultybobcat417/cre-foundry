# Brampton Industrial Permit Silver

The latest successful bronze snapshot is normalized into:

- `silver.brampton_industrial_permits`
- `silver.brampton_active_permit_signals`
- `silver.brampton_permit_signal_summary`

## Record identity

`OBJECTID`, `PERMITNUMBER` and `FOLDERRSN` must each be present and unique.
Every bronze record is preserved as one silver record.

## Active research signal

A permit appears in the active-signal view only when:

- its classifier marks it as a signal candidate;
- its application date is present;
- its application date is within 90 days of the snapshot timestamp.

Revisions and terminal lifecycle states are excluded automatically.

## Safety

The source is a current event feed, not proof of a leasing requirement.
Every silver record retains `outreach_eligible = false`.
