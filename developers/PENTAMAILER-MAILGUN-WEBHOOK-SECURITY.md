# PentaMailer — Mailgun Webhook Security

PentaMailer verifies Mailgun HTTP webhooks before any event is accepted into CrownThrive runtime processing.

## Credential binding

The raw signing key is secret material and must never be committed, logged, emailed, or projected to client code.

- Runtime environment alias: `MAILGUN_WEBHOOK_SIGNING_KEY`
- PentaCredentials Vault alias: `ct.pentamailer.mailgun.webhook_signing_key`
- Primary sending credential alias: `ct.pentamailer.mailgun.primary.api_key`
- Secondary sending credential alias: `ct.pentamailer.mailgun.secondary.api_key`

Sending credentials and the webhook-signing credential are distinct capabilities. A send-only key must not be substituted for the webhook-signing key.

## Verification contract

Per Mailgun's webhook security contract, PentaMailer:

1. Reads `timestamp`, `token`, and `signature` from the webhook signature payload.
2. Concatenates `timestamp` and `token` with no separator.
3. Computes HMAC-SHA256 using the bound webhook-signing key.
4. Compares the expected and supplied hexadecimal signatures with a constant-time comparison.
5. Supports `parent-signature` for subaccount events when present.
6. Can reject replayed tokens through a TTL replay cache that persists only a SHA-256 token fingerprint.
7. Enforces a configurable timestamp window; the shipped default is 24 hours with five minutes of future-clock skew tolerance.

Provider reference: https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/securing-webhooks

## Runtime

`runtime/penta_mailgun_security.py` exposes `MailgunWebhookVerifier`, `TokenReplayCache`, and `verify_mailgun_webhook()`.

The verification result is deliberately sanitized. It contains provider/operation state, timestamp, the signature source, and a truncated SHA-256 token fingerprint. It does not return the signing key, raw token, or supplied signature.

## Production integration rule

Webhook receivers must call the verifier before event-specific business logic. A verification failure is terminal for that request and must not be converted into a PASS. Multi-instance receivers should supply a durable TTL-backed replay-cache mapping rather than relying only on process-local memory.

## Tests

`tests/test_penta_mailgun_security.py` covers the exact HMAC contract, malformed signatures, wrong signatures, parent signatures, replay rejection, stale/future timestamps, optional freshness disabling, environment resolution, and secret non-disclosure.
