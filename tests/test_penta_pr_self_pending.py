from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_pr_lifecycle import checks, classify  # noqa: E402


class SelfCheckGH:
    def __init__(self, *, unrelated_pending: bool = False):
        self.repo = "crownthrive1/CrownThrive-Support"
        self.unrelated_pending = unrelated_pending
        self.pr = {
            "number": 12,
            "title": "Ready candidate",
            "body": "",
            "state": "open",
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "head": {"sha": "abc"},
        }
        self.issue = {"number": 12, "labels": [{"name": "penta:tagged"}]}

    def get(self, path):
        if path.endswith("/pulls/12"):
            return self.pr
        if path.endswith("/issues/12"):
            return self.issue
        if "/commits/abc/check-runs" in path:
            runs = [
                {
                    "name": "run / lifecycle",
                    "status": "in_progress",
                    "conclusion": None,
                },
                {
                    "name": "CrownThrive governed merge gate",
                    "status": "completed",
                    "conclusion": "success",
                },
                {
                    "name": "Security Governance",
                    "status": "completed" if not self.unrelated_pending else "in_progress",
                    "conclusion": "success" if not self.unrelated_pending else None,
                },
            ]
            return {"check_runs": runs}
        if "/commits/abc/status" in path:
            return {"state": "success"}
        raise AssertionError(f"unexpected GET {path}")


class PentaPRSelfPendingTests(unittest.TestCase):
    def test_current_lifecycle_job_is_ignored_for_pending_state(self):
        state = checks(SelfCheckGH(), "abc")
        self.assertFalse(state["pending"])
        self.assertFalse(state["failed"])
        self.assertTrue(state["governed_ok"])
        self.assertEqual(state["ignored_self_count"], 1)
        self.assertEqual(state["observed_count"], 3)
        self.assertEqual(state["count"], 2)

    def test_self_running_job_does_not_prevent_merge_classification(self):
        disposition, reason = classify(SelfCheckGH(), SelfCheckGH().pr)
        self.assertEqual(disposition, "MERGE")
        self.assertEqual(reason, "mergeable_governed_green")

    def test_unrelated_pending_job_still_blocks(self):
        state = checks(SelfCheckGH(unrelated_pending=True), "abc")
        self.assertTrue(state["pending"])
        disposition, reason = classify(
            SelfCheckGH(unrelated_pending=True),
            SelfCheckGH(unrelated_pending=True).pr,
        )
        self.assertEqual(disposition, "NURTURE")
        self.assertEqual(reason, "checks_pending")


if __name__ == "__main__":
    unittest.main()
