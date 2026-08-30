#!/usr/bin/env python3
"""Trusted pull_request_target adapter for collision governance v2.

This adapter preserves the read-only/fail-closed collision engine while avoiding
an unnecessary `/commits/{branch}` dependency in the trusted PR path. Both the
start and end main-branch fences are independently read from GitHub's live Git
ref endpoint. The webhook PR `base.sha` is retained only as audit context because
it can represent historical PR ancestry rather than the current branch head.

GitHub may also return HTTP 403 for primary/secondary rate limits. Those cases
receive bounded retry/backoff. Permission/authentication 403s remain terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

import governed_collision_agent_v2 as agent


MAX_HTTP_ATTEMPTS = 5
MAX_RATE_LIMIT_SLEEP_SECONDS = 30


def _header(headers: Mapping[str, str] | Any, name: str) -> str:
    try:
        value = headers.get(name)
    except AttributeError:
        return ""
    return str(value or "")


def _rate_limited_403(exc: urllib.error.HTTPError, body: str) -> bool:
    if exc.code != 403:
        return False
    headers = exc.headers or {}
    remaining = _header(headers, "X-RateLimit-Remaining")
    retry_after = _header(headers, "Retry-After")
    message = body.lower()
    return (
        remaining == "0"
        or bool(retry_after)
        or "rate limit" in message
        or "secondary rate" in message
        or "abuse detection" in message
    )


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> int:
    retry_after = _header(exc.headers or {}, "Retry-After")
    try:
        requested = int(float(retry_after)) if retry_after else 0
    except ValueError:
        requested = 0
    exponential = 2**attempt
    return min(MAX_RATE_LIMIT_SLEEP_SECONDS, max(1, requested, exponential))


class TrustedCandidateClient(agent.GitHubClient):
    """GitHub client with live Git-ref fencing and bounded 403 rate-limit retry."""

    def __init__(
        self,
        repository: str,
        token: str | None,
        *,
        event_base_sha: str,
        candidate: int,
    ) -> None:
        super().__init__(repository, token)
        if not event_base_sha:
            raise agent.GitHubReadError("trusted_event_base_sha_required")
        self.event_base_sha = event_base_sha
        self.candidate = candidate

    def live_branch_sha(self, branch: str) -> str:
        encoded_branch = urllib.parse.quote(branch, safe="")
        data = self.get(f"/git/ref/heads/{encoded_branch}")
        try:
            object_record = data["object"]
            if str(object_record.get("type")) != "commit":
                raise agent.GitHubReadError("trusted_live_ref_not_commit")
            sha = str(object_record["sha"])
        except (KeyError, TypeError, AttributeError) as exc:
            raise agent.GitHubReadError("trusted_live_ref_sha_missing") from exc
        if not sha:
            raise agent.GitHubReadError("trusted_live_ref_sha_empty")
        return sha

    def main_sha(self, branch: str) -> str:
        return self.live_branch_sha(branch)

    def _request(self, url: str) -> tuple[Any, Mapping[str, str]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "crownthrive-collision-agent-v2-trusted",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        last_error = "unknown"
        for attempt in range(MAX_HTTP_ATTEMPTS):
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    return body, response.headers
            except urllib.error.HTTPError as exc:
                try:
                    body_text = exc.read().decode("utf-8", errors="replace")
                except OSError:
                    body_text = ""
                last_error = f"HTTP {exc.code}: {exc.reason}"
                retryable = exc.code in {429, 502, 503, 504} or _rate_limited_403(exc, body_text)
                if not retryable or attempt >= MAX_HTTP_ATTEMPTS - 1:
                    break
                time.sleep(_retry_delay(exc, attempt))
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = str(exc)
                if attempt >= MAX_HTTP_ATTEMPTS - 1:
                    break
                time.sleep(min(MAX_RATE_LIMIT_SLEEP_SECONDS, 2**attempt))
            except json.JSONDecodeError as exc:
                raise agent.GitHubReadError(f"github_invalid_json:{url}:{exc}") from exc

        raise agent.GitHubReadError(f"github_read_failed:{url}:{last_error}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--candidate", type=int, required=True)
    parser.add_argument("--event-base-sha", required=True)
    parser.add_argument("--event-action", default=os.environ.get("GITHUB_EVENT_ACTION"))
    parser.add_argument("--output", default="collision-governance-v2-report.json")
    parser.add_argument("--fail-on-severity", type=int, default=2)
    args = parser.parse_args(argv)

    if not args.repository:
        parser.error("--repository or GITHUB_REPOSITORY is required")

    try:
        client = TrustedCandidateClient(
            args.repository,
            args.token,
            event_base_sha=args.event_base_sha,
            candidate=args.candidate,
        )
        report = agent.analyze_snapshot(
            client,
            branch=args.branch,
            candidate=args.candidate,
            event_action=args.event_action,
        )
        report["trusted_event_base_sha"] = args.event_base_sha
        report["trusted_base_fence_source"] = "git_ref_live_branch_sha"
        report["trusted_end_fence_source"] = "git_ref_live_branch_sha"
        agent.write_report(report, args.output)
        decision = report.get("decision")
        if isinstance(decision, Mapping) and int(decision.get("max_severity", 0)) >= args.fail_on_severity:
            return 2
        return 0
    except (agent.ContractError, agent.GitHubReadError, KeyError, TypeError, ValueError, OSError) as exc:
        failure = {
            "schema_version": agent.SCHEMA_VERSION,
            "disposition": "HOLD",
            "reason_code": "COLLISION_OBSERVER_FAILED_CLOSED",
            "error": str(exc),
            "merge_authority": False,
            "D3_auto": False,
        }
        agent.write_report(failure, args.output)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
