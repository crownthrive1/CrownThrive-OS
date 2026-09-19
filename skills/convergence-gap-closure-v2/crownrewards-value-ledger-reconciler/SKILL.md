# CrownRewards Value Ledger Reconciler

## Identity

- Skill: `ct.skill.convergence.crownrewards-value-ledger-reconciler.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: CrownRewards / PentaGreen
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Reconcile closed-loop credits, rewards, promotional value, earning/burning events, expiration, reversals, liability classification, and entitlement evidence without treating credits as unrestricted money.

## Strategic lanes

- CrownRewards
- Credit-only stores
- Virality Music
- KJV Visualized
- PentaGreen

## Deterministic sequence

1. Resolve account, program/version, event identity, earning source, offer, unit basis, expiry, restrictions, and provider/system evidence.
2. Validate event idempotency, balance continuity, promotional versus purchased units, reversals, refunds, and cross-brand redemption rules.
3. Compute deterministic ledger movement and resulting candidate balance.
4. Detect negative balance, duplicate event, orphaned entitlement, expired promotion, and migration drift.
5. Generate accounting/economic evidence candidates while preserving closed-loop restrictions.
6. Require authoritative ledger write/readback before active balance claims.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No money movement, cash-value claim, securities/stored-value legal classification, or tax conclusion.
- No balance mutation by this audit skill.
- No invented rewards or entitlements.
- No cross-customer data exposure.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- value-ledger reconciliation;
- balance candidate;
- event exception register;
- entitlement link map;
- write/readback handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
