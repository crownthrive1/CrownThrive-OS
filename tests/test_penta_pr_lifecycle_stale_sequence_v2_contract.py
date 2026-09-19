from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260902193000_penta_pr_lifecycle_stale_sequence_fix_v2.sql"
)
ROLLBACK = Path(
    "supabase/rollback/20260902193000_penta_pr_lifecycle_stale_sequence_fix_v2_rollback.sql"
)


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_stale_classification_no_longer_requires_successor_before_classification():
    sql = _normalized(MIGRATION)
    assert "stale classification is allowed before successor creation" in sql
    assert "stale_predecessor_requires_successor_or_handoff_before_close" not in sql
    assert "handoff_required_before_terminalization" in sql
    assert "invalid_successor_pr_number" in sql


def test_terminal_readback_fail_closes_stale_predecessor_without_handoff():
    sql = _normalized(MIGRATION)
    assert "for update" in sql
    assert "hold_stale_predecessor_handoff_required" in sql
    assert "successor_pr_number" in sql
    assert "handoff_receipt_ref" in sql
    assert "hold_stale_predecessor_must_close_not_merge" in sql


def test_terminal_readback_cannot_relabel_exact_row_to_bypass_policy():
    sql = _normalized(MIGRATION)
    assert "v_stored_class := upper" in sql
    assert "hold_classification_mismatch" in sql
    assert "stored_classification" in sql
    assert "requested_classification" in sql


def test_security_boundary_and_exact_identity_remain_fail_closed():
    sql = _normalized(MIGRATION)
    assert "security definer" in sql
    assert "service_role_required" in sql
    assert "exact_pr_identity_required" in sql
    assert "and head_sha = p_head_sha" in sql
    assert "terminal_state is null" in sql
    assert "authority_created', false" in sql
    assert "grant execute" not in sql
    assert "grant all" not in sql


def test_external_hold_and_provenance_guards_are_preserved():
    sql = _normalized(MIGRATION)
    assert "external_hold_review_at_required" in sql
    assert "provenance_ref_required" in sql
    assert "pr_owner_required" in sql
    assert "next_predicate_required" in sql


def test_rollback_restores_prechange_classifier_and_readback_contract():
    sql = _normalized(ROLLBACK)
    assert "fail-closed rollback" in sql
    assert "stale_predecessor_requires_successor_or_handoff_before_close" in sql
    assert "create or replace function public.penta_pr_record_provider_terminal_readback_v2" in sql
    assert "hold_stale_predecessor_handoff_required" not in sql
    assert "grant execute" not in sql
