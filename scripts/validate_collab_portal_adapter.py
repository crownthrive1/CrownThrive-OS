#!/usr/bin/env python3
"""Validate the historical/public-safe Collab Portal S101/S102/S105 source contract.

This validator is intentionally a source-lineage validator, not a designated-current
provider-state validator. It checks only non-secret institutional contract metadata,
never performs a live authenticated request, and must never require production
secrets in CI. S101 is the recovered Secure API/OpenAPI source, S102 is first-party
webhook UI evidence, and S105 records the historical server-side Vault-capable
runtime-v2 certification state. Current Collab provider truth is validated separately
by scripts/validate_phase_namespace_and_api_control.py against
ct.manifest.api-mcp-current-control-state.v1.
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
EXPECTED_PROJECT_EVENTS = ["Project Created", "Project Updated", "Project Deleted"]
EXPECTED_RUNTIME_READS = {"health", "project_meta", "list_projects", "find_project"}
EXPECTED_RUNTIME_WRITE_FIELDS = {"status", "info_description", "project_custom_fields"}
EXPECTED_RELATED_SOURCES = ["S102", "S105"]
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
    (ROOT / "knowledge/source-register.mdx", "| `S105` |"),
    (ROOT / "technology/collab-portal-and-signatures.mdx", "secure_runtime_version: 2"),
    (ROOT / "technology/collab-portal-and-signatures.mdx", "screenshot_transcription_result: not_character_exact"),
    (ROOT / "knowledge/current-state-validation-queue.mdx", "`S105` advances the Supabase runtime"),
    (ROOT / "developers/api-base-url-and-endpoint-seed-register.mdx", "secure_runtime: active_v2_vault_capable"),
    (ROOT / "developers/collab-portal-secure-api-adapter.mdx", "runtime_version: 2"),
    (ROOT / "developers/collab-portal-secure-api-adapter.mdx", "screenshot_transcription_auth_failed"),
    (ROOT / "changelog/phase-2-99-collab-runtime-v2-vault-certification.mdx", "classification: screenshot_transcription_auth_failed"),
    (ROOT / "automation/institutional-hourly-agent-relay.mdx", "Agent A — Orchestrator & Integrator"),
]
FORBIDDEN_CURRENT_DOC_FRAGMENTS = [
    (ROOT / "technology/collab-portal-and-signatures.mdx", "webhook_contract_recovered: false"),
    (ROOT / "developers/api-base-url-and-endpoint-seed-register.mdx", "webhook_contract: not_recovered"),
    (ROOT / "developers/collab-portal-secure-api-adapter.mdx", "active_fail_closed_unconfigured"),
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
    if data.get("related_source_ids") != EXPECTED_RELATED_SOURCES:
        errors.append("related_source_ids must pin S102 and S105 separately from S101")

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
    if auth.get("production_credential_binding") != "pending_exact_secure_copy":
        errors.append("historical S105 production credential binding must remain pending_exact_secure_copy")

    operations = data.get("operations", [])
    actual_operations = {
        (str(item.get("method", "")).upper(), str(item.get("path", "")))
        for item in operations if isinstance(item, dict)
    }
    if actual_operations != EXPECTED_OPERATIONS:
        errors.append(
            f"operation set drifted; missing={sorted(EXPECTED_OPERATIONS - actual_operations)}, "
            f"extra={sorted(actual_operations - EXPECTED_OPERATIONS)}"
        )

    pm_policy = data.get("hourly_pm_policy", {})
    if set(pm_policy.get("allowed_read", [])) != EXPECTED_PM_READS:
        errors.append("hourly PM allowed_read set drifted")
    if set(pm_policy.get("conditional_write", [])) != EXPECTED_PM_WRITE:
        errors.append("hourly PM conditional_write set drifted")

    not_exposed = set(data.get("not_exposed_in_recovered_openapi", []))
    if not REQUIRED_NOT_EXPOSED.issubset(not_exposed):
        errors.append(f"S101 negative-capability controls are incomplete; missing {sorted(REQUIRED_NOT_EXPOSED - not_exposed)}")

    webhook = data.get("webhook_evidence", {})
    if webhook.get("source_id") != "S102":
        errors.append("webhook_evidence.source_id must remain S102")
    if webhook.get("evidence_type") != "current_first_party_ui":
        errors.append("S102 evidence_type must remain current_first_party_ui for the historical captured source")
    if webhook.get("ui_contract") != "verified" or webhook.get("endpoint_configuration_ui") != "verified":
        errors.append("S102 webhook UI and endpoint configuration must remain verified in the captured source")
    if webhook.get("project_events") != EXPECTED_PROJECT_EVENTS:
        errors.append("S102 Project event identities/order drifted")
    if webhook.get("project_payload_selector") != "verified":
        errors.append("project payload selector must remain verified from S102")
    if webhook.get("project_created_preview_payload") != "observed":
        errors.append("Project Created preview payload evidence must remain observed")
    if webhook.get("preview_uid_binding") != "unverified_sample_preview":
        errors.append("preview UID must remain unverified_sample_preview in historical S102 evidence")
    if webhook.get("authoritative_event_source") is not False:
        errors.append("historical webhook evidence must not become authoritative")
    require_pending(
        errors,
        webhook,
        ("sender_integrity", "delivery_attempt_identity", "retry_contract", "replay_contract", "timeout_dead_letter_contract", "receiver_idempotency", "receiver_certification"),
        "historical_webhook_evidence",
    )

    runtime = data.get("runtime", {})
    if runtime.get("provider") != "Supabase Edge Functions":
        errors.append("runtime.provider must remain Supabase Edge Functions")
    if runtime.get("function") != "collab-portal-pm":
        errors.append("runtime.function must remain collab-portal-pm")
    if runtime.get("version") != 2:
        errors.append("runtime.version must remain 2 for the captured S105 runtime release")
    if runtime.get("state") != "active_vault_capable_read_certification_blocked_on_exact_credential_copy":
        errors.append("historical runtime.state must preserve the S105 exact-credential-copy blocker")
    if runtime.get("caller_authentication") != "Supabase JWT required":
        errors.append("runtime caller authentication must remain Supabase JWT required")
    if runtime.get("collab_portal_credentials_in_source") is not False:
        errors.append("Collab Portal credentials must not be present in runtime source")
    if set(runtime.get("secret_sources", [])) != {"managed_environment", "supabase_vault_service_role_bridge"}:
        errors.append("runtime secret_sources must preserve environment + service-role Vault options")
    if runtime.get("vault_bridge") != "verified_service_role_only":
        errors.append("runtime Vault bridge must remain service-role only")
    if runtime.get("server_side_secret_binding") != "vault_path_verified_exact_value_pending":
        errors.append("historical runtime secret binding must preserve exact-value-pending state")
    if runtime.get("write_gate_default") != "closed":
        errors.append("runtime write gate must default closed")
    if set(runtime.get("allowed_read_actions", [])) != EXPECTED_RUNTIME_READS:
        errors.append("runtime allowed_read_actions drifted")
    if runtime.get("conditional_write_action") != "update_project_status":
        errors.append("runtime conditional write action drifted")
    if set(runtime.get("conditionally_allowed_fields", [])) != EXPECTED_RUNTIME_WRITE_FIELDS:
        errors.append("runtime conditionally allowed write fields drifted")
    if runtime.get("read_before_write") is not True or runtime.get("read_after_write") is not True:
        errors.append("runtime must require read-before-write and read-after-write")
    if runtime.get("blind_mutation_retry") is not False:
        errors.append("runtime must prohibit blind mutation retry")

    attempt = runtime.get("read_only_certification_attempt", {})
    if attempt.get("action") != "GET /project/meta":
        errors.append("S105 certification attempt must identify GET /project/meta")
    if attempt.get("provider_reached") is not True or attempt.get("http_status") != 401:
        errors.append("S105 certification evidence must preserve provider-reached HTTP 401 observation")
    if attempt.get("classification") != "screenshot_transcription_auth_failed":
        errors.append("S105 certification attempt classification drifted")
    if attempt.get("provider_key_invalid_established") is not False:
        errors.append("S105 must not classify the actual provider key as invalid")
    if attempt.get("write_attempted") is not False:
        errors.append("S105 must preserve that no write was attempted")

    state = data.get("state", {})
    if state.get("contract") != "verified":
        errors.append("historical source contract state must remain verified")
    if state.get("base_url") != "verified_from_openapi":
        errors.append("state.base_url must remain verified_from_openapi")
    if state.get("auth_header_contract") != "verified_from_openapi":
        errors.append("state.auth_header_contract must remain verified_from_openapi")
    if state.get("secure_runtime") != "verified_v2_vault_capable":
        errors.append("historical state.secure_runtime must remain verified_v2_vault_capable")
    if state.get("vault_binding_path") != "verified":
        errors.append("state.vault_binding_path must remain verified")
    if state.get("exact_secure_credential_copy") != "pending":
        errors.append("historical exact secure credential copy must remain pending")
    require_pending(
        errors,
        state,
        ("production_auth", "account_project_meta", "institutional_project_uid", "authenticated_read", "bounded_write", "read_after_write", "webhook_sender_integrity", "webhook_delivery_semantics", "webhook_receiver_certification", "certification"),
        "historical_state",
    )
    if state.get("webhook_ui_contract") != "verified":
        errors.append("state.webhook_ui_contract must remain verified from S102")
    if "webhook_contract" in state:
        errors.append("legacy state.webhook_contract is ambiguous; use separate S101/S102 webhook fields")

    for path, fragment in DOCUMENT_REQUIREMENTS:
        if not path.is_file():
            errors.append(f"required source-lineage document missing: {path.relative_to(ROOT)}")
        elif fragment not in path.read_text(encoding="utf-8"):
            errors.append(f"required S102/S105/runtime lineage fragment {fragment!r} missing from {path.relative_to(ROOT)}")

    for path, fragment in FORBIDDEN_CURRENT_DOC_FRAGMENTS:
        if path.is_file() and fragment in path.read_text(encoding="utf-8"):
            errors.append(f"stale source-lineage fragment {fragment!r} remains in {path.relative_to(ROOT)}")

    serialized = json.dumps(data, sort_keys=True)
    forbidden_fragments = ("sk-proj-", "sk_live_", "whsec_", "DummySecretKey", "$2y$13$")
    for fragment in forbidden_fragments:
        if fragment in serialized:
            errors.append(f"forbidden credential/test-secret fragment present: {fragment}")

    if errors:
        for error in errors:
            fail(error)
        print(f"Collab Portal historical S101/S102/S105 source-contract validation FAILED with {len(errors)} error(s).")
        return 1

    print(
        "Collab Portal historical S101/S102/S105 source-contract validation PASSED: "
        f"{len(actual_operations)} S101 operations pinned; captured S102 UI/events and S105 runtime-v2/Vault lineage preserved. "
        "This result is not current provider certification; designated-current Collab truth is validated separately."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
