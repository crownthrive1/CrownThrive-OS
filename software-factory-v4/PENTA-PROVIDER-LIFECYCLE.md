# Penta Provider Lifecycle — Phase 3 Software Priority

Status: **Production**  
Owner: CrownThrive, LLC  
Canonical authorities: **PentaBuild™**, **PentaCertify™**, **PentaCredentials™**, **PentaNurture™**

## Purpose

The Penta Provider Lifecycle converts unresolved provider execution gaps into bounded software work instead of treating `hold_unbound` as a terminal state. It preserves the CrownThrive fail-closed authority model: a provider action does not become executable merely because code exists, a credential reference exists, or a build completed.

The lifecycle is:

`discover gap -> classify -> credential reference -> PentaBuild -> PentaCertify -> binding eligibility -> PentaNurture -> remediation/re-certification`

Software is the priority. Human intervention is reserved for provider-side authorization, unavailable credentials/permissions, D3 governance, legal/financial authority, or provider behavior that cannot be proven safely by software.

## PentaBuild™

PentaBuild owns construction and maintenance of bounded software assets required to close provider gaps. Its output may include provider adapter contracts, runtime adapters, plugins, probes, MCP manifests, API contracts, tests, policy manifests, event contracts, readback contracts, rollback/compensation contracts, evidence manifests, and CI verification assets.

PentaBuild does **not** grant provider authority. A compilable package is not a certification receipt.

Provider-gap build requests are enriched to the `ct.penta.build.provider-assets.v1` output contract. The quality sweep requires institutional contract artifacts rather than accepting metadata-only scaffolds. Shallow builds are automatically requeued for rebuild and remain uncertified.

## PentaCertify™

PentaCertify owns independent provider capability certification. It consumes live evidence and advances a provider adapter only through the applicable gates:

- provider adapter exists;
- authenticated/read-only provider capability passes;
- bounded write canary passes when writes are required;
- read-after-write passes;
- rollback or compensating action passes when applicable;
- runtime binding is present;
- required credential state is verified;
- D3 actions remain human-governed.

`ct_factory_adapter_certification_queue` is the certification-state source of truth. A queue state advances only when the corresponding evidence exists.

The provider-evidence bridge promotes already-verified live control receipts from `ct_factory_provider_control_bindings` into `integration_control.site_provider_adapters`. It does not manufacture evidence. This closes stale handoff gaps where a provider read had actually passed but the adapter registry had not received the receipt.

## PentaCredentials™

PentaCredentials owns credential-reference readiness, custody health, continuity, runtime-consumer binding, and credential evidence.

It uses CrownThrive's existing credential continuity/custody registries. Raw credentials are not copied into the Penta Provider Lifecycle. Generated software may reference a custody record identifier but must not embed API keys, passwords, tokens, recovery values, or service-account secret material.

Credential custody and provider certification remain separate facts:

- `credential reference present` means CrownThrive has a governed reference/custody path;
- `credential verified for provider operation` means the provider action itself has passed the required certification evidence.

PentaCredentials never fabricates either state.

## PentaNurture™

PentaNurture continuously nurses the software/provider fabric after build and certification. It monitors adapter state, certification state, credential-reference health, provider/surface health, task drift, binding state, and remediation ownership.

PentaNurture writes cycle receipts and per-surface checks. It invokes reconciliation and sends unresolved software gaps back through the factory rather than silently degrading provider authority.

### Operational cookie telemetry

PentaNurture uses an opaque first-party operational session cookie for provider-fabric correlation. The runtime cookie is:

- Secure;
- HttpOnly;
- SameSite=Lax;
- opaque UUID material;
- scoped to operational correlation, not secret storage.

The server persists only the SHA-256 correlation hash. Raw cookie values, authorization headers, provider tokens, API keys, passwords, and credential values are prohibited from the telemetry record.

This telemetry is for software/runtime maintenance, not a substitute for consent-required marketing or behavioral tracking.

## Autonomous schedules

- `ct-penta-certify-v3`: certification/build dispatch loop every 2 minutes.
- `ct-penta-provider-evidence-bridge-v1`: live evidence activation every 2 minutes.
- `ct-penta-build-quality-v1`: provider build contract quality sweep every 5 minutes.
- `ct-penta-nurture-v1`: runtime nursing/maintenance every 5 minutes.
- Existing software-factory continuity/dispatch jobs remain in force.

## Binding rule

A surface may leave `hold_unbound` only when its required provider capability has actually been certified. Missing provider APIs, missing provider-side permissions, missing bounded write semantics, missing readback/rollback evidence, and D3 governance remain explicit blockers rather than being inferred away.

## Production invariants

1. PentaBuild may build software; it may not self-certify consequential provider authority.
2. PentaCertify may certify only on evidence; it may not manufacture credentials or waive required gates.
3. PentaCredentials may manage references/custody evidence; it may not expose or invent secret material.
4. PentaNurture may reconcile, monitor, retry bounded work, and create remediation receipts; it may not bypass certification.
5. Universal delete, arbitrary administrative mutation, credential invention, and D3 auto-promotion remain disabled.
6. Provider certification and runtime authority are revocable and must remain observable through receipts and health checks.
7. Production truth wins over documentation claims.
