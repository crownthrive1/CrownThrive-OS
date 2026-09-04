---
name: stripe-monetization
description: Govern CrownThrive Stripe catalog, pricing, Payment Link, webhook, MCP, credential-route, and PentaGreen factory work. Use for Stripe integration, monetization-readiness, or provider-remediation tasks; money movement and other held capabilities still require their exact authority gates.
---

# CrownThrive Stripe Monetization Skill

Use this skill whenever a CrownThrive site, Penta, factory, marketplace, service, membership, event, digital product, creator/seller rail, invoice flow, or commercial workflow needs Stripe.

## Canonical rule

Stripe is an external execution provider beneath **PentaGreen**. Do not describe Stripe publicly as a strategic partner unless a governing relationship record expressly supports that claim. Never let a Stripe Product, Price, Payment Link, Checkout Session, connected-account, invoice, or subscription identifier become CrownThrive's canonical economic identity.

The canonical provider adapter is `ct.adapter.stripe.v1`, component version `2.0.0`. Its MCP, runtime, webhook, and catalog-mirror variants are transports under that identity, not independent authority planes.

Canonical CrownThrive owners include:

- PentaSKU — SKU identity
- PentaCatalog — product catalog truth
- PentaPrice — price authority and evidence
- PentaCheckout — checkout configuration
- PentaInvoice — subscriptions and invoices
- PentaMarket — marketplace/platform economics
- PentaReceipt / PentaReconcile — provider-event reconciliation
- PentaLedger — institutional economic ledger
- PentaHook / PentaWire — webhook ingress and transport
- PentaCredentials — credential custody
- PentaRoute / PentaBridge — provider selection and normalization
- PentaGreen — CrownThrive economic authority

## Start with current truth

Before any Stripe mutation:

1. Read `integration_control.stripe_os_runtime_readiness_v2()`.
2. Read `integration_control.pentagreen_stripe_mesh_v3` and `integration_control.stripe_os_capability_adoption_v2`.
3. Confirm the PentaGreen commerce clock is still paused unless a separately authorized activation receipt says otherwise.
4. Read the relevant product, service, offer, PentaSKU, PentaPrice, entitlement, route, and owner state.
5. Reuse the current mirrors:
   - `integration_control.stripe_catalog_products_v2`
   - `integration_control.stripe_catalog_prices_v2`
   - `integration_control.stripe_payment_link_inventory_v4`
   - `integration_control.stripe_webhook_lanes_v3`
6. Read open requests, receipts, and provider aliases before creating anything.
7. Keep provider availability, CrownThrive authority, runtime certification, and product readiness as separate states.

The current factory baseline is zero ready profiles out of 1,042. Do not turn this into a monetization-ready claim because the typed adapter exists.

## Supported execution boundary

Only four provider-write families have typed CrownThrive routes:

| Family | Route | State |
| --- | --- | --- |
| Product | `integration_control.stripe_os_provider_operation_v2` | Typed; factory paused |
| Price | `integration_control.stripe_os_provider_operation_v2` | Typed; factory paused |
| Payment Link | `integration_control.stripe_os_provider_operation_v2` | Typed; factory paused |
| Webhook | `integration_control.stripe_webhook_provider_reconcile_v3` | Typed reconciliation; degraded topology and factory paused |

The accepted PentaGreen preparation pairs are:

- `PRODUCT_PRICE` -> `product_price`;
- `PAYMENT_LINK` -> `payment_link`;
- `WEBHOOK_BINDING` -> `webhook_binding`;
- `CATALOG_SYNC` -> `catalog_sync`, a mirror/reconciliation workflow rather than broad provider-write authority.

Any other request/output pair must return or remain `HOLD_SPECIALIZED_EXECUTOR_REQUIRED`.

Checkout Sessions, customers, subscription plans, invoices, quotes, Connect mutations, application-fee bindings, standalone PaymentIntents, coupons, promotion codes, billing meters, Terminal, Identity, Financial Connections, Issuing, Treasury, and Radar are not executable through the generic factory path. Planning or readback may continue, but provider mutation requires a specialized typed executor, exact authority contract, tests, canary, compensation behavior, and read-after-write evidence.

Refunds, transfers, payouts, external-account changes, dispute disposition, material money routing, and final legal or rights commitments remain separately D3/human gated. The payout rail is currently `HOLD_DEFAULT_BANK_ERRORED` even though the Stripe account-level payout flag is enabled.

## MCP and API use

The official Stripe MCP endpoint is:

`https://mcp.stripe.com`

Use MCP for operator discovery, provider documentation, and bounded operations within the same capability policy. OAuth or a restricted key must be configured outside repository source. MCP identity must not become an application runtime identity or bypass PentaGreen, capability, D3, tax, rights, or product gates.

Server execution uses the private low-level request function only through `integration_control.stripe_os_provider_operation_v2`. The certified route pins `Stripe-Version: 2026-07-29.dahlia` and writes sanitized operation receipts. Do not expose or rebuild an arbitrary Stripe path/body tunnel.

## Account and credential routing

Use account roles, not hard-coded account IDs:

- `COMMERCE_PRIMARY`
- `SECONDARY_COMMERCE_EXPANSION`

A surface-specific override must be explicit and provider-verified. Connect account visibility does not establish mutation authority: the current readback observed four accounts, three accessible and one inaccessible.

Credential custody comes only from `integration_control.stripe_live_secret_lanes_v1`:

`HOT -> WARM -> COLD -> EMERGENCY`

- HOT is the current provider-verified route.
- WARM and COLD must be independently verified before failover.
- Same-material aliases do not create redundancy.
- EMERGENCY cannot auto-promote without same-account provider verification.
- Never wildcard-select a Stripe-looking secret.
- Never expose, return, log, commit, or project raw secret material.

## Product readiness gate

A profile may enter a one-product canary only after exact readback proves:

- product type `enabled_for_sale=true`;
- a provider-verified Stripe tax code;
- a legal taxability state of ready, verified, approved, certified, `taxable_verified`, or `not_taxable_verified`;
- `tax_behavior` is exactly `inclusive` or `exclusive`;
- rights state is ready;
- fulfillment state is ready;
- quality state is ready;
- route state is ready;
- custody state is ready;
- documentation state is ready;
- `stripe_entitlement_handler_ref` exists;
- `stripe_webhook_binding_key` exists;
- the exact handler/event matrix and a signed provider webhook canary pass.

The current source state has no eligible profiles: all 17 product types are disabled for sale, all tax profiles remain under jurisdiction review, and profiles lack the complete tax-behavior, entitlement-handler, webhook-binding, and automatic-tax decision evidence. Founder or D3 authority cannot manufacture those facts.

## Product and Price work

- Reconcile the provider mirrors before creation.
- Use an idempotency key bound to the executing CrownThrive request.
- Pin the certified Stripe API version in the typed server adapter.
- Preserve PentaSKU and PentaPrice as canonical identity.
- Use a successor Stripe Price when amount or recurring semantics change; do not rewrite economic history.
- Read the provider object back and bind the exact account scope before marking the request complete.
- Reconcile dependent Payment Links before activating a successor Price.

## Payment Links and fulfillment

- Do not grant entitlement from a success-page redirect.
- Require an exact webhook binding and verified provider-event receipt.
- Persist provider event IDs and make delivery idempotent.
- Read after write; a provider `2xx` alone is not institutional completion.
- Do not assume promotion-code readiness: 14 Payment Links allow promotion codes while the audited account has zero promotion codes.

## Webhooks

Reuse `integration_control.stripe_webhook_lanes_v3`; never create a second site-specific webhook control plane.

Every lane must have:

- stable lane identity;
- exact handler and event matrix;
- provider endpoint/readback evidence;
- correct signing-secret alias;
- raw-body signature verification;
- event-ID idempotency;
- bounded retry behavior;
- PentaWire/PentaHook routing;
- PentaReceipt/PentaReconcile completion;
- a passing signed canary;
- explicit compensation and recovery behavior.

The current provider topology has 16 enabled endpoints while the mirror has 15 endpoint records. A wildcard canary failed, and redundant coverage/API-version fragmentation remain. Prefer governed repair and reuse over endpoint churn.

## Capability adoption and D3

Read `integration_control.stripe_os_capability_adoption_v2` before work. It contains 30 capability rows; 16 have the literal autonomy state `d3_gated`. The capability policy marks 22 of 30 as requiring a D3/human gate; some of those 22 use a more specific legal-tax or specialized-executor hold label. A row can also be held by privacy review or degraded topology.

`provider_availability=active` never implies `provider_write_allowed=true`, `monetization_write_allowed=true`, or production certification. Products, Prices, Payment Links, and Webhooks are the only current provider-write families, and their factory paths remain paused.

## One-product canary and activation

1. Keep the scheduler paused and choose exactly one governed product profile.
2. Read back every sale, tax, legal, rights, fulfillment, quality, route, custody, docs, entitlement, and webhook gate.
3. Reconcile existing Stripe aliases and account scope.
4. Submit one idempotent supported request.
5. Run one bounded Commerce Binder item through the typed route.
6. Read the provider object back; prove no duplicate Product, Price, Payment Link, request, or queue row.
7. Deliver a signed test/natural provider event through the exact handler and prove entitlement/ledger reconciliation.
8. Append and read back the terminal receipt/DAIL evidence.
9. Obtain required human authorization for scheduler activation, then verify exactly one desired job and one live job.
10. Pause immediately on duplicate work, provider/mirror drift, a failed signed canary, missing entitlement, tax/legal drift, or payout/money-movement crossover.

Do not re-enable the factory merely because a rollback-only database canary passed; that proves contract mechanics, not a sale-ready product.

## Evidence and completion

A Stripe task is complete only after:

1. the exact CrownThrive authority and supported operation are bound;
2. the provider request is idempotent and accepted;
3. provider readback matches the intended object, account role, and API version;
4. the local mirror reconciles;
5. the signed event, entitlement, PentaReceipt, PentaReconcile, and PentaLedger state close when applicable;
6. CHLOM/DAIL append and readback succeed;
7. no secret appears in logs, docs, source, receipts, or public metadata.

## Optimization and learning

Use reconciled evidence to recommend conversion routing, payment-method eligibility, recurring versus one-time structures, catalog deduplication, price bands, failed-payment recovery, and webhook coverage. Learning stays inside an already-authorized capability; it cannot create legal, tax, rights, credential, money-movement, privacy, or D3 authority.

## Status references

- Mesh: `integration_control.pentagreen_stripe_mesh_v3`
- Runtime readiness: `integration_control.stripe_os_runtime_readiness_v2()`
- Capabilities: `integration_control.stripe_os_capabilities_v1`
- Adoption: `integration_control.stripe_os_capability_adoption_v2`
- Adapters: `integration_control.stripe_os_adapter_registry_v1`
- Credential lanes: `integration_control.stripe_live_secret_lanes_v1`
- Requests: `integration_control.pentagreen_stripe_monetization_requests_v1`
- Provider receipts: `integration_control.stripe_os_provider_operation_receipts_v2`
- Clock: `integration_control.pentagreen_stripe_clock_status_v1()`
- Docs: `/commerce/stripe-os-monetization-fabric`
