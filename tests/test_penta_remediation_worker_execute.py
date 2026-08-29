from __future__ import annotations

import unittest
from pathlib import Path

from scripts.penta_remediation_worker_execute import assigned_pentas_from_labels, finding_id_from_pr


class PentaRemediationWorkerExecutionTests(unittest.TestCase):
    def test_finding_marker_is_extracted_from_remediation_pr(self) -> None:
        pr = {"body": "<!-- penta-self-remediation:bf3636f9-6578-474a-9e64-c99c6b3716b7 -->\nCloses #1037"}
        self.assertEqual(
            finding_id_from_pr(pr),
            "bf3636f9-6578-474a-9e64-c99c6b3716b7",
        )

    def test_assignment_labels_become_worker_packet(self) -> None:
        labels = {
            "penta:assigned:pentabuild",
            "penta:assigned:pentacertify",
            "penta:hold",
        }
        self.assertEqual(
            assigned_pentas_from_labels(labels),
            ["pentabuild", "pentacertify"],
        )

    def test_trusted_worker_has_event_and_sweep_paths(self) -> None:
        workflow = Path(".github/workflows/penta-remediation-worker-execution.yml").read_text(encoding="utf-8")
        self.assertIn("types: [penta-remediation-execute]", workflow)
        self.assertIn("cron: '*/5 * * * *'", workflow)
        self.assertIn("PENTA_PM_GITHUB_TOKEN", workflow)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", workflow)
        self.assertIn("scripts/penta_remediation_worker_execute.py", workflow)

    def test_assignment_dispatches_execution_after_metadata(self) -> None:
        source = Path("scripts/penta_pm_remediation_assign.py").read_text(encoding="utf-8")
        self.assertIn('EXECUTION_EVENT = "penta-remediation-execute"', source)
        self.assertIn("execution_dispatch = dispatch_execution", source)
        self.assertIn('"state": "ASSIGNED_AND_DISPATCHED"', source)

    def test_database_bridge_is_durable_and_fail_closed(self) -> None:
        migration = Path(
            "supabase/migrations/20260829183000_penta_pm_assignment_execution_bridge_v1.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("remediation_execution_queue_v1", migration)
        self.assertIn("pgmq.send('penta_execution'", migration)
        self.assertIn("penta_os20.execution_tasks", migration)
        self.assertIn("penta_remediation_execution_claim_v1", migration)
        self.assertIn("penta_remediation_execute_known_v1", migration)
        self.assertIn("penta_remediation_execution_reconcile_v1", migration)
        self.assertIn("D3_HUMAN_RESERVED", migration)
        self.assertIn("authority_manufactured", migration)

    def test_verified_state_is_only_path_that_releases_hold(self) -> None:
        source = Path("scripts/penta_remediation_worker_execute.py").read_text(encoding="utf-8")
        verified_block = source.split('if state == "verified":', 1)[1].split('elif state in', 1)[0]
        self.assertIn("mark_verified_pr", verified_block)
        self.assertIn('if "penta:hold" in labels:', source)
        self.assertNotIn("penta:hold", source.split("def adopt_pr", 1)[0])


if __name__ == "__main__":
    unittest.main()
