# Agent Spec: Promo Email Triage (MVP)

Version: 0.1.0
Status: Initial informal draft, not version controlled at time of writing

## Purpose
Scan Gmail inbox for promotional/marketing email, present a reviewable
summary before deletion, respect a fixed whitelist of protected senders.

## Rules
- Candidate = category:promotions AND older than 14 days
- Whitelist = fixed list, provided once, excluded entirely
- Action on approval = move to Trash (not permanent delete)
- Trigger = manual first, then weekly

## Whitelist (v1)
doris1122@icloud.com
doris_761122@hotmail.com
nb@marinasailing.com
hansmollym@gmail.com
newsong@newsongworshipcenter.ccsend.com
newsong@newsong.cc

## Known limitations
- No audit trail
- Whitelist can only exclude, has no way to learn from ambiguous senders
- Not under version control
