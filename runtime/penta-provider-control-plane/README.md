# Penta Provider Control Plane v1

This runtime package closes the Phase 3 software-provider gap through four independently governed subsystems:

- **PentaCredentials™** — binds provider credentials from server/runtime secret stores and records only presence plus non-reversible fingerprints.
- **PentaBuild™** — materializes deterministic adapter/plugin assets and appendable build receipts.
- **PentaCertify™** — independently validates artifact digest, contract shape, secret leakage, credential binding, and exact operation readback evidence.
- **PentaNurture™** — continuously checks binding/certification health, records drift, and sets **software** as the priority lane.

## Production eligibility

A provider operation is executable only when the runtime can prove the required credential binding, build receipt, current certification, current nurture health, and—when the operation mutates provider state—operation-specific readback evidence.

`HOLD_UNBOUND` is intentional. Missing credentials are never invented and are never converted into a passing state.

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

- GitHub: `GITHUB_TOKEN` or GitHub Actions OIDC request variables
- Supabase: `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, or GitHub Actions OIDC for the governed bridge
- Vercel: `VERCEL_TOKEN`
- Stripe: `STRIPE_SECRET_KEY`
- Resend: `RESEND_API_KEY`
- Mailgun: `MAILGUN_API_KEY` + `MAILGUN_DOMAIN`
- Slack: `SLACK_BOT_TOKEN`
- ElevenLabs: `ELEVENLABS_API_KEY`

These aliases are contract names, not claims that the corresponding secret is currently configured. PentaCredentials resolves that truth at runtime.

## State progression

`UNINSPECTED → DISCOVERED → DOCUMENTED → AUTHENTICATED → SANDBOX_TESTED → INTEGRATION_TESTED → CERTIFIED → WRITE_VERIFIED → PRODUCTION_MONITORED`

PentaBuild alone stops at `BUILT_PENDING_INDEPENDENT_VERIFICATION`.

## Safety invariants

- Provider capability is not CrownThrive authority.
- Credential presence is not write certification.
- Adapter compilation is not live-provider proof.
- A write operation is never inherited from a different certified operation.
- Certification expires and must be renewed.
- D3/reserved authority is not self-created.
