#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'supabase/migrations/20260826185700_pentagreen_hourly_candidate_identity_fix_v1.sql'
SUITE = ROOT / 'supabase/migrations/20260826190019_penta_autonomic_incident_response_suite_v1.sql'
DOC = ROOT / 'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md'


def require(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f'missing contract token: {needle}')


def main() -> None:
    fix = FIX.read_text()
    suite = SUITE.read_text()
    doc = DOC.read_text()

    require(fix, "v_snapshot->>''candidate_type'',case when")
    require(fix, "''proprietary_product_candidate''")
    require(fix, "else null end")
    require(fix, "run_thriveevergreen_hourly_product_cycle_v1")

    for name in (
        'PentaReports', 'PentaNotifs', 'PentaFlagger', 'PentaTagger',
        'PentaHarvestor', 'PentaBackup', 'PentaRestore', 'PentaFlush'
    ):
        require(suite, name)
        require(doc, name)

    for fn in (
        'penta_incident_control_tick_v1',
        'penta_remediate_pentagreen_23514_v1',
        'penta_redblue_pentagreen_23514_v1',
        'penta_backup_control_plane_v1',
        'penta_restore_plan_v1',
        'penta_flush_ephemeral_v1',
    ):
        require(suite, fn)

    # Safety invariants: repair the writer, do not weaken the database guard;
    # restore and flush remain fail-closed/bounded by default.
    if 'drop constraint thriveevergreen_packets_candidate_identity_v1' in suite.lower():
        raise AssertionError('protective PentaGreen candidate identity constraint must not be dropped')
    require(suite, "p_dry_run boolean default true")
    require(suite, "'dry_run'")
    require(suite, "canonical_records_deleted',false")
    require(suite, "economic_activation','HOLD_PENDING_GOVERNANCE_EVIDENCE'")
    require(suite, "'money_movement_function_invoked'")
    require(suite, "'checkout_activation_invoked'")

    print('PENTA autonomic operations contract: PASS')


if __name__ == '__main__':
    main()
