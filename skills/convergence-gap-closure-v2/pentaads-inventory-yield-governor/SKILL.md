# PentaAds Inventory and Yield Governor

## Identity

- Skill: `ct.skill.convergence.pentaads-inventory-yield-governor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaAds / AdLuxe Network
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Normalize CrownThrive advertising inventory, placement classes, sponsored disclosures, house-fill behavior, pricing basis, campaign eligibility, and yield evidence across AdLuxe-powered surfaces.

## Strategic lanes

- PentaAds
- AdLuxe Network
- All CrownThrive media/brand surfaces

## Deterministic sequence

1. Inventory every placement, brand/site, device class, format, audience boundary, house-fill asset, and provider/runtime identity.
2. Assign stable zone IDs, disclosure rules, default house/sponsored creative behavior, and non-personal fallback.
3. Evaluate price basis using recorded inventory and market research evidence without fabricating demand.
4. Validate campaign rights, brand safety, targeting consent, pacing, delivery, reporting, billing, payout, and internal no-revenue-split rules where applicable.
5. Emit publisher, advertiser, campaign, placement, and reporting manifests.
6. Require provider delivery/readback and transaction evidence before revenue or production claims.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No ad spend, billing, payout, settlement, or advertiser commitment.
- No sensitive or prohibited targeting.
- No fake impressions, clicks, conversions, users, or revenue.
- No provider-wide activation claim from source readiness.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- inventory registry;
- zone manifest;
- pricing evidence record;
- house-fill pack;
- campaign eligibility matrix;
- yield receipt;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
