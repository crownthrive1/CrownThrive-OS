from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pr_control_plane_janitor import (  # noqa: E402
    JanitorError,
    classify_branch,
    load_policy,
    paginate,
    pagination_request_paths,
)


class PRControlPlaneJanitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(ROOT / "config/pr_control_plane_janitor.json")

    def classify(self, name: str, **overrides):
        kwargs = {
            "name": name,
            "protected": False,
            "active_pr_refs": set(),
            "merged_into_main": True,
            "age_hours": 48.0,
            "policy": self.policy,
            "execution_branch": None,
        }
        kwargs.update(overrides)
        return classify_branch(**kwargs)

    def test_old_merged_generated_remediation_is_eligible(self) -> None:
        row = self.classify("pentaself/remediation/deadbeef")
        self.assertTrue(row["eligible"])
        self.assertEqual(row["reason"], "safe_generated_ref_already_preserved_on_main")

    def test_open_pr_head_or_base_is_never_deleted(self) -> None:
        name = "pentaself/remediation/deadbeef"
        row = self.classify(name, active_pr_refs={name})
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "open_pr_head_or_base")

    def test_unmerged_unique_tip_is_never_deleted(self) -> None:
        row = self.classify(
            "pentarelease/auto-3.99.0.0-123",
            merged_into_main=False,
        )
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "unique_tip_not_merged_into_main")

    def test_protected_branch_is_never_deleted(self) -> None:
        row = self.classify("noop", protected=True)
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "protected_branch")

    def test_archive_namespace_is_preserved(self) -> None:
        row = self.classify("archive/pentaself/remediation/deadbeef")
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "preserve_pattern")

    def test_unmanaged_branch_is_not_swept(self) -> None:
        row = self.classify("admin-mcp/important-human-work")
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "outside_managed_generated_namespaces")

    def test_retention_window_is_enforced(self) -> None:
        row = self.classify("pentaself/remediation/new", age_hours=2)
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "retention_window_active")

    def test_noop_can_be_retired_without_age_delay_once_merged(self) -> None:
        row = self.classify("noop-should-not-create", age_hours=0)
        self.assertTrue(row["eligible"])

    def test_current_execution_branch_is_preserved(self) -> None:
        name = "pentaself/remediation/current"
        row = self.classify(name, execution_branch=name)
        self.assertFalse(row["eligible"])
        self.assertEqual(row["reason"], "current_execution_branch")

    def test_policy_declares_no_unique_work_deletion(self) -> None:
        invariants = self.policy["invariants"]
        self.assertTrue(invariants["delete_only_if_tip_is_ancestor_of_main"])
        self.assertTrue(invariants["delete_only_if_not_open_pr_head_or_base"])
        self.assertTrue(invariants["closed_unmerged_unique_work_is_not_deleted"])
        self.assertTrue(invariants["preserve_commit_and_pr_history"])

    def test_pagination_uses_repository_relative_numeric_pages(self) -> None:
        calls: list[str] = []

        def fake_api_request(*, repo_full_name, token, path, method="GET"):
            self.assertEqual(repo_full_name, "crownthrive1/CrownThrive-OS")
            self.assertEqual(token, "token")
            self.assertEqual(method, "GET")
            calls.append(path)
            if path.endswith("page=1"):
                return (
                    [{"name": "a"}, {"name": "b"}],
                    {
                        "Link": (
                            '<https://api.github.com/repositories/1336348391/branches'
                            '?per_page=2&page=2>; rel="next"'
                        )
                    },
                    200,
                )
            return ([{"name": "c"}], {}, 200)

        with patch("pr_control_plane_janitor.api_request", side_effect=fake_api_request):
            rows = paginate(
                "crownthrive1/CrownThrive-OS",
                "token",
                "/branches?per_page=2",
            )

        self.assertEqual([row["name"] for row in rows], ["a", "b", "c"])
        self.assertEqual(
            calls,
            ["/branches?per_page=2&page=1", "/branches?per_page=2&page=2"],
        )

    def test_pagination_rejects_absolute_caller_path(self) -> None:
        with self.assertRaises(JanitorError):
            pagination_request_paths(
                "https://api.github.com/repositories/1336348391/branches?per_page=100"
            )

    def test_pagination_bounds_per_page(self) -> None:
        with self.assertRaises(JanitorError):
            pagination_request_paths("/branches?per_page=101")

    def test_pagination_rejects_duplicate_page_parameter(self) -> None:
        with self.assertRaises(JanitorError):
            pagination_request_paths("/branches?page=1&page=2")


if __name__ == "__main__":
    unittest.main()
