# PentaAds / AdLuxe Network — Production Baseline v1

Status: **PRODUCTION**  
Provider: **AdLuxe Network**  
Contract: `ct.adluxe.pentaads.v1`  
Canonical publisher/inventory identity: `contact@crownthrive.com`  
Provider publisher ID: `58324`  
Central PentaAds inventory ID: `49942`  
Central inventory URL: `https://penta.crownthrive.io/advertising`

## Secret custody

The AdLuxe API credential is held only in Supabase Vault.

- Canonical secret reference: `supabase-vault:crownthrive/adluxe/pentaads/admin`
- Raw credential MUST NOT be copied to GitHub, Google Drive, Google Sheets, PentaDocs, application logs, analytics, browser code, client bundles, or agent memory.
- Runtime access is server-side through bounded AdLuxe adapters and `chlom_runtime.dail_http_v1`.
- Provider host is fixed to `https://api.adsrv.net/v2`.

## Production census at activation

- CrownThrive publisher inventory records: **27**
- Estate zones after PentaAds expansion: **149**
- Central PentaAds zones: **42**
- Central provider blueprints discovered: **43**
- Auto-materializable blueprints: **42**
- Custom banner blueprint: parameterized; explicit width/height required
- Reconciled campaigns: **22**
- Reconciled ads: **119**
- Reconciled transactions: **2,339**
- Payout records: **17**
- Finance anomalies quarantined: **2**

Every production zone is normalized into ThriveBase with provider state, evidence hash, pricing metadata, and the canonical internal revenue split.

## Revenue and accounting rule

Default revenue allocation is:

- Publisher attribution: **70%**
- CrownThrive network attribution: **30%**

This split is tracked even for CrownThrive-owned inventory so gross, publisher-attributed, and network-attributed economics remain independently observable.

Promotional credits are separate from cash. They are inventory-bound, non-refundable, non-cash entitlements and MUST NOT be counted as cash revenue or external publisher payout unless an explicit settlement rule says otherwise.

## Zone surface

PentaAds materializes provider-supported inventory without inventing unsupported dimensions.

Supported central formats include Banner, VAST, Direct link, Popup, Push notification, Interscroller, Interstitial, Slider, Sidebar, Push down, Footer marquee, Background, and In-Page notification.

The provider `Custom` banner size remains a parameterized template because AdLuxe requires explicit width and height.

## Dynamic pricing

Pricing is controlled by `PentaYield` and uses provider/current floor, observed AdLuxe gross eCPM, observed publisher eCPM, request volume, fill rate, format/size baseline, and bounded target-CPM-style adjustment.

Guardrails:

- minimum evidence threshold: **100 requests**
- maximum upward move per refresh: **25%**
- maximum downward move per refresh: **15%**
- no fabricated market floor
- new zones hold seeded floors until enough production traffic exists

Seed floors are market anchors, not guarantees. Yield converges from observed demand.

## HOT / WARM / COLD routes

### HOT — `ct.route.hot.pentaads.provider`

Direct provider inventory reads, bounded zone writes, mandatory read-after-write, and central PentaAds sync every 5 minutes.

### WARM — `ct.route.warm.pentaads.analytics`

Full estate reconciliation hourly, commercial reconciliation hourly, zone metrics refresh, dynamic pricing, and ThriveBase/CrownLytics-normalized state. The runtime route table exposes `hot|cold`; WARM uses HOT-class transport with `temperature=WARM` metadata.

### COLD — `ct.route.cold.pentaads.evidence`

Raw provider response snapshots, SHA-256 evidence, sync receipts, daily cold checkpoint, and DAIL/PentaVault institutional evidence. No raw secret is present in evidence snapshots.

## Scheduler topology

- `ct-pentaads-hot-central-sync-v1` — `*/5 * * * *`
- `ct-pentaads-warm-inventory-reconcile-v1` — `7 * * * *`
- `ct-pentaads-warm-pricing-v1` — `17 * * * *`
- `ct-pentaads-commercial-reconcile-v1` — `27 * * * *`
- `ct-pentaads-cold-checkpoint-v1` — `37 3 * * *`

## Penta family

Production/runtime: `PentaAds`, `PentaAdCatalog`, `PentaAdInventory`, `PentaZones`, `PentaYield`, `PentaAdLytics`, `PentaAdSync`, `PentaAdAssure`, `PentaAdScribe`.

Governed commercial: `PentaCampaign`, `PentaCreative`, `PentaPlacement`, `PentaSeed`, `PentaAttribution`, `PentaAdCredits`, `PentaAdFinance`, `PentaAdPayout`, `PentaAdPolicy`, `PentaAdSelf`.

## Authority boundaries

- D0/D1: provider discovery, catalog, readback, metrics, evidence
- D2: reversible zone/configuration writes, creative/campaign draft construction, promotional entitlement accounting
- D3: campaign activation that can incur spend, payments, payout execution, or other external money movement

PentaCampaign's provider draft entrypoint forcibly sets campaigns to **Pending + Paused**. PentaCreative's provider draft entrypoint forcibly sets ads to **Pending + inactive**. Neither entrypoint can activate spend.

## Runtime objects

Key database entrypoints:

- `integration_control.penta_ads_provider_get_v1`
- `integration_control.penta_ads_provider_write_v1`
- `integration_control.penta_ads_refresh_blueprints_v1`
- `integration_control.penta_ads_sync_site_v1`
- `integration_control.penta_ads_sync_inventory_v1`
- `integration_control.penta_ads_materialize_zone_blueprints_v1`
- `integration_control.penta_ads_refresh_zone_metrics_v1`
- `integration_control.penta_ads_pricing_cycle_v1`
- `integration_control.penta_ads_full_reconcile_v1`
- `integration_control.penta_ads_commercial_reconcile_v1`
- `integration_control.penta_ads_cold_checkpoint_v1`
- `integration_control.penta_ads_issue_credit_v1`
- `integration_control.penta_ads_reserve_credit_v1`
- `integration_control.penta_ads_consume_credit_v1`
- `integration_control.penta_ads_create_paused_campaign_v1`
- `integration_control.penta_ads_create_inactive_ad_v1`

## Creative/programmatic capability registry

Normalized creative contracts: image banner, HTML/JS banner, HTML5 ZIP, native, video banner, RTB banner, direct link, popup, VAST linear, RTB/VAST, and push. RTB/VAST surfaces are tagged programmatic. Intrusive and consent-sensitive surfaces remain policy-gated at placement time.

## Advertiser bonus programs

Spend-qualified programs do not auto-issue without verified paid spend:

| Program | Qualifying paid spend | Bonus | Cap |
|---|---:|---:|---:|
| Launch Bonus | $100 | 25% | $25 |
| Growth Bonus | $500 | 30% | $150 |
| Scale Bonus | $2,500 | 35% | $875 |
| Strategic Match | $10,000 | 50% | $5,000 |

Strategic Match is invite-only and requires governed/founder approval. All programs are inventory-bound, non-cash, non-refundable, and use an internal settlement model.

## Finance anomaly handling

Two historical AdLuxe payout records are quarantined because their amounts materially exceed normal operating history. They are evidence/reconciliation anomalies only and MUST NOT be treated as recognized revenue or automatically acted upon.

Payout account data is not mirrored to institutional spreadsheets. Normalized payout account identifiers are hashed in ThriveBase.

## Institutional mirror

Google Drive contains a PentaAds operations folder and native spreadsheet mirror with tabs for Control, Inventory, Zones, Pricing, Campaigns, Ads, Finance, and Evidence. The Sheet is a human/institutional mirror, not the production authority source. ThriveBase/provider readback remains canonical.

## Production recovery doctrine

- Writes are bounded by method, host, path, field allowlist, and CHLOM authority.
- Zone writes require provider read-after-write.
- Materialization is idempotent and per-zone failure isolated.
- A failed format must not roll back healthy zones.
- PentaAdSelf may repair D2 adapters/sync/pricing defects, then retry.
- Money movement never inherits repair authority.

## Activation evidence

First provider zone canary: Banner 468x60 Full Banner; HTTP 200; provider readback Approved + active; revenue rate 70%; secret export false.

The factory then converged every automatically materializable blueprint with zero remaining eligible central blueprints.

First sealed COLD production checkpoint:

- checkpoint ID: `624898e5-5352-455c-b11a-b1c786d48416`
- evidence SHA-256: `f76d0cdafa0739aa1909bd3676ccde638483e71d2ed7240d585887d12f55e27b`
- sites: 27
- estate zones: 149
- central zones: 42

## Operating objective

PentaAds is an OS-level advertising and monetization utility intended to increase monetizable inventory utilization, cross-ecosystem house fill, advertiser acquisition, programmatic demand compatibility, and attributable revenue while preserving evidence, policy, and financial authority boundaries.

Revenue targets are operating objectives, not guarantees. Forecasting must derive from observed requests, fill, impressions, realized eCPM/CPC/CPA, advertiser retention, and credit-adjusted cash economics.
