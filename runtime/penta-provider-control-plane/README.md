# Penta Provider Control Plane v1.2

This runtime package closes the Phase 3 software-provider gap through four independently governed subsystems:

- **PentaCredentials™** — binds provider credentials from server/runtime secret stores and records only presence plus non-reversible fingerprints.
- **PentaBuild™** — materializes deterministic adapter/plugin assets and appendable build receipts.
- **PentaCertify™** — independently validates artifact digest, contract shape, secret leakage, credential binding, and live provider readback for the exact operation being certified.
- **PentaNurture™** — continuously checks binding/certification health, records drift, and sets **software** as the priority lane.

## Production eligibility

Credential presence is not live authentication. An adapter is not `CERTIFIED` until PentaCertify receives a successful live, read-only provider response for its registered certification probe.

A provider operation is executable only when the runtime can prove the required credential binding, build receipt, live certification, current nurture health, and exact-operation readback when the operation contract requires it. All initial operation contracts require readback.

`HOLD_UNBOUND` and `AUTH_BOUND_PENDING_READBACK` are intentional. Missing credentials or failed/unavailable provider probes are never converted into passing states.

## Lifecycle integration

This control plane is complementary to the production provider-lifecycle surface documented at `software-factory-v4/PENTA-PROVIDER-LIFECYCLE.md`. The control plane evaluates exact provider/credential/build/certification readiness; the ThriveBase/Supabase lifecycle persists governed evidence, maintenance state, and PentaNurture continuity. Neither surface may infer or expand authority from the other.

Material provider events also bind to the DAIL evidence spine. A consequential provider operation cannot be certified solely from an adapter receipt: it needs the canonical DAIL receipt and its operation-specific readback. The Stripe adapter declares a separate raw-body webhook verification operation. That operation remains held until its Supabase secret/runtime binding, DAIL migration, distinct provider readback, and independent verification pass.

## Cookies

PentaNurture can emit `ct_penta_nurture` as a signed, one-hour, non-sensitive priority/health pointer. It contains a provider ID, `priority=software`, health, opaque correlation ID, and expiry.

It **never** contains provider keys, bearer tokens, webhook signing secrets, credential references, customer data, or the authoritative audit record. The complete event stays server-side. Set `PENTA_NURTURE_COOKIE_SIGNING_KEY` only in a server-side secret store.

## Commands

```bash
python3 runtime/penta-provider-control-plane/penta_control_plane.py validate
python3 runtime/penta-provider-control-plane/penta_control_plane.py all
python3 runtime/penta-provider-control-plane/penta_control_plane.py gate github repository_read
```

Generated state defaults to `.penta/provider-control-plane/` and is evidence/output, not an authority source.

## Credential environment aliases

The initial registry can bind these runtime aliases when present:

- GitHub: `GITHUB_TOKEN`
- Supabase native REST: `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
- Vercel: `VERCEL_TOKEN`
- Stripe: `STRIPE_SECRET_KEY`
- Stripe webhook ingress: `DAIL_STRIPE_WEBHOOK_SECRETS_JSON` (versioned secret references and values supplied only to the Edge Function runtime)
- Resend: `RESEND_API_KEY`
- Mailgun: `MAILGUN_API_KEY` + `MAILGUN_DOMAIN`
- Slack: `SLACK_BOT_TOKEN`
- ElevenLabs: `ELEVENLABS_API_KEY`

The existing PentaFactory GitHub→Supabase OIDC bridge remains a separately evidenced provider path; generic GitHub Actions OIDC availability is not treated as proof that the native Supabase adapter authenticated.

These aliases are contract names, not claims that the corresponding secret is currently configured. PentaCredentials resolves that truth at runtime and PentaCertify separately proves authentication with a live read-only provider probe.

The Stripe webhook secret is not interchangeable with the Stripe API secret. The raw signature header, raw body, and secret value never enter DAIL. DAIL stores their safe digests, the provider event identity, and the verification receipt. Stripe HMAC verification establishes provider-origin evidence but not public non-repudiation because the endpoint secret is shared; the External Evidence Relay must perform separate provider readback and a separate witness must anchor the checkpoint before independent immutability is claimed.

## Initial certification probes

- GitHub — repository metadata read.
- Supabase — REST/OpenAPI root read using service-role authentication.
- Vercel — authenticated current-user read.
- Stripe — authenticated balance read.
- Resend — authenticated domain list read.
- Mailgun — authenticated domain list read.
- Slack — authenticated `auth.test`.
- ElevenLabs — authenticated current-user read.

Probe response bodies are not persisted. Certification evidence contains only the operation, PASS/FAIL/readback state, status/semantic result where applicable, and timestamp.

## State progression

`UNINSPECTED → DISCOVERED → DOCUMENTED → AUTH_BOUND_PENDING_READBACK → CERTIFIED → WRITE_VERIFIED → PRODUCTION_MONITORED`

PentaBuild alone stops at `BUILT_PENDING_INDEPENDENT_VERIFICATION`.

## Safety invariants

- Provider capability is not CrownThrive authority.
- Credential presence is not provider certification.
- Adapter compilation is not live-provider proof.
- Read certification does not grant write authority.
- A write operation is never inherited from a different certified operation.
- Certification expires and must be renewed.
- D3/reserved authority is not self-created.
