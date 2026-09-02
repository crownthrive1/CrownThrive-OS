# ThrivePush Journey Orchestrator

## Identity

- Skill: `ct.skill.convergence.thrivepush-journey-orchestrator.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: ThrivePush / CrownLytics
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Design and reconcile consent-aware, brand-aligned multichannel notification journeys across push, email, in-app, SMS-capable providers, and ecosystem handoffs.

## Strategic lanes

- ThrivePush
- CrownLytics
- PentaComms
- All opted-in brands

## Deterministic sequence

1. Resolve journey, audience source, consent, purpose, brand/corridor, event trigger, frequency cap, quiet hours, suppression, and destination.
2. Generate channel-specific message candidates with CIE, accessibility, link, and disclosure constraints.
3. Validate deduplication, sequencing, retry, expiration, unsubscribe/suppression, and cross-brand limits.
4. Route only authorized provider operations through registered adapters.
5. Reconcile delivery, bounce/failure, click/conversion evidence, and suppression state.
6. Feed truthful aggregate outcomes to CrownLytics without fabricating impact.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No unsolicited messaging or consent manufacture.
- No live send by default.
- No sensitive targeting or cross-brand audience leakage.
- No fake delivery, engagement, conversion, or revenue.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- journey manifest;
- message candidates;
- consent/frequency matrix;
- provider handoff;
- delivery reconciliation;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
