from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import governed_collision_agent_v2 as agent  # noqa: E402
import governed_collision_agent_v2_trusted_consolidated as trusted  # noqa: E402

A40 = "a" * 40
B40 = "b" * 40
C40 = "c" * 40
D40 = "d" * 40


def pull_node(number: int, head: str, base: str, *, renamed=False, paginated=False):
    return {
        "number": number,
        "headRefOid": head,
        "baseRefOid": base,
        "body": None,
        "isDraft": False,
        "updatedAt": "2026-09-07T00:00:00Z",
        "files": {
            "pageInfo": {"hasNextPage": paginated, "endCursor": None},
            "nodes": [
                {
                    "path": f"file-{number}.py",
                    "changeType": "RENAMED" if renamed else "MODIFIED",
                }
            ],
        },
    }


def snapshot(nodes):
    return {
        "data": {
            "repository": {
                "pullRequests": {
                    "totalCount": len(nodes),
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": nodes,
                }
            }
        }
    }


class StubClient(trusted.ConsolidatedTrustedCandidateClient):
    def __init__(self, response, candidate=11):
        super().__init__(
            "crownthrive1/CrownThrive-OS",
            "test-token",
            event_base_sha=B40,
            candidate=candidate,
            branch="main",
        )
        self.response = response
        self.graphql_calls = 0

    def _graphql_request(self, query, variables):
        self.graphql_calls += 1
        return self.response


class ConsolidatedSnapshotTests(unittest.TestCase):
    def test_batches_then_scopes_to_current_gold(self):
        response = snapshot(
            [
                pull_node(11, A40, B40),
                pull_node(12, C40, D40),
                pull_node(13, D40, B40),
            ]
        )
        client = StubClient(response, candidate=11)
        with patch.object(client, "live_branch_sha", return_value=B40):
            pulls = client.open_pulls()
        self.assertEqual([p["number"] for p in pulls], [11, 13])
        self.assertEqual(client.observed_open_pull_count, 3)
        self.assertEqual(client.gold_lane_open_pull_count, 2)
        self.assertEqual(client.stale_base_open_pull_count, 1)
        self.assertTrue(client.graphql_snapshot_mode)
        self.assertEqual(client.graphql_calls, 1)

    def test_candidate_retained_when_stale(self):
        response = snapshot([pull_node(11, A40, D40)])
        client = StubClient(response, candidate=11)
        with patch.object(client, "live_branch_sha", return_value=B40):
            pulls = client.open_pulls()
        self.assertEqual([p["number"] for p in pulls], [11])
        self.assertEqual(client.stale_base_open_pull_count, 0)

    def test_graphql_files_used_for_simple_current_peer(self):
        response = snapshot([pull_node(11, A40, B40)])
        client = StubClient(response, candidate=11)
        with patch.object(client, "live_branch_sha", return_value=B40):
            client.open_pulls()
        files = client.files(11)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "file-11.py")
        self.assertIsNone(files[0].value_digest)

    def test_paginated_files_require_rest(self):
        response = snapshot([pull_node(11, A40, B40, paginated=True)])
        client = StubClient(response, candidate=11)
        with patch.object(client, "live_branch_sha", return_value=B40):
            client.open_pulls()
        self.assertIn(11, client._snapshot_rest_file_numbers)

    def test_renamed_files_require_rest_for_previous_path(self):
        response = snapshot([pull_node(11, A40, B40, renamed=True)])
        client = StubClient(response, candidate=11)
        with patch.object(client, "live_branch_sha", return_value=B40):
            client.open_pulls()
        self.assertIn(11, client._snapshot_rest_file_numbers)

    def test_invalid_graphql_snapshot_fails_closed_through_rest_fallback(self):
        response = snapshot([pull_node(11, A40, B40)])
        response["data"]["repository"]["pullRequests"]["nodes"][0]["baseRefOid"] = ""
        client = StubClient(response, candidate=11)
        with patch.object(
            trusted.base.TrustedCandidateClient,
            "open_pulls",
            side_effect=agent.GitHubReadError("rest_fallback_failed_closed"),
        ):
            with self.assertRaisesRegex(agent.GitHubReadError, "rest_fallback_failed_closed"):
                client.open_pulls()
        self.assertFalse(client.graphql_snapshot_mode)
        self.assertIn("graphql_pull_sha_invalid", client.graphql_last_error)

    def test_too_many_open_prs_fails_closed_to_rest(self):
        response = snapshot([])
        response["data"]["repository"]["pullRequests"]["totalCount"] = agent.MAX_OPEN_PRS + 1
        client = StubClient(response, candidate=11)
        with patch.object(
            trusted.base.TrustedCandidateClient,
            "open_pulls",
            side_effect=agent.GitHubReadError("rest_fallback_failed_closed"),
        ):
            with self.assertRaisesRegex(agent.GitHubReadError, "rest_fallback_failed_closed"):
                client.open_pulls()
        self.assertFalse(client.graphql_snapshot_mode)
        self.assertIn("bounded_snapshot_may_be_truncated", client.graphql_last_error)

    def test_transport_evidence_contains_both_budgets(self):
        client = StubClient(snapshot([pull_node(11, A40, B40)]))
        evidence = client.transport_evidence()
        self.assertEqual(evidence["public_request_budget"], 50)
        self.assertEqual(evidence["graphql_request_budget"], 20)
        self.assertEqual(
            evidence["consolidated_scope"],
            "graphql_snapshot_then_current_gold_partition",
        )
        self.assertNotIn("token", " ".join(evidence).lower())

    def test_graphql_error_uses_one_existing_rest_path(self):
        client = StubClient(snapshot([pull_node(11, A40, B40)]))
        with patch.object(
            client,
            "_load_graphql_open_pulls",
            side_effect=agent.GitHubReadError("graphql_test_failure"),
        ), patch.object(
            trusted.base.TrustedCandidateClient,
            "open_pulls",
            return_value=[{"number": 11, "base": {"sha": B40}, "head": {"sha": A40}}],
        ):
            pulls = client.open_pulls()
        self.assertEqual(pulls[0]["number"], 11)
        self.assertFalse(client.graphql_snapshot_mode)
        self.assertEqual(client.graphql_last_error, "graphql_test_failure")

    def test_wrapper_restores_base_class_after_main_error(self):
        original = trusted.base.TrustedCandidateClient
        with patch.object(trusted.base, "main", return_value=7):
            self.assertEqual(trusted.main([]), 7)
        self.assertIs(trusted.base.TrustedCandidateClient, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
