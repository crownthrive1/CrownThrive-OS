#!/usr/bin/env python3
"""PentaTagger™ GitHub Native v3.

PentaTagger owns semantic labels and provider readback receipts. It never merges
or closes. PentaPR owns lifecycle classification; PentaMerge and PentaCloser
own terminal writes.

v3 hardens the transport against installation-quota exhaustion, eliminates
unnecessary API calls by consuming trusted GitHub event snapshots, bounds sweep
work, and emits an explicit deferred receipt instead of losing events.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import email.utils
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from penta_github_labels import (
    DISPOSITION_LABELS,
    DISPOSITION_STAGE,
    ENTITY_PREFIXES,
    LANE_PREFIXES,
    RISK_PREFIXES,
    STAGE_PREFIXES,
    TERMINAL_PREFIXES,
    add_labels,
    read_labels,
    remove_label,
)

API = "https://api.github.com"
COMMENT_MARKER = "<!-- penta-github-tagger:"
MAX_PAGES = 10
EXIT_DEFERRED = 75
TRANSIENT_HTTP = frozenset({429, 500, 502, 503, 504})
SEMANTIC_PR_ACTIONS = frozenset({"opened", "reopened", "synchronize", "edited"})
LIFECYCLE_PREFIXES = (*STAGE_PREFIXES, *TERMINAL_PREFIXES)
MANAGED_PREFIXES = (
    *ENTITY_PREFIXES,
    *LANE_PREFIXES,
    *RISK_PREFIXES,
    *LIFECYCLE_PREFIXES,
)

LANE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "docs": (
        "docs", "documentation", "mintlify", "pentadocs", "readme", "guide",
        "handbook", "sop", "policy", "constitution", "registry",
    ),
    "workflow": (
        "workflow", "github actions", "runner", "ci", "automation", "cron",
        "pipeline", "pull request", "issue", "label", "tagger", "closer",
    ),
    "database": (
        "database", "supabase", "postgres", "sql", "migration", "schema",
        "table", "rls", "row level security", "function", "trigger",
    ),
    "provider": (
        "provider", "adapter", "integration", "api", "webhook", "oauth",
        "mailgun", "resend", "stripe", "vercel", "cloudflare", "mintlify",
    ),
    "security": (
        "security", "credential", "secret", "token", "auth", "oauth", "rls",
        "policy", "incident", "vulnerability", "attestation", "provenance",
    ),
    "commerce": (
        "commerce", "checkout", "payment", "stripe", "price", "product",
        "license", "economic", "money", "subscription", "invoice", "wallet",
    ),
    "media": (
        "media", "music", "video", "television", "tv", "radio", "audio",
        "publishing", "book", "sermon", "kjv", "stream", "riverside",
    ),
    "observability": (
        "observability", "logger", "logging", "error", "report", "alert",
        "notification", "metric", "trace", "telemetry", "status", "monitor",
    ),
}

HIGH_RISK_TERMS = (
    "production", "deploy", "release", "security", "credential", "secret",
    "token", "auth", "oauth", "rls", "payment", "checkout", "stripe",
    "money", "delete", "close", "merge", "migration", "schema", "database",
    "governance", "rights", "license", "webhook", "provider",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _header(headers: Mapping[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    return str(value) if value is not None else None


def _parse_int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_retry_after(value: str | None, now: float) -> float | None:
    if not value:
        return None
    seconds = _parse_int(value)
    if seconds is not None:
        return max(0.0, float(seconds))
    try:
        when = email.utils.parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return max(0.0, when.timestamp() - now)
    except (TypeError, ValueError, OverflowError):
        return None


def _is_rate_limit(status: int, body: str, headers: Mapping[str, str] | None) -> bool:
    text = body.lower()
    remaining = _header(headers, "X-RateLimit-Remaining")
    return (
        status == 429
        or (
            status == 403
            and (
                remaining == "0"
                or "rate limit" in text
                or "secondary rate" in text
                or "abuse detection" in text
            )
        )
    )


@dataclass(frozen=True)
class RateLimitEvidence:
    status: int
    method: str
    path: str
    remaining: int | None
    reset_epoch: int | None
    retry_after_seconds: float | None
    resource: str | None
    request_id: str | None
    body_excerpt: str

    @property
    def reset_at(self) -> str | None:
        if self.reset_epoch is None:
            return None
        return (
            dt.datetime.fromtimestamp(self.reset_epoch, tz=dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )


class GitHubRequestError(RuntimeError):
    """Structured GitHub transport error."""

    def __init__(
        self,
        *,
        method: str,
        path: str,
        status: int,
        body: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.method = method
        self.path = path
        self.status = status
        self.body = body
        self.headers = headers or {}
        super().__init__(f"{method} {path} -> {status}: {body[:500]}")


class RateLimitDeferred(GitHubRequestError):
    """The provider quota cannot recover inside the bounded workflow window."""

    def __init__(self, error: GitHubRequestError, *, now: float) -> None:
        retry_after = _parse_retry_after(_header(error.headers, "Retry-After"), now)
        reset_epoch = _parse_int(_header(error.headers, "X-RateLimit-Reset"))
        if retry_after is None and reset_epoch is not None:
            retry_after = max(0.0, float(reset_epoch) - now)
        self.evidence = RateLimitEvidence(
            status=error.status,
            method=error.method,
            path=error.path,
            remaining=_parse_int(_header(error.headers, "X-RateLimit-Remaining")),
            reset_epoch=reset_epoch,
            retry_after_seconds=retry_after,
            resource=_header(error.headers, "X-RateLimit-Resource"),
            request_id=_header(error.headers, "X-GitHub-Request-Id"),
            body_excerpt=error.body[:500],
        )
        super().__init__(
            method=error.method,
            path=error.path,
            status=error.status,
            body=error.body,
            headers=error.headers,
        )


class GH:
    """PentaGitHubQuotaShield transport.

    Authenticated requests remain authoritative for writes. Safe GET requests
    may fall back to GitHub's public repository read surface when the
    installation bucket is exhausted. Writes never fall back to anonymous
    transport and instead emit RateLimitDeferred.
    """

    def __init__(
        self,
        repo: str,
        token: str | None = None,
        *,
        public_read_fallback: bool = True,
        max_attempts: int = 4,
        inline_wait_seconds: float | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        randomizer: Callable[[], float] = random.random,
    ) -> None:
        if "/" not in repo:
            raise ValueError("repo_must_be_owner_slash_name")
        self.repo = repo
        self.token = token or os.environ.get("PENTA_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            raise RuntimeError("github_token_required")
        self.public_read_fallback = public_read_fallback
        self.max_attempts = max(1, max_attempts)
        if inline_wait_seconds is None:
            inline_wait_seconds = float(os.getenv("PENTA_GITHUB_INLINE_WAIT_SECONDS", "20"))
        self.inline_wait_seconds = max(0.0, inline_wait_seconds)
        self._sleep = sleeper
        self._clock = clock
        self._random = randomizer
        self.request_count = 0
        self.authenticated_request_count = 0
        self.public_request_count = 0
        self.last_transport = "none"
        self.last_rate_limit: RateLimitEvidence | None = None

    def _request_once(
        self,
        method: str,
        path: str,
        body: Any | None,
        *,
        token: str | None,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PentaTagger/3.0",
        }
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers=headers,
        )
        self.request_count += 1
        if token:
            self.authenticated_request_count += 1
            transport = "authenticated"
        else:
            self.public_request_count += 1
            transport = "public-fallback"
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                self.last_transport = transport
                if not raw:
                    return None
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"github_invalid_json:{method}:{path}") from exc
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            raise GitHubRequestError(
                method=method,
                path=path,
                status=exc.code,
                body=raw,
                headers=exc.headers,
            ) from exc

    def _delay_for(self, error: GitHubRequestError, attempt: int) -> float:
        now = self._clock()
        retry_after = _parse_retry_after(_header(error.headers, "Retry-After"), now)
        if retry_after is None:
            reset_epoch = _parse_int(_header(error.headers, "X-RateLimit-Reset"))
            if reset_epoch is not None:
                retry_after = max(0.0, float(reset_epoch) - now)
        if retry_after is None:
            retry_after = min(float(2**attempt), 8.0)
        # Bounded jitter prevents synchronized retries without obscuring reset evidence.
        return retry_after + min(1.0, self._random())

    def _handle_retryable(self, error: GitHubRequestError, attempt: int) -> bool:
        rate_limited = _is_rate_limit(error.status, error.body, error.headers)
        if rate_limited:
            deferred = RateLimitDeferred(error, now=self._clock())
            self.last_rate_limit = deferred.evidence
            delay = self._delay_for(error, attempt)
            if attempt + 1 < self.max_attempts and delay <= self.inline_wait_seconds:
                self._sleep(delay)
                return True
            raise deferred
        if error.status in TRANSIENT_HTTP and attempt + 1 < self.max_attempts:
            delay = min(float(2**attempt), 8.0) + min(1.0, self._random())
            if delay <= self.inline_wait_seconds:
                self._sleep(delay)
                return True
        return False

    def req(self, method: str, path: str, body: Any | None = None) -> Any:
        method = method.upper()
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                return self._request_once(method, path, body, token=self.token)
            except GitHubRequestError as auth_error:
                last_error = auth_error
                auth_rate_limited = _is_rate_limit(
                    auth_error.status,
                    auth_error.body,
                    auth_error.headers,
                )
                if method == "GET" and self.public_read_fallback and auth_rate_limited:
                    try:
                        return self._request_once(method, path, body, token=None)
                    except GitHubRequestError as public_error:
                        last_error = public_error
                        if self._handle_retryable(public_error, attempt):
                            continue
                        # Public 401/403/404 is not authoritative for a private repo;
                        # retain authenticated rate-limit evidence for deferral.
                        if public_error.status in {401, 403, 404}:
                            if self._handle_retryable(auth_error, attempt):
                                continue
                        raise
                    except (urllib.error.URLError, TimeoutError, OSError) as exc:
                        last_error = exc
                        if attempt + 1 < self.max_attempts:
                            delay = min(float(2**attempt), 8.0)
                            if delay <= self.inline_wait_seconds:
                                self._sleep(delay)
                                continue
                        raise RuntimeError(f"GET {path} public fallback failed: {exc}") from exc
                if self._handle_retryable(auth_error, attempt):
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt + 1 < self.max_attempts:
                    delay = min(float(2**attempt), 8.0) + min(1.0, self._random())
                    if delay <= self.inline_wait_seconds:
                        self._sleep(delay)
                        continue
                raise RuntimeError(f"{method} {path} transport failed: {exc}") from exc
        raise RuntimeError(f"{method} {path} retry_exhausted:{last_error}")

    def get(self, path: str) -> Any:
        return self.req("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def delete(self, path: str) -> Any:
        return self.req("DELETE", path)

    def paginate(
        self,
        path: str,
        *,
        list_key: str | None = None,
        max_pages: int = MAX_PAGES,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            payload = self.get(f"{path}{separator}page={page}")
            batch = payload.get(list_key, []) if list_key else payload
            if not isinstance(batch, list):
                raise RuntimeError(f"pagination_expected_list:{path}")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items


@dataclass(frozen=True)
class Entity:
    number: int
    kind: str
    title: str
    body: str
    state: str
    merged: bool
    draft: bool
    labels: set[str]
    files: tuple[str, ...]
    html_url: str
    source: str = "api"


def _contains_keyword(text: str, keyword: str) -> bool:
    if len(keyword) <= 3 and keyword.isalnum():
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def classify_lanes(title: str, body: str, files: tuple[str, ...]) -> list[str]:
    text = f"{title}\n{body}".lower()
    scores = {lane: 0 for lane in LANE_KEYWORDS}

    for lane, keywords in LANE_KEYWORDS.items():
        for keyword in keywords:
            if _contains_keyword(text, keyword):
                scores[lane] += 1

    for raw_path in files:
        path = raw_path.lower()
        suffix = Path(path).suffix
        if path.startswith(("docs/", "documentation/")) or suffix in {".md", ".mdx", ".rst"}:
            scores["docs"] += 3
        if path.startswith(".github/workflows/") or "workflow" in path or "actions" in path:
            scores["workflow"] += 4
        if path.startswith("supabase/") or "migration" in path or suffix == ".sql":
            scores["database"] += 4
        if any(part in path for part in ("provider", "adapter", "integration", "webhook", "oauth")):
            scores["provider"] += 3
        if any(part in path for part in ("security", "credential", "secret", "auth", "rls", "policy")):
            scores["security"] += 3
        if any(part in path for part in ("commerce", "checkout", "payment", "stripe", "product", "license", "wallet")):
            scores["commerce"] += 3
        if any(part in path for part in ("media", "music", "video", "radio", "television", "publishing", "book", "sermon")):
            scores["media"] += 3
        if any(part in path for part in ("observability", "logger", "error", "report", "alert", "metric", "trace")):
            scores["observability"] += 3

    selected = [
        lane
        for lane, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if score >= 2
    ][:4]
    return selected or ["general"]


def classify_risk(title: str, body: str, files: tuple[str, ...], lanes: list[str]) -> str:
    text = f"{title}\n{body}\n{' '.join(files)}".lower()
    if any(_contains_keyword(text, term) for term in HIGH_RISK_TERMS):
        return "d2"
    if {"security", "database", "provider", "commerce"}.intersection(lanes):
        return "d2"
    non_docs = [path for path in files if Path(path.lower()).suffix not in {".md", ".mdx", ".rst"}]
    if files and not non_docs and set(lanes).issubset({"docs", "general"}):
        return "d0"
    if {"workflow", "media", "observability"}.intersection(lanes) or non_docs:
        return "d1"
    return "d0"


def lifecycle_projection(entity: Entity) -> tuple[list[str], list[str]]:
    if entity.state == "closed":
        terminal = "penta:terminal:merged" if entity.merged else "penta:terminal:closed"
        return [], [terminal]
    if entity.kind == "issue":
        return ["penta:stage:open"], []
    for disposition, label in DISPOSITION_LABELS.items():
        if label in entity.labels:
            return [DISPOSITION_STAGE[disposition]], []
    if entity.draft:
        return ["penta:stage:nurture"], []
    return ["penta:stage:review"], []


def _labels_from_payload(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        str(item.get("name"))
        for item in value
        if isinstance(item, dict) and item.get("name")
    }


def load_event_payload(event_path: str | None) -> dict[str, Any]:
    if not event_path:
        return {}
    path = Path(event_path)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def entity_from_event_payload(payload: Mapping[str, Any]) -> Entity | None:
    pr = payload.get("pull_request")
    if isinstance(pr, dict):
        return Entity(
            number=int(pr["number"]),
            kind="pr",
            title=pr.get("title") or "",
            body=pr.get("body") or "",
            state=(pr.get("state") or "open").lower(),
            merged=bool(pr.get("merged")),
            draft=bool(pr.get("draft")),
            labels=_labels_from_payload(pr.get("labels")),
            files=(),
            html_url=pr.get("html_url") or "",
            source="event_payload",
        )
    issue = payload.get("issue")
    if isinstance(issue, dict):
        return Entity(
            number=int(issue["number"]),
            kind="issue",
            title=issue.get("title") or "",
            body=issue.get("body") or "",
            state=(issue.get("state") or "open").lower(),
            merged=False,
            draft=False,
            labels=_labels_from_payload(issue.get("labels")),
            files=(),
            html_url=issue.get("html_url") or "",
            source="event_payload",
        )
    return None


def target_from_event(event_path: str | None) -> int | None:
    entity = entity_from_event_payload(load_event_payload(event_path))
    return entity.number if entity else None


def fetch_pr_files(gh: GH, number: int) -> tuple[str, ...]:
    return tuple(
        item.get("filename", "")
        for item in gh.paginate(f"/repos/{gh.repo}/pulls/{number}/files?per_page=100")
        if item.get("filename")
    )


def fetch_entity(
    gh: GH,
    number: int,
    *,
    seed: Entity | None = None,
    refresh_files: bool = True,
) -> Entity:
    if seed is not None:
        if seed.number != number:
            raise ValueError("event_seed_number_mismatch")
        if seed.kind == "pr" and refresh_files:
            return dataclasses.replace(seed, files=fetch_pr_files(gh, number))
        return seed

    issue = gh.get(f"/repos/{gh.repo}/issues/{number}")
    labels = _labels_from_payload(issue.get("labels", []))
    if "pull_request" not in issue:
        return Entity(
            number=number,
            kind="issue",
            title=issue.get("title") or "",
            body=issue.get("body") or "",
            state=(issue.get("state") or "open").lower(),
            merged=False,
            draft=False,
            labels=labels,
            files=(),
            html_url=issue.get("html_url") or "",
            source="api",
        )

    pr = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    files = fetch_pr_files(gh, number) if refresh_files else ()
    return Entity(
        number=number,
        kind="pr",
        title=pr.get("title") or issue.get("title") or "",
        body=pr.get("body") or issue.get("body") or "",
        state=(pr.get("state") or issue.get("state") or "open").lower(),
        merged=bool(pr.get("merged")),
        draft=bool(pr.get("draft")),
        labels=labels,
        files=files,
        html_url=pr.get("html_url") or issue.get("html_url") or "",
        source="api",
    )


def _existing_lanes(labels: set[str]) -> list[str]:
    return sorted(
        label.removeprefix("penta:lane:")
        for label in labels
        if label.startswith("penta:lane:")
    )


def _existing_risk(labels: set[str]) -> str | None:
    candidates = sorted(
        label.removeprefix("penta:risk:")
        for label in labels
        if label.startswith("penta:risk:")
    )
    return candidates[0] if candidates else None


def classify_entity(entity: Entity, *, preserve_semantics: bool = False) -> tuple[list[str], str]:
    if preserve_semantics:
        lanes = _existing_lanes(entity.labels)
        risk = _existing_risk(entity.labels)
        if lanes and risk:
            return lanes, risk
        if not lanes:
            lanes = classify_lanes(entity.title, entity.body, entity.files)
        if not risk:
            risk = classify_risk(entity.title, entity.body, entity.files, lanes)
        return lanes, risk
    lanes = classify_lanes(entity.title, entity.body, entity.files)
    return lanes, classify_risk(entity.title, entity.body, entity.files, lanes)


def receipt_digest(material: dict[str, Any]) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def find_receipt_comment(gh: GH, number: int) -> tuple[dict[str, Any] | None, str | None]:
    comments = gh.paginate(
        f"/repos/{gh.repo}/issues/{number}/comments?per_page=100",
        max_pages=3,
    )
    for comment in comments:
        body = comment.get("body") or ""
        if COMMENT_MARKER not in body:
            continue
        match = re.search(r"<!-- penta-github-tagger:(\{.*?\}) -->", body, re.S)
        if not match:
            return comment, None
        try:
            marker = json.loads(match.group(1))
            return comment, marker.get("digest")
        except json.JSONDecodeError:
            return comment, None
    return None, None


def save_receipt_comment(gh: GH, receipt: dict[str, Any]) -> str:
    number = int(receipt["number"])
    existing, old_digest = find_receipt_comment(gh, number)
    if old_digest == receipt["digest"]:
        return "unchanged"

    lanes = ", ".join(receipt["lanes"])
    stage = receipt["stage"] or receipt["terminal"] or "none"
    marker = json.dumps(
        {
            "digest": receipt["digest"],
            "number": number,
            "kind": receipt["kind"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    body = (
        f"{COMMENT_MARKER}{marker} -->\n\n"
        "**PentaTagger GitHub-native receipt**\n\n"
        f"- Entity: `{receipt['kind'].upper()} #{number}`\n"
        f"- Lanes: `{lanes}`\n"
        f"- Risk: `{receipt['risk'].upper()}`\n"
        f"- Lifecycle projection: `{stage}`\n"
        f"- Label readback: `PASS` ({len(receipt['readback_labels'])} labels visible)\n"
        f"- Readback source: `{receipt['readback_source']}`\n"
        f"- Receipt digest: `{receipt['digest']}`\n\n"
        "Authority boundary: PentaTagger classifies and verifies labels; "
        "PentaPR classifies lifecycle; PentaMerge and PentaCloser execute terminal actions."
    )
    if existing:
        gh.patch(f"/repos/{gh.repo}/issues/comments/{existing['id']}", {"body": body})
        return "updated"
    gh.post(f"/repos/{gh.repo}/issues/{number}/comments", {"body": body})
    return "created"


def _starts_with_any(label: str, prefixes: tuple[str, ...]) -> bool:
    return label.startswith(prefixes)


def _label_plan(current: set[str], expected: set[str]) -> tuple[set[str], set[str]]:
    desired_managed = {name for name in expected if _starts_with_any(name, MANAGED_PREFIXES)}
    current_managed = {name for name in current if _starts_with_any(name, MANAGED_PREFIXES)}
    stale = current_managed.difference(desired_managed)
    missing = expected.difference(current)
    return missing, stale


def tag_entity(
    gh: GH,
    number: int,
    *,
    entity: Entity | None = None,
    preserve_semantics: bool = False,
    dry_run: bool = False,
    comment: bool = True,
) -> dict[str, Any]:
    entity = entity or fetch_entity(gh, number)
    lanes, risk = classify_entity(entity, preserve_semantics=preserve_semantics)
    stage_labels, terminal_labels = lifecycle_projection(entity)
    entity_labels = [f"penta:entity:{entity.kind}"]
    lane_labels = [f"penta:lane:{lane}" for lane in lanes]
    risk_labels = [f"penta:risk:{risk}"]
    core_labels = {"penta:tagged", "penta:authority:tagger"}

    expected = core_labels.union(
        entity_labels,
        lane_labels,
        risk_labels,
        stage_labels,
        terminal_labels,
    )
    current = set(entity.labels)
    missing, stale = _label_plan(current, expected)
    changed = bool(missing or stale)

    if dry_run:
        current = current.union(expected).difference(stale)
        readback_source = "dry_run"
    elif not changed:
        # The event/API entity snapshot is already provider readback. Avoid a
        # redundant issue GET and comment-list read on idempotent events.
        readback_source = entity.source
    else:
        # Add before remove so a rate-limit interruption cannot strip the
        # previous classification without installing the successor.
        if missing:
            add_labels(gh, number, missing)
        for name in sorted(stale):
            remove_label(gh, number, name)
        current = read_labels(gh, number)
        still_missing = expected.difference(current)
        unexpected_managed = {
            name
            for name in current
            if _starts_with_any(name, MANAGED_PREFIXES) and name not in expected
        }
        if still_missing or unexpected_managed:
            raise RuntimeError(
                "label_readback_failed:"
                f"{number}:missing={','.join(sorted(still_missing))}:"
                f"unexpected={','.join(sorted(unexpected_managed))}"
            )
        readback_source = gh.last_transport

    material = {
        "repo": gh.repo,
        "number": number,
        "kind": entity.kind,
        "state": entity.state,
        "merged": entity.merged,
        "lanes": lanes,
        "risk": risk,
        "stage": stage_labels[0] if stage_labels else None,
        "terminal": terminal_labels[0] if terminal_labels else None,
        "expected_labels": sorted(expected),
    }
    receipt = {
        **material,
        "observed_at": utc_now(),
        "readback_labels": sorted(current),
        "readback_source": readback_source,
        "status": "DRY_RUN" if dry_run else "PASS",
        "digest": receipt_digest(material),
        "url": entity.html_url,
        "labels_changed": changed,
        "api_requests": gh.request_count,
    }

    if comment and not dry_run and changed:
        try:
            receipt["comment_state"] = save_receipt_comment(gh, receipt)
        except RateLimitDeferred as exc:
            # Classification already passed provider readback. A receipt
            # comment is useful evidence but is not label authority.
            receipt["comment_state"] = "deferred-rate-limit"
            receipt["comment_retry_at"] = exc.evidence.reset_at
            receipt["comment_request_id"] = exc.evidence.request_id
    elif comment and not dry_run:
        receipt["comment_state"] = "unchanged-no-api"
    else:
        receipt["comment_state"] = "disabled"
    receipt["api_requests"] = gh.request_count
    return receipt


def sweep_numbers(
    gh: GH,
    kind: str,
    max_items: int,
    *,
    since_hours: int = 72,
) -> list[int]:
    since = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=max(1, since_hours))
    ).isoformat().replace("+00:00", "Z")
    encoded_since = urllib.parse.quote(since, safe=":-TZ")
    max_pages = max(1, min(MAX_PAGES, (max_items + 99) // 100 + 1))
    issues = gh.paginate(
        f"/repos/{gh.repo}/issues?state=all&per_page=100"
        f"&sort=updated&direction=desc&since={encoded_since}",
        max_pages=max_pages,
    )
    candidates: list[tuple[bool, int]] = []
    for issue in issues:
        is_pr = "pull_request" in issue
        if kind == "pr" and not is_pr:
            continue
        if kind == "issue" and is_pr:
            continue
        labels = _labels_from_payload(issue.get("labels", []))
        candidates.append(("penta:tagged" in labels, int(issue["number"])))
    # Missing PentaTagger identity is recovered before already-tagged drift.
    candidates.sort(key=lambda item: item[0])
    return [number for _, number in candidates[:max_items]]


def _deferred_receipt(
    *,
    number: int,
    kind: str,
    phase: str,
    reason: str,
    evidence: RateLimitEvidence | None = None,
) -> dict[str, Any]:
    return {
        "number": number,
        "kind": kind,
        "state": "unknown",
        "merged": False,
        "lanes": [],
        "risk": "unknown",
        "stage": None,
        "terminal": None,
        "expected_labels": [],
        "observed_at": utc_now(),
        "readback_labels": [],
        "readback_source": "not_available",
        "status": "DEFERRED",
        "digest": hashlib.sha256(
            f"{number}:{kind}:{phase}:{reason}".encode("utf-8")
        ).hexdigest(),
        "url": "",
        "labels_changed": False,
        "comment_state": "not_attempted",
        "deferred_phase": phase,
        "deferred_reason": reason,
        "retry_at": evidence.reset_at if evidence else None,
        "retry_after_seconds": evidence.retry_after_seconds if evidence else None,
        "rate_limit_resource": evidence.resource if evidence else None,
        "provider_request_id": evidence.request_id if evidence else None,
    }


def _failed_receipt(
    *,
    number: int,
    kind: str,
    phase: str,
    error: Exception,
) -> dict[str, Any]:
    return {
        "number": number,
        "kind": kind,
        "state": "unknown",
        "merged": False,
        "lanes": [],
        "risk": "unknown",
        "stage": None,
        "terminal": None,
        "expected_labels": [],
        "observed_at": utc_now(),
        "readback_labels": [],
        "readback_source": "not_available",
        "status": "FAIL",
        "digest": hashlib.sha256(
            f"{number}:{kind}:{phase}:{type(error).__name__}:{error}".encode("utf-8")
        ).hexdigest(),
        "url": "",
        "labels_changed": False,
        "comment_state": "not_attempted",
        "failed_phase": phase,
        "error_type": type(error).__name__,
        "error": str(error)[:1000],
    }


def write_outputs(
    receipts: list[dict[str, Any]],
    receipt_path: str | None,
    summary_path: str | None,
    *,
    transport: GH | None = None,
) -> dict[str, Any]:
    statuses = {item.get("status") for item in receipts}
    if "FAIL" in statuses:
        status = "FAIL"
    elif "DEFERRED" in statuses:
        status = "DEFERRED"
    else:
        status = "PASS"
    payload = {
        "generated_at": utc_now(),
        "status": status,
        "count": len(receipts),
        "deferred_count": sum(item.get("status") == "DEFERRED" for item in receipts),
        "failed_count": sum(item.get("status") == "FAIL" for item in receipts),
        "transport": {
            "requests": transport.request_count if transport else 0,
            "authenticated_requests": transport.authenticated_request_count if transport else 0,
            "public_fallback_requests": transport.public_request_count if transport else 0,
            "last_transport": transport.last_transport if transport else "none",
            "last_rate_limit_reset_at": (
                transport.last_rate_limit.reset_at
                if transport and transport.last_rate_limit
                else None
            ),
        },
        "receipts": receipts,
    }
    if receipt_path:
        Path(receipt_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if summary_path:
        lines = [
            "## PentaTagger GitHub Native v3",
            "",
            f"- Entities processed: **{len(receipts)}**",
            f"- Classification/readback status: **{status}**",
            f"- Deferred: **{payload['deferred_count']}**",
            f"- Failed: **{payload['failed_count']}**",
            f"- GitHub API calls: **{payload['transport']['requests']}** "
            f"(authenticated {payload['transport']['authenticated_requests']}; "
            f"public fallback {payload['transport']['public_fallback_requests']})",
            "- Authority: classification/readback only; no merge or close authority",
            "",
            "| Entity | Status | Risk | Lanes | Lifecycle | Readback | Digest |",
            "|---|---|---|---|---|---|---|",
        ]
        for receipt in receipts[:50]:
            lifecycle = receipt.get("stage") or receipt.get("terminal") or "none"
            lines.append(
                f"| {str(receipt.get('kind', 'unknown')).upper()} "
                f"#{receipt.get('number', 0)} | {receipt.get('status', 'UNKNOWN')} | "
                f"{str(receipt.get('risk', 'unknown')).upper()} | "
                f"{', '.join(receipt.get('lanes', [])) or 'none'} | {lifecycle} | "
                f"{receipt.get('readback_source', 'not_available')} | "
                f"`{str(receipt.get('digest', ''))[:12]}` |"
            )
        if status == "DEFERRED":
            retry_values = sorted(
                {
                    item.get("retry_at")
                    for item in receipts
                    if item.get("retry_at")
                }
            )
            lines.extend(
                [
                    "",
                    "> Provider quota deferral is explicit and recoverable. "
                    "The bounded scheduled sweep will replay the current provider state.",
                ]
            )
            if retry_values:
                lines.append(f"> Earliest provider reset evidence: `{retry_values[0]}`")
        Path(summary_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["event", "sweep", "verify"])
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
    parser.add_argument("--number", type=int)
    parser.add_argument("--kind", choices=["all", "pr", "issue"], default="all")
    parser.add_argument("--max-items", type=int, default=75)
    parser.add_argument("--request-budget", type=int, default=180)
    parser.add_argument("--sweep-since-hours", type=int, default=72)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-comment", action="store_true")
    parser.add_argument("--no-public-read-fallback", action="store_true")
    parser.add_argument("--receipt-path")
    parser.add_argument("--summary-path")
    args = parser.parse_args(argv)

    if not args.repo:
        raise SystemExit("repo_required")
    gh = GH(
        args.repo,
        public_read_fallback=not args.no_public_read_fallback,
    )
    receipts: list[dict[str, Any]] = []
    payload = load_event_payload(args.event_path)
    event_entity = entity_from_event_payload(payload)
    event_action = str(payload.get("action") or "").lower()

    try:
        if args.number:
            numbers = [args.number]
        elif args.mode == "event":
            numbers = [event_entity.number] if event_entity else []
        else:
            numbers = sweep_numbers(
                gh,
                args.kind,
                max(1, args.max_items),
                since_hours=max(1, args.sweep_since_hours),
            )
    except RateLimitDeferred as exc:
        kind = event_entity.kind if event_entity else args.kind
        number = event_entity.number if event_entity else (args.number or 0)
        receipts.append(
            _deferred_receipt(
                number=number,
                kind=kind,
                phase="target-selection",
                reason="github-rate-limit",
                evidence=exc.evidence,
            )
        )
        result = write_outputs(receipts, args.receipt_path, args.summary_path, transport=gh)
        print(json.dumps(result, sort_keys=True))
        return EXIT_DEFERRED
    except Exception as exc:
        receipts.append(
            _failed_receipt(
                number=args.number or 0,
                kind=event_entity.kind if event_entity else args.kind,
                phase="target-selection",
                error=exc,
            )
        )
        result = write_outputs(receipts, args.receipt_path, args.summary_path, transport=gh)
        print(json.dumps(result, sort_keys=True))
        return 1

    if not numbers and args.mode == "event":
        receipts.append(
            _failed_receipt(
                number=0,
                kind=args.kind,
                phase="event-selection",
                error=RuntimeError("event_target_missing"),
            )
        )

    for number in numbers:
        kind = event_entity.kind if event_entity and event_entity.number == number else args.kind
        if gh.request_count >= max(1, args.request_budget):
            receipts.append(
                _deferred_receipt(
                    number=number,
                    kind=kind,
                    phase="request-budget",
                    reason=f"request-budget-{args.request_budget}-reached",
                )
            )
            break
        try:
            seed = event_entity if event_entity and event_entity.number == number else None
            refresh_files = not (
                seed
                and seed.kind == "pr"
                and event_action not in SEMANTIC_PR_ACTIONS
            )
            entity = fetch_entity(
                gh,
                number,
                seed=seed,
                refresh_files=refresh_files,
            )
            preserve_semantics = bool(
                seed
                and seed.kind == "pr"
                and event_action not in SEMANTIC_PR_ACTIONS
            )
            receipts.append(
                tag_entity(
                    gh,
                    number,
                    entity=entity,
                    preserve_semantics=preserve_semantics,
                    dry_run=args.dry_run,
                    comment=not args.no_comment,
                )
            )
        except RateLimitDeferred as exc:
            receipts.append(
                _deferred_receipt(
                    number=number,
                    kind=kind,
                    phase="classification-write-readback",
                    reason="github-rate-limit",
                    evidence=exc.evidence,
                )
            )
            # Installation quota is shared; continuing would only amplify load.
            break
        except Exception as exc:
            receipts.append(
                _failed_receipt(
                    number=number,
                    kind=kind,
                    phase="classification-write-readback",
                    error=exc,
                )
            )
            if args.mode == "event":
                break

    result = write_outputs(receipts, args.receipt_path, args.summary_path, transport=gh)
    print(json.dumps(result, sort_keys=True))
    if result["status"] == "FAIL":
        return 1
    if result["status"] == "DEFERRED":
        return EXIT_DEFERRED
    return 0


if __name__ == "__main__":
    sys.exit(main())
