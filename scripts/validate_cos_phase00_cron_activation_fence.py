#!/usr/bin/env python3
"""Fail-closed static checks for the COS Phase 00 cron activation fence."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "supabase/migrations/20260830035900_cos_phase00_cron_activation_fence_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260830035900_cos_phase00_cron_activation_fence_v1.rollback.sql"
EVENT = "ct.maintenance.2026-08-29.cos-v1-interactive-build.v1"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    forward = FORWARD.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")
    lower = forward.lower()

    checks = {
        "exact_event": EVENT in forward,
        "maintenance_readback": "chlom_runtime.maintenance_state_v1()" in forward,
        "before_insert": "before insert or update of active on cron.job" in lower,
        "forces_inactive": "new.active := false" in lower,
        "does_not_unschedule": "cron.unschedule" not in lower,
        "does_not_disable_operation": "operation_registry_v2" not in lower,
        "does_not_disable_executor": "operation_executors_v3" not in lower,
        "no_delete": "delete from" not in lower,
        "no_d3": "d3" not in lower,
        "rollback_exact_event": EVENT in rollback,
        "rollback_blocked_while_active": "rollback_blocked_active_cos_build_session" in rollback,
        "rollback_drops_trigger": "drop trigger if exists cos_build_session_cron_activation_fence_v1 on cron.job" in rollback.lower(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    require(not failures, "COS Phase 00 cron fence validation failed: " + ", ".join(failures))
    print(f"COS Phase 00 cron activation fence: PASS ({len(checks)} invariants)")


if __name__ == "__main__":
    main()
