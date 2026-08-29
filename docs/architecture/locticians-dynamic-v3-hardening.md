# Locticians Dynamic Outreach V3 — Production Hardening

Status: **PRODUCTION ACTIVE / PROVIDER-CERTIFIED**  
Authority: `ct.locticians.brilliant-directories.api-fabric.v3`

## Certified production path

The governed path is:

`Locticians V3 discovery/reference → PentaCrawler evidence → PentaMarketer V3 renderer → schedule → PentaMail multipart outbox → governed dispatch → Mailgun adaptive gateway → provider receipt`

The first provider-certified rich V3 send was accepted by Mailgun with HTTP 200 and `multipart_html=true`. The provider receipt also records the Avery persona identity and an HTML content digest; it does not archive the raw HTML body.

## Dynamic copy and offer context

Each eligible prospect is rendered at enqueue time from current verified prospect/offer evidence. The CTA uses the canonical Locticians profile URL and includes `ct_offer=CLAIMMONTH50` as outreach attribution/context. The visible email also displays `CLAIMMONTH50`.

The parameter is not evidence that checkout automatically applies the coupon. Checkout/offer claims remain limited to the canonical safe offer evidence.

## Reference redundancy

Reference order:

1. `crownthrive1/brilliant-directories-mcp`
2. `brilliantdirectories/brilliant-directories-mcp`

Both remain `execution_authority=false`; V3 remains authoritative.

An initial daily GitHub-API reference receipt truthfully recorded a 403/403 degraded read. That append-only receipt remains historical evidence. A quota-independent raw-content fallback was then added and independently read back HTTP 200/200 with matching tracked content digests. Recovery is recorded as a new DAIL event rather than rewriting the earlier receipt.

## Daily autonomy

`ct-locticians-bd-reference-daily-v3` executes daily at `31 6 * * *` UTC. Future receipts use the redundant raw-content reference probe and preserve `v3_authority_state=authoritative_unchanged` unless the canonical V3 contract is separately changed through governance.

## RPC perimeter hardening

Migration `pentamarketer_locticians_v3_rpc_acl_hardening` revoked default PUBLIC, `anon`, and `authenticated` EXECUTE privileges from the changed internal renderer/planner/discovery/promotion/reference RPCs and preserved `service_role` execution where required.

A post-hardening Supabase security-advisor readback no longer reports the newly introduced dynamic-outreach/reference RPCs as publicly executable. Existing unrelated estate warnings and intentionally public V3 discovery/decision surfaces are not reclassified by this change.

## Custody

Public source contains safe contracts, topology, authority rules, skill interfaces, and evidence semantics. Restricted renderer/runtime source is held in `PRIVATE-PentaOS` and CHLOM restricted implementation custody. Raw Brilliant Directories and Mailgun credentials are not stored in these source projections.

## Invariants

- suppression and opt-out are never bypassed;
- provider-adaptive pacing remains authoritative;
- campaign daily/monthly limits remain authoritative;
- D3/provider-destructive authority cannot be inferred from reference code;
- reference drift can trigger reconciliation, never automatic permission expansion;
- dynamic personalization may use only verified public evidence or conservative verified-listing context;
- rich HTML always has a plain-text fallback.
