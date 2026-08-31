# Penta Assignment Review-Only Owner Routing v1

## Status

Candidate extension stacked on the canonical Penta Assignment owner-routing repair (#1899). Source/readiness only until governed exact-head gates, DAIL evidence, institutional projections and independent certification pass.

## Purpose

The assignment fabric must be able to hand exact evidence to canonical reviewer systems without pretending that a reviewer is a project-management executor. This contract adds review-only Census handoff routes for the already-registered canonical identities `PentaSecurity` (`penta.security`), `PentaTime` (`penta.time`) and `PentaDemocracy` (`penta.democracy`).

It does not create new Pentas, new authority, a new scheduler, an OS20 execution route, provider-write power, credential authority, money movement, sovereign-vote authority, D3 execution, release authority or certification authority.

## Relationship to #1899

#1899 remains the base owner-routing repair. It establishes the explicit owner-route registry, canonical executable routes, HOLD semantics for unknown routes and real dispatch readback. This candidate does not duplicate or replace that implementation; it adds a bounded review-only route class using the existing `CENSUS_HANDOFF` mechanism.

The review-only route registry metadata is authoritative for the distinction:

- `route_mode=review_only`
- `pm_execution_eligible=false`
- `provider_write=false`
- `credential_change=false`
- `money_movement=false`
- `d3_execution=false`
- `authority_expansion=false`
- `authority_effect=none`

A database trigger rejects attempts to mutate a review-only route into `OS20_TASK` or to smuggle execution/authority flags into its metadata.

## Assignment semantics

A review-only handoff means: deliver the assignment's exact subject, exact artifact/head identity, acceptance criteria and evidence package to the registered reviewer. Completion of the handoff is evidence that the reviewer route was reached; it is not by itself a PentaSecurity PASS, CHLOM authority grant, sovereign vote, certification, deployment or release.

Security decisions, CHLOM rights/authority decisions, applicable CIE decisions and independent PentaCertifier dispositions remain separate governed evidence objects and must be read back through their canonical runtimes.

## CHLOM + DAIL boundary

Assignment routing is an interop/orchestration concern. CHLOM remains the canonical rights/authority/governance protocol. PentaCHLOM may translate and bind the review evidence, but it does not inherit CHLOM authority.

Material lifecycle evidence must preserve the canonical semantic lanes:

1. DAIL-EVIDENCE — exact observed source, provider/runtime state and provenance.
2. DAIL-DECISION — bounded reviewer/security/rights/cultural/certifier decisions.
3. DAIL-EXECUTION — actual governed mutation/release/readback receipts.

The three DAIL lanes are not token classes. No CHLOM token semantics are inferred by this routing contract.

## Threat model

This contract specifically blocks:

- reviewer-to-executor privilege escalation;
- OS20 execution through a review-only route;
- metadata-based PM execution eligibility escalation;
- provider-write, credential, money, D3 or authority-expansion leakage;
- unknown reviewer names silently becoming executable routes;
- treating a completed transport handoff as independent certification.

Unknown/unregistered owner identities continue to fail closed under #1899.

## Acceptance

The transactional test must prove that the four existing executable routes remain unchanged, all three reviewer routes are canonical review-only Census handoffs, OS20 escalation and metadata authority escalation are rejected, a synthetic assignment reaches all three review handoffs, and zero OS20 execution tasks are created. The transaction must roll back all canary state.

## Rollback

Before production apply: close/supersede this candidate with #1899/current main unchanged.

After governed apply: deactivate/remove only the three additive review-only registry rows and the review-only guard through a governed forward migration, then read back the original four-route registry. Historical assignment/DAIL evidence is never deleted or rewritten.

## Release boundary

Required order remains `Build -> security scanning -> threat model -> tests -> PentaSecurity -> CHLOM rights/authority -> applicable CIE -> independent PentaCertifier -> release -> exact readback`.

Originators, builders, PentaSecurity, PentaCHLOM and CHLOM builders may not self-certify. D3/human-reserved authority remains unchanged.
