# Data Consent and Retention Governor

## Identity

- Skill: `ct.skill.convergence.data-consent-retention-governor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: CHLOM / PentaPrivacy
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Map personal, community, creator, customer, audience, telemetry, and model-use data to exact purpose, consent/authority, retention, deletion, export, sharing, and sensitivity rules.

## Strategic lanes

- ThriveBase
- CrownLytics
- CrownPulse
- Communities
- Commerce
- AI systems

## Deterministic sequence

1. Inventory data fields, source, subject class, environment, purpose, processor/provider, consumers, and destinations.
2. Resolve the applicable consent, contract, legitimate operational authority, privacy notice, CHLOM rule, and special audience constraints.
3. Define minimum collection, retention, archival, deletion/tombstone, export, correction, and incident behavior.
4. Detect purpose drift, over-retention, consent mismatch, public/private leakage, model-training ambiguity, and orphaned exports.
5. Generate policy and schema deltas without deleting live data.
6. Route authorized remediation through separate bounded workflows with readback.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No legal-compliance attestation.
- No destructive deletion or export.
- No health, child, identity, financial, or other sensitive-data publication.
- No model-training permission inferred from access.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- data inventory;
- purpose/consent matrix;
- retention schedule candidate;
- privacy gap register;
- remediation handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
