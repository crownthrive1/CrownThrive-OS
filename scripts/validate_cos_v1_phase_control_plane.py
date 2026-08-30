#!/usr/bin/env python3
"""Static fail-closed validation for the COS V1 phase/certification control plane."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_MIGRATION = ROOT / "supabase/migrations/20260830020500_cos_v1_phase_control_plane_v1.sql"
BASE_ROLLBACK = ROOT / "supabase/rollbacks/20260830020500_cos_v1_phase_control_plane_v1.rollback.sql"
D3_MIGRATION = ROOT / "supabase/migrations/20260830021100_cos_v1_phase15_d3_release_gate_v1.sql"
D3_ROLLBACK = ROOT / "supabase/rollbacks/20260830021100_cos_v1_phase15_d3_release_gate_v1.rollback.sql"

EXPECTED_PHASES = [f"{n:02d}" for n in range(16)]
EXPECTED_COMMON_GATES = {
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
D3_GATE = "d3_human_release_approval"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    base = read(BASE_MIGRATION)
    base_rollback = read(BASE_ROLLBACK)
    d3 = read(D3_MIGRATION)
    d3_rollback = read(D3_ROLLBACK)
    lower = (base + "\n" + d3).lower()

    phase_ids = sorted(set(re.findall(r"\('([01][0-9])',\s*\d+,", base)))
    require(phase_ids == EXPECTED_PHASES, f"phase seed drift: {phase_ids}")

    common_gates = set(re.findall(r"\(\d+,'([a-z0-9_]+)',(?:true|false),(?:true|false),", base))
    require(common_gates == EXPECTED_COMMON_GATES, f"common gate seed drift: {sorted(common_gates)}")
    require(f"'15','{D3_GATE}',18,true,true,false" in d3, "Phase 15 D3 release gate missing or not mandatory/independent")

    require("originator_cannot_verify_independent_gate" in base, "missing originator/verifier separation")
    require("provider_production_readback" in base, "missing provider/production readback gate")
    require("chlom_runtime.append_dail_event" in base, "missing DAIL terminal certification")
    require("predecessor_not_certified" in base, "missing predecessor certification gate")
    require("phase_execution_already_active" in base, "missing duplicate-active-execution guard")
    require("cos_phase_gate_receipts_are_append_only" in base, "missing append-only gate receipt guard")

    # D3 release authority must never be a caller-supplied PASS string.
    require("use_cos_phase_bind_d3_approval_v1" in d3, "generic receipt path can record D3 approval")
    require("cos_phase_bind_d3_approval_v1" in d3, "missing governed D3 binding function")
    require("'cos.production_release' = any(b.authorized_actions)" in d3, "D3 campaign lacks explicit COS release action check")
    require("'repository','crownthrive1/CrownThrive-OS'" in d3, "D3 campaign lacks exact repository binding")
    require("'source_sha',v_source_sha" in d3, "D3 campaign lacks exact source SHA binding")
    require("not exists(\n      select 1 from penta_runtime.d3_campaign_holds_v1" in d3, "D3 bind path does not honor campaign holds")
    require("phase15_d3_approval_expired_held_or_drifted" in d3, "Phase 15 finalizer does not revalidate D3 authority")
    require("phase15_d3_approval_not_bound" in d3, "Phase 15 finalizer does not require bound D3 authority")
    require("state='released',production_sha=v_source_sha,released_at=now()" in d3, "Phase 15 does not bind production SHA/release")

    # Existing standing D3 campaign must not accidentally satisfy this contract by name.
    require("ct.penta.flow-control.20260826.v1" not in d3, "hard-coded standing campaign would expand authority")

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
        require(token not in lower, f"forbidden authority expansion in forward migrations: {token}")

    require("rollback_blocked_cos_phase_execution_history_exists" in base_rollback, "base rollback is not history-safe")
    require("rollback_blocked_phase15_execution_history_exists" in d3_rollback, "D3 rollback is not Phase-15-history-safe")
    require("create or replace function integration_control.cos_phase_record_gate_v1" in d3_rollback, "D3 rollback does not restore generic gate function deterministically")
    require("create or replace function integration_control.cos_phase_finalize_v1" in d3_rollback, "D3 rollback does not restore finalizer deterministically")
    require("drop table" not in base.lower(), "base forward migration must be additive")
    require("drop table" not in d3.lower(), "D3 forward migration must be additive")

    print("COS V1 phase control plane static validation: PASS")
    print(f"phases={len(phase_ids)} common_gates={len(common_gates)} phase15_extra_gates=1 total_requirement_rows={len(phase_ids)*len(common_gates)+1}")


if __name__ == "__main__":
    main()
