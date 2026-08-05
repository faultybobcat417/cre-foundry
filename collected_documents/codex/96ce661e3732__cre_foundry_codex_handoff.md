# CRE Foundry Codex Handoff

## Role

Act as the senior staff engineer, quantitative research engineer and data
governance lead for CRE Foundry.

Work directly inside the existing local repository. Inspect the implementation
before changing it. Preserve the existing architecture, tests, contracts,
source-governance rules and fail-closed behavior.

Do not rebuild the project from scratch.

## End Goal

Build a local-first, adaptive and auditable commercial-real-estate decision
system for Southern Ontario.

The system should eventually help representatives decide where limited
prospecting and verification effort should be allocated each day.

The system must distinguish carefully between:

- source evidence;
- address evidence;
- business identity;
- permit applicant;
- intended occupant;
- current commercial requirement;
- relevant decision-maker;
- internal relationship restrictions;
- outreach authorization;
- opportunity scoring and ranking.

None of these concepts may be silently treated as equivalent.

## Current Geographic and Market Scope

Initial operating scope:

- Brampton, Ontario;
- industrial and flex occupiers;
- active industrial building-permit signals;
- tenant-representation oriented research;
- shadow operating mode.

Historical ODBus coverage also includes Mississauga, but current operational
work is concentrated on Brampton because the licensed Brampton Business
Directory and industrial permit sources are already connected.

## Current Repository State

The project currently contains:

1. Local ARM64 Python environment managed by uv.
2. DuckDB analytical warehouse.
3. SQLite control plane using WAL and guarded writes.
4. Source registry, run history, locks and adaptive cadence.
5. Prefect metadata-watch orchestration.
6. launchd scheduling.
7. Statistics Canada ODBus bronze, silver and canonical entity models.
8. Brampton industrial permit bronze and silver models.
9. Conservative permit event and lifecycle classifiers.
10. Exact permit-to-historical-entity bridge.
11. Licensed Brampton Business Directory bronze and silver models.
12. Exact permit-to-current-directory address bridge.
13. Historical-versus-current cross-source reconciliation.
14. Unified permit opportunity-evidence table.
15. Ten mandatory verification gates per permit.
16. Additional evidence-resolution tasks for ambiguous or unresolved records.
17. Append-only verification event ledger in SQLite.
18. Hash-chained verification events.
19. Rebuildable DuckDB task and workflow projections.
20. Human and machine-readable review-packet exports.

At the current checkpoint:

- 30 active industrial permit evidence rows exist.
- 319 verification tasks exist.
- 30 tasks are initially ready.
- 19 ready tasks are evidence-resolution tasks.
- 11 ready tasks are identity-verification tasks.
- zero analyst events have been recorded;
- zero tasks are completed;
- zero requirements are verified;
- zero decision-makers are verified;
- zero opportunities are ranked;
- zero records are outreach eligible.

## Non-Negotiable Safety Rules

Keep all of the following rules unless the user explicitly approves a later,
documented governance change:

- operating mode remains shadow;
- outreach_eligible remains false;
- opportunity_ranked remains false;
- automatic identity promotion remains false;
- an address match is not occupant proof;
- a directory record is not permit-applicant proof;
- a permit is not proof of a commercial requirement;
- a business name is not proof of a decision-maker;
- cross-source name agreement is diagnostic evidence only;
- fuzzy matching cannot promote identities automatically;
- historical ODBus records cannot establish current operating status;
- analyst evidence must be recorded through the append-only ledger;
- source-derived silver tables must not be overwritten with analyst conclusions;
- every result must remain reproducible and auditable;
- queue priority is workflow ordering, not opportunity scoring;
- passing verification does not itself authorize outreach;
- internal exclusions and relationship restrictions remain mandatory.

## Engineering Rules

Follow these repository conventions:

- use Python 3.12;
- preserve ARM64 compatibility;
- use pathlib;
- add type annotations;
- use Ruff formatting and linting;
- use mypy;
- add targeted pytest coverage;
- run targeted checks before the full suite;
- finish every checkpoint with scripts/verify.sh;
- keep data, logs, outputs and mutable control state out of Git;
- write generated contracts atomically;
- use transactions around warehouse model replacement;
- use append-only control events for analyst state;
- reject invalid state transitions;
- avoid hidden network calls in tests;
- use fixtures instead of live sources in unit tests;
- do not introduce fuzzy or probabilistic promotion without a separate review
  contract;
- do not introduce ranking until verified outcome labels and evaluation rules
  exist.

Make small, coherent commits. Do not mix unrelated changes.

## Existing Verification Workflow

Every permit receives these ten blocking gates:

1. identity_verification
2. permit_occupancy_verification
3. commercial_requirement_verification
4. decision_maker_verification
5. existing_client_exclusion
6. protected_relationship_check
7. active_assignment_conflict_check
8. territory_restriction_check
9. relationship_owner_check
10. do_not_contact_check

Ambiguous, conflicting or unresolved records receive an additional:

- evidence_resolution

The current event ledger supports:

- task_started
- evidence_added
- task_passed
- task_failed
- task_reset

A task cannot pass or fail unless it is in progress and has at least one
evidence event since its latest reset.

## Immediate Next Milestone

Build an analyst-operated verification interface without changing the safety
model.

The interface should initially be a local CLI and file workflow, not a complex
web application.

Implement the following cohesive milestone:

### A. Review Queue Commands

Add commands that can:

- list current ready tasks;
- filter by gate, strength, evidence status and permit number;
- show a compact task packet;
- show the full event history for one task;
- show the workflow state for one opportunity;
- print the exact safe commands required to start, add evidence, pass, fail or
  reset a task.

The listing command must never rank opportunities. It may only preserve the
existing workflow queue priority.

### B. Structured Evidence Input

Create a validated local JSON input format for analyst evidence.

Required fields should include:

- verification_task_id;
- reviewer;
- event_type;
- evidence_source_type when applicable;
- evidence_reference when applicable;
- evidence_observed_at;
- findings;
- contradictory_evidence;
- remaining_uncertainty;
- notes.

Add a dry-run validator that performs no writes.

Add an explicit import command that appends validated events to the existing
ledger.

Reject:

- unknown task IDs;
- invalid event types;
- missing evidence references;
- pass or fail without evidence;
- completed-task mutations without reset;
- conclusions for blocked tasks;
- malformed timestamps;
- empty reviewers;
- attempts to set outreach eligibility or opportunity rank.

### C. Batch Safety

Support batch evidence files, but require the whole batch to validate before
any event is written.

Use a control-plane transaction so partially accepted batches are impossible.

Reproject verification state only after the entire batch commits.

### D. Audit Export

Create a reproducible audit export for one task and one opportunity containing:

- source task definition;
- all append-only events;
- event-chain verification;
- current task state;
- prerequisite state;
- workflow state;
- current safety locks.

### E. Tests and Contracts

Add:

- unit tests for validation;
- state-transition tests;
- atomic batch rollback tests;
- event-chain tests;
- CLI tests where practical;
- Markdown and JSON contracts;
- one live zero-write smoke test.

Do not record real analyst conclusions during implementation.

## Milestone After the Verification Interface

After the analyst interface is complete, continue in this order:

1. Integrate rebuilding of opportunity evidence, verification plan and state
   projection into the governed metadata-watch pipeline.
2. Add freshness and staleness status to every source-derived evidence row.
3. Add explicit source-snapshot lineage to every verification packet.
4. Add a governed internal exclusions import contract.
5. Add representative, territory and relationship-owner reference tables.
6. Design verified-outcome labels.
7. Build a shadow-only scoring research dataset.
8. Establish baselines and backtesting before any machine-learning model.
9. Compare transparent rules, logistic models and tree models.
10. Add calibration, ranking metrics and temporal validation.
11. Keep production outreach disabled until governance and pilot acceptance
    criteria are explicitly approved.

## Quantitative Modeling Boundary

Do not create a production opportunity score yet.

Before modeling, the repository must contain verified labels such as:

- occupant identity confirmed;
- requirement confirmed;
- requirement type;
- decision-maker confirmed;
- contact permitted;
- meeting obtained;
- mandate obtained;
- transaction outcome;
- timestamps for each stage.

Model evaluation must account for:

- temporal leakage;
- source availability at prediction time;
- class imbalance;
- geographic drift;
- sector drift;
- repeated businesses and addresses;
- duplicated permits;
- calibration;
- precision at the daily representative capacity;
- value-weighted outcomes;
- abstention and uncertainty.

## Required Working Method

Start every work session by:

1. reading this handoff;
2. checking git status and recent tags;
3. running scripts/verify.sh;
4. inspecting the existing contracts and implementation;
5. identifying the smallest coherent milestone;
6. implementing it with targeted tests;
7. running the full verification suite;
8. committing and tagging the completed milestone;
9. leaving the repository clean.

Do not ask the user to manually reproduce information already present in this
repository or handoff.

If a requirement is genuinely unresolved, preserve it as an explicit
configuration value, verification gate or documented placeholder rather than
inventing a business rule.

## Completion Criteria for the Immediate Milestone

The analyst verification interface is complete only when:

- all existing tests pass;
- new tests pass;
- the repository is clean;
- zero live analyst conclusions were created during testing;
- the live ledger still contains zero events unless the user deliberately
  supplied evidence;
- batch imports are atomic;
- dry runs perform no writes;
- source silver tables remain unchanged;
- every event remains hash chained;
- invalid transitions fail closed;
- outreach remains false;
- opportunity ranking remains disabled;
- a new tagged checkpoint exists.
