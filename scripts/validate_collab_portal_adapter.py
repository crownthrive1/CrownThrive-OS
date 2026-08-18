#!/usr/bin/env python3
"""Validate the public-safe Collab Portal adapter, webhook evidence, and runtime state.

This validator checks only non-secret institutional contract metadata. It never
performs a live authenticated request and must never require production secrets in CI.
S101 remains the Secure API/OpenAPI source; S102 is separately pinned as current
first-party webhook UI evidence.
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
EXPECTED_PROJECT_EVENTS = [
    "Project Created",
    "Project Updated",
    "Project Deleted",
]
EXPECTED_RUNTIME_READS = {"health", "project_meta", "find_project"}
EXPECTED_RUNTIME_WRITE_FIELDS = {"status", "info_description", "project_custom_fields"}
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
DOCUMENT_REQUIREMENTS = [
    (ROOT / "knowledge/source-register.mdx", "| `S102` |"),
    (ROOT / "technology/collab-portal-and-signatures.mdx", "webhook_ui_contract_verified: true"),
    (ROOT / "knowledge/current-state-validation-queue.mdx", "`S102` separately verifies"),
    (ROOT / "developers/api-base-url-and-endpoint-seed-register.mdx", "webhook_ui_contract: verified_s102"),
    (ROOT / "developers/collab-portal-secure-api-adapter.mdx", "source_id: S102"),
    (ROOT / "changelog/phase-2-99-s102-webhook-state-reconciliation.mdx", "s102_webhook_ui_state_synchronized: required_pass"),
]
FORBIDDEN_CURRENT_DOC_FRAGMENTS = [
    (ROOT / "technology/collab-portal-and-signatures.mdx", "webhook_contract_recovered: false"),
    (ROOT / "developers/api-base-url-and-endpoint-seed-register.mdx", "webhook_contract: not_recovered"),
]


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def require_pending(errors: list[str], mapping: dict, keys: tuple[str, ...], prefix: str) -> None:
    for key in keys:
        if mapping.get(key) != "pending":
            errors.append(f"{prefix}.{key} must remain pending until independently certified")


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
    if data.get("related_source_ids") != ["S102"]:
        errors.append("related_source_ids must pin S102 separately from S101")

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
            "S101 negative-capability controls are incomplete; missing "
            f"{sorted(REQUIRED_NOT_EXPOSED - not_exposed)}"
        )

    webhook = data.get("webhook_evidence", {})
    if webhook.get("source_id") != "S102":
        errors.append("webhook_evidence.source_id must remain S102")
    if webhook.get("evidence_type") != "current_first_party_ui":
        errors.append("S102 evidence_type must remain current_first_party_ui")
    if webhook.get("ui_contract") != "verified":
        errors.append("S102 webhook UI contract must remain verified")
    if webhook.get("endpoint_configuration_ui") != "verified":
        errors.append("webhook endpoint configuration UI must remain verified")
    if webhook.get("project_events") != EXPECTED_PROJECT_EVENTS:
        errors.append("S102 Project event identities/order drifted")
    if webhook.get("project_payload_selector") != "verified":
        errors.append("project payload selector must remain verified from S102")
    if webhook.get("project_created_preview_payload") != "observed":
        errors.append("Project Created preview payload evidence must remain observed")
    if webhook.get("preview_uid_binding") != "unverified_sample_preview":
        errors.append("preview UID must remain unverified_sample_preview until authenticated lookup")
    if webhook.get("authoritative_event_source") is not False:
        errors.append("webhook must not become an authoritative event source before certification")
    require_pending(
        errors,
        webhook,
        (
            "sender_integrity",
            "delivery_attempt_identity",
            "retry_contract",
            "replay_contract",
            "timeout_dead_letter_contract",
            "receiver_idempotency",
            "receiver_certification",
        ),
        "webhook_evidence",
    )

    runtime = data.get("runtime", {})
    if runtime.get("provider") != "Supabase Edge Functions":
        errors.append("runtime.provider must remain Supabase Edge Functions for v1")
    if runtime.get("function") != "collab-portal-pm":
        errors.append("runtime.function must remain collab-portal-pm")
    if runtime.get("version") != 1:
        errors.append("runtime.version must remain 1 until a versioned runtime change is recorded")
    if runtime.get("state") != "active_fail_closed_unconfigured":
        errors.append("runtime.state must remain active_fail_closed_unconfigured before secret binding")
    if runtime.get("caller_authentication") != "Supabase JWT required":
        errors.append("runtime caller authentication must remain Supabase JWT required")
    if runtime.get("collab_portal_credentials_in_source") is not False:
        errors.append("Collab Portal credentials must not be present in runtime source")
    if runtime.get("server_side_secret_binding") != "pending_external_secret_configuration":
        errors.append("runtime secret binding must remain pending_external_secret_configuration")
    if runtime.get("write_gate_default") != "closed":
        errors.append("runtime write gate must default closed")
    if set(runtime.get("allowed_read_actions", [])) != EXPECTED_RUNTIME_READS:
        errors.append("runtime allowed_read_actions drifted")
    if runtime.get("conditional_write_action") != "update_project_status":
        errors.append("runtime conditional write action drifted")
    if set(runtime.get("conditionally_allowed_fields", [])) != EXPECTED_RUNTIME_WRITE_FIELDS:
        errors.append("runtime conditionally allowed write fields drifted")
    if runtime.get("read_before_write") is not True:
        errors.append("runtime must require read_before_write")
    if runtime.get("read_after_write") is not True:
        errors.append("runtime must require read_after_write")
    if runtime.get("blind_mutation_retry") is not False:
        errors.append("runtime must prohibit blind mutation retry")

    state = data.get("state", {})
    if state.get("contract") != "verified":
        errors.append("contract state must remain verified")
    if state.get("base_url") != "verified_from_openapi":
        errors.append("state.base_url must remain verified_from_openapi")
    if state.get("auth_header_contract") != "verified_from_openapi":
        errors.append("state.auth_header_contract must remain verified_from_openapi")
    require_pending(
        errors,
        state,
        (
            "production_auth",
            "account_project_meta",
            "institutional_project_uid",
            "authenticated_read",
            "bounded_write",
            "read_after_write",
            "webhook_sender_integrity",
            "webhook_delivery_semantics",
            "webhook_receiver_certification",
            "certification",
        ),
        "state",
    )
    if state.get("webhook_ui_contract") != "verified":
        errors.append("state.webhook_ui_contract must remain verified from S102")
    if "webhook_contract" in state:
        errors.append("legacy state.webhook_contract is ambiguous; use separate S101/S102 webhook fields")

    for path, fragment in DOCUMENT_REQUIREMENTS:
        if not path.is_file():
            errors.append(f"required current-state document missing: {path.relative_to(ROOT)}")
            continue
        if fragment not in path.read_text(encoding="utf-8"):
            errors.append(
                f"required S102/runtime fragment {fragment!r} missing from {path.relative_to(ROOT)}"
            )

    for path, fragment in FORBIDDEN_CURRENT_DOC_FRAGMENTS:
        if path.is_file() and fragment in path.read_text(encoding="utf-8"):
            errors.append(
                f"stale current-state fragment {fragment!r} remains in {path.relative_to(ROOT)}"
            )

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
        f"{len(actual_operations)} S101 operations pinned, S102 webhook UI/events synchronized, "
        "Supabase runtime fail-closed, sender/delivery certification pending, PM write bounded."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
