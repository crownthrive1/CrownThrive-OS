#!/usr/bin/env python3
"""Validate runtime 0.3 MCP resource and successor submission boundaries."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "developers/manifests/crownthrive-interoperability-runtime.v0.3.json"
SUBMISSION = ROOT / "apps/crownthrive-interoperability-plugin/chatgpt-app-submission.candidate.v0.2.json"
RESOURCE = ROOT / "apps/crownthrive-interoperability-plugin/mcp-resource-manifest.json"
WIDGET = ROOT / "apps/crownthrive-interoperability-plugin/widget/index.html"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    submission = json.loads(SUBMISSION.read_text(encoding="utf-8"))
    resource = json.loads(RESOURCE.read_text(encoding="utf-8"))
    widget = WIDGET.read_text(encoding="utf-8")

    require(runtime["runtime_version"] == "0.3.0", "runtime 0.3 required")
    require(runtime["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "runtime must remain controlled-test/HOLD")
    require(runtime["mcp"]["resources_list"] is True, "resources/list support missing")
    require(runtime["mcp"]["resources_read"] is True, "resources/read support missing")
    require(runtime["mcp"]["tool_annotations"] is True, "tool annotations missing")
    require(runtime["mcp"]["widget_resource_uri"].startswith("ui://"), "UI resource URI required")
    require(runtime["security"]["service_role_access_from_widget"] is False, "widget cannot access service role")
    require(runtime["security"]["secret_export"] is False, "secret export must remain disabled")
    require(runtime["security"]["private_identity_export"] is False, "private identity export must remain disabled")
    require(runtime["current_proof"]["plugin_installed"] is False, "installation must not be claimed")
    require(runtime["current_proof"]["plugin_submitted"] is False, "submission must not be claimed")
    require(runtime["current_proof"]["plugin_published"] is False, "publication must not be claimed")

    require(submission["submission_packet_id"] == "ct.plugin-submission.interoperability-chatgpt.v0.2", "unexpected packet ID")
    require(submission["supersedes"] == "ct.plugin-submission.interoperability-chatgpt.v0.1", "supersession history missing")
    require(submission["runtime_version"] == "0.3.0", "submission/runtime version mismatch")
    require(submission["state"] == "candidate_not_submitted", "submission must remain a candidate")
    require(submission["submitted"] is False and submission["published"] is False, "submission/publication cannot be claimed")
    require(submission["mcp_capabilities"]["resources"] is True, "submission must bind MCP resources")
    require(submission["privacy"]["service_role_access_from_widget"] is False, "widget service-role access prohibited")
    require(submission["commerce"]["checkout_enabled"] is False, "checkout must remain disabled")
    require(submission["commerce"]["entitlement_active"] is False, "entitlement must remain inactive")

    require(resource["resource_uri"] == runtime["mcp"]["widget_resource_uri"], "resource URI mismatch")
    require(resource["security"]["network_domains"] == [], "widget should not request external network domains")
    require(resource["security"]["resource_domains"] == [], "widget should not request external resource domains")
    require(resource["security"]["secret_access"] is False, "widget secret access prohibited")
    require(resource["submission"]["submitted"] is False, "resource submission must remain false")

    forbidden = ("SUPABASE_SERVICE_ROLE_KEY", "OPENAI_API_KEY", "vault.decrypted_secrets", "private_subject_ids", "Authorization: Bearer")
    for token in forbidden:
        require(token not in widget, f"widget contains forbidden token: {token}")
    require("window.openai" in widget, "widget must use the host bridge")
    require("aria-live" in widget, "live status region required")
    require("prefers-reduced-motion" in widget, "reduced-motion support required")

    print("CrownThrive Interoperability Runtime 0.3 invariants: PASS")


if __name__ == "__main__":
    main()
