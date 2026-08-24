# Changelog
All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/), versioning is semantic (MAJOR.MINOR.PATCH) applied to the spec/agent as a whole.

## [1.1.0] - 2026-08-24
### Changed
- Replaced SQLite (`schema/schema.sql`) with a single JSON file (`data/store.json`) for sender decisions and a trashed-message log, validated against `schema/store.schema.json`.
- Replaced the full audit log (every candidate, classification, signals, per-run summary table) with a minimal `trashed_log` — only messages actually moved to Trash are recorded (sender, subject, message ID, timestamp). Classification reasoning is no longer persisted anywhere; it exists only in-memory during a run.
- Dropped the `runs` table concept entirely. Run summaries are reported in output only, not persisted.

### Added
- Tracked seed file `data/store.seed.json` — initial state (Appendix A whitelist pre-loaded, empty trashed log). Live `data/store.json` is generated from this seed on first run and is gitignored from that point forward.
- Explicit atomic-write requirement (SPEC.md Section 5.5): every write to `data/store.json` must use a write-temp-then-rename pattern, since a flat JSON file has no transactional guarantees.
- Startup schema-validation requirement (SPEC.md Section 8.1): agent must validate `data/store.json` against `schema/store.schema.json` before trusting it.
- New open item (SPEC.md Section 10, #4): full audit logging is explicitly flagged to be reinstated before this pattern is used for any client through Pete's MSP — dropped here only because personal-scale use doesn't yet need it.

### Rationale
Full audit logging (added in 1.0.0) was correctly identified by the owner as over-engineered for a single personal inbox with no external accountability requirement. Rather than delete the idea outright, it's documented as deliberately deferred — not forgotten — so it isn't rediscovered as a surprise gap when this pattern is later adapted for client work.

## [1.0.0] - 2026-08-24
### Added
- Full SME-format specification (`docs/SPEC.md`), superseding the informal 0.1.0 draft.
- Persistent sender-decision store design (`schema/schema.sql`, table `sender_decisions`) — replaces static whitelist with whitelist/blacklist/pending states and an ask-once escalation flow.
- Persistent audit log design (`schema/schema.sql`, table `audit_log`) — one row per evaluated candidate, per run, with classification and signal evidence.
- `runs` table for per-execution summary stats.
- Functional requirements FR-1 through FR-10, each with priority.
- Content-signal classification logic (Section 6) to distinguish true bulk marketing from personally-addressed automated outreach (validated against a real recruiter email during prototyping).
- Non-functional requirements: idempotency, safety guardrails (Trash-only, never auto-approve), data handling.
- Acceptance criteria checklist for MVP sign-off.
- Open items / risk log.
- Git version control established for spec and future agent code.

### Changed
- Whitelist mechanism: from "fixed list, provided once, rarely changes" to a living, queryable decision store seeded by that same list.

## [0.1.0] - 2026-08-24
### Added
- Initial informal spec captured via interview (docx format, not version controlled).
- Basic rule: `category:promotions` + 14-day age + static whitelist exclusion.
- Manual-then-weekly trigger cadence defined.
- Trash-only deletion action defined.

### Known limitations (resolved in 1.0.0)
- No audit trail.
- Whitelist could only exclude, not learn from ambiguous cases.
- Not under version control.