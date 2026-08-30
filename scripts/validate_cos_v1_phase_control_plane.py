#!/usr/bin/env python3
"""Static fail-closed validation for the COS V1 phase control-plane migration."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260830020500_cos_v1_phase_control_plane_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260830020500_cos_v1_phase_control_plane_v1.rollback.sql"

EXPECTED_PHASES = [f"{n:02d}" for n in range(16)]
EXPECTED_GATES = {
    "pre_state",
    "census_dependency_read",
    "r1_rollback",
    "static_unit_test",
    "contract_test",
    "integration_test",
    "security_test",
    "failure_retry_test",
    "canary",
    "provider_production_readback",
    "independent_certification",
    "regression_test",
    "cleanup_retire_superseded",
    "dail_binding",
    "penta_context_census_binding",
    "chlom_binding",
    "governed_docs_projection",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    require(MIGRATION.is_file(), f"missing migration: {MIGRATION}")
    require(ROLLBACK.is_file(), f"missing rollback: {ROLLBACK}")
    migration = MIGRATION.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")
    lower = migration.lower()

    phase_ids = sorted(set(re.findall(r"\('([01][0-9])',\s*\d+,", migration)))
    require(phase_ids == EXPECTED_PHASES, f"phase seed drift: {phase_ids}")

    gate_names = set(re.findall(r"\(\d+,'([a-z0-9_]+)',(?:true|false),(?:true|false),", migration))
    require(gate_names == EXPECTED_GATES, f"gate seed drift: {sorted(gate_names)}")

    require("originator_cannot_verify_independent_gate" in migration, "missing originator/verifier separation")
    require("provider_production_readback" in migration, "missing provider/production readback gate")
    require("chlom_runtime.append_dail_event" in migration, "missing DAIL terminal certification")
    require("state='released',production_sha=v_source_sha,released_at=now()" in migration, "phase 15 does not bind production SHA/release")
    require("predecessor_not_certified" in migration, "missing predecessor certification gate")
    require("phase_execution_already_active" in migration, "missing duplicate-active-execution guard")
    require("cos_phase_gate_receipts_are_append_only" in migration, "missing append-only gate receipt guard")

    for table in (
        "cos_phase_registry_v1",
        "cos_phase_executions_v1",
        "cos_phase_gate_requirements_v1",
        "cos_phase_gate_receipts_v1",
    ):
        require(f"alter table integration_control.{table} enable row level security" in lower, f"RLS not enabled: {table}")
        require(f"alter table integration_control.{table} force row level security" in lower, f"FORCE RLS missing: {table}")

    forbidden = (
        "disable row level security",
        "grant all on schema",
        "alter role",
        "create extension",
        "cron.schedule",
        "net.http",
    )
    for token in forbidden:
        require(token not in lower, f"forbidden authority expansion in migration: {token}")

    require("rollback_blocked_cos_phase_execution_history_exists" in rollback, "rollback is not history-safe")
    require("drop table" not in lower, "forward migration must be additive")

    print("COS V1 phase control plane static validation: PASS")
    print(f"phases={len(phase_ids)} gates_per_phase={len(gate_names)}")


if __name__ == "__main__":
    main()
