# AdLuxe Places OS Integration

Issue: #4238

AdLuxe Places is CrownThrive's governed place-based media and screen-monetization layer. AdSpot Pro and AdSpot TV are licensed third-party implementation components and must remain replaceable behind CrownThrive-owned service identities and contracts.

## Canonical role

- AdLuxe Places: venue/screen supply, local DOOH inventory, screen monetization and publisher operations.
- AdLuxe Network: broader advertising demand/orchestration layer.
- CrownLytics: normalized proof-of-play, attribution, yield and campaign reporting.
- CrownPulse: fleet health, offline-screen, heartbeat, delivery and anomaly monitoring.
- ThrivePush: operational, publisher and advertiser notifications.
- CrownRewards: QR, offer, redemption and downstream conversion attribution.
- CHLOM/DAIL: rights, entitlement, governance, evidence append/readback and institutional completion.
- PentaAds: campaign/inventory placement and partner routing.

## Non-negotiable controls

1. No destructive overwrite of the current cPanel deployment. Fingerprint and diff first.
2. Preserve AdLuxe branding and all live customizations.
3. Treat vendor software as replaceable implementation, not CrownThrive identity.
4. Redact authorization credentials and secrets from client/server logs.
5. Move the TV REST control plane to device-scoped authentication after pairing.
6. Distinguish proof-of-play/served plays from modeled or verified audience impressions.
7. Billing, transaction and campaign-spend changes are D2-risk and fail closed until governed merge/readback.
8. No institutional completion until CHLOM DAIL append and readback succeed.
9. Existing PentaTagger/PentaPR/PentaMerge/PentaCloser governance remains authoritative.

## Production sequence

1. Fingerprint live cPanel app, database, runtime, WebSocket/proxy, storage and deployed version.
2. Diff live state against the CrownThrive-held AdSpot Pro 2.3.0 and AdSpot TV source packages.
3. Diff vendor 2.3.1 billing/transaction/campaign-spend changes before any upgrade.
4. Populate `crownthrive1/AdLuxe-Places` with governed source, provenance, license metadata and software contract.
5. Implement OS adapters and event contracts.
6. Produce a CrownThrive-branded Android TV build with production endpoint, package identity, token-log redaction and device credentialing.
7. Validate proof-of-play, attribution, fleet health, house inventory, payout and demand-routing behavior.
8. Execute governed merge gates and provider readback.
9. Append/read back CHLOM DAIL evidence.

## Event model

Minimum normalized events:

- `adluxe.places.screen.paired`
- `adluxe.places.screen.heartbeat`
- `adluxe.places.screen.offline`
- `adluxe.places.campaign.assigned`
- `adluxe.places.creative.started`
- `adluxe.places.creative.completed`
- `adluxe.places.proof_of_play.recorded`
- `adluxe.places.qr.scanned`
- `adluxe.places.conversion.recorded`
- `adluxe.places.billing.debit_recorded`
- `adluxe.places.publisher.credit_recorded`
- `adluxe.places.delivery.failed`

Every event must carry stable CrownThrive identifiers for venue, screen, campaign and creative where applicable, plus event time, provider provenance and correlation/idempotency data.

## Measurement vocabulary

`proof_of_play` means the player/device confirms that creative playback occurred. It must not be projected as a verified human impression without an approved audience-measurement methodology.
