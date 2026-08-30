from pathlib import Path
import sys
import unittest
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import governed_collision_agent_v2_trusted as trusted  # noqa: E402


class StubTrustedClient(trusted.TrustedCandidateClient):
    def __init__(self) -> None:
        super().__init__(
            "crownthrive1/CrownThrive-OS",
            None,
            event_base_sha="a" * 40,
            candidate=1502,
        )
        self.live_ref_reads = 0
        self.live_ref_values = ["b" * 40, "b" * 40]

    def get(self, path: str):
        self.assert_live_ref_path(path)
        value = self.live_ref_values[self.live_ref_reads]
        self.live_ref_reads += 1
        return {"object": {"type": "commit", "sha": value}}

    @staticmethod
    def assert_live_ref_path(path: str) -> None:
        if path != "/git/ref/heads/main":
            raise AssertionError(f"unexpected trusted ref path {path}")


class CollisionTrustedObserverTests(unittest.TestCase):
    def test_both_main_fences_use_live_git_ref(self) -> None:
        client = StubTrustedClient()
        self.assertEqual(client.main_sha("main"), "b" * 40)
        self.assertEqual(client.main_sha("main"), "b" * 40)
        self.assertEqual(client.live_ref_reads, 2)

    def test_event_base_sha_is_audit_context_not_main_fence(self) -> None:
        client = StubTrustedClient()
        self.assertEqual(client.event_base_sha, "a" * 40)
        self.assertEqual(client.main_sha("main"), "b" * 40)
        self.assertNotEqual(client.event_base_sha, client.main_sha("main"))

    def test_live_ref_requires_commit_object(self) -> None:
        client = StubTrustedClient()
        client.get = lambda path: {"object": {"type": "tag", "sha": "c" * 40}}
        with self.assertRaises(trusted.agent.GitHubReadError):
            client.main_sha("main")

    def test_rate_limit_403_detection_is_narrow(self) -> None:
        limited = urllib.error.HTTPError(
            "https://api.github.com/example",
            403,
            "Forbidden",
            {"X-RateLimit-Remaining": "0"},
            None,
        )
        permission = urllib.error.HTTPError(
            "https://api.github.com/example",
            403,
            "Forbidden",
            {"X-RateLimit-Remaining": "100"},
            None,
        )
        self.assertTrue(trusted._rate_limited_403(limited, "API rate limit exceeded"))
        self.assertFalse(
            trusted._rate_limited_403(permission, "Resource not accessible by integration")
        )

    def test_rate_limit_backoff_is_bounded(self) -> None:
        limited = urllib.error.HTTPError(
            "https://api.github.com/example",
            403,
            "Forbidden",
            {"Retry-After": "999"},
            None,
        )
        self.assertEqual(
            trusted._retry_delay(limited, 0),
            trusted.MAX_RATE_LIMIT_SLEEP_SECONDS,
        )

    def test_wrapper_preserves_fail_closed_and_no_authority_expansion(self) -> None:
        text = (SCRIPTS / "governed_collision_agent_v2_trusted.py").read_text(encoding="utf-8")
        self.assertIn('"reason_code": "COLLISION_OBSERVER_FAILED_CLOSED"', text)
        self.assertIn('"merge_authority": False', text)
        self.assertIn('"D3_auto": False', text)
        self.assertNotIn("provider_write_authority", text)


if __name__ == "__main__":
    unittest.main()
