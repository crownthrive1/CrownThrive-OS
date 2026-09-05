#!/usr/bin/env python3
"""Bounded public-only crawl and fingerprint audit for CrownThrive surfaces.

Safety boundaries: no mailbox access, credentials, authenticated routes, form
submission, checkout mutation, upload, or rights inference. Results remain
HOLD_DAIL_UNBOUND until the canonical CHLOM DAIL append/readback succeeds.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
TARGET_FILE = ROOT / "evidence/estate-crawl/crawl-targets-20260904.tsv"
OUT = ROOT / "artifacts/estate-crawl-20260904"
OUT.mkdir(parents=True, exist_ok=True)
UA = "CrownThrive-Governed-Public-Surface-Audit/1.0 (+https://crownthrive.com)"
MAX_BYTES = 2_000_000
MAX_PAGES = 8
TIMEOUT = 12
WORKERS = 8


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.title: list[str] = []
        self.canonical: list[str] = []
        self.text: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "link" and "canonical" in (a.get("rel") or "").lower() and a.get("href"):
            self.canonical.append(a["href"])
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.text.append(value)
            if self._in_title:
                self.title.append(value)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def same_host(left: str, right: str) -> bool:
    a = (urlparse(left).hostname or "").lower().removeprefix("www.")
    b = (urlparse(right).hostname or "").lower().removeprefix("www.")
    return bool(a and b and a == b)


def fetch(url: str, method: str = "GET") -> dict:
    request = Request(
        url,
        method=method,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,*/*;q=0.5",
        },
    )
    started = time.monotonic()
    try:
        with build_opener(HTTPRedirectHandler).open(request, timeout=TIMEOUT) as response:
            body = b"" if method == "HEAD" else response.read(MAX_BYTES + 1)
            truncated = len(body) > MAX_BYTES
            body = body[:MAX_BYTES]
            return {
                "ok": True,
                "status": getattr(response, "status", 200),
                "final_url": response.geturl(),
                "headers": dict(response.headers.items()),
                "body": body,
                "truncated": truncated,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
    except HTTPError as error:
        try:
            body = error.read(MAX_BYTES)
        except Exception:
            body = b""
        return {
            "ok": False,
            "status": error.code,
            "final_url": error.geturl() or url,
            "headers": dict(error.headers.items()) if error.headers else {},
            "body": body,
            "truncated": False,
            "error": f"HTTPError:{error.code}",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    except Exception as error:
        return {
            "ok": False,
            "status": None,
            "final_url": url,
            "headers": {},
            "body": b"",
            "truncated": False,
            "error": f"{type(error).__name__}:{str(error).replace(chr(0), '')[:300]}",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }


def parse_page(result: dict) -> dict:
    body = result["body"]
    content_type = (result["headers"].get("Content-Type") or "").lower()
    title = ""
    canonical = ""
    links: list[str] = []
    text = ""
    if body and ("html" in content_type or body[:100].lstrip().lower().startswith((b"<!doctype html", b"<html"))):
        parser = PageParser()
        try:
            parser.feed(body.decode("utf-8", "replace"))
        except Exception:
            pass
        title = " ".join(parser.title).strip()[:300]
        canonical = (parser.canonical[0] if parser.canonical else "")[:1000]
        text = " ".join(parser.text).strip()[:20000]
        for href in parser.links:
            target = urldefrag(urljoin(result["final_url"], href))[0]
            parsed = urlparse(target)
            if parsed.scheme in ("http", "https") and same_host(target, result["final_url"]):
                links.append(target)
    else:
        text = body.decode("utf-8", "replace").strip()[:20000]
    normalized = " ".join(text.split()).lower().encode("utf-8")
    return {
        "title": title,
        "canonical": canonical,
        "links": sorted(set(links)),
        "text_excerpt": text[:1200],
        "content_type": content_type,
        "bytes": len(body),
        "binary_sha256": sha256(body),
        "content_fingerprint": sha256(normalized),
    }


def discover_robots_and_sitemaps(root: str) -> dict:
    robots_url = urljoin(root, "/robots.txt")
    robots_result = fetch(robots_url)
    robots_text = robots_result["body"].decode("utf-8", "replace") if robots_result["body"] else ""
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.parse(robots_text.splitlines())
        root_allowed = parser.can_fetch(UA, root)
    except Exception:
        root_allowed = True
    sitemap_urls: list[str] = []
    for line in robots_text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemap_urls.append(line.split(":", 1)[1].strip())
    sitemap_urls.extend((urljoin(root, "/sitemap.xml"), urljoin(root, "/sitemap_index.xml")))
    sitemaps = []
    for sitemap_url in dict.fromkeys(sitemap_urls):
        result = fetch(sitemap_url)
        body = result["body"].decode("utf-8", "replace") if result["body"] else ""
        locations = [html.unescape(value.strip()) for value in re.findall(r"<loc>\s*(.*?)\s*</loc>", body, re.I | re.S)]
        sitemaps.append(
            {
                "url": sitemap_url,
                "status": result.get("status"),
                "binary_sha256": sha256(result["body"]),
                "location_count": len(locations),
                "locations": locations[:500],
            }
        )
    return {
        "robots_url": robots_url,
        "robots_status": robots_result.get("status"),
        "robots_binary_sha256": sha256(robots_result["body"]),
        "root_allowed": root_allowed,
        "robot_parser": parser,
        "sitemaps": sitemaps,
    }


def classify(status, title: str, text: str, final_url: str, error: str, allowed: bool) -> str:
    if not allowed:
        return "ROBOTS_BLOCKED"
    sample = f"{title} {text[:4000]} {final_url} {error}".lower()
    if "account suspended" in sample or "suspendedpage.cgi" in sample:
        return "HOSTING_SUSPENDED"
    if any(term in sample for term in ("domain is for sale", "buy this domain", "sedoparking", "hugedomains", "parked free")):
        return "PARKED_OR_FOR_SALE"
    if status in (401, 403):
        return "AUTH_OR_ACCESS_RESTRICTED"
    if status == 404:
        return "NOT_FOUND"
    if status and status >= 500:
        return "SERVER_ERROR"
    if status and 200 <= status < 400:
        return "RESPONDING"
    if error:
        return "NETWORK_OR_DNS_ERROR"
    return "UNKNOWN"


def crawl_target(target: dict) -> dict:
    requested_root = target["url"]
    discovery = discover_robots_and_sitemaps(requested_root)
    if discovery["root_allowed"]:
        root_result = fetch(requested_root)
        if root_result.get("status") is None and requested_root.startswith("https://"):
            fallback = "http://" + requested_root[len("https://") :]
            fallback_result = fetch(fallback)
            if fallback_result.get("status") is not None:
                root_result = fallback_result
    else:
        root_result = fetch(requested_root, method="HEAD")
    root_page = parse_page(root_result)
    seeds: list[str] = []
    for sitemap in discovery["sitemaps"]:
        seeds.extend(url for url in sitemap["locations"] if same_host(url, requested_root))
    if not seeds:
        seeds = root_page["links"]
    queue = deque([requested_root, *seeds])
    visited: set[str] = set()
    pages: list[dict] = []
    while queue and len(pages) < MAX_PAGES:
        url = urldefrag(queue.popleft())[0]
        if url in visited or not same_host(url, requested_root):
            continue
        try:
            allowed = discovery["robot_parser"].can_fetch(UA, url)
        except Exception:
            allowed = True
        if not allowed:
            continue
        visited.add(url)
        result = root_result if not pages and url == requested_root else fetch(url)
        page = root_page if not pages and url == requested_root else parse_page(result)
        pages.append(
            {
                "url": url,
                "status": result.get("status"),
                "final_url": result.get("final_url"),
                "ok": result.get("ok"),
                "elapsed_ms": result.get("elapsed_ms"),
                "error": result.get("error", ""),
                "title": page["title"],
                "canonical": page["canonical"],
                "content_type": page["content_type"],
                "bytes": page["bytes"],
                "binary_sha256": page["binary_sha256"],
                "content_fingerprint": page["content_fingerprint"],
                "truncated": result.get("truncated", False),
            }
        )
        for link in page["links"]:
            if link not in visited and len(queue) < 500:
                queue.append(link)
        time.sleep(0.05)
    status = root_result.get("status")
    state = classify(
        status,
        root_page["title"],
        root_page["text_excerpt"],
        root_result.get("final_url", ""),
        root_result.get("error", ""),
        discovery["root_allowed"],
    )
    observed = {
        "target_id": target["target_id"],
        "requested_url": requested_root,
        "final_url": root_result.get("final_url"),
        "status": status,
        "state": state,
        "root_binary_sha256": root_page["binary_sha256"],
        "root_content_fingerprint": root_page["content_fingerprint"],
        "page_count": len(pages),
    }
    return {
        **target,
        "checked_at": now(),
        "root_status": status,
        "final_url": root_result.get("final_url"),
        "state": state,
        "root_title": root_page["title"],
        "root_binary_sha256": root_page["binary_sha256"],
        "root_content_fingerprint": root_page["content_fingerprint"],
        "observation_fingerprint": sha256(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()),
        "page_count": len(pages),
        "robots_status": discovery["robots_status"],
        "sitemap_count": sum(1 for item in discovery["sitemaps"] if item["status"] and 200 <= item["status"] < 400),
        "entitlement_state": "RECONCILIATION_REQUIRED",
        "fingerprint_state": "OBSERVED_NOT_CANONICALLY_BOUND",
        "dail_state": "HOLD_DAIL_UNBOUND",
        "error": root_result.get("error", ""),
        "pages": pages,
        "discovery": {key: value for key, value in discovery.items() if key != "robot_parser"},
    }


def load_targets() -> list[dict]:
    with TARGET_FILE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for row in rows:
        row["domain"] = (urlparse(row["url"]).hostname or "").lower()
    return rows


def main() -> None:
    targets = load_targets()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(crawl_target, target): target for target in targets}
        for index, future in enumerate(as_completed(futures), 1):
            target = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    **target,
                    "domain": urlparse(target["url"]).hostname or "",
                    "checked_at": now(),
                    "root_status": None,
                    "final_url": target["url"],
                    "state": "CRAWLER_EXCEPTION",
                    "root_title": "",
                    "root_binary_sha256": sha256(b""),
                    "root_content_fingerprint": sha256(b""),
                    "observation_fingerprint": sha256(f"{target['target_id']}|{type(error).__name__}".encode()),
                    "page_count": 0,
                    "robots_status": None,
                    "sitemap_count": 0,
                    "entitlement_state": "RECONCILIATION_REQUIRED",
                    "fingerprint_state": "OBSERVED_NOT_CANONICALLY_BOUND",
                    "dail_state": "HOLD_DAIL_UNBOUND",
                    "error": f"{type(error).__name__}:{str(error)[:300]}",
                    "pages": [],
                    "discovery": {},
                }
            results.append(result)
            print(f"[{index}/{len(targets)}] {result['domain']} -> {result['state']}", flush=True)
    results.sort(key=lambda item: item["domain"])
    states: dict[str, int] = {}
    for result in results:
        states[result["state"]] = states.get(result["state"], 0) + 1
    summary = {
        "schema": "ct.website-crawl-observation.v1",
        "checked_at": now(),
        "target_count": len(results),
        "responding": states.get("RESPONDING", 0),
        "state_counts": states,
        "dail_state": "HOLD_DAIL_UNBOUND",
        "entitlement_state": "RECONCILIATION_REQUIRED",
    }
    (OUT / "estate-crawl.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    (OUT / "estate-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    target_fields = [
        "source", "target_id", "domain", "url", "checked_at", "root_status", "final_url", "state", "root_title",
        "root_binary_sha256", "root_content_fingerprint", "observation_fingerprint", "page_count", "robots_status",
        "sitemap_count", "entitlement_state", "fingerprint_state", "dail_state", "error",
    ]
    with (OUT / "estate-targets.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=target_fields)
        writer.writeheader()
        for result in results:
            writer.writerow({key: result.get(key, "") for key in target_fields})
    page_fields = [
        "target_id", "domain", "url", "status", "final_url", "title", "canonical", "content_type", "bytes",
        "binary_sha256", "content_fingerprint", "elapsed_ms", "error",
    ]
    with (OUT / "estate-pages.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=page_fields)
        writer.writeheader()
        for result in results:
            for page in result["pages"]:
                writer.writerow({"target_id": result["target_id"], "domain": result["domain"], **{key: page.get(key, "") for key in page_fields if key not in ("target_id", "domain")}})
    report = [
        "# CrownThrive Digital Estate Crawl — 2026-09-04", "", f"Checked targets: {len(results)}",
        f"Responding: {summary['responding']}", f"DAIL state: {summary['dail_state']}", "", "## State counts",
    ]
    report.extend(f"- {key}: {value}" for key, value in sorted(states.items()))
    report.extend(("", "## Target ledger", "", "| Domain | State | HTTP | Pages | Observation fingerprint |", "|---|---|---:|---:|---|"))
    for result in results:
        report.append(f"| {result['domain']} | {result['state']} | {result['root_status'] or ''} | {result['page_count']} | `{result['observation_fingerprint']}` |")
    (OUT / "estate-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
