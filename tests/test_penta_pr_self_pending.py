from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_pr_lifecycle import checks, classify  # noqa: E402


APP = {"slug": "github-actions"}


class SelfCheckGH:
    def __init__(self, *, unrelated_pending: bool = False, empty_legacy: bool = False):
        self.repo = "crownthrive1/CrownThrive-OS"
        self.unrelated_pending = unrelated_pending
        self.empty_legacy = empty_legacy
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
                    "id": 103,
                    "app": APP,
                    "name": "run / lifecycle",
                    "status": "in_progress",
                    "conclusion": None,
                },
                {
                    "id": 102,
                    "app": APP,
                    "name": "CrownThrive governed merge gate",
                    "status": "completed",
                    "conclusion": "success",
                },
                {
                    "id": 101,
                    "app": APP,
                    "name": "Security Governance",
                    "status": "completed" if not self.unrelated_pending else "in_progress",
                    "conclusion": "success" if not self.unrelated_pending else None,
                },
            ]
            return {"check_runs": runs}
        if "/commits/abc/status" in path:
            if self.empty_legacy:
                return {"state": "pending", "total_count": 0, "statuses": []}
            return {"state": "success", "total_count": 1, "statuses": [{"context": "legacy", "state": "success"}]}
        raise AssertionError(f"unexpected GET {path}")


class SupersededCheckGH(SelfCheckGH):
    def __init__(self, *, latest_conclusion="success", latest_status="completed", different_app_failure=False):
        super().__init__(empty_legacy=True)
        self.latest_conclusion = latest_conclusion
        self.latest_status = latest_status
        self.different_app_failure = different_app_failure

    def get(self, path):
        if "/commits/abc/check-runs" in path:
            runs = [
                {
                    "id": 210,
                    "app": APP,
                    "name": "run / lifecycle",
                    "status": "in_progress",
                    "conclusion": None,
                },
                {
                    "id": 205,
                    "app": APP,
                    "name": "CrownThrive governed merge gate",
                    "status": "completed",
                    "conclusion": "success",
                },
                {
                    "id": 100,
                    "app": APP,
                    "name": "Trusted base — live prevention and reaction",
                    "status": "completed",
                    "conclusion": "failure",
                },
                {
                    "id": 200,
                    "app": APP,
                    "name": "Trusted base — live prevention and reaction",
                    "status": self.latest_status,
                    "conclusion": self.latest_conclusion,
                },
            ]
            if self.different_app_failure:
                runs.append(
                    {
                        "id": 220,
                        "app": {"slug": "independent-provider"},
                        "name": "Trusted base — live prevention and reaction",
                        "status": "completed",
                        "conclusion": "failure",
                    }
                )
            return {"check_runs": runs}
        return super().get(path)


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

    def test_empty_legacy_status_pending_is_not_a_real_pending_context(self):
        state = checks(SelfCheckGH(empty_legacy=True), "abc")
        self.assertEqual(state["legacy_status_count"], 0)
        self.assertFalse(state["pending"])
        self.assertFalse(state["failed"])
        disposition, reason = classify(SelfCheckGH(empty_legacy=True), SelfCheckGH(empty_legacy=True).pr)
        self.assertEqual((disposition, reason), ("MERGE", "mergeable_governed_green"))

    def test_newer_success_supersedes_older_failure_for_same_context(self):
        gh = SupersededCheckGH()
        state = checks(gh, "abc")
        self.assertEqual(state["observed_count"], 4)
        self.assertEqual(state["current_context_count"], 3)
        self.assertEqual(state["superseded_check_count"], 1)
        self.assertFalse(state["failed"])
        self.assertFalse(state["pending"])
        disposition, reason = classify(gh, gh.pr)
        self.assertEqual((disposition, reason), ("MERGE", "mergeable_governed_green"))

    def test_newer_failure_still_blocks_even_if_older_run_succeeded(self):
        gh = SupersededCheckGH(latest_conclusion="failure")
        state = checks(gh, "abc")
        self.assertTrue(state["failed"])
        disposition, reason = classify(gh, gh.pr)
        self.assertEqual((disposition, reason), ("NURTURE", "checks_failed"))

    def test_newer_pending_still_blocks_even_if_older_run_failed(self):
        gh = SupersededCheckGH(latest_conclusion=None, latest_status="in_progress")
        state = checks(gh, "abc")
        self.assertTrue(state["pending"])
        self.assertFalse(state["failed"])
        disposition, reason = classify(gh, gh.pr)
        self.assertEqual((disposition, reason), ("NURTURE", "checks_pending"))

    def test_same_name_from_different_provider_app_remains_independent(self):
        gh = SupersededCheckGH(different_app_failure=True)
        state = checks(gh, "abc")
        self.assertTrue(state["failed"])
        self.assertEqual(state["superseded_check_count"], 1)


if __name__ == "__main__":
    unittest.main()
