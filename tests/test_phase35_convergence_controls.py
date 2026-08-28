from __future__ import annotations

import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import upsert_pr_governance_state as governance  # noqa: E402


def forbidden_error() -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.github.test/actions/runs",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )


class Phase35ConvergenceControlTests(unittest.TestCase):
    def test_actions_403_uses_trusted_event_and_receipts_evidence_hold(self):
        event = {
            "workflow_run": {
                "id": 12345,
                "name": "Security Governance",
                "status": "completed",
                "conclusion": "failure",
                "head_sha": "abc123",
                "head_branch": "feature/example",
            }
        }
        original_api = governance.api

        def deny_actions(method: str, path: str, data=None):
            self.assertEqual(method, "GET")
            self.assertIn("/actions/runs?", path)
            raise forbidden_error()

        governance.api = deny_actions
        try:
            runs, state, reason, http_status = governance.latest_workflows(
                "crownthrive1/CrownThrive-OS",
                "abc123",
                event,
            )
        finally:
            governance.api = original_api

        self.assertEqual(state, "DEGRADED")
        self.assertEqual(reason, "ACTIONS_READ_FORBIDDEN")
        self.assertEqual(http_status, 403)
        self.assertEqual(
            runs["Security Governance"]["source"],
            "trusted_workflow_run_event",
        )
        self.assertEqual(
            governance.evidence_state(runs, state),
            "DEGRADED_PROVIDER_ENRICHMENT",
        )

        comment = governance.build_comment(
            {
                "state": "open",
                "draft": False,
                "head": {"sha": "abc123", "ref": "feature/example"},
                "base": {"sha": "def456", "ref": "main"},
            },
            runs,
            provider_enrichment_state=state,
            degraded_reason=reason,
            provider_http_status=http_status,
        )
        self.assertIn("Evidence disposition: `HOLD_EVIDENCE`", comment)
        self.assertIn("CHLOM/D3 disposition created by this readback: `NONE`", comment)
        self.assertNotIn("Institutional disposition: `PASS`", comment)

    def test_workflow_bounds_sweep_and_handles_deferred_exit_without_bad_heal_path(self):
        workflow = (
            ROOT / ".github/workflows/penta-pr-lifecycle-reusable.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("PENTA_TAGGER_SWEEP_MAX_ITEMS: '24'", workflow)
        self.assertIn("PENTA_TAGGER_REQUEST_BUDGET: '180'", workflow)
        self.assertGreaterEqual(workflow.count('if [[ "$status" -eq 75 ]]'), 2)
        self.assertGreaterEqual(
            workflow.count('payload.get("status") != "DEFERRED"'),
            2,
        )
        self.assertIn(
            "steps.tagger-preflight.outputs.deferred != 'true'",
            workflow,
        )
        self.assertIn(
            '--gate-report "$RUNNER_TEMP/pentagate-pr-lifecycle.json"',
            workflow,
        )
        self.assertNotIn(
            '--gate-report "$RUNNER_TEMP/pentaheal-pr-lifecycle.json"',
            workflow,
        )
        self.assertNotIn("--max-items 500", workflow)

    def test_governance_workflow_publishes_receipt_even_when_enrichment_is_degraded(self):
        workflow = (
            ROOT / ".github/workflows/governance-observability.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("if: always()", workflow)
        self.assertIn("github-observability.json", workflow)
        self.assertIn("actions: read", workflow)


if __name__ == "__main__":
    unittest.main()
