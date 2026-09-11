# Changelog

## 2026-09-06 — DAIL Oracle Capacity Mesh v1

- Added `ct.dail.oracle-capacity-mesh.v1`, a local Cursor-subordinate fabric where five verified evidence oracles donate 100% of idle capacity at 100,000 or more pending routes while native oracle work always preempts donation.
- Registered PentaDAIL, PentaCertify, PentaWire, PentaCensus, and PentaDiscovery as bounded donor identities operating inside the same ThriveBase database with zero core network hops, one canonical DAIL chain, and one canonical append fabric.
- Added `LOCK_OVERCLOCK` at 500,000 pending routes, `RECOVERY_OVERCLOCK` from 100,000 through 499,999, and hysteresis release at 80,000 or fewer.
- Added one verification donor and up to four route donors per cycle, verification-lag-aware route throttling, PentaBalancer admission, PentaGas accounting, signed Penta cookies, oracle-attributed terminal DAIL appends, exact readback, and slice-level rollback.
- Added the 20-second PentaBalancer-managed scheduler `ct-dail-oracle-capacity-mesh-v1`, exact desired-state restoration, PentaTime registration, P0 operating assignment, RLS-isolated internal state, service-role-only execution, and authenticated safe status.
- Corrected observability projections so MeshAssist and Cursor separate scheduler attempts, no-ops, deferrals, material runs, and completed runs; continuity status now separates exact counts, estimates, observation times, and staleness.
- Initial observation recorded 3,000 oracle-attributed route deliveries, 15,000 oracle-attributed verifications, 13 signed cookies, zero route failures, a whole-stack pending-route change of -13,900, and a whole-stack verification-lag change of -13,421.
- Added architecture documentation, reader-writer/cookie operations manual, Drive custody, production canary, and machine-readable OS resource without changing the canonical CrownThrive OS v18.0.0 version.

## 2026-09-06 — ThriveBase Demo Sandbox Cursor Donor v1

- Activated the underused `ThriveBase-Public` Micro project under the operational alias `ThriveBase Demo Sandbox` while preserving its provider name and bindings.
- Added a continuously enforced managed-capacity policy reserving 70 of 100 discretionary units per minute for DAIL Cursor and retaining 30 units for existing request-driven public APIs and Vercel staging services.
- Added two 35-unit signed donor dispatch slots per minute through the existing ECDSA P-256 public-to-private bridge, with exact replay protection, manifest fingerprints, PentaBalancer admission, PentaGas settlement, and terminal DAIL readback.
- Preserved one canonical DAIL writer, no direct cross-project database access, no second ledger, and no independent authority source. The 70% figure is a CrownThrive-managed scheduler/worker budget, not a provider CPU partition guarantee.
- Added one pressure-deferral retry with a six-second offset, allowing the donor to avoid common scheduler collisions without bypassing PentaBalancer.
- Initial production observation recorded five bound donor runs, 3,000 donor-attributed routes, zero donor route failures, and an overall route-backlog movement from 548,013 to 539,230 during the measured deployment window.
- Registered PentaGas formula and recipe, verified interop contract, P0 assignment, node identity, RLS-isolated donor controls, production canary, and machine-readable OS resource.

## 2026-09-06 — DAIL 500K Continuity Lock + PentaGas v1

- Added `ct.dail.continuity.500k.v1`: lock routed evidence at 500,000 pending rows, retain the newest 500,000 as the active continuity window, and release only at 450,000 or fewer.
- Added deterministic depth bands and locked routing of 70% Head, 30% Continuity, and 0% Archive while preserving every queued row and the single canonical DAIL chain.
- Added six production nodes for Head, Continuity, Archive, Router, Verifier, and PentaGas, with Archive execution budget frozen while the lock is active.
- Added the nonfinancial `penta.gas` runtime with deterministic quote, node-budget reservation, settlement, five versioned formulas, five operational recipes, five verified interop contracts, and four nonbilling CHLOM Wallet meters.
- Added service-role-only windowed lookup admission so deep-history reads defer below the continuity floor unless exact critical authority exists for integrity verification, disaster restore, incident response, rights conflict, or Founder override.
- Upgraded DAIL Cursor to `dail_lane_drain_v5`, which applies the active-window fence and PentaGas controls while preserving one canonical writer and sequential chain verification.
- Added PentaBalancer-managed exact reconciliation job `ct-dail-continuity-exact-reconcile-v1` every five minutes, while retaining the every-minute Cursor controller. Cohesion remains 100.
- Added production semantic canary, bounded manual catch-up evidence, RLS/role isolation, architecture documentation, operational recipes, and machine-readable runtime state without rewriting CrownThrive OS v18.0.0.

## 2026-09-05 — Four-Part DAIL Cursor Runtime Extension v1

- Added `ct.dail.cursor.v1` as a fourth coordination rail over the single canonical CHLOM DAIL chain; Machine, Human, Hybrid, and Cursor remain projections rather than independent authority realities.
- Added input-manifest and terminal-reconciliation DAIL binding, bounded rail high-water marks, route/deferred draining, compact verification catch-up, service-role isolation, RLS, and a production canary.
- Integrated `ct-dail-cursor-control-v1` with PentaBalancer admission and exact scheduler cohesion. Retired the overlapping `ct-dail-serial-lane-drain-v4` and `chlom-dail-compact-catchup-v4` clocks without deleting their history.
- Added hard emergency ceilings of four serial virtual slices, one canonical database writer, 100,000 rail events, 600 route events, 50 deferred events, 20,000 verification events, and 120 minutes maximum per activation.
- Completed 20 DAIL-bound manual catch-up cycles: 4,928 route rows delivered, 6 deferred events delivered, 49,355 events verified, and observed verification lag reduced to zero.
- Added architecture, operations, and machine-readable production resources under `docs/` and `.crownthrive/resources/` without rewriting the canonical CrownThrive OS v18.0.0 version.

## 2026-08-27 — D3 Founder Production Approval Window v1

- Added an immutable, nonrenewing Founder-human approval window tied to `ct.penta.flow-control.20260826.v1` and expiring `2026-09-10T01:23:52.144189Z`.
- Added exact-candidate approval receipts, automatic governed-release binding, D3 release-dimension enforcement, cumulative effect-specific gates, revocation, and authority-reducing rollback.
- Added a deterministic evaluator and expanded the flow-control certifier so Founder approval cannot substitute for independent verification or rollback/readback evidence.
- Kept the existing flow-control campaign on HOLD until its missing independent-verifier and exact rollback/readback evidence exists.

<!-- pentarelease:managed-release-surface:start -->
## Latest PentaRelease — v3.91.0.3

- **Official release:** https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.91.0.3
- **Release title:** CrownThrive OS 3.91.0.3 — Autonomous PentaRelease
- **Who:** PentaRelease / provider actor github-actions[bot]
- **Why:** release-relevant bounded delta
- **Changed paths:** 5
- **Provider actual cost:** $0.00 USD
- **Recognized release exposure:** $0.00 USD
- **Direct usage calculation:** `not_available`
- **CIE:** **PASS — 100/100**
- **CIE dimensions:** brand_safety=20, identity_fit=20, legacy_impact=20, community_value=20, story_alignment=20
- **Evidence:** `75d7df8f38034b3b094473e9938e4c33edc872c785b5b244560e151ac03f05a8`

PentaRelease maintains this bounded block. Content outside the markers remains under its existing ownership and editorial authority.
<!-- pentarelease:managed-release-surface:end -->
