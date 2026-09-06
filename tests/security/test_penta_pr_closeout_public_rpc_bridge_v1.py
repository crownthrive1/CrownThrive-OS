from pathlib import Path

MIGRATION = Path("supabase/migrations/20260906001500_penta_pr_closeout_public_rpc_bridge_v1.sql")


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_public_bridges_delegate_only_to_governed_implementations():
    text = source()
    assert "select integration_control.penta_pr_closeout_claim_v1(" in text
    assert "select integration_control.penta_pr_closeout_result_v1(" in text
    assert "create or replace function public.penta_pr_closeout_claim_v1" in text
    assert "create or replace function public.penta_pr_closeout_result_v1" in text


def test_public_anon_authenticated_have_no_execute_authority():
    text = source().lower()
    assert "revoke all on function public.penta_pr_closeout_claim_v1(uuid,text,text)" in text
    assert "revoke all on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text)" in text
    assert "from public, anon, authenticated" in text
    assert "to service_role" in text


def test_wrapper_does_not_add_provider_mutation_or_bypass_logic():
    text = source().lower()
    for forbidden in (
        "http_post",
        "http_put",
        "http_patch",
        "http_delete",
        "merge_pull_request",
        "force merge",
        "branch deletion",
        "credential rotation",
    ):
        assert forbidden not in text
    assert "security definer" in text
    assert "set search_path to 'pg_catalog', 'integration_control'" in text


def test_result_bridge_preserves_exact_evidence_arguments():
    text = source()
    for arg in (
        "p_request_sha256",
        "p_response_sha256",
        "p_readback_pass",
        "p_pr_number",
        "p_base_ref",
        "p_head_sha",
        "p_source_branch",
    ):
        assert arg in text


def test_claim_bridge_preserves_wake_token_and_worker_identity():
    text = source()
    assert "p_wake_token text" in text
    assert "p_worker_id text" in text
    assert "p_wake_token," in text
    assert "p_worker_id" in text