# Artifact Custody Binder

## Identity

- Skill: `ct.skill.convergence.artifact-custody-binder.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaPreserve / PentaGeneration
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Package durable CrownThrive artifacts, hashes, manifests, source references, rights/provenance notes, and successor relationships into governed Drive custody and bind them back to canonical ledgers.

## Strategic lanes

- Google Drive
- CHLOM
- DAIL
- PentaGeneration
- CrownThrive OS

## Deterministic sequence

1. Inventory every generated or materially revised artifact in scope.
2. Classify public-safe, internal-governed, restricted, provider-origin, and historical custody boundaries.
3. Generate a deterministic manifest with path, media type, size, SHA-256, stable subject, version, source revision, and relationship edges.
4. Create a preservation package without embedding credentials or restricted evidence.
5. Save source-readable files and the package into the governed Drive destination.
6. Read back Drive identities and bind direct links, hashes, and package status into affected ledgers.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No plaintext secret, private key, credential, or restricted customer data in public packages.
- No package upload claimed complete without Drive readback.
- No overwrite of prior accepted package versions.
- No rights conclusion from possession alone.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- custody manifest;
- artifact package;
- SHA-256 inventory;
- Drive receipt;
- ledger binding map;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
