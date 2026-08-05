# SQL Safety Remediation Inventory

This inventory preserves every blocking B608 finding and binds it to its source and statement digests before any source rewrite occurs.

- Blocking B608 findings: `19`
- Affected files: `11`
- Affected scopes: `15`
- Existing parameter-binding signals: `6`
- Discovered test references: `46`
- Secret review findings: `506`
- Likely digest artifacts: `445`
- License review items: `5`
- Automatic rewrites: `0`
- Automatic suppressions: `0`
- Automatic risk acceptances: `0`
- Database access: `0`
- Database writes: `0`
- Security gate passed: `false`

## Remediation waves

1. Parameterize Parquet and other file paths; separate fixed table structure from path values.
2. Introduce one strict qualified-identifier validation and quoting layer.
3. Refactor projection, column and INSERT query construction onto the shared safety layer.
4. Manually investigate any query shape that cannot be proven safe mechanically.

## Blocking locations

### src/cre_foundry/brampton_business_directory_silver.py:530

- Scope: `build_brampton_business_directory_silver`
- Query kind: `parquet_path_ingestion`
- Remediation wave: `1`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `2`
- Source digest: `280f1972dc06a06ee5de11c8f8fb030c840476ac2a17697b883fb57ffaba2e05`
- Statement digest: `505c24b012ef0391b7ba50b3b4edaed00d02ec0809fc8a9deaa7e7626fe0421b`

Bind the file path as a DuckDB value parameter or use the Python read_parquet relation API; keep the destination identifier fixed or strictly validated.

### src/cre_foundry/brampton_cross_source_reconciliation.py:549

- Scope: `build_brampton_cross_source_reconciliation`
- Query kind: `dynamic_insert`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `true`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `879ea3d2bfc11d82f9c1c6007bdbc546d786228c6f7275573234397060ff38f1`
- Statement digest: `a8d3120334adf0d79ef8ea6890fbf7cef6abfb080b6b84ff84b6f245f8bd2c8e`

Validate and quote table and column identifiers; bind every row value through execute parameters.

### src/cre_foundry/brampton_permit_silver.py:361

- Scope: `build_brampton_permit_silver`
- Query kind: `dynamic_insert`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `true`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `d372bf778791c22db5562645f1ec39ac1cf5635feb78ab9c23d20ff619732af5`
- Statement digest: `84555a74898642e4b4e80cab95213e4abfeeb8ab85c655c52f8ee0d3187436da`

Validate and quote table and column identifiers; bind every row value through execute parameters.

### src/cre_foundry/brampton_permit_silver.py:396

- Scope: `build_brampton_permit_silver`
- Query kind: `parquet_path_ingestion`
- Remediation wave: `1`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `d372bf778791c22db5562645f1ec39ac1cf5635feb78ab9c23d20ff619732af5`
- Statement digest: `b71092391127aa9a6286b1d1a72c5f953076ea0efb88a4da9b684ea740ebdbeb`

Bind the file path as a DuckDB value parameter or use the Python read_parquet relation API; keep the destination identifier fixed or strictly validated.

### src/cre_foundry/brampton_verification_ledger.py:1066

- Scope: `project_verification_state`
- Query kind: `dynamic_insert`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `true`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `9eb04932a9d218ff14800bc7f2502007dd7801127dd1c7f02a22b7ddf2a73d48`
- Statement digest: `3d2e2c6f294a518e60b436e788c3b4ff6f35029fee313065ec8f2697c318834c`

Validate and quote table and column identifiers; bind every row value through execute parameters.

### src/cre_foundry/brampton_verification_ledger.py:1109

- Scope: `project_verification_state`
- Query kind: `dynamic_insert`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `true`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `9eb04932a9d218ff14800bc7f2502007dd7801127dd1c7f02a22b7ddf2a73d48`
- Statement digest: `4642229511ccfa634f8ac165874ae123b0311a219c30eb6e77ce84f1153e99c9`

Validate and quote table and column identifiers; bind every row value through execute parameters.

### src/cre_foundry/data_plane.py:813

- Scope: `_warehouse_inventory`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `2`
- Source digest: `4f152987fbe8ef6bec02c31ed7731ce700a619ad34038b44f1de6676c97786a9`
- Statement digest: `08b8dc8376c6a288640fd3be7c5125a60a6c3bfd92cd2f66f8984d2b910fb8ac`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.

### src/cre_foundry/data_plane.py:834

- Scope: `_warehouse_inventory`
- Query kind: `dynamic_projection_or_relation`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `2`
- Test references: `2`
- Source digest: `4f152987fbe8ef6bec02c31ed7731ce700a619ad34038b44f1de6676c97786a9`
- Statement digest: `8ba656c93e6f5852a797f40f7983cf4a39bbf3ed8420700f43dba2566deb181a`

Construct only validated identifier tokens; bind all data values separately.

### src/cre_foundry/data_plane.py:923

- Scope: `_sqlite_inventory`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `2`
- Source digest: `4f152987fbe8ef6bec02c31ed7731ce700a619ad34038b44f1de6676c97786a9`
- Statement digest: `24e34ab75edcbc957ba7e2e26a7b1f01f38418d7abf7e474d6c3a7dbd811e5b8`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.

### src/cre_foundry/odbus_silver.py:505

- Scope: `load_silver_into_duckdb`
- Query kind: `parquet_path_ingestion`
- Remediation wave: `1`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `eb370d10e0dfc9f0393bea7469be0dadd6619b71c08c27107cf18626e239eae9`
- Statement digest: `2632527606b2d9abf41e58edd977a32c481312fe35baa0424c71670efc2bdbf5`

Bind the file path as a DuckDB value parameter or use the Python read_parquet relation API; keep the destination identifier fixed or strictly validated.

### src/cre_foundry/odbus_silver.py:515

- Scope: `load_silver_into_duckdb`
- Query kind: `parquet_path_ingestion`
- Remediation wave: `1`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `1`
- Source digest: `eb370d10e0dfc9f0393bea7469be0dadd6619b71c08c27107cf18626e239eae9`
- Statement digest: `3cab6451b352c70ab2efe3d060b18929a16a49e3526d362a41d28b0a178c1ea0`

Bind the file path as a DuckDB value parameter or use the Python read_parquet relation API; keep the destination identifier fixed or strictly validated.

### src/cre_foundry/pilot_readiness.py:197

- Scope: `_relation_metrics`
- Query kind: `dynamic_projection_or_relation`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `5`
- Test references: `3`
- Source digest: `92f1bdf1a7e6254b57ea6e0cd565be13887aef642f7e608f43f566363d2f967f`
- Statement digest: `eac6a4bfe68a03e2fee41a79c6ee2966f1079b46b73d723bf84fc1f57c3e030d`

Construct only validated identifier tokens; bind all data values separately.

### src/cre_foundry/primitive_inventory.py:291

- Scope: `_duckdb_inventory`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `6`
- Source digest: `e45f5f0ec6d6986d27e5a564b2c174216ca03f58c23868dddea9317e71fea7ec`
- Statement digest: `190c6afdc464eab937dbdac472355c32727507f46ca97b18b384c1d89bf1f037`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.

### src/cre_foundry/primitive_inventory.py:419

- Scope: `_sqlite_inventory`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `6`
- Source digest: `e45f5f0ec6d6986d27e5a564b2c174216ca03f58c23868dddea9317e71fea7ec`
- Statement digest: `050863549e13fcbe20ec707fd5bc8bfbaaeb4d9e26f27874bba4d783dc5c27fe`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.

### src/cre_foundry/primitive_quality.py:554

- Scope: `_duckdb_profile_relation`
- Query kind: `dynamic_distinct_projection`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `true`
- Dynamic expressions: `2`
- Test references: `5`
- Source digest: `4c632de37553dead1a1be1689f4b491a7851e309661006af7f17fc401ff4db03`
- Statement digest: `403c9cad67454e3de22e3b163ef871094b7c6160436a83dea093eaf41f29a11f`

Validate and quote relation and column identifiers; keep LIMIT and filter values parameter-bound.

### src/cre_foundry/primitive_quality.py:675

- Scope: `_sqlite_profile_relation`
- Query kind: `dynamic_distinct_projection`
- Remediation wave: `3`
- Review priority: `critical-review`
- Parameter binding present: `true`
- Dynamic expressions: `2`
- Test references: `5`
- Source digest: `4c632de37553dead1a1be1689f4b491a7851e309661006af7f17fc401ff4db03`
- Statement digest: `8680371ff802442164f8b832583f7758c886c2435ff208706378d36afa9e5120`

Validate and quote relation and column identifiers; keep LIMIT and filter values parameter-bound.

### src/cre_foundry/shadow_learning.py:472

- Scope: `audit_shadow_learning`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `2`
- Source digest: `c308ff418d4c65591992666979da66ce1a914bb6588797563fb92dff013ee198`
- Statement digest: `a42739c88dd94bc12b9e92b6e1f074359e14dec27ab077586625e9930bee735c`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.

### src/cre_foundry/source_operations.py:490

- Scope: `initialize_source_operations`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `2`
- Source digest: `c0fb86dea807d7d06f4d38f14c925a252c3a575786366f057951584fd49518e8`
- Statement digest: `4482b2550b5817c8220d88fc37504a38191eb0d980f133df4b907381b4d5eab3`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.

### src/cre_foundry/source_operations.py:895

- Scope: `audit_source_operations`
- Query kind: `dynamic_relation_count`
- Remediation wave: `2`
- Review priority: `critical-review`
- Parameter binding present: `false`
- Dynamic expressions: `1`
- Test references: `2`
- Source digest: `c0fb86dea807d7d06f4d38f14c925a252c3a575786366f057951584fd49518e8`
- Statement digest: `4482b2550b5817c8220d88fc37504a38191eb0d980f133df4b907381b4d5eab3`

Route the relation through a strict qualified-identifier validator and quoting function before SQL construction.
