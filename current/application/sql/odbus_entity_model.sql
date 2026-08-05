BEGIN TRANSACTION;

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.odbus_entity_observations AS
WITH cluster_stats AS (
    SELECT
        entity_fingerprint,
        count(*) AS cluster_observation_count,
        count(DISTINCT full_address) AS address_count,
        count(DISTINCT business_id_number) AS business_id_count,
        count(DISTINCT provider) AS provider_count,
        count(DISTINCT municipality) AS municipality_count,
        count(DISTINCT licence_number) AS licence_count,
        count(DISTINCT naics_primary) AS naics_count,
        count(DISTINCT employee_count_raw) AS employee_value_count,
        count(DISTINCT business_sector) AS sector_count
    FROM silver.odbus_target_businesses
    GROUP BY entity_fingerprint
),
classified AS (
    SELECT
        *,
        CASE
            WHEN
                address_count > 1
                OR business_id_count > 1
                OR provider_count > 1
                OR municipality_count > 1
            THEN 'ambiguous_identity'

            WHEN
                cluster_observation_count > 1
                AND licence_count > 1
                AND naics_count <= 1
                AND employee_value_count <= 1
                AND sector_count <= 1
            THEN 'multi_licence_same_entity'

            WHEN cluster_observation_count > 1
            THEN 'attribute_variation_same_identity'

            ELSE 'singleton'
        END AS cluster_classification
    FROM cluster_stats
)
SELECT
    CASE
        WHEN c.cluster_classification = 'ambiguous_identity'
        THEN
            'ENT-AMB-'
            || substr(b.entity_fingerprint, 1, 24)
            || '-'
            || b.source_record_id
        ELSE
            'ENT-'
            || substr(b.entity_fingerprint, 1, 32)
    END AS entity_id,

    CASE
        WHEN c.cluster_classification = 'ambiguous_identity'
        THEN
            'CLU-'
            || substr(b.entity_fingerprint, 1, 32)
        ELSE NULL
    END AS unresolved_cluster_id,

    CASE
        WHEN c.cluster_classification = 'ambiguous_identity'
        THEN 'unresolved_split'
        WHEN c.cluster_observation_count > 1
        THEN 'resolved_cluster'
        ELSE 'singleton'
    END AS resolution_status,

    c.cluster_classification,
    c.cluster_observation_count,
    b.*
FROM silver.odbus_target_businesses AS b
JOIN classified AS c
USING (entity_fingerprint);

CREATE OR REPLACE TABLE silver.odbus_entities AS
WITH scored AS (
    SELECT
        *,
        (
            CASE WHEN business_name IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN alternate_business_name IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN full_address IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN postal_code IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN longitude IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN business_id_number IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN licence_number IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN naics_primary IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN employee_count_raw IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN business_sector IS NOT NULL THEN 1 ELSE 0 END
            + CASE WHEN provider IS NOT NULL THEN 1 ELSE 0 END
        ) AS representative_score
    FROM silver.odbus_entity_observations
),
ranked AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY entity_id
            ORDER BY
                representative_score DESC,
                source_record_id
        ) AS representative_rank
    FROM scored
),
aggregated AS (
    SELECT
        entity_id,
        max(unresolved_cluster_id) AS unresolved_cluster_id,
        max(resolution_status) AS resolution_status,
        max(cluster_classification) AS cluster_classification,
        count(*) AS observation_count,
        count(DISTINCT licence_number) AS licence_count,
        count(DISTINCT full_address) AS address_count,
        count(DISTINCT business_id_number) AS business_id_count,
        count(DISTINCT provider) AS provider_count,
        count(DISTINCT naics_primary) AS naics_count,
        count(DISTINCT employee_count_raw) AS employee_value_count,
        count(DISTINCT business_sector) AS sector_count
    FROM silver.odbus_entity_observations
    GROUP BY entity_id
)
SELECT
    r.entity_id,
    a.unresolved_cluster_id,
    a.resolution_status,
    a.cluster_classification,

    r.municipality,
    r.business_name AS canonical_business_name,
    r.alternate_business_name,
    r.full_address AS canonical_address,
    r.postal_code,
    r.latitude,
    r.longitude,

    r.business_id_number,
    r.naics_2d,
    r.naics_primary,
    r.business_sector,
    r.business_subsector,
    r.employee_count_min,
    r.employee_count_max,
    r.status_normalized,
    r.provider,

    a.observation_count,
    a.licence_count,
    a.address_count,
    a.business_id_count,
    a.provider_count,
    a.naics_count,
    a.employee_value_count,
    a.sector_count,

    (
        a.naics_count > 1
        OR a.employee_value_count > 1
        OR a.sector_count > 1
    ) AS has_attribute_variation,

    false AS current_status_verified
FROM ranked AS r
JOIN aggregated AS a
USING (entity_id)
WHERE r.representative_rank = 1;

CREATE OR REPLACE VIEW silver.odbus_entity_resolution_summary AS
SELECT
    resolution_status,
    cluster_classification,
    count(*) AS entity_count,
    sum(observation_count) AS observation_count
FROM silver.odbus_entities
GROUP BY
    resolution_status,
    cluster_classification;

COMMIT;
