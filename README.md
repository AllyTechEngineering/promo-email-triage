# Promo Email Triage Agent

MVP agent that scans a Gmail inbox for bulk-marketing email, classifies it with a mix of Gmail's own tagging and content-signal checks, and — only after human review — moves approved messages to Trash. Never permanently deletes. Built as the first reference agent under Exem Concepts' AI Agent Development & Learning Plan.

## Status
Spec finalized (v1.1.0). Prototyping in progress. Not yet built as standalone scheduled code — currently being validated interactively.

## Structure
```
docs/
SPEC.md — the authoritative specification (versioned)
schema/
store.schema.json — JSON Schema for the data store
data/
store.seed.json — tracked seed data (initial whitelist, empty trashed log)
store.json — live runtime state (gitignored, generated from seed on first run)
agent/ — (empty) future home for the standalone agent implementation
CHANGELOG.md — version history
```

## Start here
Read `docs/SPEC.md`. Section 0 has version history; Section 4 has functional requirements; Section 5 has the data store design; Section 9 has acceptance criteria for MVP sign-off.

## What changed in 1.1.0
Storage moved from SQLite to a single JSON file, and logging was scaled back from a full per-candidate audit trail to a minimal record of what was actually trashed. Both were deliberate simplifications for personal-inbox scale — not oversights. Full audit logging is explicitly flagged in `docs/SPEC.md` Section 10 to come back before this pattern is used for any client through Pete's MSP.

## Target environment
Personal Gmail (admin rights). Microsoft 365 / Graph API is a deliberately deferred, separate effort — see `docs/SPEC.md` Section 2.2 and Section 10, item 5.

## Version control
This repo is git-controlled locally (tags `v0.1.0`, `v1.0.0`; `v1.1.0` pending tag once these file updates are committed). Not yet pushed to GitHub — the GitHub connector wasn't cooperating, so files are currently synced into this Claude Project's knowledge store manually for review instead. Revisit pushing to a real GitHub remote once that's sorted out.