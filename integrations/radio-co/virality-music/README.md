# Virality Music — Radio.co Institutional Provider Binding

Status: ACTIVE provider contract  
Effective: 2026-08-28  
Owner brand: Virality Music  
Provider: Radio.co  
Station ID: `s0831f6c44`

This package institutionalizes the non-secret Radio.co configuration supplied for Virality Music. CrownThrive-OS carries the canonical integration contract, capability inventory, embed identifiers, public stream endpoints, public provider readback contract, and the logical secret reference. Provider credentials remain outside source control.

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

The verifier is deliberately restricted to HTTPS on `public.radio.co`, performs GET-only operations, does not read the broadcast credential, and does not mutate provider state. A failed required check produces `overall_state=unverified`; observational transport failures produce `overall_state=degraded`; required checks passing without observational failures produce `overall_state=verified`.

## Public projection

`public-projection.json` is the browser/downstream-safe projection of this provider binding. It contains the public widget sources, listening URLs, and selected public readback URLs, but excludes the live-broadcast credential and its secret reference. Downstream website, documentation, analytics, and agent consumers should prefer this projection when they do not need privileged broadcast configuration.

## Live broadcasting contract

- Host: `s0831f6c44.dj.radio.co`
- Port: `80`
- Password: resolve at runtime from `RADIOCO_VIRALITY_LIVE_BROADCAST_PASSWORD`
- Plaintext credentials: prohibited in Git, docs, logs, client bundles, analytics events, or public projections

The live-broadcast password must be stored in the approved secret store and injected only into authorized broadcast/runtime workloads. Because a live password was supplied in conversational text during institutionalization, rotate/regenerate that Radio.co live broadcasting credential before treating it as production-safe.

## Provider documentation

- Radio.co custom branded player guidance: `https://help.radio.co/en/articles/899717-create-custom-branded-players`
- Radio.co playout API: `https://www.radio.co/api`
- Radio.co Public API v2 contract: `https://developers-84608658bd058c817.radio.co/api-reference/openapi_specs/public-v2`

## Institutional awareness contract

The provider binding exposes these system capabilities to CrownThrive institutional awareness:

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

Only non-secret integration metadata may be projected to websites, documentation, registries, analytics, or downstream agents. Secrets remain represented by logical secret references only in privileged configuration.

## Consumer rules

1. Consumer surfaces may use the public stream URLs and embed script sources from `public-projection.json`.
2. Privileged server-side consumers may resolve `provider.json`; public/browser consumers must not receive privileged credential configuration.
3. A page should select the appropriate player variant intentionally rather than assuming both player scripts belong in the same placement.
4. Server-side/live-broadcast workloads resolve the logical secret reference at runtime.
5. No consumer may substitute a cached plaintext password for the secret reference.
6. Changes to station IDs, widget IDs, stream endpoints, or live host/port require provider readback and an update to this package.
7. Public-site deployment and provider-side credential rotation are separate execution boundaries; this contract does not claim either occurred unless independently verified.

## Verification checklist

- `provider.json`, `public-projection.json`, and `verification-contract.json` parse as valid JSON.
- `verify_public_readback.py` compiles and uses standard-library networking only.
- Request, schedule, and player identifiers match the supplied Radio.co configuration.
- Standard and mobile endpoints use HTTPS as supplied.
- Playlist endpoint is retained exactly as supplied.
- Public API endpoints align with Radio.co's published station/playout contract.
- Secret value is absent from source control and public projection.
- Secret logical key exists in the target runtime before live-broadcast activation.
- Website placement is verified after deployment on the intended Virality Music surface.
- Provider-side password rotation is completed after any credential exposure.
