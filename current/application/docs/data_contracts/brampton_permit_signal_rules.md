# Brampton Industrial Permit Signal Rules

## Source scope

Only permit records whose `SUBDESC` is one of:

- `F1: Industrial`
- `F2: Industrial`
- `F3: Industrial`

A record used as a current event must have a non-null `INDATE`.
Null application dates must never appear at the top of a recency query.

## Event classification

High-strength research signals:

- New construction
- Building additions
- Change of use
- Interior or tenant fit-outs

Medium-strength research signals:

- Alterations and renovations
- Building-system work such as HVAC, plumbing, sprinklers or fire alarms

Review-only records:

- Revisions
- Demolition
- Unclassified work descriptions

Permit numbers matching `-P##-##` and records whose work description is
`Revision` are revision observations rather than new primary events.

## Lifecycle

Active research stages:

- Applied
- Zoning Certified
- Ready to Issue
- Issued

Occupancy granted, closed, cancelled, revoked and deemed-abandoned records are
retained as lifecycle evidence but are not active signal candidates.

## Safety

Classification alone does not make a permit an opportunity. Every record has
`outreach_eligible = false` until entity matching, exclusion controls, current
verification and the pilot's success criteria are implemented.
