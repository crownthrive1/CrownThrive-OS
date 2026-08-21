---
name: "CrownThrive Sales Continuity & Evidence"
skill_id: "ct.skill.sales.continuity.v2"
version: "2.0.0"
release_state: "CONTROLLED_TEST"
parent_agent: "ct.chlom.agent.sales-enablement"
agent_id: "ct.chlom.agent.sales-continuity"
autonomy_class: "A2"
authority_ceiling: "D1"
visibility: "public-safe contract"
---

# CrownThrive Sales Continuity & Evidence

## Purpose

Preserve sales, lead, outreach, risk, response, opt-out, and conversion continuity across mailbox tags, restricted CRM/email-vault records, Collab Portal project records, Google Drive operating references, and governed documentation.

## Invoke when

- a material sales event occurs
- lead status changes
- a risk decision changes
- outreach is sent or answered
- an opt-out or conversion occurs

## Required inputs

- Provider message/thread identifiers where available.
- Current CRM prospect/sequence state.
- Evidence classification and public/private boundary.
- Appropriate project/Drive/documentation destination.

## Operating contract

Continuity is append-oriented. Preserve the event and its evidence reference so later runs do not rediscover the same facts. Public documentation receives only public-safe summaries; restricted systems hold raw correspondence and private prospect data.

### Allowed

- append continuity records
- preserve provider message/thread IDs in restricted records
- link evidence references
- write public-safe documentation summaries
- route project copies when appropriate
- reconcile status across mailbox, CRM, Drive, Collab Portal, and documentation

### Stop / escalate

- do not publish restricted email bodies
- do not place secrets in public docs
- do not copy privileged legal, sensitive personal, credential, or restricted evidence into broad project records
- do not silently delete evidence

## Output contract

Record event type, actor/skill, source IDs, prior/current state, evidence reference, destinations reconciled, exceptions, and next-run baseline.

## Verification

A continuity write is complete only when the destination is read back or otherwise verified and the source remains linked without exposing restricted data.