CREATE TABLE IF NOT EXISTS voucher_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voucher_sessions (
    session_id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    content_version TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    seed BIGINT NOT NULL,
    status TEXT NOT NULL,
    identity_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    completed_at TEXT,
    abandoned_at TEXT,
    timer_state TEXT NOT NULL,
    time_limit_ms BIGINT,
    remaining_ms BIGINT,
    timer_client_event_at TEXT,
    last_checkpoint_at TEXT,
    basket_revision INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_voucher_active_player_version
ON voucher_sessions(player_id, content_version)
WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS voucher_session_offers (
    offer_instance_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES voucher_sessions(session_id),
    vendor_id TEXT NOT NULL,
    offer_id TEXT NOT NULL,
    offer_type TEXT NOT NULL,
    dialogue_root_node_id TEXT NOT NULL,
    dialogue_offer_node_id TEXT NOT NULL,
    ask_option_id TEXT NOT NULL,
    confirm_option_id TEXT NOT NULL,
    price_variant TEXT NOT NULL,
    base_price_cents INTEGER NOT NULL,
    bundle_size INTEGER NOT NULL,
    bundle_price_cents INTEGER NOT NULL,
    parameters_json TEXT NOT NULL,
    label_en TEXT NOT NULL,
    label_han TEXT NOT NULL,
    content_status TEXT NOT NULL,
    approved INTEGER NOT NULL,
    display_order INTEGER NOT NULL,
    revealed_at TEXT,
    resolved_at TEXT,
    UNIQUE(session_id, vendor_id)
);

CREATE TABLE IF NOT EXISTS voucher_session_questions (
    question_instance_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES voucher_sessions(session_id),
    offer_instance_id TEXT NOT NULL REFERENCES voucher_session_offers(offer_instance_id),
    skill TEXT NOT NULL,
    prompt_en TEXT NOT NULL,
    answer_unit TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    correct_answer INTEGER NOT NULL,
    rule_hint TEXT NOT NULL,
    formula_hint TEXT NOT NULL,
    correct_feedback TEXT NOT NULL,
    misconceptions_json TEXT NOT NULL,
    source_variant TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    first_try_correct INTEGER,
    UNIQUE(offer_instance_id, skill)
);

CREATE TABLE IF NOT EXISTS voucher_attempts (
    attempt_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL REFERENCES voucher_sessions(session_id),
    question_instance_id TEXT NOT NULL REFERENCES voucher_session_questions(question_instance_id),
    attempt_number INTEGER NOT NULL,
    answer INTEGER NOT NULL,
    answer_unit TEXT NOT NULL,
    english_support_used INTEGER NOT NULL,
    response_time_ms INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    misconception TEXT,
    feedback_level TEXT NOT NULL,
    feedback_en TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, question_instance_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS voucher_basket_items (
    session_id TEXT NOT NULL REFERENCES voucher_sessions(session_id),
    offer_instance_id TEXT NOT NULL REFERENCES voucher_session_offers(offer_instance_id),
    quantity INTEGER NOT NULL,
    spent_cents INTEGER NOT NULL,
    PRIMARY KEY(session_id, offer_instance_id)
);

CREATE TABLE IF NOT EXISTS voucher_session_events (
    event_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    session_id TEXT NOT NULL REFERENCES voucher_sessions(session_id),
    event_type TEXT NOT NULL,
    offer_instance_id TEXT,
    dialogue_node_id TEXT,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    internal INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS voucher_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_voucher_offers_session
ON voucher_session_offers(session_id);
CREATE INDEX IF NOT EXISTS ix_voucher_questions_session
ON voucher_session_questions(session_id);
CREATE INDEX IF NOT EXISTS ix_voucher_attempts_session
ON voucher_attempts(session_id);
CREATE INDEX IF NOT EXISTS ix_voucher_events_session
ON voucher_session_events(session_id);
