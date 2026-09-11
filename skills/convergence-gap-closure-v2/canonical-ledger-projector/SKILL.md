# Canonical Ledger Projector

## Identity

- Skill: `ct.skill.convergence.canonical-ledger-projector.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaReconcile / PentaDocs
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Project accepted, evidence-linked skill and artifact state into the affected CrownThrive master ledgers using additive, versioned records without letting a downstream ledger redefine OS truth.

## Strategic lanes

- Master IP & Asset Registry
- COS Census
- Operation C.L.E.A.N.
- Penta Activation Continuity

## Deterministic sequence

1. Resolve the exact canonical subject, stable ID, source revision, and affected ledger set.
2. Read the current ledger schema and locate the canonical row or append position.
3. Prepare an additive projection with lifecycle, evidence, custody, rights, deployment, rollback, and successor fields.
4. Use compare-and-append or explicitly scoped field updates; never rewrite unrelated rows.
5. Read back each written ledger surface and compare normalized values.
6. Emit a projection receipt for every ledger and an unresolved-delta record for any failed write/readback.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No ledger row may manufacture OS, provider, rights, financial, or D3 authority.
- No bulk overwrite of master registries.
- No silent mutation of historical snapshots.
- No PASS without destination readback.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- ledger projection plan;
- write receipt;
- readback receipt;
- unresolved delta;
- rollback reference;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
