# Brand Corridor and Lane Validator

## Identity

- Skill: `ct.skill.convergence.brand-corridor-lane-validator.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: CIE / Convergent Ecosystem
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Validate that each CrownThrive brand, platform, product, asset, persona, and distribution surface has a coherent corridor/lane role, Cultural Imprint alignment, flywheel relationship, and non-conflicting canonical identity.

## Strategic lanes

- All CrownThrive brands
- CIE
- MM Suites
- Thrive Flywheel

## Deterministic sequence

1. Resolve the canonical brand/platform identity, aliases, parent, corridor, lane, audience, cultural profile, and commercial role.
2. Read current CIE, Convergent Ecosystem, MM Suites, and Thrive Flywheel references.
3. Detect orphaned brands, duplicated identities, conflicting lane claims, missing handoffs, audience mismatch, and public-copy drift.
4. Map inbound and outbound value flows across creation, community, commerce, media, education, rewards, and reinvestment.
5. Emit correction candidates and relationship edges without changing brand canon automatically.
6. Require founder/CIE authority for material identity, canon, or cultural-position changes.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No brand rename, canon rewrite, cultural claim, or trademark/legal conclusion.
- No invented audience, traction, partnership, or economic claim.
- No automatic public copy deployment.
- No collapse of distinct brands merely because they share infrastructure.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- corridor map;
- lane validation;
- flywheel edge map;
- drift register;
- correction candidates;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
