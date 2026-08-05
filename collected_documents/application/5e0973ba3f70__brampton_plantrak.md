# Brampton Plantrak Source Access Review

## Current decision

- Source state: `review`
- Metadata inspection: permitted in the alpha
- Bulk snapshot acquisition: fail-closed
- Production scoring use: not approved

## Evidence currently recorded

1. The City of Brampton describes GeoHub as its open-data portal.
2. The city's open-data page describes open data as machine-readable,
   freely shared, used and built upon without restrictions.
3. The Plantrak ArcGIS service is publicly reachable and identifies
   the City of Brampton as the copyright holder.
4. The city's general website terms disclaim accuracy and require
   users to verify information independently.
5. The project has not yet connected the exact Plantrak MapServer
   to a definitive GeoHub catalogue record or written permission.

## Required approval evidence

At least one of:

- A GeoHub catalogue record that clearly connects to this service
  and states the applicable licence;
- A dataset-specific licence attached to the service;
- Written clarification from the City of Brampton open-data team.

## Operational rule

Until approval evidence is recorded, the connector may inspect
service and layer metadata but must reject full data acquisition.
