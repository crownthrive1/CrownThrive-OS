# Backroad FM / Virality Music — Radio.co Institutional Provider Binding

Status: ACTIVE provider contract; provider readback VERIFIED  
Effective: 2026-08-28  
Provider station: Backroad FM  
Consumer/integration label: Virality Music Website Demo  
Consumer brand: Virality Music  
Provider: Radio.co  
Station ID: `s0831f6c44`

This package institutionalizes the Radio.co station and its CrownThrive consumer contract without collapsing two distinct identities. Radio.co's public station readback identifies station `s0831f6c44` as **Backroad FM**. The supplied Radio.co widget label is **Virality Music Website Demo**, owned by the Virality Music consumer lane. Both bind to the same station ID, but they are not interchangeable names.

CrownThrive-OS carries the canonical provider contract, station identity, capability inventory, embed identifiers, public stream endpoints, public provider readback contract, retained readback evidence, consumer binding state, and the logical broadcast-secret reference. Provider credentials remain outside source control.

## Identity model

| Identity | Value | Semantics |
|---|---|---|
| Provider station | Backroad FM | Radio.co-reported station identity |
| Station ID | `s0831f6c44` | Stable provider station identifier |
| Consumer/widget label | Virality Music Website Demo | Supplied Radio.co integration/widget label |
| Consumer brand | Virality Music | CrownThrive media consumer lane |
| Integration ID | `virality-music.radio-co.s0831f6c44` | Compatibility-stable CrownThrive integration identifier |

`station-identity.json` is the canonical identity crosswalk. The integration ID is intentionally retained for compatibility; station identity reconciliation does not authorize an implicit rename of runtime keys, consumers, or credentials.

## Verified provider evidence

The first governed post-merge public readback completed at `2026-08-29T00:10:13.711297Z` and classified the integration as `verified`. At that observation:

- Radio.co reported the station name as Backroad FM.
- station metadata returned HTTP 200.
- station status returned HTTP 200 with `onair`.
- the 192 kbps and 64 kbps stream URLs matched the institutional contract.
- current track, next track, and 24-hour history endpoints returned HTTP 200.
- no broadcast secret was accessed.
- no provider state was mutated.

The immutable-style retained observation is `readback-receipts/2026-08-29T001013Z.json`. Track titles and on-air state inside a receipt are timestamped observations, not permanent declarations.

## Public embed inventory

### Listener request widget

```html
<script src="https://embed.radio.co/request/wc84c77d.js"></script>
```

### Schedule widget

```html
<script src="https://embed.radio.co/embeds/schedule/es891d079.js"></script>
```

### Player variant 1

```html
<script src="https://embed.radio.co/player/50f694e.js"></script>
```

### Player variant 2

```html
<script src="https://embed.radio.co/player/5c84942.js"></script>
```

Radio.co widget display reference supplied with this binding: `650 × 350`.

## Listen endpoints

| Surface | Format | Endpoint |
|---|---|---|
| Standard | 192 kbps MP3 | `https://streams.radio.co/s0831f6c44/listen` |
| Mobile | 64 kbps MP3 | `https://streams.radio.co/s0831f6c44/low` |
| Playlist | 192 kbps M3U | `http://streams.radio.co/s0831f6c44/listen.m3u` |

Canonical link snippets:

```html
<a href="https://streams.radio.co/s0831f6c44/listen" target="_blank" rel="noopener noreferrer">Listen Live!</a>
<a href="https://streams.radio.co/s0831f6c44/low" target="_blank" rel="noopener noreferrer">Listen Live!</a>
<a href="http://streams.radio.co/s0831f6c44/listen.m3u" target="_blank" rel="noopener noreferrer">Listen Live!</a>
```

The M3U endpoint is preserved exactly as supplied by the provider. Do not silently rewrite its scheme without provider readback/verification.

## Public provider readback

Radio.co publishes secret-free station and playout readback endpoints. This package registers the station-specific endpoints in `provider.json` and codifies verification semantics in `verification-contract.json`.

Registered readback includes:

- station metadata and streaming-link readback
- on-air/off-air status
- current source
- current track
- next track
- recent track history
- legacy/full station status

The required institutional checks are station metadata and station status. Track endpoints are observational: an accepted `404` from an optional track resource does not, by itself, declare the station unavailable.

Run the secret-free verifier from this directory:

```bash
python3 verify_public_readback.py
```

Optional evidence file:

```bash
python3 verify_public_readback.py --output radio-co-readback.json
```

The verifier is restricted to HTTPS on `public.radio.co`, performs GET-only operations, does not read the broadcast credential, and does not mutate provider state. A failed required check produces `overall_state=unverified`; observational transport failures produce `overall_state=degraded`; required checks passing without observational failures produce `overall_state=verified`.

The GitHub governance workflow executes this verifier after relevant changes reach `main` and on manual dispatch. Future executions retain the generated JSON as a workflow artifact so provider evidence is not confined to ephemeral console logs.

## Public projection

`public-projection.json` is the browser/downstream-safe projection. It exposes **Backroad FM** as the provider station name and **Virality Music Website Demo** as the consumer/integration label, along with public widget sources, listening URLs, and selected readback URLs. It excludes both the live-broadcast credential and its secret reference.

Downstream website, documentation, analytics, and agent consumers should prefer this projection when they do not need privileged broadcast configuration.

## Consumer binding

`consumer-bindings.json` tracks the intended `vm.crownthrive.com` public consumer. The binding is currently `unbound` in the inspected GitHub/Vercel control planes: the authoritative website repository/runtime has not yet been identified there. Therefore this provider integration must not be represented as already deployed on that website.

Issue `#742` tracks the remaining consumer-binding and related institutional work. Activation requires locating the authoritative website runtime, binding `public-projection.json`, deploying through that consumer's own pipeline, and verifying the rendered Backroad FM player/request/schedule behavior.

## Live broadcasting contract

- Host: `s0831f6c44.dj.radio.co`
- Port: `80`
- Password: resolve at runtime from `RADIOCO_VIRALITY_LIVE_BROADCAST_PASSWORD`
- Plaintext credentials: prohibited in Git, docs, logs, client bundles, analytics events, public projections, and evidence receipts

The existing logical secret key is retained as a compatibility key. Renaming it is prohibited until every consuming runtime is discovered and a controlled secret migration is verified.

Because a live password was supplied in conversational text during initial institutionalization, rotate/regenerate that Radio.co live broadcasting credential before treating credentialed live-broadcast ingest as production-safe. Public readback verification does **not** prove credential rotation or credential validity.

## Provider documentation

- Radio.co custom branded player guidance: `https://help.radio.co/en/articles/899717-create-custom-branded-players`
- Radio.co playout API: `https://www.radio.co/api`
- Radio.co Public API v2 contract: `https://developers-84608658bd058c817.radio.co/api-reference/openapi_specs/public-v2`

## Institutional awareness contract

The provider binding exposes these system capabilities to CrownThrive institutional awareness:

- Backroad FM provider-station identity reconciliation
- live audio streaming
- embedded player delivery
- listener-request intake
- public schedule publication
- low-bandwidth mobile streaming
- M3U/directory distribution
- live broadcast ingest
- public station readback
- now-playing readback
- track-history readback
- retained provider evidence

Only non-secret integration metadata may be projected to websites, documentation, registries, analytics, or downstream agents. Secrets remain represented by logical references only in privileged configuration.

## Consumer rules

1. Public consumers use `public-projection.json`; privileged consumers use `provider.json` only when needed.
2. `Backroad FM` is the provider station identity; `Virality Music Website Demo` is the consumer/widget integration label.
3. A page should select the appropriate player variant intentionally rather than assuming both player scripts belong in the same placement.
4. Server-side/live-broadcast workloads resolve the compatibility secret reference at runtime.
5. No consumer may substitute a cached plaintext password for the secret reference.
6. Changes to provider station identity, station ID, widget IDs, stream endpoints, or live host/port require provider readback and an institutional update.
7. Public-site deployment and provider-side credential rotation are separate execution boundaries; neither may be inferred from successful public readback.

## Verification checklist

- `provider.json`, `station-identity.json`, `public-projection.json`, `verification-contract.json`, `consumer-bindings.json`, and retained receipt JSON parse successfully.
- `verify_public_readback.py` compiles and uses standard-library networking only.
- station identity is consistently `Backroad FM` across provider, identity, and public projection contracts.
- consumer/widget label remains `Virality Music Website Demo` across compatible consumer contracts.
- request, schedule, and player identifiers match the supplied Radio.co configuration.
- standard and mobile endpoints use HTTPS as supplied.
- playlist endpoint is retained exactly as supplied.
- public API endpoints align with the provider contract.
- secret value and secret reference are absent from public projection and retained public-readback evidence.
- secret logical key exists in authorized target runtime before credentialed live-broadcast activation.
- website placement is verified only after deployment on the intended consumer surface.
- provider-side password rotation is completed after credential exposure.
