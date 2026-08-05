# Brampton Verification Review Packets

This export layer creates one machine-readable JSON packet and one
human-readable Markdown packet for every task in the active verification
queue.

Snapshots are written under:

`outputs/brampton_verification_review_packets/<snapshot>/`

Each snapshot contains:

- `manifest.json`
- `queue.csv`
- one JSON packet per ready task
- one Markdown packet per ready task

## Packet content

Each packet includes:

- permit, opportunity and verification-task identifiers;
- current task and prerequisite state;
- provisional cross-source business evidence;
- historical and current candidate names;
- current directory attributes when available;
- a gate-specific analyst checklist;
- suggested evidence-source categories;
- safe command templates for appending ledger events.

## Workflow boundary

The exporter reads from:

- `control.brampton_verification_active_queue`
- `control.brampton_verification_events`
- `silver.brampton_permit_opportunity_evidence`

It does not modify DuckDB task state or append ledger events.

## Safety

The exporter does not:

- start or complete tasks;
- add analyst evidence;
- choose a verified business;
- rank opportunities;
- authorize or initiate contact.

Every packet preserves:

- `automatic_conclusion_allowed = false`
- `opportunity_ranked = false`
- `outreach_authorization_required = true`
- `outreach_eligible = false`
- `operating_mode = 'shadow'`
