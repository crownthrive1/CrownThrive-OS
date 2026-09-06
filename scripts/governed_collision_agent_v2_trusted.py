#!/usr/bin/env python3
"""Trusted pull_request_target adapter for collision governance v2.

This adapter preserves the read-only/fail-closed collision engine while avoiding
an unnecessary `/commits/{branch}` dependency in the trusted PR path. Both the
start and end main-branch fences are independently read from GitHub's live Git
ref endpoint. The webhook PR `base.sha` is retained only as audit context because
it can represent historical PR ancestry rather than the current branch head.

GitHub Actions installation tokens can be temporarily unavailable even while the
same public repository resources remain readable through GitHub's public GET
surface. Every exact provider read prefers the authenticated transport. A
403/429 may degrade that exact read to a bounded public GET, but later reads
retry authenticated transport rather than entering a sticky public-only mode.
No writes use this transport and both transports remain fail-closed.

The trusted PR path also batches the open-PR/file snapshot through GitHub GraphQL
before the REST fallback path. This prevents a large open PR cohort from burning
the installation-token REST budget one `pulls/{number}/files` request at a time.
GraphQL supplies paths/change types only; when a PR needs pagination or rename
lineage, the client deliberately falls back to the original REST file reader.
Missing blob digests on the batched path are conservative: they can remove an
inert byte-identical optimization, but can never convert a collision into PASS.
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
MAX_GRAPHQL_REQUESTS = 20
GRAPHQL_PULLS_PAGE_SIZE = 50
GRAPHQL_FILES_PAGE_SIZE = 100
GRAPHQL_URL = "https://api.github.com/graphql"


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
    """GitHub client with live-ref fencing and bounded provider degradation."""

    _OPEN_PULLS_QUERY = """
query TrustedCollisionSnapshot(
  $owner: String!,
  $name: String!,
  $cursor: String,
  $pullPage: Int!,
  $filePage: Int!
) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: $pullPage,
      after: $cursor,
      states: OPEN,
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        headRefOid
        baseRefOid
        body
        isDraft
        updatedAt
        files(first: $filePage) {
          pageInfo { hasNextPage endCursor }
          nodes { path changeType }
        }
      }
    }
  }
}
"""

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
        self.graphql_requests = 0
        self.graphql_snapshot_reads = 0
        self.graphql_snapshot_mode = False
        self.graphql_last_error: str | None = None
        self._snapshot_files: dict[int, list[agent.ChangedFile]] = {}
        self._snapshot_rest_file_numbers: set[int] = set()
        # Evidence flag: at least one exact read used the public fallback. It is
        # deliberately not a transport-mode latch.
        self.public_read_mode = False
        self.last_transport = "none"

    def transport_evidence(self) -> dict[str, Any]:
        return {
            "authenticated_requests": self.authenticated_requests,
            "public_fallback_requests": self.public_fallback_requests,
            "public_read_mode": self.public_read_mode,
            "public_request_budget": MAX_PUBLIC_FALLBACK_REQUESTS,
            "graphql_requests": self.graphql_requests,
            "graphql_request_budget": MAX_GRAPHQL_REQUESTS,
            "graphql_snapshot_reads": self.graphql_snapshot_reads,
            "graphql_snapshot_mode": self.graphql_snapshot_mode,
            "graphql_last_error": self.graphql_last_error,
            "graphql_file_value_digest_mode": "unavailable_fail_conservative",
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
                # Authenticated 403/429 is the exact handoff signal for the
                # bounded public GET fallback. Do not spend five authenticated
                # retries before exercising that fail-closed alternate read.
                if transport == "authenticated" and exc.status in {403, 429}:
                    raise
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

        if not self.token:
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

            # Record that public degradation occurred, but do not latch future
            # requests into public-only mode. The next exact read retries the
            # authenticated provider surface and can recover immediately.
            self.public_read_mode = True
            return result
        except (urllib.error.URLError, TimeoutError) as exc:
            raise agent.GitHubReadError(f"github_read_failed:{url}:{exc}") from exc

    def _graphql_once(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise agent.GitHubReadError("graphql_authenticated_token_required")
        if self.graphql_requests >= MAX_GRAPHQL_REQUESTS:
            raise agent.GitHubReadError(
                f"graphql_request_budget_exceeded:{MAX_GRAPHQL_REQUESTS}"
            )
        self.graphql_requests += 1
        payload = json.dumps(
            {"query": query, "variables": dict(variables)},
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "crownthrive-collision-agent-v2-trusted-graphql",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        request = urllib.request.Request(
            GRAPHQL_URL,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
                self.last_transport = "graphql-authenticated"
        except urllib.error.HTTPError as exc:
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except OSError:
                body_text = ""
            raise ProviderHTTPError(
                url=GRAPHQL_URL,
                status=exc.code,
                reason=str(exc.reason),
                headers=exc.headers or {},
                body=body_text,
                transport="graphql-authenticated",
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise agent.GitHubReadError(f"graphql_read_failed:{exc}") from exc
        except json.JSONDecodeError as exc:
            raise agent.GitHubReadError(f"graphql_invalid_json:{exc}") from exc
        if not isinstance(body, dict):
            raise agent.GitHubReadError("graphql_object_response_required")
        errors = body.get("errors")
        if errors:
            compact = " ".join(json.dumps(errors, sort_keys=True).split())[:480]
            raise agent.GitHubReadError(f"graphql_response_errors:{compact}")
        return body

    def _graphql_request(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                return self._graphql_once(query, variables)
            except ProviderHTTPError as exc:
                last_error = exc
                retryable = exc.status in {429, 502, 503, 504} or _rate_limited(
                    exc.status,
                    exc.headers,
                    exc.body,
                )
                if not retryable or attempt >= MAX_HTTP_ATTEMPTS - 1:
                    raise agent.GitHubReadError(
                        f"graphql_provider_read_failed:{exc}"
                    ) from exc
                time.sleep(_retry_delay_headers(exc.headers, attempt))
            except agent.GitHubReadError:
                raise
        raise agent.GitHubReadError(f"graphql_retry_exhausted:{last_error}")

    @staticmethod
    def _graphql_change_access(change_type: str) -> str:
        return {
            "ADDED": "create",
            "DELETED": "retire",
            "RENAMED": "create",
        }.get(change_type.upper(), "mutate")

    def _load_graphql_open_pulls(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        dict[int, list[agent.ChangedFile]],
        set[int],
    ]:
        try:
            owner, name = self.repository.split("/", 1)
        except ValueError as exc:
            raise agent.GitHubReadError("graphql_repository_owner_name_required") from exc

        cursor: str | None = None
        pulls: list[dict[str, Any]] = []
        files_by_pr: dict[int, list[agent.ChangedFile]] = {}
        rest_file_numbers: set[int] = set()
        while True:
            body = self._graphql_request(
                self._OPEN_PULLS_QUERY,
                {
                    "owner": owner,
                    "name": name,
                    "cursor": cursor,
                    "pullPage": GRAPHQL_PULLS_PAGE_SIZE,
                    "filePage": GRAPHQL_FILES_PAGE_SIZE,
                },
            )
            try:
                connection = body["data"]["repository"]["pullRequests"]
                total_count = int(connection["totalCount"])
                nodes = connection.get("nodes") or []
                page_info = connection["pageInfo"]
            except (KeyError, TypeError, ValueError) as exc:
                raise agent.GitHubReadError("graphql_pull_snapshot_shape_invalid") from exc

            if total_count > agent.MAX_OPEN_PRS:
                raise agent.GitHubReadError(
                    f"bounded_snapshot_may_be_truncated:{agent.MAX_OPEN_PRS}"
                )
            if not isinstance(nodes, list):
                raise agent.GitHubReadError("graphql_pull_nodes_list_required")

            for node in nodes:
                if not isinstance(node, Mapping):
                    raise agent.GitHubReadError("graphql_pull_node_object_required")
                try:
                    number = int(node["number"])
                    head_sha = str(node["headRefOid"] or "")
                    base_sha = str(node["baseRefOid"] or "")
                    file_connection = node["files"]
                    file_nodes = file_connection.get("nodes") or []
                    file_page_info = file_connection["pageInfo"]
                except (KeyError, TypeError, ValueError) as exc:
                    raise agent.GitHubReadError("graphql_pull_node_shape_invalid") from exc
                if len(head_sha) != 40 or len(base_sha) != 40:
                    raise agent.GitHubReadError(
                        f"graphql_pull_sha_invalid:{number}"
                    )
                pulls.append(
                    {
                        "number": number,
                        "head": {"sha": head_sha},
                        "base": {"sha": base_sha},
                        "body": node.get("body"),
                        "draft": bool(node.get("isDraft", False)),
                        "updated_at": node.get("updatedAt"),
                    }
                )

                parsed_files: list[agent.ChangedFile] = []
                needs_rest = bool(file_page_info.get("hasNextPage"))
                if not isinstance(file_nodes, list):
                    raise agent.GitHubReadError("graphql_file_nodes_list_required")
                for file_node in file_nodes:
                    if not isinstance(file_node, Mapping) or not file_node.get("path"):
                        raise agent.GitHubReadError(
                            f"graphql_changed_file_shape_invalid:{number}"
                        )
                    change_type = str(file_node.get("changeType") or "MODIFIED")
                    if change_type.upper() == "RENAMED":
                        # Previous-path lineage is not exposed by this GraphQL
                        # node, so preserve exact semantics through REST.
                        needs_rest = True
                    parsed_files.append(
                        agent.ChangedFile(
                            path=str(file_node["path"]),
                            access=self._graphql_change_access(change_type),
                            value_digest=None,
                            previous_path=None,
                        )
                    )
                if not parsed_files:
                    # Preserve the existing fail-closed "no readable files"
                    # behavior rather than treating an empty node list as PASS.
                    needs_rest = True
                if needs_rest:
                    rest_file_numbers.add(number)
                else:
                    files_by_pr[number] = sorted(
                        set(parsed_files),
                        key=lambda item: (item.path, item.access, item.previous_path or ""),
                    )

            if not bool(page_info.get("hasNextPage")):
                break
            cursor = page_info.get("endCursor")
            if not cursor:
                raise agent.GitHubReadError("graphql_pull_cursor_missing")
            if len(pulls) >= agent.MAX_OPEN_PRS:
                raise agent.GitHubReadError(
                    f"bounded_snapshot_may_be_truncated:{agent.MAX_OPEN_PRS}"
                )

        if len(pulls) != len({int(item["number"]) for item in pulls}):
            raise agent.GitHubReadError("graphql_duplicate_pull_number")
        return pulls, files_by_pr, rest_file_numbers

    def open_pulls(self) -> list[dict[str, Any]]:
        if self.token:
            try:
                pulls, files_by_pr, rest_file_numbers = self._load_graphql_open_pulls()
                self._snapshot_files = files_by_pr
                self._snapshot_rest_file_numbers = rest_file_numbers
                self.graphql_snapshot_reads += 1
                self.graphql_snapshot_mode = True
                self.graphql_last_error = None
                return pulls
            except agent.GitHubReadError as exc:
                # One bounded alternate path: revert to the proven REST/public
                # reader. The outer adapter remains fail-closed if that path also
                # lacks enough provider capacity.
                self.graphql_snapshot_mode = False
                self.graphql_last_error = _body_excerpt(str(exc))

        self._snapshot_files = {}
        self._snapshot_rest_file_numbers = set()
        return super().open_pulls()

    def files(self, number: int) -> list[agent.ChangedFile]:
        if (
            number in self._snapshot_files
            and number not in self._snapshot_rest_file_numbers
        ):
            return list(self._snapshot_files[number])
        return super().files(number)


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
