# Phase 2.99 hard-exit ledger v1.3.6 — current proof refresh and collision cleanup

Date: 2026-08-20
Packet: PR #122 / Agent C implementation family
Canonical baseline: `8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7`

## Purpose

Reconcile the bounded Phase 2.99 hard-exit ledger to fresh accepted GitHub, Mintlify and connected Supabase evidence without altering sovereign authority, public/private boundaries, commercialization state or Phase-3 eligibility.

This pass also repairs a branch-collision defect: five API/navigation/platform files from another implementation lane had entered PR #122. They were restored to the exact canonical-main state rather than repaired or adopted inside Agent C's ledger packet.

## Evidence used

- GitHub canonical `main` remains PR #91 merge `8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7`.
- GitHub PR #122 exact pre-repair head exposed the foreign-file collision and failed Documentation Governance on a broken ThrivePush adapter link.
- Mintlify `crown-thrive` is sourced from `crownthrive1/CrownThrive-Support`, deploy branch `main`; the published Help Center seed still contains the stale `complete_machine_manifest_generated_in_repo: pending_governed_merge` projection even though PR #91 is canonical.
- Connected Supabase at `2026-08-20T04:36:52.317363Z` reports 267 authoritative reconciliation tags: 149 PASS / 77 OPEN / 15 BLOCKED / 17 CLOSED / 9 DEFERRED. All 267 are scan-required and reconcile-required.
- The latest formal L/M/N/O scan still reconciles 170 scopes with 8 drift and 73 unresolved, leaving a formal proof-coverage gap of 97.
- The latest credential-continuity supplemental scan is 266 tagged / 23 reconciled / 3 drift / 10 unresolved; it is non-voting and not formal L/M/N/O proof.
- The latest Agent-H webhook-delivery supplemental scan is 18 tagged / 18 reconciled / 6 drift / 11 unresolved; it is non-voting and not formal L/M/N/O proof.
- Fresh PostgreSQL catalog/policy inspection shows 15 `integration_control` base tables, 15/15 RLS enabled, 15/15 explicit service-role-only ALL-policy coverage, FORCE RLS on 0 tables. Supabase Security Advisor reports 0 current lints.

## Current hard-exit accounting

- PASS: CT-P299-GATE-001, CT-P299-GATE-004, CT-P299-GATE-005.
- Governed deferred, technically NOT-PASS: CT-P299-GATE-006 at 6/7 Collab predicates.
- Blocking NOT-MET: CT-P299-GATE-002, CT-P299-GATE-003, CT-P299-GATE-007, CT-P299-GATE-008.
- Phase 2 complete: false.
- Phase 3 entry: false.

Registry growth itself is not a certification defect. In this snapshot, however, all 267 authoritative scopes are explicitly marked `reconcile_required`, so the formal reconciliation denominator is 267 by accepted machine state. Supplemental scanners cannot substitute for the formal L/M/N/O proof lane.

## IP / publication gate

Issue #131 classification is applied before this public repository projection:

```yaml
classification:
  - PUBLIC_STANDARD
  - PUBLIC_DOCTRINE
projection: public_specification
publication_state: PUBLIC_SAFE
uncertainty_rule: HOLD
commercialization: not_applicable
```

This packet contains no trade-secret candidate/controlled implementation, patent-candidate mechanism, RESTRICTED_INSTITUTIONAL record, credential/fingerprint, private policy/economic calibration, proprietary evaluation corpus or private DAIL/evidence body. Any uncertainty remains HOLD rather than being sanitized by guesswork.

## Commercialization state

Not applicable. This packet creates no offer promotion, exact price, Stripe Product/Price, checkout, certification status, customer entitlement or live revenue. PR #133 remains a separate noncanonical candidate implementation for the permanent IP/commercialization framework.

## Files / collision repair

The following foreign files were removed from PR #122 by restoring canonical-main state:

- `developers/crownlytics-api-adapter.mdx` — removed from this branch because it does not exist on canonical main.
- `developers/crownpulse-admin-api-adapter.mdx` — removed from this branch because it does not exist on canonical main.
- `docs.json` — restored to canonical main.
- `platforms/crownpulse-institutional-registry.mdx` — restored to canonical main.
- `platforms/thrivepush-institutional-registry.mdx` — restored to canonical main.

Agent C does not adopt, verify or publish those foreign surfaces through this packet.

## Validation / negative cases

The v1.3.6 validator fails closed on:

- 20-phase promotion before a governed roadmap-v2 ADR/namespace;
- expansion of the sovereign voter pool beyond A/B/C/D/S;
- D3 authority escaping the human-reserved boundary;
- GATE-001 being inflated into production certification;
- regression of PR #91 machine-manifest truth;
- false Help Center terminal/P0-P1 closure;
- hidden reconciliation-tag or reconcile-required drift;
- false formal-LMNO coverage;
- supplemental scanners substituting for formal proof;
- RLS or explicit-policy coverage regression;
- false Collab 7/7 or deferred webhook evidence promoted to technical PASS;
- protected/restricted IP projected public;
- HOLD represented as PUBLIC_SAFE;
- checkout/commercial activation introduced by the ledger;
- premature GATE-008 or Phase-3 entry.

## Security / rights implications

The RLS security gate remains PASS only because the complete current table estate is RLS/policy covered. New tables without equivalent coverage reopen the gate. Provider-wide security inventories not exposed by the available connector are not represented as zero findings.

No rights grant, license issuance, trademark/patent claim, source-code license or private evidence publication occurs.

## Documentation impact

`docs_updated` for the hard-exit ledger and this changelog. The Help Center projection drift remains open under the non-deferrable full-documentation-estate gate and remains owned by the documentation reconciliation lane.

## Rollback / reopen

Rollback: revert the bounded v1.3.6 ledger/validator/changelog refresh and collision-cleanup commits. There is no provider/database schema/credential/payment/rights/customer/production mutation to unwind.

Reopen on canonical-main/head movement; reconciliation tag or reconcile-required drift; formal L/M/N/O movement; RLS/policy/advisor drift; GATE-001 authority/source-universe change; #120 point-of-use trigger; roadmap-v2 canonical migration; full-documentation disposition change; #131 IP/publication change; or new critical/high evidence.

## Downstream phase effects

Phases 3–10 continue to inherit the current canonical ten-phase roadmap until a governed roadmap-v2 migration occurs. No downstream phase may interpret this proof refresh as Phase-3 entry authority. The prospective 20-phase structure and Phase-20 domain continuity direction remain founder direction, not current machine namespace.
