# Promo Email Triage Agent — Project Context

## What this is
A proof-of-concept agent that scans a Gmail inbox for bulk-marketing email,
classifies it, and — only after explicit human review — moves approved
messages to Gmail Trash. It never permanently deletes anything.

This is a reference implementation for a client-facing "inbox cleanup"
agent pattern: scan → classify → human review gate → act. The version here
targets a single Gmail inbox; the same pattern is intended to generalize to
other mail platforms (e.g. Microsoft 365 / Graph API) and multi-tenant use
in a future iteration — not in scope for this version.

**Authoritative spec:** `docs/SPEC.md` (currently v1.1.0). Read it before
making any design decision — this file is a summary, not a replacement.

## Tech stack
- Python
- Gmail API for scanning/trashing messages
- A single JSON file (`data/store.json`) as the data store — no database
- Validated against `schema/store.schema.json`

## Hard constraints — never violate these
- **Never permanently delete email.** Trash only (`trashMessage`/`trashThread`
  equivalents). Permanent delete is explicitly disallowed regardless of how
  the request is phrased.
- **Never auto-approve a delete batch.** Every run must stop at a human
  review step before anything is trashed — manual mode and scheduled mode
  both.
- **Never skip the ask-once flow for a new ambiguous sender.** See
  `docs/SPEC.md` Section 6.2 / FR-5.
- **All writes to `data/store.json` must be atomic**: write to a temp file,
  then rename over the original. A crash mid-write must never corrupt or
  truncate the store. (Section 5.5.)
- **Validate `data/store.json` against `schema/store.schema.json` on
  startup** before trusting it. If validation fails, halt and alert — don't
  silently overwrite.

## Data model (current — v1.1.0)
`data/store.json` holds exactly two things:
1. `sender_decisions` — keyed by email address, each with a `decision`
   (`whitelist` | `blacklist` | `pending`) and `source`
   (`seed_list` | `agent_inferred` | `user_confirmed`)
2. `trashed_log` — one entry per message actually trashed (message_id,
   sender_email, subject, trashed_at). No classification reasoning is
   persisted — that's intentional (Section 5.6), not a gap.

`data/store.seed.json` is the tracked starting state (whitelist pre-loaded,
empty trashed_log). `data/store.json` is generated from the seed on first
run and is gitignored after that — it's runtime state, not source.

## What's deliberately NOT built yet (see SPEC.md Section 10)
- Full audit logging (every candidate + classification + signals) was cut
  for this scale of deployment. It should be reinstated before this agent
  is used in any production/client-facing context — don't quietly rebuild
  it now, and don't quietly leave it out of a later production version
  either. It's a tracked open item, not a closed decision.
- No scheduling/cron mechanism chosen yet for the weekly run (Phase 2).
- Microsoft 365 / Graph API support — out of scope, deferred by design.

## Workflow this agent must follow (SPEC.md Section 7)
1. Scan Gmail: `category:promotions older_than:14d`
2. Drop anything whose sender is `whitelist` in the store
3. Anything `blacklist` skips straight to candidate list
4. Everything else gets content-signal classification (Section 6.2:
   unsubscribe link, tracking pixel, mail-merge artifacts, ESP sending
   infrastructure — 2+ signals = bulk_marketing, else ambiguous)
5. Ambiguous senders get asked about once, answer persisted to the store
6. Present the review list, grouped by sender — nothing deleted yet
7. Wait for explicit approval
8. Trash only what was approved
9. Append trashed messages to `trashed_log`

## How this project should be built
Propose a plan before writing code — don't jump straight to implementation.
Build incrementally, one piece at a time, rather than generating the whole
agent in one shot. Each piece should be reviewable on its own before moving
to the next. Explain non-obvious code when asked, in plain terms.