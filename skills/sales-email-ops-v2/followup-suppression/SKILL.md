---
name: "CrownThrive Follow-Up, Suppression & Opt-Out"
skill_id: "ct.skill.sales.followup-suppression.v2"
version: "2.0.0"
release_state: "CONTROLLED_TEST"
parent_agent: "ct.chlom.agent.sales-enablement"
agent_id: "ct.chlom.agent.sales-followup-suppression"
autonomy_class: "A2"
authority_ceiling: "D1"
visibility: "public-safe contract"
---

# CrownThrive Follow-Up, Suppression & Opt-Out

## Purpose

Manage bounded follow-up timing, stop conditions, suppression, opt-outs, bounces, wrong-person notices, complaint holds, and duplicate prevention across sales sequences.

## Invoke when

- a follow-up becomes due
- a reply arrives
- an opt-out is detected
- a bounce or complaint arrives
- a profile is claimed or a deal is won/lost

## Required inputs

- Current sequence state and last-contact time.
- Suppression and risk state.
- Reply/claim/conversion status.
- Governed follow-up cadence.

## Operating contract

Follow-up exists to resolve uncertainty, not to overwhelm recipients. Every sequence must have a fixed maximum touch count and explicit stop events. A reply suspends the cold cadence until the response is classified.

### Allowed

- schedule bounded touches
- stop active sequences
- write suppression state
- apply follow-up tags
- reconcile duplicates
- mark won, lost, claimed, or wrong-person states

### Stop / escalate

- never ignore opt-out or unsubscribe language
- never reset cadence to evade limits
- never contact suppressed addresses
- never restart after a complaint or legal hold without human authorization
- stop on hard bounce, wrong person, reply, claim completion, risk hold, or conversion

## Output contract

Record sequence ID, touch number, due date/window, stop reason, suppression source, provider state, and next allowed action.

## Verification

Suppression must be checked immediately before every send, not only when the sequence is first created.