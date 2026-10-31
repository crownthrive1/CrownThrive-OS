from pathlib import Path

SOURCE = Path("supabase/functions/penta-institutional-pr-terminal-provider/index.ts")


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_terminal_provider_binds_institutional_schema():
    src = _source()
    assert 'sb.schema("integration_control")' in src
    assert 'institutional.rpc("penta_pr_closeout_claim_v1"' in src
    assert 'institutional.rpc("penta_pr_closeout_result_v1"' in src


def test_terminal_provider_never_defaults_privileged_rpcs_to_public_schema():
    src = _source()
    assert 'sb.rpc("penta_pr_closeout_claim_v1"' not in src
    assert 'sb.rpc("penta_pr_closeout_result_v1"' not in src


def test_terminal_provider_preserves_one_time_wake_and_repo_allowlist():
    src = _source()
    assert 'ONE_TIME_WAKE_REQUIRED' in src
    assert 'REPOSITORY_NOT_ALLOWLISTED' in src
    assert 'action.repository !== "crownthrive1/CrownThrive-OS"' in src


def test_terminal_mutation_remains_exact_head_fail_closed():
    src = _source()
    assert 'EXACT_HEAD_MISMATCH' in src
    assert 'if (!action.expected_head_sha || pull.head.sha !== action.expected_head_sha)' in src
    assert 'if (pull.draft) throw new Error("PR_DRAFT")' in src


def test_observe_path_is_read_only_and_records_no_authority_expansion():
    src = _source()
    observe_start = src.index('if (action.action_kind === "observe")')
    observe_end = src.index('if (!GH) throw new Error("MISSING_GITHUB_PROVIDER_CREDENTIAL")')
    observe = src[observe_start:observe_end]
    assert 'provider_write: false' in observe
    assert 'authority_expansion: false' in observe
    assert 'method: "PUT"' not in observe
    assert 'method: "PATCH"' not in observe
