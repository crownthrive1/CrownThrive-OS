from __future__ import annotations

import unittest

from scripts import penta_pr_autopilot as autopilot


class PentaPRAutopilotReleaseTopologyTests(unittest.TestCase):
    def test_d0_and_d1_can_use_github_native_merge_path(self) -> None:
        for label in ("penta:risk:d0", "penta:risk:d1"):
            with self.subTest(label=label):
                allowed, reason = autopilot.autonomous_merge_allowed({label})
                self.assertTrue(allowed)
                self.assertIn("github_native_merge_eligible", reason)

    def test_d2_requires_independent_release_topology(self) -> None:
        allowed, reason = autopilot.autonomous_merge_allowed({"penta:risk:d2"})
        self.assertFalse(allowed)
        self.assertEqual(reason, "d2_independent_release_topology_required")

    def test_d3_is_human_reserved(self) -> None:
        allowed, reason = autopilot.autonomous_merge_allowed({"penta:risk:d3"})
        self.assertFalse(allowed)
        self.assertEqual(reason, "d3_human_reserved")

    def test_missing_or_ambiguous_risk_fails_closed(self) -> None:
        for labels in (set(), {"penta:risk:d1", "penta:risk:d2"}):
            with self.subTest(labels=labels):
                allowed, reason = autopilot.autonomous_merge_allowed(labels)
                self.assertFalse(allowed)
                self.assertEqual(reason, "risk_unclassified_or_ambiguous")


if __name__ == "__main__":
    unittest.main()
