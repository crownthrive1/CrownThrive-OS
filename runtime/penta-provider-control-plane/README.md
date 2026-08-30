# Penta Provider Control Plane v1.1

This runtime package closes the Phase 3 software-provider gap through four independently governed subsystems:

- **PentaCredentials™** — binds provider credentials from server/runtime secret stores and records only presence plus non-reversible fingerprints.
- **PentaBuild™** — materializes deterministic adapter/plugin assets and appendable build receipts.
- **PentaCertify™** — independently validates artifact digest, contract shape, secret leakage, credential binding, and live provider readback for the exact operation being certified.
- **PentaNurture™** — continuously checks binding/certification health, records drift, and sets **software** as the priority lane.

## Production eligibility

Credential presence is not live authentication. An adapter is not `CERTIFIED` until PentaCertify receives a successful live, read-only provider response for its registered certification probe.

A provider operation is executable only when the runtime can prove the required credential binding, build receipt, live certification, current nurture health, and exact-operation readback when the operation contract requires it. All initial operation contracts require readback.

The `all` command exits non-zero whenever any provider listed in `policy.required_provider_certifications` remains unbound, uncertified, expired, unhealthy, or ineligible at its registered probe operation. The readiness matrix is still written before exit so a failed automation run preserves its exact HOLD reasons. Pull-request validation remains credential-free and never invokes `all` or a live provider probe.

Caller-supplied `result=PASS` or `readback=true` dictionaries are not certification evidence. PentaCertify rejects the legacy `live_evidence` input. Side-effect certification accepts only a minimal provider receipt locator for an explicitly implemented verifier; PentaCertify then re-reads that object from the provider with its own credential and generates the evidence itself. Operations without a trusted provider-receipt verifier remain fail-closed.

Live credential jobs execute only from exact `main`, require the explicit `PENTA_PROVIDER_READBACK_ENABLED=true` repository gate, and run inside the `provider-readback` GitHub environment. The provider matrix receives one selected provider credential per job. The environment's reviewers, prevent-self-review rule, exact-main deployment policy, variables, and scoped secrets still require external settings readback before that gate may be enabled.

The PentaMail write job is **BUILT_HOLD_AUTHORITY** and hard-disabled in source. A shaped manual input is not founder authority. Activation requires an adopted, current, scoped, expiring and single-use authority receipt channel plus verified `pentamail-production` environment controls. Resend receipt verification remains implemented and tested so it cannot promote substituted, failed, stale or unrelated messages when a legitimate authority channel is later adopted.

`HOLD_UNBOUND` and `AUTH_BOUND_PENDING_READBACK` are intentional. Missing credentials or failed/unavailable provider probes are never converted into passing states.

## Lifecycle integration

This control plane is complementary to the production provider-lifecycle surface documented at `software-factory-v4/PENTA-PROVIDER-LIFECYCLE.md`. The control plane evaluates exact provider/credential/build/certification readiness; the ThriveBase/Supabase lifecycle persists governed evidence, maintenance state, and PentaNurture continuity. Neither surface may infer or expand authority from the other.

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
- Supabase read-only REST probe: `SUPABASE_URL` + `SUPABASE_ANON_KEY`
- Vercel: `VERCEL_TOKEN`
- Stripe: `STRIPE_SECRET_KEY`
- Resend: `RESEND_API_KEY`
- Mailgun: `MAILGUN_API_KEY` + `MAILGUN_DOMAIN`
- Slack: `SLACK_BOT_TOKEN`
- ElevenLabs: `ELEVENLABS_API_KEY`

The existing PentaFactory GitHub→Supabase OIDC bridge remains a separately evidenced provider path; generic GitHub Actions OIDC availability is not treated as proof that the native Supabase adapter authenticated.

These aliases are contract names, not claims that the corresponding secret is currently configured. PentaCredentials resolves that truth at runtime and PentaCertify separately proves authentication with a live read-only provider probe.

## Initial certification probes

- GitHub — repository metadata read.
- Supabase — REST/OpenAPI root read using the least-privilege anonymous key; service-role authority is not released to the health probe.
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
- Caller-authored evidence flags cannot promote an operation.
- Certification expires and must be renewed.
- D3/reserved authority is not self-created.
