from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/collision-governance-trusted-v2.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


class CollisionSnapshotRetryContractTests(unittest.TestCase):
    def test_transient_snapshot_retry_is_bounded(self) -> None:
        workflow = workflow_text()
        self.assertIn("max_attempts=3", workflow)
        self.assertIn('attempt=$((attempt + 1))', workflow)
        self.assertIn('"$attempt" -ge "$max_attempts"', workflow)
        self.assertIn("sleep $((attempt * 2))", workflow)

    def test_retry_predicate_only_tolerates_subthreshold_awareness(self) -> None:
        workflow = workflow_text()
        self.assertIn('fail_threshold=2', workflow)
        self.assertIn('"snapshot_changed_during_evaluation" in codes', workflow)
        self.assertIn('int(item.get("severity") or 0) >= fail_threshold', workflow)
        self.assertIn("and not material_collisions", workflow)
        self.assertIn("and not inspection_errors", workflow)
        self.assertIn("and main_stable", workflow)
        self.assertIn("and candidate_stable", workflow)

    def test_nonretryable_and_material_failures_remain_fail_closed(self) -> None:
        workflow = workflow_text()
        self.assertIn('if [[ "$retryable" != "true" ]]', workflow)
        self.assertIn('exit "$status"', workflow)
        self.assertIn('--fail-on-severity 2', workflow)

    def test_bounded_candidate_fence_can_resolve_only_transient_global_churn(self) -> None:
        workflow = workflow_text()
        self.assertIn('if [[ "$attempt" -ge "$max_attempts" ]]', workflow)
        self.assertIn('global_snapshot_churn_accepted_after_bounded_candidate_fence', workflow)
        self.assertIn('candidate_bounded_snapshot_resolution', workflow)
        self.assertIn('candidate_bounded_fence_after_transient_global_churn', workflow)
        self.assertIn(
            '"material_collision_count": sum(1 for item in collisions if int(item.get("severity") or 0) >= 2)',
            workflow,
        )
        self.assertIn('"inspection_error_count": len(report.get("inspection_errors") or {})', workflow)
        self.assertIn('decision["max_severity"] = observed_max', workflow)

    def test_trusted_checkout_uses_control_plane_event_commit(self) -> None:
        workflow = workflow_text()
        self.assertIn('ref: ${{ github.sha }}', workflow)
        self.assertNotIn('ref: ${{ github.event.pull_request.base.sha }}', workflow)
        self.assertIn('Checkout trusted control-plane commit without credentials', workflow)

    def test_each_attempt_recomputes_and_preserves_evidence(self) -> None:
        workflow = workflow_text()
        self.assertIn('report="collision-governance-v2-report-attempt-${attempt}.json"', workflow)
        self.assertEqual(workflow.count("python3 scripts/governed_collision_agent_v2_trusted.py"), 1)
        self.assertEqual(workflow.count("python3 scripts/governed_collision_agent_v2.py"), 1)
        self.assertIn('--event-base-sha "${{ github.event.pull_request.base.sha }}"', workflow)
        self.assertNotIn('--expected-main-sha', workflow)
        self.assertIn('cp "$report" collision-governance-v2-report.json', workflow)
        self.assertIn("recomputing from fresh provider state", workflow)

    def test_main_reconciliation_threshold_is_unchanged(self) -> None:
        workflow = workflow_text()
        self.assertIn('--fail-on-severity 6', workflow)
        self.assertNotIn("D3", workflow)


if __name__ == "__main__":
    unittest.main()
