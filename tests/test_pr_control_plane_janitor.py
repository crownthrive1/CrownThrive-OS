from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pr_control_plane_janitor import (  # noqa: E402
    JanitorError,
    classify_branch,
    create_archive_anchor,
    load_policy,
    paginate,
    pagination_request_paths,
    run,
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

    def test_old_merged_generated_remediation_is_directly_eligible(self) -> None:
        row = self.classify("pentaself/remediation/deadbeef")
        self.assertTrue(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "safe_generated_ref_already_preserved_on_main")

    def test_old_unique_generated_tip_requires_archive(self) -> None:
        row = self.classify(
            "pentarelease/auto-3.99.0.0-123",
            merged_into_main=False,
        )
        self.assertFalse(row["eligible"])
        self.assertTrue(row["archive_eligible"])
        self.assertEqual(row["reason"], "safe_archive_required_for_unique_generated_tip")

    def test_open_pr_head_or_base_is_never_deleted_or_archived(self) -> None:
        name = "pentaself/remediation/deadbeef"
        row = self.classify(name, active_pr_refs={name}, merged_into_main=False)
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "open_pr_head_or_base")

    def test_protected_branch_is_never_deleted(self) -> None:
        row = self.classify("noop", protected=True)
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "protected_branch")

    def test_archive_namespace_is_preserved(self) -> None:
        row = self.classify("archive/pentaself/remediation/deadbeef")
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "preserve_pattern")

    def test_unmanaged_human_branch_is_not_swept(self) -> None:
        row = self.classify("fix/important-human-work", merged_into_main=False)
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "outside_managed_generated_namespaces")

    def test_retention_window_is_enforced_before_archive(self) -> None:
        row = self.classify(
            "pentaself/remediation/new",
            age_hours=2,
            merged_into_main=False,
        )
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "retention_window_active")

    def test_old_admin_mcp_unique_tip_requires_archive_after_seven_days(self) -> None:
        row = self.classify(
            "admin-mcp/old-editor-projection-deadbeef",
            age_hours=200,
            merged_into_main=False,
        )
        self.assertFalse(row["eligible"])
        self.assertTrue(row["archive_eligible"])
        self.assertEqual(row["min_age_hours"], 168.0)
        self.assertEqual(row["reason"], "safe_archive_required_for_unique_generated_tip")

    def test_recent_admin_mcp_branch_is_retained(self) -> None:
        row = self.classify(
            "admin-mcp/recent-editor-projection-deadbeef",
            age_hours=72,
            merged_into_main=False,
        )
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "retention_window_active")

    def test_old_mintlify_branch_uses_same_seven_day_boundary(self) -> None:
        row = self.classify(
            "mintlify/weekly-link-repair",
            age_hours=200,
            merged_into_main=False,
        )
        self.assertFalse(row["eligible"])
        self.assertTrue(row["archive_eligible"])
        self.assertEqual(row["min_age_hours"], 168.0)

    def test_active_provider_branch_is_preserved_even_when_old(self) -> None:
        name = "admin-mcp/active-editor-projection"
        row = self.classify(
            name,
            age_hours=500,
            merged_into_main=False,
            active_pr_refs={name},
        )
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "open_pr_head_or_base")

    def test_noop_can_be_retired_without_age_delay_once_merged(self) -> None:
        row = self.classify("noop-should-not-create", age_hours=0)
        self.assertTrue(row["eligible"])

    def test_current_execution_branch_is_preserved(self) -> None:
        name = "pentaself/remediation/current"
        row = self.classify(name, execution_branch=name, merged_into_main=False)
        self.assertFalse(row["eligible"])
        self.assertFalse(row["archive_eligible"])
        self.assertEqual(row["reason"], "current_execution_branch")

    def test_policy_declares_archive_or_main_reachability_requirement(self) -> None:
        invariants = self.policy["invariants"]
        self.assertTrue(invariants["delete_only_if_tip_is_ancestor_of_main_or_verified_archive_anchor"])
        self.assertTrue(invariants["archive_anchor_uses_protected_main_tree_only"])
        self.assertTrue(invariants["archive_exact_ref_readback_required_before_unique_tip_delete"])
        self.assertTrue(invariants["delete_only_if_not_open_pr_head_or_base"])
        self.assertTrue(invariants["preserve_commit_and_pr_history"])
        self.assertTrue(invariants["closed_unmerged_unique_work_requires_archive_before_ref_retirement"])

    def test_pagination_uses_repository_relative_numeric_pages(self) -> None:
        calls: list[str] = []

        def fake_api_request(*, repo_full_name, token, path, method="GET", payload=None):
            self.assertEqual(repo_full_name, "crownthrive1/CrownThrive-OS")
            self.assertEqual(token, "token")
            self.assertEqual(method, "GET")
            self.assertIsNone(payload)
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

    def test_archive_anchor_uses_main_tree_and_exact_tip_parents(self) -> None:
        main_sha = "1" * 40
        main_tree = "2" * 40
        tip_a = "a" * 40
        tip_b = "b" * 40
        anchor_sha = "c" * 40
        calls: list[tuple[str, str, object]] = []

        def fake_git(repo, *args, check=True):
            if args == ("rev-parse", "refs/remotes/origin/main^{commit}"):
                return main_sha
            if args == ("rev-parse", "refs/remotes/origin/main^{tree}"):
                return main_tree
            self.fail(f"unexpected git call: {args}")

        def fake_api_request(*, repo_full_name, token, path, method="GET", payload=None):
            calls.append((path, method, payload))
            if path == "/git/commits" and method == "POST":
                self.assertEqual(payload["tree"], main_tree)
                self.assertEqual(payload["parents"], [main_sha, tip_a, tip_b])
                return ({
                    "sha": anchor_sha,
                    "tree": {"sha": main_tree},
                    "parents": [{"sha": main_sha}, {"sha": tip_a}, {"sha": tip_b}],
                }, {}, 201)
            if path == "/git/refs" and method == "POST":
                self.assertTrue(str(payload["ref"]).startswith("refs/heads/archive/generated-branches/"))
                self.assertEqual(payload["sha"], anchor_sha)
                return ({"ref": payload["ref"], "object": {"sha": anchor_sha}}, {}, 201)
            if path.startswith("/git/ref/heads/archive/generated-branches/"):
                return ({"object": {"sha": anchor_sha}}, {}, 200)
            self.fail(f"unexpected API call: {method} {path}")

        with (
            patch("pr_control_plane_janitor.git", side_effect=fake_git),
            patch("pr_control_plane_janitor.api_request", side_effect=fake_api_request),
            patch.dict("os.environ", {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2"}),
        ):
            result = create_archive_anchor(
                repo=ROOT,
                repo_full_name="crownthrive1/CrownThrive-OS",
                token="token",
                main_ref="refs/remotes/origin/main",
                candidates=[{"tip_sha": tip_a}, {"tip_sha": tip_b}],
                now=dt.datetime(2026, 8, 31, tzinfo=dt.timezone.utc),
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["archive_anchor_sha"], anchor_sha)
        self.assertEqual(result["archive_tree_sha"], main_tree)
        self.assertEqual(result["archived_tip_shas"], [tip_a, tip_b])
        self.assertTrue(result["exact_ref_readback"])
        self.assertFalse(result["source_tree_changed"])
        self.assertEqual(result["archive_branch"], "archive/generated-branches/20260831-123-2")
        self.assertEqual(len(calls), 3)

    def test_archive_anchor_holds_on_parent_readback_drift(self) -> None:
        main_sha = "1" * 40
        main_tree = "2" * 40
        tip = "a" * 40

        def fake_git(repo, *args, check=True):
            return main_sha if args[-1].endswith("^{commit}") else main_tree

        def fake_api_request(*, repo_full_name, token, path, method="GET", payload=None):
            if path == "/git/commits":
                return ({
                    "sha": "c" * 40,
                    "tree": {"sha": main_tree},
                    "parents": [{"sha": main_sha}],
                }, {}, 201)
            self.fail("archive ref must never be created after parent drift")

        with (
            patch("pr_control_plane_janitor.git", side_effect=fake_git),
            patch("pr_control_plane_janitor.api_request", side_effect=fake_api_request),
        ):
            with self.assertRaises(JanitorError):
                create_archive_anchor(
                    repo=ROOT,
                    repo_full_name="crownthrive1/CrownThrive-OS",
                    token="token",
                    main_ref="refs/remotes/origin/main",
                    candidates=[{"tip_sha": tip}],
                    now=dt.datetime(2026, 8, 31, tzinfo=dt.timezone.utc),
                )


class ArchiveParentRegressionTests(unittest.TestCase):
    """Exercise archive requests against real, isolated local Git objects.

    The API boundary is mocked throughout. No GitHub requests or ref deletions
    occur, including tests of the apply-mode safety gate.
    """

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="janitor-archive-test-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Archive test",
            "GIT_AUTHOR_EMAIL": "archive-test@example.invalid",
            "GIT_COMMITTER_NAME": "Archive test",
            "GIT_COMMITTER_EMAIL": "archive-test@example.invalid",
        }
        self.local_git("init", "-q")
        self.main_tree = self.local_git("mktree", input="")
        self.main_sha = self.local_git("commit-tree", self.main_tree, "-m", "main")
        self.local_git("update-ref", "refs/remotes/origin/main", self.main_sha)
        self.tip = self.new_tip("candidate")
        self.calls: list[tuple[str, str, object]] = []
        self.commit_requests: list[dict] = []
        self.parent_mutation = None
        self.tree_drift = False
        self.ref_drift = False

    def local_git(self, *args: str, input: str | None = None) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, input=input,
            text=True, capture_output=True, check=True,
        )
        return result.stdout.strip()

    def new_tip(self, message: str) -> str:
        return self.local_git(
            "commit-tree", self.main_tree, "-p", self.main_sha, "-m", message,
        )

    def fake_api(self, *, repo_full_name, token, path, method="GET", payload=None):
        self.calls.append((path, method, payload))
        if path == "/git/commits" and method == "POST":
            self.commit_requests.append(payload)
            args = ["commit-tree", payload["tree"], "-m", payload["message"]]
            for parent in payload["parents"]:
                args.extend(["-p", parent])
            sha = self.local_git(*args)
            # commit-tree removes duplicate parents, just as a Git-backed
            # provider may do. Read the actual object instead of echoing input.
            parents = self.local_git("show", "-s", "--format=%P", sha).split()
            if self.parent_mutation is not None:
                parents = self.parent_mutation(parents)
            tree = self.local_git("rev-parse", f"{sha}^{{tree}}")
            return ({
                "sha": sha,
                "tree": {"sha": "f" * 40 if self.tree_drift else tree},
                "parents": [{"sha": parent} for parent in parents],
            }, {}, 201)
        if path == "/git/refs" and method == "POST":
            self.local_git("update-ref", payload["ref"], payload["sha"])
            return ({"ref": payload["ref"], "object": {"sha": payload["sha"]}}, {}, 201)
        if path.startswith("/git/ref/heads/") and method == "GET":
            ref = "refs/heads/" + path.removeprefix("/git/ref/heads/")
            sha = self.local_git("rev-parse", ref)
            return ({"object": {"sha": self.main_sha if self.ref_drift else sha}}, {}, 200)
        self.fail(f"unexpected API call: {method} {path}")

    def anchor(self, tips: list[str]):
        with patch("pr_control_plane_janitor.api_request", side_effect=self.fake_api):
            return create_archive_anchor(
                repo=self.repo,
                repo_full_name="owner/repository",
                token="unused-test-token",
                main_ref="refs/remotes/origin/main",
                candidates=[{"tip_sha": tip} for tip in tips],
                now=dt.datetime(2026, 11, 6, tzinfo=dt.timezone.utc),
            )

    def test_shared_tip_is_requested_once_but_preserves_both_candidate_records(self):
        result = self.anchor([self.tip, self.tip])
        self.assertEqual(self.commit_requests[0]["parents"], [self.main_sha, self.tip])
        self.assertEqual(result["archived_count"], 2)
        self.assertEqual(result["archived_tip_shas"], [self.tip, self.tip])
        self.assertTrue(result["exact_ref_readback"])
        self.assertFalse(result["source_tree_changed"])

    def test_tip_equal_to_chain_parent_does_not_duplicate_first_parent(self):
        result = self.anchor([self.main_sha, self.tip])
        self.assertEqual(self.commit_requests[0]["parents"], [self.main_sha, self.tip])
        self.assertTrue(result["exact_ref_readback"])

    def test_duplicate_tips_across_chunks_keep_exact_ordered_chain(self):
        tips = [self.new_tip(f"candidate-{index}") for index in range(24)]
        result = self.anchor([*tips, tips[0], tips[1], tips[1]])
        anchors = result["archive_commits"]
        self.assertEqual(len(anchors), 2)
        self.assertEqual(self.commit_requests[0]["parents"], [self.main_sha, *tips])
        self.assertEqual(self.commit_requests[1]["parents"], [anchors[0], tips[0], tips[1]])
        self.assertEqual(result["archived_count"], 27)
        self.assertEqual(len(result["archived_tip_shas"]), 27)
        for tip in tips:
            self.local_git("merge-base", "--is-ancestor", tip, anchors[-1])
        for anchor in anchors:
            self.assertEqual(self.local_git("rev-parse", f"{anchor}^{{tree}}"), self.main_tree)

    def test_missing_unique_parent_still_holds(self):
        self.parent_mutation = lambda parents: parents[:-1]
        with self.assertRaisesRegex(JanitorError, "exact requested parents"):
            self.anchor([self.tip, self.tip])
        self.assertEqual(len(self.calls), 1)

    def test_reordered_unique_parents_still_hold(self):
        self.parent_mutation = lambda parents: list(reversed(parents))
        with self.assertRaisesRegex(JanitorError, "exact requested parents"):
            self.anchor([self.tip])
        self.assertEqual(len(self.calls), 1)

    def test_unexpected_extra_parent_still_holds(self):
        extra = self.new_tip("unexpected")
        self.parent_mutation = lambda parents: [*parents, extra]
        with self.assertRaisesRegex(JanitorError, "exact requested parents"):
            self.anchor([self.tip])
        self.assertEqual(len(self.calls), 1)

    def test_duplicate_parent_in_response_still_holds(self):
        self.parent_mutation = lambda parents: [*parents, parents[-1]]
        with self.assertRaisesRegex(JanitorError, "exact requested parents"):
            self.anchor([self.tip])
        self.assertEqual(len(self.calls), 1)

    def test_tree_drift_still_holds_before_ref_creation(self):
        self.tree_drift = True
        with self.assertRaisesRegex(JanitorError, "tree drifted"):
            self.anchor([self.tip])
        self.assertEqual(len(self.calls), 1)

    def test_ref_drift_still_holds(self):
        self.ref_drift = True
        with self.assertRaisesRegex(JanitorError, "ref exact readback mismatch"):
            self.anchor([self.tip])
        self.assertEqual(len(self.calls), 3)

    def test_archive_hold_prevents_all_deletions_including_direct_main_candidates(self):
        self.parent_mutation = lambda parents: parents[:-1]
        branches = [
            {"name": "noop-archive", "protected": False, "commit": {"sha": self.tip}},
            {"name": "noop-direct", "protected": False, "commit": {"sha": self.main_sha}},
        ]
        for branch in branches:
            self.local_git("update-ref", f"refs/remotes/origin/{branch['name']}", branch["commit"]["sha"])
        with (
            patch("pr_control_plane_janitor.api_request", side_effect=self.fake_api),
            patch("pr_control_plane_janitor.open_pr_refs", return_value=set()),
            patch("pr_control_plane_janitor.branch_rows", return_value=branches),
            patch("pr_control_plane_janitor.delete_branch") as delete,
        ):
            with self.assertRaisesRegex(JanitorError, "exact requested parents"):
                run(
                    repo=self.repo, repo_full_name="owner/repository", token="unused-test-token",
                    policy=load_policy(ROOT / "config/pr_control_plane_janitor.json"),
                    mode="apply", max_delete=75, execution_branch="main",
                )
        delete.assert_not_called()
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
