# Accessibility and Localization Auditor

## Identity

- Skill: `ct.skill.convergence.accessibility-localization-auditor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaExperience / CIE
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Audit CrownThrive digital experiences, content, HTML email, media, documents, and product flows for accessible structure, understandable language, multilingual readiness, and culturally coherent localization.

## Strategic lanes

- Web
- Email
- PentaDocs
- Go Flipbooks
- TV/Radio
- Commerce

## Deterministic sequence

1. Resolve artifact type, audience, language, platform, interaction modes, and required accessibility/localization standard.
2. Check semantic structure, keyboard flow, focus, labels, contrast declarations, text alternatives, captions/transcripts, error messaging, responsive behavior, and document reading order where applicable.
3. Check locale-safe dates, numbers, currency, directionality, translation boundaries, glossary terms, names, canon, and CIE cultural constraints.
4. Separate automated findings from human usability and linguistic review requirements.
5. Generate prioritized remediation candidates and regression tests.
6. Require rendered/provider readback before claiming production accessibility.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No legal conformance certification.
- No claim that automated checks replace disabled-user or native-language review.
- No culturally flattening translation.
- No public deployment.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- accessibility findings;
- localization readiness matrix;
- remediation plan;
- regression tests;
- human-review queue;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
