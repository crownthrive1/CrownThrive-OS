import unittest

from scripts import penta_pm_pr_converge as mod


class FakeGH:
    repo = "crownthrive1/CrownThrive-OS"

    def __init__(self, *, pr_body: str, labels: list[str]) -> None:
        self._entity_cache = {}
        self.pr = {"number": 77, "title": "test governed PR", "body": pr_body}
        self.pr_issue = {
            "number": 77,
            "labels": [{"name": name} for name in labels],
            "body": pr_body,
            "pull_request": {"url": "https://example.invalid/pr/77"},
        }
        self.issues = {
            10: {"id": 1010, "number": 10, "title": "umbrella", "body": ""},
            20: {"id": 1020, "number": 20, "title": "remediation", "body": ""},
            30: {
                "id": 1030,
                "number": 30,
                "title": "older PR",
                "body": "",
                "pull_request": {"url": "https://example.invalid/pr/30"},
            },
        }

    def get(self, path: str):
        if path.endswith("/pulls/77"):
            return dict(self.pr)
        if path.endswith("/issues/77"):
            return dict(self.pr_issue)
        for number, issue in self.issues.items():
            if path.endswith(f"/issues/{number}"):
                return dict(issue)
        raise AssertionError(path)


class PentaPMPRConvergeTests(unittest.TestCase):
    def test_reference_parsing_is_unique_and_case_insensitive(self):
        body = "Refs #10\nreferences: #10\nCLOSES #20\nFixes #21"
        self.assertEqual(mod.issue_numbers(mod.TRACKING_RE, body), [10])
        self.assertEqual(mod.issue_numbers(mod.TERMINAL_RE, body), [20, 21])

    def test_tracking_reference_can_be_promoted_to_terminal_link(self):
        self.assertEqual(
            mod.replace_tracking_with_terminal("Summary\n\nRefs #20\n", 20),
            "Summary\n\nCloses #20\n",
        )

    def test_governed_requires_penta_label(self):
        self.assertTrue(mod.governed({"penta:pm"}))
        self.assertTrue(mod.governed({"penta-development"}))
        self.assertFalse(mod.governed({"bug", "documentation"}))

    def test_issue_entity_rejects_pull_requests(self):
        self.assertTrue(mod.is_issue_entity({"number": 10}))
        self.assertFalse(mod.is_issue_entity({"number": 30, "pull_request": {}}))

    def test_reference_selection_prefers_issue_over_pr(self):
        pr = {"number": 30, "pull_request": {}}
        issue = {"number": 20}
        self.assertEqual(mod.select_issue_reference([pr, issue]), issue)

    def test_pentaself_tracking_link_is_terminal_candidate(self):
        gh = FakeGH(
            pr_body="<!-- penta-self-remediation:abc -->\n\nRefs #20",
            labels=["penta:remediation"],
        )
        result = mod.converge_pr(gh, 77, apply=False)
        self.assertTrue(result["governed"])
        self.assertEqual(result["relationship_kind"], "pentaself-root")
        self.assertEqual(result["development_action"], "promote-to-closes:20")
        self.assertEqual(result["reference_source_kind"], "issue")

    def test_partial_tracking_link_gets_child_issue_contract(self):
        gh = FakeGH(pr_body="Refs #10", labels=["penta:pm"])
        result = mod.converge_pr(gh, 77, apply=False)
        self.assertEqual(result["development_action"], "create-or-reuse-child-under:10")

    def test_pr_then_issue_reference_uses_issue_as_parent(self):
        gh = FakeGH(pr_body="Refs #30\nRefs #10", labels=["penta:pm"])
        result = mod.converge_pr(gh, 77, apply=False)
        self.assertEqual(result["reference_source"], 10)
        self.assertEqual(result["reference_source_kind"], "issue")
        self.assertEqual(result["development_action"], "create-or-reuse-child-under:10")

    def test_only_pr_reference_uses_cross_reference_child_contract(self):
        gh = FakeGH(pr_body="Refs #30", labels=["penta:pm"])
        result = mod.converge_pr(gh, 77, apply=False)
        self.assertEqual(result["reference_source_kind"], "pull_request")
        self.assertEqual(result["development_action"], "create-or-reuse-child-related-to-pr:30")

    def test_existing_terminal_link_is_preserved(self):
        gh = FakeGH(pr_body="Closes #10", labels=["penta:pm"])
        result = mod.converge_pr(gh, 77, apply=False)
        self.assertEqual(result["development_action"], "terminal-link-present")

    def test_explicit_relationship_markers_parse(self):
        body = "Parent: #10\nBlocked by: #20\nBlocks #30"
        self.assertEqual(mod.issue_numbers(mod.PARENT_RE, body), [10])
        self.assertEqual(mod.issue_numbers(mod.BLOCKED_BY_RE, body), [20])
        self.assertEqual(mod.issue_numbers(mod.BLOCKS_RE, body), [30])


if __name__ == "__main__":
    unittest.main()
