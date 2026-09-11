# Go Flipbooks Commercial Packager

## Identity

- Skill: `ct.skill.convergence.go-flipbooks-commercial-packager.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaBooks / PentaGreen
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Package Go Flipbooks static-reader and Go Flipbooks PRO/provider-backed offers into deterministic, rights-aware, fulfillment-ready commercial candidates with clear product separation.

## Strategic lanes

- Go Flipbooks
- Go Flipbooks PRO
- CrownReader
- PentaGreen
- CHLOM

## Deterministic sequence

1. Classify each offer as Go Flipbooks static/CrownReader or Go Flipbooks PRO/FlipLink-backed.
2. Resolve source master, renderer/provider dependency, rights, license, price basis, tax treatment evidence, entitlement, fulfillment, destination, support, and telemetry requirements.
3. Generate SKU, offer manifest, product copy, delivery contract, license/CHLOM references, and provider adapter handoff.
4. Validate no physical-shipping promise for digital-only offers.
5. Route commercially eligible candidates to PentaGreen without activating checkout automatically.
6. Require checkout, entitlement, delivery, and provider readback before active/production claims.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No invented provider entitlement, price, tax conclusion, rights, or fulfillment proof.
- No confusion between CrownThrive product identity and third-party renderer/provider identity.
- No automatic public checkout activation.
- No replacement of accepted editions.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- commercial package;
- SKU/offer manifest;
- delivery contract;
- rights/economic gate matrix;
- PentaGreen handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
