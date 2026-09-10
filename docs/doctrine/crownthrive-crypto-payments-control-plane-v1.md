# CrownThrive Crypto Payments Control Plane v1

**Status:** Canonical / Active  
**Parent:** CrownThrive Transaction Plane (CTTP v1)  
**Authority:** CHLOM Wallet + ThriveEvergreen ECAC  
**Doctrine ID:** `ct.doctrine.crownthrive.crypto-payments.v1`

## Purpose

The CrownThrive Crypto Payments Control Plane (CTCP) governs cryptocurrency and stablecoin payment acceptance, customer-wallet interactions, provider admission, settlement routing, reconciliation, and conversational payment intelligence across the CrownThrive estate.

CTCP is a payment and settlement system. It is not an autonomous trading system.

## Canon

1. Stablecoin-first. The canonical CrownThrive native settlement anchor is USDC on Base.
2. CHLOM Wallet is the wallet authority. It does not yield custody or policy authority to a payment processor.
3. Volatile-asset acceptance (for example BTC, ETH, SOL) defaults to an external processor that can settle into USDC or fiat unless a separately governed direct-wallet route is certified.
4. No hidden conversion, swap, bridge, staking, trading, signing, broadcast, capture, payout, or transfer is permitted merely because a provider can perform it.
5. Provider connectivity or provider success never manufactures economic authority.
6. Exact ThriveEvergreen ECAC is mandatory for economic execution. D3 and required human approval boundaries remain intact.
7. Credentials remain Vault-first and provider-specific. Candidate partners are not assigned credentials until admitted.
8. Every live provider requires explicit API, webhook, read-after-write, idempotency, reversal/refund, reconciliation, observability, compliance, and recovery certification before money movement.
9. Conversational MCP/API tools are read, quote, network-discovery, provider-discovery, and route-preview surfaces only unless a separately named mutation contract is independently certified.
10. Existing subscriptions and entitlements remain provider-sticky unless a deliberate migration is governed and evidenced.

## Hot / Warm / Cold

### Hot: CHLOM Wallet / Base USDC

The Hot crypto route is the internal policy and settlement anchor. The managed wallet is production-bound, Base-native, USDC-first, Vault-backed, and has a maximum unattended value of zero. Customer pay-in checkout still requires a separately certified customer-payment adapter and address/session lifecycle.

### Warm: Trust Wallet + MetaMask

Trust Wallet Agent Kit supplies read-only market, provider, and network-routing intelligence through the existing HMAC gateway. MetaMask Embedded Wallets supplies the customer-approved wallet mode. Conversational signing and broadcast are prohibited.

### Cold: External crypto-payment provider mesh

The Cold route is sealed until one or more external providers pass the admission contract. Provider admission is independent: a commercial relationship or API key does not automatically grant checkout, payout, or treasury authority.

## Conversational API / MCP surface

The canonical functions are:

- `public.ct_crypto_payment_api_v1(text,jsonb)`
- `public.ct_crypto_payment_mcp_call_v1(text,jsonb)`

The production conversation tools are:

- `crypto.rails.status`
- `crypto.partners.list`
- `crypto.assets.list`
- `crypto.wallet.status`
- `crypto.stripe.status`
- `crypto.trustwallet.price`
- `crypto.trustwallet.providers`
- `crypto.trustwallet.domains`
- `crypto.route.preview`

All schemas are closed with `additionalProperties=false`. These tools do not sign, broadcast, capture, transfer, payout, refund, swap, bridge, or move value.

## Asset policy

### Native anchor

- USDC / Base: native settlement anchor; direct custom-wallet settlement is permitted by policy, but customer checkout requires a separate certified adapter.

### External-processor-ready

- USDC: Ethereum, Solana, Polygon, Arbitrum, Optimism
- BTC: Bitcoin
- ETH: Ethereum
- SOL: Solana
- USDT: TRON

Volatile assets default to stablecoin or fiat settlement. USDP and USDG remain provider-documented holds until an admitted provider exposes them to CrownThrive and the exact route is certified.

## Provider admission registry

### Tier 0: Current CrownThrive estate

- CHLOM Wallet: active native wallet authority and Base/USDC settlement anchor.
- Trust Wallet Agent Kit: read-verified market/provider/network intelligence.
- MetaMask Embedded Wallets: configured user-approved wallet mode; frontend/allowlist gates remain.
- Stripe Stablecoin Payments: existing processor integration, but live Payment Method Configuration currently reports `crypto.available=false`; acceptance remains provider-enablement HOLD.

### Tier 1: Strategic admission candidates

- Coinbase Business: independent USDC checkout/payment links/invoicing rail.
- Circle / Circle Payments Network: USDC-native payment, settlement, wallet, quote, transaction and webhook infrastructure.
- MoonPay Commerce: broad-asset merchant checkout with stablecoin/fiat settlement options.
- Triple-A: regulated stablecoin acceptance and payout APIs with local-currency settlement.
- Fireblocks Flow: enterprise payment/orchestration infrastructure for broad wallet and asset acceptance, compliance, conversion and reconciliation.
- Bridge (Stripe): fiat/stablecoin orchestration and wallet infrastructure; useful but not independent processor redundancy from Stripe.

### Tier 2: Redundancy and coverage candidates

- BVNK
- CoinGate
- BitPay

### Tier 3: Long-tail candidate

- NOWPayments

No candidate is live or credentialed merely by appearing in this registry.

## Management architecture

CTCP manages the estate through ten layers:

1. **Partner Admission Registry** — commercial, compliance, credential, API, webhook and write certification state.
2. **Asset/Network Policy** — accepted assets, networks, direct-wallet permissions, conversion preferences, and confirmation policy.
3. **Route Resolver** — deterministic Hot/Warm/Cold and provider selection without execution.
4. **Provider Adapter Layer** — one bounded adapter per provider; no generic secret proxy.
5. **Wallet Authority Layer** — CHLOM Wallet, MetaMask customer mode, and Trust Wallet intelligence separated by authority.
6. **Webhook/Event Normalizer** — all provider events normalized into CrownThrive transaction semantics before entitlement or settlement effects.
7. **Settlement/Reconciliation Ledger** — provider amount, network fee, conversion fee, settlement asset, finality, internal allocation and entitlement correlation.
8. **Refund/Reversal/Dispute Plane** — provider-specific reversal events mapped to CHLOM entitlement and ledger consequences.
9. **Treasury Policy** — stablecoin retention, fiat conversion, liquidity, and payout policy under ECAC; no conversational trading authority.
10. **PentaDocs / DAIL / Observability** — immutable evidence, provider-readback receipts, route health, latency, failure state, and recovery history.

## Provider admission state machine

`candidate -> sandbox_verified -> credentials_bound -> api_read_verified -> webhook_verified -> bounded_write_verified -> reconciliation_verified -> production_admitted`

A provider that fails any required stage remains HOLD. Production admission never implies unrestricted money movement.

## Stripe-specific truth

The founder attestation that Stripe Crypto was enabled is preserved. The latest live Stripe Payment Method Configuration readback reports `crypto.available=false`, and the latest CrownThrive stablecoin checkout canary did not offer crypto. Therefore Stripe stablecoin checkout remains `HOLD_PROVIDER_ENABLEMENT` until Stripe itself exposes the payment method to the CrownThrive account and a fresh no-charge canary proves it.

## Public inspection surface

The Commerce Rail Lab contains the CTCP read-only public projection at:

`/functions/v1/crownthrive-commerce-rail-lab/crypto-control-plane`

The public projection contains no credentials, signing controls, private wallet material, provider mutation authority, or money-movement capability.
