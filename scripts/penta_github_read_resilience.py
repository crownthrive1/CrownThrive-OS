#!/usr/bin/env python3
"""PentaGitHubResilience™ — fail-closed GitHub read resilience for Collision Governance v2.

The adapter preserves the existing collision-governance decision engine while
removing avoidable dependency on the installation REST quota for public
repository reads. It never grants write, merge, force-push, or provider
authority.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

import governed_collision_agent_v2 as collision

_TRANSIENT = {429, 502, 503, 504}
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "crownthrive-penta-github-resilience-v1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_error_payload(exc: urllib.error.HTTPError) -> tuple[str, Mapping[str, str]]:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    return body, exc.headers


def _is_rate_limit(code: int, body: str, headers: Mapping[str, str]) -> bool:
    remaining = str(headers.get("X-RateLimit-Remaining", ""))
    text = body.lower()
    return code == 429 or (code == 403 and (remaining == "0" or "rate limit" in text or "secondary rate" in text or "abuse detection" in text))


def resilient_request(self: collision.GitHubClient, url: str) -> tuple[Any, Mapping[str, str]]:
    last_error: Exception | str | None = None
    for attempt in range(4):
        candidates: list[tuple[str, str | None]] = [("authenticated", self.token)]
        if self.token:
            candidates.append(("public-fallback", None))
        auth_was_rate_limited = False
        for label, token in candidates:
            if label == "public-fallback" and not auth_was_rate_limited:
                continue
            request = urllib.request.Request(url, headers=_headers(token))
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = response.read().decode("utf-8")
                    try:
                        return json.loads(payload), response.headers
                    except json.JSONDecodeError as exc:
                        raise collision.GitHubReadError(f"github_invalid_json:{url}:{exc}") from exc
            except urllib.error.HTTPError as exc:
                body, response_headers = _http_error_payload(exc)
                rate_limited = _is_rate_limit(exc.code, body, response_headers)
                last_error = f"HTTP {exc.code}: {body[:240]}"
                if label == "authenticated" and rate_limited:
                    auth_was_rate_limited = True
                    continue
                if rate_limited or exc.code in _TRANSIENT:
                    break
                if label == "public-fallback" and auth_was_rate_limited and exc.code in {401, 403, 404}:
                    break
                raise collision.GitHubReadError(f"github_read_failed:{url}:HTTP {exc.code}:{body[:240]}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                break
        if attempt < 3:
            time.sleep(min(2**attempt, 8))
    raise collision.GitHubReadError(f"github_read_failed:{url}:{last_error}")


_original_main_sha = collision.GitHubClient.main_sha


def resilient_main_sha(self: collision.GitHubClient, branch: str) -> str:
    ref = f"refs/heads/{branch}"
    try:
        output = subprocess.check_output(["git", "ls-remote", f"https://github.com/{self.repository}.git", ref], text=True, stderr=subprocess.DEVNULL, timeout=30)
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == ref and _SHA.fullmatch(parts[0]):
                return parts[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return _original_main_sha(self, branch)


collision.GitHubClient._request = resilient_request
collision.GitHubClient.main_sha = resilient_main_sha


if __name__ == "__main__":
    raise SystemExit(collision.main())
