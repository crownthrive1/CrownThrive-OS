# Skill Fleet Gap Analyzer

## Identity

- Skill: `ct.skill.convergence.skill-fleet-gap-analyzer.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: PentaDiscover / PentaFactory
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Compare the accepted CrownThrive OS skill estate, Drive manifests, affected provider capabilities, and current directives to identify true capability gaps without duplicating current or historical skills.

## Strategic lanes

- CrownThrive OS
- PentaFactory
- PentaDocs
- ThriveBase
- Google Drive

## Deterministic sequence

1. Read the exact accepted OS source revision and current skill registry.
2. Read current canonical Drive skill/asset manifests and preserve historical manifests as lineage.
3. Normalize skill names, stable IDs, versions, owners, lanes, authority ceilings, evidence requirements, and deployment states.
4. Classify each requested capability as existing_current, existing_partial, superseded_lineage, missing_implementation, missing_binding, missing_evidence, or provider/human_gate.
5. Reject proposed skills that materially duplicate an accepted capability unless a distinct versioned specialization is justified.
6. Emit a gap register, collision report, prioritized build cohort, and explicit unresolved gates.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No state promotion based on names, plans, or generated files.
- No deletion or silent replacement of historical skills.
- No provider write, merge, release, or D3 authority.
- No inference that an indexed skill is executable or production-certified.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- gap register;
- collision report;
- build cohort;
- supersession map;
- gate register;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
