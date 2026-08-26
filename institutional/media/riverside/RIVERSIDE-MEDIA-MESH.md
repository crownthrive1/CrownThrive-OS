# CrownThrive Riverside Media Mesh

## Status

Institutional integration contract for Riverside as a governed CrownThrive media-production provider.

This layer is additive. Riverside remains the source of truth for provider-native media objects. CrownThrive records durable identifiers, lineage, governance, routing, evidence, and downstream distribution intent without silently replacing Riverside data.

## Canonical provider topology

Production: `6316ad12874a96000b2e7f0d`

Registered studios:

- `631e09dadf4a1d000a31b95b` — **FRONT PORCH SERMONS!**
- `631e09c7df4a1d000a31b2b2` — **BUILT TO OUTLIVE US!**
- `631e0971bd6683000cda2d49` — **RECEIPTS & REVELATIONS!**

The immutable Riverside ID, not the display name, is the binding key.

## Hardwired provider endpoints

The media mesh also binds these founder-supplied provider endpoints through `ct.media.provider-endpoints.v1`:

- Riverside hosting RSS: `https://api.riverside.com/hosting/HdbnBVG2.rss`
- Riverside CrownThrive studio entrypoint: `https://riverside.com/studio/crownthrive`
- Viloud RTMP ingest base: `rtmp://broadcast.viloud.tv/in/`

The Riverside public studio entrypoint is treated as an alias/intake surface and does not replace any immutable Riverside dashboard studio ID. The RTMP endpoint is stored without its stream key. Runtime authorization must resolve `VILOUD_RTMP_STREAM_KEY` from the approved secret vault.

## Mesh position

Riverside is bound into the CrownThrive media corridor as:

`capture -> Riverside recording/take -> transcript -> edit -> export -> CrownThrive asset vault metadata -> CHLOM rights gate -> CIE cultural/context enrichment -> CrownThrive Studios packaging -> governed distribution -> evidence/analytics feedback`

Live/syndication extension:

`Riverside/CrownThrive intake -> governed live production -> Viloud RTMP ingest -> linear/syndicated media surfaces -> publication receipts -> analytics/evidence feedback`

Primary CrownThrive participants include CrownThrive Studios, Melanated Voices TV, Melanated TV, Locticians TV, CrownThrive IO/MCP, CHLOM, Cultural Imprint Engine, CrownLytics, CrownPulse, ThrivePush, CrownFluence, AdLuxe Network, CrownRewards and CrownThriveU where the content and rights scope is applicable.

Participation never grants an unrelated platform authority to mutate Riverside source media.

## Bound asset classes

The registry recognizes productions, studios, projects, recordings, takes, transcripts, edits, exports, brand kits, caption presets, media assets, podcast feeds, provider entrypoints, live-ingest endpoints and social-publication receipts.

Every discovered asset receives a lineage record using the provider ID as the stable identity. Display names and metadata may change without breaking lineage.

## Asset Bound Vault

The Asset Bound Vault is a metadata-and-lineage vault, not a place to commit provider credentials.

For every bound object, preserve where available:

- provider and immutable provider ID;
- parent production/studio/project identifiers;
- canonical title and provider URL;
- public distribution/feed endpoints;
- live-ingest base endpoints and secret-reference names;
- creation/update timestamps;
- processing/readiness state;
- transcript/edit/export lineage;
- content hash or provider digest when available;
- rights state and CHLOM decision references;
- CIE classification/enrichment references;
- publishing destination and publication receipt;
- tombstone state for deletions;
- secret reference names only, never secret values.

Token-bearing preview URLs and live stream keys are treated as credentials and must not be committed to GitHub, documentation, logs, or analytics.

## API/MCP binding contract

The live ChatGPT Riverside connector is an operational interface for discovery, transcript access, editing, branding, export inspection and supported social publishing. It is not itself a deployable public credential that can be copied into GitHub Actions.

Accordingly, the institutional hardwire is split into two layers:

1. **Control-plane binding** — this repository contains immutable IDs, public endpoints, schemas, governance policy, routing, validation and evidence receipts.
2. **Runtime provider binding** — Riverside API/MCP/connector credentials and Viloud stream authorization secrets must be stored only in the approved runtime secret/vault layer and referenced by name.

Never fabricate a provider API endpoint, credential, webhook or OAuth grant. A capability is marked ACTIVE only after a live call verifies it.

## Authority model

Read/write/delete capabilities are bounded by the provider's actual live surface and CHLOM authority. `available` does not mean `authorized for every asset`.

- Reads may discover and inspect provider resources.
- Writes may create or mutate provider resources only when the provider surface exposes the operation and the requested action is governed.
- Deletes, unpublishes and destructive changes require an explicit supported operation and must preserve a tombstone/receipt in CrownThrive institutional records.
- No process may convert an absent provider capability into a claimed capability.

## Auto-discovery and reconciliation

A production reconciliation runner should:

1. enumerate Riverside productions and studios;
2. enumerate projects per studio;
3. fan out projects into recordings and edits;
4. enumerate exports and readiness state where supported;
5. compare immutable provider IDs against the registry;
6. monitor the bound RSS feed as a distribution/source-of-truth pointer without overwriting Riverside provider records;
7. resolve the Viloud RTMP stream key only from runtime secret storage when a governed live-ingest job executes;
8. add newly discovered objects;
9. refresh mutable metadata for known objects;
10. tombstone missing objects only after a second verification pass;
11. emit a machine-readable evidence receipt;
12. route rights-sensitive downstream actions through CHLOM before publication or monetization.

Discovery is idempotent. Re-running it must not duplicate assets.

## Current verified live state — 2026-08-25

- 1 Riverside production is accessible.
- 3 studios are accessible.
- 0 projects are currently present across those studios.
- 0 social publishing accounts are currently connected across those studios.
- FRONT PORCH SERMONS! has a configured brand kit with an existing Riverside background media asset, colors, and caption configuration.
- BUILT TO OUTLIVE US! and RECEIPTS & REVELATIONS! currently return empty brand kits.
- The RSS, public CrownThrive studio entrypoint and Viloud RTMP ingest base are founder-supplied endpoint bindings. The external web fetch used in this session did not independently resolve the two HTTPS endpoints, so their endpoint records preserve that verification state rather than claiming an independent live probe.

These facts are operational truth until a newer reconciliation receipt supersedes them.

## Non-negotiable invariants

- Preserve source-system IDs.
- Never silently replace an asset.
- Never commit secrets or stream keys.
- Never commit token-bearing share/preview URLs.
- Never claim a social rail is connected until Riverside reports it connected.
- Never claim an RTMP rail is authenticated until its runtime secret is present and a governed connection test passes.
- Never claim a project/recording/edit/export exists until discovered live.
- Preserve lineage across renames and deletions.
- Fail closed on rights ambiguity, revision conflicts, missing credentials, unsupported operations, and provider uncertainty.
