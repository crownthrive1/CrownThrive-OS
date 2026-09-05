#!/usr/bin/env python3
"""Retry relative-sitemap exceptions and emit a corrected governed ingest manifest."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parents[1] / "artifacts/estate-crawl-20260904"
OUT.mkdir(parents=True, exist_ok=True)
UA = "CrownThrive-Governed-Public-Surface-Audit/1.0 (+https://crownthrive.com)"
TARGETS = {
    "crownaffiliates.com": "https://crownaffiliates.com/",
    "thezazabar.xyz": "https://thezazabar.xyz/",
}
SOURCE_COMMIT_SHA = os.getenv("GITHUB_SHA", "local-unversioned")
PROVIDER_RUN_REF = f"github-actions:{os.getenv('GITHUB_RUN_ID', 'local')}"


class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.text.append(value)
            if self.in_title:
                self.title.append(value)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> dict:
    started = time.monotonic()
    try:
        request = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml,text/plain,*/*;q=0.5"})
        with urlopen(request, timeout=20) as response:
            body = response.read(2_000_000)
            return {"status": getattr(response, "status", 200), "final_url": response.geturl(), "body": body,
                    "headers": dict(response.headers.items()), "elapsed_ms": round((time.monotonic()-started)*1000)}
    except HTTPError as error:
        try:
            body = error.read(2_000_000)
        except Exception:
            body = b""
        return {"status": error.code, "final_url": error.geturl() or url, "body": body,
                "headers": dict(error.headers.items()) if error.headers else {}, "error": f"HTTPError:{error.code}",
                "elapsed_ms": round((time.monotonic()-started)*1000)}
    except Exception as error:
        return {"status": None, "final_url": url, "body": b"", "headers": {},
                "error": f"{type(error).__name__}:{str(error)[:300]}",
                "elapsed_ms": round((time.monotonic()-started)*1000)}


def classify(status, final_url, title, text, error):
    sample = f"{final_url} {title} {text[:4000]} {error}".lower()
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
    return "NETWORK_OR_DNS_ERROR" if error else "UNKNOWN"


def inspect(domain: str, root: str) -> dict:
    robots = fetch(urljoin(root, "/robots.txt"))
    robots_text = robots["body"].decode("utf-8", "replace")
    sitemap_urls = []
    for line in robots_text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemap_urls.append(urljoin(root, line.split(":", 1)[1].strip()))
    sitemap_urls.extend((urljoin(root, "/sitemap.xml"), urljoin(root, "/sitemap_index.xml")))
    sitemaps = []
    for sitemap_url in dict.fromkeys(sitemap_urls):
        result = fetch(sitemap_url)
        text = result["body"].decode("utf-8", "replace")
        locations = [unescape(value.strip()) for value in re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.I | re.S)]
        sitemaps.append({"url": sitemap_url, "status": result["status"], "sha256": digest(result["body"]),
                         "location_count": len(locations)})
    result = fetch(root)
    parser = TitleParser()
    try:
        parser.feed(result["body"].decode("utf-8", "replace"))
    except Exception:
        pass
    title = " ".join(parser.title).strip()[:300]
    text = " ".join(parser.text).strip()[:20000]
    content_fingerprint = digest(" ".join(text.split()).lower().encode())
    state = classify(result["status"], result["final_url"], title, text, result.get("error", ""))
    observed = {"domain": domain, "requested_url": root, "final_url": result["final_url"], "status": result["status"],
                "state": state, "binary_sha256": digest(result["body"]), "content_fingerprint": content_fingerprint}
    return {**observed, "checked_at": datetime.now(timezone.utc).isoformat(), "title": title,
            "observation_fingerprint": digest(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()),
            "robots_status": robots["status"], "sitemaps": sitemaps, "error": result.get("error", ""),
            "fingerprint_state": "OBSERVED_NOT_CANONICALLY_BOUND", "entitlement_state": "RECONCILIATION_REQUIRED",
            "dail_state": "HOLD_DAIL_UNBOUND"}


def compact_ingest(result: dict) -> dict:
    identity_seed = f"{result['target_id']}|{result['url']}".encode()
    error = result.get("error") or ""
    return {
        "target_id": result["target_id"], "source_system": result["source"], "requested_url": result["url"],
        "final_url": result.get("final_url"), "subject_identity_ref": "ct.website.subject." + digest(identity_seed),
        "http_status": result.get("root_status"), "availability_state": result["state"],
        "page_title": result.get("root_title") or None, "page_count": result.get("page_count") or 0,
        "robots_status": result.get("robots_status"), "sitemap_count": result.get("sitemap_count") or 0,
        "binary_sha256": result.get("root_binary_sha256") or digest(b""),
        "content_fingerprint": result.get("root_content_fingerprint") or digest(b""),
        "observation_fingerprint": result["observation_fingerprint"],
        "error_class": error.split(":", 1)[0] if error else None, "checked_at": result["checked_at"],
        "metadata": {"target_domain": result.get("domain"), "source_commit_sha": SOURCE_COMMIT_SHA,
                     "provider_run_ref": PROVIDER_RUN_REF, "public_only": True, "mailbox_sources_excluded": True,
                     "retry_corrected": result.get("domain") in TARGETS},
    }


def main():
    retry_results = [inspect(domain, root) for domain, root in TARGETS.items()]
    retry_payload = {"schema": "ct.website-crawl-exception-retry.v1", "target_count": len(retry_results),
                     "results": retry_results, "dail_state": "HOLD_DAIL_UNBOUND"}
    (OUT / "estate-exception-retry.json").write_text(json.dumps(retry_payload, indent=2), encoding="utf-8")
    base = json.loads((OUT / "estate-crawl.json").read_text(encoding="utf-8"))
    by_domain = {result["domain"]: result for result in base["results"]}
    for retry in retry_results:
        current = by_domain[retry["domain"]]
        current.update({"checked_at": retry["checked_at"], "root_status": retry["status"], "final_url": retry["final_url"],
                        "state": retry["state"], "root_title": retry["title"],
                        "root_binary_sha256": retry["binary_sha256"],
                        "root_content_fingerprint": retry["content_fingerprint"],
                        "observation_fingerprint": retry["observation_fingerprint"],
                        "robots_status": retry["robots_status"],
                        "sitemap_count": sum(1 for item in retry["sitemaps"] if item.get("status") and 200 <= item["status"] < 400),
                        "error": retry["error"], "fingerprint_state": retry["fingerprint_state"],
                        "entitlement_state": retry["entitlement_state"], "dail_state": retry["dail_state"],
                        "pages": [], "discovery": {"retry_sitemaps": retry["sitemaps"]}})
    results = sorted(by_domain.values(), key=lambda item: item["domain"])
    counts = Counter(item["state"] for item in results)
    summary = dict(base["summary"])
    summary.update({"checked_at": retry_results[-1]["checked_at"], "target_count": len(results),
                    "responding": counts.get("RESPONDING", 0), "state_counts": dict(counts),
                    "corrected_retry_count": len(retry_results)})
    corrected = {"summary": summary, "results": results}
    (OUT / "estate-crawl-corrected.json").write_text(json.dumps(corrected, indent=2), encoding="utf-8")
    (OUT / "estate-summary-corrected.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    ingest = [compact_ingest(item) for item in results]
    (OUT / "estate-ingest.json").write_text(json.dumps(ingest, separators=(",", ":")), encoding="utf-8")
    manifest = {"schema": "ct.website-crawl-ingest-manifest.v1", "target_count": len(ingest),
                "source_commit_sha": SOURCE_COMMIT_SHA, "provider_run_ref": PROVIDER_RUN_REF,
                "corrected_crawl_sha256": digest((OUT / "estate-crawl-corrected.json").read_bytes()),
                "ingest_sha256": digest((OUT / "estate-ingest.json").read_bytes()),
                "state_counts": dict(counts), "dail_state": "HOLD_DAIL_UNBOUND"}
    (OUT / "estate-ingest-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
