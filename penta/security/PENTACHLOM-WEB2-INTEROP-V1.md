# PentaCHLOM Web2 Interoperability Runtime v1

Status: **source candidate / independent certification required**

## Role

PentaCHLOM is CrownThrive's governed Web2/interoperability translation and projection adapter over canonical CHLOM. It exists to let conventional provider identities, APIs, databases, SaaS systems and other Web2 surfaces interoperate with CHLOM-native identity, rights, authority and evidence objects without collapsing those systems into one authority plane.

PentaCHLOM is **not CHLOM**. It does not inherit CHLOM authority and cannot create authority, grant rights, create credentials, move money, perform provider writes, invent token classes or perform D3 actions. CHLOM remains the canonical rights/authority/governance protocol.

## Collision-safe family placement

Fresh family census exposes a canonical `ROUTING_INTEROP` family: **Penta Routing & Interoperability Family**, whose job is to coordinate routing and interoperability capabilities. PentaCHLOM is therefore registered there when the runtime migration is actually applied. This avoids incorrectly duplicating PentaSecurity or placing the adapter inside the CHLOM authority plane.

Security and trust decisions remain owned by PentaSecurity and existing Security, Identity & Trust capabilities. Governance decisions remain owned by CHLOM and applicable governance/CIE authorities. PentaCHLOM translates and projects only after those boundaries are satisfied.

## Canonical DAIL topology

The verified runtime has three canonical DAIL systems:

1. `ct.dail.human.v1`
2. `ct.dail.hybrid.v1`
3. `ct.dail.machine.v1`

Evidence, Decision and Execution are **semantic stages** classified across those systems. They are not three replacement ledgers and they are not CHLOM token classes. PentaCHLOM never trusts a caller-supplied canonical DAIL lane. Each governed action appends through canonical CHLOM DAIL, invokes the DAIL classifier, and persists the exact event ID/hash only after readback succeeds.

No current production readback proves a CHLOM-native multi-token model. Token semantics remain outside this adapter until an exact governed CHLOM runtime establishes them.

## Data model

### Identity bindings

`penta_runtime.pentachlom_identity_bindings_v1` records append-only mappings from a **hashed Web2 provider subject** to a canonical CHLOM identity reference for an exact tenant and purpose. Raw provider subject values are deliberately absent. A new mapping supersedes a prior binding rather than editing it.

Each binding carries:

- provider system;
- SHA-256 provider-subject digest;
- tenant and purpose;
- CHLOM identity reference;
- source evidence reference/digest;
- predecessor binding when superseding;
- canonical DAIL event ID/hash/classification;
- safe metadata only.

### Projection requests

`penta_runtime.pentachlom_projection_requests_v1` is immutable source intent for `web2_to_chlom` or `chlom_to_web2` translation. Supported object kinds are identity, rights, authority, consent, license, provenance, evidence, audit, eligibility, split, expiration and waiver.

Every request permanently asserts:

- `authority_inherited = false`;
- `rights_granted = false`;
- `provider_write_performed = false`.

These are database constraints, not documentation promises.

### Projection chronology

`penta_runtime.pentachlom_projection_events_v1` is append-only chronology. Current state is derived by `penta_runtime.pentachlom_projection_status_v1`; base records are never mutated to simulate state transitions.

State progression is bounded:

`candidate -> validated -> projected`

with governed `hold`, `rejected` and post-projection `superseded` dispositions. Originators cannot independently validate their own projection. Governance-bearing objects cannot reach projected state without an exact CHLOM authority-evidence event reference. That reference is evidence linkage only; PentaCHLOM does not itself issue the CHLOM decision.

## Web2 wrapper behavior

`penta_runtime.pentachlom_render_projection_v1(uuid)` emits a safe derived envelope only after validation. The envelope contains stable references, hashes, target/source identity, CHLOM object reference, canonical DAIL linkage and explicit non-authority flags. It does not call a provider.

Actual provider mutations remain behind the provider's separately certified PentaWire/API/MCP/adapter contract with its own scopes, authentication, idempotency, readback, rollback and current authority gates.

This separation is deliberate:

`Provider/Web2 source -> PentaCHLOM evidence normalization -> CHLOM authority/rights decision -> PentaCHLOM derived projection -> separately certified provider adapter`

## Security properties

The v1 candidate implements:

- service-only internal tables/functions;
- RLS enabled on internal tables plus explicit anon/authenticated revocation;
- immutable source records and chronology;
- canonical DAIL append + classifier + exact hash readback;
- tenant/purpose-bound hashed identity links;
- lower-case SHA-256 digest validation;
- fail-closed secret/credential-like metadata rejection;
- maker/checker separation for validation;
- exact CHLOM authority-evidence requirement for governance-bearing projections;
- no provider writes;
- no rights grant;
- no authority inheritance;
- no token issuance;
- no credential operation;
- no money movement;
- no D3.

## Runtime and census identity

When migration `20260830113000_pentachlom_web2_interop_v1.sql` is actually applied, it registers:

- system key: `penta.chlom.web2-interop`
- canonical name: `PentaCHLOM`
- family: `ROUTING_INTEROP`
- version: `1.0.0`
- maturity: `implemented`
- runtime: `function:penta_runtime.pentachlom_status_v1`
- public exposure: false
- risk ceiling: D2
- certification: **pending independent certification**

`implemented` means executable runtime exists after migration application. It does **not** mean production-certified. The PentaSecurity capability binding remains `certification_hold` until PentaCensus identity refresh, independent security review, PentaCertifier disposition and production readback agree.

## Acceptance gates

The source candidate is not production authority. Promotion requires:

1. exact-head GitHub CI/security/collision/PentaPM gates;
2. bounded migration application through the governed ThriveBase release path;
3. transactional positive/negative/adversarial tests;
4. exact runtime readback;
5. canonical DAIL append/classification/hash readback;
6. PentaCensus identity/family/runtime registration readback;
7. independent security disposition;
8. CHLOM authority-boundary verification;
9. applicable CIE decision;
10. independent PentaCertifier certification;
11. rollback/readback proof;
12. governed merge/release.

Originator self-certification artifacts are readiness metadata only and have no independent certification effect.

## Continuity cursor

Current source work lives in CrownThrive-OS PR #1431. Continue that PR rather than opening a duplicate CHLOM/security implementation. Preserve its pre-repair rollback/safety branch and exact-head governance. The CHLOM Continuous Publisher newline repair in the same PR remains a separate release predicate and must not be called production until the repaired migration is applied and provider/runtime publication readback succeeds.
