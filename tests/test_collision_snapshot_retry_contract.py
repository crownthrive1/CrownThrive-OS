from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/collision-governance-trusted-v2.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_transient_snapshot_retry_is_bounded() -> None:
    workflow = workflow_text()
    assert "max_attempts=3" in workflow
    assert 'attempt=$((attempt + 1))' in workflow
    assert '"$attempt" -ge "$max_attempts"' in workflow
    assert "sleep $((attempt * 2))" in workflow


def test_retry_predicate_only_tolerates_subthreshold_awareness() -> None:
    workflow = workflow_text()
    assert 'fail_threshold=2' in workflow
    assert '"snapshot_changed_during_evaluation" in codes' in workflow
    assert 'int(item.get("severity") or 0) >= fail_threshold' in workflow
    assert "and not material_collisions" in workflow
    assert "and not inspection_errors" in workflow
    assert "and main_stable" in workflow
    assert "and candidate_stable" in workflow


def test_retry_exhaustion_and_material_failures_remain_fail_closed() -> None:
    workflow = workflow_text()
    assert 'if [[ "$retryable" != "true" || "$attempt" -ge "$max_attempts" ]]' in workflow
    assert 'exit "$status"' in workflow
    assert '--fail-on-severity "$fail_threshold"' in workflow


def test_each_attempt_recomputes_and_preserves_evidence() -> None:
    workflow = workflow_text()
    assert 'report="collision-governance-v2-report-attempt-${attempt}.json"' in workflow
    assert workflow.count("python3 scripts/governed_collision_agent_v2.py") == 2
    assert 'cp "$report" collision-governance-v2-report.json' in workflow
    assert "recomputing from fresh provider state" in workflow


def test_main_reconciliation_threshold_is_unchanged() -> None:
    workflow = workflow_text()
    assert '--fail-on-severity 6' in workflow
    assert "D3" not in workflow
