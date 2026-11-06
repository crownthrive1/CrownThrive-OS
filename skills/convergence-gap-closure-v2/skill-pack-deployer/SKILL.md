# Skill Pack Deployer

## Identity

- Skill: `ct.skill.convergence.skill-pack-deployer.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaDeploy / PentaFactory
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Build, validate, package, branch, and prepare governed source deployment of CrownThrive skill families while preserving version, rollback, evidence, and review boundaries.

## Strategic lanes

- GitHub
- PentaFactory
- PentaDeploy
- CrownThrive OS

## Deterministic sequence

1. Resolve the accepted base revision, unique skill namespace, target registry, and required validators.
2. Validate every SKILL.md contract, manifest entry, schema, runtime, test, and public/private classification.
3. Build a deterministic source package and hash inventory.
4. Create an isolated source branch and coherent commit.
5. Open a reviewed pull request with exact tests, changed states, unresolved gates, rollback, and custody references.
6. After authorized merge, require exact-head and downstream readback before claiming active deployment.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No direct-main mutation for material changes.
- No self-approval or automatic D3 merge.
- No production claim from branch, commit, PR, or CI alone.
- No secret material in the source pack.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- validated source pack;
- branch/commit receipt;
- pull request;
- test record;
- rollback reference;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
