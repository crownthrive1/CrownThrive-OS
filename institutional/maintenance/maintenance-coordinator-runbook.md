# CrownThrive Targeted Maintenance Coordinator Runbook

## Institutional purpose

This runbook governs a **targeted quiescence event**, not a CrownThrive shutdown. The purpose is to create a stable recovery boundary before broad convergence or production mutation. Background writers are paused because a moving packet/queue/provider/commerce/documentation state can invalidate backup manifests, hashes, restore tests, and scheduler-equivalence evidence.

Canonical active event at adoption:

`ct.maintenance.2026-08-24.targeted-quiescence.v1`

Founder authority:

`ct.founder.directive.2026-08-24.targeted-maintenance.v1`

Temporary coordinator:

`ct.maintenance.coordinator.sol`

The coordinator is bounded. It is not a sovereign super-agent and cannot manufacture D3, rights, entitlements, economic truth, votes, approvals, customer assent, or production certification.

## Mandatory maintenance sequence

1. Capture the exact external scheduler pre-state.
2. Capture the exact internal `pg_cron` pre-state.
3. Preserve source/database rollback anchors.
4. Pause mutating external schedules.
5. Pause mutating internal schedules while preserving backup continuity.
6. Register the maintenance event in ThriveBase.
7. Run maintenance preflight negative tests.
8. Create/verify the pre-convergence golden backup manifest.
9. Upload recoverable artifacts to the canonical Drive archive.
10. Read back critical artifacts.
11. Validate restore paths.
12. Reconcile duplicate/external/internal schedulers.
13. Verify DAIL.
14. Resolve high-consequence unknowns or leave them explicit HOLD.
15. Stage reactivation wave-by-wave.
16. Close the maintenance event only after every release gate is PASS.

## Database controls

Use:

- `chlom_runtime.maintenance_state_v1()`
- `chlom_runtime.maintenance_preflight_v1(actor_id, capability_id, mutation_requested, d3_requested)`
- `chlom_runtime.maintenance_record_gate_v1(...)`
- `chlom_runtime.maintenance_release_ready_v1(event_id)`
- `chlom_runtime.maintenance_reactivation_plan_v1(event_id)`
- `chlom_runtime.maintenance_close_v1(event_id, actor_id, evidence_refs)`

The maintenance preflight is an **additional fail-closed ceiling**. A PASS from it never grants capability authority that the caller did not already possess.

## Quiescence policy

During strict golden-snapshot capture:

- keep backup/recovery active;
- keep a genuinely read-only founder alert lane active;
- keep the bounded maintenance coordinator active;
- pause routine agents, builders, verifiers, site automation, commerce, outbound sales, release automation, reconciliations, queue dispatchers, stale actuators, and other background writers.

Status is `PAUSED_FOR_TARGETED_MAINTENANCE`. Do not classify an intentionally paused agent as failed or unhealthy solely because heartbeats stop.

## Backup gate

The release condition is evidence-based, not time-based.

`BACKUP_GATE=PASS_RECOVERABLE`

A complete PASS requires:

- a manifest tied to the maintenance event;
- source SHAs/versions where applicable;
- Drive destination references;
- readback evidence;
- restore instructions;
- tested restore path to the required scope;
- missing-object and backup-gap accounting;
- no plaintext secret export.

## Scheduler reconciliation

For each external ChatGPT automation and each internal scheduler:

1. identify the institutional workload;
2. identify cadence and trigger semantics;
3. compare authority ceiling;
4. compare data access and secret boundary;
5. compare failure domain;
6. compare evidence/DAIL behavior;
7. compare rollback and missed-run semantics;
8. determine whether both clocks are genuinely required.

Final disposition is one of:

- `RESTORE_EXTERNAL`
- `RESTORE_INTERNAL`
- `KEEP_ENABLED`
- `RETIRED_SCHEDULING_SCAFFOLDING`
- `HOLD`

Never blindly re-enable every pre-maintenance scheduler.

## Reactivation waves

### Wave 0 — Maintenance core

Backup/recovery, Drive readback, restore validation, maintenance coordination.

### Wave 1 — Observation and continuity

Health/continuity/credential-custody controls. Verify they do not dispatch ordinary application work during maintenance.

### Wave 2 — Independent verifiers

Evidence/security/domain/webhook/gate certifiers. No originator self-certification.

### Wave 3 — Bounded builders and executors

D0-D2 work only after authority, backup, tests, independent verification, and rollback pass.

### Wave 4 — Documentation and site projection

Documentation and site reconciliation. Every material change must produce `docs_updated`, `docs_no_change`, or `docs_delta_opened`.

### Wave 5 — Commercial and outbound

Release, checkout, sales, outreach, publishing, fulfillment, or other customer-facing mutation returns last.

After every wave, re-read queue state, duplicate scheduling, stale leases, DAIL, provider/economic side effects, and error state before advancing.

## CHLOM Agentic Foundry production handoff

Founder-authorized foundry package `ct.system.chlom-agentic-foundry.v1` is a Wave 3 bounded-builder/executor activation candidate. Canonical handoff:

`institutional/maintenance/handoffs/chlom-agentic-foundry-production-v1.json`

The coordinator must resolve the current governed successors of CrownThrive-CIE PR #24 and CrownThrive-Support PR #375 before acting. Never trust a stale head literal over the current accepted source.

The foundry contains SidecarForge, AssetForge, VaultBridge, InteropMesh, ThriveOptimizer, PatchPilot, and RelayFabric. Source-package PASS does not mean live ThriveBase activation. While maintenance release does not permit Wave 3, state remains `HOLD_MAINTENANCE` and no foundry migration is applied.

When Wave 3 becomes eligible, require exact-head foundry/CIE governance PASS, current public-safe contract consistency, DAIL integrity, rollback readiness, no newer supersession, and zero new external scheduler requirement. Apply only the exact source-controlled migration from the accepted CIE source; never reconstruct protected SQL from public documentation.

After apply, immediately second-read and prove: seven active planes; at least thirteen bounded sidecar classes; D2 maximum; non-voting/non-quorum/no-authority-inheritance; Vault alias presence without reading the secret; protected-body exposure false; MCP/plugin/skill bindings; internal pg_cron at the governed cadence; reuse of the existing External Evidence Relay; and zero new ChatGPT scheduler slots.

Required negative tests include D3 patch rejection, recursive sidecar rejection, owner/verifier collision rejection, invalid asset digest rejection, client-role denial, no raw-secret/public-body return, patch `apply_authorized=false` default, and no provider-write/money/rights/credential authority manufactured by foundry candidate creation.

Run `chlom_runtime.agentic_foundry_stress_test_v1()` at least twice on unchanged state and require deterministic PASS. Record exact activation/readback/stress/security evidence in the foundry receipt ledger and DAIL. Only then may the public certification advance from `PASS_PACKAGE / HOLD_MAINTENANCE_RUNTIME` to `PASS_PRODUCTION_RUNTIME`.

This foundry handoff never authorizes closing the broader maintenance event, D3, money movement, rights/entitlements, credential export, protected-body publication, or provider-write expansion.

## Vault and secret handling

Vault is the secret custody plane. Public source and ordinary Drive artifacts may contain only safe references such as alias, fingerprint, provider, purpose, rotation/custody state, and restore requirements. Drive may contain ciphertext when governed, but never ordinary plaintext secrets.

## Failure behavior

If any release predicate is missing, stale, contradictory, or unavailable:

`HOLD`

Continue independent recovery work elsewhere. Do not widen authority to get a PASS.

If a system cannot be backed up:

`BACKUP_GAP → HOLD affected mutation`

Do not block unrelated recovery work, but do not mutate that unrecoverable affected lane.

## Rollback

Maintenance-control changes are additive wherever possible. Rollback removes only maintenance-control objects after dependency checks. Do not delete DAIL, scheduler history, queue history, rights records, financial evidence, identities, or prior institutional evidence.

## Founder communication

Use `ACTION NEEDED` only when the founder must perform a genuinely human-reserved action. Routine maintenance, internal HOLDs, backup progress, or scheduler reconciliation are `INFO`, `WATCH`, `HOLD`, `CONTROLLED MAINTENANCE`, or `NO FOUNDER ACTION`.
