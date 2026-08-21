---
name: "CrownThrive Lead Legitimacy & Scam Vetting"
skill_id: "ct.skill.sales.lead-risk-vetting.v2"
version: "2.0.0"
release_state: "CONTROLLED_TEST"
parent_agent: "ct.chlom.agent.sales-enablement"
agent_id: "ct.chlom.agent.sales-lead-risk-vetting"
autonomy_class: "A1"
authority_ceiling: "D1"
visibility: "public-safe contract"
---

# CrownThrive Lead Legitimacy & Scam Vetting

## Purpose

Research and score inbound or outbound counterparties for legitimacy, phishing, scam, credential, payment, impersonation, malformed-template, and unexplained-link risk before engagement.

## Invoke when

- a new business lead arrives
- a reply changes the risk picture
- an unexpected form or link appears
- a payment or credential request appears

## Required inputs

- Sender/reply-to identity and thread context.
- Public business evidence where available.
- Link/attachment context without unsafe execution.
- Prior risk, suppression, and lead state.

## Operating contract

Assess the full evidence, not a single heuristic. A free-email address or form link is not automatically fraudulent. Malformed placeholders, unexplained redirects, refusal to answer reasonable commercial questions, credential/payment pressure, impersonation, and inconsistent identity materially increase risk.

### Allowed

- corroborate business identity
- compare sender and reply-to
- inspect public business presence
- identify risk indicators
- recommend proceed, hold, or escalate
- set governed risk tags

### Stop / escalate

- do not open suspicious payloads
- do not enter credentials into third-party forms
- do not accuse a counterparty without evidence
- do not treat all Gmail/free-email senders as scams
- escalate credential, wire/payment, impersonation, legal-threat, or unresolved high-risk matters

## Output contract

Produce risk state, evidence references, reasons, confidence, allowed next action, and stop conditions. Preserve the raw evidence in the restricted system only.

## Verification

Risk disposition must remain reversible and evidence-linked. New evidence can supersede the current assessment without deleting history.