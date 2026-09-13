# Cross-Provider Readback Reconciler

## Identity

- Skill: `ct.skill.convergence.cross-provider-readback-reconciler.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaVerify / PentaAudit
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Reconcile operation-level provider observations into exact-subject evidence without allowing request dispatch, HTTP success, or a provider snapshot to become broader institutional certification.

## Strategic lanes

- Providers
- DAIL
- PentaAudit
- PentaCertify
- CrownThrive OS

## Deterministic sequence

1. Resolve exact subject, source SHA, environment, provider, operation, requested state, authority, and idempotency identity.
2. Collect the least-sensitive provider readback available for the exact operation.
3. Compare requested and observed normalized state, including timing, duplication, partial failure, and rollback/compensation state.
4. Classify verified_match, verified_mismatch, stale_readback, no_readback, ambiguous_effect, or provider_denial.
5. Bind sanitized evidence to DAIL/PentaAudit-compatible receipts.
6. Return the narrowest supported claim and explicit remaining institutional gates.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No provider mutation.
- No broad provider certification.
- No rights, settlement, entitlement, legal, tax, or D3 conclusion from technical readback.
- No sensitive raw log export.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- normalized readback;
- effect comparison;
- evidence receipt;
- narrow claim;
- remaining gate list;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
