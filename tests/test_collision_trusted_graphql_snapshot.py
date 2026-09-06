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
import governed_collision_agent_v2_trusted as trusted  # noqa: E402


A40 = "a" * 40
B40 = "b" * 40
C40 = "c" * 40
D40 = "d" * 40


def graphql_snapshot(*, paginated_files: bool = False):
    return {
        "data": {
            "repository": {
                "pullRequests": {
                    "totalCount": 2,
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "number": 11,
                            "headRefOid": A40,
                            "baseRefOid": B40,
                            "body": "first",
                            "isDraft": False,
                            "updatedAt": "2026-09-06T00:00:00Z",
                            "files": {
                                "pageInfo": {
                                    "hasNextPage": paginated_files,
                                    "endCursor": "file-cursor" if paginated_files else None,
                                },
                                "nodes": [
                                    {"path": "supabase/migrations/a.sql", "changeType": "ADDED"}
                                ],
                            },
                        },
                        {
                            "number": 12,
                            "headRefOid": C40,
                            "baseRefOid": D40,
                            "body": "second",
                            "isDraft": True,
                            "updatedAt": "2026-09-06T00:01:00Z",
                            "files": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": [
                                    {"path": "tests/test_x.py", "changeType": "MODIFIED"}
                                ],
                            },
                        },
                    ],
                }
            }
        }
    }


class StubGraphQLClient(trusted.TrustedCandidateClient):
    def __init__(self, response):
        super().__init__(
            "crownthrive1/CrownThrive-OS",
            "test-token",
            event_base_sha=B40,
            candidate=11,
        )
        self.response = response
        self.graphql_calls = 0

    def _graphql_request(self, query, variables):
        self.graphql_calls += 1
        self.assert_query(query, variables)
        return self.response

    @staticmethod
    def assert_query(query, variables):
        if "pullRequests" not in query:
            raise AssertionError("trusted snapshot query missing pullRequests")
        if variables["owner"] != "crownthrive1":
            raise AssertionError("owner mismatch")
        if variables["name"] != "CrownThrive-OS":
            raise AssertionError("repository mismatch")


class TrustedGraphQLSnapshotTests(unittest.TestCase):
    def test_open_pulls_batches_files_without_rest_file_reads(self):
        client = StubGraphQLClient(graphql_snapshot())
        pulls = client.open_pulls()
        self.assertEqual([item["number"] for item in pulls], [11, 12])
        self.assertEqual(client.graphql_calls, 1)
        self.assertTrue(client.graphql_snapshot_mode)
        self.assertEqual(client.graphql_snapshot_reads, 1)

        with patch.object(
            agent.GitHubClient,
            "files",
            side_effect=AssertionError("REST files should not be called"),
        ):
            files = client.files(11)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "supabase/migrations/a.sql")
        self.assertEqual(files[0].access, "create")
        self.assertIsNone(files[0].value_digest)

    def test_paginated_graphql_files_fall_back_to_exact_rest_reader(self):
        client = StubGraphQLClient(graphql_snapshot(paginated_files=True))
        client.open_pulls()
        sentinel = [
            agent.ChangedFile(
                path="supabase/migrations/a.sql",
                access="create",
                value_digest="f" * 64,
            )
        ]
        with patch.object(agent.GitHubClient, "files", return_value=sentinel) as rest_files:
            observed = client.files(11)
        rest_files.assert_called_once_with(11)
        self.assertEqual(observed, sentinel)

    def test_rename_graphql_file_falls_back_for_previous_path_lineage(self):
        response = graphql_snapshot()
        response["data"]["repository"]["pullRequests"]["nodes"][0]["files"]["nodes"][0][
            "changeType"
        ] = "RENAMED"
        client = StubGraphQLClient(response)
        client.open_pulls()
        sentinel = [
            agent.ChangedFile(
                path="new.sql",
                access="create",
                value_digest="e" * 64,
                previous_path="old.sql",
            )
        ]
        with patch.object(agent.GitHubClient, "files", return_value=sentinel) as rest_files:
            observed = client.files(11)
        rest_files.assert_called_once_with(11)
        self.assertEqual(observed[0].previous_path, "old.sql")

    def test_graphql_snapshot_over_bound_fails_closed(self):
        response = graphql_snapshot()
        response["data"]["repository"]["pullRequests"]["totalCount"] = agent.MAX_OPEN_PRS + 1
        client = StubGraphQLClient(response)
        with patch.object(
            agent.GitHubClient,
            "open_pulls",
            side_effect=agent.GitHubReadError("rest_fallback_unavailable"),
        ):
            with self.assertRaises(agent.GitHubReadError):
                client.open_pulls()
        self.assertFalse(client.graphql_snapshot_mode)
        self.assertIn("bounded_snapshot_may_be_truncated", client.graphql_last_error or "")

    def test_transport_evidence_contains_snapshot_mode_without_token(self):
        client = StubGraphQLClient(graphql_snapshot())
        client.open_pulls()
        evidence = client.transport_evidence()
        self.assertTrue(evidence["graphql_snapshot_mode"])
        self.assertEqual(evidence["graphql_snapshot_reads"], 1)
        self.assertEqual(
            evidence["graphql_file_value_digest_mode"],
            "unavailable_fail_conservative",
        )
        self.assertNotIn("test-token", str(evidence))


if __name__ == "__main__":
    unittest.main()
