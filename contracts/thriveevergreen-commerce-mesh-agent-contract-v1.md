# ThriveEvergreen Commerce Mesh Agent Contract v1

**Contract ID:** `ct.contract.thriveevergreen-commerce-mesh-agents.v1`  
**Framework:** `ct.framework.thriveevergreen-commerce-mesh.v1`  
**Authority:** `ct-founder-override-checkout-credit-production-20260824-v1`  
**State:** production

## Purpose

This contract defines the redundant agent topology used by the ThriveEvergreen Commerce Mesh. It permits bounded elastic capacity while preventing uncontrolled self-replication, self-approval, authority escalation, duplicate provider writes, or unsupervised D3 actions.

## Required paired roles

Every role operates as an independent A/B pair:

1. Product Architect
2. Rights & License Binder
3. Commerce Binder
4. Route Mesh Agent
5. Fulfillment QA
6. Certification Agent
7. Continuity & Recovery Agent
8. Procurement & Source Binder
9. Documentation & Repository Convergence Agent

Each role has at least two independent replicas. A role may scale above two only when queue depth, age or failure pressure requires additional capacity and only up to the configured maximum replica ceiling.

## Replica contract

Every replica MUST inherit:

- the same immutable role scope and authority ceiling;
- no-self-approval;
- non-voting status unless a different signed contract explicitly grants voting eligibility;
- D3 human reservation;
- heartbeat and stale-worker fencing;
- deterministic assignment and idempotency keys;
- least-privilege tools;
- no recursive spawn capability;
- no credential minting or permission expansion;
- no authority delegation to another replica;
- provider read-after-write where a write occurs;
- rollback or compensating-action reference;
- DAIL evidence emission for material state changes.

A worker may process more work. It may not make itself more powerful.

## Independent output rule

For release-critical dimensions, A and B work from the same pinned subject identity and evidence bundle but produce independent conclusions. Comparison yields `PASS`, `HOLD`, `CONFLICT`, or `FAIL`.

The originating producer cannot be its own final verifier. A certification agent cannot manufacture missing source evidence to convert HOLD into PASS.

## Provider-write rule

Only the Commerce Binder lane may perform provider publication writes under the Founder production override, and then only for exact catalog identities, exact prices, and exact provider objects already supported by institutional evidence. Customer charges are never initiated by background agents. Paid Checkout Sessions require a customer-initiated request.

## Rights and licensing rule

Rights & License Binder agents may normalize, map, verify and propose rights/license records. They may not invent ownership, contributor releases, territory, exclusivity, tax conclusions or other facts absent from evidence. Operative customer rights are issued only from a governed release/license binding.

## Demand scaling

The scaler uses queue depth to calculate desired replicas within the configured bounds. The secondary scheduler is a watchdog: it runs only when the primary production cycle is stale, preventing redundant schedulers from duplicating a healthy cycle.

## Failure handling

A replica must stop or fail closed when it encounters:

- ambiguous provider mutation outcome without readback;
- exact-version mismatch;
- identity/SKU mismatch;
- corrupt or missing deliverable;
- payment/entitlement mismatch;
- invalid rights/license state;
- credential exposure or exploit-critical security defect;
- missing rollback or reconciliation path for a mutating action.

The persistent desired state for Founder-authorized checkout routes remains `ENABLED`; a safety hold is a repair state, not a silent retirement of the route.
