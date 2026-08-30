#!/usr/bin/env python3
"""Trusted pull_request_target adapter for collision governance v2.

This adapter preserves the read-only/fail-closed collision engine while avoiding
an unnecessary `/commits/{branch}` dependency in the trusted PR path. Both the
start and end main-branch fences are independently read from GitHub's live Git
ref endpoint. The webhook PR `base.sha` is retained only as audit context because
it can represent historical PR ancestry rather than the current branch head.

GitHub Actions installation tokens can be temporarily unavailable even while the
same public repository resources remain readable through GitHub's public GET
surface. Authenticated reads are attempted first. A 403/429 may degrade to a
bounded public read only when that exact provider resource succeeds publicly.
No writes use this transport and both transports remain fail-closed.
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
MAX_PUBLIC_FALLBACK_REQUESTS = 50


def _header(headers: Mapping[str, str] | Any, name: str) -> str:
    try:
        value = headers.get(name)
        if value is not None:
            return str(value)
        value = headers.get(name.lower())
        if value is not None:
            return str(value)
        for key, candidate in headers.items():
            if str(key).lower() == name.lower():
                return str(candidate or "")
    except (AttributeError, TypeError):
        return ""
    return ""


def _rate_limited(status: int, headers: Mapping[str, str] | Any, body: str) -> bool:
    remaining = _header(headers, "X-RateLimit-Remaining")
    retry_after = _header(headers, "Retry-After")
    message = body.lower()
    return (
        status == 429
        or (
            status == 403
            and (
                remaining == "0"
                or bool(retry_after)
                or "rate limit" in message
                or "secondary rate" in message
                or "abuse detection" in message
            )
        )
    )


def _rate_limited_403(exc: urllib.error.HTTPError, body: str) -> bool:
    return _rate_limited(exc.code, exc.headers or {}, body)


def _retry_delay_headers(headers: Mapping[str, str] | Any, attempt: int) -> int:
    retry_after = _header(headers, "Retry-After")
    try:
        requested = int(float(retry_after)) if retry_after else 0
    except ValueError:
        requested = 0
    exponential = 2**attempt
    return min(MAX_RATE_LIMIT_SLEEP_SECONDS, max(1, requested, exponential))


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> int:
    return _retry_delay_headers(exc.headers or {}, attempt)


def _body_excerpt(body: str) -> str:
    return " ".join(body.replace("\x00", "").split())[:240]


class ProviderHTTPError(RuntimeError):
    def __init__(
        self,
        *,
        url: str,
        status: int,
        reason: str,
        headers: Mapping[str, str] | Any,
        body: str,
        transport: str,
    ) -> None:
        self.url = url
        self.status = status
        self.reason = reason
        self.headers = headers or {}
        self.body = body
        self.transport = transport
        request_id = _header(self.headers, "X-GitHub-Request-Id")
        remaining = _header(self.headers, "X-RateLimit-Remaining")
        details = [f"{transport}:HTTP {status}: {reason}"]
        if request_id:
            details.append(f"request_id={request_id}")
        if remaining:
            details.append(f"remaining={remaining}")
        excerpt = _body_excerpt(body)
        if excerpt:
            details.append(f"body={excerpt}")
        super().__init__(";".join(details))


class TrustedCandidateClient(agent.GitHubClient):
    """GitHub client with live-ref fencing and bounded public GET degradation."""

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
        self.authenticated_requests = 0
        self.public_fallback_requests = 0
        self.public_read_mode = False
        self.last_transport = "none"

    def transport_evidence(self) -> dict[str, Any]:
        return {
            "authenticated_requests": self.authenticated_requests,
            "public_fallback_requests": self.public_fallback_requests,
            "public_read_mode": self.public_read_mode,
            "public_request_budget": MAX_PUBLIC_FALLBACK_REQUESTS,
            "last_transport": self.last_transport,
        }

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

    def _request_once(
        self,
        url: str,
        *,
        token: str | None,
        transport: str,
    ) -> tuple[Any, Mapping[str, str]]:
        if transport == "public-fallback":
            if self.public_fallback_requests >= MAX_PUBLIC_FALLBACK_REQUESTS:
                raise agent.GitHubReadError(
                    f"public_fallback_request_budget_exceeded:{MAX_PUBLIC_FALLBACK_REQUESTS}"
                )
            self.public_fallback_requests += 1
        else:
            self.authenticated_requests += 1

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "crownthrive-collision-agent-v2-trusted",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
                self.last_transport = transport
                return body, response.headers
        except urllib.error.HTTPError as exc:
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except OSError:
                body_text = ""
            raise ProviderHTTPError(
                url=url,
                status=exc.code,
                reason=str(exc.reason),
                headers=exc.headers or {},
                body=body_text,
                transport=transport,
            ) from exc
        except json.JSONDecodeError as exc:
            raise agent.GitHubReadError(f"github_invalid_json:{url}:{exc}") from exc

    def _request_transport(
        self,
        url: str,
        *,
        token: str | None,
        transport: str,
    ) -> tuple[Any, Mapping[str, str]]:
        last_error: Exception | None = None
        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                return self._request_once(url, token=token, transport=transport)
            except ProviderHTTPError as exc:
                last_error = exc
                retryable = exc.status in {429, 502, 503, 504} or _rate_limited(
                    exc.status,
                    exc.headers,
                    exc.body,
                )
                if not retryable or attempt >= MAX_HTTP_ATTEMPTS - 1:
                    raise
                time.sleep(_retry_delay_headers(exc.headers, attempt))
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= MAX_HTTP_ATTEMPTS - 1:
                    raise
                time.sleep(min(MAX_RATE_LIMIT_SLEEP_SECONDS, 2**attempt))
        raise agent.GitHubReadError(f"github_transport_retry_exhausted:{url}:{last_error}")

    def _request(self, url: str) -> tuple[Any, Mapping[str, str]]:
        if not url.startswith(self.base + "/"):
            raise agent.GitHubReadError("trusted_public_fallback_repo_scope_required")

        if self.public_read_mode or not self.token:
            try:
                return self._request_transport(
                    url,
                    token=None,
                    transport="public-fallback",
                )
            except (ProviderHTTPError, urllib.error.URLError, TimeoutError) as exc:
                raise agent.GitHubReadError(f"github_public_read_failed:{url}:{exc}") from exc

        try:
            return self._request_transport(
                url,
                token=self.token,
                transport="authenticated",
            )
        except ProviderHTTPError as auth_error:
            if auth_error.status not in {403, 429}:
                raise agent.GitHubReadError(f"github_read_failed:{url}:{auth_error}") from auth_error

            try:
                result = self._request_transport(
                    url,
                    token=None,
                    transport="public-fallback",
                )
            except (ProviderHTTPError, urllib.error.URLError, TimeoutError, agent.GitHubReadError) as public_error:
                raise agent.GitHubReadError(
                    f"github_read_failed:{url}:authenticated={auth_error};public={public_error}"
                ) from public_error

            # The exact provider resource was independently readable without the
            # installation token. Remaining reads stay on that bounded public
            # surface to avoid repeated pressure on a degraded auth transport.
            self.public_read_mode = True
            return result
        except (urllib.error.URLError, TimeoutError) as exc:
            raise agent.GitHubReadError(f"github_read_failed:{url}:{exc}") from exc


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

    client: TrustedCandidateClient | None = None
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
        report["trusted_provider_transport"] = client.transport_evidence()
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
        if client is not None:
            failure["trusted_provider_transport"] = client.transport_evidence()
        agent.write_report(failure, args.output)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
