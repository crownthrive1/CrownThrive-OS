# ThrivePush cPanel Control-Plane Certification Receipt

**Record date:** September 2, 2026  
**Service:** `cpanel_thrivepush_io`  
**Target:** `thrivepush.io`  
**Implementation plane:** `crownthrive1/ThrivePush`  
**Runtime source of truth:** ThriveBase  
**Authority:** Kavonte Jones Sr., Founding Member

## Bound architecture

The dedicated cPanel control plane is isolated from the general CrownThrive cPanel credential. Its immutable credential identity is `ct.credential.cpanel.thrivepush-io.penta-api`, and its only permitted runtime source is the Vault reference `cpanel.penta_thrivepush_io.api_token`.

The provider token is unrestricted at the cPanel account layer. CHLOM and PentaWire reduce execution authority to explicit operations. Provider scope never overrides CrownThrive authority, evidence, DAIL, mutation, or founder-reserved gates.

Required fabrics are registered: PentaCredentials, PentaFlex, PentaMCP, PentaWire, and PentaCertify.

## Runtime components

| Component | State | Enforcement |
|---|---|---|
| `cpanel-thrivepush-io-api-control` | ACTIVE, version 1 | JWT-protected; resolves the dedicated Vault reference only |
| `penta-wire-secure-cpanel-thrivepush-io` | ACTIVE, version 1 | Constant-time internal authentication; five-operation read allowlist |
| `integration_control.cpanel_thrivepush_io_secure_canary_dispatch_v1` | Deployed | Service-role-only network canary dispatcher |

Allowed reads are `health.read`, `domains.read`, `target_domain.read`, `disk_usage.read`, and `site_profile.read`. Provider writes are disabled.

## Route contract

- **Hot:** live authenticated provider reads and exact `thrivepush.io` certification. State: blocked until exact Vault binding and provider readback pass.
- **Warm:** standby reconciliation, failover, and separately authorized mutations. It references the same Vault-held credential and does not create another plaintext copy.
- **Cold:** sealed recovery and explicit rebind. It does not claim an independently issued provider credential.

## MCP projection

Registered tools:

- `cpanel_thrivepush_io_health`
- `cpanel_thrivepush_io_domains`
- `cpanel_thrivepush_io_target_domain`
- `cpanel_thrivepush_io_disk_usage`
- `cpanel_thrivepush_io_site_profile`

Health is staged. Provider-dependent tools remain withheld from production exposure until authenticated provider certification succeeds.

## Evidence

The secure PentaWire façade returned HTTP 200 for `health.read` with `BLOCKED_UNBOUND_SECRET`, `credential_exposed=false`, `provider_write=false`, and `authority_effect=none`. This certifies deployment, transport, internal authentication, operation allowlisting, credential-reference selection, and fail-closed behavior. It does not certify cPanel authentication or target-domain visibility.

Response digest: `898b102ab88aaa130251874ca21b87d4b964c51a12186851808908629e770848`

## Current certification state

| Gate | State |
|---|---|
| Service, custody, continuity, variable, API, MCP, and route registries | PASS |
| Edge deployment | PASS |
| Secure façade health and fail-closed behavior | PASS |
| Exact production credential stored in Vault | BLOCKED — protected secret ingress required |
| cPanel authentication | NOT EXERCISED |
| Exact `thrivepush.io` provider visibility | NOT EXERCISED |
| Hot-route activation | WITHHELD |
| Production MCP exposure | WITHHELD |

No raw or encoded credential is present in this repository, Drive, API contracts, MCP schemas, logs, or evidence. The fixed production credential has no scheduled or automatic rotation. Replacement requires explicit founder authority, confirmed compromise, or provider invalidation.
