# API and MCP Capability Reconciler

## Identity

- Skill: `ct.skill.convergence.api-mcp-capability-reconciler.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: CrownThrive IO / PentaBind
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Reconcile declared APIs, MCP tools, scopes, side effects, versions, data classes, costs, rate limits, credential references, and evidence states across CrownThrive IO and connected systems.

## Strategic lanes

- CrownThrive IO
- APIs
- MCPs
- PentaBind
- ThriveBase

## Deterministic sequence

1. Read exact API/MCP manifests, provider documentation references, and current bound capability records.
2. Normalize operation IDs, versions, authentication model, scopes, data class, side effects, approval class, rate/budget limits, webhooks, and rollback/compensation behavior.
3. Compare declared capability with connector-visible capability and accepted provider evidence.
4. Classify absent, stale, undocumented, overbroad, under-scoped, read-only, write-candidate, or write-verified operations.
5. Generate machine-readable registry deltas and consumer-safe tool descriptions.
6. Route binding work to PentaBind and evidence gaps to the cross-provider readback skill.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No endpoint, scope, provider state, or write authority may be invented.
- No credential values in manifests or receipts.
- No provider-wide certification inferred from one operation.
- No destructive or financial write execution.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- capability registry;
- scope matrix;
- tool-description delta;
- binding handoff;
- evidence gap register;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
