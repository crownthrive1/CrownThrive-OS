#!/usr/bin/env python3
"""Validate the public-safe Collab Portal Secure API adapter manifest.

This validator deliberately checks only non-secret contract metadata. It does not
perform a live authenticated request and must never require production secrets in CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/collab-portal-secure-api.adapter.json"
EXPECTED_SHA256 = "65a59d29859e0ba04993985c7e3bdfcd1d4e07b97f0a17cd9d1683eea6423376"
EXPECTED_BASE_URL = "https://portal.crownthrive.com/secure-api/"
EXPECTED_SWAGGER_URL = "https://portal.crownthrive.com/secure-api/swagger"
EXPECTED_HEADERS = ["X-Public-ID", "X-Secret-Key"]
EXPECTED_OPERATIONS = {
    ("GET", "/contact/meta"),
    ("GET", "/contacts"),
    ("POST", "/contact"),
    ("GET", "/contact/{identifier}"),
    ("PUT", "/contact/{identifier}"),
    ("GET", "/company/meta"),
    ("GET", "/companies"),
    ("POST", "/company"),
    ("GET", "/company/{identifier}"),
    ("PUT", "/company/{identifier}"),
    ("GET", "/project/meta"),
    ("GET", "/projects"),
    ("GET", "/project/{type}/{identifier}"),
    ("PUT", "/project/{type}/{identifier}"),
    ("POST", "/marketing/subscribe"),
    ("GET", "/worlds"),
}
EXPECTED_PM_READS = {
    "GET /project/meta",
    "GET /projects",
    "GET /project/{type}/{identifier}",
}
EXPECTED_PM_WRITE = {"PUT /project/{type}/{identifier}"}
REQUIRED_NOT_EXPOSED = {
    "project_create",
    "task_crud",
    "project_comments",
    "milestone_crud",
    "file_upload",
    "signature_api",
    "webhook_registration",
    "webhook_event_schema",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def main() -> int:
    errors: list[str] = []

    if not MANIFEST.is_file():
        fail(f"Missing adapter manifest: {MANIFEST.relative_to(ROOT)}")
        return 1

    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"Invalid adapter manifest JSON: {exc}")
        return 1

    if data.get("adapter_id") != "ct.adapter.collab-portal.secure.v1":
        errors.append("adapter_id must remain ct.adapter.collab-portal.secure.v1")
    if data.get("platform_id") != "ct.platform.collab-portal":
        errors.append("platform_id must remain ct.platform.collab-portal")
    if data.get("api_id") != "ct.api.collab-portal.secure":
        errors.append("api_id must remain ct.api.collab-portal.secure")
    if data.get("source_id") != "S101":
        errors.append("source_id must remain S101")

    snapshot = data.get("source_snapshot", {})
    if snapshot.get("openapi_version") != "3.0.3":
        errors.append("OpenAPI version must be 3.0.3 for this source snapshot")
    if snapshot.get("swagger_url") != EXPECTED_SWAGGER_URL:
        errors.append("Swagger URL differs from the registered S101 contract")
    if snapshot.get("base_url") != EXPECTED_BASE_URL:
        errors.append("Base URL differs from the registered S101 contract")
    if snapshot.get("sha256") != EXPECTED_SHA256:
        errors.append("S101 snapshot SHA-256 differs from the registered value")

    auth = data.get("authentication", {})
    if auth.get("type") != "paired_api_key_headers":
        errors.append("authentication.type must be paired_api_key_headers")
    if auth.get("headers") != EXPECTED_HEADERS:
        errors.append("authentication headers must be X-Public-ID and X-Secret-Key in order")
    if auth.get("secret_storage") != "server_side_only":
        errors.append("secret_storage must remain server_side_only")
    if auth.get("raw_secret_in_repository") is not False:
        errors.append("raw_secret_in_repository must be false")

    operations = data.get("operations", [])
    actual_operations = {
        (str(item.get("method", "")).upper(), str(item.get("path", "")))
        for item in operations
        if isinstance(item, dict)
    }
    if actual_operations != EXPECTED_OPERATIONS:
        missing = sorted(EXPECTED_OPERATIONS - actual_operations)
        extra = sorted(actual_operations - EXPECTED_OPERATIONS)
        errors.append(f"operation set drifted; missing={missing}, extra={extra}")

    pm_policy = data.get("hourly_pm_policy", {})
    if set(pm_policy.get("allowed_read", [])) != EXPECTED_PM_READS:
        errors.append("hourly PM allowed_read set drifted")
    if set(pm_policy.get("conditional_write", [])) != EXPECTED_PM_WRITE:
        errors.append("hourly PM conditional_write set drifted")

    not_exposed = set(data.get("not_exposed_in_recovered_openapi", []))
    if not REQUIRED_NOT_EXPOSED.issubset(not_exposed):
        errors.append(
            "negative-capability controls are incomplete; missing "
            f"{sorted(REQUIRED_NOT_EXPOSED - not_exposed)}"
        )

    state = data.get("state", {})
    if state.get("contract") != "verified":
        errors.append("contract state must remain verified")
    for pending_key in (
        "production_auth",
        "account_project_meta",
        "institutional_project_uid",
        "authenticated_read",
        "bounded_write",
        "read_after_write",
        "certification",
    ):
        if state.get(pending_key) not in {"pending", "verified", "certified"}:
            errors.append(f"state.{pending_key} must be pending/verified/certified")
    if state.get("webhook_contract") not in {"not_recovered", "verified"}:
        errors.append("state.webhook_contract must be not_recovered or verified")

    # Defensive secret-shape check: this public manifest may name headers and policy,
    # but must never contain raw credential-looking values.
    serialized = json.dumps(data, sort_keys=True)
    forbidden_fragments = ("sk-proj-", "sk_live_", "whsec_", "DummySecretKey")
    for fragment in forbidden_fragments:
        if fragment in serialized:
            errors.append(f"forbidden credential/test-secret fragment present: {fragment}")

    if errors:
        for error in errors:
            fail(error)
        print(f"Collab Portal adapter validation FAILED with {len(errors)} error(s).")
        return 1

    print(
        "Collab Portal adapter validation PASSED: "
        f"{len(actual_operations)} operations, S101 checksum pinned, "
        "PM write remains bounded and production auth remains independently gated."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
