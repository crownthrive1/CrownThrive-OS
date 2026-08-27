import unittest

from scripts.penta_immune_hunt import candidates_from_snapshot, report


class PentaImmuneHuntTests(unittest.TestCase):
    def test_failed_workflow_becomes_repo_local_candidate(self):
        snapshot = {
            "repo": "crownthrive1/CrownThrive-OS",
            "failed_workflow_runs": [
                {
                    "id": 12,
                    "name": "Governed Merge Gate",
                    "head_branch": "factory/example",
                    "head_sha": "a" * 40,
                    "html_url": "https://github.com/example/run/12",
                }
            ],
            "open_issues": [],
        }
        result = report(snapshot)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["selected"]["source_ref"], "workflow-run:12")
        self.assertTrue(result["selected"]["rollback"])
        self.assertTrue(result["selected"]["fallback"])
        self.assertFalse(result["mutation_performed"])

    def test_unlabeled_issue_is_not_autonomously_selected(self):
        snapshot = {
            "repo": "crownthrive1/CrownThrive-OS",
            "failed_workflow_runs": [],
            "open_issues": [{"number": 9, "title": "random", "labels": []}],
        }
        self.assertEqual(candidates_from_snapshot(snapshot), [])

    def test_explicit_ready_issue_can_enter_queue(self):
        snapshot = {
            "repo": "crownthrive1/CrownThrive-OS",
            "failed_workflow_runs": [],
            "open_issues": [
                {
                    "number": 9,
                    "title": "bounded repair",
                    "labels": [{"name": "penta-immune-ready"}],
                    "html_url": "https://github.com/example/issues/9",
                }
            ],
        }
        result = report(snapshot)
        self.assertEqual(result["selected"]["source_ref"], "issue:9")
        self.assertEqual(result["selected"]["authority_level"], "D2")


if __name__ == "__main__":
    unittest.main()
