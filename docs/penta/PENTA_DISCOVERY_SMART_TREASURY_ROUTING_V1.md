# PentaDiscovery + Smart Treasury Metered Routing v1

Status: production implementation contract

## Canonical semantics

- A **Penta** is the governed packet/envelope transmitted through PentaFabric.
- **PentaDiscovery** is the systemwide discovery, identification, classification, registration, pricing-handoff, and routing coordinator. It discovers and packages evidence; it does not manufacture authority.
- **PentaPay** converts certified execution/routing usage into priced obligations denominated in real currency. A pay obligation is not money-movement authority.
- **PentaTreasury / Smart Treasury** is the machine-banking control plane for internal-unit issuance, budget reservation, metering, reconciliation, settlement orchestration, and economic optimization.
- **CHLOM** is the authority bridge/metaprotocol between packet execution and any economic effect. DAIL preserves immutable evidence.
- External money movement remains exact-authority-only and requires the settlement authority fabric, independent approval where configured, provider readback, and finality evidence.

## PentaDiscovery family

PentaDiscovery coordinates PentaCrawler, PentaSearch, PentaQuery, PentaFetch, PentaGet, PentaParse, PentaResolve, PentaSignal, PentaContext, PentaCensus, and PentaHarvestor.

Operating loop:

`OBSERVE -> FINGERPRINT -> RESOLVE -> CLASSIFY -> REGISTER -> PACKAGE -> PRICE_ROUTE -> RESERVE -> DISPATCH -> ACK -> METER -> RECONCILE -> PAY_OBLIGATION -> RECEIPT`

## Mandatory packet economics

Each billable Penta route carries an economic envelope containing at least:

- `rate_key`
- `treasury_reservation_id`
- `sender_penta_id`
- `receiver_penta_id`
- `estimated_route_units`
- `actual_route_units`
- `provider_cost_minor`
- `currency`
- `hop_count`
- `max_hops`
- `route_class`
- `economic_effect`
- `settlement_state`
- `usage_event_ids[]`
- `receipt_refs[]`

Infrastructure-fault retries are internally non-billable. Actual third-party provider consumption remains accounted separately when incurred.

## Dynamic routing economics and anti-abuse

Routing prices are policy/rate-book driven, not hard-coded into agents. Prices may be adjusted through governed evidence from PentaDiscovery/PentaSignal/PentaCensus/PentaCosts/PentaLoad/PentaBalancer, subject to Executive/Legislative/Judicial reconciliation where policy requires it. Factors may include route class, payload size, risk, congestion, provider cost, retry provenance, abuse score, urgency, scarcity, and verified operating demand.

No Penta may mint authority, self-approve economic authority, convert internal units into spendable currency by itself, or inherit provider money-movement authority from a routing edge.

## Backward compatibility

Legacy `crownthrive.penta.event.v1` packets remain valid. Economic-envelope fields are additive. Unpriced legacy traffic uses the compatibility route and is marked `legacy_unpriced` until upgraded; no fake currency obligation is created.
