# Locticians Brilliant Directories API Fabric v3

Status: **ADDITIVE / CONTROLLED TEST / PRODUCTION REGISTRY LIVE**  
Institutional date: **2026-08-28**  
Provider: **Brilliant Directories**  
Service: **Locticians Community + Directory**

## Purpose

This contract institutionalizes the Brilliant Directories API surface exposed to Locticians without overwriting the existing v1/v2 adapter, endpoint catalog, credentials, or evidence. It makes provider capabilities discoverable across CrownThrive OS while preserving the core governance rule:

> **Provider permission is capability evidence, not CrownThrive execution authority.**

All destructive API operations are D3. They may be discovered and reasoned about, but no DELETE provider request may be dispatched without a separately supplied founder/human D3 approval path.

## Preserved prior state

The following are preserved and remain independently auditable:

- `ct.adapter.brilliant-directories.locticians.v1`
- `integration_control.locticians_endpoint_catalog_v2`
- `locticians-api-control` v6 and its bounded read/member-update evidence
- the pre-existing Vault reference `locticians_brilliant_directories_api_key`
- existing Locticians runtime/configuration rows and provider evidence

Fabric v3 is additive and does not rewrite those records.

## Canonical provider endpoint

The v3 router uses:

`https://locticians.com/api/v2`

The currently verified bound credential identifies itself through `GET /api/v2/token/verify` as **Mintlify x GitHub API** with provider website `https://locticians.com` and HTTP 200. The historical `www.locticians.com` base remains preserved in v1 records; v3 uses the direct canonical host to avoid redirect-mediated method changes on non-GET requests.

Authentication remains `X-Api-Key`. Raw provider tokens are never projected into registries, DAIL, documentation, logs, or MCP discovery responses.

## Provider permission snapshot and OS discovery

Founder-supplied Brilliant Directories permissions on 2026-08-28 establish that the relevant Standard and Advanced endpoint surfaces are enabled at the provider fine-grained layer. Sensitive `include_user_token` is treated separately and remains closed unless a specifically required, separately authorized path is established.

Reconciliation against the pre-existing OS catalog produced:

- **539** pre-existing governed endpoint-catalog records
- **99** missing exact endpoint signatures added as a v3 permission delta
- **638** total OS-discoverable route signatures through the unified v3 projection
- **108** routes classified D3 because they are destructive or secret/high-consequence surfaces
- **149** routes currently hot-eligible after existing CrownThrive certification gates are applied

The 99-row v3 table is not a replacement endpoint catalog. It stores only exact signatures that were missing from the existing catalog.

### Source-of-truth objects

- `integration_control.locticians_endpoint_catalog_v2` — preserved existing governed catalog
- `integration_control.locticians_provider_endpoint_manifest_v3` — additive 2026-08-28 permission delta
- `integration_control.locticians_bd_capability_view_v3` — unified OS discovery projection
- `public.locticians_bd_discover_v3(...)` — bounded discovery RPC
- `public.locticians_bd_route_decision_v3(...)` — execution decision RPC
- `integration_control.mcp_tools: locticians.endpoint.discover.v3` — D0 discovery contract
- `ct.system.locticians.brilliant-directories.v3` — CHLOM interop-system registration
- `ct.adapter.brilliant-directories.locticians.v3` — additive provider adapter registration

OS components including PentaMCP, PentaRoute, PentaCertify, PentaMarketer, PentaCrawler, PentaCredentials, PentaQuery, PentaSearch, PentaQueue, PentaRetry, PentaAudit, PentaUpdate, and PentaNurture can discover the provider contract through these governed registries rather than hard-coding provider permissions independently.

## Execution states

Discovery returns both provider permission and CrownThrive execution state. Expected decision classes include:

- `ROUTE_ELIGIBLE` — registered and already CrownThrive-certified for bounded execution
- `DISCOVERABLE_NOT_INTERNALLY_CERTIFIED` — provider permission is known, but CrownThrive has not certified this exact route
- `CERTIFICATION_REQUIRED` — a registered CrownThrive route exists but is not currently certified for dispatch
- `D3_FOUNDER_APPROVAL_REQUIRED` — destructive/secret/high-consequence route; no provider dispatch
- `D3_APPROVAL_PRESENT_ROUTE_ELIGIBLE` — reserved decision class for a future separately authenticated D3 approval path; the ordinary router does not manufacture this authority

Example: `DELETE /api/v2/user/delete` resolves to D3 with `execution_allowed=false` without an explicit D3 approval basis.

Specialized permission-visible routes such as `POST /api/v2/user/send-template` can be discovered before certification but remain non-executable until PentaCertify establishes a bounded provider contract.

## Durable router

Edge Function: `locticians-bd-router-v2`  
JWT verification: **enabled**

Operations:

- `discover` — reads the unified governed capability registry; never returns secrets
- `route.execute` — requires admin/service authority, exact registered route template, matching concrete path, execution certification, and site-wide rate-budget approval

Execution rules:

1. DELETE is rejected before provider dispatch with `D3_FOUNDER_APPROVAL_REQUIRED`.
2. Any route classified D3 is rejected before provider dispatch.
3. `include_user_token` is rejected before provider dispatch.
4. Unregistered or uncertified routes fail closed.
5. Request and provider-response sizes are bounded.
6. Provider calls use the canonical Locticians host and `application/x-www-form-urlencoded` for write bodies.
7. Every provider dispatch is recorded through the existing integration request-audit path.

## Rate limit, queueing, and redundancy policy

Brilliant Directories applies a shared site allowance: all endpoints, all HTTP methods, and all API keys consume the same website-wide quota. Therefore additional keys are **credential redundancy**, not quota multiplication.

Institutional policy: `ct.locticians.bd.rate.v1`

- Provider hard limit: **100 requests / 60 seconds website-wide**
- CrownThrive soft limit: **80 requests / 60 seconds**
- Reserved provider headroom: **20 requests / 60 seconds**
- Default page size: **25**
- Maximum page size: **100**
- 429 behavior: cool the entire Brilliant Directories provider route and retry with bounded jitter
- 429 key-hopping: **prohibited**
- Credential failover is reserved for auth/credential/transport failure, not rate-limit bypass

`public.locticians_bd_sitewide_rate_check_v3()` counts all Locticians request-audit actors together rather than maintaining an unsafe per-key quota fiction.

## Hot/cold credential lanes

Three independent lane identities are registered:

| Lane | Intended role | Current state |
| --- | --- | --- |
| `ct.locticians.bd.hot.a.v3` | primary autonomous hot provider credential | HOLD — provider-admin reissuance required |
| `ct.locticians.bd.hot.b.v3` | independent hot failover credential | HOLD — provider-admin reissuance required |
| `ct.locticians.bd.cold.reserve.v3` | cold reserve, never quota-bypass | HOLD — provider-admin generation required |

Vault aliases are pre-registered but no fabricated secret is considered ready:

- `locticians_brilliant_directories_hot_a_v3`
- `locticians_brilliant_directories_hot_b_v3`
- `locticians_brilliant_directories_cold_reserve_v3`

### Provider issuance finding

A founder-authorized bootstrap exercised Brilliant Directories' API-key CRUD endpoint without destructive cleanup:

- Provider record **15**, `CrownThrive Locticians Hot A`, was created, failed `/token/verify` with HTTP 401 across two token-shape attempts, and was disabled.
- Provider record **16**, `CrownThrive Locticians Hot B`, was created with a 32-character token; the provider returned the same token, but `/token/verify` returned HTTP 401, so the record was disabled.
- Cold Reserve creation was intentionally stopped after the second independent failure rather than creating another unusable provider record.
- No new failed token was vaulted because verification is required before Vault insertion.
- Records 15 and 16 were not deleted because DELETE is D3 and no destructive approval was requested or consumed.

Brilliant Directories' admin-generated key flow is therefore the current production boundary for issuing the three usable independent credentials. Once a provider-admin-generated key authenticates, `PentaCredentials` can ingest it into its pre-registered Vault alias and enable the corresponding lane; it must never scrape or infer a token from the provider inventory representation.

Until then, the durable router may use only the previously verified primary credential as the last-resort legacy lane for routes already certified by CrownThrive.

## Sensitive data

`include_user_token` remains OFF. The v3 router explicitly rejects that parameter. API-key, password-retrieval-session, webhook-secret, and equivalent credential-bearing families remain D3/high-consequence surfaces even when provider permissions make their schemas discoverable.

## Contract drift and maintenance

Table: `integration_control.locticians_bd_contract_watch_v1`  
Scheduled job: `locticians-bd-contract-watch-v1`  
Schedule: **daily at 06:17 UTC**

The watch:

- fetches the official Brilliant Directories API Getting Started reference;
- fetches the official Brilliant Directories API-key management reference;
- hashes each reference and compares it with the previous snapshot;
- records HTTP status and drift state;
- snapshots unified route count, D3 count, hot-eligible count, key-lane state, and site-wide rate policy.

Initial 2026-08-28 baseline: both official references returned HTTP 200.

PentaUpdate/PentaCertify/PentaAudit/PentaNurture can use this evidence to open a reconciliation lane when documentation drift is observed. Documentation drift is evidence for review, not automatic permission expansion.

## DAIL evidence

Institutional event:

- Event ID: `df82415f-e1d0-42cc-8291-860fe75283e8`
- Event type: `locticians.brilliant_directories.fabric_v3_added`
- Entity: `ct.system.locticians.brilliant-directories.v3`
- Event hash: `199f524caa9036c9b2e5b4d329dab2bc9cb90839a5096effad9337d624c90f21`

The DAIL receipt records the additive/non-overwrite rule, route/D3 counts, rate policy, router, credential-lane status, and the fact that no D3 destructive provider operation was executed.

## Required future promotion gates

The fabric can operate immediately for previously certified routes through the verified legacy credential. Promotion of Hot A, Hot B, or Cold Reserve to dispatch-ready requires all of the following:

1. provider-admin issuance of an independently generated key;
2. `/token/verify` success against `https://locticians.com`;
3. Vault insertion under the pre-registered lane alias without exposing the token;
4. PentaCredentials continuity registration and runtime binding;
5. fine-grained provider permissions readback/save for the intended lane;
6. PentaCertify endpoint canaries/readback for the routes assigned to that lane;
7. DAIL evidence and registry state transition.

No step may convert provider capability into D3 authority automatically.
