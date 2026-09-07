#!/usr/bin/env python3
"""Consolidated trusted collision adapter.

This module composes the current-gold scoping from the current repair lane with
bounded authenticated GraphQL PR/file snapshots from the stale unique GraphQL
repair. It preserves conservative REST fallback semantics for pagination,
renames, semantic reads, missing GraphQL data, provider errors and all other
cases where the batched snapshot cannot prove an exact equivalent read.

It is read-only and fail-closed. GraphQL metadata does not create authority,
merge permission, certification, provider-write capability, or D3 effect.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

import governed_collision_agent_v2 as agent
import governed_collision_agent_v2_trusted as base

MAX_GRAPHQL_REQUESTS = 20
GRAPHQL_PULLS_PAGE_SIZE = 50
GRAPHQL_FILES_PAGE_SIZE = 100
GRAPHQL_URL = "https://api.github.com/graphql"


class ConsolidatedTrustedCandidateClient(base.TrustedCandidateClient):
    """Current-gold scope plus bounded GraphQL snapshot and exact REST fallback."""

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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.graphql_requests = 0
        self.graphql_snapshot_reads = 0
        self.graphql_snapshot_mode = False
        self.graphql_last_error: str | None = None
        self._snapshot_files: dict[int, list[agent.ChangedFile]] = {}
        self._snapshot_rest_file_numbers: set[int] = set()

    def transport_evidence(self) -> dict[str, Any]:
        evidence = super().transport_evidence()
        evidence.update(
            {
                "graphql_requests": self.graphql_requests,
                "graphql_request_budget": MAX_GRAPHQL_REQUESTS,
                "graphql_snapshot_reads": self.graphql_snapshot_reads,
                "graphql_snapshot_mode": self.graphql_snapshot_mode,
                "graphql_last_error": self.graphql_last_error,
                "graphql_file_value_digest_mode": "unavailable_fail_conservative",
                "consolidated_scope": "graphql_snapshot_then_current_gold_partition",
            }
        )
        return evidence

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
            "User-Agent": "crownthrive-collision-agent-v2-trusted-consolidated",
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
            raise base.ProviderHTTPError(
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
        if body.get("errors"):
            compact = " ".join(json.dumps(body["errors"], sort_keys=True).split())[:480]
            raise agent.GitHubReadError(f"graphql_response_errors:{compact}")
        return body

    def _graphql_request(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(base.MAX_HTTP_ATTEMPTS):
            try:
                return self._graphql_once(query, variables)
            except base.ProviderHTTPError as exc:
                last_error = exc
                retryable = exc.status in {429, 502, 503, 504} or base._rate_limited(
                    exc.status, exc.headers, exc.body
                )
                if not retryable or attempt >= base.MAX_HTTP_ATTEMPTS - 1:
                    raise agent.GitHubReadError(
                        f"graphql_provider_read_failed:{exc}"
                    ) from exc
                time.sleep(base._retry_delay_headers(exc.headers, attempt))
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
    ) -> tuple[list[dict[str, Any]], dict[int, list[agent.ChangedFile]], set[int]]:
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
                    raise agent.GitHubReadError(f"graphql_pull_sha_invalid:{number}")
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

    def _current_gold_partition(self, pulls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        current_main = self.live_branch_sha(self.gold_lane_branch)
        eligible: list[dict[str, Any]] = []
        stale_count = 0
        for pull in pulls:
            try:
                number = int(pull["number"])
                base_sha = str(pull["base"]["sha"])
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise agent.GitHubReadError("trusted_pull_scope_metadata_missing") from exc
            if not base_sha:
                raise agent.GitHubReadError("trusted_pull_base_sha_empty")
            if number == self.candidate or base_sha == current_main:
                eligible.append(pull)
            else:
                stale_count += 1
        self.gold_lane_main_sha = current_main
        self.observed_open_pull_count = len(pulls)
        self.gold_lane_open_pull_count = len(eligible)
        self.stale_base_open_pull_count = stale_count
        return eligible

    def open_pulls(self) -> list[dict[str, Any]]:
        if self.token:
            try:
                pulls, files_by_pr, rest_file_numbers = self._load_graphql_open_pulls()
                self._snapshot_files = files_by_pr
                self._snapshot_rest_file_numbers = rest_file_numbers
                self.graphql_snapshot_reads += 1
                self.graphql_snapshot_mode = True
                self.graphql_last_error = None
                return self._current_gold_partition(pulls)
            except agent.GitHubReadError as exc:
                self.graphql_snapshot_mode = False
                self.graphql_last_error = base._body_excerpt(str(exc))
                self._snapshot_files = {}
                self._snapshot_rest_file_numbers = set()
        return super().open_pulls()

    def files(self, number: int) -> list[agent.ChangedFile]:
        if number in self._snapshot_files and number not in self._snapshot_rest_file_numbers:
            return list(self._snapshot_files[number])
        return super().files(number)


def main(argv: Sequence[str] | None = None) -> int:
    original = base.TrustedCandidateClient
    base.TrustedCandidateClient = ConsolidatedTrustedCandidateClient
    try:
        return base.main(argv)
    finally:
        base.TrustedCandidateClient = original


if __name__ == "__main__":
    raise SystemExit(main())
