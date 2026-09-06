# DAIL 500K Continuity Lock + PentaGas v1

**Status:** Production canary PASS  
**Policy:** `ct.dail.continuity.500k.v1`  
**Penta system:** `penta.gas`  
**Assignment:** `ct.assignment.dail-500k-continuity-pentagas-node-control-v1`  
**Assignment ID:** `866a89ea-ba0e-4c7e-918f-63e817b2d70e`

## Architecture decision

CrownThrive retains one append-only canonical CHLOM DAIL chain. The 500K Continuity Lock changes scheduling and lookup admission only; it never deletes history, rewrites event identity, reorders canonical sequence, or skips sequential verification.

When pending routed evidence reaches 500,000 rows, the newest 500,000 rows form the active continuity window. Older overflow waits. The lock remains active until the pending count falls to 450,000 or fewer, creating a 50,000-row hysteresis band that prevents lock flapping.

## Depth bands

- **Head:** newest 50,000 blocks and current work.
- **Continuity:** the remainder of the newest 500,000-block active window.
- **Archive:** overflow older than the active window.

While locked, route selection is 70% Head, 30% Continuity, and 0% Archive. Archive rows remain queued and its effective PentaGas LockFactor is zero. Sequential chain verification continues independently across the canonical chain.

## Core formulas

1. Continuity floor: `F = max(1, H - 500000 + 1)`.
2. Lock hysteresis: lock when `P >= 500000`; release when `P <= 450000`; otherwise preserve prior state.
3. Locked route weight: `ceil(N * 0.70)` Head plus the remainder Continuity and zero Archive.
4. PentaGas quote: `G = ceil((B + ceil(S/1000)Rs + WRw + RRp + ARa + ceil(V/1000)Rv) * Md * Mp * Mr)`.
5. Effective node budget: `E = floor(Base * Health * max(0.10, 1 - Pressure/100) * LockFactor)`.

Each formula is versioned and SHA-256 bound in `penta_gas.formula_registry_v1`.

## Node-oriented fabric

- `node:chlom.dail.head`
- `node:chlom.dail.continuity`
- `node:chlom.dail.archive`
- `node:chlom.dail.router`
- `node:chlom.dail.verifier`
- `node:penta.gas`

Nodes are workload and evidence-control roles, not independent ledgers or authority realities.

## PentaGas boundary

PentaGas provides deterministic internal quote, reservation, and settlement controls. It is not money, a token, a public-chain fee, a customer charge, a rights grant, an approval, or independent execution authority. Billing, price calculation, market value, token issuance, and provider write for the four registered meters remain disabled. Provider cost is fixed at zero.

Runtime functions:

- `penta_gas.quote_v1`
- `penta_gas.reserve_v1`
- `penta_gas.settle_v1`
- `chlom_runtime.dail_continuity_reconcile_v1`
- `chlom_runtime.dail_continuity_admit_lookup_v1`
- `public.chlom_query_dail_windowed_v1`
- `chlom_runtime.dail_lane_drain_v5`
- `chlom_runtime.dail_continuity_status_v1`
- `chlom_runtime.dail_continuity_canary_v1`

## Critical deep-history bypass

Archive lookup admission can bypass the wait only for an exact authority reference and one of these operation classes:

- integrity verification
- disaster restore
- incident response
- rights conflict
- founder override

A bypass remains bounded, PentaGas-metered, and DAIL-evidenced. It does not reopen Archive generally.

## Scheduler topology

- `ct-dail-cursor-control-v1`: every minute through PentaBalancer; normal admission; priority 95.
- `ct-dail-continuity-exact-reconcile-v1`: minute 2 modulo 5 through PentaBalancer; elastic admission; priority 45.

The minute controller uses `dail_lane_drain_v5`. Exact pending counts and continuity fences are reconciled separately so a full count does not block every hot-path cycle. Both paths share a continuity-control advisory lock and preserve one canonical writer.

## Production inventory

- 5 production formulas
- 5 production recipes
- 5 verified interop contracts
- 4 controlled-test nonbilling meters
- 6 active nodes
- 10 RLS-protected continuity/PentaGas tables
- PentaBalancer cohesion score 100

## Production proof

- Policy SHA-256: `e21ae6c326d705c5ee0e756b0c2a0d2cf64d063239ca491a5539d6edb5bf74cb`
- Lock transition event: `f45a0be3-b680-4198-a7ba-6c989e1b1dfc`
- Production canary event: `26d21b74-ac58-4fe8-aa3f-dc950dcc2c53`
- Initial manual catch-up event: `686ab824-a0ff-4656-9516-fbefc7196fbc`
- Latest bounded manual run: `1a64566e-2230-47f6-9d95-9b30ce8ba0cc`
- Latest terminal event: `1896313c-86b8-4e0d-8da8-80242a9cab84`

The latest bounded run delivered 500 route rows and 2 deferred events, verified 568 canonical events, and completed with input and terminal DAIL readback. Immediate overlapping attempts returned `DEFERRED_DAIL_LOCK_BUSY` and created no partial institutional result.

## CHLOM preparation purpose

The design establishes stable node identities, deterministic formula hashes, repeatable recipes, exact interop contracts, internal resource metering, continuity receipts, and sequential-verification guarantees. It prepares CHLOM for node-aware resource governance without prematurely creating a currency, token, public-chain gas fee, or financial claim.

## Rollback

Stop new continuity drains, retain every queued route and lookup request, cancel unsettled reservations, preserve the current lock state, repair the smallest failed dependency, run the semantic canary, and resume only after provider and DAIL readback. Never reopen Archive automatically during an incident.
