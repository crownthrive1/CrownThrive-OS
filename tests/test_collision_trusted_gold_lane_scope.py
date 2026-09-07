from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import governed_collision_agent_v2_trusted as trusted  # noqa: E402

MAIN = "a" * 40
CURRENT = "b" * 40
STALE = "c" * 40
CANDIDATE = 3818


def pull(number: int, base_sha: str) -> dict:
    return {
        "number": number,
        "head": {"sha": f"{number:040x}"[-40:]},
        "base": {"sha": base_sha},
        "body": None,
    }


class TrustedGoldLaneScopeTests(unittest.TestCase):
    def client(self) -> trusted.TrustedCandidateClient:
        return trusted.TrustedCandidateClient(
            "crownthrive1/CrownThrive-OS",
            "test-token",
            event_base_sha=MAIN,
            candidate=CANDIDATE,
            branch="main",
        )

    def test_current_base_peers_and_candidate_are_retained(self) -> None:
        client = self.client()
        observed = [
            pull(100, CURRENT),
            pull(200, STALE),
            pull(CANDIDATE, STALE),
            pull(400, CURRENT),
        ]
        with patch.object(
            trusted.agent.GitHubClient, "open_pulls", return_value=observed
        ), patch.object(client, "live_branch_sha", return_value=CURRENT):
            selected = client.open_pulls()

        self.assertEqual([int(item["number"]) for item in selected], [100, CANDIDATE, 400])
        evidence = client.transport_evidence()
        self.assertEqual(evidence["observed_open_pull_count"], 4)
        self.assertEqual(evidence["gold_lane_open_pull_count"], 3)
        self.assertEqual(evidence["stale_base_open_pull_count"], 1)
        self.assertEqual(evidence["gold_lane_main_sha"], CURRENT)
        self.assertEqual(
            evidence["gold_lane_scope_rule"],
            "candidate_plus_open_prs_with_base_sha_equal_live_target_sha",
        )

    def test_stale_non_candidate_is_excluded(self) -> None:
        client = self.client()
        with patch.object(
            trusted.agent.GitHubClient,
            "open_pulls",
            return_value=[pull(200, STALE), pull(CANDIDATE, CURRENT)],
        ), patch.object(client, "live_branch_sha", return_value=CURRENT):
            selected = client.open_pulls()
        self.assertEqual([item["number"] for item in selected], [CANDIDATE])
        self.assertEqual(client.stale_base_open_pull_count, 1)

    def test_exact_candidate_is_never_hidden_by_stale_base(self) -> None:
        client = self.client()
        with patch.object(
            trusted.agent.GitHubClient,
            "open_pulls",
            return_value=[pull(CANDIDATE, STALE)],
        ), patch.object(client, "live_branch_sha", return_value=CURRENT):
            selected = client.open_pulls()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["number"], CANDIDATE)
        self.assertEqual(client.stale_base_open_pull_count, 0)

    def test_missing_base_metadata_fails_closed(self) -> None:
        client = self.client()
        malformed = {"number": 99, "head": {"sha": "d" * 40}}
        with patch.object(
            trusted.agent.GitHubClient, "open_pulls", return_value=[malformed]
        ), patch.object(client, "live_branch_sha", return_value=CURRENT):
            with self.assertRaisesRegex(
                trusted.agent.GitHubReadError, "trusted_pull_scope_metadata_missing"
            ):
                client.open_pulls()

    def test_empty_base_sha_fails_closed(self) -> None:
        client = self.client()
        malformed = pull(99, "")
        with patch.object(
            trusted.agent.GitHubClient, "open_pulls", return_value=[malformed]
        ), patch.object(client, "live_branch_sha", return_value=CURRENT):
            with self.assertRaisesRegex(
                trusted.agent.GitHubReadError, "trusted_pull_base_sha_empty"
            ):
                client.open_pulls()

    def test_branch_is_explicit_and_evidence_only(self) -> None:
        client = trusted.TrustedCandidateClient(
            "crownthrive1/CrownThrive-OS",
            None,
            event_base_sha=MAIN,
            candidate=CANDIDATE,
            branch="release-candidate",
        )
        self.assertEqual(client.gold_lane_branch, "release-candidate")
        evidence = client.transport_evidence()
        self.assertNotIn("token", " ".join(evidence.keys()).lower())

    def test_missing_branch_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            trusted.agent.GitHubReadError, "trusted_gold_lane_branch_required"
        ):
            trusted.TrustedCandidateClient(
                "crownthrive1/CrownThrive-OS",
                None,
                event_base_sha=MAIN,
                candidate=CANDIDATE,
                branch="",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
