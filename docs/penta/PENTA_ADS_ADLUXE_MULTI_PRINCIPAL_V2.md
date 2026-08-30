# PentaAds / AdLuxe Network — Multi-Principal Authority Baseline v2

Status: **PRODUCTION CERTIFIED**  
Contract: `ct.adluxe.pentaads.v2`  
Provider API docs: `https://adserver.online/api`  
Provider reporting reference: `https://adserver.online/article/reporting-and-analytics`

This document supplements `PENTA_ADS_ADLUXE_PRODUCTION_V1.md` and records the production authority model after adding separate PentaAds Manager and Publisher API principals.

## Credential custody

Three AdLuxe credentials are held only in Supabase Vault. Raw token values are forbidden from GitHub, Drive, Sheets, logs, client code, analytics, documentation, browser bundles, or agent memory.

| Lane | Vault reference | Purpose | Authority |
|---|---|---|---|
| Estate Control | `supabase-vault:crownthrive/adluxe/pentaads/admin` | Canonical controller for the existing CrownThrive AdLuxe estate | D2; D3 money movement separately gated |
| Publisher | `supabase-vault:crownthrive/adluxe/pentaads/publisher` | Least-privilege independent inventory and publisher-statistics readback | D1 |
| Manager | `supabase-vault:crownthrive/adluxe/pentaads/manager` | Separate management principal; authenticated but currently isolated/unassigned from existing estate objects | D2 capability ceiling; no current-estate write eligibility |

No lane automatically escalates to another lane.

## Evidence-backed routing decision

The new Publisher token is not valid on the generic management routes. Generic `/stats` and `/site` returned HTTP 403, while the publisher-specific routes work:

- `/publish/site` — HTTP 200
- `/publish/zone/{id}` — HTTP 200
- `/publish/stats` — HTTP 200

Therefore Publisher is bound only to the provider's publisher-specific surfaces.

The new Manager token authenticates successfully on generic management endpoints but currently returns empty object sets:

- `/site` — HTTP 200, zero assigned sites
- `/campaign` — HTTP 200, zero assigned campaigns
- `/user` — HTTP 200, zero assigned users

The manager self-service advertiser route tested returned HTTP 403. Manager is classified `AUTHENTICATED_ISOLATED` rather than broken. It must not be used for current-estate writes until provider assignment grants visible objects.

The original full-scope PentaAds credential remains Estate Control because it has proven visibility and bounded write authority over the live estate.

## Independent publisher verification

`integration_control.penta_ads_publisher_readback_cycle_v2()` compares the Publisher principal's object IDs against the canonical Estate Control census.

First certified readback:

- Publisher sites: **27**
- Canonical sites: **27**
- Publisher zones: **149**
- Canonical zones: **149**
- Site ID mismatches: **0**
- Zone ID mismatches: **0**
- State: **PASS**
- Evidence SHA-256: `99cce9819743f0e76e4b1c5c439a6d641ec319c269c744146d36623a69493d80`

This creates independent least-privilege verification of the inventory controlled by the full estate credential.

## Publisher statistics lane

Publisher statistics are pulled from `/publish/stats` and stored separately from full network statistics.

The 7-day certification readback returned:

- publisher stats rows: **28**
- publisher impressions: **764**
- publisher revenue: **$5.348**

Publisher CPM and publisher revenue are kept distinct from advertiser spend and network/owner revenue.

## Statistics semantic correction

Adserver.Online defines:

- **Fill rate** = Responses / Requests
- **Remnant** = requests that ended without an ad
- **Passback** = requests that returned a passback tag
- **Render rate** = Impressions / Responses
- **Publisher revenue** = `P.revenue`
- **Owner revenue** = Advertiser Spend - Publisher Revenue
- **rCPM** = Owner Revenue / Impressions × 1000

The original PentaAds metrics implementation used Impressions / Requests as `fill_rate`. That was semantically incorrect and has been repaired.

Because the default management stats payload does not expose a direct `responses` field, PentaAds now stores a labeled proxy:

`fill_rate_proxy = (requests - remnant - passback) / requests`

and a render proxy:

`render_rate_proxy = impressions / served_requests_proxy`

The proxy is explicitly labeled and MUST NOT be represented as provider-native fill rate.

For the leading 7-day Locticians zone at certification:

- requests: 932
- remnant: 79
- passback: 0
- served-request proxy: 853
- impressions: 305
- fill proxy: 91.52%
- render proxy: 35.76%
- advertiser/gross CPM: $10
- publisher CPM: $7
- network rCPM: $3
- spend/gross amount: $3.05
- publisher revenue: $2.135
- network revenue: $0.915

This preserves the 70/30 economic model while keeping delivery semantics accurate.

## Runtime entrypoints

Multi-principal control:

- `integration_control.penta_ads_provider_get_lane_v2`
- `integration_control.penta_ads_provider_get_v1` — canonical Estate Control compatibility read
- `integration_control.penta_ads_provider_write_v1` — bounded Estate Control zone write with estate + Publisher readback
- `integration_control.penta_ads_publisher_readback_cycle_v2`
- `integration_control.penta_ads_manager_health_cycle_v2`
- `integration_control.penta_ads_release_certify_v2`

Stats:

- `integration_control.penta_ads_refresh_zone_metrics_v1`
- `public.penta_ads_zone_metrics_latest_v2`
- `public.penta_ads_publisher_zone_stats_v2`
- `public.penta_ads_publisher_readbacks_v2`
- `public.penta_ads_manager_health_v2`

Credential registry:

- `integration_control.penta_ads_credential_lanes_v2`
- `public.penta_ads_credential_lanes_v2`

## Scheduler topology v2

Seven PentaAds schedulers are active:

- `ct-pentaads-hot-central-sync-v1` — every 5 minutes
- `ct-pentaads-publisher-readback-v2` — minute 2, 17, 32, 47 each hour
- `ct-pentaads-warm-inventory-reconcile-v1` — minute 7 hourly
- `ct-pentaads-warm-pricing-v1` — minute 17 hourly
- `ct-pentaads-commercial-reconcile-v1` — minute 27 hourly
- `ct-pentaads-manager-health-v2` — minute 52 hourly
- `ct-pentaads-cold-checkpoint-v1` — daily 03:37

## Write authority

Current-estate provider writes remain on Estate Control because that credential has proven object visibility and production read-after-write history.

A successful Estate Control zone write requires:

1. strict host/path/method/field allowlist
2. D2 authority
3. provider write success
4. Estate Control readback
5. independent Publisher `/publish/zone/{id}` readback when available
6. evidence snapshot with no credential material

Manager writes are prohibited against the current estate while its assignment state is `AUTHENTICATED_ISOLATED`.

D3 actions remain separately gated:

- campaign activation that incurs spend
- payments
- payouts
- external money movement

## Production census

The underlying estate remains stable after the credential expansion:

- sites: **27**
- estate zones: **149**
- central PentaAds zones: **42**
- campaigns: **22**
- ads: **119**
- transactions: **2,339**
- payouts: **17**
- quarantined finance anomalies: **2**

No inventory was duplicated or removed by the credential migration.

## Release certification v2

Certification state: **PASS**

Receipt ID: `61506ff9-4e02-4570-9207-2cb7db0e3ab0`

Evidence SHA-256: `409b73f1e9e0773489415952079f2d29fd5a6cc8e996474788c493f5c3bc7d78`

Certified invariants:

- 3/3 active authority lanes verified
- Publisher independent readback PASS
- 0 publisher site mismatches
- 0 publisher zone mismatches
- Manager = AUTHENTICATED_ISOLATED
- 7/7 PentaAds schedulers active
- 28 corrected metric rows present
- 27 sites / 149 zones / 42 central zones preserved
- 22 campaigns / 119 ads / 2,339 transactions preserved
- secret_exported = false

## Institutional mirror

The existing PentaAds Google Sheet now includes two additional tabs:

- `Credentials` — Vault references, scopes, lane state and authority boundaries; never raw tokens
- `Stats v2` — corrected delivery/economic metrics separating remnant, passback, fill proxy, render proxy, publisher revenue and network rCPM

Drive remains a mirror. ThriveBase plus provider readback remains authoritative.

## Doctrine

Use the lowest-privilege principal that can perform the required operation, but do not confuse scope declaration with object assignment. Provider readback determines actual authority.

Never respond to a 403 or an empty object set by silently escalating credentials. Diagnose the contract, preserve the boundary, and route through the proven authorized principal only when the operation's governed authority permits it.
