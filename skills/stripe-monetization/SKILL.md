# CrownThrive Stripe Monetization Skill

Use this skill whenever a CrownThrive site, Penta, factory, marketplace, service, membership, event, digital product, creator/seller rail, invoice flow, or commercial workflow needs Stripe.

## Canonical rule

Stripe is an execution provider beneath **PentaGreen**. Never let a Stripe Product ID, Price ID, Payment Link ID, Checkout Session ID, connected-account ID, or subscription ID become CrownThrive's canonical economic identity.

Canonical owners:

- PentaSKU — SKU identity
- PentaCatalog — product catalog truth
- PentaPrice — price authority and evidence
- PentaCheckout — checkout configuration
- PentaInvoice — subscriptions and invoices
- PentaMarket — marketplace/platform economics
- PentaReceipt / PentaReconcile — provider-event reconciliation
- PentaLedger — institutional economic ledger
- PentaHook / PentaWire — webhook/event ingress and transport
- PentaCredentials — credential custody
- PentaRoute / PentaBridge — provider selection and normalization
- PentaGreen — final CrownThrive economic authority

## Start with current truth

Before creating or mutating Stripe state:

1. Read `integration_control.stripe_os_mesh_status_v1()`.
2. Read the relevant PentaGreen product/service/offer state.
3. Reuse the existing CrownThrive SKU, price evidence, catalog identity, entitlement model and owner lane.
4. Read current Stripe mirrors before provider calls:
   - `integration_control.stripe_catalog_products_v2`
   - `integration_control.stripe_catalog_prices_v2`
   - `integration_control.stripe_payment_link_inventory_v4`
   - `integration_control.stripe_webhook_lanes_v3`
5. Read open work/ownership so another Penta or site is not already executing the same subject.
6. Do not infer a hold from historical state when current provider/ThriveBase truth has superseded it.

## Account routing

Use provider roles, not hard-coded account IDs in application code:

1. `COMMERCE_PRIMARY` — first-party CrownThrive products, Checkout, Billing, subscriptions, invoices and general commerce.
2. `SECONDARY_COMMERCE_EXPANSION` — platform/Connect/expansion workloads when the product architecture requires that route.

A surface-specific override must be explicit and recorded in ThriveBase.

## Credential routing

Credential custody comes only from `integration_control.stripe_live_secret_lanes_v1`.

Selection order:

`HOT -> WARM -> COLD -> EMERGENCY`

Rules:

- HOT is the current provider-verified authority route.
- WARM is the first independent standby.
- A same-material recovery alias is continuity metadata, not an independent failover key.
- COLD is a separate provider-verified standby.
- EMERGENCY cannot auto-promote without same-account provider verification.
- Internal worker secrets never become Stripe provider authority merely because their names contain `stripe`.
- Never expose or return raw secret material.
- Never auto-delete, silently replace or auto-rotate founder-controlled Stripe credentials.

## Preferred integration path

For CrownThrive factories/sites, use the PentaGreen request contract rather than direct ad hoc Stripe creation:

```sql
select integration_control.pentagreen_stripe_prepare_monetization_v1(
  p_subject_type := 'penta_sku',
  p_subject_ref := '<canonical SKU>',
  p_request_type := 'PRODUCT_PRICE',
  p_requested_output := 'product_price',
  p_payload := jsonb_build_object(
    'pricing_authority','PentaPrice',
    'catalog_authority','PentaCatalog/PentaSKU',
    'checkout_authority','PentaCheckout'
  )
);
```

The function is idempotent and reuses the existing PentaGreen work queue and Commerce Binder role.

## Factory outputs

Supported request classes:

- `PRODUCT_PRICE` -> `product_price`
- `PAYMENT_LINK` -> `payment_link`
- `CHECKOUT_BINDING` -> `checkout`
- `SUBSCRIPTION_PLAN` -> `subscription`
- `INVOICE_OFFER` -> `invoice`
- `WEBHOOK_BINDING` -> `webhook_binding`
- `CONNECT_PLAN` -> `connect_plan`
- `REPRICE` -> `product_price` using a new Stripe Price object when amount semantics change
- `CATALOG_SYNC` -> `catalog_sync`

Do not create duplicate provider objects merely because an existing object is not yet mirrored. Reconcile first.

## Automatic monetization

The existing PentaGreen commerce clock invokes `integration_control.pentagreen_stripe_autowire_v1`.

Autowire is allowed only when the existing product profile has reconciled:

- rights;
- fulfillment;
- quality;
- route;
- custody;
- documentation;
- direct-checkout desired state.

If those states are not reconciled, do not invent monetization eligibility. The product remains in its existing PentaGreen work lanes and autowire waits.

## Checkout and fulfillment

- Prefer Stripe Checkout for standard web payment flows unless a custom Elements/PaymentIntent flow is required by the product.
- Never grant entitlement from the success-page redirect alone.
- Fulfillment-sensitive state comes from a verified provider webhook/event receipt.
- Persist provider event IDs and make event handling idempotent.
- Read after write; do not treat a 2xx mutation alone as final institutional completion.

## Subscriptions and Billing

- Bind recurring plans to CrownThrive offer/SKU/price identities.
- Subscription lifecycle changes must reconcile from provider events.
- Failed-payment recovery belongs to PentaInvoice/PentaNurture or the product-specific customer-success lane.
- Do not silently convert recurring cadence or product scope.
- Price changes generally create a successor provider Price object; preserve prior Price lineage.

## Invoices and quotes

- Use invoices for sales-led or contract-backed collection when Checkout is not the appropriate rail.
- Quote creation may be automated for governed offers, but accepting or changing final legal/commercial terms follows the owner lane.
- Invoice finalization/send must preserve customer identity, terms and provider readback.

## Connect

Before selecting a Connect charge model, resolve the marketplace/SaaS economic architecture and liability owner.

Possible models include direct charges, destination charges, and separate charges/transfers. Do not switch among them casually: fees, refunds, disputes, merchant-of-record responsibilities, connected-account balances and reporting differ.

Allowed autonomous scope:

- prepare connected-account/onboarding plan;
- read capabilities/requirements;
- create bounded platform configuration under an existing approved marketplace/SaaS model;
- bind application-fee configuration where the economic model already authorizes it.

Reserved scope:

- material payout routing;
- transfers of funds;
- bank/external account changes;
- liability-altering or legal/economic model changes.

## Webhooks

Reuse `integration_control.stripe_webhook_lanes_v3`; do not create a second site-specific webhook control plane.

Every webhook lane must have:

- stable lane key;
- explicit handler;
- provider endpoint/readback evidence;
- correct signing-secret alias;
- raw-body signature verification;
- event-ID idempotency;
- PentaWire/PentaHook routing;
- PentaReceipt/PentaReconcile institutionalization;
- exact recovery/rollback behavior.

Endpoint create/delete is topology- and provider-capacity-bound. Prefer reusing or updating existing provider endpoints when safe.

## Provider interfaces

Use the adapter registry:

- `ct.adapter.stripe.mcp.v1` — operator/API discovery and governed Stripe MCP calls.
- `ct.adapter.stripe.runtime.v1` — CrownThrive-owned server API wrapper.
- `ct.adapter.stripe.webhook.v3` — signed provider-event ingress.
- `ct.adapter.stripe.catalog-mirror.v2` — canonical provider mirrors.

Do not clone or represent Stripe's proprietary backend as CrownThrive software. CrownThrive may own its adapters, workers, contracts, SDK wrappers, mirrors, tests, schemas, webhook routers, recovery logic and provider-neutral interfaces.

## Capability policy

Read `integration_control.stripe_os_capabilities_v1` before provider writes.

Catalog/checkout/billing configuration can execute autonomously when `monetization_write_allowed=true` and the underlying CrownThrive offer is already governed.

Specialized human/D3 effects remain separate even under founder monetization authority:

- refunds;
- transfers and payouts;
- bank/external-account changes;
- dispute disposition;
- consequential payment-intent/customer charging outside a governed order;
- material application-fee or money-routing changes;
- final legal or rights commitments.

## Evidence and completion

A Stripe task is institutionally complete only after:

1. provider request accepted;
2. provider readback matches intended state;
3. local mirror reconciles;
4. PentaGreen/PentaReceipt/PentaLedger state updates as applicable;
5. webhook/event validation is complete when applicable;
6. CHLOM/DAIL append + readback succeeds;
7. no secret was projected into logs/docs/source.

## Optimization / learning

Use reconciled evidence to improve recommendations for:

- one-time vs recurring billing;
- Checkout vs invoice;
- payment-method eligibility;
- geographic payment options;
- failed-payment recovery;
- conversion optimization;
- catalog deduplication;
- price-band proposals;
- marketplace vs first-party routing;
- webhook/event coverage.

Learning can select within already-authorized capability boundaries. It cannot manufacture new economic, legal, credential, money-movement or rights authority.

## Status references

- Mesh: `integration_control.pentagreen_stripe_mesh_v3`
- Capabilities: `integration_control.stripe_os_capabilities_v1`
- Adapters: `integration_control.stripe_os_adapter_registry_v1`
- Credential lanes: `integration_control.stripe_live_secret_lanes_v1`
- Requests: `integration_control.pentagreen_stripe_monetization_requests_v1`
- Status: `integration_control.stripe_os_mesh_status_v1()`
- Clock: `integration_control.pentagreen_stripe_clock_status_v1()`
- Docs: `/commerce/stripe-os-monetization-fabric`
