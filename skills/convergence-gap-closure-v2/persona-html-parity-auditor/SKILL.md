# Persona HTML Parity Auditor

## Identity

- Skill: `ct.skill.convergence.persona-html-parity-auditor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaPersonas / PentaComms
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Audit persona email templates against the accepted Avery HTML standard while preserving each persona’s bounded identity, accessibility, responsive behavior, functional links, and production continuity.

## Strategic lanes

- Penta Personas
- Email
- PentaAds
- Avery baseline

## Deterministic sequence

1. Read the accepted Avery baseline without modifying it.
2. Inventory each persona template, sender identity, use cases, required modules, examples, and functional links.
3. Compare semantic HTML, responsive layout, accessibility, dark-mode resilience, plain-text fallback, tracking disclosures, and brand/CIE alignment.
4. Generate per-persona upgrade candidates and a parity scorecard.
5. Keep a persona in service until its replacement is validated; use a bounded maintenance window only for atomic swap.
6. Require test-send/readback evidence before activation.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- Never modify the Avery baseline unless separately authorized.
- No exposure of credentials, private prompts, protected personal data, or unrestricted capabilities.
- No production deactivation before a validated replacement is ready.
- No email send without authorized sender identity and transport.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- persona inventory;
- HTML parity scorecard;
- upgrade candidate;
- accessibility report;
- test-send plan;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
