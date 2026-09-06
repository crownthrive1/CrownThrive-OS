# DAIL Oracle Reader-Writer and Cookie Runbook v1

## Purpose

Operate the DAIL Oracle Capacity Mesh as a subordinate Cursor capacity layer while preserving native oracle duties, one canonical CHLOM DAIL chain, one append fabric, PentaBalancer admission, PentaGas accounting, signed cookies, and exact terminal evidence.

## Normal scheduler

- Job: `ct-dail-oracle-capacity-mesh-v1`
- Cadence: every 20 seconds
- Managed by: `penta_balancer.execute_managed_job_v1`
- Admission class: `elastic`
- Priority: `90`
- Maximum wrapper runtime: `28 seconds`
- Inner managed tick: `chlom_runtime.dail_oracle_capacity_mesh_managed_tick_v1()`

## Entry conditions

A donor is eligible only when:

- Pending routes are at least 100,000, or the mesh is still inside its active hysteresis band.
- PentaBalancer is in `NORMAL` or `RECOVERY`.
- Pressure is 45 or lower.
- Session utilization is 60% or lower.
- Lock waiters are at most 1.
- Running jobs are at most 12.
- The oracle is active and healthy.
- The oracle heartbeat is no older than 15 minutes.
- The native oracle queue is zero.
- Registered capacity is positive.

Native work preempts donation immediately.

## Work selection

1. Prefer `ct.oracle.penta-dail` for one verification slice when verification lag is positive.
2. Select up to four remaining idle oracles for route slices.
3. Use LOCK_OVERCLOCK at 500,000 or more pending routes.
4. Use RECOVERY_OVERCLOCK from 100,000 through 499,999.
5. Apply the verification-lag factor before assigning route work.
6. Execute slices serially through the existing canonical functions.

## Verification slice

A successful verification slice:

1. Creates a bounded decision digest and SHA-256.
2. Quotes and reserves PentaGas.
3. Calls `chlom_runtime.dail_checkpoint_catchup_v4` for at most 5,000 events.
4. Publishes a signed Penta cookie.
5. Settles PentaGas using actual verified events.
6. Appends `ct.dail.cursor.oracle_capacity_mesh.slice.completed.v1` with the oracle ID as actor and Penta node as agent.
7. Reads back the exact terminal event.
8. Persists the slice receipt.

## Route slice

A successful route slice:

1. Calculates a route ceiling from mode, capacity, and verification lag.
2. Calls `chlom_runtime.dail_lane_drain_v5` with zero deferred-event allocation.
3. Inherits the active continuity policy. Archive selection must stay zero while the 500K lock is active.
4. Publishes a signed Penta cookie.
5. Appends an oracle-attributed terminal DAIL event.
6. Reads back the exact event and persists the slice receipt.

## Cookie requirements

Every successful slice publishes a signed cookie containing:

- Oracle ID and Penta node ID.
- Mesh run ID and slice ID.
- Work class and overclock mode.
- Bounded decision-digest SHA-256.
- Native queue and capacity posture.
- Assigned limit and actual result counters.
- One-chain and one-writer declarations.
- Expiry and signature state.

Cookies must not contain credentials, payment instruments, customer secrets, full protected source bodies, or hidden reasoning.

## Attempt and run observability

Do not equate a successful cron wrapper with executed work.

Read these separately:

- Scheduler wrapper attempt from `penta_balancer.job_state_v1`.
- Inner attempt from `chlom_runtime.dail_runtime_attempts_v1`.
- Last material Oracle Mesh run from `chlom_runtime.dail_oracle_capacity_mesh_runs_v1`.
- Last successful slice from `chlom_runtime.dail_oracle_capacity_mesh_slice_runs_v1`.
- Safe status from `public.ct_dail_oracle_capacity_mesh_status_v1()`.

A deferred attempt must never inherit the identity of a prior completed run.

## Deferral handling

| Condition | Result | Required treatment |
|---|---|---|
| PentaBalancer gate fails | `DEFERRED_PENTABALANCER` | Healthy yield; no material completion |
| Canonical lock unavailable | `DEFERRED_LOCK_CONTENTION_ROLLED_BACK` | Retry later; no partial run |
| Route-drain lock unavailable | Slice deferral | Do not degrade the oracle |
| No idle oracle | `DEFERRED_NO_VERIFIED_IDLE_ORACLE` | Capacity remains with native duties |
| PentaGas denial | Slice rollback | No work or terminal completion |
| Cookie failure | Slice rollback | No unsigned completion |
| DAIL readback failure | Slice rollback | Do not represent institutional completion |
| Pending routes at or below 80,000 | `RELEASED` | Return all donor capacity to native duties |

## Throughput observation

Capture and report:

- Exact pending and failed routes.
- Five-minute, fifteen-minute, and one-hour arrivals and deliveries.
- Canonical head and verification cursor.
- Whole-stack route and verification-lag movement.
- Direct Oracle Mesh routes, verification, cookies, failures, and per-oracle contribution.
- Evidence overhead and deferrals.

Never attribute whole-stack movement entirely to Oracle Mesh.

## Release and rollback

At 80,000 pending routes or fewer:

- Set the mesh to released.
- Stop donor slices.
- Return all capacity to native oracle jobs.
- Append and read back the release event.
- Keep the scheduler as a dormant monitor.
- Retain cookies, formulas, recipes, contracts, run receipts, and evidence.

For containment:

1. Set the control state to `hold`.
2. Disable the scheduler through exact desired-state controls.
3. Preserve the canonical chain and all evidence.
4. Diagnose the smallest failed dependency.
5. Re-enable only after the production canary passes.

## Production references

- Deployment event: `13a60111-008a-44a3-90b6-b1dd86333ff9`
- Deployment sequence: `2,585,930`
- Assignment ID: `b5728fd9-6f45-4e14-9b5b-c04ec7214adf`
- Representative run: `2bf54fd9-074d-412b-a012-eeddc6d3fc37`
- Representative terminal event: `c67c7c25-14fe-4220-ae41-2bbfa1f2fcfe`
- Canary evidence SHA-256: `4debcb290ac052a403a9a0d867c37a98346e962914969ce71408e110900968f5`
