from __future__ import annotations

import datetime as dt
import importlib.util
import json
import tempfile
import unittest
import sys
from unittest.mock import patch
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "penta_rg.py"
SPEC = importlib.util.spec_from_file_location("penta_rg", MODULE_PATH)
assert SPEC and SPEC.loader
penta_rg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = penta_rg
SPEC.loader.exec_module(penta_rg)


class RecoveryGitHubClient:
    """A provider fixture that records writes without contacting GitHub."""

    def __init__(self, runs, rejection=None):
        self.repo = "acme/repo"
        self.runs = runs
        self.rejection = rejection
        self.comments = []
        self.posts = []

    def paginate(self, path, pages=3):
        if "/pulls?state=open" in path:
            return [{"number": 42, "title": "Fix governed workflow", "head": {"sha": "a" * 40}}]
        if "/pulls/42/files" in path:
            return [{"filename": "README.md"}]
        if "/issues/42/comments" in path:
            return list(self.comments)
        raise AssertionError(path)

    def get(self, path):
        if "/actions/runs?head_sha=" in path:
            return {"workflow_runs": self.runs}
        raise AssertionError(path)

    def post(self, path, body):
        self.posts.append((path, body))
        if path.endswith("/rerun-failed-jobs"):
            if self.rejection:
                raise self.rejection
            return None
        if "/issues/42/comments" in path:
            self.comments.append({"body": body["body"]})
            return {}
        raise AssertionError(path)

    def patch(self, path, body):
        raise AssertionError((path, body))


class PentaRGTests(unittest.TestCase):
    def policy(self):
        return {
            "schema": penta_rg.POLICY_SCHEMA,
            "mode": "FULL_AUTONOMOUS_GOVERNED",
            "authority": {
                "d2": {"mode": "bounded_autonomous"},
                "d3": {
                    "founder_lease": {
                        "enabled": True,
                        "starts_at": "2026-08-27T00:00:00Z",
                        "expires_at": "2026-09-10T23:59:59Z",
                    }
                },
            },
            "archive": {
                "generic_title_prefixes": ["create "],
                "generic_workflow_paths": [".github/workflows/static.yml"],
            },
            "provider": {
                "request_budget": 100,
                "max_open_pulls_per_sweep": 10,
                "deferred_retry_seconds": 1800,
            },
            "required_paths": [],
            "required_topology_nodes": [],
            "required_topology_edges": [],
            "vercel": {"required_files": []},
        }

    def test_founder_lease_is_time_bounded(self):
        policy = self.policy()
        active = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
        expired = dt.datetime(2026, 9, 11, tzinfo=dt.timezone.utc)
        self.assertTrue(penta_rg.founder_lease_active(policy, active))
        self.assertFalse(penta_rg.founder_lease_active(policy, expired))
        self.assertTrue(penta_rg.authority_allowed(policy, "D2", active))
        self.assertFalse(penta_rg.authority_allowed(policy, "D3", expired))

    def test_full_sha_pins_pass_and_floating_refs_block(self):
        good = "steps:\n  - uses: actions/checkout@" + "a" * 40 + "\n"
        bad = "steps:\n  - uses: actions/checkout@v4\n"
        self.assertEqual([], penta_rg.scan_workflow_text("good.yml", good))
        findings = penta_rg.scan_workflow_text("bad.yml", bad)
        self.assertEqual("workflow_action_not_full_sha_pinned", findings[0].code)
        self.assertEqual("BLOCK", findings[0].severity)

    def test_pull_request_target_untrusted_checkout_is_blocked(self):
        text = """
on:
  pull_request_target:
permissions:
  contents: write
steps:
  - run: echo '${{ github.event.pull_request.head.sha }}'
"""
        codes = {f.code for f in penta_rg.scan_workflow_text("unsafe.yml", text)}
        self.assertIn("untrusted_pr_target_checkout_with_write_authority", codes)

    def test_generic_starter_classification_is_exact(self):
        policy = self.policy()
        self.assertTrue(penta_rg.starter_pr_match("Create static.yml", [".github/workflows/static.yml"], policy))
        self.assertFalse(penta_rg.starter_pr_match("Fix production static route", [".github/workflows/static.yml"], policy))
        self.assertFalse(penta_rg.starter_pr_match("Create static.yml", [".github/workflows/static.yml", "README.md"], policy))

    def test_duplicate_group_uses_changed_file_fingerprint(self):
        groups = penta_rg.duplicate_groups([
            {"number": 1, "files": ["a", "b"]},
            {"number": 2, "files": ["b", "a"]},
            {"number": 3, "files": ["c"]},
        ])
        self.assertEqual([[1, 2]], groups)

    def test_action_required_never_becomes_pass(self):
        state, route = penta_rg.classify_run_conclusion("action_required")
        self.assertEqual("HOLD", state)
        self.assertEqual("provider_approval_or_actor_policy", route)

    def test_request_budget_fails_closed(self):
        budget = penta_rg.RequestBudget(1)
        budget.consume()
        with self.assertRaises(penta_rg.ProviderDeferred):
            budget.consume()

    def test_provider_nonretriable_classifier_is_narrow(self):
        nonretriable = penta_rg.PentaRGError(
            'github_POST_/repos/acme/repo/actions/runs/123/rerun-failed-jobs_403:{"message":"This workflow run cannot be retried"}'
        )
        permission = penta_rg.PentaRGError(
            'github_POST_/repos/acme/repo/actions/runs/123/rerun-failed-jobs_403:{"message":"Resource not accessible by integration"}'
        )
        self.assertTrue(penta_rg.provider_rerun_not_retriable(nonretriable))
        self.assertFalse(penta_rg.provider_rerun_not_retriable(permission))
        self.assertFalse(penta_rg.provider_rerun_not_retriable(penta_rg.ProviderDeferred("github_quota_exhausted")))

    def test_remote_audit_preserves_hold_and_receipt_when_old_run_cannot_rerun(self):
        original_client = penta_rg.GitHubClient

        class FakeGitHubClient:
            comments = []

            def __init__(self, repo, token, budget):
                self.repo, self.token, self.budget = repo, token, budget

            def paginate(self, path, pages=3):
                if "/pulls?state=open" in path:
                    return [{
                        "number": 42,
                        "title": "Fix current governed workflow",
                        "draft": False,
                        "head": {"sha": "a" * 40},
                    }]
                if "/pulls/42/files" in path:
                    return [{"filename": "README.md"}]
                if "/issues/42/comments" in path:
                    return list(self.comments)
                raise AssertionError(path)

            def get(self, path):
                if "/actions/runs?head_sha=" in path:
                    return {
                        "workflow_runs": [{
                            "id": 123,
                            "name": "Historical Gate",
                            "status": "completed",
                            "conclusion": "failure",
                        }]
                    }
                raise AssertionError(path)

            def post(self, path, body):
                if path.endswith("/actions/runs/123/rerun-failed-jobs"):
                    raise penta_rg.PentaRGError(
                        'github_POST_/repos/acme/repo/actions/runs/123/rerun-failed-jobs_403:{"message":"This workflow run cannot be retried"}'
                    )
                if "/issues/42/comments" in path:
                    self.comments.append({"body": body["body"]})
                    return {}
                raise AssertionError(path)

            def patch(self, path, body):
                raise AssertionError((path, body))

        penta_rg.GitHubClient = FakeGitHubClient
        try:
            result = penta_rg.remote_audit("acme/repo", "token", self.policy(), apply=True)
        finally:
            penta_rg.GitHubClient = original_client

        self.assertEqual("HOLD", result["status"])
        self.assertFalse(result["pass_manufactured"])
        self.assertIsNone(result["deferred"])
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")
        skipped = [
            action for action in result["executed_actions"]
            if action.get("status") == "SKIPPED_PROVIDER_NOT_RETRIABLE"
        ]
        self.assertEqual(1, len(skipped))
        self.assertEqual(123, skipped[0]["run_id"])
        self.assertEqual("workflow_run_cannot_be_retried", skipped[0]["provider_reason"])

    def test_local_audit_detects_missing_required_path(self):
        policy = self.policy()
        policy["required_paths"] = ["missing.txt"]
        topology = {"schema": penta_rg.TOPOLOGY_SCHEMA, "nodes": [], "edges": []}
        with tempfile.TemporaryDirectory() as tmp:
            result = penta_rg.local_audit(Path(tmp), policy, topology)
        self.assertEqual("HOLD", result["status"])
        self.assertIn("required_path_missing", {f["code"] for f in result["findings"]})
        self.assertFalse(result["pass_manufactured"])

    def failed_run(self, created_at=None, run_id=123):
        return {
            "id": run_id,
            "name": f"Gate {run_id}",
            "status": "completed",
            "conclusion": "failure",
            "created_at": created_at,
        }

    def recover(self, client, apply=True):
        now = dt.datetime(2026, 11, 5, 19, tzinfo=dt.timezone.utc)
        with patch.object(penta_rg, "GitHubClient", return_value=client), patch.object(penta_rg, "utc_now", return_value=now):
            return penta_rg.remote_audit("acme/repo", "token", self.policy(), apply=apply)

    def test_rerun_window_uses_creation_and_exact_30_day_boundary(self):
        now = dt.datetime(2026, 11, 5, 19, tzinfo=dt.timezone.utc)
        for created_at, expired in [
            ("2026-10-06T19:00:01Z", False),
            ("2026-10-06T19:00:00Z", True),
            ("2026-10-06T20:00:00+01:00", True),
            ("2026-09-01T00:00:00Z", True),
            ("2026-11-06T00:00:00Z", False),
            (None, False),
            ("invalid", False),
        ]:
            with self.subTest(created_at=created_at):
                run = {"created_at": created_at, "updated_at": penta_rg.iso(now), "run_started_at": penta_rg.iso(now)}
                self.assertEqual(expired, penta_rg.workflow_rerun_expired(run, now))

    def test_expired_run_preserves_hold_without_provider_writes(self):
        client = RecoveryGitHubClient([self.failed_run("2026-10-01T00:00:00Z")])
        result = self.recover(client)
        self.assertEqual("HOLD", result["status"])
        self.assertEqual([], client.posts)
        self.assertEqual([], result["executed_actions"])
        planned = result["planned_actions"][0]
        self.assertEqual("remediate_expired_workflow_run", planned["action"])
        self.assertFalse(planned["apply_allowed"])
        self.assertEqual("workflow_run_rerun_window_expired", planned["metadata"]["provider_reason"])
        self.assertEqual("current_head_remediation_or_supersession", result["observations"][0]["runs"][0]["route"])
        self.assertFalse(result["pass_manufactured"])
        self.assertEqual(penta_rg.digest({k: v for k, v in result.items() if k != "receipt_sha256"}), result["receipt_sha256"])

    def test_expired_run_does_not_block_fresh_retry_in_same_sweep(self):
        client = RecoveryGitHubClient([
            self.failed_run("2026-10-01T00:00:00Z"),
            self.failed_run("2026-11-05T18:00:00Z", 456),
        ])
        result = self.recover(client)
        reruns = [path for path, _ in client.posts if path.endswith("/rerun-failed-jobs")]
        self.assertEqual(["/repos/acme/repo/actions/runs/456/rerun-failed-jobs"], reruns)
        self.assertEqual("HOLD", result["status"])
        self.assertEqual("DISPATCHED", result["executed_actions"][0]["status"])

    def test_month_old_provider_rejection_produces_receipt_and_is_not_repeated(self):
        rejection = penta_rg.PentaRGError(
            'github_POST_/repos/acme/repo/actions/runs/123/rerun-failed-jobs_403:{"message":"Unable to retry this workflow run because it was created over a month ago"}'
        )
        client = RecoveryGitHubClient([self.failed_run()], rejection)
        result = self.recover(client)
        self.assertEqual("HOLD", result["status"])
        self.assertEqual("SKIPPED_PROVIDER_NOT_RETRIABLE", result["executed_actions"][0]["status"])
        self.assertEqual(1, len(client.comments))
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")
        again = self.recover(client)
        self.assertEqual("HOLD", again["status"])
        self.assertEqual("NOOP_PROVIDER_NOT_RETRIABLE", again["executed_actions"][0]["status"])
        self.assertEqual(1, len([path for path, _ in client.posts if path.endswith("/rerun-failed-jobs")]))
        self.assertEqual(1, len(client.comments))

    def test_successful_retry_is_still_bounded_to_one_request(self):
        client = RecoveryGitHubClient([self.failed_run("2026-11-05T18:00:00Z")])
        self.recover(client)
        again = self.recover(client)
        self.assertEqual("NOOP_ALREADY_REQUESTED", again["executed_actions"][0]["status"])
        self.assertEqual(1, len([path for path, _ in client.posts if path.endswith("/rerun-failed-jobs")]))

    def test_dry_run_never_posts_retry_or_comment(self):
        client = RecoveryGitHubClient([self.failed_run("2026-11-05T18:00:00Z")])
        result = self.recover(client, apply=False)
        self.assertEqual("HOLD", result["status"])
        self.assertEqual("rerun_failed_workflow", result["planned_actions"][0]["action"])
        self.assertEqual([], result["executed_actions"])
        self.assertEqual([], client.posts)

    def test_permission_and_unrelated_age_errors_still_fail_closed(self):
        for message in ["Resource not accessible by integration", "Forbidden", "An unrelated record was created over a month ago"]:
            with self.subTest(message=message):
                rejection = penta_rg.PentaRGError(
                    f'github_POST_/repos/acme/repo/actions/runs/123/rerun-failed-jobs_403:{{"message":"{message}"}}'
                )
                client = RecoveryGitHubClient([self.failed_run()], rejection)
                with self.assertRaises(penta_rg.PentaRGError):
                    self.recover(client)
                self.assertEqual([], client.comments)
        unrelated = penta_rg.PentaRGError(
            'github_PATCH_/repos/acme/repo/pulls/42_403:{"message":"Unable to retry this workflow run because it was created over a month ago"}'
        )
        self.assertFalse(penta_rg.provider_rerun_not_retriable(unrelated))

    def test_quota_exhaustion_remains_deferred(self):
        client = RecoveryGitHubClient([self.failed_run()], penta_rg.ProviderDeferred("github_quota_exhausted"))
        result = self.recover(client)
        self.assertEqual("DEFERRED", result["status"])
        self.assertEqual("github_quota_exhausted", result["deferred"]["reason"])
        self.assertEqual([], client.comments)

    def test_nonretriable_receipt_after_300_comments_prevents_repeat(self):
        # Save the real paginator because recover() replaces the client class.
        paginator = penta_rg.GitHubClient.paginate

        class PaginatedClient(RecoveryGitHubClient):
            def paginate(self, path, pages=3):
                if "/comments?" in path:
                    return paginator(self, path, pages)
                return super().paginate(path, pages)

            def get(self, path):
                if "/comments?" in path:
                    self.budget.consume()
                    page = int(path.rsplit("page=", 1)[1])
                    return self.comments[(page - 1) * 100:page * 100]
                return super().get(path)

        client = PaginatedClient([self.failed_run()], penta_rg.PentaRGError(
            'github_POST_/repos/acme/repo/actions/runs/123/rerun-failed-jobs_403:{"message":"Unable to retry this workflow run because it was created over a month ago"}'
        ))
        client.comments = [{"body": f"Existing comment {i}"} for i in range(300)]
        client.budget = penta_rg.RequestBudget(100)
        first = self.recover(client)
        again = self.recover(client)
        self.assertEqual("SKIPPED_PROVIDER_NOT_RETRIABLE", first["executed_actions"][0]["status"])
        self.assertEqual("NOOP_PROVIDER_NOT_RETRIABLE", again["executed_actions"][0]["status"])
        self.assertEqual(301, len(client.comments))
        self.assertEqual(1, len([path for path, _ in client.posts if path.endswith("/rerun-failed-jobs")]))

        # If complete history cannot be established, do not request another run.
        client.budget = penta_rg.RequestBudget(3)
        client.posts.clear()
        deferred = self.recover(client)
        self.assertEqual("DEFERRED", deferred["status"])
        self.assertEqual("provider_request_budget_exhausted", deferred["deferred"]["reason"])
        self.assertEqual([], client.posts)

    def test_local_audit_passes_minimal_valid_contract(self):
        policy = self.policy()
        topology = {"schema": penta_rg.TOPOLOGY_SCHEMA, "nodes": [], "edges": []}
        with tempfile.TemporaryDirectory() as tmp:
            result = penta_rg.local_audit(Path(tmp), policy, topology)
        self.assertEqual("PASS", result["status"])
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
