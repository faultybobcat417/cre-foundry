# Brampton Business Directory Silver

The latest successful licensed production snapshot is normalized into:

- `silver.brampton_business_directory`
- `silver.brampton_business_directory_summary`

## Record identity

`GLOBALID` is the stable source record key.

`OBJECTID` and `GLOBALID` must both be present and unique. Company names
and addresses are not unique identifiers because businesses may have
multiple locations and buildings may contain multiple businesses.

## Current-directory evidence

Every silver row was returned from the approved production query:

`OPERATIONAL = 'YES'`

The field `directory_operational_at_snapshot` therefore means only that
the City directory classified that record as operational at acquisition
time.

## Safety

Directory presence does not prove:

- a current commercial real-estate requirement;
- the identity of a relevant decision-maker;
- permission or appropriateness for outreach.

Accordingly:

- `commercial_requirement_verified = false`
- `decision_maker_verified = false`
- `outreach_eligible = false`
