# Agent Specification: Promo Email Triage

| | |
|---|---|
| **Document ID** | EXEM-AGT-001 |
| **Version** | 1.0.0 |
| **Status** | Draft — Approved for prototyping, not yet approved for scheduled/unattended operation |
| **Owner** | Bobby Taylor, Exem Concepts |
| **Governing framework** | AI Agent Development & Learning Plan (AI_Agent_Development.docx) |
| **Target environment (this version)** | Personal Gmail (admin rights) — MVP only |
| **Future environment (out of scope, this version)** | Microsoft 365 / Graph API, multi-tenant, for Pete's MSP clients |

---

## 0. Version History

| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1.0 | 2026-08-24 | Bobby Taylor + Claude | Initial informal draft. Static whitelist, no audit trail, no persistence layer. Superseded. |
| 1.0.0 | 2026-08-24 | Bobby Taylor + Claude | Full SME rewrite. Added: persistent audit log (FR-6), living sender-decision store replacing static whitelist (FR-5), SQLite data model, ambiguous-candidate escalation workflow, non-functional requirements, acceptance criteria, git version control for spec + future code. |

Change requests against this spec should be made as pull requests against `docs/SPEC.md` with an updated Version History row. Do not silently edit prior sections without a version bump.

---

## 1. Purpose & Business Context

Bobby (Exem Concepts, 1099 contractor to Pete's MSP) needs a working reference pattern for an email-triage agent: scan → classify → hold for human review → act. This is the first agent built under the governing Learning Plan and is explicitly intended to generalize: the classification and review-gate pattern developed here is the template for future client-facing agents in Pete's tiered AI service offering (M365/Graph API target, out of scope for this version).

**Primary use case:** reduce inbox clutter from bulk marketing email without risking loss of anything from a real correspondent.

**Secondary use case (why this spec is written this carefully):** serve as a demonstrable, defensible pattern — audit trail included — that can be shown to a client as "here is how the agent decides, and here is proof of what it did."

---

## 2. Scope

### 2.1 In scope
- Gmail inbox, one personal account, owner has full admin rights
- Detection of bulk/promotional email using Gmail's `category:promotions` label as a first-pass filter, refined by content-signal classification (Section 6)
- Human-reviewed deletion (move to Trash, never permanent delete)
- Persistent sender-decision memory and run audit log (local SQLite)
- Manual trigger (Phase 1) and unattended weekly trigger (Phase 2)

### 2.2 Out of scope (this version)
- Microsoft 365 / Outlook / Graph API — requires separate M365 Developer Program sandbox effort
- Multi-tenant / multi-client operation
- Any label other than Promotions (e.g., Social, Updates, Forums)
- Folders/labels other than Inbox
- Permanent deletion (explicitly disallowed, see Section 8.2)

---

## 3. Definitions

| Term | Definition |
|---|---|
| **Candidate** | A message that has passed the initial `category:promotions` + age filter and is under consideration for deletion. |
| **Bulk marketing** | Automated, templated mail sent to many recipients — regardless of whether it reads as personally addressed. Confirmed via structural signals (Section 6.2), not tone. |
| **Sender decision store** | Persistent table (`sender_decisions`) recording whether a sender is always-keep, always-candidate, or undecided. |
| **Ambiguous candidate** | A message matching `category:promotions` + age, with no confirmed sender decision, whose content signals are mixed or inconclusive. |
| **Run** | One execution of the agent, manual or scheduled, logged as a row in `runs`. |

---

## 4. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Agent scans Gmail Inbox for messages matching `category:promotions` AND older than a configurable age threshold (default 14 days). | Must |
| FR-2 | Agent excludes any message whose sender is in `sender_decisions` with `decision = 'whitelist'`. | Must |
| FR-3 | Agent applies content-signal classification (Section 6) to every remaining candidate to confirm bulk-marketing status. | Must |
| FR-4 | Confirmed bulk-marketing candidates are added to a review list; nothing is deleted without explicit human approval of that run's list. | Must |
| FR-5 | Candidates classified as **ambiguous** are NOT auto-included in the delete batch. Agent asks the user once per unresolved sender; the answer is written to `sender_decisions` (whitelist or blacklist) so future runs never ask again for that sender. | Must |
| FR-6 | Every candidate evaluated in a run — regardless of outcome — is written to `audit_log` with its classification, the signals that drove the decision, and the action taken. | Must |
| FR-7 | On approval, agent moves only the approved messages to Gmail Trash (`trashMessage`/`trashThread`). Permanent delete is never invoked. | Must |
| FR-8 | Agent supports manual, on-demand triggering. | Must |
| FR-9 | Agent supports unattended weekly triggering, but still halts at the human-review gate (FR-4) — no auto-delete without approval, even when scheduled. | Should (Phase 2) |
| FR-10 | Agent reports run summary (scanned / trashed / held / pending-ask counts) at the end of each run. | Should |

---

## 5. Sender Decision Store

Replaces the "static whitelist" concept from v0.1.0. See `schema/schema.sql`, table `sender_decisions`.

### 5.1 States
- **whitelist** — never a candidate, regardless of category/content
- **blacklist** — confirmed bulk marketing; future messages from this sender skip content-classification and go straight to the candidate list
- **pending** — seen but not yet resolved; triggers the ask-once flow (FR-5)

### 5.2 Seeding
Version 1 seed list (whitelist, provided by Bobby 2026-08-24) — see Appendix A. Loaded once at first run; not re-requested on subsequent runs.

### 5.3 Growth
Every ambiguous candidate resolved by the user (FR-5) is written back as `whitelist` or `blacklist` with `source = 'user_confirmed'`. Over time this store should require decreasing manual input.

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

*(Open item, Section 10: signal detection is currently manual/LLM-judgment based, not yet codified into a deterministic scoring function. Acceptable for prototyping; should be tightened before Phase 2 / unattended operation.)*

---

## 7. Workflow

1. **Scan** — query per Section 6.1
2. **Pre-filter** — drop anything with `sender_decisions.decision = 'whitelist'`
3. **Fast-path** — anything with `sender_decisions.decision = 'blacklist'` skips straight to candidate list (classification already resolved for this sender)
4. **Classify** — apply Section 6.2 to everything else
5. **Resolve ambiguous** — for each ambiguous sender not already `pending` in the store, ask the user once; persist the answer (FR-5)
6. **Present** — review list of confirmed bulk-marketing candidates, grouped by sender, with subject/date
7. **Approve** — user confirms all, some, or none
8. **Act** — move approved messages to Trash only
9. **Log** — write every evaluated candidate (all outcomes) to `audit_log`; write run summary to `runs`

---

## 8. Non-Functional Requirements & Guardrails

### 8.1 Reliability
- Idempotent re-runs: a message already logged as `trashed` in `audit_log` for a prior run must not be re-presented as a candidate.
- Partial failure: if the Gmail API fails mid-batch, already-approved-and-trashed messages remain trashed; unprocessed candidates are simply left for the next run. No partial/inconsistent state should block future runs.

### 8.2 Safety
- **Never** permanent-delete. Trash only.
- **Never** auto-approve a delete batch, in manual or scheduled mode.
- **Never** silently skip the ask-once flow for a genuinely new ambiguous sender.

### 8.3 Data handling
- `sender_decisions` and `audit_log` are local to Bobby's environment (SQLite file). No transmission of inbox content to third parties beyond what Gmail's own API + the LLM classification step already requires.

### 8.4 Performance / cost
- Not yet specified. Open item (Section 10).

---

## 9. Acceptance Criteria (for MVP sign-off)

- [ ] A manual run correctly excludes all Appendix A whitelist senders
- [ ] A manual run correctly identifies at least one bulk-marketing message via content signals, not category alone
- [ ] An ambiguous candidate triggers exactly one ask, and is never asked again after resolution
- [ ] Nothing is trashed without an explicit approval step
- [ ] `audit_log` contains one row per evaluated candidate, per run, with classification and signals populated
- [ ] Re-running immediately after a batch approval does not re-present already-trashed messages

---

## 10. Open Items / Risks

| # | Item | Status |
|---|---|---|
| 1 | Weekly unattended trigger mechanism (cron via Claude Code? Always-on host required) not yet chosen. | Open |
| 2 | Section 6.2 signal detection is LLM-judgment based; not yet a codified scoring function. Fine for MVP, revisit before Phase 2. | Open |
| 3 | Performance/cost budget (API calls per run, LLM classification cost per candidate) not yet specified. | Open |
| 4 | No retention/purge policy yet defined for `audit_log` growth over time. | Open |
| 5 | Multi-tenant generalization (M365/Graph, per-client sender stores) intentionally deferred — do not build for it prematurely. | Deferred by design |

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
