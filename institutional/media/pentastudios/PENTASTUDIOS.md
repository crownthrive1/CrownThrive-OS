# PentaStudios

## Institutional role

PentaStudios is CrownThrive's governed media-production subsystem. It coordinates capture, podcasting, transcript intelligence, editing, packaging, linear/live distribution, publication evidence, analytics feedback, monetization routing, and long-horizon preservation without replacing provider-native systems of record.

PentaStudios is additive to CrownThrive Studios. CrownThrive Studios remains the outward-facing studio/media brand; PentaStudios is the interoperable software and governance subsystem that operates the production mesh.

## Core architecture

`capture/provider -> Asset Bound Vault -> PentaStudios -> CHLOM rights gate -> CIE context -> packaging/distribution -> CrownLytics/CrownPulse evidence -> ThrivePush/CrownFluence/AdLuxe growth -> PentaGeneration continuity`

### Governed production lanes

1. Capture & intake — Riverside, uploads, live sessions, provider-native recordings.
2. Asset Bound Vault — immutable provider IDs, lineage, hashes when available, tombstones, rights/context state, secret references only.
3. Production — transcripts, edits, captions, brand application, derivative clips, exports.
4. Distribution — Riverside hosting/RSS, provider-native social publishing, Viloud linear/live ingest, Melanated TV, Melanated Voices TV, Locticians TV.
5. Intelligence — CrownLytics and CrownPulse receipts, engagement and operational evidence.
6. Growth — ThrivePush, CrownFluence, AdLuxe Network, CrownRewards and campaign packaging where CHLOM permits.
7. Continuity — PentaGeneration preservation of masters, transcripts, rights records and publication receipts.

## Live ThriveBase surfaces

Production database: CrownThrive / ThriveBase.

Tables:
- `public.penta_studios_assets`
- `public.penta_studios_provider_bindings`
- `public.penta_studios_routes`

Edge Functions:
- `penta-studios-control` — JWT-protected read control surface for status, assets, bindings and routes.
- `penta-studios-mcp` — JWT-protected MCP surface using protocol `2026-07-28`.

Autonomous software factory adapters:
- `ct.adapter.pentastudios.control.v1`
- `ct.adapter.pentastudios.mcp.v1`

Both adapters are registered as enabled and verified native adapters. Provider-side mutation authority remains bounded by each provider's actual certified write surface and CHLOM governance.

## MCP tools

PentaStudios MCP exposes read-only institutional tools:
- `penta_studios_status`
- `penta_studios_assets`
- `penta_studios_bindings`
- `penta_studios_routes`

Provider writes are intentionally not manufactured by the MCP. Riverside editing/publishing remains provider-native through the connected Riverside surface; Viloud live ingest remains disabled until its runtime stream-key secret reference resolves and a canary succeeds.

## Bound provider truth

Riverside production ID: `6316ad12874a96000b2e7f0d`

Canonical Riverside studios:
- `631e09dadf4a1d000a31b95b` — FRONT PORCH SERMONS!
- `631e09c7df4a1d000a31b2b2` — BUILT TO OUTLIVE US!
- `631e0971bd6683000cda2d49` — RECEIPTS & REVELATIONS!

Bound endpoints:
- Riverside studio entrypoint: `https://riverside.com/studio/crownthrive`
- Riverside hosting RSS: `https://api.riverside.com/hosting/HdbnBVG2.rss`
- Viloud RTMP ingest base: `rtmp://broadcast.viloud.tv/in/`
- Viloud authorization secret reference: `VILOUD_RTMP_STREAM_KEY`

Token-bearing Riverside links and RTMP stream keys are credential-class data and must never enter GitHub, public docs, logs, analytics, or manifests.

## Governance invariants

- Provider IDs are immutable binding keys.
- Renames update display metadata without breaking lineage.
- Missing/deleted assets are tombstoned only after repeat verification.
- CHLOM governs rights, licensing, monetization and provider-write authority.
- CIE may enrich cultural/context metadata but may not overwrite provider evidence.
- PentaGeneration receives continuity-critical masters and receipts.
- No secret value is stored in the PentaStudios registry; only secret reference names are permitted.
- No provider capability may be marked active solely because an endpoint is known.
- Write authority requires provider support, a governed adapter, read-after-write evidence and rollback/readback semantics where applicable.

## Version

Subsystem: `ct.pentastudios.v1`
Runtime/API: `1.0.0`
MCP: `1.0.0`
Institutional status: `OPERATIONAL / BOUNDED`
