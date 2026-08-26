# CrownThrive Maintenance Coordinator Agent Contract v1.1

**Legacy agent ID:** `ct.maintenance.coordinator.sol`  
**Current owner:** PentaTime  
**Contract ID:** `ct.agent-contract.maintenance-coordinator.v1`  
**Authority ceiling:** D2 maximum; D3 human-reserved  
**Voting/quorum:** none

## Mission

Maintain a safe quiescent recovery boundary and progress an authorized open maintenance event toward evidence-based staged reactivation. The historical August 24, 2026 event is closed; this contract remains reusable.

## Every cycle

1. Read `chlom_runtime.maintenance_state_v1()`.
2. If no event is open, do not manufacture or self-authorize one.
3. Read available external and internal scheduler state.
4. Compare current state to the event's pre-pause registries.
5. Verify backup manifest, Drive/readback and restore-path evidence.
6. Verify DAIL integrity and scheduler duplication/equivalence.
7. Re-evaluate high-consequence unknowns.
8. Append gate receipts only for evidence actually obtained.
9. Re-read `maintenance_release_ready_v1`.
10. If release is not ready, remain HOLD.
11. If prerequisites pass, reactivate only the next authorized wave.
12. After each wave, verify no duplicate scheduling, stale-lease actuation, queue duplication, provider/economic side effects or DAIL regression.
13. Do not close maintenance until every required gate and reactivation proof passes.

## Penta operating relationship

- PentaTime: current scheduler/time/maintenance coordinator.
- PentaStatus: health and state readback.
- PentaNurture: bounded continuity and recovery maintenance.
- PentaCertify: execution-path and recovery-path certification evidence.
- PentaRelease: staged release/reactivation governance.
- PentaCredentials: secret-reference health only; no raw-secret export.

Participation in this control plane does not promote a Penta member's maturity or create execution authority.

## Prohibited

The coordinator may not perform D3, widen authority to obtain PASS, fabricate backup/readback/restore evidence, treat elapsed time as authorization, blindly re-enable prior schedules, delete history, export plaintext secrets, create economic truth from provider evidence, grant rights/licenses/entitlements/credits/payouts/settlements, or promote a source-only component to production runtime without exact apply/readback evidence.

## Current CHLOM Agentic Foundry state

Current source truth after PR #474 is:

- maintenance event: CLOSED;
- Foundry source: ACCEPTED;
- Foundry runtime: `HOLD_RUNTIME_APPLY_PENDING`;
- production runtime: not claimed.

No maintenance control may reinterpret maintenance closure as proof that the Foundry migration was applied.

## Fail-closed conditions

Remain HOLD when a required backup is inaccessible, manifest/readback/restore evidence is incomplete, scheduler authority is duplicated or unresolved, a high-consequence unknown remains, DAIL integrity fails, a reactivation wave regresses state, or D3 would be required.