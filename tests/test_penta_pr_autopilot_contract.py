from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_penta_pr_autopilot_is_event_driven() -> None:
    workflow = read(".github/workflows/penta-pr-autopilot.yml")
    assert "pull_request_target:" in workflow
    assert "workflow_run:" in workflow
    assert 'workflows: ["Governed Merge Gate"]' in workflow
    assert "cron: '*/10 * * * *'" in workflow
    assert "penta_pr_autopilot.py" in workflow
    assert "PentaGate and PentaHeal preflight" in workflow
    assert "PentaTagger terminal provider readback" in workflow


def test_split_lifecycle_clocks_are_retired() -> None:
    workflow = read(".github/workflows/penta-pr-lifecycle.yml")
    assert "workflow_dispatch:" in workflow
    assert "pull_request_target:" not in workflow
    assert "schedule:" not in workflow
    assert "27 * * * *" not in workflow
    assert "47 * * * *" not in workflow


def test_autopilot_preserves_fail_closed_and_restack_contract() -> None:
    script = read("scripts/penta_pr_autopilot.py")
    assert 'AUTOPILOT_SELF_CHECK = "pentapr autopilot"' in script
    assert '"penta:hold" in labels' in script
    assert 'pull.get("draft")' in script
    assert 'pull.get("mergeable_state") != "behind"' in script
    assert 'f"/repos/{gh.repo}/pulls/{number}/update-branch"' in script
    assert "lifecycle.attempt_merge" in script
    assert "--allow-deadline-close" in script


def test_supabase_inventory_snapshot_is_not_a_mutable_expected_count() -> None:
    validator = read("scripts/validate_supabase_production_convergence_state.py")
    assert "local_count == expected_count" not in validator
    assert "local_count >= snapshot_count" in validator
    assert "repository_snapshot_migrations" in validator
    assert 'migration.get("gate") == "HOLD"' in validator
    assert 'migration.get("count_parity_is_not_custody_proof") is True' in validator
