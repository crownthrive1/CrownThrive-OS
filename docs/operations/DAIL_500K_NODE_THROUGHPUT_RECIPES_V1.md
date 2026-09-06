# DAIL 500K Node Throughput Recipes v1

## Operating objective

Preserve current CrownThrive throughput while routed CHLOM DAIL evidence exceeds 500,000 pending rows. Deep history waits safely; current and active-continuity work moves; sequential verification continues; every material control transition and terminal result is DAIL-bound.

## Formula set

1. **Continuity floor** — `F = max(1, H - 500000 + 1)`.
2. **Lock hysteresis** — lock at `P >= 500000`; release at `P <= 450000`; otherwise preserve the previous state.
3. **Locked route weight** — 70% Head, 30% active Continuity, 0% Archive.
4. **PentaGas quote** — combine versioned rate-book work with depth, pressure, and risk multipliers.
5. **Effective node budget** — `Base × Health × max(0.10, 1 - Pressure/100) × LockFactor`.

## Recipe 1 — Locked 500K throughput

Entry: pending route rows are at or above 500,000.

1. Reconcile exact lock state and set the 500,000-row route fence.
2. Freeze Archive route share and Archive PentaGas LockFactor at zero.
3. Quote and reserve Router PentaGas.
4. Select 70% newest/current rows.
5. Select the remainder oldest-first inside the active fence.
6. Append through one canonical DAIL writer.
7. Continue sequential chain verification.
8. Settle actual PentaGas units.
9. Persist and, when material, DAIL-bind the terminal receipt.

Exit: zero route failures, queued overflow preserved, and no Archive row selected.

Rollback: stop new drains, retain all queued rows, cancel unsettled reservations, and do not unlock until the exact pending count is 450,000 or fewer.

## Recipe 2 — Normal throughput

Entry: pending route rows are 450,000 or fewer.

1. Release the lock and DAIL-bind the transition.
2. Restore Archive node budget.
3. Resume oldest-first route draining.
4. Verify the canonical chain sequentially.
5. Settle PentaGas and bind the terminal result.

Rollback: reactivate the lock if exact pending work returns to 500,000 or more.

## Recipe 3 — Deep-history lookup

Entry: requested sequence range begins below the active continuity floor.

1. Classify the request as Head, Continuity, or Archive.
2. Build a deterministic PentaGas quote.
3. When locked, defer Archive work unless an exact critical authority class and authority reference both exist.
4. If admitted, reserve the selected node budget.
5. Execute a bounded read and return safe event headers rather than full protected payload bodies.
6. Hash the result, settle PentaGas, and DAIL-bind the disposition.

Critical classes: integrity verification, disaster restore, incident response, rights conflict, and founder override.

Rollback: cancel the reservation on failure and retain the request as deferred.

## Recipe 4 — Emergency catch-up

Entry: exact Founder or incident authority, PentaBalancer pressure at or below 45, and a self-expiring emergency window.

1. Activate the emergency profile for no more than 120 minutes.
2. Preserve one canonical writer.
3. Use serial bounded virtual slices only.
4. Honor the 500K continuity lock and Archive freeze.
5. Stop or reduce throughput when PentaBalancer pressure rises.
6. Verify the chain and bind every material run input and terminal result.
7. Disable emergency mode explicitly or allow automatic expiry.

Rollback: PentaBalancer may reduce or refuse throughput; no partial institutional result is created on lock or pressure deferral.

## Recipe 5 — Node recovery

Entry: node health is not healthy or provider readback fails.

1. Reduce the node health factor and defer unsafe work.
2. Diagnose the smallest failed dependency.
3. Repair without changing authority boundaries.
4. Read back provider state.
5. Restore node budget.
6. Run the continuity semantic canary.

Provider failure is not billable and cannot be represented as completion.

## Contract set

- `ct.contract.dail.continuity-window.v1`
- `ct.contract.dail.windowed-lookup.v1`
- `ct.contract.pentagas.quote-reserve-settle.v1`
- `ct.contract.dail.node-routing.v1`
- `ct.contract.dail.archive-release.v1`

All contracts are D1, idempotent, rollback-required, verified, and nonfinancial. They do not create rights, payments, entitlements, provider authority, or a second ledger.

## PentaGas lifecycle

`quote → reserve → execute → settle → evidence`

The internal unit is `PENTAGAS_INTERNAL`. It has no market value and no customer balance. Billing, price calculation, provider write for metering, token issuance, and chain broadcast remain disabled.

## Production checks

Before changing any rate, formula, node budget, route share, threshold, scheduler, or contract:

1. Confirm exact policy SHA-256 and current continuity state.
2. Confirm Archive share and LockFactor are zero while locked.
3. Confirm Cursor uses `dail_lane_drain_v5`.
4. Confirm both jobs are PentaBalancer-managed and cohesion remains 100.
5. Confirm route failures are zero and the verifier has no unhandled error.
6. Run `chlom_runtime.dail_continuity_canary_v1()`.
7. DAIL-bind and read back the material change before treating it as complete.
