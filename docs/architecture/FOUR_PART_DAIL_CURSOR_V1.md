# Four-Part DAIL Cursor Runtime Extension v1

**Status:** Production verified  
**Canonical OS:** CrownThrive OS v18.0.0 (runtime extension; no canonical-version rewrite)  
**System key:** `ct.dail.cursor.v1`  
**Assignment:** `ct.assignment.dail-cursor-four-rail-production-v1`  
**Assignment ID:** `c51a9ffc-88ea-4faa-991d-13447223e99e`

## Architecture decision

CrownThrive retains one canonical CHLOM DAIL event chain. Machine, Human, Hybrid, and Cursor are operating projections over that chain, not four independent ledgers or authority realities.

- **Machine DAIL** projects runtime-produced evidence.
- **Human DAIL** projects Founder and explicit human-governance evidence.
- **Hybrid DAIL** projects crossover, handoff, approval, reconciliation, and cross-system evidence.
- **DAIL Cursor** coordinates bounded high-water marks, binds run inputs, drives catch-up, and records terminal reconciliation evidence across the other three rails.

Cursor never rewrites canonical event identity, changes rights, creates approval, substitutes for a verified provider result, or moves money.

## Production objects

- Registry: `chlom_runtime.dail_system_registry_v1`
- Cursor control: `chlom_runtime.dail_cursor_control_v1`
- Rail positions: `chlom_runtime.dail_cursor_rail_positions_v1`
- Input manifests: `chlom_runtime.dail_cursor_input_manifests_v1`
- Run receipts: `chlom_runtime.dail_cursor_runs_v1`
- Cursor projection: `chlom_runtime.dail_cursor_v1`
- Rail projector: `chlom_runtime.dail_cursor_project_rails_v1(integer)`
- Controller: `chlom_runtime.dail_cursor_tick_v1(text, boolean)`
- Emergency control: `chlom_runtime.dail_cursor_set_emergency_v1(boolean, integer)`
- Status: `chlom_runtime.dail_cursor_status_v1()`
- Canary: `chlom_runtime.dail_cursor_canary_v1()`

## Scheduler and PentaBalancer

The canonical production scheduler is `ct-dail-cursor-control-v1`, running every minute through `penta_balancer.execute_managed_job_v1`.

PentaBalancer owns admission and temporal cohesion only. Cursor remains the runtime coordinator. The job is instrumented with admission class `normal`, priority `95`, zero cooldown, and a 60-second maximum runtime.

Two overlapping clocks were retired and made non-restorable:

- `ct-dail-serial-lane-drain-v4`
- `chlom-dail-compact-catchup-v4`

## Hard throttle and emergency mode

Cursor preserves one canonical database writer. “Virtual workers” are serial bounded slices, not concurrent writers.

| Bound | Ceiling |
|---|---:|
| Virtual slices per tick | 4 |
| Rail events per tick | 100,000 |
| Routed mutations per tick | 600 |
| Deferred events per tick | 50 |
| Verification events per tick | 20,000 |
| Emergency duration | 120 minutes maximum |

Emergency throughput is admitted only when PentaBalancer is in `NORMAL` or `RECOVERY`, pressure is at most 45, session use is at most 60%, lock waiters are at most 1, and running jobs are at most 24. Otherwise Cursor falls back to constrained mode or defers without creating a partial institutional result.

## Mandatory evidence protocol

Every material Cursor cycle performs:

1. Build a minimal safe input manifest.
2. Hash the manifest.
3. Append `ct.dail.cursor.input.bound.v1`.
4. Read back event ID, sequence, and hash.
5. Advance bounded Machine, Human, and Hybrid cursors.
6. Drain routed and deferred evidence within hard limits.
7. Advance compact chain verification.
8. Append `ct.dail.cursor.reconciliation.completed.v1`.
9. Read back the terminal event before the cycle is complete.

Full event bodies, credentials, payment instruments, and unnecessary personal data are not copied into Cursor receipts.

## Production proof

Production canary event: `ca948bbd-2b10-489d-ab4c-e2579fddccc2`  
Canary sequence: `2485792`  
Canary evidence SHA-256: `474e13364aac205ebdf0d8706f9e1eb951e09a02e77de50427d84146cfc1e56c`

The canary verified registry identity, single-chain semantics, three rail positions, RLS, role isolation, real-time assignment, exact scheduler state, retired legacy jobs, PentaBalancer policy, cohesion score 100, emergency bounds, and DAIL readback.

## Initial catch-up result

Twenty bound manual cycles completed under PentaBalancer-constrained mode:

- 4,928 route rows delivered
- 6 deferred events delivered
- 49,355 events verified
- Rail cursor advanced from 2,433,793 to 2,485,510
- Verification cursor advanced from 2,435,919 to 2,485,760
- Verification lag reached zero for the observed head
- Route backlog decreased by 4,167 during the measured window
- Recent 19,916-event assignment scan found zero missing primary, Hybrid, or Cursor assignments

Emergency maximums were requested but not used because PentaBalancer remained in `WATCH`; the safety gate therefore operated correctly.

## Rollback

Rollback is authority-reducing:

1. Disable `ct-dail-cursor-control-v1`.
2. Set Cursor state to `paused`.
3. Leave canonical DAIL events and all Cursor receipts intact.
4. Do not auto-restore retired legacy jobs.
5. Diagnose and repair the smallest failed dependency.
6. Re-enable only after canary and readback pass.
