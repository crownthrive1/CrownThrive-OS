---
title: "Phase 2.99 Hard-Exit Ledger v1.3.4 — Reconciliation Debt Separation"
sidebarTitle: "Hard-Exit v1.3.4"
description: "Public-safe reconciliation separating the authoritative registry from scopes that actually require formal Phase 2.99 reconciliation proof."
icon: "diagram-project"
---

# Phase 2.99 Hard-Exit Ledger v1.3.4 — Reconciliation Debt Separation

## Publication/IP disposition

```yaml
ip_governing_issue: 131
classification:
  - PUBLIC_STANDARD
  - PUBLIC_DOCTRINE
projection: public_specification
publication_state: PUBLIC_SAFE
uncertainty_rule: HOLD
commercial_offer_state: not_applicable
```

This public packet contains governance/current-state facts only. It excludes credentials/fingerprints, private DAIL/evidence, proprietary evaluation corpora, private policy/economic calibration, trade-secret implementation detail, patent-candidate mechanisms and restricted institutional records. It creates no price, Stripe Product/Price, checkout, certification or customer entitlement.

## Why v1.3.4 was required

The live routing/scan registry expanded while v1.3.3 was validating. Treating every authoritative registry row as formal reconciliation debt would violate the CrownThrive rule that **registry growth alone is not a build/certification gap**.

Current permissioned evidence now distinguishes:

```yaml
authoritative_registry_total: 240
scan_required: 240
reconcile_required: 233
scan_only_or_non_debt: 7
state_distribution:
  PASS: 137
  OPEN: 68
  BLOCKED: 12
  CLOSED: 14
  DEFERRED: 9
```

The seven current authoritative scopes explicitly marked `reconcile_required=false` are ThriveTools OPT service-state records already suitable for drift scanning without creating new formal Phase-2.99 proof debt. They remain scan-required and may reopen on drift.

Twenty scopes entered the authoritative registry after the prior 220-scope snapshot. Thirteen explicitly require reconciliation; seven do not. Therefore formal debt grows by **13**, not by 20.

## Formal L/M/N/O proof denominator

The last global formal reconciliation run remains:

```yaml
scanner: ct.reconciliation.lmno.agent-e
reconciled_scopes: 170
drift_scopes: 8
unresolved_scopes: 73
status: partial
```

Formal proof debt is now calculated against the current `reconcile_required` universe:

```text
233 reconcile-required scopes - 170 formally reconciled scopes = 63-scope formal coverage gap
```

It is **not** calculated as `240 - 170 = 70`, because that would incorrectly convert seven scan-only current records into certification debt.

Supplemental non-voting evidence has also advanced:

- credential continuity: 220 tagged / 19 reconciled / 4 drift / 7 unresolved;
- Agent H webhook delivery: 18 tagged / 18 reconciled / 5 drift / 11 unresolved.

Neither helper scan substitutes for formal L/M/N/O proof or sovereign verification.

## ThriveTools OPT current-public boundary

The new ThriveTools OPT state includes a separate open PR #134 for a `PUBLIC_STANDARD` API projection. The candidate page explicitly excludes secret values, credential fingerprints, private runtime mapping, proprietary conformance corpora and restricted implementation logic, and keeps provider writes, package pricing, checkout and customer-impacting automation closed.

An open public documentation PR is evidence of a candidate projection, not canonical publication authority. Its `public_standard_docs_projection` scope remains OPEN until governed disposition.

## Hard-exit state

No hard-exit or phase promotion occurs:

- GATE-004: PASS
- GATE-005: PASS
- GATE-006: governed deferred / technically NOT-PASS
- GATE-001, GATE-002, GATE-003, GATE-007, GATE-008: NOT-MET and blocking
- Phase 2 complete: false
- Phase 3 entry: false

GATE-003 now records the **63-scope reconciliation-required proof gap**.

## Negative tests

The v1.3.4 validator preserves all prior fail-closed tests and adds explicit protection against:

- treating the full registry count as formal reconciliation debt;
- deleting the seven explicit scan-only/non-debt current records to force count equality;
- calculating formal proof gap from total registry rows instead of `reconcile_required` scopes.

The existing #131 tests continue to reject protected material in the public projection, HOLD state represented as public-safe, and commercial/checkout activation from the hard-exit ledger.

## Rollback / reopen

Rollback remains a revert of the bounded ledger/validator/changelog commits; no external runtime state is changed.

Reopen on current-main/head movement, tag distribution or `reconcile_required` classification change, formal L/M/N/O coverage movement, RLS/policy drift, #120 point-of-use triggers, full-documentation disposition change, roadmap-v2 migration, IP-classification/publication-state change, or new critical/high evidence.
