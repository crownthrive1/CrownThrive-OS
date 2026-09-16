# Storage Command integration

Component: `ct.command.storage-status.v1` · version `1.0.0`  
Institutional generation: Phase 3 / CrownThrive OS 3.x  
Owner: CrownThrive engineering/platform stewardship  
Audience: developers, operators, and public-safe command-center readers  
Source state: release candidate; deployment and commercial states require separate receipts.

## Scope

The existing Command shell gains storage panels in Overview, Three DAIL, Infrastructure, Commerce, Evidence, and Integrations. The principal link is `/infrastructure#storage-command`. Ten command routes resolve through the existing index loader so enhancements are consistent across direct navigation. The original `/command-v3.html` remains available as the loader's source and recovery shell. Existing application, API, security-header, and non-command routes are preserved.

`GET /api/storage-command` and `HEAD /api/storage-command` use only the existing `ct_wasabi_status_v1` and `ct_storage_fabric_catalog_v1` read RPCs. The fixed canonical ThriveBase origin and existing server-only service credential are reused. This integration does not grant ordinary authenticated users access to private status RPCs, impersonate an operator, add database permissions, or change a storage provider.

## Truth and privacy contract

The response is an explicit allowlist, never an upstream-object spread. It omits raw events, actor/customer identities, bucket names, object keys, provider customer/order identifiers, secret aliases and values, private metadata, and signed URLs. Unknown numbers and booleans stay unknown. Duplicate identities are not counted as verified instances. Catalog bindings are not payment or fulfillment proof.

Archive progress uses actual section event count divided by the configured section target. It never substitutes sequence high-water for event count. Configured upload admission and empirically tested object size remain separate fields. Registered object bytes are not provider billable usage. A logical hot view is not physical source pruning; retention-policy readback is not an isolated disaster-recovery certification.

An observed snapshot means the read succeeded, not that every subsystem passed. A missing source produces a partial response; two unavailable sources produce HTTP 503. Provider errors are not echoed. A failed browser refresh preserves only an explicitly stale, timestamped last-known snapshot. Each upstream read has a nine-second timeout. Response parsing is bounded to two MiB. Alternate origins and redirecting upstream responses are rejected.

## Refresh and authority

The browser observes the existing Command freshness indicator, coalesces refresh requests, follows manual refresh and visibility changes, and marks retained observations stale after ninety seconds. There is no new polling interval, cron, mailbox watcher, or canonical writer. The stale timer changes presentation only; it performs no network or provider operation.

There are no start-archive, unlock, delete, retention-change, checkout, payment, or sale-enable controls in the public panel. Existing storage, security, finance, and CHLOM owners retain those actions. CrownThrive IO is not advertised as unlimited resale capacity. Off-chain custody is not represented as an independently available IPFS or blockchain network.

## Validation and acceptance

Run from this app directory:

```bash
node --test tests/storage-command.test.mjs
npm run validate
```

The focused suite covers privacy allowlisting, actual-event progress, unknown values, duplicate identities, quarterly billing, stale source rejection, origin binding, method rejection, partial outages, malformed and oversized input, HEAD behavior, loader injection, and command routes. The initial focused suite passed twenty tests on local Node 22; the project runtime is Node 24, whose repository validation remains required. Offline Chromium DOM fixtures also exercised six panels, mobile width, refresh coalescing, and stale-state preservation. These are tests, not a production deployment receipt.

Release acceptance requires the exact reviewed source head, required repository checks, the intended Vercel production alias mapped to that source, served API and asset readback, and interactive route/mobile acceptance. Do not promote preview availability, a source-gate pass, or a deployed HTML shell into proof of paid storage fulfillment. The current external sales gate remains owned by the live catalog function.

## Rollback and continuation

Revert this scoped commit through the normal reviewed source path, or restore its prior deployment only through the existing authorized release procedure. No database migration is introduced. Wasabi objects, retention, consumers, DAIL cursors, source records, billing, and existing schedulers are unchanged by the UI release. Keep the private execution receipt and source lineage even after rollback. Required reviews and deployment failures remain visible; do not remove checks to manufacture a release.

AI-assisted source prepared under the Founder's website/command-center integration directive, September 16, 2026. This file grants no additional license, provider authority, or commercial permission.
