# Client Answer Workbook

Each section requires an authoritative value, named confirmer, timestamp and evidence reference.

## 1. primary_success_event

Which exact event is the pilot's primary success outcome?

Required fields:

- `event_name`
- `qualifying_definition`
- `observation_window_days`
- `evidence_required`
- `negative_definition`
- `censoring_rules`

- Complete: `false`
- Missing fields: `['censoring_rules', 'event_name', 'evidence_required', 'negative_definition', 'observation_window_days', 'qualifying_definition']`
- Blockers: `['client_confirmation_false', 'client_evidence_reference_missing', 'confirmed_at_missing_or_invalid', 'confirmed_by_missing', 'required_authoritative_fields_missing']`

## 2. transaction_economics

What are the firm's actual transaction economics?

Required fields:

- `currency`
- `typical_transaction_value_range`
- `commission_structure`
- `firm_share`
- `representative_share`
- `typical_sales_cycle_days`
- `typical_cost_per_assignment`
- `typical_cost_per_transaction`

- Complete: `false`
- Missing fields: `['commission_structure', 'currency', 'firm_share', 'representative_share', 'typical_cost_per_assignment', 'typical_cost_per_transaction', 'typical_sales_cycle_days', 'typical_transaction_value_range']`
- Blockers: `['client_confirmation_false', 'client_evidence_reference_missing', 'confirmed_at_missing_or_invalid', 'confirmed_by_missing', 'required_authoritative_fields_missing']`

## 3. pilot_representatives_and_capacity

Who are the actual pilot representatives and what can each handle?

Required fields:

- `representative_ids`
- `starting_locations`
- `territories`
- `specializations`
- `existing_relationships`
- `daily_review_capacity`
- `daily_action_capacity`
- `preferred_channels`
- `current_prospecting_routine`

- Complete: `false`
- Missing fields: `['current_prospecting_routine', 'daily_action_capacity', 'daily_review_capacity', 'existing_relationships', 'preferred_channels', 'representative_ids', 'specializations', 'starting_locations', 'territories']`
- Blockers: `['client_confirmation_false', 'client_evidence_reference_missing', 'confirmed_at_missing_or_invalid', 'confirmed_by_missing', 'required_authoritative_fields_missing']`

## 4. protected_accounts_and_exclusions

Which accounts, relationships and territories must be excluded?

Required fields:

- `existing_clients`
- `protected_relationships`
- `active_assignments`
- `do_not_contact_records`
- `broker_owned_accounts`
- `conflicts`
- `territory_restrictions`
- `contact_frequency_limits`

- Complete: `false`
- Missing fields: `['active_assignments', 'broker_owned_accounts', 'conflicts', 'contact_frequency_limits', 'do_not_contact_records', 'existing_clients', 'protected_relationships', 'territory_restrictions']`
- Blockers: `['client_confirmation_false', 'client_evidence_reference_missing', 'confirmed_at_missing_or_invalid', 'confirmed_by_missing', 'required_authoritative_fields_missing']`

## 5. operating_environment

Which operating environment must the alpha use?

Required fields:

- `primary_interface`
- `deployment_location`
- `authentication_method`
- `supported_devices`
- `crm_or_sheet_integration`
- `data_export_format`
- `notification_channels`
- `retention_requirements`
- `backup_requirements`

- Complete: `false`
- Missing fields: `['authentication_method', 'backup_requirements', 'crm_or_sheet_integration', 'data_export_format', 'deployment_location', 'notification_channels', 'primary_interface', 'retention_requirements', 'supported_devices']`
- Blockers: `['client_confirmation_false', 'client_evidence_reference_missing', 'confirmed_at_missing_or_invalid', 'confirmed_by_missing', 'required_authoritative_fields_missing']`
