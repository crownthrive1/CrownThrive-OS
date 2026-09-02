from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import governed_collision_agent_v2_trusted_main as trusted_main  # noqa: E402


class FakeTrustedClient:
    instances: list["FakeTrustedClient"] = []

    def __init__(
        self,
        repository: str,
        token: str | None,
        *,
        event_base_sha: str,
        candidate: int,
    ) -> None:
        self.repository = repository
        self.token = token
        self.event_base_sha = event_base_sha
        self.candidate = candidate
        self.__class__.instances.append(self)

    def transport_evidence(self) -> dict[str, object]:
        return {
            "authenticated_requests": 1,
            "public_fallback_requests": 1,
            "public_read_mode": True,
            "last_transport": "public-fallback",
        }


class CollisionTrustedMainObserverTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeTrustedClient.instances.clear()

    def test_build_client_reuses_shared_trusted_transport(self) -> None:
        with patch.object(trusted_main, "TrustedCandidateClient", FakeTrustedClient):
            client = trusted_main.build_client(
                "crownthrive1/CrownThrive-OS",
                "test-token",
                branch="main",
                event_sha="a" * 40,
            )
        self.assertIsInstance(client, FakeTrustedClient)
        self.assertEqual(client.event_base_sha, "a" * 40)
        self.assertEqual(client.candidate, trusted_main.MAIN_RECONCILIATION_CANDIDATE)

    def test_missing_event_sha_uses_non_authoritative_live_ref_context(self) -> None:
        with patch.object(trusted_main, "TrustedCandidateClient", FakeTrustedClient):
            client = trusted_main.build_client(
                "crownthrive1/CrownThrive-OS",
                None,
                branch="main",
                event_sha=None,
            )
        self.assertEqual(client.event_base_sha, "live-ref:main")

    def test_successful_main_observation_records_live_fences_and_transport(self) -> None:
        captured: dict[str, object] = {}

        def analyze(client, *, branch, candidate, event_action):
            captured.update(
                client=client,
                branch=branch,
                candidate=candidate,
                event_action=event_action,
            )
            return {"decision": {"max_severity": 0, "disposition": "ALLOW"}}

        with patch.object(trusted_main, "TrustedCandidateClient", FakeTrustedClient), patch.object(
            trusted_main.agent,
            "analyze_snapshot",
            side_effect=analyze,
        ), patch.object(trusted_main.agent, "write_report") as write_report:
            status = trusted_main.main(
                [
                    "--repository",
                    "crownthrive1/CrownThrive-OS",
                    "--token",
                    "super-secret-token",
                    "--branch",
                    "main",
                    "--event-sha",
                    "b" * 40,
                    "--event-action",
                    "push",
                    "--output",
                    "report.json",
                ]
            )

        self.assertEqual(status, 0)
        self.assertIsNone(captured["candidate"])
        self.assertEqual(captured["branch"], "main")
        self.assertEqual(captured["event_action"], "push")
        report = write_report.call_args.args[0]
        self.assertEqual(report["trusted_base_fence_source"], "git_ref_live_branch_sha")
        self.assertEqual(report["trusted_end_fence_source"], "git_ref_live_branch_sha")
        self.assertTrue(report["trusted_provider_transport"]["public_read_mode"])
        self.assertFalse(report["merge_authority"])
        self.assertFalse(report["D3_auto"])
        self.assertNotIn("super-secret-token", json.dumps(report))

    def test_material_collision_threshold_is_preserved(self) -> None:
        with patch.object(trusted_main, "TrustedCandidateClient", FakeTrustedClient), patch.object(
            trusted_main.agent,
            "analyze_snapshot",
            return_value={"decision": {"max_severity": 6, "disposition": "HOLD"}},
        ), patch.object(trusted_main.agent, "write_report"):
            status = trusted_main.main(
                [
                    "--repository",
                    "crownthrive1/CrownThrive-OS",
                    "--fail-on-severity",
                    "6",
                ]
            )
        self.assertEqual(status, 2)

    def test_provider_failure_remains_fail_closed_with_transport_diagnostics(self) -> None:
        with patch.object(trusted_main, "TrustedCandidateClient", FakeTrustedClient), patch.object(
            trusted_main.agent,
            "analyze_snapshot",
            side_effect=trusted_main.agent.GitHubReadError("github_public_read_failed:HTTP 403"),
        ), patch.object(trusted_main.agent, "write_report") as write_report:
            status = trusted_main.main(
                [
                    "--repository",
                    "crownthrive1/CrownThrive-OS",
                    "--token",
                    "super-secret-token",
                ]
            )

        self.assertEqual(status, 3)
        report = write_report.call_args.args[0]
        self.assertEqual(report["disposition"], "HOLD")
        self.assertEqual(report["reason_code"], "COLLISION_OBSERVER_FAILED_CLOSED")
        self.assertFalse(report["merge_authority"])
        self.assertFalse(report["D3_auto"])
        self.assertIn("trusted_provider_transport", report)
        self.assertNotIn("super-secret-token", json.dumps(report))

    def test_main_wrapper_contains_no_duplicate_http_or_authorization_logic(self) -> None:
        source = (SCRIPTS / "governed_collision_agent_v2_trusted_main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from governed_collision_agent_v2_trusted import TrustedCandidateClient",
            source,
        )
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("urlopen", source)
        self.assertNotIn('headers["Authorization"]', source)

    def test_trusted_main_workflow_invokes_resilient_wrapper(self) -> None:
        workflow = (
            ROOT / ".github/workflows/collision-governance-trusted-v2.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "python3 scripts/governed_collision_agent_v2_trusted_main.py",
            workflow,
        )
        trusted_main_section = workflow.split("trusted-main-reconciliation:", 1)[1]
        self.assertNotIn(
            "python3 scripts/governed_collision_agent_v2.py",
            trusted_main_section,
        )
        self.assertIn('--event-sha "${{ github.sha }}"', trusted_main_section)


if __name__ == "__main__":
    unittest.main()
