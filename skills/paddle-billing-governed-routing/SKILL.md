---
name: paddle-billing-governed-routing
description: Mandatory CrownThrive routing for any Paddle Billing catalog, checkout, pricing, webhook, subscription, customer-portal, billing-history, or sandbox task. Load the matching upstream paddle-* skill and use the Paddle MCP under fail-closed commerce controls.
---

# Paddle Billing governed routing

## Trigger

Use this skill for every CrownThrive task involving Paddle Billing. Paddle Classic is outside this integration.

This wrapper does not replace Paddle's ten implementation skills. It makes their use mandatory and adds CrownThrive's authority, evidence, privacy, and environment boundaries.

## Required routing

Load the exact upstream skill before implementation:

| Work | Required skill |
| --- | --- |
| Customer transaction or invoice history | `paddle-billing-history` |
| Products, prices, tax categories, or catalog seeding | `paddle-catalog-setup` |
| Web checkout | `paddle-checkout-web` |
| Hosted customer self-service | `paddle-customer-portal` |
| Localized pricing pages | `paddle-pricing-pages` |
| Sandbox canaries and end-to-end tests | `paddle-sandbox-testing` |
| Subscription cancellation | `paddle-subscription-cancel` |
| Customer and subscription mirroring | `paddle-subscription-sync` |
| Subscription upgrades, downgrades, or item changes | `paddle-subscription-update` |
| Webhook verification, idempotency, and retry | `paddle-webhooks` |

Use `paddle-docs` whenever current provider semantics, field shapes, events, permissions, or error behavior are material. When the MCP exposes `search` and `execute`, resolve the current method and parameter contract with `search` before calling `execute`.

## Environment invariant

1. Default to `paddle-sandbox`.
2. Name the selected environment in the work record and final receipt.
3. Never infer `paddle-live` from an existing credential, account connection, product ID, domain, or deployment.
4. A live read requires an authenticated eligible operator and task-level authorization.
5. A live mutation additionally requires explicit human direction for the exact operation, current CrownThrive authority, provider write permission, bounded scope, duplicate control, rollback or compensation, and provider readback.
6. If any required predicate is missing, return `HOLD` and continue only with source preparation, documentation, or sandbox-safe work.

## Secret and data boundary

- Resolve `PADDLE_SANDBOX_API_KEY` from the protected runtime or operator keychain. Never write, echo, serialize, commit, or return its value.
- Use OAuth for `paddle-live` in the eligible operator context. Do not turn an OAuth connection into general write authority.
- Minimize customer, payment, tax, dispute, payout, settlement, invoice, address, and business data.
- Keep restricted payloads out of public Git, screenshots, general logs, and DAIL. Record identifiers, digests, states, timestamps, and sanitized provider receipts instead.
- Never accept a customer, subscription, or transaction owner identifier from an untrusted client when it can be resolved server-side from the authenticated CrownThrive identity.

## Execution sequence

1. Resolve the matching Paddle skill.
2. Read current Paddle semantics through `paddle-docs` when material.
3. Resolve the requested environment; choose sandbox unless live was explicitly authorized.
4. Resolve identity, credential binding, exact-operation authority, data class, side effects, and rollback.
5. Use the named Paddle MCP. Prefer its current `search` contract before `execute`.
6. Perform the smallest bounded operation.
7. Read back the affected provider object or state.
8. Reconcile webhook, database, CHLOM, entitlement, and PentaGreen state only within separately granted authority.
9. Record a sanitized evidence receipt.
10. State unresolved provider, settlement, entitlement, rights, tax, legal, or production gates without promoting them.

## Completion boundary

MCP availability, authentication, a successful call, a checkout, or a webhook proves only the observed event within its scope. It does not independently prove:

- Paddle account-wide write authority;
- settlement or payout;
- CrownThrive entitlement delivery;
- CHLOM ownership or license rights;
- tax or legal sufficiency;
- revenue recognition;
- unrestricted production certification.

Do not mark the integration `PRODUCTION` until the exact source candidate, workspace/plugin activation, sandbox canary, live authorization posture, provider readback, downstream reconciliation, security review, and independent verification are all evidenced.
