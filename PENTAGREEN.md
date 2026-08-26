# PentaGreen™

**Canonical identity:** `PentaGreen™`  
**Stable contract:** `ct.pentagreen.core.v1`  
**Legacy alias:** `ThriveEvergreen™`  
**Institutional role:** CrownThrive mandatory Commerce & Economic Activation Authority and CHLOM cross-pallet commerce/economic-execution subprotocol.

> **Constitutional rule:** PentaGreen may optimize within authority. It may never manufacture authority.

## Decision contract

Every governed economic activation resolves through one of three states:

- `ECAC` — economically authorized within the exact current authority and evidence envelope;
- `HOLD` — incomplete, uncertain, unverified, unbound, or awaiting reconciliation/authority;
- `DENY` — prohibited, revoked, outside authority, or failed hard policy.

Provider delivery, payment, fulfillment, advertising, marketplace, API, MCP, plugin, agent, webhook, or deployment success is evidence of execution. It is **not** institutional economic truth by itself. PentaGreen requires reconciliation before that evidence can create or advance invoice, earning, payout, entitlement, settlement, public-performance, SKU, or other governed economic state.

## Canonical subsystem family

| Component | Stable contract | Role |
| --- | --- | --- |
| **PentaCredits™** | `ct.pentagreen.credits.v1` | Credits, stored value, balances, programs, top-ups, purchases, caps, reversals, and reconciliation. |
| **PentaSKU™** | `ct.pentagreen.sku.v1` | Exclusive CrownThrive SKU issuance, aliases, retirement, and non-reuse. |
| **PentaLedger™** | `ct.pentagreen.ledger.v1` | Reconciled institutional economic-truth ledger projection. |
| **PentaReconcile™** | `ct.pentagreen.reconcile.v1` | Reconciles provider evidence before economic truth is accepted. |
| **PentaHold™** | `ct.pentagreen.hold.v1` | `ECAC | HOLD | DENY`, SAFE_HOLD, and fail-closed economic gating. |
| **PentaSettle™** | `ct.pentagreen.settle.v1` | Settlement eligibility, gating, and finality orchestration. |
| **PentaEntitle™** | `ct.pentagreen.entitle.v1` | Governed entitlement issuance, revocation, and reconciliation. |
| **PentaInvoice™** | `ct.pentagreen.invoice.v1` | Governed invoice creation and invoice-state reconciliation. |
| **PentaPayout™** | `ct.pentagreen.payout.v1` | Payout eligibility, authorization, reconciliation, and completion. |
| **PentaPrice™** | `ct.pentagreen.price.v1` | Prices, offers, denominations, and commercial-term authority. |
| **PentaCatalog™** | `ct.pentagreen.catalog.v1` | Canonical economic catalog of products, offers, SKUs, aliases, and provider bindings. |
| **PentaCheckout™** | `ct.pentagreen.checkout.v1` | Governed purchase intent and checkout-entry orchestration. |
| **PentaReceipt™** | `ct.pentagreen.receipt.v1` | Immutable provider/execution evidence receipts. |
| **PentaCompensate™** | `ct.pentagreen.compensate.v1` | Rollback, reversal, remediation, and compensating actions. |
| **PentaPolicy™** | `ct.pentagreen.policy.v1` | Machine-readable commerce authority, quorum, limits, and execution policy. |
| **PentaBridge™** | `ct.pentagreen.bridge.v1` | Replaceable provider adapters and cross-pallet economic bridges. |
| **PentaMarket™** | `ct.pentagreen.market.v1` | Marketplace activation and governed market-state routing. |

## Runtime compatibility

The rename is additive and non-destructive.

- New institutional authoring and machine-readable identities use `PentaGreen` and the Penta subsystem names.
- Existing `thriveevergreen_*` database tables, function names, event IDs, receipts, historical documentation, release evidence, and provider bindings remain valid provenance surfaces until deliberately migrated.
- Canonical `pentagreen_*` compatibility views and wrapper functions resolve to the existing verified runtime paths rather than rewriting evidence history.
- `ThriveEvergreen` remains readable as a legacy alias, not a competing authority.
- Retired SKUs are never reused.
- No migration may convert provider success into economic authority or bypass CHLOM, PentaBound, quorum, legal, finance, evidence, security, or D3 controls.

## PENTA topology

PentaGreen is a first-class member of CrownThrive's PENTA operating family. Its runtime topology is bound to:

- **PentaOS** — institutional operating generation and system-of-systems coordination;
- **PentaBase** — operational data/control plane;
- **PentaBound** — authority ceilings and bounded execution;
- **PentaRoute** — API/MCP and execution routing;
- **PentaFactory** — governed software/package generation and maintenance;
- **PentaDocs** — canonical documentation projection;
- **PentaVergence** — reconciliation, stale-state repair, supersession, and convergence;
- **PentaFlex** — API/MCP adapter exposure where separately certified;
- **PentaWire** — events, connectivity, and transport fabric.

## Agent boundary

`ct.penta.agent.green` is the bounded PentaGreen Agent. It may assess status, resolve aliases, route economic gates, and supervise reconciliation within its current authority ceiling. It is not sovereign, cannot self-approve, cannot self-vote, and cannot manufacture D3, money-movement, licensing, settlement, or provider-write authority.

## Migration rule

Current code, docs, APIs, MCPs, workflows, agents, registries, factories, and new releases should use the canonical Penta names. Historical changelogs, immutable receipts, prior releases, signed evidence, and exact legacy identifiers should preserve `ThriveEvergreen` where changing the identifier would damage provenance. Where useful, render them as **PentaGreen™ (legacy: ThriveEvergreen™)**.

**Effective:** 2026-08-26  
**Owner:** CrownThrive, LLC
