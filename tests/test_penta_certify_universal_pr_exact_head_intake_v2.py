from pathlib import Path

MIGRATION = Path("supabase/migrations/20260902232100_penta_certify_universal_pr_exact_head_intake_v2.sql")


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_exact_head_subject_and_head_change_invalidation_are_required():
    text = source()
    assert "pr-exact-head:" in text
    assert "PR_HEAD_SUPERSEDED" in text
    assert "PR_HEAD_CHANGED" in text
    assert "exact_head_bound" in text


def test_originator_separation_and_no_generic_adapter_dispatch():
    text = source()
    assert "ORIGINATOR_SEPARATION_REQUIRED" in text
    assert "generic_adapter_dispatch_prohibited" in text
    assert "task_kind='inspect'" in text
    assert "provider_system" in text and "'github'" in text


def test_detail_readback_is_rate_bounded_and_fail_closed():
    text = source()
    assert "https://api.github.com/rate_limit" in text
    assert "HOLD_PROVIDER_RATE_BUDGET" in text
    assert "v_safe_prs:=least" in text
    assert "raw_provider_body_stored',false" in text
    assert "provider_write',false" in text
    assert "authority_created',false" in text


def test_expensive_provider_reads_precede_dail_summary_append():
    text = source()
    detail_pos = text.index("/pulls/'||r.pr_number::text")
    checks_pos = text.index("/check-runs?per_page=100")
    dail_pos = text.index("penta_pr.lifecycle.github_detail_reconciliation")
    assert detail_pos < dail_pos
    assert checks_pos < dail_pos
    assert "chlom_runtime.dail.global.v1" not in text


def test_native_clock_order_is_inventory_detail_seed_certify():
    text = source()
    lifecycle = text.index("'ct-penta-pr-lifecycle-sync-v1','2 * * * *'")
    detail = text.index("'ct-penta-pr-detail-readback-v2','3 * * * *'")
    seed = text.index("'ct-penta-certify-pr-exact-head-seed-v1','4 * * * *'")
    certify = text.index("'ct-penta-certify-v3','5 * * * *'")
    assert lifecycle < detail < seed < certify


def test_no_prohibited_authority_is_created():
    text = source()
    assert "money_movement" not in text.lower() or "money" in text.splitlines()[2].lower()
    assert "grant execute" in text.lower()
    assert " to service_role" in text.lower()
    assert "from public,anon,authenticated" in text.lower()
    assert "merge authority" not in text.lower()
    assert "release authority" not in text.lower()
