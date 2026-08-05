BEGIN TRANSACTION;

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE
    silver.odbus_industrial_observation_evidence
AS
SELECT
    entity_id,
    source_record_id,
    resolution_status,
    current_status_verified,
    naics_primary,

    CASE
        WHEN regexp_matches(
            naics_primary,
            '^(31|32|33)'
        )
        THEN 'manufacturing'

        WHEN regexp_matches(
            naics_primary,
            '^41'
        )
        THEN 'wholesale'

        WHEN regexp_matches(
            naics_primary,
            '^(48|49)'
        )
        THEN 'transport_warehousing'

        WHEN regexp_matches(
            naics_primary,
            '^(236|237|238)'
        )
        THEN 'construction_trades'

        WHEN regexp_matches(
            naics_primary,
            '^(562|56173|56174|56179|56191)'
        )
        THEN 'industrial_facility_services'

        WHEN naics_primary = '23'
        THEN 'broad_construction_review'

        WHEN naics_primary = '56'
        THEN 'broad_support_review'

        ELSE NULL
    END AS segment_name,

    CASE
        WHEN regexp_matches(
            naics_primary,
            '^(31|32|33|41|48|49)'
        )
        THEN 'core'

        WHEN regexp_matches(
            naics_primary,
            '^(236|237|238|562|56173|56174|56179|56191)'
        )
        THEN 'adjacent'

        WHEN naics_primary IN ('23', '56')
        THEN 'review'

        ELSE NULL
    END AS segment_tier,

    CASE
        WHEN naics_primary IN ('23', '56')
        THEN 'low'

        WHEN length(naics_primary) = 2
        THEN 'medium'

        ELSE 'high'
    END AS evidence_precision

FROM silver.odbus_entity_observations

WHERE
    naics_primary IS NOT NULL
    AND (
        regexp_matches(
            naics_primary,
            '^(31|32|33|41|48|49|236|237|238|562|56173|56174|56179|56191)'
        )
        OR naics_primary IN ('23', '56')
    );

CREATE OR REPLACE TABLE
    silver.odbus_industrial_entities
AS
WITH evidence AS (
    SELECT
        entity_id,

        count(*) AS evidence_observation_count,

        count(
            DISTINCT segment_name
        ) FILTER (
            WHERE segment_tier <> 'review'
        ) AS assigned_segment_count,

        count(*) FILTER (
            WHERE segment_tier = 'review'
        ) AS review_evidence_count,

        min(segment_name) FILTER (
            WHERE segment_tier <> 'review'
        ) AS assigned_segment_name,

        min(segment_tier) FILTER (
            WHERE segment_tier <> 'review'
        ) AS assigned_segment_tier,

        min(segment_name) FILTER (
            WHERE segment_tier = 'review'
        ) AS review_segment_name,

        min(evidence_precision) AS minimum_precision

    FROM
        silver.odbus_industrial_observation_evidence

    GROUP BY entity_id
)

SELECT
    e.entity_id,
    e.municipality,
    e.canonical_business_name,
    e.canonical_address,
    e.postal_code,
    e.latitude,
    e.longitude,
    e.employee_count_min,
    e.employee_count_max,
    e.resolution_status,
    e.current_status_verified,

    v.evidence_observation_count,
    v.assigned_segment_count,
    v.review_evidence_count,
    v.minimum_precision,

    CASE
        WHEN v.assigned_segment_count > 1
        THEN 'mixed_industrial_evidence'

        WHEN v.assigned_segment_count = 1
        THEN v.assigned_segment_name

        ELSE v.review_segment_name
    END AS segment_name,

    CASE
        WHEN v.assigned_segment_count > 1
        THEN 'review'

        WHEN v.assigned_segment_count = 1
        THEN v.assigned_segment_tier

        ELSE 'review'
    END AS segment_tier,

    (
        v.assigned_segment_count = 1
        AND e.resolution_status <> 'unresolved_split'
    ) AS baseline_eligible,

    (
        v.assigned_segment_count = 1
        AND v.assigned_segment_tier = 'core'
        AND e.resolution_status <> 'unresolved_split'
    ) AS core_pool_eligible,

    false AS outreach_eligible

FROM silver.odbus_entities AS e

JOIN evidence AS v
USING (entity_id);

CREATE OR REPLACE VIEW
    silver.odbus_industrial_segment_summary
AS
SELECT
    segment_tier,
    segment_name,
    count(*) AS entities,
    count(*) FILTER (
        WHERE baseline_eligible
    ) AS baseline_eligible_entities,
    count(*) FILTER (
        WHERE core_pool_eligible
    ) AS core_pool_entities,
    count(*) FILTER (
        WHERE resolution_status = 'unresolved_split'
    ) AS unresolved_entities
FROM silver.odbus_industrial_entities
GROUP BY
    segment_tier,
    segment_name;

COMMIT;
