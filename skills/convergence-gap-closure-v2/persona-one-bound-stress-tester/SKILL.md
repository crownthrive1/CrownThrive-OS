# Persona One-Bound Stress Tester

## Identity

- Skill: `ct.skill.convergence.persona-one-bound-stress-tester.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaPersonas / PentaTest
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Exercise a persona’s declared functionality, authority boundaries, edge cases, code examples, escalation rules, transport behavior, and failure handling in one comprehensive bounded test bundle.

## Strategic lanes

- Penta Personas
- PentaTest
- Email
- PentaComms

## Deterministic sequence

1. Resolve persona identity, source version, capability contract, authority ceiling, sender/transport, audience, and prohibited decisions.
2. Generate representative examples for every declared capability and every material denial boundary.
3. Test malformed input, prompt injection, secret requests, authority escalation, duplicate work, provider failure, timeout, and after-hours/identity rules where applicable.
4. Validate HTML and plain-text output, links, examples, disclosures, and escalation labels.
5. Produce one human-readable test email candidate plus machine-readable results.
6. Require provider test-send readback before calling transport functionality verified.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No real consequential decision or live transaction.
- No secret disclosure or prompt extraction.
- No unapproved external recipient.
- No persona self-expansion beyond its registered contract.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- one-bound test bundle;
- coverage matrix;
- email candidate;
- machine receipt;
- defect list;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
