# Changelog
All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/), versioning is semantic (MAJOR.MINOR.PATCH) applied to the spec/agent as a whole.

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
