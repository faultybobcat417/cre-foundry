# Brampton Industrial Building Permits

## Access decision

`approved`

The City of Brampton publishes building-permit information through its
public open-data infrastructure and describes open data as information
that may be freely shared, used and built upon.

## Approved technical scope

- ArcGIS FeatureServer layer `0`
- Only records whose `SUBDESC` is:
  - `F1: Industrial`
  - `F2: Industrial`
  - `F3: Industrial`
- Read-only ArcGIS REST queries
- Deterministic object-ID batching
- Immutable compressed GeoJSON snapshots
- Required attribution: City of Brampton Open Data

Activity layer `1` and upcoming-inspection layer `2` are not included in
the first acquisition contract.

## Safety constraints

- Unexpected permit categories fail the acquisition.
- Historical or current permit records are never automatically treated
  as outreach opportunities.
- `outreach_eligible` remains false.
- Entity matching and client exclusion controls must be implemented
  before any operational use.
