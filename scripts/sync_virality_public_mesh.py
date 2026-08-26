#!/usr/bin/env python3
"""Build a deterministic, public-safe Virality Music website mesh inventory.

The inventory is deliberately observational (D0).  It starts with the public
sitemap, follows only same-origin public HTML links, records a whitelisted
metadata projection, and never downloads images, media, documents, archives,
checkout resources, account routes, APIs, callbacks, or mutation endpoints.

Only the Python standard library is used so the same code can run locally, in
offline fixture tests, and in a read-only GitHub Actions drift job.
"""

from __future__ import annotations

import argparse
import html as html_module
import hashlib
import heapq
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol


SCHEMA = "ct.inventory.virality-public-mesh.v1"
INVENTORY_ID = "ct.inventory.virality-music.public-mesh"
PLATFORM_ID = "ct.platform.virality-music"
DEFAULT_SITEMAP_URL = "https://vm.crownthrive.com/sitemap.xml"
DEFAULT_OUTPUT = Path("artifacts/virality-public-mesh/virality-public-mesh.json")
USER_AGENT = "CrownThrive-PentaDocs-PublicMesh/1.0 (+https://docs.crownthrive.io/)"
MAX_RESOURCE_BYTES = 2_000_000
MAX_JSON_LD_BYTES = 512_000
DEFAULT_MAX_ROUTES = 2_500
DEFAULT_MAX_SITEMAPS = 50
DEFAULT_CONCURRENCY = 8

# A path matching one of these segments is never fetched as a page.  Public
# product/editorial pages remain crawlable; transaction, private, and service
# surfaces do not.
BLOCKED_PATH_SEGMENTS = frozenset(
    {
        "_next",
        "account",
        "accounts",
        "admin",
        "api",
        "auth",
        "billing",
        "callback",
        "callbacks",
        "cart",
        "checkout",
        "delete",
        "download",
        "downloads",
        "entitlement",
        "entitlements",
        "login",
        "logout",
        "mutation",
        "oauth",
        "order",
        "orders",
        "password",
        "pay",
        "payment",
        "payments",
        "private",
        "protected",
        "purchase",
        "reset-password",
        "session",
        "sessions",
        "sign-in",
        "sign-up",
        "signed",
        "signin",
        "signup",
        "submit",
        "subscribe",
        "token",
        "tokens",
        "unsubscribe",
        "update",
        "webhook",
        "webhooks",
    }
)

# XML sitemaps are handled by the sitemap loader.  Every other non-HTML suffix
# is a reference-only asset and cannot enter the page fetch queue.
BLOCKED_PAGE_SUFFIXES = frozenset(
    {
        ".7z",
        ".aac",
        ".avi",
        ".avif",
        ".bin",
        ".css",
        ".csv",
        ".doc",
        ".docx",
        ".eot",
        ".epub",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".m4a",
        ".m4v",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".ogg",
        ".otf",
        ".pdf",
        ".png",
        ".rar",
        ".rss",
        ".svg",
        ".tar",
        ".tgz",
        ".tif",
        ".tiff",
        ".ttf",
        ".txt",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xml",
        ".zip",
    }
)

ALLOWED_META_NAMES = frozenset(
    {
        "author",
        "description",
        "keywords",
        "robots",
        "theme-color",
        "application-name",
    }
)
ALLOWED_META_PREFIXES = ("og:", "twitter:", "article:", "book:", "music:", "product:")

ASSET_SUFFIX_TYPES: dict[str, str] = {
    ".7z": "archive",
    ".aac": "audio",
    ".avi": "video",
    ".avif": "image",
    ".css": "stylesheet",
    ".doc": "document",
    ".docx": "document",
    ".eot": "font",
    ".epub": "ebook",
    ".gif": "image",
    ".ico": "icon",
    ".jpeg": "image",
    ".jpg": "image",
    ".js": "script",
    ".json": "data",
    ".m4a": "audio",
    ".m4v": "video",
    ".mov": "video",
    ".mp3": "audio",
    ".mp4": "video",
    ".mpeg": "video",
    ".ogg": "audio",
    ".otf": "font",
    ".pdf": "document",
    ".png": "image",
    ".rar": "archive",
    ".rss": "feed",
    ".svg": "image",
    ".tar": "archive",
    ".tgz": "archive",
    ".tif": "image",
    ".tiff": "image",
    ".ttf": "font",
    ".wav": "audio",
    ".webm": "video",
    ".webp": "image",
    ".woff": "font",
    ".woff2": "font",
    ".xml": "feed",
    ".zip": "archive",
}

CATEGORY_SEGMENTS: dict[str, frozenset[str]] = {
    "books": frozenset({"book", "books", "edition", "editions", "library", "reader"}),
    "characters": frozenset({"character", "characters", "dossier", "dossiers"}),
    "commerce": frozenset({"bundle", "bundles", "collection", "collections", "product", "products", "shop", "store"}),
    "creator": frozenset({"artist", "artists", "creator", "creators", "submission", "submissions"}),
    "licensing": frozenset({"license", "licenses", "licensing", "sync"}),
    "music": frozenset({"album", "albums", "discography", "music", "release", "releases", "song", "songs", "track", "tracks"}),
    "poetry": frozenset({"poem", "poems", "poetry", "spoken-word", "spoken-word-poetry"}),
    "publishing": frozenset({"imprint", "imprints", "publication", "publications", "publishing"}),
    "radio": frozenset({"backroad-fm", "program", "programs", "radio", "station", "stations"}),
    "universe": frozenset({"series", "universe", "universes", "world", "worlds"}),
}

KNOWN_UNIVERSES: dict[str, str] = {
    "backroad-fm": "backroad-fm",
    "bless-the-house": "bless-the-house",
    "good-shit-only": "good-shit-only",
    "jenkins": "jenkins",
    "little-crowns": "little-crowns",
    "living-witness": "living-witness",
    "melanin-magic": "melanin-magic",
    "shadow-files": "shadow-files",
    "spoken-word-poetry": "spoken-word-poetry",
    "tendernism": "tendernism",
    "the-mane-experience": "the-mane-experience",
    "trap-opera": "trapopera",
    "trapopera": "trapopera",
    "word-house": "word-house",
}

STRUCTURED_TYPE_CATEGORIES = {
    "Book": "books",
    "MusicAlbum": "music",
    "MusicRecording": "music",
    "Offer": "commerce",
    "AggregateOffer": "commerce",
    "Product": "commerce",
    "RadioStation": "radio",
}


class CrawlError(RuntimeError):
    """A stable, user-safe crawler failure."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class FetchedResource:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body: bytes


class Fetcher(Protocol):
    mode: str

    def fetch(self, url: str, *, purpose: str) -> FetchedResource:
        """Fetch one approved text resource."""


def canonical_json(value: Any) -> bytes:
    """Return the canonical JSON representation used by every inventory hash."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def value_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def utc_timestamp(value: str | None = None) -> str:
    """Normalize a supplied timestamp, SOURCE_DATE_EPOCH, or current time."""
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("source timestamp must include a UTC offset")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        parsed = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def origin_for(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"URL must be absolute HTTP(S): {url!r}")
    host = parsed.hostname.lower()
    port = parsed.port
    default_port = (parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)
    authority = host if port is None or default_port else f"{host}:{port}"
    return f"{parsed.scheme.lower()}://{authority}"


def sanitize_url(url: str, *, base_url: str | None = None) -> tuple[str | None, bool]:
    """Resolve an HTTP(S) URL while removing fragments, queries, and userinfo."""
    resolved = urllib.parse.urljoin(base_url, url) if base_url else url
    parsed = urllib.parse.urlsplit(resolved)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None, False
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    authority = host if port is None or default_port else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    quoted_path = urllib.parse.quote(urllib.parse.unquote(path), safe="/%:@!$&'()*+,;=-._~")
    sanitized = urllib.parse.urlunsplit((scheme, authority, quoted_path, "", ""))
    return sanitized, bool(parsed.query or parsed.fragment or parsed.username or parsed.password)


def same_origin(url: str, expected_origin: str) -> bool:
    try:
        return origin_for(url) == expected_origin
    except (ValueError, urllib.parse.PortNotFoundError):
        return False


def path_segments(url: str) -> tuple[str, ...]:
    return tuple(
        segment.lower()
        for segment in urllib.parse.unquote(urllib.parse.urlsplit(url).path).split("/")
        if segment
    )


def page_policy_reason(url: str, expected_origin: str) -> str | None:
    parsed = urllib.parse.urlsplit(url)
    if not same_origin(url, expected_origin):
        return "cross_origin"
    if parsed.query:
        return "query_route_not_crawled"
    segments = path_segments(url)
    if ".well-known" in segments:
        return "public_machine_endpoint_reference_only"
    blocked = sorted(set(segments) & BLOCKED_PATH_SEGMENTS)
    if blocked:
        return f"protected_or_mutation_segment:{blocked[0]}"
    suffix = Path(parsed.path).suffix.lower()
    if suffix in BLOCKED_PAGE_SUFFIXES:
        return f"non_html_or_protected_suffix:{suffix}"
    return None


def safe_text(value: Any, limit: int = 2_048) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit] if text else None


def infer_asset_type(url: str, hint: str | None = None) -> str:
    """Infer a coarse public reference type without requesting the asset."""
    normalized_hint = (hint or "").strip().lower()
    hint_map = {
        "audio": "audio",
        "document": "document",
        "ebook": "ebook",
        "embed": "embed",
        "font": "font",
        "icon": "icon",
        "image": "image",
        "script": "script",
        "style": "stylesheet",
        "stylesheet": "stylesheet",
        "video": "video",
    }
    if normalized_hint in hint_map:
        return hint_map[normalized_hint]
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return ASSET_SUFFIX_TYPES.get(suffix, "linked_resource")


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, guard: Callable[[str], bool]) -> None:
        super().__init__()
        self.guard = guard

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:
        target, _ = sanitize_url(newurl, base_url=req.full_url)
        if target is None or not self.guard(target):
            raise CrawlError("unsafe_redirect", "redirect target is outside the approved public-text boundary")
        return super().redirect_request(req, fp, code, msg, headers, target)


class NetworkFetcher:
    """GET-only bounded fetcher with guarded same-origin redirects."""

    mode = "network"

    def __init__(self, root_origin: str, *, timeout: float = 20.0, max_bytes: int = MAX_RESOURCE_BYTES) -> None:
        self.root_origin = root_origin
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.opener = urllib.request.build_opener(_GuardedRedirectHandler(self._redirect_allowed))

    def _redirect_allowed(self, url: str) -> bool:
        if not same_origin(url, self.root_origin):
            return False
        segments = path_segments(url)
        return not bool(set(segments) & BLOCKED_PATH_SEGMENTS)

    def fetch(self, url: str, *, purpose: str) -> FetchedResource:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,text/plain;q=0.8",
                "Accept-Encoding": "identity",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = int(response.status)
                content_type = response.headers.get_content_type().lower()
                final_url, _ = sanitize_url(response.geturl())
                if final_url is None or not same_origin(final_url, self.root_origin):
                    raise CrawlError("unsafe_final_url", "final URL is outside the approved origin")
                self._validate_content_type(content_type, purpose)
                declared_length = response.headers.get("Content-Length")
                if declared_length and int(declared_length) > self.max_bytes:
                    raise CrawlError("resource_too_large", f"resource exceeds {self.max_bytes} bytes")
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise CrawlError("resource_too_large", f"resource exceeds {self.max_bytes} bytes")
                return FetchedResource(url, final_url, status, content_type, body)
        except CrawlError:
            raise
        except urllib.error.HTTPError as exc:
            raise CrawlError("http_error", f"HTTP {exc.code}", retryable=500 <= exc.code < 600) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = safe_text(getattr(exc, "reason", None), 160) or exc.__class__.__name__
            raise CrawlError("network_error", reason, retryable=True) from exc

    @staticmethod
    def _validate_content_type(content_type: str, purpose: str) -> None:
        allowed = {
            "page": {"text/html", "application/xhtml+xml"},
            "robots": {"text/plain"},
            "sitemap": {"application/xml", "application/xhtml+xml", "text/html", "text/plain", "text/xml"},
        }[purpose]
        if content_type not in allowed:
            # This check occurs before response.read(), so a disguised binary is
            # never downloaded into the inventory process.
            raise CrawlError("disallowed_content_type", f"content type {content_type!r} is not allowed for {purpose}")


class FixtureFetcher:
    """Offline fetcher driven by ``fixture-dir/index.json``."""

    mode = "fixture"

    def __init__(self, fixture_dir: Path, root_origin: str, *, max_bytes: int = MAX_RESOURCE_BYTES) -> None:
        self.fixture_dir = fixture_dir.resolve()
        self.root_origin = root_origin
        index_path = self.fixture_dir / "index.json"
        raw_index = json.loads(index_path.read_text(encoding="utf-8"))
        resources = raw_index.get("resources")
        if not isinstance(resources, dict):
            raise ValueError("fixture index must contain an object at resources")
        self.resources = resources
        self.max_bytes = max_bytes
        self.requests: list[tuple[str, str]] = []

    def fetch(self, url: str, *, purpose: str) -> FetchedResource:
        sanitized, _ = sanitize_url(url)
        if sanitized is None:
            raise CrawlError("fixture_invalid_url", "fixture URL is invalid")
        self.requests.append((sanitized, purpose))
        record = self.resources.get(sanitized)
        if not isinstance(record, dict):
            raise CrawlError("fixture_missing", f"no fixture registered for {sanitized}")
        if "error" in record:
            raise CrawlError(
                safe_text(record.get("error"), 80) or "fixture_error",
                safe_text(record.get("message"), 160) or "fixture-declared failure",
                retryable=bool(record.get("retryable")),
            )
        relative = Path(str(record["file"]))
        path = (self.fixture_dir / relative).resolve()
        if self.fixture_dir not in path.parents:
            raise CrawlError("fixture_path_escape", "fixture path escapes fixture directory")
        body = path.read_bytes()
        if len(body) > self.max_bytes:
            raise CrawlError("resource_too_large", f"fixture exceeds {self.max_bytes} bytes")
        content_type = str(record.get("content_type", "text/html")).lower()
        NetworkFetcher._validate_content_type(content_type, purpose)
        final_url, _ = sanitize_url(str(record.get("final_url", sanitized)), base_url=sanitized)
        if final_url is None or not same_origin(final_url, self.root_origin):
            raise CrawlError("unsafe_final_url", "fixture final URL is outside the approved origin")
        return FetchedResource(
            requested_url=sanitized,
            final_url=final_url,
            status=int(record.get("status", 200)),
            content_type=content_type,
            body=body,
        )


def _srcset_urls(value: str) -> Iterable[str]:
    for candidate in value.split(","):
        parts = candidate.strip().split(maxsplit=1)
        if not parts:
            continue
        url = parts[0]
        if url and not url.startswith("data:"):
            yield url


class PublicHTMLParser(HTMLParser):
    """Extract a bounded public metadata projection; never retain page bodies."""

    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.title_chunks: list[str] = []
        self.h1_chunks: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._json_ld_depth = 0
        self._json_ld_chunks: list[str] = []
        self._json_ld_documents: list[str] = []
        self.metadata: dict[str, str] = {}
        self.canonical_url: str | None = None
        self.language: str | None = None
        self.internal_links: set[str] = set()
        self.external_references: list[tuple[str, str]] = []
        self.images: list[dict[str, Any]] = []
        self.assets: list[dict[str, Any]] = []
        self.style_chunks: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        if tag == "html":
            self.language = safe_text(values.get("lang"), 80)
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            name = (values.get("name") or values.get("property") or "").strip().lower()
            content = safe_text(values.get("content"))
            if content and (name in ALLOWED_META_NAMES or name.startswith(ALLOWED_META_PREFIXES)):
                self.metadata.setdefault(name, content)
                if name.endswith("image") or name.endswith("image:url"):
                    self._add_image(content, None, False, "metadata")
        elif tag == "link":
            rels = {part.lower() for part in values.get("rel", "").split()}
            href = values.get("href", "")
            if "canonical" in rels:
                canonical, _ = sanitize_url(href, base_url=self.page_url)
                self.canonical_url = canonical
            relationship = "stylesheet" if "stylesheet" in rels else "link_resource"
            self._add_reference(href, relationship)
            if "stylesheet" in rels:
                self._add_asset(href, "stylesheet", "link:stylesheet")
            if rels & {"icon", "apple-touch-icon", "image_src"}:
                self._add_image(href, None, False, "link")
                if rels & {"icon", "apple-touch-icon"}:
                    self._add_asset(href, "icon", "link:icon")
            if "preload" in rels or "modulepreload" in rels:
                preload_type = values.get("as") or ("script" if "modulepreload" in rels else None)
                if preload_type == "image":
                    self._add_image(href, None, False, "link:preload")
                else:
                    self._add_asset(href, preload_type, "link:preload")
        elif tag == "a":
            href = values.get("href", "")
            target, _ = sanitize_url(href, base_url=self.page_url)
            if target and Path(urllib.parse.urlsplit(target).path).suffix.lower() in ASSET_SUFFIX_TYPES:
                self._add_asset(href, None, "anchor:asset")
            else:
                self._add_reference(href, "link", follow=True)
        elif tag == "img":
            alt_present = "alt" in values
            alt = safe_text(values.get("alt"), 500) if alt_present else None
            for attribute in ("src", "data-src", "data-lazy-src"):
                if values.get(attribute):
                    self._add_image(values[attribute], alt, alt_present, attribute)
            for attribute in ("srcset", "data-srcset"):
                for image_url in _srcset_urls(values.get(attribute, "")):
                    self._add_image(image_url, alt, alt_present, attribute)
        elif tag == "source":
            for attribute in ("src", "srcset"):
                raw = values.get(attribute, "")
                candidates = _srcset_urls(raw) if attribute == "srcset" else (raw,)
                for asset_url in candidates:
                    mime = values.get("type", "").lower()
                    hint = mime.split("/", 1)[0] if "/" in mime else None
                    if hint == "image" or infer_asset_type(asset_url, hint) == "image":
                        self._add_image(asset_url, None, False, f"source:{attribute}")
                    else:
                        self._add_asset(asset_url, hint, f"source:{attribute}")
        elif tag in {"audio", "video"}:
            self._add_asset(values.get("src", ""), tag, tag)
            if tag == "video" and values.get("poster"):
                self._add_image(values["poster"], None, False, "video:poster")
        elif tag in {"embed", "iframe"}:
            self._add_asset(values.get("src", ""), "embed", tag)
        elif tag == "object":
            self._add_asset(values.get("data", ""), None, "object:data")
        elif tag == "script":
            self._add_reference(values.get("src", ""), "script")
            self._add_asset(values.get("src", ""), "script", "script:src")
            if values.get("type", "").split(";", 1)[0].strip().lower() == "application/ld+json":
                self._json_ld_depth += 1
                self._json_ld_chunks = []
        elif tag == "style":
            self._in_style = True
        elif tag == "form":
            # The action domain is useful relationship context, but forms are
            # never submitted and their action URLs are never retained.
            self._add_reference(values.get("action", ""), "form_action")

        if values.get("style"):
            self._add_css_images(values["style"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "style":
            self._in_style = False
            self._add_css_images("".join(self.style_chunks))
            self.style_chunks = []
        elif tag == "script" and self._json_ld_depth:
            document = "".join(self._json_ld_chunks)
            if len(document.encode("utf-8")) <= MAX_JSON_LD_BYTES:
                self._json_ld_documents.append(document)
            self._json_ld_chunks = []
            self._json_ld_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)
        if self._in_h1:
            self.h1_chunks.append(data)
        if self._in_style and sum(map(len, self.style_chunks)) < MAX_JSON_LD_BYTES:
            self.style_chunks.append(data)
        if self._json_ld_depth and sum(map(len, self._json_ld_chunks)) < MAX_JSON_LD_BYTES:
            self._json_ld_chunks.append(data)

    def _add_reference(self, value: str, relationship: str, *, follow: bool = False) -> None:
        target, _ = sanitize_url(value, base_url=self.page_url)
        if target is None:
            return
        if follow and origin_for(target) == origin_for(self.page_url):
            self.internal_links.add(target)
        elif origin_for(target) != origin_for(self.page_url):
            self.external_references.append((urllib.parse.urlsplit(target).hostname or "", relationship))

    def _add_asset(self, value: str, asset_type: str | None, source: str) -> None:
        target, query_redacted = sanitize_url(value, base_url=self.page_url)
        if target is None:
            return
        normalized_type = infer_asset_type(target, asset_type)
        self.assets.append(
            {
                "url": target,
                "asset_type": normalized_type,
                "source": source,
                "query_redacted": query_redacted,
                "observation_status": "public_reference_observed_not_downloaded",
            }
        )
        if origin_for(target) != origin_for(self.page_url):
            self.external_references.append((urllib.parse.urlsplit(target).hostname or "", normalized_type))

    def _add_image(self, value: str, alt: str | None, alt_present: bool, source: str) -> None:
        target, query_redacted = sanitize_url(value, base_url=self.page_url)
        if target is None:
            return
        if not alt_present:
            alt_state = "not_applicable" if source in {"metadata", "link"} or source.startswith("source:") else "missing"
        elif alt:
            alt_state = "present"
        else:
            alt_state = "empty"
        self.images.append(
            {
                "url": target,
                "alt": alt,
                "alt_state": alt_state,
                "source": source,
                "query_redacted": query_redacted,
            }
        )
        self._add_asset(target, "image", source)
        if origin_for(target) != origin_for(self.page_url):
            self.external_references.append((urllib.parse.urlsplit(target).hostname or "", "image"))

    def _add_css_images(self, css: str) -> None:
        for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, flags=re.IGNORECASE):
            self._add_image(match.group(2), None, False, "css")

    def public_metadata(self) -> dict[str, Any]:
        title = safe_text(" ".join(self.title_chunks), 500)
        h1 = safe_text(" ".join(self.h1_chunks), 500)
        return {
            "title": title,
            "description": self.metadata.get("description"),
            "canonical_url": self.canonical_url,
            "language": self.language,
            "robots": self.metadata.get("robots"),
            "h1": h1,
            "meta": dict(sorted(self.metadata.items())),
        }

    def structured_summaries(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        products: list[dict[str, Any]] = []
        offers: list[dict[str, Any]] = []
        types: set[str] = set()
        for document in self._json_ld_documents:
            try:
                value = json.loads(document)
            except json.JSONDecodeError:
                continue
            for node in walk_json_ld(value):
                node_types = json_ld_types(node)
                types.update(node_types)
                for key in ("contentUrl", "image", "thumbnailUrl"):
                    hint = "image" if key in {"image", "thumbnailUrl"} else None
                    for asset_url in structured_asset_values(node.get(key)):
                        if infer_asset_type(asset_url, hint) == "image":
                            self._add_image(asset_url, None, False, f"json_ld:{key}")
                        else:
                            self._add_asset(asset_url, hint, f"json_ld:{key}")
                if "Product" in node_types:
                    products.append(summarize_product(node, self.page_url))
                if node_types & {"Offer", "AggregateOffer"}:
                    offers.append(summarize_offer(node, self.page_url))
        return dedupe_dicts(products), dedupe_dicts(offers), sorted(types)


def structured_asset_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key in ("url", "contentUrl", "thumbnailUrl"):
            if isinstance(value.get(key), str):
                yield value[key]
    elif isinstance(value, list):
        for item in value:
            yield from structured_asset_values(item)


def walk_json_ld(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json_ld(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json_ld(child)


def json_ld_types(node: Mapping[str, Any]) -> set[str]:
    value = node.get("@type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def summarize_brand(value: Any) -> str | None:
    if isinstance(value, dict):
        return safe_text(value.get("name"), 300)
    return safe_text(value, 300)


def credit_labels(node: Mapping[str, Any]) -> list[str]:
    """Extract public credit labels without assigning value or redemption."""
    labels: set[str] = set()
    for key in ("credit", "credits", "creditText"):
        value = node.get(key)
        if isinstance(value, list):
            for item in value:
                label = summarize_brand(item)
                if label:
                    labels.add(label)
        else:
            label = summarize_brand(value)
            if label:
                labels.add(label)
    properties = node.get("additionalProperty")
    if not isinstance(properties, list):
        properties = [properties]
    for item in properties:
        if not isinstance(item, dict):
            continue
        name = safe_text(item.get("name"), 160)
        value = safe_text(item.get("value"), 300)
        if name and "credit" in name.lower():
            labels.add(f"{name}: {value}" if value else name)
    return sorted(labels)


def structured_url(value: Any, base_url: str) -> str | None:
    if not isinstance(value, str):
        return None
    result, _ = sanitize_url(value, base_url=base_url)
    return result


def structured_images(value: Any, base_url: str) -> list[str]:
    raw_values: list[Any]
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = [value]
    urls: set[str] = set()
    for raw in raw_values:
        if isinstance(raw, dict):
            raw = raw.get("url") or raw.get("contentUrl")
        url = structured_url(raw, base_url)
        if url:
            urls.add(url)
    return sorted(urls)


def summarize_offer(node: Mapping[str, Any], base_url: str) -> dict[str, Any]:
    types = sorted(json_ld_types(node) & {"Offer", "AggregateOffer"}) or ["Offer"]
    seller = node.get("seller")
    seller_name = summarize_brand(seller)
    summary = {
        "types": types,
        "name": safe_text(node.get("name"), 300),
        "url": structured_url(node.get("url"), base_url),
        "price": safe_text(node.get("price"), 80),
        "low_price": safe_text(node.get("lowPrice"), 80),
        "high_price": safe_text(node.get("highPrice"), 80),
        "price_currency": safe_text(node.get("priceCurrency"), 20),
        "availability": safe_text(node.get("availability"), 300),
        "item_condition": safe_text(node.get("itemCondition"), 300),
        "price_valid_until": safe_text(node.get("priceValidUntil"), 40),
        "seller": seller_name,
    }
    return {key: value for key, value in summary.items() if value not in (None, [], "")}


def summarize_product(node: Mapping[str, Any], base_url: str) -> dict[str, Any]:
    nested_offers = node.get("offers")
    offer_nodes = nested_offers if isinstance(nested_offers, list) else [nested_offers]
    offers = [summarize_offer(item, base_url) for item in offer_nodes if isinstance(item, dict)]
    summary = {
        "types": sorted(json_ld_types(node)) or ["Product"],
        "name": safe_text(node.get("name"), 300),
        "description": safe_text(node.get("description"), 500),
        "sku": safe_text(node.get("sku"), 160),
        "category": safe_text(node.get("category"), 300),
        "brand": summarize_brand(node.get("brand")),
        "url": structured_url(node.get("url"), base_url),
        "images": structured_images(node.get("image"), base_url),
        "credits_labels": credit_labels(node),
        "offers": dedupe_dicts(offers),
    }
    return {key: value for key, value in summary.items() if value not in (None, [], "")}


def dedupe_dicts(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}
    for value in values:
        by_hash[value_sha256(value)] = value
    return [by_hash[key] for key in sorted(by_hash)]


def classify_route(url: str, structured_types: Iterable[str]) -> dict[str, list[str]]:
    segments = path_segments(url)
    segment_set = set(segments)
    categories = {
        category
        for category, markers in CATEGORY_SEGMENTS.items()
        if segment_set & markers
    }
    categories.update(
        category
        for structured_type, category in STRUCTURED_TYPE_CATEGORIES.items()
        if structured_type in structured_types
    )
    universes: set[str] = set()
    for index, segment in enumerate(segments[:-1]):
        if segment in {"series", "universe", "universes", "world", "worlds"}:
            universes.add(segments[index + 1])
    for segment in segments:
        if segment in KNOWN_UNIVERSES:
            universes.add(KNOWN_UNIVERSES[segment])
    if universes:
        categories.add("universe")
    if not categories:
        categories.add("general")
    return {"categories": sorted(categories), "universes": sorted(universes)}


def decode_text(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def recover_malformed_sitemap(
    text: str,
    base_url: str,
) -> tuple[list[tuple[str, str | None]], list[str], list[dict[str, Any]]]:
    """Recover bounded ``loc`` fields after strict XML parsing fails.

    Recovery intentionally extracts only the public URL/lastmod/image fields
    already allowed by the inventory schema.  It never executes XML entities,
    scripts, embedded instructions, or arbitrary element bodies.
    """

    def element_text(fragment: str, name: str) -> str | None:
        match = re.search(
            rf"(?is)<(?:[A-Za-z0-9_-]+:)?{re.escape(name)}\b[^>]*>(.*?)</(?:[A-Za-z0-9_-]+:)?{re.escape(name)}\s*>",
            fragment,
        )
        if not match:
            return None
        return html_module.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()

    if re.search(r"(?is)<(?:[A-Za-z0-9_-]+:)?sitemapindex\b", text):
        nested: set[str] = set()
        for block in re.findall(
            r"(?is)<(?:[A-Za-z0-9_-]+:)?sitemap\b[^>]*>(.*?)</(?:[A-Za-z0-9_-]+:)?sitemap\s*>",
            text,
        ):
            raw = element_text(block, "loc")
            url, _ = sanitize_url(raw or "", base_url=base_url)
            if url:
                nested.add(url)
        if not nested:
            raise CrawlError("malformed_sitemap_unrecoverable", "strict XML failed and no sitemap locations were recoverable")
        return [], sorted(nested), []

    entries: list[tuple[str, str | None]] = []
    assets: list[dict[str, Any]] = []
    blocks = re.findall(
        r"(?is)<(?:[A-Za-z0-9_-]+:)?url\b[^>]*>(.*?)</(?:[A-Za-z0-9_-]+:)?url\s*>",
        text,
    )
    for block in blocks:
        page_raw = element_text(block, "loc")
        page_url, _ = sanitize_url(page_raw or "", base_url=base_url)
        if not page_url:
            continue
        entries.append((page_url, safe_text(element_text(block, "lastmod"), 80)))
        for image_block in re.findall(
            r"(?is)<(?:[A-Za-z0-9_-]+:)?image\b[^>]*>(.*?)</(?:[A-Za-z0-9_-]+:)?image\s*>",
            block,
        ):
            image_raw = element_text(image_block, "loc")
            image_url, query_redacted = sanitize_url(image_raw or "", base_url=base_url)
            if not image_url:
                continue
            alt = safe_text(element_text(image_block, "title") or element_text(image_block, "caption"), 500)
            assets.append(
                {
                    "page_url": page_url,
                    "url": image_url,
                    "asset_type": "image",
                    "source": "sitemap:image",
                    "alt": alt,
                    "alt_state": "present" if alt else "not_applicable",
                    "query_redacted": query_redacted,
                    "observation_status": "public_reference_observed_not_downloaded",
                }
            )
    if not entries:
        raise CrawlError("malformed_sitemap_unrecoverable", "strict XML failed and no public URL entries were recoverable")
    assets.sort(key=lambda row: (row["page_url"], row["url"], row.get("alt") or ""))
    return sorted(set(entries)), [], assets


def parse_sitemap_document(
    body: bytes,
    base_url: str,
) -> tuple[list[tuple[str, str | None]], list[str], list[dict[str, Any]], dict[str, Any]]:
    """Return pages, nested maps, and reference-only image sitemap assets."""
    text = decode_text(body).lstrip("\ufeff\r\n\t ")
    if text.startswith("<") and not re.search(r"(?is)^<!doctype\s+html|<html\b", text[:1_024]):
        if re.search(r"(?is)<!doctype|<!entity", text):
            raise CrawlError("unsafe_xml_declaration", "sitemap contains a prohibited DTD/entity declaration")
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            entries, nested, assets = recover_malformed_sitemap(text, base_url)
            return entries, nested, assets, {
                "state": "malformed_xml_recovered_bounded_fields",
                "warning_code": "invalid_sitemap_xml",
                "warning": safe_text(exc, 160) or "invalid XML",
            }
        root_name = xml_local_name(root.tag)
        if root_name == "sitemapindex":
            nested = []
            for element in root.iter():
                if xml_local_name(element.tag) == "loc" and element.text:
                    url, _ = sanitize_url(element.text.strip(), base_url=base_url)
                    if url:
                        nested.append(url)
            return [], sorted(set(nested)), [], {"state": "xml_well_formed", "warning_code": None, "warning": None}
        if root_name != "urlset":
            raise CrawlError("unsupported_sitemap_root", f"unsupported sitemap root {root_name!r}")
        entries: list[tuple[str, str | None]] = []
        assets: list[dict[str, Any]] = []
        for url_element in root:
            if xml_local_name(url_element.tag) != "url":
                continue
            loc: str | None = None
            lastmod: str | None = None
            for child in url_element:
                name = xml_local_name(child.tag)
                if name == "loc" and child.text:
                    loc, _ = sanitize_url(child.text.strip(), base_url=base_url)
                elif name == "lastmod" and child.text:
                    lastmod = safe_text(child.text, 80)
            if loc:
                for child in url_element:
                    if xml_local_name(child.tag) != "image":
                        continue
                    image_url: str | None = None
                    image_query_redacted = False
                    alt: str | None = None
                    for detail in child:
                        detail_name = xml_local_name(detail.tag)
                        if detail_name == "loc" and detail.text:
                            image_url, image_query_redacted = sanitize_url(detail.text.strip(), base_url=base_url)
                        elif detail_name in {"caption", "title"} and detail.text and alt is None:
                            alt = safe_text(detail.text, 500)
                    if image_url:
                        assets.append(
                            {
                                "page_url": loc,
                                "url": image_url,
                                "asset_type": "image",
                                "source": "sitemap:image",
                                "alt": alt,
                                "alt_state": "present" if alt else "not_applicable",
                                "query_redacted": image_query_redacted,
                                "observation_status": "public_reference_observed_not_downloaded",
                            }
                        )
            if loc:
                entries.append((loc, lastmod))
        assets.sort(key=lambda row: (row["page_url"], row["url"], row.get("alt") or ""))
        return sorted(set(entries)), [], assets, {"state": "xml_well_formed", "warning_code": None, "warning": None}

    parser = PublicHTMLParser(base_url)
    parser.feed(text)
    return [(url, None) for url in sorted(parser.internal_links)], [], [], {
        "state": "html_sitemap",
        "warning_code": None,
        "warning": None,
    }


def stable_failure(url: str, stage: str, error: CrawlError) -> dict[str, Any]:
    sanitized, _ = sanitize_url(url)
    return {
        "url": sanitized or "invalid-url",
        "stage": stage,
        "code": error.code,
        "message": safe_text(error, 240) or error.code,
        "retryable": error.retryable,
    }


def normalize_image_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str | None, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["url"], row.get("alt"), row["alt_state"], row["source"])
        existing = deduped.get(key)
        if existing:
            existing["query_redacted"] = existing["query_redacted"] or row["query_redacted"]
        else:
            deduped[key] = dict(row)
    return [deduped[key] for key in sorted(deduped, key=lambda item: tuple(part or "" for part in item))]


def normalize_asset_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["url"], row["asset_type"], row["source"])
        existing = deduped.get(key)
        if existing:
            existing["query_redacted"] = existing["query_redacted"] or bool(row.get("query_redacted"))
        else:
            deduped[key] = {
                "url": row["url"],
                "asset_type": row["asset_type"],
                "source": row["source"],
                "query_redacted": bool(row.get("query_redacted")),
                "observation_status": "public_reference_observed_not_downloaded",
            }
    return [deduped[key] for key in sorted(deduped)]


def commerce_observations(
    page_url: str,
    observed_at: str,
    metadata: Mapping[str, Any],
    products: Iterable[dict[str, Any]],
    offers: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []

    def append(kind: str, source_type: str, value: Mapping[str, Any]) -> None:
        row = {
            "kind": kind,
            "source_type": source_type,
            "source_route": page_url,
            "observed_at": observed_at,
            "name": safe_text(value.get("name"), 300),
            "sku": safe_text(value.get("sku"), 160),
            "url": structured_url(value.get("url"), page_url),
            "price": safe_text(value.get("price"), 80),
            "price_currency": safe_text(value.get("price_currency") or value.get("priceCurrency"), 20),
            "availability": safe_text(value.get("availability"), 300),
            "credits_labels": sorted(
                {
                    label
                    for label in value.get("credits_labels", [])
                    if isinstance(label, str) and label.strip()
                }
            ),
            "observation_only": True,
            "paid_redeemable": 0,
            "redemption_inferred": False,
        }
        normalized = {key: item for key, item in row.items() if item not in (None, [], "")}
        semantic_observation = {key: item for key, item in normalized.items() if key != "observed_at"}
        normalized["observation_sha256"] = value_sha256(semantic_observation)
        observations.append(normalized)

    for product in products:
        append("product", "json_ld", product)
        for offer in product.get("offers", []):
            if isinstance(offer, dict):
                append("offer", "json_ld_nested", offer)
    for offer in offers:
        append("offer", "json_ld", offer)

    meta = metadata.get("meta", {}) if isinstance(metadata, Mapping) else {}
    if isinstance(meta, Mapping) and (meta.get("og:type") == "product" or any(str(key).startswith("product:") for key in meta)):
        credit_values = [
            str(value)
            for key, value in meta.items()
            if "credit" in str(key).lower() and isinstance(value, str)
        ]
        append(
            "product",
            "open_graph",
            {
                "name": meta.get("og:title"),
                "sku": meta.get("product:retailer_item_id"),
                "url": meta.get("og:url"),
                "price": meta.get("product:price:amount"),
                "price_currency": meta.get("product:price:currency"),
                "availability": meta.get("product:availability"),
                "credits_labels": credit_values,
            },
        )
    by_hash = {row["observation_sha256"]: row for row in observations}
    return [by_hash[key] for key in sorted(by_hash)]


def route_record(
    response: FetchedResource,
    sitemap_lastmod: str | None,
    discovery: set[str],
    source_timestamp: str,
    sitemap_assets: Iterable[dict[str, Any]] = (),
) -> tuple[dict[str, Any], set[str], list[tuple[str, str]]]:
    parser = PublicHTMLParser(response.final_url)
    parser.feed(decode_text(response.body))
    metadata = parser.public_metadata()
    products, offers, structured_types = parser.structured_summaries()
    sitemap_assets = list(sitemap_assets)
    sitemap_images = [
        {
            "url": row["url"],
            "alt": row.get("alt"),
            "alt_state": row.get("alt_state", "not_applicable"),
            "source": row.get("source", "sitemap:image"),
            "query_redacted": bool(row.get("query_redacted")),
        }
        for row in sitemap_assets
        if row.get("asset_type") == "image"
    ]
    images = normalize_image_rows([*parser.images, *sitemap_images])
    assets = normalize_asset_rows([*parser.assets, *sitemap_assets])
    commerce = commerce_observations(response.requested_url, source_timestamp, metadata, products, offers)
    commerce_for_hash = [
        {key: value for key, value in observation.items() if key != "observed_at"}
        for observation in commerce
    ]
    internal_links = sorted(parser.internal_links)
    external_refs = sorted(set(parser.external_references))
    record: dict[str, Any] = {
        "url": response.requested_url,
        "final_url": response.final_url,
        "path": urllib.parse.urlsplit(response.requested_url).path or "/",
        "status": response.status,
        "content_type": response.content_type,
        "sitemap_lastmod": sitemap_lastmod,
        "discovered_via": sorted(discovery),
        "metadata": metadata,
        "classification": classify_route(response.requested_url, structured_types),
        "structured_data_types": structured_types,
        "images": images,
        "asset_references": assets,
        "products": products,
        "offers": offers,
        "commerce_observations": commerce,
        "internal_links": internal_links,
        "external_domains": sorted({domain for domain, _ in external_refs if domain}),
        "hashes": {
            "content_sha256": sha256_bytes(response.body),
            "metadata_sha256": value_sha256(
                {
                    "metadata": metadata,
                    "classification": classify_route(response.requested_url, structured_types),
                    "structured_data_types": structured_types,
                    "images": images,
                    "asset_references": assets,
                    "products": products,
                    "offers": offers,
                    "commerce_observations": commerce_for_hash,
                    "internal_links": internal_links,
                    "external_references": external_refs,
                }
            ),
        },
    }
    return record, set(internal_links), external_refs


def compute_inventory_hashes(inventory: Mapping[str, Any]) -> dict[str, str]:
    """Compute snapshot and time-independent semantic hashes."""
    snapshot_payload = dict(inventory)
    snapshot_payload.pop("hashes", None)
    semantic_payload = json.loads(json.dumps(snapshot_payload))
    source = semantic_payload.get("source")
    if isinstance(source, dict):
        source.pop("source_timestamp", None)
        source.pop("retrieval_mode", None)

    def strip_observation_times(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("observed_at", None)
            for child in value.values():
                strip_observation_times(child)
        elif isinstance(value, list):
            for child in value:
                strip_observation_times(child)

    strip_observation_times(semantic_payload)
    return {
        "semantic_sha256": value_sha256(semantic_payload),
        "snapshot_sha256": value_sha256(snapshot_payload),
    }


def load_route_index(path: Path, root_origin: str) -> tuple[list[str], dict[str, Any]]:
    """Load the committed dated route observation without treating it as authority."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("registry_id") != "ct.registry.vm.public-route-index.2026-08-26":
        raise ValueError("unsupported Virality route-index registry ID")
    if data.get("classification") != "PUBLIC_FIRST_PARTY_ROUTE_OBSERVATION":
        raise ValueError("route index is not a public first-party observation")
    if data.get("site_origin") != root_origin:
        raise ValueError("route-index origin does not match sitemap origin")
    rows = data.get("routes")
    if not isinstance(rows, list) or data.get("route_count") != len(rows):
        raise ValueError("route-index count contract is invalid")
    urls: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not row["path"].startswith("/"):
            raise ValueError("route-index rows require root-relative paths")
        url, _redacted = sanitize_url(row["path"], base_url=root_origin)
        if url is None or not same_origin(url, root_origin):
            raise ValueError("route-index contains an unsafe path")
        urls.add(url)
    metadata = {
        "registry_id": data["registry_id"],
        "observed_at": data.get("observed_at"),
        "route_count": len(rows),
        "unique_route_count": len(urls),
        "source_capture_sha256": data.get("source_capture_sha256"),
        "observation_only": True,
    }
    return sorted(urls), metadata


def load_xml_estate_index(
    path: Path,
    root_origin: str,
) -> tuple[dict[str, str | None], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Load the dated recovered XML census as a fail-closed continuity seed."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("registry_id") != "ct.registry.vm.public-xml-estate-index.2026-08-26":
        raise ValueError("unsupported Virality XML-estate registry ID")
    if data.get("classification") != "PUBLIC_FIRST_PARTY_SITEMAP_OBSERVATION":
        raise ValueError("XML-estate index is not a public sitemap observation")
    if data.get("site_origin") != root_origin:
        raise ValueError("XML-estate origin does not match sitemap origin")
    rows = data.get("routes")
    unique_images = data.get("unique_images")
    if not isinstance(rows, list) or data.get("route_count") != len(rows):
        raise ValueError("XML-estate route count contract is invalid")
    if not isinstance(unique_images, list) or data.get("unique_image_count") != len(unique_images):
        raise ValueError("XML-estate image count contract is invalid")
    routes: dict[str, str | None] = {}
    assets_by_page: dict[str, list[dict[str, Any]]] = {}
    occurrence_count = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("XML-estate route rows must be objects")
        page_url, _ = sanitize_url(str(row.get("url", "")), base_url=root_origin)
        if page_url is None or not same_origin(page_url, root_origin):
            raise ValueError("XML-estate contains a non-public route URL")
        routes.setdefault(page_url, safe_text(row.get("lastmod"), 80))
        images = row.get("images", [])
        if not isinstance(images, list):
            raise ValueError("XML-estate route images must be a list")
        for image in images:
            if not isinstance(image, dict):
                raise ValueError("XML-estate image rows must be objects")
            image_url, query_redacted = sanitize_url(str(image.get("url", "")), base_url=page_url)
            if image_url is None:
                raise ValueError("XML-estate contains an invalid image URL")
            alt = safe_text(image.get("title"), 500)
            assets_by_page.setdefault(page_url, []).append(
                {
                    "page_url": page_url,
                    "url": image_url,
                    "asset_type": "image",
                    "source": "dated_xml_estate:image",
                    "alt": alt,
                    "alt_state": "present" if alt else "not_applicable",
                    "query_redacted": query_redacted,
                    "observation_status": "public_reference_observed_not_downloaded",
                }
            )
            occurrence_count += 1
    if occurrence_count != data.get("image_occurrence_count"):
        raise ValueError("XML-estate image occurrence count drift")
    for page_url in assets_by_page:
        assets_by_page[page_url].sort(key=lambda row: (row["url"], row.get("alt") or ""))
    metadata = {
        "registry_id": data["registry_id"],
        "observed_date": data.get("observed_date"),
        "route_count": len(rows),
        "unique_image_count": len(unique_images),
        "image_occurrence_count": occurrence_count,
        "source_sha256": data.get("source_sha256"),
        "parse_recovery_required": data.get("parse_recovery_required"),
        "observation_only": True,
    }
    return routes, assets_by_page, metadata


class PublicMeshCrawler:
    def __init__(
        self,
        sitemap_url: str,
        fetcher: Fetcher,
        *,
        source_timestamp: str,
        max_routes: int = DEFAULT_MAX_ROUTES,
        max_sitemaps: int = DEFAULT_MAX_SITEMAPS,
        concurrency: int = DEFAULT_CONCURRENCY,
        route_index_path: Path | None = None,
        xml_estate_index_path: Path | None = None,
    ) -> None:
        sanitized, redacted = sanitize_url(sitemap_url)
        if sanitized is None or redacted:
            raise ValueError("sitemap URL must be an absolute query-free HTTP(S) URL")
        self.sitemap_url = sanitized
        self.root_origin = origin_for(sanitized)
        self.fetcher = fetcher
        self.source_timestamp = utc_timestamp(source_timestamp)
        self.max_routes = max_routes
        self.max_sitemaps = max_sitemaps
        self.concurrency = concurrency
        self.route_index_path = route_index_path
        self.xml_estate_index_path = xml_estate_index_path
        self.failures: list[dict[str, Any]] = []
        self.exclusions: dict[tuple[str, str], dict[str, str]] = {}

    def _exclude(self, url: str, reason: str, discovered_from: str) -> None:
        sanitized, _ = sanitize_url(url)
        row = {
            "url": sanitized or "invalid-url",
            "reason": reason,
            "discovered_from": discovered_from,
        }
        self.exclusions[(row["url"], reason)] = row

    def _load_robots(self) -> tuple[urllib.robotparser.RobotFileParser, dict[str, Any]]:
        robots_url = f"{self.root_origin}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = self.fetcher.fetch(robots_url, purpose="robots")
            parser.parse(decode_text(response.body).splitlines())
            return parser, {
                "url": robots_url,
                "status": response.status,
                "content_type": response.content_type,
                "content_sha256": sha256_bytes(response.body),
                "available": True,
            }
        except CrawlError as exc:
            # Unavailable robots does not manufacture permission for paths in
            # the explicit protected-route denylist.  Standard robotparser
            # behavior permits remaining public paths.
            parser.parse([])
            self.failures.append(stable_failure(robots_url, "robots", exc))
            return parser, {
                "url": robots_url,
                "status": None,
                "content_type": None,
                "content_sha256": None,
                "available": False,
            }

    def _load_sitemaps(
        self,
    ) -> tuple[dict[str, str | None], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        pending = [self.sitemap_url]
        seen: set[str] = set()
        routes: dict[str, str | None] = {}
        documents: list[dict[str, Any]] = []
        assets_by_page: dict[str, list[dict[str, Any]]] = {}
        while pending and len(seen) < self.max_sitemaps:
            sitemap_url = heapq.heappop(pending)
            if sitemap_url in seen:
                continue
            seen.add(sitemap_url)
            if not same_origin(sitemap_url, self.root_origin):
                self._exclude(sitemap_url, "cross_origin_sitemap", "sitemap_index")
                continue
            suffix = Path(urllib.parse.urlsplit(sitemap_url).path).suffix.lower()
            if suffix in BLOCKED_PAGE_SUFFIXES - {".xml"}:
                self._exclude(sitemap_url, "compressed_or_binary_sitemap_not_downloaded", "sitemap_index")
                continue
            try:
                response = self.fetcher.fetch(sitemap_url, purpose="sitemap")
                entries, nested, sitemap_assets, parse_observation = parse_sitemap_document(
                    response.body,
                    response.final_url,
                )
                documents.append(
                    {
                        "url": sitemap_url,
                        "final_url": response.final_url,
                        "status": response.status,
                        "content_type": response.content_type,
                        "content_sha256": sha256_bytes(response.body),
                        "entry_count": len(entries),
                        "nested_sitemap_count": len(nested),
                        "image_reference_count": len(sitemap_assets),
                        "parse_observation": parse_observation,
                    }
                )
                for route_url, lastmod in entries:
                    if not same_origin(route_url, self.root_origin):
                        self._exclude(route_url, "cross_origin_sitemap_entry", sitemap_url)
                    else:
                        routes.setdefault(route_url, lastmod)
                for asset in sitemap_assets:
                    assets_by_page.setdefault(asset["page_url"], []).append(asset)
                for nested_url in nested:
                    if nested_url not in seen:
                        heapq.heappush(pending, nested_url)
            except CrawlError as exc:
                self.failures.append(stable_failure(sitemap_url, "sitemap", exc))
        if pending:
            for sitemap_url in sorted(set(pending)):
                self._exclude(sitemap_url, "sitemap_limit", "sitemap_index")
        for page_url in assets_by_page:
            assets_by_page[page_url].sort(key=lambda row: (row["url"], row["source"], row.get("alt") or ""))
        return routes, sorted(documents, key=lambda row: row["url"]), assets_by_page

    def crawl(self) -> dict[str, Any]:
        robots, robots_record = self._load_robots()
        sitemap_routes, sitemap_documents, sitemap_assets_by_page = self._load_sitemaps()
        xml_estate_metadata: dict[str, Any] | None = None
        xml_estate_urls: set[str] = set()
        if self.xml_estate_index_path:
            xml_routes, xml_assets_by_page, xml_estate_metadata = load_xml_estate_index(
                self.xml_estate_index_path,
                self.root_origin,
            )
            xml_estate_urls = set(xml_routes)
            for url, lastmod in xml_routes.items():
                sitemap_routes.setdefault(url, lastmod)
            for page_url, assets in xml_assets_by_page.items():
                sitemap_assets_by_page.setdefault(page_url, []).extend(assets)
        route_index_metadata: dict[str, Any] | None = None
        route_index_urls: list[str] = []
        if self.route_index_path:
            route_index_urls, route_index_metadata = load_route_index(self.route_index_path, self.root_origin)
            for url in route_index_urls:
                sitemap_routes.setdefault(url, None)
        queue: list[str] = []
        discovery: dict[str, set[str]] = {}
        for url in sorted(sitemap_routes):
            discovery.setdefault(url, set()).add("sitemap")
            heapq.heappush(queue, url)
        for url in route_index_urls:
            discovery.setdefault(url, set()).add("dated_route_index")
        for url in xml_estate_urls:
            discovery.setdefault(url, set()).add("dated_xml_estate_index")

        processed: set[str] = set()
        routes: list[dict[str, Any]] = []
        external_refs_by_page: dict[str, list[tuple[str, str]]] = {}

        def fetch_page(url: str) -> tuple[dict[str, Any], set[str], list[tuple[str, str]]]:
            response = self.fetcher.fetch(url, purpose="page")
            return route_record(
                response,
                sitemap_routes.get(url),
                discovery.get(url, {"internal_link"}),
                self.source_timestamp,
                sitemap_assets_by_page.get(url, []),
            )

        batch_size = max(self.concurrency, self.concurrency * 4)
        with ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix="vm-public-mesh") as executor:
            while queue and (self.max_routes == 0 or len(processed) < self.max_routes):
                batch: list[str] = []
                while queue and len(batch) < batch_size and (self.max_routes == 0 or len(processed) < self.max_routes):
                    url = heapq.heappop(queue)
                    if url in processed:
                        continue
                    processed.add(url)
                    reason = page_policy_reason(url, self.root_origin)
                    if reason:
                        self._exclude(url, reason, ",".join(sorted(discovery.get(url, {"unknown"}))))
                        continue
                    if not robots.can_fetch(USER_AGENT, url):
                        self._exclude(url, "robots_disallowed", ",".join(sorted(discovery.get(url, {"unknown"}))))
                        continue
                    batch.append(url)

                futures = {executor.submit(fetch_page, url): url for url in batch}
                outcomes: dict[str, tuple[dict[str, Any], set[str], list[tuple[str, str]]] | CrawlError] = {}
                for future in as_completed(futures):
                    url = futures[future]
                    try:
                        outcomes[url] = future.result()
                    except CrawlError as exc:
                        outcomes[url] = exc
                    except Exception as exc:  # pragma: no cover - defensive isolation for one public route
                        outcomes[url] = CrawlError("page_parse_error", exc.__class__.__name__)

                for url in sorted(outcomes):
                    outcome = outcomes[url]
                    if isinstance(outcome, CrawlError):
                        self.failures.append(stable_failure(url, "page", outcome))
                        continue
                    record, internal_links, external_refs = outcome
                    routes.append(record)
                    external_refs_by_page[url] = external_refs
                    for target in sorted(internal_links):
                        target_reason = page_policy_reason(target, self.root_origin)
                        if target_reason:
                            self._exclude(target, target_reason, url)
                            continue
                        discovery.setdefault(target, set()).add("internal_link")
                        if target not in processed:
                            heapq.heappush(queue, target)

        if queue:
            for url in sorted(set(queue)):
                self._exclude(url, "route_limit", "crawl_queue")

        routes.sort(key=lambda row: row["url"])
        sitemap_asset_rows = [
            row
            for page_url in sorted(sitemap_assets_by_page)
            for row in sitemap_assets_by_page[page_url]
        ]
        images = self._aggregate_images(routes, sitemap_asset_rows)
        asset_references = self._aggregate_asset_references(routes, sitemap_asset_rows)
        products = self._aggregate_structured(routes, "products")
        offers = self._aggregate_structured(routes, "offers")
        commerce_observation_rows = sorted(
            [observation for route in routes for observation in route["commerce_observations"]],
            key=lambda row: (row["source_route"], row["kind"], row["observation_sha256"]),
        )
        related_domains = self._aggregate_domains(routes, external_refs_by_page, products, offers, sitemap_asset_rows)
        failures = sorted(self.failures, key=lambda row: (row["url"], row["stage"], row["code"]))
        exclusions = sorted(self.exclusions.values(), key=lambda row: (row["url"], row["reason"], row["discovered_from"]))

        inventory: dict[str, Any] = {
            "schema": SCHEMA,
            "inventory_id": INVENTORY_ID,
            "platform_id": PLATFORM_ID,
            "visibility": "public_projection_observation",
            "authority": {
                "authority_class": "D0_observational",
                "creates_rights_or_runtime_authority": False,
                "certifies_availability_or_purchase": False,
            },
            "source": {
                "sitemap_url": self.sitemap_url,
                "origin": self.root_origin,
                "source_timestamp": self.source_timestamp,
                "retrieval_mode": self.fetcher.mode,
                "user_agent": USER_AGENT,
                "robots": robots_record,
                "sitemap_documents": sitemap_documents,
                "dated_route_index": route_index_metadata,
                "dated_xml_estate_index": xml_estate_metadata,
            },
            "policy": {
                "same_origin_page_fetches_only": True,
                "http_method": "GET",
                "queries_and_fragments_retained": False,
                "images_or_binaries_downloaded": False,
                "forms_submitted": False,
                "checkout_or_mutation_routes_followed": False,
                "robots_unavailable_behavior": "record_failure_then_explicit_denylist_and_public_html_only",
                "asset_first_seen_rule": "lexicographically_first_referencing_route",
                "blocked_path_segments": sorted(BLOCKED_PATH_SEGMENTS),
                "blocked_page_suffixes": sorted(BLOCKED_PAGE_SUFFIXES),
                "max_resource_bytes": MAX_RESOURCE_BYTES,
                "max_routes": self.max_routes,
                "max_sitemaps": self.max_sitemaps,
                "concurrency": self.concurrency,
            },
            "summary": {
                "route_count": len(routes),
                "asset_reference_count": len(asset_references),
                "image_reference_count": len(images),
                "product_summary_count": len(products),
                "offer_summary_count": len(offers),
                "commerce_observation_count": len(commerce_observation_rows),
                "related_domain_count": len(related_domains),
                "failure_count": len(failures),
                "excluded_route_count": len(exclusions),
                "category_count": len({category for route in routes for category in route["classification"]["categories"]}),
                "universe_count": len({universe for route in routes for universe in route["classification"]["universes"]}),
            },
            "routes": routes,
            "assets": {"references": asset_references, "images": images},
            "products": products,
            "offers": offers,
            "commerce": {
                "economic_state": "SAFE_HOLD",
                "observation_only": True,
                "checkout_requests_performed": 0,
                "redemption_enabled": False,
                "paid_redeemable": 0,
                "observations": commerce_observation_rows,
            },
            "related_domains": related_domains,
            "failures": failures,
            "excluded_routes": exclusions,
        }
        inventory["hashes"] = compute_inventory_hashes(inventory)
        return inventory

    def _aggregate_images(
        self,
        routes: Iterable[dict[str, Any]],
        sitemap_assets: Iterable[dict[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}
        image_sources: list[tuple[str, dict[str, Any]]] = [
            (route["url"], image)
            for route in routes
            for image in route["images"]
        ]
        image_sources.extend(
            (row["page_url"], row)
            for row in sitemap_assets
            if row.get("asset_type") == "image"
        )
        for page_url, image in image_sources:
            row = aggregate.setdefault(
                image["url"],
                {
                    "url": image["url"],
                    "same_origin": same_origin(image["url"], self.root_origin),
                    "alt_texts": set(),
                    "alt_states": set(),
                    "source_types": set(),
                    "referenced_by": set(),
                    "query_redacted": False,
                },
            )
            if image.get("alt"):
                row["alt_texts"].add(image["alt"])
            row["alt_states"].add(image["alt_state"])
            row["source_types"].add(image["source"])
            row["referenced_by"].add(page_url)
            row["query_redacted"] = row["query_redacted"] or bool(image.get("query_redacted"))
        result: list[dict[str, Any]] = []
        for url in sorted(aggregate):
            row = aggregate[url]
            normalized = {
                "url": url,
                "same_origin": row["same_origin"],
                "alt_texts": sorted(row["alt_texts"]),
                "alt_states": sorted(row["alt_states"]),
                "source_types": sorted(row["source_types"]),
                "referenced_by": sorted(row["referenced_by"]),
                "query_redacted": row["query_redacted"],
            }
            normalized["reference_sha256"] = value_sha256(normalized)
            result.append(normalized)
        return result

    def _aggregate_asset_references(
        self,
        routes: Iterable[dict[str, Any]],
        sitemap_assets: Iterable[dict[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}
        sources: list[tuple[str, dict[str, Any]]] = [
            (route["url"], asset)
            for route in routes
            for asset in route["asset_references"]
        ]
        sources.extend((row["page_url"], row) for row in sitemap_assets)
        for page_url, asset in sources:
            row = aggregate.setdefault(
                asset["url"],
                {
                    "url": asset["url"],
                    "asset_types": set(),
                    "source_types": set(),
                    "referenced_by": set(),
                    "query_redacted": False,
                },
            )
            row["asset_types"].add(asset["asset_type"])
            row["source_types"].add(asset["source"])
            row["referenced_by"].add(page_url)
            row["query_redacted"] = row["query_redacted"] or bool(asset.get("query_redacted"))
        result: list[dict[str, Any]] = []
        for url in sorted(aggregate):
            raw = aggregate[url]
            referenced_by = sorted(raw["referenced_by"])
            row = {
                "url": url,
                "same_origin": same_origin(url, self.root_origin),
                "asset_types": sorted(raw["asset_types"]),
                "source_types": sorted(raw["source_types"]),
                "first_seen_route": referenced_by[0],
                "referenced_by": referenced_by,
                "query_redacted": raw["query_redacted"],
                "observation_status": "public_reference_observed_not_downloaded",
            }
            row["reference_sha256"] = value_sha256(row)
            result.append(row)
        return result

    @staticmethod
    def _aggregate_structured(routes: Iterable[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}
        for route in routes:
            for value in route[field]:
                digest = value_sha256(value)
                row = aggregate.setdefault(digest, {"summary": value, "referenced_by": set()})
                row["referenced_by"].add(route["url"])
        result = []
        for digest in sorted(aggregate):
            result.append(
                {
                    "summary_sha256": digest,
                    "summary": aggregate[digest]["summary"],
                    "referenced_by": sorted(aggregate[digest]["referenced_by"]),
                }
            )
        return result

    def _aggregate_domains(
        self,
        routes: Iterable[dict[str, Any]],
        external_refs_by_page: Mapping[str, list[tuple[str, str]]],
        products: Iterable[dict[str, Any]],
        offers: Iterable[dict[str, Any]],
        sitemap_assets: Iterable[dict[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}

        def add(domain: str, relationship: str, page: str) -> None:
            if not domain or domain == urllib.parse.urlsplit(self.root_origin).hostname:
                return
            row = aggregate.setdefault(domain, {"relationship_types": set(), "referenced_by": set(), "reference_count": 0})
            row["relationship_types"].add(relationship)
            row["referenced_by"].add(page)
            row["reference_count"] += 1

        for page, references in external_refs_by_page.items():
            for domain, relationship in references:
                add(domain, relationship, page)
        for collection in (products, offers):
            for item in collection:
                summary = item["summary"]
                for key in ("url",):
                    value = summary.get(key)
                    if isinstance(value, str):
                        domain = urllib.parse.urlsplit(value).hostname or ""
                        add(domain, "structured_data", item["referenced_by"][0])
                for value in summary.get("images", []):
                    domain = urllib.parse.urlsplit(value).hostname or ""
                    add(domain, "structured_data_image", item["referenced_by"][0])
        for asset in sitemap_assets:
            domain = urllib.parse.urlsplit(asset["url"]).hostname or ""
            add(domain, "sitemap_image", asset["page_url"])

        result: list[dict[str, Any]] = []
        for domain in sorted(aggregate):
            raw = aggregate[domain]
            row = {
                "domain": domain,
                "relationship_types": sorted(raw["relationship_types"]),
                "referenced_by": sorted(raw["referenced_by"]),
                "reference_count": raw["reference_count"],
            }
            row["reference_sha256"] = value_sha256(row)
            result.append(row)
        return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sitemap-url", default=DEFAULT_SITEMAP_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture-dir", type=Path, help="Use fixture-dir/index.json instead of the network")
    parser.add_argument("--route-index", type=Path, help="Optional dated public route-index seed")
    parser.add_argument("--xml-estate-index", type=Path, help="Optional dated recovered XML-estate census seed")
    parser.add_argument("--source-timestamp", help="ISO-8601 observation time; SOURCE_DATE_EPOCH is the fallback")
    parser.add_argument("--max-routes", type=int, default=DEFAULT_MAX_ROUTES)
    parser.add_argument("--max-sitemaps", type=int, default=DEFAULT_MAX_SITEMAPS)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="Bounded parallel page fetches (1-32).",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_routes < 0 or args.max_sitemaps < 1 or not 1 <= args.concurrency <= 32:
        print("max-routes must be >= 0, max-sitemaps positive, and concurrency within 1..32", file=sys.stderr)
        return 2
    try:
        source_timestamp = utc_timestamp(args.source_timestamp)
        root_origin = origin_for(args.sitemap_url)
        fetcher: Fetcher
        if args.fixture_dir:
            fetcher = FixtureFetcher(args.fixture_dir, root_origin)
        else:
            fetcher = NetworkFetcher(root_origin, timeout=args.timeout)
        inventory = PublicMeshCrawler(
            args.sitemap_url,
            fetcher,
            source_timestamp=source_timestamp,
            max_routes=args.max_routes,
            max_sitemaps=args.max_sitemaps,
            concurrency=args.concurrency,
            route_index_path=args.route_index,
            xml_estate_index_path=args.xml_estate_index,
        ).crawl()
        write_json(args.output, inventory)
    except (CrawlError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Virality public mesh crawl failed: {exc}", file=sys.stderr)
        return 1

    summary = inventory["summary"]
    print(
        "Virality public mesh inventory written: "
        f"routes={summary['route_count']} images={summary['image_reference_count']} "
        f"products={summary['product_summary_count']} failures={summary['failure_count']} "
        f"sha256={inventory['hashes']['semantic_sha256']}"
    )
    # A partial inventory is still written for read-only evidence, but a failed
    # sitemap fetch is a hard execution failure rather than a fabricated PASS.
    return 1 if any(item["stage"] == "sitemap" for item in inventory["failures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
