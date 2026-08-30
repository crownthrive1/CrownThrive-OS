from pathlib import Path
import io
import json
import sys
import unittest
import urllib.error
from unittest.mock import patch


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


class FakeResponse:
    def __init__(self, payload: object, headers: dict[str, str] | None = None) -> None:
        self.payload = payload
        self.headers = headers or {"X-RateLimit-Remaining": "59"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def http_error(
    status: int,
    body: str,
    *,
    remaining: str = "100",
) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://api.github.com/repos/crownthrive1/CrownThrive-OS/git/ref/heads/main",
        status,
        "Forbidden",
        {
            "X-RateLimit-Remaining": remaining,
            "X-GitHub-Request-Id": "REQ-123",
        },
        io.BytesIO(body.encode("utf-8")),
    )


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

    def test_authenticated_403_can_degrade_to_exact_public_provider_read(self) -> None:
        client = trusted.TrustedCandidateClient(
            "crownthrive1/CrownThrive-OS",
            "test-token",
            event_base_sha="a" * 40,
            candidate=1474,
        )
        payload = {"object": {"type": "commit", "sha": "b" * 40}}
        with patch.object(
            trusted.urllib.request,
            "urlopen",
            side_effect=[
                http_error(403, "Resource not accessible by integration"),
                FakeResponse(payload),
                FakeResponse(payload),
            ],
        ):
            self.assertEqual(client.main_sha("main"), "b" * 40)
            self.assertEqual(client.main_sha("main"), "b" * 40)

        evidence = client.transport_evidence()
        self.assertTrue(evidence["public_read_mode"])
        self.assertEqual(evidence["authenticated_requests"], 1)
        self.assertEqual(evidence["public_fallback_requests"], 2)
        self.assertEqual(evidence["last_transport"], "public-fallback")

    def test_public_fallback_failure_remains_fail_closed(self) -> None:
        client = trusted.TrustedCandidateClient(
            "crownthrive1/CrownThrive-OS",
            "test-token",
            event_base_sha="a" * 40,
            candidate=1474,
        )
        with patch.object(
            trusted.urllib.request,
            "urlopen",
            side_effect=[
                http_error(403, "Resource not accessible by integration"),
                http_error(403, "API rate limit exceeded", remaining="0"),
                http_error(403, "API rate limit exceeded", remaining="0"),
                http_error(403, "API rate limit exceeded", remaining="0"),
                http_error(403, "API rate limit exceeded", remaining="0"),
                http_error(403, "API rate limit exceeded", remaining="0"),
            ],
        ), patch.object(trusted.time, "sleep", return_value=None):
            with self.assertRaises(trusted.agent.GitHubReadError):
                client.main_sha("main")

        self.assertFalse(client.public_read_mode)
        self.assertEqual(client.authenticated_requests, 1)
        self.assertEqual(client.public_fallback_requests, trusted.MAX_HTTP_ATTEMPTS)

    def test_public_fallback_request_budget_is_hard_bounded(self) -> None:
        client = trusted.TrustedCandidateClient(
            "crownthrive1/CrownThrive-OS",
            "test-token",
            event_base_sha="a" * 40,
            candidate=1474,
        )
        client.public_read_mode = True
        client.public_fallback_requests = trusted.MAX_PUBLIC_FALLBACK_REQUESTS
        with self.assertRaises(trusted.agent.GitHubReadError) as ctx:
            client.main_sha("main")
        self.assertIn("public_fallback_request_budget_exceeded", str(ctx.exception))

    def test_transport_evidence_contains_no_token(self) -> None:
        client = trusted.TrustedCandidateClient(
            "crownthrive1/CrownThrive-OS",
            "super-secret-token",
            event_base_sha="a" * 40,
            candidate=1474,
        )
        rendered = json.dumps(client.transport_evidence())
        self.assertNotIn("super-secret-token", rendered)

    def test_wrapper_preserves_fail_closed_and_no_authority_expansion(self) -> None:
        text = (SCRIPTS / "governed_collision_agent_v2_trusted.py").read_text(encoding="utf-8")
        self.assertIn('"reason_code": "COLLISION_OBSERVER_FAILED_CLOSED"', text)
        self.assertIn('"merge_authority": False', text)
        self.assertIn('"D3_auto": False', text)
        self.assertNotIn("provider_write_authority", text)


if __name__ == "__main__":
    unittest.main()
