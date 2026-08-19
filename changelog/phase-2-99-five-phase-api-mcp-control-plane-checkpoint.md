# Phase 2.99 — Five-Phase Namespace and API/MCP Control-Plane Checkpoint

## Status

- Baseline `main`: `1eca8fab2d82be4944a44ccf334a2ca0e93a4aca`
- Current institutional phase: Phase 2 / Subphase 2.99
- Phase 3 entry: `blocked_pending_phase_2_99_hard_exit`
- Documentation impact: `docs_delta_opened`
- Provider mutation: disabled
- Collab Portal mutation: blocked

## Five-phase top-level namespace

The current governing institutional namespace contains exactly five top-level phases:

1. Institutional Mapping
2. Institutional Recovery, Reconciliation & Documentation
3. Executable Institutional Core
4. Federated Ecosystem Activation
5. Institutional Scale, Licensing & Expansion

Earlier ten-phase material is preserved as historical/operational decomposition. It is not the current top-level institutional namespace. No historical accepted record is deleted or silently renumbered.

The machine authority for this checkpoint is `developers/manifests/institutional-phase-namespace.v2.json`. Existing prose that still describes ten phases as current is now an explicit P0 documentation reconciliation delta rather than an alternate source of truth.

## Current API/MCP control-plane evidence

The current Supabase `integration_control` snapshot establishes the following operational state without exposing any credential value:

### CrownThrive API/MCP Control Plane

- `crownthrive-api-control` version 2 is active.
- JWT authentication is required and an additional admin/service-role authorization boundary exists.
- MCP protocol `2026-07-28` is implemented for `server/discover`, `tools/list`, and `tools/call`.
- Header/body protocol consistency, input-schema validation, output sanitization, private cache scope, rate limiting and request-evidence hashing are present in the current runtime.
- Provider writes are disabled and the provider-write gate is closed.
- The remaining major MCP gate is an authorized external-client conformance test.

### CrownThrive IO

- Runtime credential state is verified through a protected Vault reference.
- Authenticated read certification passed.
- The current integration state is `read_verified` and health is `healthy` with observed HTTP 200 evidence.
- Verified read families include User, Links, Statistics, Projects, Pixels, Splash pages, QR codes, Data, Notification handlers, Domains, Teams, team memberships, Payments and Logs.
- `/team-members/{team_id}` still requires a real team ID and remains documented but not certified.
- Mutation families remain closed.
- The observed Splash-page create documentation entry `POST /projects` remains an unresolved source-owner anomaly and is not silently corrected.
- CrownThrive IO remains an interoperability/gateway layer. It does not become CrownThrive ID, CHLOM rights authority or the institutional source of truth.

### Collab Portal

- The integration is configured but current credential evidence is `mismatch`.
- Exact-credential certification remains blocked.
- Authenticated read remains blocked.
- Bounded write remains closed.
- No control-plane Collab Portal request has been consumed in the current request ledger snapshot.
- The monthly request ceiling remains 20,000.
- Project UID, approved field mapping, authenticated project read and webhook sender-integrity/retry/replay/idempotency evidence remain open.
- No brute force, screenshot transcription, rotation, reconstruction or credential exposure is authorized.

## Collision prevention

A separate branch, `admin-mcp/phase-2-99-agent-sovereignty-quorum-security`, is ahead of `main` with a distinct seven-file governance/security packet and no open PR at this checkpoint. This Agent-C packet does not modify those files and does not compete with that packet.

No open pull request owned this five-phase/API-MCP packet when this branch was created.

## Phase 3–5 propagation

### Phase 3 — Executable Institutional Core

Phase 3 inherits the five-phase namespace, the current API/MCP read-only control plane, MCP `2026-07-28`, explicit provider-write closure, Vault-only credential references, external-client conformance as an open gate, and the requirement that unresolved source/provider state cannot promote to authority or permission.

### Phase 4 — Federated Ecosystem Activation

Phase 4 may consume only certified adapters and stable institutional identities. CrownThrive IO can serve interoperability reads, but it cannot replace CrownThrive ID or CHLOM authority. Collab Portal cannot become a governed execution-state projection until exact credential, project UID, approved field map and authenticated read/write-readback gates pass.

### Phase 5 — Institutional Scale, Licensing & Expansion

External licensing, developer access, partner automation and scale inherit the same authority boundaries: no runtime credential becomes a public developer credential; no provider capability becomes CrownThrive deployment proof; no historical or unverified state becomes a commercial, legal, rights or economic authorization.

## Open deltas

- Reconcile remaining current prose that still presents the ten-phase roadmap as the top-level institutional namespace.
- Complete external MCP client conformance with an authorized client path.
- Keep all provider mutation families disabled until separately governed and certified.
- Resolve Collab Portal credential mismatch through a secure authorized runtime path before any authenticated read or write certification.
- Continue Phase 2.99 Workstream 0 articleization and Workstream 3A source/identity/provider/domain reconciliation.
- Establish GitHub fail-closed branch/ruleset enforcement before Phase 3 entry.

This checkpoint does not advance CrownThrive into Phase 3.
