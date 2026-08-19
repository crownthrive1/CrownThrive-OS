# Phase 2.99 — Reconciled Phase Namespace and API/MCP Control-Plane Checkpoint

## Status

- Original PR #62 baseline: `1eca8fab2d82be4944a44ccf334a2ca0e93a4aca`
- PR #62 merge: `58caa1628cc54e03c8dccc70fad6124c54d4b0c8`
- Current institutional phase: Phase 2 / Subphase 2.99
- Current roadmap: `ten_phase_v1` / CT-ADR-ROADMAP-010
- Phase 3 entry: `blocked_pending_phase_2_99_hard_exit`
- Namespace reconciliation: `docs_updated`
- API/MCP broader documentation/conformance: `docs_delta_opened`
- Provider mutation: disabled
- Collab Portal mutation: blocked

## Concurrency reconciliation

PR #62 recovered and recorded valuable sanitized API/MCP control-plane evidence, but it also introduced a transient five-top-level-phase machine namespace while a separate governance/security packet was already in flight.

**PR #62 five-phase machine assertion is superseded** during this reconciliation because it conflicts with the previously accepted CT-ADR-ROADMAP-010 Ten-Phase Institutional Program Charter and the current governance direction. The five-phase record is preserved as historical/concurrency lineage rather than deleted or silently rewritten.

The current machine authority is `developers/manifests/institutional-phase-namespace.v2.json`, which now carries the ten current top-level phases and explicitly records the transient PR #62 five-phase snapshot as superseded lineage.

## Ten-phase top-level namespace

1. Institutional Mapping
2. Institutional Recovery, Reconciliation & Documentation
3. Executable Institutional Core
4. Federated Ecosystem Activation
5. Revenue & Market Activation
6. Licensing, IP & Developer Economy
7. Physical, Phygital & Regional Expansion
8. Holdings, Capital & Portfolio Scale
9. Advanced CHLOM & Interoperable Infrastructure
10. Generational Continuity, Sovereign Scale & Institutional Permanence

Existing historical five-phase planning material remains evidence of prior planning structure. It is not current machine authority.

## Current API/MCP control-plane evidence retained from PR #62

The current sanitized Supabase `integration_control` snapshot remains accepted without exposing any credential value.

### CrownThrive API/MCP Control Plane

- `crownthrive-api-control` version 2 is active.
- JWT authentication is required and an additional admin/service-role authorization boundary exists.
- MCP protocol `2026-07-28` is implemented for `server/discover`, `tools/list`, and `tools/call`.
- Header/body protocol consistency, input-schema validation, output sanitization, private cache scope, rate limiting and request-evidence hashing are part of the recorded runtime evidence.
- Provider writes are disabled and the provider-write gate is closed.
- The remaining major MCP gate is an authorized external-client conformance test.

### CrownThrive IO

- Runtime credential state is verified through a protected Vault reference.
- Authenticated read certification passed.
- Current integration state is `read_verified`; the recorded health snapshot is `healthy` with HTTP 200 evidence.
- Verified read families include User, Links, Statistics, Projects, Pixels, Splash pages, QR codes, Data, Notification handlers, Domains, Teams, team memberships, Payments and Logs.
- `/team-members/{team_id}` remains documented but not certified.
- Mutation families remain closed.
- The observed Splash-page create documentation entry `POST /projects` remains an unresolved source-owner anomaly and is not silently corrected.
- CrownThrive IO remains an interoperability/gateway layer. It does not replace CrownThrive ID, CHLOM rights authority or institutional truth.

### Collab Portal

- Integration is configured but current credential evidence remains `mismatch`.
- Exact-credential certification remains blocked.
- Authenticated read remains blocked.
- Bounded write remains closed.
- No control-plane Collab Portal request had been consumed in the PR #62 request-ledger snapshot.
- Monthly request ceiling remains 20,000.
- Project UID, approved field mapping, authenticated project read and webhook sender-integrity/retry/replay/idempotency evidence remain open.
- No brute force, screenshot reconstruction, secret exposure or provider mutation is authorized.

## Governance reconciliation

`CT-ADR-GOV-011` additionally supersedes the prior assumption that GitHub physical branch/ruleset enforcement must be CrownThrive's sovereign merge authority. GitHub remains CI, audit, repository transport, CodeQL/dependency/security evidence and post-merge defense-in-depth. The coded five-agent CrownThrive policy is the institutional fail-closed gate.

This change does not weaken Phase 2.99. Automatic D0–D2-eligible promotion requires institutional/security validation, applicable security-scan evidence, minimum risk score, specialist endorsements, 4-of-5 quorum, independent Agent D approval, no deny/block vote, rollback and documentation/downstream reconciliation. D3 remains human/reserved.

## Phases 3–10 propagation

### Phase 3 — Executable Institutional Core

Inherit the ten-phase namespace, current API/MCP read-only control plane, MCP `2026-07-28`, provider-write closure, Vault-only credential references, external-client conformance as an open gate and provider-independent agent governance. Build executable decision/vote/evidence records without promoting unresolved state.

### Phase 4 — Federated Ecosystem Activation

Consume only certified adapters and stable institutional identities. CrownThrive IO may provide interoperability reads without replacing CrownThrive ID or CHLOM authority. Collab Portal cannot become a governed execution-state projection until credential/project/field/read/write-readback gates pass.

### Phase 5 — Revenue & Market Activation

Provider/API availability does not create offer, price, consent, attribution, fulfillment, entitlement or revenue authority. Economic transitions need their own effective records and evidence.

### Phase 6 — Licensing, IP & Developer Economy

External API/MCP/SDK access requires explicit identity/scopes, rights, developer terms, versioning, security certification, rate/cost controls and support/remedy policy. Runtime credentials never become public developer credentials.

### Phase 7 — Physical, Phygital & Regional Expansion

API/MCP integrations reaching devices/locations inherit device identity, local privacy/safety, accessibility, incident, rollback and regional operating requirements.

### Phase 8 — Holdings, Capital & Portfolio Scale

API/MCP data may support portfolio evidence but cannot create entity, ownership, capital, securities or IP-transfer authority. Those remain separately governed D3 domains.

### Phase 9 — Advanced CHLOM & Interoperable Infrastructure

The API/MCP control plane becomes an integration substrate for advanced CHLOM, cryptographic proofs and decentralized/poly-chain adapters only after legal, security, privacy, custody and recovery gates.

### Phase 10 — Generational Continuity, Sovereign Scale & Institutional Permanence

Preserve API/MCP contracts, source/evidence mappings, secret-reference reconstruction, provider-exit procedures, agent policy, quorum/risk rules and migration paths so no single provider becomes institutional lock-in.

## Open deltas

- Complete authorized external MCP client conformance.
- Keep provider mutation families closed until separately governed and certified.
- Resolve Collab Portal credential mismatch through a secure authorized runtime path before authenticated read/write certification.
- Continue Phase 2.99 Workstream 0 articleization and Workstream 3A source/identity/provider/domain reconciliation.
- Continue remaining private-core, security/evaluation, provider/account/version/deployment/API/export and registrar/DNS/TLS/runtime hard-exit work.

This checkpoint does not advance CrownThrive into Phase 3.
