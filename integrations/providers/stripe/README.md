# Stripe Provider Adapter Plan

This directory defines CrownThrive-owned integration code around Stripe. Stripe is an external financial-infrastructure provider beneath PentaGreen; this adapter does not clone Stripe's proprietary backend or establish a public strategic-partner claim.

## Current state

The canonical CrownThrive adapter is `ct.adapter.stripe.v1`, component version `2.0.0`, with four transport variants:

| Variant | Current role | State |
| --- | --- | --- |
| `ct.adapter.stripe.mcp.v1` | Operator discovery and governed MCP use | Active for operator use; not application runtime identity |
| `ct.adapter.stripe.runtime.v1` | Typed server-side provider operations | Active for Product, Price, and Payment Link operations; factory paused |
| `ct.adapter.stripe.webhook.v3` | Signed webhook reconciliation | Active with degraded provider topology; factory paused |
| `ct.adapter.stripe.catalog-mirror.v2` | Products, Prices, Payment Links, and endpoint mirrors | Active with reconciliation lag |

The variants do not create independent authority. PentaRoute resolves the transport under the canonical adapter and the operation's exact capability, account role, authority, and readiness evidence.

The official Stripe MCP endpoint is `https://mcp.stripe.com`. OAuth or a restricted Stripe key is resolved outside source. Never commit an MCP authorization header, secret key, Connect token, or webhook signing secret.

## Executable boundary

Only these provider-write families have a typed CrownThrive execution route:

| Family | Typed route | Current factory state |
| --- | --- | --- |
| Product | `integration_control.stripe_os_provider_operation_v2` | Ready at adapter level; factory clock paused |
| Price | `integration_control.stripe_os_provider_operation_v2` | Ready at adapter level; factory clock paused |
| Payment Link | `integration_control.stripe_os_provider_operation_v2` | Ready at adapter level; factory clock paused |
| Webhook | `integration_control.stripe_webhook_provider_reconcile_v3` | Reconcile route exists; topology degraded and factory paused |

The low-level provider request is private to the typed runtime. There is no general service-role tunnel for arbitrary Stripe paths, query parameters, or request bodies. The server route pins `Stripe-Version: 2026-07-29.dahlia` and appends sanitized operation evidence to `integration_control.stripe_os_provider_operation_receipts_v2`.

Checkout Sessions, customers, subscriptions, invoices, quotes, Connect mutations, application fees, coupons, promotion codes, billing meters, standalone PaymentIntents, Terminal, Identity, Financial Connections, Issuing, Treasury, and Radar are not generic factory outputs. They remain read-only, planning-only, D3-gated, or `HOLD_SPECIALIZED_EXECUTOR_REQUIRED` until an operation-specific executor, authority contract, tests, canary, compensation behavior, and readback are certified.

Tax writes and money movement are separately held. The payout rail is `HOLD_DEFAULT_BANK_ERRORED`; account-level payout enablement is not proof that the settlement rail is healthy.

## Provider and mirror inventory

Observed production evidence is intentionally separated from CrownThrive mirrors:

| Surface | Stripe provider readback | CrownThrive mirror | Reconciliation note |
| --- | ---: | ---: | --- |
| Products | 459 total / 434 active | 456 | 131 active products lack a default Price; 8 active products have no list Price |
| Prices | 484 total / 465 active | 478 | 384 active Prices lack a lookup key; 107 mirrored Prices lack account scope |
| Payment Links | 48 total / 33 active | 48 | 15 inactive; duplicate configurations remain |
| Webhook endpoints | 16 enabled | 15 endpoint records | Wildcard canary failed; redundant coverage and API-version fragmentation remain |

The live capability-adoption registry contains 30 rows. Sixteen have the literal autonomy state `d3_gated`; the underlying capability policy marks 22 of 30 as requiring a D3/human gate. Some of those 22 use a more specific legal-tax or specialized-executor hold label instead of the literal D3 adoption label.

## Provider-neutral application contract

Applications request CrownThrive economic intent rather than arbitrary Stripe objects:

```text
PentaFactory/site
  -> PentaGreen request
  -> readiness gates
  -> Commerce Binder
  -> canonical Stripe adapter
  -> typed provider operation
  -> provider readback / signed webhook
  -> PentaReceipt + PentaReconcile
  -> entitlement + ledger
```

A future payment provider can implement the CrownThrive economic contract without replacing PentaSKU, PentaPrice, PentaCatalog, entitlement, or ledger identity.

## Account and credential routing

Runtime code selects account roles, never embedded provider account IDs:

- `COMMERCE_PRIMARY`
- `SECONDARY_COMMERCE_EXPANSION`

An account flag or provider capability is availability evidence, not operation authority. The exact route must be reverified before each provider write.

Credentials resolve only from `integration_control.stripe_live_secret_lanes_v1`:

```text
HOT -> WARM -> COLD -> EMERGENCY
```

Never wildcard-search for a Stripe-looking secret. Same-material aliases are continuity metadata, not independent failover. EMERGENCY cannot auto-promote without same-account provider verification.

## Factory integration and readiness

Factories prepare idempotent work through:

`integration_control.pentagreen_stripe_prepare_monetization_v1`

The accepted request/output pairs are:

- `PRODUCT_PRICE` -> `product_price`;
- `PAYMENT_LINK` -> `payment_link`;
- `WEBHOOK_BINDING` -> `webhook_binding`;
- `CATALOG_SYNC` -> `catalog_sync` for read/reconciliation work.

The PentaGreen commerce clock is intentionally paused. Current readiness is zero eligible profiles out of 1,042. A profile must independently prove all of the following before a Product/Price or Payment Link can enter the one-product canary:

- its product type is enabled for sale;
- its tax profile has a provider-verified Stripe code and a legally ready taxability state;
- `tax_behavior` is explicitly `inclusive` or `exclusive`;
- rights, fulfillment, quality, route, custody, and documentation states are ready;
- an entitlement handler reference exists;
- a stable webhook binding, exact handler/event matrix, and signed provider canary are verified.

Founder or D3 authority does not substitute for missing legal, rights, tax, fulfillment, entitlement, webhook, or evidence state.

## Testing

Every adapter change must prove:

1. wrong or missing authority fails closed;
2. unsupported resource/path combinations fail before a provider request;
3. no raw secret appears in output, receipts, logs, docs, or source;
4. idempotent retries do not duplicate provider objects;
5. provider read-after-write matches the intended object and account role;
6. webhook signatures and duplicate delivery are safe;
7. HOT failure does not promote unverified EMERGENCY material;
8. a Stripe provider ID never replaces CrownThrive identity;
9. a rollback-only canary leaves no queue, request, or provider residue;
10. factory-clock activation remains false until an authorized one-product canary closes cleanly.

## Recovery

1. Read `integration_control.stripe_os_runtime_readiness_v2()` and the current mesh record.
2. Keep the factory clock paused while any legal, product, entitlement, webhook, custody, or payout hold remains.
3. Verify the current Stripe account role, credential lane, provider API version, and supported typed operation.
4. Fail over HOT -> WARM -> COLD only with exact provider evidence; never auto-promote EMERGENCY.
5. Reconcile provider objects and endpoints without deleting economic history.
6. Verify local mirrors, signed event evidence, entitlements, and receipts.
7. Append and read back the terminal DAIL state.

Re-enable the commerce clock only after one governed product passes every gate, executes through the typed route, reconciles without duplication, proves signed fulfillment/entitlement behavior, and receives the required human authorization for scheduler activation.
