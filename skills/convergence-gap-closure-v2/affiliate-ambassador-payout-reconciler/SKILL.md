# Affiliate and Ambassador Payout Reconciler

## Identity

- Skill: `ct.skill.convergence.affiliate-ambassador-payout-reconciler.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: Crown Affiliates / Crown Ambassadors / PentaGreen
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Reconcile referral identity, attribution, eligible sale, returns/refunds, commission rule, override, payout status, and evidence across Crown Affiliates, Crown Ambassadors, partner programs, and commerce providers.

## Strategic lanes

- Crown Affiliates
- Crown Ambassadors
- CrownFluence
- Partner Circle
- PentaGreen

## Deterministic sequence

1. Resolve program, participant, referral/campaign identity, governing terms/version, transaction, product, time window, and provider evidence.
2. Separate gross order, eligible net sale, tax, discounts, refunds, chargebacks, platform fees, commission base, rate, override, holdback, and payout.
3. Detect duplicate attribution, self-referral, stale cookies, cross-program collision, reversed transactions, and provider mismatch.
4. Compute a deterministic candidate statement without moving money.
5. Generate participant-safe and internal reconciliation views.
6. Require payout-provider readback and applicable approval before paid status.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No money movement, payout promise, contract modification, tax advice, or settlement conclusion.
- No fabricated sale or attribution.
- No exposure of unrelated customer/payment data.
- No self-approval.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- commission candidate;
- attribution reconciliation;
- exception register;
- participant statement;
- payout handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
