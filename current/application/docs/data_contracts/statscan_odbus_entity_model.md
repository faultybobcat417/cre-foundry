# ODBus Entity Model

Every silver source row remains available in
`silver.odbus_entity_observations`.

Safe repeated identity clusters become one canonical entity. Licence,
NAICS, employee and sector variations remain separate observations.

Clusters differing by address, business ID, provider or municipality
are not collapsed. Each observation remains a separate candidate
entity linked through `unresolved_cluster_id`.

No ODBus entity is considered currently verified.
