# Deployment Binding Convergence Auditor

## Identity

- Skill: `ct.skill.convergence.deployment-binding-convergence-auditor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaDeploy / PentaBind
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Compare accepted source, deployment configuration, environment bindings, runtime identity, and provider readback to determine whether a CrownThrive component is merely built, deployed, write-verified, active, or still held.

## Strategic lanes

- Vercel
- Supabase/ThriveBase
- GitHub
- CrownThrive IO
- PentaDeploy

## Deterministic sequence

1. Resolve exact source SHA, artifact hash, deployment target, environment, stable component ID, and binding manifest.
2. Verify non-secret environment-variable references and runtime/provider identity.
3. Compare source artifact, provider deployment metadata, route health, and exact readback.
4. Classify built_undeployed, deployed_unreadback, deployed_mismatch, read_only_verified, write_verified_scope, active_scope, or hold.
5. Generate remediation and rollback/compensation handoffs.
6. Project only evidence-supported state into canonical records.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No deployment or provider write by default.
- No environment-secret disclosure.
- No PRODUCTION state from source/CI alone.
- No cross-environment promotion.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- convergence matrix;
- deployment classification;
- binding mismatch report;
- readback receipt;
- remediation handoff;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
