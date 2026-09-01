# Stripe Provider Adapter Plan

This directory defines CrownThrive-owned integration code around Stripe. It does **not** clone Stripe's proprietary backend.

## Objective

Make Stripe plug-and-play for CrownThrive sites, PentaFactory outputs, marketplaces, SaaS surfaces, subscriptions, invoices, events and digital commerce while retaining provider portability and PentaGreen economic authority.

## Adapter families

### `ct.adapter.stripe.mcp.v1`

Operator/API surface for discovering current Stripe capabilities and performing governed provider operations through the connected Stripe MCP.

Use for:

- current account/capability readback;
- provider API discovery;
- bounded operator writes;
- integration planning and provider-documentation lookup.

Do not use MCP identity as application runtime identity.

### `ct.adapter.stripe.runtime.v1`

CrownThrive-owned server-side REST/SDK abstraction for production application workloads.

Required behavior:

- server-side only;
- credential resolution from `stripe_live_secret_lanes_v1`;
- HOT -> WARM -> COLD routing;
- EMERGENCY route only after provider verification;
- idempotency keys for retriable writes;
- bounded timeouts/backoff;
- explicit provider account role;
- read-after-write;
- provider response normalization;
- no raw credential return/logging.

### `ct.adapter.stripe.webhook.v3`

Signed event ingress and routing through existing PentaHook/PentaWire infrastructure.

Required behavior:

- stable lane identity;
- raw request body preserved for signature verification;
- correct lane-specific signing secret;
- provider event ID dedupe;
- append-only receipt;
- no fulfillment from redirect-only evidence;
- replay-safe downstream routing;
- PentaReceipt/PentaReconcile completion.

### `ct.adapter.stripe.catalog-mirror.v2`

Provider mirror for products, prices and Payment Links. The mirror does not become canonical CrownThrive catalog authority.

Existing sources:

- `integration_control.stripe_catalog_products_v2`
- `integration_control.stripe_catalog_prices_v2`
- `integration_control.stripe_payment_link_inventory_v4`
- `integration_control.pentagreen_stripe_catalog_bridge_v1`

## Provider-neutral application contract

Applications should request economic intent from CrownThrive, not call Stripe objects directly.

Example:

```text
PentaFactory/site
  -> PentaGreen request
  -> Commerce Binder
  -> PentaRoute
  -> Stripe adapter
  -> Stripe provider
  -> signed webhook/readback
  -> PentaReceipt/Reconcile
  -> entitlement/ledger
```

A future payment provider can implement the same CrownThrive economic contract without rewriting PentaSKU/PentaPrice/PentaCatalog identity.

## Account selection

Runtime code selects account **roles**, never embedded provider account IDs:

- `COMMERCE_PRIMARY`
- `SECONDARY_COMMERCE_EXPANSION`

Account IDs belong in provider configuration/ThriveBase projections only.

## Credential selection

Never search the vault with a wildcard like `%stripe%` and pick an arbitrary key.

Always resolve from the governed credential-lane table:

```text
HOT -> WARM -> COLD -> EMERGENCY
```

Same-material aliases do not count as independent failover.

## Product factory integration

Factories submit work through:

`integration_control.pentagreen_stripe_prepare_monetization_v1`

The existing PentaGreen commerce clock calls:

`integration_control.pentagreen_stripe_autowire_v1`

Autowire waits for existing rights, fulfillment, quality, route, custody and docs reconciliation; it does not bypass those product gates.

## Connect architecture

Charge model is an economic architecture choice, not merely an API parameter. Before implementing a platform flow, bind the subject to its approved model:

- direct charge;
- destination charge;
- separate charge and transfer;
- SaaS/platform fee model.

Do not silently switch models because disputes, refunds, merchant balance, fees and liability differ.

## Monetization authority

Current founder authority clears global provider-configuration holds for already-governed monetization work such as:

- Product/Price creation;
- Checkout and Payment Link binding;
- subscription plan configuration;
- invoice configuration;
- webhook route binding;
- catalog synchronization;
- bounded Connect planning/onboarding configuration.

It does not collapse specialized controls for:

- refunds;
- transfers/payouts;
- bank or external-account changes;
- dispute disposition;
- material money routing;
- final legal/rights commitments.

## Testing

Every adapter must prove:

1. wrong/missing authority fails closed;
2. no raw secret appears in outputs;
3. idempotent retries do not duplicate provider objects;
4. read-after-write validates the final provider state;
5. webhook duplicate delivery is safe;
6. account-role routing is deterministic;
7. HOT failure does not automatically promote unverified EMERGENCY material;
8. a Stripe provider ID never replaces CrownThrive canonical SKU/offer identity.

## Recovery

Recovery order:

1. read current ThriveBase mesh status;
2. verify current Stripe account/provider state;
3. verify current credential lane and provider response;
4. fail over HOT -> WARM -> COLD only with exact evidence;
5. do not auto-promote EMERGENCY;
6. reconcile provider objects and webhook endpoints;
7. verify local mirrors and entitlements;
8. append/read back DAIL terminal state.
