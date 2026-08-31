from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import governed_collision_agent_v2 as agent  # noqa: E402
import governed_collision_agent_v2_trusted as trusted  # noqa: E402


class _Response:
    def __init__(self, body: bytes):
        self._body = body
        self.headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._body
        return self._body[:size]


def _client(*, token: str | None = None) -> trusted.TrustedCandidateClient:
    return trusted.TrustedCandidateClient(
        "crownthrive1/CrownThrive-OS",
        token,
        event_base_sha="a" * 40,
        candidate=1962,
    )


class TrustedRawFallbackTests(unittest.TestCase):
    def test_degraded_semantic_content_uses_exact_raw_transport_without_rest_budget(self):
        client = _client(token=None)
        seen: list[str] = []

        def fake_urlopen(request, timeout=30):
            seen.append(request.full_url)
            return _Response(b"create table example(id bigint);\n")

        with mock.patch.object(trusted.urllib.request, "urlopen", side_effect=fake_urlopen):
            content = client.content("supabase/migrations/example.sql", "b" * 40)

        self.assertEqual(content, "create table example(id bigint);\n")
        self.assertEqual(
            seen,
            [
                "https://raw.githubusercontent.com/crownthrive1/CrownThrive-OS/"
                + ("b" * 40)
                + "/supabase/migrations/example.sql"
            ],
        )
        evidence = client.transport_evidence()
        self.assertEqual(evidence["public_fallback_requests"], 0)
        self.assertEqual(evidence["public_raw_requests"], 1)
        self.assertEqual(evidence["last_transport"], "public-raw")

    def test_raw_transport_requires_immutable_exact_sha(self):
        client = _client(token=None)

        with mock.patch.object(
            trusted.urllib.request,
            "urlopen",
            side_effect=AssertionError("provider request must not occur for mutable ref"),
        ):
            with self.assertRaisesRegex(
                agent.GitHubReadError, "trusted_public_raw_exact_sha_required"
            ):
                client.content("supabase/migrations/example.sql", "main")

    def test_raw_transport_remains_bounded_and_fail_closed(self):
        client = _client(token=None)
        client.public_raw_requests = trusted.MAX_PUBLIC_RAW_REQUESTS

        with mock.patch.object(
            trusted.urllib.request,
            "urlopen",
            side_effect=AssertionError(
                "provider request must not occur after raw budget is exhausted"
            ),
        ):
            with self.assertRaisesRegex(
                agent.GitHubReadError, "public_raw_request_budget_exceeded"
            ):
                client.content("supabase/migrations/example.sql", "c" * 40)

    def test_raw_content_cache_does_not_reconsume_budget(self):
        client = _client(token=None)
        calls = 0

        def fake_urlopen(request, timeout=30):
            nonlocal calls
            calls += 1
            return _Response(b"alter table example add column safe boolean;\n")

        with mock.patch.object(trusted.urllib.request, "urlopen", side_effect=fake_urlopen):
            first = client.content("supabase/migrations/example.sql", "d" * 40)
            second = client.content("supabase/migrations/example.sql", "d" * 40)

        self.assertEqual(first, second)
        self.assertEqual(calls, 1)
        self.assertEqual(client.public_raw_requests, 1)
        self.assertEqual(client._semantic_inspections, 1)


if __name__ == "__main__":
    unittest.main()
