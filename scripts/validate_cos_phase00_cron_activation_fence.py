#!/usr/bin/env python3
"""Fail-closed checks for the provider-compatible COS Phase 00 scheduler fence."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "supabase/migrations/20260830035900_cos_phase00_cron_activation_fence_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260830035900_cos_phase00_cron_activation_fence_v1.rollback.sql"
EVENT = "ct.maintenance.2026-08-29.cos-v1-interactive-build.v1"
ASSIGN_HASH = "3a1bec7e76e1f092c3b3d17890d7ffc33d8c401fb375908d4965550d022cf218"
RECONCILE_HASH = "e1a5d0458df8da996a29719a80a990a34017370bd122161a99d021dab00048cd"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    forward = FORWARD.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")
    lower = forward.lower()
    rlower = rollback.lower()

    checks = {
        "exact_event": EVENT in forward,
        "maintenance_readback": "chlom_runtime.maintenance_state_v1()" in forward,
        "assign_runtime_hash_pinned": ASSIGN_HASH in forward,
        "reconcile_runtime_hash_pinned": RECONCILE_HASH in forward,
        "assign_drift_abort": "pentacrons_assign_operation_v1_runtime_drift" in forward,
        "reconcile_drift_abort": "reconcile_collision_domain_slots_v1_runtime_drift" in forward,
        "assign_private_clone": "pentacrons_assign_operation_unfenced_v1" in forward,
        "reconcile_private_clone": "reconcile_collision_domain_slots_unfenced_v1" in forward,
        "assign_original_wrapper": "create or replace function pentatime.pentacrons_assign_operation_v1" in lower,
        "reconcile_original_wrapper": "create or replace function pentatime.reconcile_collision_domain_slots_v1" in lower,
        "assign_maintenance_hold": "HOLD_COS_BUILD_SESSION_MAINTENANCE" in forward,
        "assign_dnd_preflight": "scheduler.assign.operation" in forward and "penta_dnd_preflight_v1" in forward,
        "reconcile_dnd_preflight": "scheduler.reconcile.collision-domain" in forward,
        "manual_execution_preserved": "manual_execution_preserved" in forward,
        "unfenced_assign_denied_service_role": "pentacrons_assign_operation_unfenced_v1(text,text,text,text,text)\n  from public,anon,authenticated,service_role" in forward,
        "unfenced_reconcile_denied_service_role": "reconcile_collision_domain_slots_unfenced_v1(text)\n  from public,anon,authenticated,service_role" in forward,
        "no_cron_job_trigger": "trigger" not in lower or "on cron.job" not in lower,
        "no_cron_job_direct_ddl": "alter table cron.job" not in lower and "create trigger" not in lower,
        "does_not_unschedule": "cron.unschedule" not in lower,
        "does_not_disable_operation": "operation_registry_v2" not in lower,
        "does_not_disable_executor": "operation_executors_v3" not in lower,
        "no_delete": "delete from" not in lower,
        "rollback_exact_event": EVENT in rollback,
        "rollback_blocked_while_active": "rollback_blocked_active_cos_build_session" in rollback,
        "rollback_uses_assign_clone": "pentacrons_assign_operation_unfenced_v1" in rollback,
        "rollback_uses_reconcile_clone": "reconcile_collision_domain_slots_unfenced_v1" in rollback,
        "rollback_restores_original_assign": "pentacrons_assign_operation_v1'" in rollback,
        "rollback_restores_original_reconcile": "reconcile_collision_domain_slots_v1'" in rollback,
        "rollback_removes_clones": "drop function if exists pentatime.pentacrons_assign_operation_unfenced_v1" in rlower and "drop function if exists pentatime.reconcile_collision_domain_slots_unfenced_v1" in rlower,
        "rollback_no_cron_owned_ddl": "on cron.job" not in rlower and "alter table cron.job" not in rlower,
    }

    failures = [name for name, passed in checks.items() if not passed]
    require(not failures, "COS Phase 00 scheduler fence validation failed: " + ", ".join(failures))
    print(f"COS Phase 00 provider-compatible scheduler fence: PASS ({len(checks)} invariants)")


if __name__ == "__main__":
    main()
