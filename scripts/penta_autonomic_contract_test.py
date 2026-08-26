#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'supabase/migrations/20260826185700_pentagreen_hourly_candidate_identity_fix_v1.sql'
SUITE = ROOT / 'supabase/migrations/20260826190019_penta_autonomic_incident_response_suite_v1.sql'
RECURRENCE = ROOT / 'supabase/migrations/20260826200533_penta_autonomic_recurrence_and_maker_routing_v2.sql'
STATUS = ROOT / 'supabase/migrations/20260826200616_pentagreen_hourly_status_identity_projection_v2.sql'
HARDEN = ROOT / 'supabase/migrations/20260826201527_penta_autonomic_security_definer_rpc_hardening_v1.sql'
DOC = ROOT / 'docs/phase3/PENTA_AUTONOMIC_OPERATIONS.md'
MAKER_DOC = ROOT / 'docs/phase3/PENTA_MAKER.md'


def require(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f'missing contract token: {needle}')


def main() -> None:
    fix = FIX.read_text()
    suite = SUITE.read_text()
    recurrence = RECURRENCE.read_text()
    status = STATUS.read_text()
    harden = HARDEN.read_text()
    doc = DOC.read_text()
    maker_doc = MAKER_DOC.read_text()

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

    # Original safety invariants remain intact.
    if 'drop constraint thriveevergreen_packets_candidate_identity_v1' in (suite + recurrence + status + harden).lower():
        raise AssertionError('protective PentaGreen candidate identity constraint must not be dropped')
    require(suite, "p_dry_run boolean default true")
    require(suite, "'dry_run'")
    require(suite, "canonical_records_deleted',false")
    require(suite, "'money_movement_function_invoked'")
    require(suite, "'checkout_activation_invoked'")

    # Recurrence identity must include the failed run id. Error-family-only
    # dedupe is not sufficient because a later 23514 is a new occurrence.
    require(recurrence, "coalesce(v_failed.error_code,'unknown')||':'||v_failed.run_id::text")
    require(recurrence, "NO_ACTIVE_PENTAGREEN_FAILURE")
    require(recurrence, "INCIDENT_OCCURRENCE_ALREADY_RESOLVED")
    require(recurrence, "REMEDIATION_ALREADY_APPLIED_FOR_THIS_OCCURRENCE")
    require(recurrence, "s.started_at>f.started_at")

    # PentaMaker selects the authoring Penta; PentaMail is transport.
    require(recurrence, "'penta.maker','PentaMaker'")
    require(recurrence, "penta_maker_select_v1")
    require(recurrence, "penta_mail_enqueue_with_maker_v1")
    require(recurrence, "'proof','proof','penta.reports'")
    require(recurrence, "'incident','incident','penta.notifs'")
    require(maker_doc, "PentaMail** transports")
    require(maker_doc, "PentaReports** authors evidence-backed proof")

    # Status must project the real candidate identity fields. It must never
    # coalesce a commercial SKU into candidate_ref.
    require(status, "'contract','ct.status.thriveevergreen-hourly-product-orchestration.v1.2'")
    require(status, "'error_code',latest.error_code")
    require(status, "'candidate_ref',latest.selected_candidate_ref")
    require(status, "'candidate_sku',latest.selected_sku")
    if "coalesce(latest.selected_candidate_ref,latest.selected_sku)" in status:
        raise AssertionError('candidate_ref must not alias selected_sku')

    # Every autonomic SECURITY DEFINER mutation/control RPC found by the
    # production security advisor is service-role-only at the API perimeter.
    for signature in (
        'public.penta_backup_control_plane_v1(text,text)',
        'public.penta_flush_ephemeral_v1(interval,boolean)',
        'public.penta_redblue_pentagreen_23514_v1()',
        'public.penta_remediate_pentagreen_23514_v1()',
        'public.penta_restore_plan_v1(uuid)',
    ):
        require(harden, f'revoke execute on function {signature} from public, anon, authenticated;')
        require(harden, f'grant execute on function {signature} to service_role;')

    require(doc, "run-occurrence fingerprint")
    require(doc, "candidate_ref = NULL")
    require(doc, "must not manufacture a PASS from stale evidence")

    print('PENTA autonomic operations contract: PASS')


if __name__ == '__main__':
    main()
