PRAGMA foreign_keys = ON;

CREATE TABLE pilot_recommendations (
    recommendation_id TEXT PRIMARY KEY,
    decision_run_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    property_id TEXT,
    representative_id TEXT,
    generated_at TEXT NOT NULL,
    as_of_at TEXT NOT NULL,
    evidence_bundle_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    assignment_group TEXT NOT NULL,
    assignment_probability REAL,
    excluded INTEGER NOT NULL CHECK (excluded IN (0, 1)),
    exclusion_reason TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE pilot_actions (
    action_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    representative_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    action_status TEXT NOT NULL,
    override_reason TEXT,
    evidence_reference TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (
        recommendation_id
    ) REFERENCES pilot_recommendations (
        recommendation_id
    )
);

CREATE TABLE pilot_outcome_events (
    outcome_event_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    action_id TEXT,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    contact_established TEXT,
    decision_maker_reached TEXT,
    meaningful_cre_conversation TEXT,
    requirement_confirmed TEXT,
    previously_known TEXT,
    requirement_type TEXT,
    need_horizon TEXT,
    representation_status TEXT,
    evidence_reference TEXT,
    censored INTEGER NOT NULL CHECK (censored IN (0, 1)),
    censoring_reason TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (
        recommendation_id
    ) REFERENCES pilot_recommendations (
        recommendation_id
    ),
    FOREIGN KEY (
        action_id
    ) REFERENCES pilot_actions (
        action_id
    )
);

CREATE TABLE pilot_economic_events (
    economic_event_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    amount_minor_units INTEGER,
    currency_code TEXT,
    representative_minutes INTEGER,
    travel_minutes INTEGER,
    contact_cost_minor_units INTEGER,
    data_cost_minor_units INTEGER,
    evidence_reference TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (
        recommendation_id
    ) REFERENCES pilot_recommendations (
        recommendation_id
    )
);

CREATE TABLE pilot_exclusions (
    exclusion_event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    property_id TEXT,
    exclusion_type TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    expires_at TEXT,
    evidence_reference TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TRIGGER pilot_recommendations_no_update
BEFORE UPDATE ON pilot_recommendations
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_update_forbidden'
    );
END;

CREATE TRIGGER pilot_recommendations_no_delete
BEFORE DELETE ON pilot_recommendations
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_delete_forbidden'
    );
END;

CREATE TRIGGER pilot_actions_no_update
BEFORE UPDATE ON pilot_actions
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_update_forbidden'
    );
END;

CREATE TRIGGER pilot_actions_no_delete
BEFORE DELETE ON pilot_actions
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_delete_forbidden'
    );
END;

CREATE TRIGGER pilot_outcome_events_no_update
BEFORE UPDATE ON pilot_outcome_events
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_update_forbidden'
    );
END;

CREATE TRIGGER pilot_outcome_events_no_delete
BEFORE DELETE ON pilot_outcome_events
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_delete_forbidden'
    );
END;

CREATE TRIGGER pilot_economic_events_no_update
BEFORE UPDATE ON pilot_economic_events
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_update_forbidden'
    );
END;

CREATE TRIGGER pilot_economic_events_no_delete
BEFORE DELETE ON pilot_economic_events
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_delete_forbidden'
    );
END;

CREATE TRIGGER pilot_exclusions_no_update
BEFORE UPDATE ON pilot_exclusions
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_update_forbidden'
    );
END;

CREATE TRIGGER pilot_exclusions_no_delete
BEFORE DELETE ON pilot_exclusions
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_delete_forbidden'
    );
END;
