#!/usr/bin/env python3
"""PentaReleaseGateReadback™ — resilient exact-SHA governed-gate poller.

This is a read-only adapter. It prefers the authenticated GitHub API, but when
the installation quota is exhausted it can read the same public check-run
state anonymously. It never turns missing, unreadable, failed, cancelled, or
timed-out evidence into PASS.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

API = "https://api.github.com"


class ReadbackError(RuntimeError):
    pass


def headers(token: str | None) -> dict[str, str]:
    value = {"Accept": "application/vnd.github+json", "User-Agent": "crownthrive-pentarelease-gate-readback-v1", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        value["Authorization"] = f"Bearer {token}"
    return value


def error_body(exc: urllib.error.HTTPError) -> tuple[str, Mapping[str, str]]:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    return body, exc.headers


def is_rate_limit(code: int, body: str, response_headers: Mapping[str, str]) -> bool:
    remaining = str(response_headers.get("X-RateLimit-Remaining", ""))
    text = body.lower()
    return code == 429 or (code == 403 and (remaining == "0" or "rate limit" in text or "secondary rate" in text or "abuse detection" in text))


def request_json(url: str, token: str | None) -> dict[str, Any]:
    last: str | None = None
    for attempt in range(4):
        candidates: list[tuple[str, str | None]] = [("authenticated", token)]
        if token:
            candidates.append(("public-fallback", None))
        auth_rate_limited = False
        for label, candidate_token in candidates:
            if label == "public-fallback" and not auth_rate_limited:
                continue
            request = urllib.request.Request(url, headers=headers(candidate_token))
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ReadbackError("github_object_response_required")
                    return payload
            except urllib.error.HTTPError as exc:
                body, response_headers = error_body(exc)
                limited = is_rate_limit(exc.code, body, response_headers)
                last = f"HTTP {exc.code}: {body[:240]}"
                if label == "authenticated" and limited:
                    auth_rate_limited = True
                    continue
                if limited or exc.code in {502, 503, 504}:
                    break
                if label == "public-fallback" and auth_rate_limited and exc.code in {401, 403, 404}:
                    break
                raise ReadbackError(last) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = str(exc)
                break
        if attempt < 3:
            time.sleep(min(2**attempt, 8))
    raise ReadbackError(last or "github_read_failed")


def latest_check(payload: dict[str, Any], name: str) -> dict[str, Any] | None:
    runs = [item for item in payload.get("check_runs", []) if isinstance(item, dict) and item.get("name") == name]
    if not runs:
        return None
    return sorted(runs, key=lambda item: (str(item.get("started_at") or ""), int(item.get("id") or 0)))[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--check-name", required=True)
    parser.add_argument("--token")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    repo = urllib.parse.quote(args.repository, safe="/")
    sha = urllib.parse.quote(args.sha, safe="")
    url = f"{API}/repos/{repo}/commits/{sha}/check-runs"
    last_state = "missing"
    for attempt in range(1, args.attempts + 1):
        try:
            payload = request_json(url, args.token)
            check = latest_check(payload, args.check_name)
            if check is None:
                state = "missing"
            else:
                status = str(check.get("status") or "missing")
                conclusion = str(check.get("conclusion") or "pending")
                state = f"{status}:{conclusion}"
            last_state = state
            print(f"Governed merge gate [{attempt}/{args.attempts}]: {state}", flush=True)
            if state == "completed:success":
                return 0
            if state.startswith("completed:") and state != "completed:success":
                print(f"PentaRelease HOLD: governed merge gate did not pass ({state}).", flush=True)
                return 44
        except ReadbackError as exc:
            last_state = f"read-error:{exc}"
            print(f"Governed merge gate [{attempt}/{args.attempts}]: {last_state}", flush=True)
        if attempt < args.attempts:
            time.sleep(max(1, args.interval))
    print(f"PentaRelease HOLD: exact-SHA governed gate readback not established ({last_state}).", flush=True)
    return 45


if __name__ == "__main__":
    raise SystemExit(main())
