from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import penta_pr_autopilot as autopilot  # noqa: E402
import resolve_pr_gate_applicability as applicability  # noqa: E402


class FakeGH:
    repo = "crownthrive1/CrownThrive-OS"

    def __init__(self, check_runs: list[dict[str, object]]) -> None:
        self.check_runs = check_runs

    def get(self, path: str):
        if "/check-runs" in path:
            return {"check_runs": self.check_runs}
        raise AssertionError(path)


class GateApplicabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads((ROOT / "config/penta_pr_gate_applicability.json").read_text(encoding="utf-8"))

    def test_docs_change_does_not_require_unrelated_runtime_gates(self) -> None:
        contract = applicability.resolve_paths(["README.md"], self.policy)
        required = set(contract["required_merge_groups"])
        self.assertIn("documentation", required)
        self.assertNotIn("security", required)
        self.assertNotIn("phase_control", required)
        self.assertEqual(contract["change_class"], "documentation_or_projection")

    def test_sql_migration_requires_security(self) -> None:
        contract = applicability.resolve_paths(["supabase/migrations/20260831_example.sql"], self.policy)
        self.assertIn("security", contract["required_merge_groups"])
        self.assertEqual(contract["risk_class"], "D2")

    def test_gate_workflow_change_receives_governance_and_security(self) -> None:
        contract = applicability.resolve_paths([".github/workflows/governed-merge-gate.yml"], self.policy)
        required = set(contract["required_merge_groups"])
        self.assertTrue({"phase_control", "workflow_policy", "security"}.issubset(required))

    def test_unrelated_binary_asset_uses_universal_controls_only(self) -> None:
        contract = applicability.resolve_paths(["assets/logo.png"], self.policy)
        self.assertEqual(contract["required_merge_groups"], [])
        self.assertTrue(contract["universal_merge_controls"])

    def test_required_gate_pass_is_not_invalidated_by_advisory_failure(self) -> None:
        gh = FakeGH(
            [
                {
                    "id": 10,
                    "name": "CrownThrive governed merge gate",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"slug": "github-actions"},
                },
                {
                    "id": 11,
                    "name": "Documentation Governance",
                    "status": "completed",
                    "conclusion": "failure",
                    "app": {"slug": "github-actions"},
                },
            ]
        )
        state, _ = autopilot.required_gate_state(gh, "a" * 40)
        advisory = autopilot.advisory_check_summary(gh, "a" * 40)
        self.assertEqual(state, "PASS")
        self.assertEqual(advisory["failed"], 1)

    def test_required_gate_failure_remains_blocking(self) -> None:
        gh = FakeGH(
            [
                {
                    "id": 20,
                    "name": "CrownThrive governed merge gate",
                    "status": "completed",
                    "conclusion": "failure",
                    "app": {"slug": "github-actions"},
                },
                {
                    "id": 21,
                    "name": "Security Governance",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"slug": "github-actions"},
                },
            ]
        )
        state, _ = autopilot.required_gate_state(gh, "b" * 40)
        self.assertEqual(state, "FAIL")

    def test_missing_required_gate_is_fail_closed(self) -> None:
        gh = FakeGH(
            [
                {
                    "id": 30,
                    "name": "Documentation Governance",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"slug": "github-actions"},
                }
            ]
        )
        state, _ = autopilot.required_gate_state(gh, "c" * 40)
        self.assertEqual(state, "MISSING")


if __name__ == "__main__":
    unittest.main()
