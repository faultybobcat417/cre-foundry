# SIGNAL_PRIMITIVE_CATALOG_V2.md

## Design rule

Collectors create durable primitives. Models create features. Raw webpages,
current portal state and field notes are never treated as timeless model
features.

## Primitive families

### Identity and location

- legal-entity version;
- operating-business and brand alias;
- establishment/location version;
- standardized address and geocode;
- parcel, building and property identity;
- owner and occupier intervals;
- predecessor/successor lineage.

### Government and regulatory events

- permit application/stage/status version;
- planning application and proposed-use version;
- licence issue, amendment, suspension and cancellation;
- environmental permission and amendment;
- inspection/enforcement event;
- contract and grant award stage.

### Operating signals

- employer-location job posting;
- positive LMIA employer quarter;
- importer product/city vintage;
- regulated activity and class;
- employment-range vintage;
- public project stage and geography.

### Market and property context

- submarket quarter with definition version;
- listing first-seen/last-seen and duplicate group;
- zoning/use snapshot;
- property characteristic and assessment vintage;
- road/access event interval.

## Mandatory clocks

- source effective time;
- publication time;
- first observed time;
- retrieval time;
- valid-from and valid-to;
- correction time;
- deletion/tombstone time.

## Forbidden shortcuts

- current record substituted for historical state;
- address equality treated as entity identity;
- source disappearance treated as business closure;
- post-contact field response copied into the original decision feature set;
- permit issue/completion state backfilled into an earlier application date;
- broker listing age assumed to equal market exposure without first-seen history.
