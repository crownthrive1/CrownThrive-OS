# Content Publication Convergence Orchestrator

## Identity

- Skill: `ct.skill.convergence.content-publication-convergence-orchestrator.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaMedia / PentaPublish
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Converge approved content, metadata, rights, destination, schedule, edition/archive state, and provider readback across CrownThrive websites, media shelves, radio, TV, newsletters, and social distribution.

## Strategic lanes

- CrownPulse
- Melanated Voices
- Melanated TV
- Locticians TV
- Backroad FM
- PentaDocs

## Deterministic sequence

1. Resolve exact content/edition identity, source master, version, audience, brand/corridor, rights, embargo, metadata, and destination.
2. Validate publish eligibility through CIE, CHLOM, privacy, platform, and brand rules.
3. Generate channel-specific projections while preserving a common canonical subject.
4. Plan current-day story/index/edition/archive convergence and deduplicate retries through idempotency keys.
5. Route authorized provider writes through registered adapters.
6. Reconcile URL/feed/media/provider readback and archive/supersession state.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No publication without exact rights and destination authority.
- No fabricated current-day edition or provider receipt.
- No silent replacement of accepted content or editions.
- No cross-audience leakage of restricted content.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- publication plan;
- channel projections;
- idempotency map;
- provider handoff;
- readback/edition receipt;
- archive delta;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
