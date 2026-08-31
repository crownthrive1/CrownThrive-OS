from __future__ import annotations

import sys
from pathlib import Path

import pytest


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


def test_degraded_semantic_content_uses_exact_raw_transport_without_rest_budget(monkeypatch):
    client = _client(token=None)
    seen: list[str] = []

    def fake_urlopen(request, timeout=30):
        seen.append(request.full_url)
        return _Response(b"create table example(id bigint);\n")

    monkeypatch.setattr(trusted.urllib.request, "urlopen", fake_urlopen)

    content = client.content("supabase/migrations/example.sql", "b" * 40)

    assert content == "create table example(id bigint);\n"
    assert seen == [
        "https://raw.githubusercontent.com/crownthrive1/CrownThrive-OS/"
        + ("b" * 40)
        + "/supabase/migrations/example.sql"
    ]
    evidence = client.transport_evidence()
    assert evidence["public_fallback_requests"] == 0
    assert evidence["public_raw_requests"] == 1
    assert evidence["last_transport"] == "public-raw"


def test_raw_transport_requires_immutable_exact_sha(monkeypatch):
    client = _client(token=None)

    def unexpected_urlopen(*args, **kwargs):
        raise AssertionError("provider request must not occur for mutable ref")

    monkeypatch.setattr(trusted.urllib.request, "urlopen", unexpected_urlopen)

    with pytest.raises(agent.GitHubReadError, match="trusted_public_raw_exact_sha_required"):
        client.content("supabase/migrations/example.sql", "main")


def test_raw_transport_remains_bounded_and_fail_closed(monkeypatch):
    client = _client(token=None)
    client.public_raw_requests = trusted.MAX_PUBLIC_RAW_REQUESTS

    def unexpected_urlopen(*args, **kwargs):
        raise AssertionError("provider request must not occur after raw budget is exhausted")

    monkeypatch.setattr(trusted.urllib.request, "urlopen", unexpected_urlopen)

    with pytest.raises(agent.GitHubReadError, match="public_raw_request_budget_exceeded"):
        client.content("supabase/migrations/example.sql", "c" * 40)


def test_raw_content_cache_does_not_reconsume_budget(monkeypatch):
    client = _client(token=None)
    calls = 0

    def fake_urlopen(request, timeout=30):
        nonlocal calls
        calls += 1
        return _Response(b"alter table example add column safe boolean;\n")

    monkeypatch.setattr(trusted.urllib.request, "urlopen", fake_urlopen)

    first = client.content("supabase/migrations/example.sql", "d" * 40)
    second = client.content("supabase/migrations/example.sql", "d" * 40)

    assert first == second
    assert calls == 1
    assert client.public_raw_requests == 1
    assert client._semantic_inspections == 1
