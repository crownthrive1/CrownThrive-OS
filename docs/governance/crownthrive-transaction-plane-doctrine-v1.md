# CrownThrive Transaction Plane Doctrine v1

**Contract:** `ct.transaction-plane.v1`  
**Doctrine:** `ct.doctrine.crownthrive.transaction-plane.v1`  
**Authority:** Founder directive, September 9, 2026  
**State:** Active

## Canonical commerce rails

| Rail | Canonical role | Primary use |
| --- | --- | --- |
| Stripe | Foundation | Platforms, marketplaces, services, physical commerce, invoices, events, Crown Credits top-ups, CrownThrive-controlled billing |
| Paddle | SaaS Merchant of Record | SaaS, software, AI products, international digital subscriptions |
| Lemon Squeezy | Digital Goods Merchant of Record | Downloads, plugins, templates, licenses, printables, bundles, rapid digital releases |
| PayPal | Choice + Payout | Buyer PayPal preference plus affiliate, ambassador, creator and vendor payout corridors |

## Transaction plane

All CrownThrive economic execution routes through the Transaction Plane. The plane composes PentaGreen routing, ThriveEvergreen/ECAC economic authority, CHLOM Wallet policy and entitlement authority, PentaWire route selection, provider-specific adapters, webhook/readback evidence, and DAIL.

A successful provider call never creates CrownThrive authority. Provider connectivity, provider-write capability, money-movement authority, rights authority, entitlement issuance, and settlement authority remain separate facts.

Existing subscriptions are provider-sticky. They are not round-robin failed over between Merchant-of-Record providers. A replacement provider may be selected only for eligible new transactions or through an explicit governed migration.

## Hot, warm and cold doctrine

Hot is the selected production route. Warm is a standby route. Cold is sealed and requires explicit activation. A route may not be labeled credential-redundant unless its credential material is independently distinct and independently authenticated.

Current credential truth:

- Paddle: independent Hot and Warm server credentials. Both authenticate independently. Cold is sealed and reuses the verified Warm server credential. The Paddle.js client token is never a server failover credential.
- PayPal CrownThrive: independent Hot and Warm LIVE credentials. Both authenticate independently. Cold is sealed and reuses Warm; no third independent PayPal credential is claimed.
- Stripe: Hot, Warm and original aliases resolve to the same live key material. This is continuity, not independent credential redundancy. Cross-provider transaction fallback is governed separately.
- Lemon Squeezy: one verified live credential. Hot is ready, Warm remains blocked, Cold is sealed. No recovery credential is fabricated.

## CHLOM Wallet transaction-plane modes

- Hot: CHLOM Wallet policy/entitlement plane. Ready.
- Warm: MetaMask Embedded Wallet / WalletConnect user-approved mode. Standby; user approval and ECAC remain required.
- Cold: managed Trust Wallet Agent Wallet recovery/execution mode. Sealed; exact ECAC and D3 boundaries remain.

The maximum unattended value remains zero. D3 and real-value execution retain their exact approval boundaries.

## Exact API and MCP surfaces

The Transaction Plane exposes new closed-contract Wallet operations for status, public-safe snapshot, deterministic route preview, policy status, Agent Wallet status and continuity status. Exact MCP tools are exposed on `ct.mcp.chlom-core`; legacy broad Wallet tools that were previously suspended remain suspended.

The CHLOM Wallet lab is also bound as controlled-test APIs for allocation preview, value-class preview, rights eligibility, provider-exit readiness, ThriveFund transition preview, signed Stripe webhook replay canary, HARP proof verification, EASOR settlement preview and portable-wallet verification.

No API or MCP surface forwards credential material to callers.

## Provider certification state

- Stripe: bounded provider-write control remains verified. Platform and connected-account production readback pass at HTTP 200.
- Paddle: bounded catalog write is verified. Hot created a canary product, Warm read it, Warm archived it, and Hot verified the archived state. No price or checkout was created and no money moved.
- PayPal: LIVE provider truth is current. Bounded order write is verified: Hot created an order, Warm authenticated and read the same order, and no authorization or capture occurred. Payout adapters remain separately ECAC/approval gated.
- Lemon Squeezy: authentication, store and catalog reads pass. Current live catalog contains zero products. Product creation is not exposed by the current provider/API adapter, so product writes and independent Warm credential redundancy remain fail-closed.

## Redundancy doctrine

Credential redundancy and provider redundancy are separate. Cross-provider fallback is product-specific, never blanket. The failover matrix must state whether a fallback is certified, conditional, wired-but-not-write-certified, or blocked. Existing subscriptions cannot silently change Merchant of Record.

## Public canary surface

The CrownThrive Commerce Rail Lab includes the CHLOM Wallet Transaction Plane Widget. The widget is read-only: it can display certification state and resolve route previews but cannot create checkout, sign, broadcast, transfer, payout, refund, or grant rights.
