# Brampton Business Directory

## Production decision

`approved`

Approved source:

- Item: `3cd59a895f404612b57e4c84fc8931be`
- Service: `Economic_Development/FeatureServer/0`
- Owner: `BramptonMaps`
- Attribution: `Brampton Economic Development`
- Licence: `CC BY`
- Scope: records with `OPERATIONAL = 'YES'`

The current Brampton Business Directory PRD experience references this
production item and production service.

## UAT decision

`blocked`

Blocked source:

- Item: `9e0656bfa1174df08d99c1ef4c11759e`
- Service: `Economic_Development_UAT/FeatureServer`
- Item licence: internal testing use only

The production and UAT schemas are similar, but licensing and lineage are
not interchangeable. The connector rejects any attempt to substitute the
UAT item or URL.

## Safety

The directory is evidence of an operational business record in the City
dataset at acquisition time. It is not proof that:

- the business remains at the location after the snapshot;
- the listed contact is the relevant decision-maker;
- the business has a commercial real-estate requirement;
- outreach is permissible or appropriate.

Bronze acquisition never produces `outreach_eligible = true`.
