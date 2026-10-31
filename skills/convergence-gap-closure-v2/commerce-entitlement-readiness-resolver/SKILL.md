# Commerce Entitlement Readiness Resolver

## Identity

- Skill: `ct.skill.convergence.commerce-entitlement-readiness-resolver.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaGreen / CHLOM
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Resolve the exact rights, price, tax-evidence status, fulfillment, entitlement, destination, provider, support, refund/dispute, and readback requirements that must converge before a CrownThrive offer is activated.

## Strategic lanes

- PentaGreen
- Go Flipbooks
- Virality Music
- KJV Visualized
- PentaAds
- Services

## Deterministic sequence

1. Resolve exact asset/product/offer, edition/version, owner, rights packet, license type, audience, territory, channel, and intended use.
2. Resolve deterministic or approved price basis, currency, discount/promotion rules, fee splits, commission rules, and tax evidence status.
3. Resolve fulfillment artifact, delivery method, download/access limits, expiry, account/library destination, support, refund/dispute, and recovery behavior.
4. Resolve payment, entitlement, fulfillment, notification, analytics, and archive providers with exact operation-level evidence requirements.
5. Classify ready_candidate, rights_hold, economic_hold, tax_evidence_hold, fulfillment_hold, entitlement_hold, provider_hold, or readback_hold.
6. Route only fully eligible candidates to PentaGreen for separately authorized activation.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No tax/legal conclusion, rights grant, price activation, checkout activation, payment, entitlement issue, or fulfillment.
- No blanket 'digital items are tax-free' assumption.
- No fake provider/readback evidence.
- No sale approval inferred from product existence.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- offer readiness matrix;
- exact gate list;
- provider operation map;
- fulfillment/entitlement contract;
- PentaGreen handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
