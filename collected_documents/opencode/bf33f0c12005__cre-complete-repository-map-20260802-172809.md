# CRE Complete Repository and Codex Preservation Map

- Generated: `2026-08-02T17:28:09`
- Repository: `/Users/alimehdi/Documents/cre`
- Branch: `handoff/kimi-architecture-001`
- HEAD: `9a5462d5144196ef944ee884952fd25f433a05a2`
- Tracked files: **518**
- Tracked text lines: **181,947**
- Source/config files: **86**
- Source/config lines: **13,096**
- Untracked files: **3**

## 1. Git State

```text
## handoff/kimi-architecture-001
?? control/ONE_SHOT_READINESS.json
?? opencode.json
?? opencode.json.before-direct-kimi-20260802-172550
```

### Worktrees
```text
/Users/alimehdi/Documents/cre 9a5462d [handoff/kimi-architecture-001]
```

### Stashes
```text
(none)
```

### Recent commits
```text
9a5462d | 2026-08-02 05:51:54 -0400 | Engine | wip: preserve interrupted ARCHITECTURE-001 handoff
aecb0fd | 2026-08-02 05:16:50 -0400 | Engine | control: checkpoint calibration and start architecture
55cc918 | 2026-08-02 05:04:22 -0400 | Engine | calibration: implement exact synthetic uncertainty framework
8513578 | 2026-08-02 03:40:41 -0400 | Engine | calibration: freeze synthetic evaluator contract
b6471df | 2026-08-02 03:24:29 -0400 | Engine | chore: complete baseline and select calibration
05137e8 | 2026-08-02 03:08:01 -0400 | Engine | baseline: implement point-in-time synthetic comparisons
8fd5cf8 | 2026-08-02 02:24:23 -0400 | Engine | baseline: freeze synthetic evaluator contract
b802776 | 2026-08-02 02:15:48 -0400 | Engine | chore: complete outcomes and select baseline
5c19588 | 2026-08-02 02:02:31 -0400 | Engine | chore: rebind frontier meta to outcomes proof
746702d | 2026-08-02 02:01:38 -0400 | Engine | outcomes: harden synthetic maturity and lineage contracts
0b4638d | 2026-08-02 01:11:00 -0400 | Engine | outcomes: freeze maturity evaluator contract
8330a8f | 2026-08-02 01:03:29 -0400 | Engine | chore: complete vertical and select outcomes
c263aa7 | 2026-08-02 00:55:01 -0400 | Engine | chore: rebind frontier meta to vertical proof
9d28360 | 2026-08-02 00:49:16 -0400 | Engine | vertical: complete deterministic synthetic shadow slice
0614230 | 2026-08-02 00:00:20 -0400 | Engine | vertical: define route event and outcome contracts
cff2338 | 2026-08-01 23:56:31 -0400 | Engine | vertical: freeze synthetic slice evaluator contract
63b5be5 | 2026-08-01 23:53:56 -0400 | Engine | chore: complete contract spine and begin vertical slice
beebe44 | 2026-08-01 23:50:00 -0400 | Engine | test: bind contract evaluation report
551c90d | 2026-08-01 23:48:25 -0400 | Engine | contract: implement synthetic source-to-decision spine
a918e2b | 2026-08-01 23:24:37 -0400 | Engine | contract: freeze thin-spine evaluator contract
b44d73b | 2026-08-01 23:22:11 -0400 | Engine | chore: advance to contract spine task
096dc9e | 2026-08-01 23:20:30 -0400 | Engine | test: bind frontier meta to math completion
3950c53 | 2026-08-01 23:19:50 -0400 | Engine | math: complete public formal contract
a15bf29 | 2026-08-01 23:03:54 -0400 | Engine | test: bind frontier meta to math checkpoint
6b9fc93 | 2026-08-01 23:02:59 -0400 | Engine | math: implement bounded exact-ten oracle
50df16e | 2026-08-01 22:26:43 -0400 | Engine | math: freeze public evaluator contract
61147e2 | 2026-08-01 22:23:57 -0400 | Engine | math: begin evaluator-first oracle task
f2cb174 | 2026-08-01 22:21:38 -0400 | Engine | research: complete task and begin math contract
2f8d2a7 | 2026-08-01 22:15:17 -0400 | Engine | chore: refresh frontier meta binding
89d5d29 | 2026-08-01 22:15:12 -0400 | Engine | test: reconcile mutation completion reports
```

## 2. Repository Areas

| Top-level area | Tracked files | All lines | Source/config files | Source/config lines |
|---|---:|---:|---:|---:|
| `.gitignore` | 1 | 14 | 0 | 0 |
| `AGENTS.md` | 1 | 43 | 0 | 0 |
| `README.md` | 1 | 42 | 0 | 0 |
| `artifacts` | 104 | 143,694 | 0 | 0 |
| `bootstrap` | 129 | 17,769 | 19 | 933 |
| `contracts` | 24 | 1,770 | 0 | 0 |
| `control` | 7 | 3,599 | 0 | 0 |
| `docs` | 2 | 107 | 0 | 0 |
| `evals` | 198 | 7,561 | 27 | 5,321 |
| `pyproject.toml` | 1 | 14 | 1 | 14 |
| `scripts` | 26 | 4,421 | 26 | 4,421 |
| `src` | 13 | 2,407 | 13 | 2,407 |
| `tasks` | 10 | 257 | 0 | 0 |
| `uv.lock` | 1 | 249 | 0 | 0 |

## 3. Complete Current Directory Tree

```text
cre/
    .gitignore
    AGENTS.md
    artifacts/
    bootstrap/
    contracts/
    control/
    docs/
    evals/
    opencode.json
    opencode.json.before-direct-kimi-20260802-172550
    pyproject.toml
    README.md
    scripts/
    src/
    tasks/
    uv.lock
        architecture/
        baselines/
        bootstrap/
        calibration/
        context/
        contracts/
        evaluations/
        math/
        models/
        outcomes/
        research/
        task-results/
        vertical/
        vertical-slice/
        BOOTSTRAP-001.partial.json
        GATE-OS-ARTIFACT-001.json
        project_os_v2.2/
        autonomous_frontier_contract.schema.json
        baseline_evaluation.schema.json
        baseline_policy.schema.json
        calibration_evaluation.schema.json
        calibration_input.schema.json
        calibration_uncertainty.schema.json
        estimand_registry.schema.json
        f9_outcome.schema.json
        f9_outcome_input_ledger.schema.json
        f9_window_policy.schema.json
        math_authority_input.schema.json
        math_decision_policy.schema.json
        math_route_decision.schema.json
        research/
        route_decision.schema.json
        synthetic_f9_outcome.schema.json
        synthetic_field_event.schema.json
        synthetic_route_day.schema.json
        thin_slice_candidate.schema.json
        thin_slice_observation.schema.json
        AUTONOMOUS_FRONTIER_CONTRACT.json
        CURRENT_STATE.json
        CURRENT_TASK.json
        DECISIONS.md
        EVALUATOR_DECISION.json
        GATES.json
        ONE_SHOT_READINESS.json
        TASK_GRAPH.json
        contracts/
        research/
        known_bad/
        public/
        reference/
        build_math_contracts.py
        build_research_contract.py
        capture_public_research_evidence.py
        compile_repository_task_context.py
        evaluate_autonomous_frontier.py
        finalize_math_contracts.py
        finalize_research_bundle.py
        generate_baseline_artifacts.py
        generate_calibration_artifacts.py
        import_independent_research_capture.py
        import_independent_row_witness.py
        prove_known_bad_fails.py
        run_research_mutation.py
        validate_baseline_framework.py
        validate_baseline_models.py
        validate_calibration_framework.py
        validate_calibration_uncertainty.py
        validate_contract_spine.py
        validate_control_plane.py
        validate_frontier_meta.py
        validate_math_contracts.py
        validate_mission_integrity.py
        validate_outcomes_labels.py
        validate_research_completion.py
        validate_source_feasibility.py
        validate_vertical_slice.py
        cre_foundry/
        ARCHITECTURE-001.json
        BASELINE-001.json
        CALIBRATION-001.json
        CONTRACT-001.json
        FRONTIER-001.json
        IDENTITY-001.json
        MATH-001.json
        OUTCOMES-001.json
        RESEARCH-001.json
        VERTICAL-001.json
            ARCHITECTURE-001-start.json
            public_evaluator_contract.json
            BASELINE-001-start.json
            canonical_run.json
            capability_classification_reconciliation.json
            frozen_benchmark.json
            policy_registry.json
            public_evaluator_contract.json
            archive_verification.json
            capability_manifest.json
            contradiction_register.json
            expertise_coverage.json
            input_classification.json
            repository_inventory.json
            CALIBRATION-001-start.json
            canonical_run.json
            frozen_input.json
            public_evaluator_contract.json
            current_task_packet.json
            current_task_packet.md
            CONTRACT-001-start.json
            contract_spine.json
            public_evaluator_contract.json
            autonomous_frontier_meta.json
            autonomous_frontier_report.json
            baseline_framework.json
            baseline_model_synthetic.json
            calibration_framework.json
            calibration_synthetic.json
            contract_spine.json
            known_bad_direct_result.json
            known_bad_public_result.json
            math_contracts.json
            outcomes_synthetic.json
            public_evaluator_manifest.json
            vertical_slice.json
            estimand_registry.json
            formal_decisions.json
            human_authority_input_template.json
            MATH-001-start.json
            public_evaluator_contract.json
            model_registry.json
            canonical_run.json
            capability_classification_reconciliation.json
            itt_inclusion_cases.json
            OUTCOMES-001-start.json
            public_evaluator_contract.json
            scenario_matrix.json
            synthetic_input_ledger.json
            synthetic_window_policy.json
            bundle_manifest.json
            canonical_field_map.json
            claim_evidence_graph.json
            counterevidence_register.json
            raw/
            RESEARCH-001-adversarial-sweep.json
            RESEARCH-001-start.json
            research_completion_report.json
            source_feasibility_registry.json
            source_feasibility_registry.v0.json
            source_reproduction_report.json
            toronto_business_licences_metadata_probe.v0.json
            BASELINE-001.json
            BOOTSTRAP-001.json
            CALIBRATION-001.json
            CONTRACT-001.json
            FRONTIER-001.json
            MATH-001.json
            OUTCOMES-001.json
            RESEARCH-001.json
            RESEARCH-001.partial.json
            VERTICAL-001.json
            public_evaluator_contract.json
            VERTICAL-001-start.json
            run_manifest.json
            CRE_Codex_Project_OS_v2.2/
            canonical_field_map.schema.json
            claim_evidence_graph.schema.json
            counterevidence_register.schema.json
            source_feasibility_registry.schema.json
            source_reproduction_report.schema.json
            THIN_SLICE_CONTRACT.md
            RESEARCH-001-source-feasibility.md
            always_abstain.py
            exact_name_only_clearance.py
            frontier/
            math/
            baseline_framework_evaluator.py
            calibration_framework_evaluator.py
            contract_spine_evaluator.py
            fixtures/
            math_oracle_evaluator.py
            outcomes_labels_evaluator.py
            route_decision_evaluator.py
            test_autonomous_frontier.py
            test_baseline_framework.py
            test_calibration_framework.py
            test_contract_spine.py
            test_math_contracts.py
            test_outcomes_labels.py
            test_research_completion.py
            test_route_decision_evaluator.py
            test_vertical_slice.py
            vertical_slice_evaluator.py
            fail_closed_reference.py
            __init__.py
            baselines/
            calibration/
            contracts/
            math/
            outcomes/
            vertical/
                independent/
                manifest.json
                on_ogl_terms.html
                on_select_package.json
                on_select_schema.json
                row_witness/
                tor_coa_2001_schema.json
                tor_coa_2016_schema.json
                tor_coa_active_schema.json
                tor_coa_closed_schema.json
                tor_coa_package.json
                tor_ogl_terms.html
                launch_kernel/
                reference_vault/
                baseline_all_row_score_projection.json
                baseline_candidate_set_asymmetry.json
                baseline_complexity_tie_promoted.json
                baseline_coordinated_feature_rehash.json
                baseline_coordinated_registry_rehash.json
                baseline_duplicate_location.json
                baseline_duplicate_route_seed.json
                baseline_feature_clock_reordered.json
                baseline_feature_view_asymmetry.json
                baseline_forged_label_view.json
                baseline_forged_math_problem_hash.json
                baseline_future_feature.json
                baseline_future_label_asof.json
                baseline_future_recency_value.json
                baseline_immature_as_negative.json
                baseline_issue_nine.json
                baseline_label_denominator_asymmetry.json
                baseline_math_input_contamination.json
                baseline_metric_wrong_denominator.json
                baseline_missing_required_policy.json
                baseline_nondeterministic_random.json
                baseline_outcome_feature.json
                baseline_outcome_source_family.json
                baseline_partial_labels_finalized.json
                baseline_policy_direct_selection.json
                baseline_production_promotion.json
                baseline_protected_selected.json
                baseline_receipt_only.json
                baseline_rehashed_future_feature.json
                baseline_rehashed_metrics.json
                baseline_rehashed_null_label.json
                baseline_rehashed_policy_score.json
                baseline_rehashed_random.json
                baseline_rehashed_receipt.json
                baseline_rehashed_split.json
                baseline_rehashed_universe.json
                baseline_replacement_with_more_abstention.json
                baseline_seed_cherrypick.json
                baseline_split_overlap.json
                baseline_split_temporal_order.json
                baseline_stat_fraction_rounded.json
                baseline_stat_null_label.json
                baseline_synthetic_as_predictive.json
                baseline_test_label_in_fit.json
                baseline_test_reuse.json
                baseline_unseeded_random.json
                baseline_winner_below_margin.json
                calibration_abstain_as_negative_or_itt_excluded.json
                calibration_abstain_dropped.json
                calibration_bin_gap_or_overlap.json
                calibration_calibrated_value_not_projected.json
                calibration_calibrator_fit_count_change.json
                calibration_common_asof_divergence.json
                calibration_common_nonscore_math_change.json
                calibration_drop_unknown_candidate.json
                calibration_empty_bin_point_estimate.json
                calibration_forged_label_lineage.json
                calibration_future_feature_in_probability.json
                calibration_future_label_in_fit.json
                calibration_issue_nine_or_direct_selection.json
                calibration_label_visible_before_prediction_freeze.json
                calibration_micro_reported_as_macro.json
                calibration_missing_probability_as_zero.json
                calibration_missing_subgroup_as_reference.json
                calibration_nonmonotonic_calibration_clock.json
                calibration_null_label_as_negative.json
                calibration_ordinal_tier_as_probability.json
                calibration_outcome_derived_temporal_slice.json
                calibration_partial_route_finalized.json
                calibration_point_only.json
                calibration_pooled_subgroup_hides_cell.json
                calibration_post_test_config_change.json
                calibration_probability_float_or_noncanonical.json
                calibration_probability_out_of_range.json
                calibration_probability_target_rebind.json
                calibration_production_promotion.json
                calibration_purge_embargo_shortened.json
                calibration_rank_score_as_probability.json
                calibration_rehashed_bin_or_subgroup_registry.json
                calibration_rehashed_cohort_or_split.json
                calibration_rehashed_fit.json
                calibration_rehashed_label_view.json
                calibration_rehashed_math_problem_and_decision.json
                calibration_rehashed_metrics.json
                calibration_rehashed_predictions.json
                calibration_rehashed_probability_contract.json
                calibration_rehashed_receipt.json
                calibration_sparse_bin_point_estimate.json
                calibration_sparse_group_disparity.json
                calibration_split_overlap_or_duplicate_route.json
                calibration_split_temporal_order.json
                calibration_stale_current_head.json
                calibration_subgroup_hidden.json
                calibration_subgroup_wrong_denominator.json
                calibration_synthetic_as_real_calibration.json
                calibration_synthetic_range_as_confidence.json
                calibration_temporal_slices_pooled.json
                calibration_test_adaptive_bin_edges.json
                calibration_test_label_selects_calibrator.json
                calibration_unknown_probability_to_zero.json
                calibration_validation_label_in_base_fit.json
                calibration_wrong_edge_membership.json
                contract_brand_location_collapse.json
                contract_decision_digest_mismatch.json
                contract_future_observation.json
                contract_protected_alias_omission.json
                contract_silent_schema_upgrade.json
                exact_ten_protected_fill.json
                exact_ten_wrong_cardinality.json
                frontier_cycle.json
                frontier_external_block_abuse.json
                frontier_self_attested_pass.json
                math_hardcoded_power.json
                math_scenario_as_measured.json
                math_undefined_estimand.json
                model_future_feature.json
                model_missing_baselines.json
                outcome_appointment_before_booking.json
                outcome_assertion_unit_mismatch.json
                outcome_booking_as_commission.json
                outcome_censored_negative.json
                outcome_clock_order.json
                outcome_common_asof_divergence.json
                outcome_competing_negative.json
                outcome_correction_cycle.json
                outcome_correction_target_missing.json
                outcome_duplicate_booking.json
                outcome_extra_ledger_field.json
                outcome_failed_competing_adjudication.json
                outcome_forged_stopper_evidence.json
                outcome_forged_supporting_evidence.json
                outcome_future_booking_before_assessment.json
                outcome_future_evidence.json
                outcome_immature_negative.json
                outcome_incomplete_watermark_negative.json
                outcome_missing_f9_conjunct.json
                outcome_missing_realtor_identity.json
                outcome_outside_window_positive.json
                outcome_partial_route_final.json
                outcome_post_window_rewrite.json
                outcome_post_window_stopper.json
                outcome_rehashed_correction.json
                outcome_rehashed_dedupe.json
                outcome_rehashed_dedupe_split_input.json
                outcome_rehashed_input_new_f9.json
                outcome_rehashed_label.json
                outcome_rehashed_policy_binding.json
                outcome_replay_receipt.json
                outcome_shifted_assignment_anchor.json
                outcome_stage1_contamination.json
                outcome_unknown_assertion_type.json
                outcome_unregistered_stopper_cause.json
                outcome_window_authority.json
                research_brand_as_location.json
                research_current_as_historical.json
                research_inference_as_fact.json
                research_metadata_as_access.json
                research_ontario_multi_address.json
                research_retrieved_as_authority.json
                research_toronto_sysid_conflict.json
                source_mutable_as_snapshot.json
                source_unspecified_licence.json
                vertical_duplicate_stop.json
                vertical_field_before_issuance.json
                vertical_immature_outcome_counted.json
                vertical_protected_stop.json
                vertical_replay_receipt_mismatch.json
                vertical_route_selection_mismatch.json
                vertical_stage2_rewrite.json
                _support.py
                collapse_duplicate_physical_locations.py
                fill_with_protected_alias.py
                greedy_individual_value.py
                issue_nine.py
                permutation_sensitive.py
                prefer_proximity_below_value_floor.py
                use_stage2_field_observation.py
                protected_alias_exact_ten.json
                ten_valid.json
                __init__.py
                framework.py
                __init__.py
                framework.py
                __init__.py
                thin_slice.py
                __init__.py
                reference_oracle.py
                __init__.py
                ledger.py
                __init__.py
                shadow_slice.py
                    capture_manifest.json
                    on_ogl_terms.html
                    on_select_package.json
                    on_select_schema.json
                    tor_coa_2001_schema.json
                    tor_coa_2016_schema.json
                    tor_coa_active_schema.json
                    tor_coa_closed_schema.json
                    tor_coa_package.json
                    tor_ogl_terms.html
                    capture_manifest.json
                    on_distinct_licence_limit0.json
                    on_licence_4716137_count.json
                    on_licence_4716137_distinct_address.json
                    on_max_address.json
                    on_max_address_post.json
                    on_summary.json
                    on_total_limit0.json
                    tor_2016_3209741.json
                    tor_closed_3209741.json
                    .codex/
                    AGENTS.md
                    artifacts/
                    CHECKSUMS.sha256
                    context/
                    control/
                    evals/
                    FINAL_AUDIT_REPORT.md
                    FINAL_CODEX_LAUNCH_PROMPT_v2.2.md
                    kernel/
                    LEVEL10_SWEEPER_REPORT.md
                    MANIFEST.json
                    README_START_HERE.md
                    RESEARCH_BASIS.md
                    RUNBOOK.md
                    schemas/
                    scripts/
                    skills/
                    standards/
                    CHECKSUMS.sha256
                    domain-v0.9/
                    implementation-v0.12/
                    index/
                    MANIFEST.json
                    source-proof-v0.10/
                    spatial-v0.11/
                        agents/
                        config.template.toml
                        codex_capabilities.json
                        context/
                        level10/
                        os_validation.json
                        prompt_audit.json
                        research_readiness_validation.json
                        selected_task.json
                        AGENT_DATA_PRIMITIVES.json
                        CORE_RESEARCH_QUESTIONS.json
                        EXPERTISE_MAP.json
                        PRODUCT_BRIEF.md
                        REFERENCE_ARCHITECTURE.md
                        VAULT_ROUTER.json
                        AUTHORIZED_FALLBACK_LADDER.md
                        CLAIM_PROOF_REGISTER.json
                        CONTEXT_POLICY.json
                        CURRENT_STATE.json
                        CURRENT_TASK.json
                        EVALUATOR_TOPOLOGY.md
                        EXECUTION_MODES.md
                        LEVEL10_DOMAIN_DEFINITIONS.json
                        MILESTONES.json
                        PRE_CODEX_LEVEL10_POLICY.md
                        RESEARCH_COMPLETION_PROTOCOL.md
                        ROLE_ACTIVATION_POLICY.json
                        SYMPHONY_WORKFLOW.md
                        TASK_GRAPH.json
                        TASK_SELECTION_POLICY.json
                        WORKFLOW.md
                        ADVERSARIAL_CASES.json
                        LEVEL10_BENCHMARKS.json
                        TRIAL_PROTOCOL.md
                        AUTHORITY.md
                        CAPABILITY_BOUNDARY.json
                        CAPABILITY_BOUNDARY.md
                        INVARIANTS.json
                        MATH_MODELING_CONSTITUTION.md
                        MISSION.md
                        PROOF_POLICY.md
                        STOP_POLICY.md
                        capability_manifest.schema.json
                        context_packet.schema.json
                        task_result.schema.json
                        compile_task_context.py
                        launch_headless_once.sh
                        probe_codex_capabilities.py
                        run_level10_campaign.py
                        run_level10_simulation.py
                        run_prompt_audit.py
                        select_next_task.py
                        validate_level10_release.py
                        validate_os.py
                        validate_research_readiness.py
                        verify_checksums.py
                        best-of-n/
                        context-compile/
                        decompose/
                        identity-provenance/
                        integrate-resume/
                        orient/
                        quant-economics/
                        research-evidence/
                        verify-sweep/
                        BENCHMARK_CROSSWALK.md
                        BENCHMARK_STANDARD_REGISTRY.json
                        contracts/
                        docs/
                        contracts/
                        docs/
                        interfaces/
                        proof/
                        VAULT_INDEX.json
                        VAULT_INDEX.md
                        contracts/
                        docs/
                        contracts/
                        docs/
                            builder.toml
                            cre_reviewer.toml
                            data_identity_reviewer.toml
                            quant_ml_reviewer.toml
                            research_mapper.toml
                            systems_security_reviewer.toml
                            verifier.toml
                            current_task_packet.json
                            current_task_packet.md
                            campaign.json
                            DOMAIN_SCORECARD.md
                            full_system_simulation.json
                            release_validation.json
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            SKILL.md
                            cold_start_experiment_design_v2.json
                            entity_relationship_ontology_v2.json
                            field_question_bank.json
                            historical_label_factory_v2.json
                            mechanism_signal_chain_registry.json
                            pilot_segment_decision.json
                            research_evidence_registry.json
                            source_intelligence_registry.json
                            phase-zero/
                            canonical_data_product_registry.json
                            codex_milestone_acceptance_plan.json
                            deployment_profile_contract_v2.json
                            implementation_architecture_contract.json
                            ml_lifecycle_contract_v2.json
                            workflow_state_machine_contract.json
                            phase-zero/
                            asyncapi.json
                            openapi.json
                            manifest.json
                            immutable_source_snapshot_contract.json
                            pilot_cross_source_join_contract.json
                            pilot_historical_sample_protocol.json
                            source_access_proof_registry.json
                            phase-zero/
                            backup_substitution_policy.json
                            daily_list_composition_policy.json
                            final_planning_readiness_matrix.json
                            representative_spatial_assignment_policy.json
                            spatial_experiment_interference_policy.json
                            spatial_proximity_policy.json
                            phase-zero/
                                COLD_START_AND_EXPERIMENT_POWER_V2.md
                                CRE_EVENT_TAXONOMY_V2.md
                                MARKET_SEGMENT_PRIORITIZATION.md
                                SIGNAL_PRIMITIVE_CATALOG_V2.md
                                CODEX_MILESTONE_ACCEPTANCE_PLAN_V0.12.md
                                IMPLEMENTATION_CONTRACT_AND_BUILD_SPEC_V0.12.md
                                PILOT_SOURCE_ACQUISITION_DOSSIER.md
                                SOURCE_INTELLIGENCE_ATLAS.md
                                MASTER_SYSTEM_BLUEPRINT_V0.11.md
                                SPATIAL_PROXIMITY_AND_DAILY_LIST_V2.md
```

## 4. Every Current Tracked File

| File | Lines | Bytes |
|---|---:|---:|
| `.gitignore` | 14 | 152 |
| `AGENTS.md` | 43 | 2,007 |
| `artifacts/architecture/ARCHITECTURE-001-start.json` | 54 | 2,646 |
| `artifacts/architecture/public_evaluator_contract.json` | 408 | 22,144 |
| `artifacts/baselines/BASELINE-001-start.json` | 34 | 2,217 |
| `artifacts/baselines/canonical_run.json` | 95,837 | 3,983,204 |
| `artifacts/baselines/capability_classification_reconciliation.json` | 17 | 1,469 |
| `artifacts/baselines/frozen_benchmark.json` | 12,636 | 636,497 |
| `artifacts/baselines/policy_registry.json` | 123 | 4,158 |
| `artifacts/baselines/public_evaluator_contract.json` | 203 | 18,651 |
| `artifacts/bootstrap/archive_verification.json` | 11 | 427 |
| `artifacts/bootstrap/capability_manifest.json` | 46 | 1,453 |
| `artifacts/bootstrap/contradiction_register.json` | 35 | 1,872 |
| `artifacts/bootstrap/expertise_coverage.json` | 21 | 2,035 |
| `artifacts/bootstrap/input_classification.json` | 59 | 2,745 |
| `artifacts/bootstrap/repository_inventory.json` | 37 | 1,332 |
| `artifacts/calibration/CALIBRATION-001-start.json` | 33 | 2,285 |
| `artifacts/calibration/canonical_run.json` | 5,594 | 206,586 |
| `artifacts/calibration/frozen_input.json` | 143 | 4,294 |
| `artifacts/calibration/public_evaluator_contract.json` | 169 | 19,523 |
| `artifacts/context/current_task_packet.json` | 159 | 6,403 |
| `artifacts/context/current_task_packet.md` | 9,149 | 434,559 |
| `artifacts/contracts/CONTRACT-001-start.json` | 61 | 2,354 |
| `artifacts/contracts/contract_spine.json` | 67 | 2,592 |
| `artifacts/contracts/public_evaluator_contract.json` | 60 | 3,320 |
| `artifacts/evaluations/autonomous_frontier_meta.json` | 40 | 2,392 |
| `artifacts/evaluations/autonomous_frontier_report.json` | 1,414 | 62,531 |
| `artifacts/evaluations/baseline_framework.json` | 742 | 24,814 |
| `artifacts/evaluations/baseline_model_synthetic.json` | 742 | 24,830 |
| `artifacts/evaluations/calibration_framework.json` | 702 | 24,706 |
| `artifacts/evaluations/calibration_synthetic.json` | 702 | 24,722 |
| `artifacts/evaluations/contract_spine.json` | 45 | 3,006 |
| `artifacts/evaluations/known_bad_direct_result.json` | 7 | 155 |
| `artifacts/evaluations/known_bad_public_result.json` | 40 | 1,196 |
| `artifacts/evaluations/math_contracts.json` | 176 | 6,357 |
| `artifacts/evaluations/outcomes_synthetic.json` | 345 | 13,517 |
| `artifacts/evaluations/public_evaluator_manifest.json` | 20 | 1,545 |
| `artifacts/evaluations/vertical_slice.json` | 96 | 3,835 |
| `artifacts/math/estimand_registry.json` | 597 | 19,934 |
| `artifacts/math/formal_decisions.json` | 30 | 4,617 |
| `artifacts/math/human_authority_input_template.json` | 54 | 1,772 |
| `artifacts/math/MATH-001-start.json` | 38 | 3,042 |
| `artifacts/math/public_evaluator_contract.json` | 45 | 3,801 |
| `artifacts/models/model_registry.json` | 128 | 4,559 |
| `artifacts/outcomes/canonical_run.json` | 3,389 | 149,270 |
| `artifacts/outcomes/capability_classification_reconciliation.json` | 46 | 2,760 |
| `artifacts/outcomes/itt_inclusion_cases.json` | 29 | 943 |
| `artifacts/outcomes/OUTCOMES-001-start.json` | 44 | 2,973 |
| `artifacts/outcomes/public_evaluator_contract.json` | 150 | 15,125 |
| `artifacts/outcomes/scenario_matrix.json` | 34 | 2,365 |
| `artifacts/outcomes/synthetic_input_ledger.json` | 497 | 22,969 |
| `artifacts/outcomes/synthetic_window_policy.json` | 30 | 1,724 |
| `artifacts/research/bundle_manifest.json` | 167 | 6,817 |
| `artifacts/research/canonical_field_map.json` | 1,162 | 44,690 |
| `artifacts/research/claim_evidence_graph.json` | 464 | 16,279 |
| `artifacts/research/counterevidence_register.json` | 111 | 3,879 |
| `artifacts/research/raw/independent/capture_manifest.json` | 107 | 5,994 |
| `artifacts/research/raw/independent/on_ogl_terms.html` | 1,034 | 95,339 |
| `artifacts/research/raw/independent/on_select_package.json` | 1 | 11,530 |
| `artifacts/research/raw/independent/on_select_schema.json` | 1 | 3,410 |
| `artifacts/research/raw/independent/tor_coa_2001_schema.json` | 1 | 1,810 |
| `artifacts/research/raw/independent/tor_coa_2016_schema.json` | 1 | 1,810 |
| `artifacts/research/raw/independent/tor_coa_active_schema.json` | 1 | 2,476 |
| `artifacts/research/raw/independent/tor_coa_closed_schema.json` | 1 | 3,160 |
| `artifacts/research/raw/independent/tor_coa_package.json` | 1 | 75,676 |
| `artifacts/research/raw/independent/tor_ogl_terms.html` | 369 | 34,435 |
| `artifacts/research/raw/manifest.json` | 114 | 6,640 |
| `artifacts/research/raw/on_ogl_terms.html` | 1,034 | 95,339 |
| `artifacts/research/raw/on_select_package.json` | 1 | 11,006 |
| `artifacts/research/raw/on_select_schema.json` | 1 | 3,185 |
| `artifacts/research/raw/row_witness/capture_manifest.json` | 260 | 13,122 |
| `artifacts/research/raw/row_witness/on_distinct_licence_limit0.json` | 1 | 883 |
| `artifacts/research/raw/row_witness/on_licence_4716137_count.json` | 1 | 3,540 |
| `artifacts/research/raw/row_witness/on_licence_4716137_distinct_address.json` | 1 | 954 |
| `artifacts/research/raw/row_witness/on_max_address.json` | 63 | 1,724 |
| `artifacts/research/raw/row_witness/on_max_address_post.json` | 63 | 1,724 |
| `artifacts/research/raw/row_witness/on_summary.json` | 63 | 1,724 |
| `artifacts/research/raw/row_witness/on_total_limit0.json` | 1 | 3,410 |
| `artifacts/research/raw/row_witness/tor_2016_3209741.json` | 1 | 2,919 |
| `artifacts/research/raw/row_witness/tor_closed_3209741.json` | 1 | 4,537 |
| `artifacts/research/raw/tor_coa_2001_schema.json` | 1 | 1,665 |
| `artifacts/research/raw/tor_coa_2016_schema.json` | 1 | 1,665 |
| `artifacts/research/raw/tor_coa_active_schema.json` | 1 | 2,244 |
| `artifacts/research/raw/tor_coa_closed_schema.json` | 1 | 2,858 |
| `artifacts/research/raw/tor_coa_package.json` | 1 | 71,736 |
| `artifacts/research/raw/tor_ogl_terms.html` | 369 | 34,435 |
| `artifacts/research/RESEARCH-001-adversarial-sweep.json` | 12 | 1,491 |
| `artifacts/research/RESEARCH-001-start.json` | 25 | 1,605 |
| `artifacts/research/research_completion_report.json` | 36 | 1,709 |
| `artifacts/research/source_feasibility_registry.json` | 223 | 8,248 |
| `artifacts/research/source_feasibility_registry.v0.json` | 258 | 16,386 |
| `artifacts/research/source_reproduction_report.json` | 527 | 19,341 |
| `artifacts/research/toronto_business_licences_metadata_probe.v0.json` | 53 | 4,586 |
| `artifacts/task-results/BASELINE-001.json` | 163 | 16,700 |
| `artifacts/task-results/BOOTSTRAP-001.json` | 141 | 14,169 |
| `artifacts/task-results/CALIBRATION-001.json` | 163 | 17,389 |
| `artifacts/task-results/CONTRACT-001.json` | 118 | 11,644 |
| `artifacts/task-results/FRONTIER-001.json` | 174 | 12,097 |
| `artifacts/task-results/MATH-001.json` | 131 | 11,606 |
| `artifacts/task-results/OUTCOMES-001.json` | 306 | 15,737 |
| `artifacts/task-results/RESEARCH-001.json` | 138 | 12,457 |
| `artifacts/task-results/RESEARCH-001.partial.json` | 177 | 8,862 |
| `artifacts/task-results/VERTICAL-001.json` | 125 | 11,224 |
| `artifacts/vertical-slice/run_manifest.json` | 284 | 11,219 |
| `artifacts/vertical/public_evaluator_contract.json` | 40 | 2,889 |
| `artifacts/vertical/VERTICAL-001-start.json` | 62 | 2,568 |
| `bootstrap/BOOTSTRAP-001.partial.json` | 175 | 7,105 |
| `bootstrap/GATE-OS-ARTIFACT-001.json` | 112 | 5,001 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/builder.toml` | 10 | 523 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/cre_reviewer.toml` | 9 | 465 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/data_identity_reviewer.toml` | 9 | 467 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/quant_ml_reviewer.toml` | 10 | 511 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/research_mapper.toml` | 9 | 440 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/systems_security_reviewer.toml` | 10 | 503 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/agents/verifier.toml` | 10 | 534 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/.codex/config.template.toml` | 11 | 310 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/AGENTS.md` | 59 | 2,224 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/codex_capabilities.json` | 32 | 667 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/context/current_task_packet.json` | 19 | 571 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/context/current_task_packet.md` | 550 | 19,996 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/level10/campaign.json` | 86 | 4,674 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/level10/DOMAIN_SCORECARD.md` | 32 | 2,166 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/level10/full_system_simulation.json` | 935 | 24,803 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/level10/release_validation.json` | 8 | 142 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/os_validation.json` | 10 | 208 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/prompt_audit.json` | 20 | 439 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/research_readiness_validation.json` | 8 | 122 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/selected_task.json` | 5 | 135 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/CHECKSUMS.sha256` | 75 | 7,170 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/AGENT_DATA_PRIMITIVES.json` | 143 | 3,058 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/CORE_RESEARCH_QUESTIONS.json` | 89 | 3,055 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/EXPERTISE_MAP.json` | 66 | 2,447 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/PRODUCT_BRIEF.md` | 28 | 1,166 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/REFERENCE_ARCHITECTURE.md` | 22 | 892 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/context/VAULT_ROUTER.json` | 46 | 2,146 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/AUTHORIZED_FALLBACK_LADDER.md` | 47 | 1,641 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/CLAIM_PROOF_REGISTER.json` | 54 | 2,123 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/CONTEXT_POLICY.json` | 32 | 1,044 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/CURRENT_STATE.json` | 23 | 1,718 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/CURRENT_TASK.json` | 16 | 1,285 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/EVALUATOR_TOPOLOGY.md` | 25 | 910 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/EXECUTION_MODES.md` | 51 | 1,875 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/LEVEL10_DOMAIN_DEFINITIONS.json` | 462 | 17,444 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/MILESTONES.json` | 124 | 2,819 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/PRE_CODEX_LEVEL10_POLICY.md` | 23 | 851 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/RESEARCH_COMPLETION_PROTOCOL.md` | 121 | 3,330 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/ROLE_ACTIVATION_POLICY.json` | 157 | 2,922 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/SYMPHONY_WORKFLOW.md` | 35 | 1,215 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/TASK_GRAPH.json` | 155 | 7,613 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/TASK_SELECTION_POLICY.json` | 38 | 1,141 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/WORKFLOW.md` | 109 | 2,726 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/evals/ADVERSARIAL_CASES.json` | 149 | 4,394 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/evals/LEVEL10_BENCHMARKS.json` | 36 | 1,205 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/evals/TRIAL_PROTOCOL.md` | 37 | 1,112 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/FINAL_AUDIT_REPORT.md` | 72 | 2,649 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/FINAL_CODEX_LAUNCH_PROMPT_v2.2.md` | 110 | 5,107 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/AUTHORITY.md` | 39 | 1,348 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/CAPABILITY_BOUNDARY.json` | 82 | 4,349 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/CAPABILITY_BOUNDARY.md` | 66 | 2,506 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/INVARIANTS.json` | 73 | 2,932 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/MATH_MODELING_CONSTITUTION.md` | 182 | 4,509 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/MISSION.md` | 34 | 1,204 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/PROOF_POLICY.md` | 42 | 1,190 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/STOP_POLICY.md` | 22 | 809 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/LEVEL10_SWEEPER_REPORT.md` | 24 | 975 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/MANIFEST.json` | 432 | 14,081 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/README_START_HERE.md` | 50 | 2,059 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/RESEARCH_BASIS.md` | 38 | 1,932 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/RUNBOOK.md` | 56 | 1,574 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/schemas/capability_manifest.schema.json` | 34 | 545 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/schemas/context_packet.schema.json` | 35 | 630 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/schemas/task_result.schema.json` | 186 | 3,342 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/compile_task_context.py` | 62 | 2,100 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/launch_headless_once.sh` | 38 | 1,045 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/probe_codex_capabilities.py` | 72 | 2,516 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/run_level10_campaign.py` | 28 | 2,349 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/run_level10_simulation.py` | 328 | 21,248 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/run_prompt_audit.py` | 36 | 1,743 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/select_next_task.py` | 61 | 1,946 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/validate_level10_release.py` | 22 | 1,553 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/validate_os.py` | 125 | 4,075 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/validate_research_readiness.py` | 65 | 2,364 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/verify_checksums.py` | 18 | 577 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/best-of-n/SKILL.md` | 10 | 430 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/context-compile/SKILL.md` | 10 | 450 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/decompose/SKILL.md` | 10 | 451 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/identity-provenance/SKILL.md` | 10 | 457 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/integrate-resume/SKILL.md` | 10 | 434 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/orient/SKILL.md` | 10 | 417 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/quant-economics/SKILL.md` | 10 | 457 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/research-evidence/SKILL.md` | 10 | 437 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/skills/verify-sweep/SKILL.md` | 10 | 435 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/standards/BENCHMARK_CROSSWALK.md` | 31 | 1,304 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/standards/BENCHMARK_STANDARD_REGISTRY.json` | 257 | 8,324 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/CHECKSUMS.sha256` | 40 | 4,977 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/cold_start_experiment_design_v2.json` | 70 | 2,507 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/entity_relationship_ontology_v2.json` | 341 | 9,430 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/field_question_bank.json` | 617 | 20,950 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/historical_label_factory_v2.json` | 68 | 1,992 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/mechanism_signal_chain_registry.json` | 1,024 | 52,150 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/pilot_segment_decision.json` | 50 | 1,903 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/research_evidence_registry.json` | 326 | 16,187 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/source_intelligence_registry.json` | 1,406 | 53,654 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/docs/phase-zero/COLD_START_AND_EXPERIMENT_POWER_V2.md` | 48 | 1,742 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/docs/phase-zero/CRE_EVENT_TAXONOMY_V2.md` | 77 | 14,858 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/docs/phase-zero/MARKET_SEGMENT_PRIORITIZATION.md` | 38 | 1,342 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/docs/phase-zero/SIGNAL_PRIMITIVE_CATALOG_V2.md` | 64 | 1,843 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/canonical_data_product_registry.json` | 646 | 19,238 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/codex_milestone_acceptance_plan.json` | 418 | 15,600 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/deployment_profile_contract_v2.json` | 87 | 2,674 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/implementation_architecture_contract.json` | 385 | 11,139 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/ml_lifecycle_contract_v2.json` | 70 | 2,300 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/workflow_state_machine_contract.json` | 239 | 5,192 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/docs/phase-zero/CODEX_MILESTONE_ACCEPTANCE_PLAN_V0.12.md` | 48 | 2,238 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/docs/phase-zero/IMPLEMENTATION_CONTRACT_AND_BUILD_SPEC_V0.12.md` | 282 | 7,678 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/interfaces/asyncapi.json` | 385 | 9,253 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/interfaces/openapi.json` | 891 | 21,809 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/proof/manifest.json` | 478 | 16,787 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/index/VAULT_INDEX.json` | 229 | 8,813 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/index/VAULT_INDEX.md` | 24 | 753 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/MANIFEST.json` | 202 | 7,668 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/contracts/immutable_source_snapshot_contract.json` | 61 | 2,421 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/contracts/pilot_cross_source_join_contract.json` | 142 | 3,712 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/contracts/pilot_historical_sample_protocol.json` | 61 | 2,431 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/contracts/source_access_proof_registry.json` | 648 | 23,945 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/docs/phase-zero/PILOT_SOURCE_ACQUISITION_DOSSIER.md` | 81 | 3,132 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/docs/phase-zero/SOURCE_INTELLIGENCE_ATLAS.md` | 112 | 17,396 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/contracts/backup_substitution_policy.json` | 34 | 1,068 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/contracts/daily_list_composition_policy.json` | 69 | 2,477 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/contracts/final_planning_readiness_matrix.json` | 127 | 5,190 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/contracts/representative_spatial_assignment_policy.json` | 46 | 1,563 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/contracts/spatial_experiment_interference_policy.json` | 40 | 1,563 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/contracts/spatial_proximity_policy.json` | 79 | 2,860 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/docs/phase-zero/MASTER_SYSTEM_BLUEPRINT_V0.11.md` | 425 | 10,888 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/docs/phase-zero/SPATIAL_PROXIMITY_AND_DAILY_LIST_V2.md` | 189 | 5,864 |
| `contracts/autonomous_frontier_contract.schema.json` | 127 | 6,905 |
| `contracts/baseline_evaluation.schema.json` | 78 | 6,685 |
| `contracts/baseline_policy.schema.json` | 38 | 2,602 |
| `contracts/calibration_evaluation.schema.json` | 56 | 24,816 |
| `contracts/calibration_input.schema.json` | 23 | 4,426 |
| `contracts/calibration_uncertainty.schema.json` | 6 | 310 |
| `contracts/estimand_registry.schema.json` | 140 | 10,041 |
| `contracts/f9_outcome.schema.json` | 150 | 13,010 |
| `contracts/f9_outcome_input_ledger.schema.json` | 133 | 9,382 |
| `contracts/f9_window_policy.schema.json` | 45 | 3,153 |
| `contracts/math_authority_input.schema.json` | 27 | 1,578 |
| `contracts/math_decision_policy.schema.json` | 109 | 6,514 |
| `contracts/math_route_decision.schema.json` | 48 | 3,240 |
| `contracts/research/canonical_field_map.schema.json` | 24 | 3,009 |
| `contracts/research/claim_evidence_graph.schema.json` | 68 | 3,719 |
| `contracts/research/counterevidence_register.schema.json` | 13 | 1,325 |
| `contracts/research/source_feasibility_registry.schema.json` | 55 | 4,767 |
| `contracts/research/source_reproduction_report.schema.json` | 109 | 5,076 |
| `contracts/route_decision.schema.json` | 31 | 859 |
| `contracts/synthetic_f9_outcome.schema.json` | 89 | 5,020 |
| `contracts/synthetic_field_event.schema.json` | 67 | 3,441 |
| `contracts/synthetic_route_day.schema.json` | 65 | 3,641 |
| `contracts/thin_slice_candidate.schema.json` | 155 | 9,328 |
| `contracts/thin_slice_observation.schema.json` | 114 | 5,499 |
| `control/AUTONOMOUS_FRONTIER_CONTRACT.json` | 2,764 | 120,055 |
| `control/CURRENT_STATE.json` | 166 | 8,121 |
| `control/CURRENT_TASK.json` | 8 | 409 |
| `control/DECISIONS.md` | 36 | 1,647 |
| `control/EVALUATOR_DECISION.json` | 40 | 1,634 |
| `control/GATES.json` | 262 | 13,874 |
| `control/TASK_GRAPH.json` | 323 | 16,846 |
| `docs/contracts/THIN_SLICE_CONTRACT.md` | 35 | 3,182 |
| `docs/research/RESEARCH-001-source-feasibility.md` | 72 | 5,745 |
| `evals/known_bad/always_abstain.py` | 10 | 323 |
| `evals/known_bad/exact_name_only_clearance.py` | 12 | 430 |
| `evals/known_bad/frontier/baseline_all_row_score_projection.json` | 8 | 328 |
| `evals/known_bad/frontier/baseline_candidate_set_asymmetry.json` | 8 | 335 |
| `evals/known_bad/frontier/baseline_complexity_tie_promoted.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_coordinated_feature_rehash.json` | 8 | 331 |
| `evals/known_bad/frontier/baseline_coordinated_registry_rehash.json` | 8 | 334 |
| `evals/known_bad/frontier/baseline_duplicate_location.json` | 8 | 319 |
| `evals/known_bad/frontier/baseline_duplicate_route_seed.json` | 8 | 323 |
| `evals/known_bad/frontier/baseline_feature_clock_reordered.json` | 8 | 325 |
| `evals/known_bad/frontier/baseline_feature_view_asymmetry.json` | 8 | 331 |
| `evals/known_bad/frontier/baseline_forged_label_view.json` | 8 | 326 |
| `evals/known_bad/frontier/baseline_forged_math_problem_hash.json` | 8 | 335 |
| `evals/known_bad/frontier/baseline_future_feature.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_future_label_asof.json` | 8 | 323 |
| `evals/known_bad/frontier/baseline_future_recency_value.json` | 8 | 328 |
| `evals/known_bad/frontier/baseline_immature_as_negative.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_issue_nine.json` | 8 | 309 |
| `evals/known_bad/frontier/baseline_label_denominator_asymmetry.json` | 8 | 336 |
| `evals/known_bad/frontier/baseline_math_input_contamination.json` | 8 | 331 |
| `evals/known_bad/frontier/baseline_metric_wrong_denominator.json` | 8 | 333 |
| `evals/known_bad/frontier/baseline_missing_required_policy.json` | 8 | 329 |
| `evals/known_bad/frontier/baseline_nondeterministic_random.json` | 8 | 329 |
| `evals/known_bad/frontier/baseline_outcome_feature.json` | 8 | 321 |
| `evals/known_bad/frontier/baseline_outcome_source_family.json` | 8 | 327 |
| `evals/known_bad/frontier/baseline_partial_labels_finalized.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_policy_direct_selection.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_production_promotion.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_protected_selected.json` | 8 | 317 |
| `evals/known_bad/frontier/baseline_receipt_only.json` | 8 | 318 |
| `evals/known_bad/frontier/baseline_rehashed_future_feature.json` | 8 | 338 |
| `evals/known_bad/frontier/baseline_rehashed_metrics.json` | 8 | 321 |
| `evals/known_bad/frontier/baseline_rehashed_null_label.json` | 8 | 323 |
| `evals/known_bad/frontier/baseline_rehashed_policy_score.json` | 8 | 326 |
| `evals/known_bad/frontier/baseline_rehashed_random.json` | 8 | 320 |
| `evals/known_bad/frontier/baseline_rehashed_receipt.json` | 8 | 322 |
| `evals/known_bad/frontier/baseline_rehashed_split.json` | 8 | 318 |
| `evals/known_bad/frontier/baseline_rehashed_universe.json` | 8 | 324 |
| `evals/known_bad/frontier/baseline_replacement_with_more_abstention.json` | 8 | 331 |
| `evals/known_bad/frontier/baseline_seed_cherrypick.json` | 8 | 317 |
| `evals/known_bad/frontier/baseline_split_overlap.json` | 8 | 311 |
| `evals/known_bad/frontier/baseline_split_temporal_order.json` | 8 | 323 |
| `evals/known_bad/frontier/baseline_stat_fraction_rounded.json` | 8 | 324 |
| `evals/known_bad/frontier/baseline_stat_null_label.json` | 8 | 321 |
| `evals/known_bad/frontier/baseline_synthetic_as_predictive.json` | 8 | 319 |
| `evals/known_bad/frontier/baseline_test_label_in_fit.json` | 8 | 319 |
| `evals/known_bad/frontier/baseline_test_reuse.json` | 8 | 303 |
| `evals/known_bad/frontier/baseline_unseeded_random.json` | 8 | 317 |
| `evals/known_bad/frontier/baseline_winner_below_margin.json` | 8 | 318 |
| `evals/known_bad/frontier/calibration_abstain_as_negative_or_itt_excluded.json` | 24 | 631 |
| `evals/known_bad/frontier/calibration_abstain_dropped.json` | 22 | 579 |
| `evals/known_bad/frontier/calibration_bin_gap_or_overlap.json` | 25 | 573 |
| `evals/known_bad/frontier/calibration_calibrated_value_not_projected.json` | 25 | 650 |
| `evals/known_bad/frontier/calibration_calibrator_fit_count_change.json` | 23 | 576 |
| `evals/known_bad/frontier/calibration_common_asof_divergence.json` | 22 | 598 |
| `evals/known_bad/frontier/calibration_common_nonscore_math_change.json` | 25 | 639 |
| `evals/known_bad/frontier/calibration_drop_unknown_candidate.json` | 23 | 601 |
| `evals/known_bad/frontier/calibration_empty_bin_point_estimate.json` | 26 | 650 |
| `evals/known_bad/frontier/calibration_forged_label_lineage.json` | 22 | 632 |
| `evals/known_bad/frontier/calibration_future_feature_in_probability.json` | 21 | 595 |
| `evals/known_bad/frontier/calibration_future_label_in_fit.json` | 21 | 558 |
| `evals/known_bad/frontier/calibration_issue_nine_or_direct_selection.json` | 23 | 591 |
| `evals/known_bad/frontier/calibration_label_visible_before_prediction_freeze.json` | 22 | 617 |
| `evals/known_bad/frontier/calibration_micro_reported_as_macro.json` | 25 | 647 |
| `evals/known_bad/frontier/calibration_missing_probability_as_zero.json` | 24 | 638 |
| `evals/known_bad/frontier/calibration_missing_subgroup_as_reference.json` | 23 | 632 |
| `evals/known_bad/frontier/calibration_nonmonotonic_calibration_clock.json` | 22 | 614 |
| `evals/known_bad/frontier/calibration_null_label_as_negative.json` | 22 | 568 |
| `evals/known_bad/frontier/calibration_ordinal_tier_as_probability.json` | 21 | 599 |
| `evals/known_bad/frontier/calibration_outcome_derived_temporal_slice.json` | 22 | 612 |
| `evals/known_bad/frontier/calibration_partial_route_finalized.json` | 25 | 651 |
| `evals/known_bad/frontier/calibration_point_only.json` | 7 | 287 |
| `evals/known_bad/frontier/calibration_pooled_subgroup_hides_cell.json` | 22 | 615 |
| `evals/known_bad/frontier/calibration_post_test_config_change.json` | 21 | 565 |
| `evals/known_bad/frontier/calibration_probability_float_or_noncanonical.json` | 25 | 659 |
| `evals/known_bad/frontier/calibration_probability_out_of_range.json` | 25 | 643 |
| `evals/known_bad/frontier/calibration_probability_target_rebind.json` | 21 | 578 |
| `evals/known_bad/frontier/calibration_production_promotion.json` | 21 | 555 |
| `evals/known_bad/frontier/calibration_purge_embargo_shortened.json` | 21 | 569 |
| `evals/known_bad/frontier/calibration_rank_score_as_probability.json` | 24 | 679 |
| `evals/known_bad/frontier/calibration_rehashed_bin_or_subgroup_registry.json` | 26 | 640 |
| `evals/known_bad/frontier/calibration_rehashed_cohort_or_split.json` | 21 | 631 |
| `evals/known_bad/frontier/calibration_rehashed_fit.json` | 50 | 1,286 |
| `evals/known_bad/frontier/calibration_rehashed_label_view.json` | 42 | 1,062 |
| `evals/known_bad/frontier/calibration_rehashed_math_problem_and_decision.json` | 134 | 4,250 |
| `evals/known_bad/frontier/calibration_rehashed_metrics.json` | 43 | 1,142 |
| `evals/known_bad/frontier/calibration_rehashed_predictions.json` | 53 | 1,359 |
| `evals/known_bad/frontier/calibration_rehashed_probability_contract.json` | 21 | 646 |
| `evals/known_bad/frontier/calibration_rehashed_receipt.json` | 31 | 900 |
| `evals/known_bad/frontier/calibration_sparse_bin_point_estimate.json` | 28 | 703 |
| `evals/known_bad/frontier/calibration_sparse_group_disparity.json` | 28 | 721 |
| `evals/known_bad/frontier/calibration_split_overlap_or_duplicate_route.json` | 22 | 596 |
| `evals/known_bad/frontier/calibration_split_temporal_order.json` | 22 | 573 |
| `evals/known_bad/frontier/calibration_stale_current_head.json` | 22 | 569 |
| `evals/known_bad/frontier/calibration_subgroup_hidden.json` | 7 | 297 |
| `evals/known_bad/frontier/calibration_subgroup_wrong_denominator.json` | 24 | 628 |
| `evals/known_bad/frontier/calibration_synthetic_as_real_calibration.json` | 21 | 554 |
| `evals/known_bad/frontier/calibration_synthetic_range_as_confidence.json` | 24 | 599 |
| `evals/known_bad/frontier/calibration_temporal_slices_pooled.json` | 23 | 596 |
| `evals/known_bad/frontier/calibration_test_adaptive_bin_edges.json` | 21 | 549 |
| `evals/known_bad/frontier/calibration_test_label_selects_calibrator.json` | 22 | 567 |
| `evals/known_bad/frontier/calibration_unknown_probability_to_zero.json` | 25 | 644 |
| `evals/known_bad/frontier/calibration_validation_label_in_base_fit.json` | 22 | 576 |
| `evals/known_bad/frontier/calibration_wrong_edge_membership.json` | 22 | 570 |
| `evals/known_bad/frontier/contract_brand_location_collapse.json` | 5 | 172 |
| `evals/known_bad/frontier/contract_decision_digest_mismatch.json` | 5 | 160 |
| `evals/known_bad/frontier/contract_future_observation.json` | 5 | 158 |
| `evals/known_bad/frontier/contract_protected_alias_omission.json` | 5 | 158 |
| `evals/known_bad/frontier/contract_silent_schema_upgrade.json` | 5 | 197 |
| `evals/known_bad/frontier/exact_ten_protected_fill.json` | 7 | 246 |
| `evals/known_bad/frontier/exact_ten_wrong_cardinality.json` | 7 | 208 |
| `evals/known_bad/frontier/frontier_cycle.json` | 7 | 226 |
| `evals/known_bad/frontier/frontier_external_block_abuse.json` | 6 | 244 |
| `evals/known_bad/frontier/frontier_self_attested_pass.json` | 6 | 162 |
| `evals/known_bad/frontier/math_hardcoded_power.json` | 8 | 238 |
| `evals/known_bad/frontier/math_scenario_as_measured.json` | 8 | 269 |
| `evals/known_bad/frontier/math_undefined_estimand.json` | 8 | 311 |
| `evals/known_bad/frontier/model_future_feature.json` | 7 | 274 |
| `evals/known_bad/frontier/model_missing_baselines.json` | 7 | 280 |
| `evals/known_bad/frontier/outcome_appointment_before_booking.json` | 5 | 156 |
| `evals/known_bad/frontier/outcome_assertion_unit_mismatch.json` | 5 | 147 |
| `evals/known_bad/frontier/outcome_booking_as_commission.json` | 5 | 146 |
| `evals/known_bad/frontier/outcome_censored_negative.json` | 5 | 142 |
| `evals/known_bad/frontier/outcome_clock_order.json` | 5 | 138 |
| `evals/known_bad/frontier/outcome_common_asof_divergence.json` | 5 | 146 |
| `evals/known_bad/frontier/outcome_competing_negative.json` | 5 | 157 |
| `evals/known_bad/frontier/outcome_correction_cycle.json` | 5 | 145 |
| `evals/known_bad/frontier/outcome_correction_target_missing.json` | 5 | 157 |
| `evals/known_bad/frontier/outcome_duplicate_booking.json` | 5 | 162 |
| `evals/known_bad/frontier/outcome_extra_ledger_field.json` | 5 | 134 |
| `evals/known_bad/frontier/outcome_failed_competing_adjudication.json` | 5 | 156 |
| `evals/known_bad/frontier/outcome_forged_stopper_evidence.json` | 5 | 148 |
| `evals/known_bad/frontier/outcome_forged_supporting_evidence.json` | 5 | 149 |
| `evals/known_bad/frontier/outcome_future_booking_before_assessment.json` | 5 | 156 |
| `evals/known_bad/frontier/outcome_future_evidence.json` | 5 | 151 |
| `evals/known_bad/frontier/outcome_immature_negative.json` | 5 | 142 |
| `evals/known_bad/frontier/outcome_incomplete_watermark_negative.json` | 5 | 166 |
| `evals/known_bad/frontier/outcome_missing_f9_conjunct.json` | 5 | 154 |
| `evals/known_bad/frontier/outcome_missing_realtor_identity.json` | 5 | 146 |
| `evals/known_bad/frontier/outcome_outside_window_positive.json` | 5 | 142 |
| `evals/known_bad/frontier/outcome_partial_route_final.json` | 5 | 158 |
| `evals/known_bad/frontier/outcome_post_window_rewrite.json` | 5 | 155 |
| `evals/known_bad/frontier/outcome_post_window_stopper.json` | 5 | 139 |
| `evals/known_bad/frontier/outcome_rehashed_correction.json` | 5 | 156 |
| `evals/known_bad/frontier/outcome_rehashed_dedupe.json` | 5 | 157 |
| `evals/known_bad/frontier/outcome_rehashed_dedupe_split_input.json` | 5 | 154 |
| `evals/known_bad/frontier/outcome_rehashed_input_new_f9.json` | 5 | 142 |
| `evals/known_bad/frontier/outcome_rehashed_label.json` | 5 | 159 |
| `evals/known_bad/frontier/outcome_rehashed_policy_binding.json` | 5 | 145 |
| `evals/known_bad/frontier/outcome_replay_receipt.json` | 5 | 148 |
| `evals/known_bad/frontier/outcome_shifted_assignment_anchor.json` | 5 | 150 |
| `evals/known_bad/frontier/outcome_stage1_contamination.json` | 5 | 141 |
| `evals/known_bad/frontier/outcome_unknown_assertion_type.json` | 5 | 142 |
| `evals/known_bad/frontier/outcome_unregistered_stopper_cause.json` | 5 | 150 |
| `evals/known_bad/frontier/outcome_window_authority.json` | 5 | 151 |
| `evals/known_bad/frontier/research_brand_as_location.json` | 8 | 449 |
| `evals/known_bad/frontier/research_current_as_historical.json` | 8 | 475 |
| `evals/known_bad/frontier/research_inference_as_fact.json` | 8 | 391 |
| `evals/known_bad/frontier/research_metadata_as_access.json` | 8 | 462 |
| `evals/known_bad/frontier/research_ontario_multi_address.json` | 8 | 563 |
| `evals/known_bad/frontier/research_retrieved_as_authority.json` | 8 | 452 |
| `evals/known_bad/frontier/research_toronto_sysid_conflict.json` | 8 | 669 |
| `evals/known_bad/frontier/source_mutable_as_snapshot.json` | 8 | 474 |
| `evals/known_bad/frontier/source_unspecified_licence.json` | 8 | 422 |
| `evals/known_bad/frontier/vertical_duplicate_stop.json` | 5 | 147 |
| `evals/known_bad/frontier/vertical_field_before_issuance.json` | 5 | 157 |
| `evals/known_bad/frontier/vertical_immature_outcome_counted.json` | 5 | 157 |
| `evals/known_bad/frontier/vertical_protected_stop.json` | 5 | 143 |
| `evals/known_bad/frontier/vertical_replay_receipt_mismatch.json` | 5 | 157 |
| `evals/known_bad/frontier/vertical_route_selection_mismatch.json` | 5 | 160 |
| `evals/known_bad/frontier/vertical_stage2_rewrite.json` | 5 | 130 |
| `evals/known_bad/math/_support.py` | 15 | 1,253 |
| `evals/known_bad/math/collapse_duplicate_physical_locations.py` | 5 | 125 |
| `evals/known_bad/math/fill_with_protected_alias.py` | 6 | 198 |
| `evals/known_bad/math/greedy_individual_value.py` | 14 | 362 |
| `evals/known_bad/math/issue_nine.py` | 5 | 124 |
| `evals/known_bad/math/permutation_sensitive.py` | 19 | 494 |
| `evals/known_bad/math/prefer_proximity_below_value_floor.py` | 6 | 213 |
| `evals/known_bad/math/use_stage2_field_observation.py` | 6 | 198 |
| `evals/public/baseline_framework_evaluator.py` | 689 | 50,759 |
| `evals/public/calibration_framework_evaluator.py` | 852 | 71,865 |
| `evals/public/contract_spine_evaluator.py` | 361 | 21,367 |
| `evals/public/fixtures/protected_alias_exact_ten.json` | 16 | 832 |
| `evals/public/fixtures/ten_valid.json` | 16 | 796 |
| `evals/public/math_oracle_evaluator.py` | 143 | 8,717 |
| `evals/public/outcomes_labels_evaluator.py` | 664 | 36,250 |
| `evals/public/route_decision_evaluator.py` | 86 | 3,130 |
| `evals/public/test_autonomous_frontier.py` | 541 | 23,461 |
| `evals/public/test_baseline_framework.py` | 204 | 11,914 |
| `evals/public/test_calibration_framework.py` | 254 | 15,769 |
| `evals/public/test_contract_spine.py` | 138 | 7,333 |
| `evals/public/test_math_contracts.py` | 281 | 18,172 |
| `evals/public/test_outcomes_labels.py` | 183 | 11,212 |
| `evals/public/test_research_completion.py` | 124 | 6,103 |
| `evals/public/test_route_decision_evaluator.py` | 51 | 1,894 |
| `evals/public/test_vertical_slice.py` | 188 | 10,516 |
| `evals/public/vertical_slice_evaluator.py` | 445 | 22,264 |
| `evals/reference/fail_closed_reference.py` | 19 | 619 |
| `pyproject.toml` | 14 | 277 |
| `README.md` | 42 | 1,659 |
| `scripts/build_math_contracts.py` | 106 | 12,180 |
| `scripts/build_research_contract.py` | 194 | 29,148 |
| `scripts/capture_public_research_evidence.py` | 134 | 5,805 |
| `scripts/compile_repository_task_context.py` | 201 | 9,906 |
| `scripts/evaluate_autonomous_frontier.py` | 1,112 | 54,154 |
| `scripts/finalize_math_contracts.py` | 72 | 3,089 |
| `scripts/finalize_research_bundle.py` | 55 | 2,723 |
| `scripts/generate_baseline_artifacts.py` | 50 | 2,413 |
| `scripts/generate_calibration_artifacts.py` | 39 | 1,987 |
| `scripts/import_independent_research_capture.py` | 46 | 1,970 |
| `scripts/import_independent_row_witness.py` | 44 | 1,833 |
| `scripts/prove_known_bad_fails.py` | 125 | 4,337 |
| `scripts/run_research_mutation.py` | 138 | 6,624 |
| `scripts/validate_baseline_framework.py` | 124 | 5,768 |
| `scripts/validate_baseline_models.py` | 41 | 1,417 |
| `scripts/validate_calibration_framework.py` | 83 | 4,779 |
| `scripts/validate_calibration_uncertainty.py` | 42 | 1,774 |
| `scripts/validate_contract_spine.py` | 181 | 8,182 |
| `scripts/validate_control_plane.py` | 301 | 14,297 |
| `scripts/validate_frontier_meta.py` | 39 | 1,293 |
| `scripts/validate_math_contracts.py` | 439 | 28,229 |
| `scripts/validate_mission_integrity.py` | 37 | 1,302 |
| `scripts/validate_outcomes_labels.py` | 284 | 16,484 |
| `scripts/validate_research_completion.py` | 287 | 18,180 |
| `scripts/validate_source_feasibility.py` | 22 | 676 |
| `scripts/validate_vertical_slice.py` | 225 | 10,837 |
| `src/cre_foundry/__init__.py` | 1 | 37 |
| `src/cre_foundry/baselines/__init__.py` | 5 | 196 |
| `src/cre_foundry/baselines/framework.py` | 472 | 33,758 |
| `src/cre_foundry/calibration/__init__.py` | 1 | 47 |
| `src/cre_foundry/calibration/framework.py` | 470 | 33,643 |
| `src/cre_foundry/contracts/__init__.py` | 2 | 55 |
| `src/cre_foundry/contracts/thin_slice.py` | 334 | 15,221 |
| `src/cre_foundry/math/__init__.py` | 5 | 162 |
| `src/cre_foundry/math/reference_oracle.py` | 213 | 9,697 |
| `src/cre_foundry/outcomes/__init__.py` | 1 | 61 |
| `src/cre_foundry/outcomes/ledger.py` | 614 | 32,273 |
| `src/cre_foundry/vertical/__init__.py` | 1 | 66 |
| `src/cre_foundry/vertical/shadow_slice.py` | 288 | 13,101 |
| `tasks/ARCHITECTURE-001.json` | 20 | 2,797 |
| `tasks/BASELINE-001.json` | 20 | 3,933 |
| `tasks/CALIBRATION-001.json` | 60 | 4,286 |
| `tasks/CONTRACT-001.json` | 20 | 2,477 |
| `tasks/FRONTIER-001.json` | 20 | 2,286 |
| `tasks/IDENTITY-001.json` | 20 | 2,943 |
| `tasks/MATH-001.json` | 25 | 3,172 |
| `tasks/OUTCOMES-001.json` | 20 | 3,481 |
| `tasks/RESEARCH-001.json` | 32 | 2,522 |
| `tasks/VERTICAL-001.json` | 20 | 2,917 |
| `uv.lock` | 249 | 27,408 |

## 5. Current Untracked Files

| File | Lines | Bytes |
|---|---:|---:|
| `control/ONE_SHOT_READINESS.json` | 189 | 36,140 |
| `opencode.json` | 52 | 969 |
| `opencode.json.before-direct-kimi-20260802-172550` | 67 | 1,339 |

## 6. Files Ever Committed but Absent from Current HEAD

These paths existed somewhere in Git history but are not tracked at the current HEAD. They may have been deleted, renamed, generated, or superseded.

No historically committed path is absent from current HEAD.

## 7. Rename and Deletion History

```text
(none)
```

## 8. Task and Result Inventory

| Task | Task status | Result artifact | Objective |
|---|---|---|---|
| `ARCHITECTURE-001` | `in_progress` | `NO RESULT FILE` | Harden the thin slice into replaceable application/module/API boundaries and a representative workflow that cannot bypass policy, protection, lineage, abstention, or idempotent issuance. |
| `BASELINE-001` | `completed` | `completed` | Implement a replaceable, point-in-time-safe synthetic framework that evaluates incumbent, random, transparent-rule, recency, and simple statistical ranking policies on identical candidate/route-day inputs and outcome contracts without claiming predictive validity or incremental lift. |
| `CALIBRATION-001` | `completed` | `completed` | Implement a replaceable public synthetic framework that evaluates calibration mechanics where probability outputs exist, preserves exact uncertainty and missingness states, reports subgroup and temporal sensitivity without sparse-cell overclaim, and propagates abstention through the exact-ten decision boundary. |
| `CONTRACT-001` | `completed` | `completed` | Define the smallest strict, versioned, point-in-time contract chain from an authorized source observation through canonical physical-location identity, eligibility/protection, synthetic scoring, exact-ten decision, and replayable output binding. |
| `FRONTIER-001` | `completed` | `completed` | Create the mandatory autonomous-frontier contract, strict tri-state evaluator, proof ceilings, external-block semantics, and adversarial meta-tests that mechanically govern all completion claims. |
| `IDENTITY-001` | `pending` | `NO RESULT FILE` | Implement synthetic temporal identity, alternative-link, ambiguity, conflict, relocation, unit, franchise, and fail-closed protected-account primitives while preserving distinct entity grains. |
| `MATH-001` | `completed` | `completed` | Define executable mathematical contracts for eligibility, protected masks, physical-location uniqueness, deterministic value-first selection, operational feasibility, and abstention, then differentially test a bounded exhaustive oracle. |
| `OUTCOMES-001` | `completed` | `completed` | Implement and evaluate synthetic F9 outcome, observation-window, maturity, censoring, competing-event, adjudication, deduplication, and lineage contracts without converting unavailable empirical evidence into labels. |
| `RESEARCH-001` | `completed` | `completed` | Close decision-changing public source and mechanism gaps, produce a dated claim-evidence graph and field-level canonical mapping, and convert access-dependent or empirical unknowns into exact gates. |
| `VERTICAL-001` | `completed` | `completed` | Connect the frozen observation/candidate contract and MATH exact-ten decision to the smallest deterministic synthetic route-day manifest, field-visit event, F9 outcome fixture, and full replay receipt. |

## 9. File Counts and Lines by Extension

| Extension | Files | Lines |
|---|---:|---:|
| `.json` | 372 | 152,907 |
| `.py` | 76 | 12,966 |
| `.md` | 52 | 12,760 |
| `.toml` | 9 | 92 |
| `.html` | 4 | 2,806 |
| `.sha256` | 2 | 115 |
| `[none]` | 1 | 14 |
| `.lock` | 1 | 249 |
| `.sh` | 1 | 38 |

## 10. Largest Current Files

| File | Lines | Bytes |
|---|---:|---:|
| `artifacts/baselines/canonical_run.json` | 95,837 | 3,983,204 |
| `artifacts/baselines/frozen_benchmark.json` | 12,636 | 636,497 |
| `artifacts/context/current_task_packet.md` | 9,149 | 434,559 |
| `artifacts/calibration/canonical_run.json` | 5,594 | 206,586 |
| `artifacts/outcomes/canonical_run.json` | 3,389 | 149,270 |
| `control/AUTONOMOUS_FRONTIER_CONTRACT.json` | 2,764 | 120,055 |
| `artifacts/research/raw/on_ogl_terms.html` | 1,034 | 95,339 |
| `artifacts/research/raw/independent/on_ogl_terms.html` | 1,034 | 95,339 |
| `artifacts/research/raw/independent/tor_coa_package.json` | 1 | 75,676 |
| `evals/public/calibration_framework_evaluator.py` | 852 | 71,865 |
| `artifacts/research/raw/tor_coa_package.json` | 1 | 71,736 |
| `artifacts/evaluations/autonomous_frontier_report.json` | 1,414 | 62,531 |
| `scripts/evaluate_autonomous_frontier.py` | 1,112 | 54,154 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/source_intelligence_registry.json` | 1,406 | 53,654 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/mechanism_signal_chain_registry.json` | 1,024 | 52,150 |
| `evals/public/baseline_framework_evaluator.py` | 689 | 50,759 |
| `artifacts/research/canonical_field_map.json` | 1,162 | 44,690 |
| `evals/public/outcomes_labels_evaluator.py` | 664 | 36,250 |
| `artifacts/research/raw/tor_ogl_terms.html` | 369 | 34,435 |
| `artifacts/research/raw/independent/tor_ogl_terms.html` | 369 | 34,435 |
| `src/cre_foundry/baselines/framework.py` | 472 | 33,758 |
| `src/cre_foundry/calibration/framework.py` | 470 | 33,643 |
| `src/cre_foundry/outcomes/ledger.py` | 614 | 32,273 |
| `scripts/build_research_contract.py` | 194 | 29,148 |
| `scripts/validate_math_contracts.py` | 439 | 28,229 |
| `uv.lock` | 249 | 27,408 |
| `artifacts/evaluations/baseline_model_synthetic.json` | 742 | 24,830 |
| `contracts/calibration_evaluation.schema.json` | 56 | 24,816 |
| `artifacts/evaluations/baseline_framework.json` | 742 | 24,814 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/level10/full_system_simulation.json` | 935 | 24,803 |
| `artifacts/evaluations/calibration_synthetic.json` | 702 | 24,722 |
| `artifacts/evaluations/calibration_framework.json` | 702 | 24,706 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/contracts/source_access_proof_registry.json` | 648 | 23,945 |
| `evals/public/test_autonomous_frontier.py` | 541 | 23,461 |
| `artifacts/outcomes/synthetic_input_ledger.json` | 497 | 22,969 |
| `evals/public/vertical_slice_evaluator.py` | 445 | 22,264 |
| `artifacts/architecture/public_evaluator_contract.json` | 408 | 22,144 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/interfaces/openapi.json` | 891 | 21,809 |
| `evals/public/contract_spine_evaluator.py` | 361 | 21,367 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/scripts/run_level10_simulation.py` | 328 | 21,248 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/field_question_bank.json` | 617 | 20,950 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/artifacts/context/current_task_packet.md` | 550 | 19,996 |
| `artifacts/math/estimand_registry.json` | 597 | 19,934 |
| `artifacts/calibration/public_evaluator_contract.json` | 169 | 19,523 |
| `artifacts/research/source_reproduction_report.json` | 527 | 19,341 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/canonical_data_product_registry.json` | 646 | 19,238 |
| `artifacts/baselines/public_evaluator_contract.json` | 203 | 18,651 |
| `scripts/validate_research_completion.py` | 287 | 18,180 |
| `evals/public/test_math_contracts.py` | 281 | 18,172 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/control/LEVEL10_DOMAIN_DEFINITIONS.json` | 462 | 17,444 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/source-proof-v0.10/docs/phase-zero/SOURCE_INTELLIGENCE_ATLAS.md` | 112 | 17,396 |
| `artifacts/task-results/CALIBRATION-001.json` | 163 | 17,389 |
| `control/TASK_GRAPH.json` | 323 | 16,846 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/proof/manifest.json` | 478 | 16,787 |
| `artifacts/task-results/BASELINE-001.json` | 163 | 16,700 |
| `scripts/validate_outcomes_labels.py` | 284 | 16,484 |
| `artifacts/research/source_feasibility_registry.v0.json` | 258 | 16,386 |
| `artifacts/research/claim_evidence_graph.json` | 464 | 16,279 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/research_evidence_registry.json` | 326 | 16,187 |
| `evals/public/test_calibration_framework.py` | 254 | 15,769 |
| `artifacts/task-results/OUTCOMES-001.json` | 306 | 15,737 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/codex_milestone_acceptance_plan.json` | 418 | 15,600 |
| `src/cre_foundry/contracts/thin_slice.py` | 334 | 15,221 |
| `artifacts/outcomes/public_evaluator_contract.json` | 150 | 15,125 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/docs/phase-zero/CRE_EVENT_TAXONOMY_V2.md` | 77 | 14,858 |
| `scripts/validate_control_plane.py` | 301 | 14,297 |
| `artifacts/task-results/BOOTSTRAP-001.json` | 141 | 14,169 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/MANIFEST.json` | 432 | 14,081 |
| `control/GATES.json` | 262 | 13,874 |
| `artifacts/evaluations/outcomes_synthetic.json` | 345 | 13,517 |
| `artifacts/research/raw/row_witness/capture_manifest.json` | 260 | 13,122 |
| `src/cre_foundry/vertical/shadow_slice.py` | 288 | 13,101 |
| `contracts/f9_outcome.schema.json` | 150 | 13,010 |
| `artifacts/task-results/RESEARCH-001.json` | 138 | 12,457 |
| `scripts/build_math_contracts.py` | 106 | 12,180 |
| `artifacts/task-results/FRONTIER-001.json` | 174 | 12,097 |
| `evals/public/test_baseline_framework.py` | 204 | 11,914 |
| `artifacts/task-results/CONTRACT-001.json` | 118 | 11,644 |
| `artifacts/task-results/MATH-001.json` | 131 | 11,606 |
| `artifacts/research/raw/independent/on_select_package.json` | 1 | 11,530 |
| `artifacts/task-results/VERTICAL-001.json` | 125 | 11,224 |
| `artifacts/vertical-slice/run_manifest.json` | 284 | 11,219 |
| `evals/public/test_outcomes_labels.py` | 183 | 11,212 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/contracts/implementation_architecture_contract.json` | 385 | 11,139 |
| `artifacts/research/raw/on_select_package.json` | 1 | 11,006 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/spatial-v0.11/docs/phase-zero/MASTER_SYSTEM_BLUEPRINT_V0.11.md` | 425 | 10,888 |
| `scripts/validate_vertical_slice.py` | 225 | 10,837 |
| `evals/public/test_vertical_slice.py` | 188 | 10,516 |
| `contracts/estimand_registry.schema.json` | 140 | 10,041 |
| `scripts/compile_repository_task_context.py` | 201 | 9,906 |
| `src/cre_foundry/math/reference_oracle.py` | 213 | 9,697 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/domain-v0.9/contracts/entity_relationship_ontology_v2.json` | 341 | 9,430 |
| `contracts/f9_outcome_input_ledger.schema.json` | 133 | 9,382 |
| `contracts/thin_slice_candidate.schema.json` | 155 | 9,328 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/implementation-v0.12/interfaces/asyncapi.json` | 385 | 9,253 |
| `artifacts/task-results/RESEARCH-001.partial.json` | 177 | 8,862 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/reference_vault/index/VAULT_INDEX.json` | 229 | 8,813 |
| `evals/public/math_oracle_evaluator.py` | 143 | 8,717 |
| `bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/standards/BENCHMARK_STANDARD_REGISTRY.json` | 257 | 8,324 |
| `artifacts/research/source_feasibility_registry.json` | 223 | 8,248 |

## 11. Codex Preservation Interpretation

Use the following evidence hierarchy:

1. Current Git objects and ancestry
2. Reflog, branches, tags and stashes
3. Unreachable Git objects
4. Current tracked and untracked files
5. Codex transcript/UI edit cards

The previously completed forensic audit found:

- Codex checkpoint `3d8407e` is an ancestor of current HEAD.
- Current HEAD is `9a5462d`.
- No stashes exist.
- No unreachable or dangling commits were found.
- Therefore, no identifiable committed Codex work is currently missing.

Historical paths listed in Section 6 still require semantic review. A deleted historical file is not necessarily lost work if a later commit intentionally replaced or regenerated it.
