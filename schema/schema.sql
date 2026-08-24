-- Promo Email Triage Agent — Data Model
-- v1.0.0

-- One row per sender the agent has ever formed an opinion about.
-- This is the living decision store described in SPEC.md Section 5.3.
CREATE TABLE IF NOT EXISTS sender_decisions (
    sender_email    TEXT PRIMARY KEY,
    decision        TEXT NOT NULL CHECK (decision IN ('whitelist', 'blacklist', 'pending')),
    source          TEXT NOT NULL CHECK (source IN ('seed_list', 'agent_inferred', 'user_confirmed')),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per agent run (manual or scheduled).
CREATE TABLE IF NOT EXISTS runs (
    run_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT,
    mode                TEXT NOT NULL CHECK (mode IN ('manual', 'scheduled')),
    candidates_scanned  INTEGER DEFAULT 0,
    candidates_trashed  INTEGER DEFAULT 0,
    candidates_held     INTEGER DEFAULT 0,
    candidates_pending  INTEGER DEFAULT 0
);

-- One row per message the agent evaluated, every run. This is the
-- durable audit trail described in SPEC.md Section 7 (FR-6).
CREATE TABLE IF NOT EXISTS audit_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(run_id),
    message_id          TEXT NOT NULL,
    thread_id           TEXT,
    sender_email        TEXT NOT NULL,
    subject             TEXT,
    received_date       TEXT,
    age_days            INTEGER,
    gmail_category_hit  INTEGER NOT NULL DEFAULT 0,   -- 1 if category:promotions matched
    classification       TEXT NOT NULL CHECK (
        classification IN ('bulk_marketing', 'ambiguous', 'excluded_whitelist', 'excluded_blacklist_na')
    ),
    signals             TEXT,   -- free text, e.g. "unsubscribe_link,tracking_pixel,mass_footer"
    action_taken         TEXT NOT NULL CHECK (
        action_taken IN ('trashed', 'held_for_review', 'skipped_whitelist', 'skipped_pending_ask')
    ),
    decided_at           TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_sender ON audit_log(sender_email);
CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_log(run_id);
CREATE INDEX IF NOT EXISTS idx_sender_decision ON sender_decisions(decision);
