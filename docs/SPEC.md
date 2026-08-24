# Agent Specification: Promo Email Triage

| | |
|---|---|
| **Document ID** | EXEM-AGT-001 |
| **Version** | 1.2.0 |
| **Status** | Draft — Approved for prototyping, not yet approved for scheduled/unattended operation |
| **Owner** | Bobby Taylor, Exem Concepts |
| **Governing framework** | AI Agent Development & Learning Plan (AI_Agent_Development.docx) |
| **Target environment (this version)** | Personal Gmail (admin rights) — MVP only |
| **Future environment (out of scope, this version)** | Microsoft 365 / Graph API, multi-tenant, for Pete's MSP clients |

---

## 0. Version History

| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1.0 | 2026-08-24 | Bobby Taylor + Claude | Initial informal draft. Static whitelist, no logging, no persistence layer. Superseded. |
| 1.0.0 | 2026-08-24 | Bobby Taylor + Claude | Full SME rewrite. Added persistent audit log (every candidate, every classification reason), living sender-decision store replacing static whitelist, SQLite data model, ambiguous-candidate escalation workflow, non-functional requirements, acceptance criteria, git version control. |
| 1.1.0 | 2026-08-24 | Bobby Taylor + Claude | Simplified for personal-MVP scale, per direct owner feedback that full audit logging was over-engineered for a single personal inbox. Replaced SQLite with a single JSON file. Replaced the full audit log (every candidate + classification + signals) with a minimal trashed-log (only messages actually trashed, no reasoning detail retained). Sender decision store (whitelist/blacklist/pending) retained as-is — it drives behavior, not just logging, so it stays. Full audit logging is deferred to whenever this pattern is adapted for client-facing/M365 use, where a defensible record of agent decisions becomes a real requirement. |
| 1.2.0 | 2026-08-24 | Bobby Taylor + Claude | Added Section 10 item on UI/frontend strategy: the frontend is deliberately deferred and undecided, and the backend (`agent/*.py`) is being built UI-agnostic on purpose — no CLI, GUI, or API-consumer assumptions baked into `store.py`, `gmail_client.py`, `classify.py`, or `workflow.py`. Documented now so this isn't quietly decided by default before there's evidence for what a production UI should be (native Windows GUI, a Flutter cross-platform client talking to a local API layer, a browser-based tool, or continued CLI). |

Change requests against this spec should be made as edits to `docs/SPEC.md` with an updated Version History row. Do not silently edit prior sections without a version bump.

---

## 1. Purpose & Business Context

Bobby (Exem Concepts, 1099 contractor to Pete's MSP) needs a working reference pattern for an email-triage agent: scan → classify → hold for human review → act. This is the first agent built under the governing Learning Plan and is intended to generalize: the classification and review-gate pattern developed here is the template for future client-facing agents in Pete's tiered AI service offering (M365/Graph API target, out of scope for this version).

**Primary use case:** reduce inbox clutter from bulk marketing email without risking loss of anything from a real correspondent.

**Note on scale (added in 1.1.0):** this version is scoped deliberately small — one personal inbox, one owner, no external accountability requirement yet. Design choices below (JSON file instead of a database, minimal logging instead of a full audit trail) reflect that. When this pattern is adapted for a paying client, several of these choices should be revisited — flagged explicitly in Section 10 rather than built prematurely.

---

## 2. Scope

### 2.1 In scope
- Gmail inbox, one personal account, owner has full admin rights
- Detection of bulk/promotional email using Gmail's `category:promotions` label as a first-pass filter, refined by content-signal classification (Section 6)
- Human-reviewed deletion (move to Trash, never permanent delete)
- Persistent sender-decision memory (JSON file)
- A minimal log of what was actually trashed
- Manual trigger (Phase 1) and unattended weekly trigger (Phase 2)
- A CLI entry point (`main.py`) sufficient to run and validate the agent end-to-end

### 2.2 Out of scope (this version)
- Microsoft 365 / Outlook / Graph API — requires separate M365 Developer Program sandbox effort
- Multi-tenant / multi-client operation
- Any label other than Promotions (e.g., Social, Updates, Forums)
- Folders/labels other than Inbox
- Permanent deletion (explicitly disallowed, see Section 8.2)
- Full audit trail of every evaluated candidate (deferred — see Section 10)
- Any production-facing UI decision (native GUI, cross-platform app, web UI) — deferred, see Section 10

---

## 3. Definitions

| Term | Definition |
|---|---|
| **Candidate** | A message that has passed the initial `category:promotions` + age filter and is under consideration for deletion. |
| **Bulk marketing** | Automated, templated mail sent to many recipients — regardless of whether it reads as personally addressed. Confirmed via structural signals (Section 6.2), not tone. |
| **Sender decision store** | Persistent record (`sender_decisions` in the JSON store) of whether a sender is always-keep, always-candidate, or undecided. |
| **Ambiguous candidate** | A message matching `category:promotions` + age, with no confirmed sender decision, whose content signals are mixed or inconclusive. |
| **Trashed log** | A minimal running record of messages the agent actually moved to Trash — sender, subject, message ID, when. No classification reasoning retained. |

---

## 4. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Agent scans Gmail Inbox for messages matching `category:promotions` AND older than a configurable age threshold (default 14 days). | Must |
| FR-2 | Agent excludes any message whose sender is recorded as `whitelist` in the sender decision store. | Must |
| FR-3 | Agent applies content-signal classification (Section 6) to every remaining candidate to confirm bulk-marketing status. | Must |
| FR-4 | Confirmed bulk-marketing candidates are added to a review list; nothing is deleted without explicit human approval of that run's list. | Must |
| FR-5 | Candidates classified as **ambiguous** are NOT auto-included in the delete batch. Agent asks the user once per unresolved sender; the answer is written to the sender decision store (whitelist or blacklist) so future runs never ask again for that sender. | Must |
| FR-6 | Every message the agent actually moves to Trash is appended to the trashed log (sender, subject, message ID, timestamp). Candidates that were held, skipped, or excluded are **not** logged individually — only actual deletions are recorded. | Must |
| FR-7 | On approval, agent moves only the approved messages to Gmail Trash (`trashMessage`/`trashThread`). Permanent delete is never invoked. | Must |
| FR-8 | Agent supports manual, on-demand triggering. | Must |
| FR-9 | Agent supports unattended weekly triggering, but still halts at the human-review gate (FR-4) — no auto-delete without approval, even when scheduled. | Should (Phase 2) |
| FR-10 | Agent reports a run summary (scanned / trashed / held / pending-ask counts) in its output at the end of each run. This summary is ephemeral (printed/returned), not persisted — see Section 5. | Should |

---

## 5. Data Store

A single JSON file (`data/store.json`) holds two things: the sender decision store, and the trashed log. Structure and validation rules are defined in `schema/store.schema.json`. A tracked seed file, `data/store.seed.json`, holds the initial state (Appendix A whitelist pre-loaded, empty trashed log) — the live `data/store.json` is generated from this seed on first run and is gitignored from that point forward (it's runtime state, not source).

### 5.1 Structure

```json
{
  "meta": {
    "schema_version": "1.1.0",
    "updated_at": "ISO-8601 timestamp"
  },
  "sender_decisions": {
    "sender@example.com": {
      "decision": "whitelist | blacklist | pending",
      "source": "seed_list | agent_inferred | user_confirmed",
      "notes": "string or null",
      "created_at": "ISO-8601 timestamp",
      "updated_at": "ISO-8601 timestamp"
    }
  },
  "trashed_log": [
    {
      "message_id": "string",
      "thread_id": "string",
      "sender_email": "string",
      "subject": "string",
      "trashed_at": "ISO-8601 timestamp"
    }
  ]
}
```

### 5.2 Sender decision states
- **whitelist** — never a candidate, regardless of category/content
- **blacklist** — confirmed bulk marketing; future messages from this sender skip content-classification and go straight to the candidate list
- **pending** — seen but not yet resolved; triggers the ask-once flow (FR-5)

### 5.3 Seeding
Version 1 seed list (whitelist, provided by Bobby 2026-08-24) is pre-loaded into `data/store.seed.json` — see Appendix A. Copied to `data/store.json` once at first run; not re-requested on subsequent runs.

### 5.4 Growth
Every ambiguous candidate resolved by the user (FR-5) is written back as `whitelist` or `blacklist` with `source = "user_confirmed"`. Over time this store should require decreasing manual input.

### 5.5 Write discipline
Because a JSON file has no transactional guarantees, every write to `data/store.json` MUST follow an atomic-replace pattern: write the full updated structure to a temp file in the same directory, then rename the temp file over the original. Partial writes (a crash mid-write) must never be able to leave `data/store.json` truncated or invalid. This is a hard requirement — see Section 8.1.

Sender-decision writes (`set_sender_decision`) persist immediately, not batched — losing an ask-once answer to a crash would break FR-5's "never ask again" guarantee. Trashed-log writes may be batched, since the Gmail Trash action itself is the actual source of truth for a deletion having happened.

### 5.6 What is deliberately NOT stored
Per-run scan results, held/skipped candidates, and classification reasoning are not persisted anywhere. They exist only in the review-list output shown to Bobby during a run and are gone once the run ends. If Bobby later wants that history retained, that's a spec change (see Section 10).

---

## 6. Classification Logic

### 6.1 First-pass filter (cheap, deterministic)
Gmail search: `category:promotions older_than:{N}d` — see Appendix B for exact query syntax.

### 6.2 Content-signal confirmation (required before any candidate is trusted)
Gmail's Promotions classifier alone is not sufficient — validated empirically during prototyping (2026-08-24: a recruiter's message was correctly caught, but only after checking structural signals, not sender identity or tone). The agent checks message content for:

- Unsubscribe link / "manage preferences" link
- Tracking pixel (1x1 image, open-tracking URL patterns)
- Mail-merge artifacts (personalization tokens, bulk ESP footer boilerplate — "you received this because...")
- Sending infrastructure associated with marketing/ESP platforms (e.g. campaign subdomains)

**Rule:** two or more signals present → classify `bulk_marketing`. One or zero signals present → classify `ambiguous`, route to FR-5.

Note (revised in 1.1.0): this classification happens in-memory during a run and is used to decide the action taken. It is **not** written to persistent storage — only the final trashed/not-trashed outcome matters for the record (Section 5.6).

*(Open item, Section 10: signal detection is currently manual/LLM-judgment based, not yet codified into a deterministic scoring function. Acceptable for prototyping; should be tightened before Phase 2 / unattended operation.)*

---

## 7. Workflow

1. **Scan** — query per Section 6.1
2. **Pre-filter** — drop anything with sender decision `whitelist`
3. **Fast-path** — anything with sender decision `blacklist` skips straight to candidate list (classification already resolved for this sender)
4. **Classify** — apply Section 6.2 to everything else
5. **Resolve ambiguous** — for each ambiguous sender not already `pending` in the store, ask the user once; persist the answer immediately (FR-5, Section 5.5)
6. **Present** — review list of confirmed bulk-marketing candidates, grouped by sender, with subject/date
7. **Approve** — user confirms all, some, or none
8. **Act** — move approved messages to Trash only
9. **Record** — append each trashed message to `trashed_log`; report run summary in output (not persisted)

---

## 8. Non-Functional Requirements & Guardrails

### 8.1 Reliability
- Idempotent re-runs: a message already present in `trashed_log` must not be re-presented as a candidate.
- Partial failure (API): if the Gmail API fails mid-batch, already-approved-and-trashed messages remain trashed and are logged; unprocessed candidates are simply left for the next run. No partial/inconsistent state should block future runs.
- Partial failure (storage): all writes to `data/store.json` use the atomic-replace pattern in Section 5.5. A crash or interrupted write must never corrupt or truncate the store. On startup, the agent should validate `data/store.json` against `schema/store.schema.json` before trusting it; if validation fails, halt and alert rather than silently overwriting.

### 8.2 Safety
- **Never** permanent-delete. Trash only.
- **Never** auto-approve a delete batch, in manual or scheduled mode.
- **Never** silently skip the ask-once flow for a genuinely new ambiguous sender.

### 8.3 Data handling
- `data/store.json` (sender decisions, trashed log) is local to Bobby's environment. No transmission of inbox content to third parties beyond what Gmail's own API + the LLM classification step already requires.

### 8.4 Performance / cost
- Not yet specified. Open item (Section 10).

---

## 9. Acceptance Criteria (for MVP sign-off)

- [ ] A manual run correctly excludes all Appendix A whitelist senders
- [ ] A manual run correctly identifies at least one bulk-marketing message via content signals, not category alone
- [ ] An ambiguous candidate triggers exactly one ask, and is never asked again after resolution
- [ ] Nothing is trashed without an explicit approval step
- [ ] `trashed_log` contains one entry per message actually trashed, with sender/subject/message ID/timestamp
- [ ] Re-running immediately after a batch approval does not re-present already-trashed messages
- [ ] A simulated crash mid-write does not corrupt `data/store.json` (atomic-replace verified)

---

## 10. Open Items / Risks

| # | Item | Status |
|---|---|---|
| 1 | Weekly unattended trigger mechanism (cron via Claude Code? Always-on host required) not yet chosen. | Open |
| 2 | Section 6.2 signal detection is LLM-judgment based; not yet a codified scoring function. Fine for MVP, revisit before Phase 2. | Open |
| 3 | Performance/cost budget (API calls per run, LLM classification cost per candidate) not yet specified. | Open |
| 4 | Full audit logging (every candidate, classification, signals) was deliberately dropped in 1.1.0 for personal-scale use. **Must be reinstated** before this pattern is offered to any client through Pete's MSP — a client will reasonably expect a defensible record of what an agent did to their inbox and why. | Deferred, revisit before client use |
| 5 | Multi-tenant generalization (M365/Graph, per-client sender stores) intentionally deferred — do not build for it prematurely. | Deferred by design |
| 6 | Production-facing UI is undecided and deliberately deferred. Options on the table: continued CLI, a native Windows GUI (Tkinter/Flet/PyQt), or a Flutter cross-platform client — the latter would require the backend to expose a local API layer (e.g. FastAPI) rather than being called in-process, a real architectural change, not just a UI skin. The backend (`agent/*.py`) is being built UI-agnostic on purpose so this decision can be made later, based on evidence from the working CLI, without having locked in assumptions prematurely. | Deferred by design |

---

## Appendix A — Whitelist Seed List (v1, 2026-08-24)
```
doris1122@icloud.com
doris_761122@hotmail.com
nb@marinasailing.com
hansmollym@gmail.com
newsong@newsongworshipcenter.ccsend.com
newsong@newsong.cc
```

## Appendix B — Reference Gmail Query
```
category:promotions older_than:14d
```