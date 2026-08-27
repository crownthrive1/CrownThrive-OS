# CrownThrive OS 2.0 — Penta Economic Fabric v2

Status: **PRODUCTION-CERTIFIED / ENABLED**  
Contract: `ct.penta.economic-fabric.v2`  
Release: `OS-2.0.0`

## Canonical operating model

The economic fabric separates execution authority from money and payment obligations.

`PentaMarket → PentaTreasury/SmartTreasury → PentaCosts → PentaRoute → usage/reconciliation → DAIL/PentaLedger → PentaPay (when an obligation exists) → governed external settlement → PentaRelease`

CHLOM and PentaBound govern identity, authority, rights and consequence boundaries across the chain. PentaPolicy/Governance controls limits and rules. PentaRelease consumes evidence; it does not manufacture missing economics.

## Separation invariants

1. **Internal execution units are not USD or another currency.** They measure bounded machine execution authority.
2. **PentaTreasury is not payroll.** It issues bounded execution authority and daily budgets; it does not grant inherited external money-movement authority.
3. **PentaCosts is the execution-economic control plane.** It reserves internal units before work, meters actual use, reconciles estimated versus actual consumption, records provider-attributable cost and enforces hard limits.
4. **PentaPay is the obligation/compensation ledger.** A PentaPay entry records what is owed and why. It is not itself provider dispatch authority.
5. **PentaPay self-approval is prohibited.** The beneficiary cannot approve its own obligation.
6. **Actual external settlement requires independent authority, provider receipt and readback evidence.** Generic Penta authority does not inherit money movement.
7. **DAIL is the immutable institutional evidence plane.** Reservations, usage, obligations, approvals, settlement evidence and production certification are projected to DAIL.
8. **Legacy v1 economic tables remain preserved.** Production v2 was introduced additively rather than silently rewriting historical semantics.

## Production v2 data plane

### PentaMarket

`penta_runtime.cost_rate_books_v2`

Certified rate records carry provider, operation, unit, internal-unit conversion, provider cost, effective dates, source reference and evidence hash.

### PentaCosts

- `penta_runtime.cost_reservations_v2`
- `penta_runtime.cost_usage_events_v2`
- `penta_runtime.cost_ledger_entries_v2`
- `public.penta_cost_reserve_v2(...)`
- `public.penta_cost_account_v2(...)`

The v2 cost ledger is append-only. Task reservation uses the OS 2.0 Penta budget authority and therefore fails closed on insufficient budget or authority.

### PentaPay

- `public.penta_pay_entries` (preserved institutional ledger)
- `public.penta_pay_obligation_links_v2`
- `public.penta_pay_settlement_receipts_v2`
- `public.penta_pay_create_obligation_v2(...)`
- `public.penta_pay_approve_v2(...)`
- `public.penta_pay_record_external_settlement_v2(...)`

External settlement recording never performs provider dispatch itself. It accepts a settlement only after a provider receipt, authority evidence and successful readback are supplied.

### PentaRelease

`public.penta_release_economic_envelope_v2(release_version)`

The envelope reports separately:

- reserved internal execution units
- accounted internal execution units
- estimated provider cost
- actual provider cost
- PentaPay obligations
- externally settled obligations
- separation invariants

## Production certification

Economic-fabric canary certification:

- Certification ID: `5542ac3f-58c4-4cef-a06f-8158c2422951`
- Evidence SHA-256: `efbf65dbdcf60e7d04bb8a727873d22bdd26631e30e169beaeb3d1b6613c0d62`
- Verdict: `PASS`

Verified canaries:

- PentaCosts reservation: PASS
- PentaCosts metering/accounting: PASS
- task settlement: PASS
- PentaPay obligation creation: PASS
- independent approval: PASS
- self-approval rejection: PASS
- money-movement non-inheritance: PASS
- internal-unit/currency separation: PASS
- DAIL evidence projection: PASS

OS 2.0 production assessment after the economic fabric became a hard gate:

- Production certification ID: `c02de656-2211-4d66-8fc8-72bc52db7f02`
- Pipeline run: `156c150b-8ced-4e3f-a6b7-930c49e6e2f9`
- Status: `CERTIFIED`
- Blockers: `0`
- Warnings: `0`
- Economic-fabric RLS-protected tables: `6/6`

## Topology registration

The Penta topology now treats these as first-class enabled components:

- `penta.market` — PentaMarket
- `penta.treasury` — PentaTreasury / SmartTreasury
- `penta.costs` — PentaCosts v2
- `penta.pay` — PentaPay v2
- `penta.ledger` — PentaLedger
- `penta.release` — PentaRelease v2

Required topology relations include certified rates, Treasury execution authority, cost authorization, routing usage evidence, ledger truth, PentaPay obligation evidence, governed settlement and PentaRelease economic provenance.

## Governance rule

No software component may reinterpret an internal execution-unit budget as a cash balance, payroll balance, stored value, or external payment entitlement. Actual money movement requires a separately authorized and certified provider edge plus readback receipt.
