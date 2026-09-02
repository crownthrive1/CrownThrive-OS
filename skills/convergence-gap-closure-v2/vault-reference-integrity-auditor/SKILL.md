# Vault Reference Integrity Auditor

## Identity

- Skill: `ct.skill.convergence.vault-reference-integrity-auditor.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaVault / PentaSecurity
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Verify that CrownThrive systems reference governed secret identifiers correctly, detect plaintext or stale bindings, and certify only non-secret metadata integrity.

## Strategic lanes

- ThriveBase Vault
- PentaVault
- PentaBind
- Security

## Deterministic sequence

1. Scan scoped manifests and configuration for secret-reference fields and forbidden plaintext patterns.
2. Validate reference syntax, environment separation, owner, consumer, provider, rotation/expiry metadata, and least-privilege declarations.
3. Compare declared references with authorized non-secret Vault metadata when available.
4. Detect orphaned, duplicated, unrestricted, cross-environment, or consumer-mismatched references.
5. Redact all secret-like values from evidence and generate remediation deltas.
6. Emit PASS only for reference integrity, never for secret validity or provider authorization.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- Never read, print, persist, echo, or transmit secret values.
- No rotation, revocation, or provider permission change.
- No claim that a syntactically valid reference contains a valid secret.
- No production certification.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- reference inventory;
- plaintext finding register;
- binding mismatch report;
- sanitized remediation plan;
- audit receipt;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
