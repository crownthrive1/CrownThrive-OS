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
            expected_main_sha="a" * 40,
            candidate=1502,
        )
        self.pull_reads = 0

    def pull(self, number: int):
        if number != 1502:
            raise AssertionError(f"unexpected candidate {number}")
        self.pull_reads += 1
        return {"base": {"sha": "b" * 40}}


class CollisionTrustedObserverTests(unittest.TestCase):
    def test_trusted_main_start_uses_event_fence_without_provider_commit_read(self) -> None:
        client = StubTrustedClient()
        self.assertEqual(client.main_sha("main"), "a" * 40)
        self.assertEqual(client.pull_reads, 0)

    def test_trusted_main_end_uses_candidate_current_base_sha(self) -> None:
        client = StubTrustedClient()
        self.assertEqual(client.main_sha("main"), "a" * 40)
        self.assertEqual(client.main_sha("main"), "b" * 40)
        self.assertEqual(client.pull_reads, 1)

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
