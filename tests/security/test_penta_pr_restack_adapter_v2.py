from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "supabase/migrations/20260904134400_penta_pr_restack_execution_adapter_v2.sql").read_text()
EDGE = (ROOT / "supabase/functions/penta-pr-restack-provider/index.ts").read_text()


def test_assignment_gate_is_exact_and_d2_bounded():
    assert "PR_RESTACK_CURRENT_MAIN" in SQL
    assert "provider_write_allowed" in SQL
    assert "D0','D1','D2" in SQL
    assert "HOLD_CURRENT_MAIN_ASSIGNMENT_DRIFT" in SQL
    assert "source_repo is distinct from 'crownthrive1/CrownThrive-OS'" in SQL


def test_provider_requires_service_role_and_exact_provider_readback():
    assert 'jwtRole(req) !== "service_role"' in EDGE
    assert 'mainSha !== req.expected_main_sha' in EDGE
    assert 'predecessorHead !== req.predecessor_head_sha' in EDGE
    assert 'readback.body?.draft === true' in EDGE
    assert 'String(readback.body?.head?.sha ?? "") === successorHead' in EDGE
    assert 'String(readback.body?.base?.ref ?? "") === "main"' in EDGE


def test_provider_is_draft_restack_only():
    assert 'method: "POST"' in EDGE
    assert 'draft: true' in EDGE
    assert 'merge_performed: false' in EDGE
    assert 'predecessor_close_performed: false' in EDGE
    assert 'certification_claimed: false' in EDGE
    assert 'authority_created: false' in EDGE
    assert '/merges' not in EDGE
    assert '/merge' not in EDGE
    assert 'method: "DELETE"' not in EDGE


def test_predecessor_history_and_zero_delta_are_fail_closed():
    assert 'predecessor.body?.state !== "open"' in EDGE
    assert 'HOLD_PREDECESSOR_ZERO_DELTA_RECLASSIFY' in EDGE
    assert 'HOLD_RESTACK_DIFF_PAGINATION_REQUIRED' in EDGE
    assert 'Predecessor branch/head/diff/history are preserved' in EDGE


def test_no_secret_material_is_serialized_to_evidence():
    assert "penta_pm_github_token" in EDGE
    assert "ghToken" in EDGE
    assert "penta_pm_github_token" not in SQL
    assert "raw_secret" not in SQL.lower()
