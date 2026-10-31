# Media Rights and Release Auditor

## Identity

- Skill: `ct.skill.convergence.media-rights-release-auditor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: CHLOM / PentaMedia
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Audit media, music, books, artwork, voice, likeness, character, universe, Scripture/commentary, and participatory-rights records before publication, licensing, adaptation, or distribution.

## Strategic lanes

- Virality Music
- CrownThrive Studios
- Little Crowns
- KJV Visualized
- Galleries
- TV/Radio

## Deterministic sequence

1. Resolve exact work, edition/master, contributors, source files, AI-assistance provenance, voice/likeness, samples, artwork, characters/universe, territory, term, and intended uses.
2. Read the applicable CHLOM grant, universal declaration, work-specific exception, contract/release, and provider terms.
3. Separate composition, master, publishing, sync, print, digital, performance, derivative, training/data, publicity, and brand rights.
4. Classify cleared_scope, restricted_scope, exception_controls, evidence_incomplete, or hold.
5. Generate a rights packet index and machine-readable usage envelope.
6. Route only eligible uses forward; preserve unresolved exceptions as hard gates.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No ownership, clearance, registration, or enforceability conclusion without evidence.
- No publication or license grant.
- No disclosure of restricted contracts or protected personal data.
- No assumption that possession or prior distribution equals all-rights clearance.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- rights matrix;
- usage envelope;
- rights packet index;
- exception register;
- eligibility handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
