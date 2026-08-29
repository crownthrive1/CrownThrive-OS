# Locticians Digital Product Syndication

## Purpose

The Locticians digital-product fabric converts verified CrownThrive products, downloads, editions, consultations, and productized services into complete Brilliant Directories listings. It is a commerce syndication lane, not a second payment authority.

The production provider binding is:

- Brilliant Directories publisher: `user_id=5`
- Post type: **Digital Products and Services**
- `data_id=73`
- `data_type=4`
- Public collection: `/digital-products`

## Release rule

A listing can enter production only when all of the following are current:

1. The product identity and deliverables are verified.
2. The price, currency, Stripe product, Stripe price, and Stripe Payment Link agree.
3. Checkout is active and publicly reachable.
4. Fulfillment and entitlement behavior is verified or explicitly governed as a manual service workflow.
5. The listing image is CrownThrive-owned, licensed, or provider-permitted and publicly readable.
6. The copy states the buyer outcome and material boundaries without fake reviews, scarcity, discounts, guarantees, or rights claims.
7. A provider category, SEO metadata, internal links, and community context are bound.
8. An independent audit approves the package.
9. Brilliant Directories accepts the record and exact readback verifies `post_url`, `post_promo`, provider identity, publication date, content, category, image, SEO fields, and homepage state.

Unverified products remain blocked. A failed checkout or provider mismatch causes hold or unpublished containment; the runtime never blindly retries a provider mutation.

## Payment authority

The active production listings use existing, verified Stripe Payment Links. Stripe remains the payment authority, while CrownThrive fulfillment and entitlement controls remain the delivery authority.

Brilliant Directories documents native digital-product payments, protected thank-you delivery, buyer and administrator emails, multiple images, promo codes, order history, Form Manager, and checkout-form customization. The Locticians API schema currently verified for `data_id=73`, `data_type=4` exposes generic post fields but not the native pricing, order, delivery, or entitlement configuration needed to reproduce that behavior safely through the API. Native Brilliant Directories payment creation therefore remains fail-closed until an exact purchase-and-fulfillment canary proves those fields and side effects.

Forms may collect governed intake information. They do not create a parallel payment authority, replace required checkout fields, or admit arbitrary script, iframe, or nested-form injection.

## Daily schedule

The policy permits at most ten new listings per Eastern calendar day. The first batch is hourly from 8:00 AM through 5:00 PM Eastern.

Future batches are produced only from newly eligible sources. The product mesh is evaluated against quality, fulfillment, rights, route, custody, documentation, tax, price, and active-checkout evidence. Products that do not pass remain visible to the certification work queue but are not listed.

## Product package

Each listing includes:

- conversion-focused title and opening;
- exact current price;
- included deliverables;
- intended buyer or use case;
- Locticians and CrownThrive ecosystem relevance;
- secure Stripe checkout link;
- fulfillment explanation;
- rights, scope, and outcome boundaries;
- provider category;
- SEO title, description, keywords, and smart tags;
- at least three governed internal links;
- a rights-verified product image;
- an evidence packet binding product, checkout, price, entitlement, fulfillment, and source page.

## Lifecycle

```text
Stripe Payment Link read-only sync
    → product-mesh crosswalk
    → source and rights certification
    → conversion profile
    → daily scheduler
    → universal Locticians package
    → media verification
    → independent product audit
    → provider create-or-reconcile
    → exact provider readback
    → checkout and listing monitoring
    → opt-in nurture and periodic refresh
```

## Nurture

Every provider-verified listing receives six governed actions:

- price and availability verification every six hours;
- listing readback one hour after scheduled publication;
- newsletter syndication after twenty-four hours for opted-in audiences only;
- owned-channel distribution after seven days;
- conversion review after fourteen days;
- SEO refresh after thirty days.

No nurture action contacts a buyer directly without a valid consent and communication basis.

## Runtime

| Capability | Function |
|---|---|
| Stripe Payment Link sync | `stripe-payment-link-sync-v4` |
| Stripe snapshot reconciliation | `integration_control.locticians_digital_product_stripe_snapshot_reconcile_v1` |
| Checkout verification | `public.locticians_digital_product_checkout_verify_tick_v1` |
| Daily scheduling | `public.locticians_digital_product_schedule_batch_v1` |
| Orchestration | `public.locticians_digital_product_orchestration_tick_v1` |
| Independent audit | `public.locticians_digital_product_audit_tick_v1` |
| Provider publication | `public.locticians_digital_product_publish_tick_v1` |
| Nurture | `public.locticians_digital_product_nurture_tick_v1` |
| Status | `public.locticians_digital_product_status_v1` |
| Provider create/reconcile | `integration_control.locticians_universal_provider_create_or_reconcile_v4` |
| Provider reverification | `integration_control.locticians_universal_reverify_one_v4` |

## Clocks

| Job | Schedule |
|---|---|
| Stripe Payment Link sync | `1 */6 * * *` |
| Checkout verification | `7 */6 * * *` |
| Listing orchestration | `9,19,29,39,49,59 * * * *` |
| Nurture and refresh | `11,26,41,56 * * * *` |

## Initial production batch

The first batch contains ten verified offers and provider post IDs `4202` through `4211`. It includes four Go Flipbooks tiers, two Virality Music personal-use art products, two governed digital archive editions, a licensing discovery brief, and a creative/catalog consultation.

The full machine-readable contract is `data/penta/locticians-digital-product-syndication.v1.json`.