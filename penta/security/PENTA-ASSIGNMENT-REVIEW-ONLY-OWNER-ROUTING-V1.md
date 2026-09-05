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

## Independent-certifier release-gate bridge

Fresh production readback exposed a bootstrap gap after the review-only route itself reached `AWAITING_CERTIFICATION`: the existing `PentaCertify v3` task runtime did not consume Penta Assignment certification state, and the assignment fabric had no exact-subject binding contract for the upstream PentaSecurity, CHLOM-rights and applicable-CIE decisions that must precede PentaCertifier.

The additive `ct.penta.assignment.certifier-preflight.v1` bridge closes only that orchestration gap. It does **not** create any of those authorities. The canonical evidence stays external to the bridge and can be bound only when all of the following agree with the current assignment subject:

- the authority identity is exactly the canonical owner (`penta.security`, `chlom`, or `cie`);
- the assignment exact Git head matches;
- the exact assignment subject digest matches;
- the evidence digest is valid;
- the referenced DAIL event/hash reads back from canonical chronology;
- predecessor/supersession lineage is preserved when a decision is replaced.

`PentaSecurity` must produce `PASS`. `CHLOM_RIGHTS` must produce `PASS` or a governed `NOT_APPLICABLE`. `CIE` must produce `PASS` or a governed `NOT_APPLICABLE`. The bridge itself cannot manufacture `NOT_APPLICABLE`; it only records the exact external disposition supplied by that authority.

The preflight additionally requires DAIL Evidence/Decision/Execution readback, PentaDocs and all three governed provider projections, current owner PASS results, exact-head PR linkage, D0-D2 scope, absence of reserved effects, and certifier-vs-owner separation. Only after all of those predicates pass may `penta_assignment_enqueue_independent_certifier_v1` place an `inspect` task into the **existing** `penta_certify_tasks_v3` queue. Queueing is not certification. The resulting task is source-bound, certification-only and explicitly carries `production_deploy=false` and `authority_created=false`.

The gate-binding ledger is append-only. Historical gate evidence is never rewritten; a changed exact head or exact subject digest invalidates prior bindings for preflight purposes and requires new authoritative evidence.

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
- treating a completed transport handoff as independent certification;
- relabeling an arbitrary actor as PentaSecurity/CHLOM/CIE;
- reusing a gate receipt across a changed Git head or changed subject digest;
- queuing PentaCertifier before upstream security/rights/cultural gates are satisfied;
- converting source/readiness or self-certified evidence into release authority.

Unknown/unregistered owner identities continue to fail closed under #1899.

## Acceptance

The review-routing transactional test must prove that the four existing executable routes remain unchanged, all three reviewer routes are canonical review-only Census handoffs, OS20 escalation and metadata authority escalation are rejected, a synthetic assignment reaches all three review handoffs, and zero OS20 execution tasks are created. The transaction must roll back all canary state.

The release-gate bridge transactional test must separately prove that current `AWAITING_CERTIFICATION` work remains HOLD without authentic PentaSecurity/CHLOM/CIE receipts, no PentaCertify task is queued on that HOLD, authority identity mismatch fails, exact-head mismatch fails, subject-digest mismatch fails, and all bridge functions remain service-role-only. It must not manufacture positive security/rights/CIE evidence merely to reach the certifier.

## Rollback

Before production apply: close/supersede this candidate with #1899/current main unchanged.

After governed apply: deactivate/remove only the additive review-only registry rows, review-only guard, exact-subject gate-binding/preflight/enqueue bridge through a governed forward migration, then exact-readback the original four-route registry and assignment state. Append-only assignment/DAIL/gate evidence remains historical and is never deleted or rewritten.

## Standards mapping

This implementation supports, without claiming external certification: NIST CSF 2.0 governance/protective controls; NIST SP 800-53 Rev.5 separation-of-duties, least-privilege, audit and configuration-management controls; NIST SP 800-207 explicit authorization; NIST SSDF/SP 800-218 verified release gates; NIST SP 800-161r1 exact source/provenance controls; CISA Secure by Design/Secure by Default fail-closed behavior; OWASP ASVS/API least privilege; CIS Controls v8; and SLSA-style source/provenance binding. SOC 2 Type II and ISO/IEC 27001:2022 remain architecture targets, not certification claims.

## Release boundary

Required order remains `Build -> security scanning -> threat model -> tests -> PentaSecurity -> CHLOM rights/authority -> applicable CIE -> independent PentaCertifier -> release -> exact readback`.

Originators, builders, PentaSecurity, PentaCHLOM and CHLOM builders may not self-certify. D3/human-reserved authority remains unchanged.
