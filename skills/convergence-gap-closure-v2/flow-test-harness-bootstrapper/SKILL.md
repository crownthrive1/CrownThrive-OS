# Flow Test Harness Bootstrapper

## Identity

- Skill: `ct.skill.convergence.flow-test-harness-bootstrapper.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaTest / PentaFactory
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Generate deterministic end-to-end test harness candidates for CrownThrive workflows that lack an executable flow command, fixture set, provider mock, failure matrix, or evidence receipt.

## Strategic lanes

- All executable workflows
- PentaTest
- PentaFactory
- CI

## Deterministic sequence

1. Read the current workflow contract, existing tests, schemas, provider boundaries, and known failure modes.
2. Identify uncovered happy path, denial, timeout, duplicate, partial failure, retry, rollback, authorization, and readback cases.
3. Generate standard-library or repository-native test fixtures without live credentials.
4. Create a stable command and machine-readable receipt format.
5. Run local static/unit validation where available.
6. Record provider-only canaries as separate gated tests rather than simulating production success.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No live destructive, financial, rights, personal-data, or production provider testing.
- No fake provider evidence.
- No weakening assertions to force a pass.
- No replacement of existing valid tests without explicit scope.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- test-gap matrix;
- harness candidate;
- fixtures;
- failure matrix;
- local test receipt;
- provider-canary handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
