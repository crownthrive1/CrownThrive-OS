from pathlib import Path
import sys
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
        assert number == 1502
        self.pull_reads += 1
        return {"base": {"sha": "b" * 40}}


def test_trusted_main_start_uses_event_fence_without_provider_commit_read() -> None:
    client = StubTrustedClient()
    assert client.main_sha("main") == "a" * 40
    assert client.pull_reads == 0


def test_trusted_main_end_uses_candidate_current_base_sha() -> None:
    client = StubTrustedClient()
    assert client.main_sha("main") == "a" * 40
    assert client.main_sha("main") == "b" * 40
    assert client.pull_reads == 1


def test_rate_limit_403_detection_is_narrow() -> None:
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
    assert trusted._rate_limited_403(limited, "API rate limit exceeded") is True
    assert trusted._rate_limited_403(permission, "Resource not accessible by integration") is False


def test_rate_limit_backoff_is_bounded() -> None:
    limited = urllib.error.HTTPError(
        "https://api.github.com/example",
        403,
        "Forbidden",
        {"Retry-After": "999"},
        None,
    )
    assert trusted._retry_delay(limited, 0) == trusted.MAX_RATE_LIMIT_SLEEP_SECONDS


def test_wrapper_preserves_fail_closed_and_no_authority_expansion() -> None:
    text = (SCRIPTS / "governed_collision_agent_v2_trusted.py").read_text(encoding="utf-8")
    assert '"reason_code": "COLLISION_OBSERVER_FAILED_CLOSED"' in text
    assert '"merge_authority": False' in text
    assert '"D3_auto": False' in text
    assert "provider_write_authority" not in text
