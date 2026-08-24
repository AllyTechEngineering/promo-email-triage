# Promo Email Triage Agent

MVP agent that scans a Gmail inbox for bulk-marketing email, classifies it with a mix of Gmail's own tagging and content-signal checks, and — only after human review — moves approved messages to Trash. Never permanently deletes. Built as the first reference agent under Exem Concepts' AI Agent Development & Learning Plan.

## Status
Spec finalized (v1.0.0). Prototyping in progress. Not yet built as standalone scheduled code — currently being validated interactively.

## Structure
```
docs/
  SPEC.md         — the authoritative specification (versioned)
schema/
  schema.sql      — SQLite schema: sender_decisions, runs, audit_log
agent/            — (empty) future home for the standalone agent implementation
CHANGELOG.md      — version history
```

## Start here
Read `docs/SPEC.md`. Section 0 has version history; Section 4 has functional requirements; Section 9 has acceptance criteria for MVP sign-off.

## Target environment
Personal Gmail (admin rights). Microsoft 365 / Graph API is a deliberately deferred, separate effort — see `docs/SPEC.md` Section 2.2 and Section 10, item 5.
