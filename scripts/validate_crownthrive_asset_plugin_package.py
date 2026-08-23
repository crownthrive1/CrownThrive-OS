#!/usr/bin/env python3
"""Validate the Institutional Asset Fabric plugin, runtime and app package."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/crownthrive-institutional-asset-fabric/plugin.manifest.json"
TOOLS = ROOT / "plugins/crownthrive-institutional-asset-fabric/tool-contracts.json"
RUNTIME = ROOT / "developers/manifests/crownthrive-asset-fabric-runtime.v0.1.json"
APP = ROOT / "apps/crownthrive-institutional-asset-fabric/app-manifest.json"
SUBMISSION = ROOT / "apps/crownthrive-institutional-asset-fabric/chatgpt-app-submission.candidate.json"
RESOURCE = ROOT / "apps/crownthrive-institutional-asset-fabric/mcp-resource-manifest.json"
WIDGET = ROOT / "apps/crownthrive-institutional-asset-fabric/widget/index.html"

EXPECTED_TOOLS = {
    "assets.status",
    "assets.search",
    "assets.fetch",
    "assets.blueprints.list",
    "assets.dependencies.plan",
    "assets.compile.plan",
    "assets.verify",
    "assets.risks.scan",
    "assets.supersession.plan",
    "assets.bundles.list",
    "assets.generation.run",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def load(path: Path) -> dict:
    require(path.is_file(), f"Missing artifact: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_false(container: dict, keys: tuple[str, ...], prefix: str) -> None:
    for key in keys:
        require(container[key] is False, f"{prefix}.{key} must remain false")


def main() -> None:
    plugin = load(PLUGIN)
    tools = load(TOOLS)
    runtime = load(RUNTIME)
    app = load(APP)
    submission = load(SUBMISSION)
    resource = load(RESOURCE)
    widget = WIDGET.read_text(encoding="utf-8")

    ids = {plugin["plugin_id"], runtime["plugin_id"], app["plugin_id"], submission["plugin_id"], resource["plugin_id"]}
    require(ids == {"ct.plugin.institutional-asset-fabric"}, "Plugin IDs are not aligned")
    versions = {plugin["version"], runtime["plugin_version"], app["plugin_version"], submission["plugin_version"], resource["plugin_version"]}
    require(versions == {"0.1.0"}, "Plugin versions are not aligned")
    runtime_versions = {runtime["runtime_version"], app["runtime_version"], submission["runtime_version"], resource["runtime_version"]}
    require(runtime_versions == {"0.1.0"}, "Runtime versions are not aligned")

    require(plugin["state"] == "controlled_test", "Plugin must remain controlled test")
    require(plugin["public_submission_state"] == "not_submitted", "Plugin submission state drift")
    require(runtime["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "Runtime must remain controlled-test/HOLD")
    require(app["state"] == "candidate_not_submitted", "App must remain candidate/not submitted")
    require(submission["state"] == "candidate_not_submitted", "Submission packet must remain candidate")
    require(resource["state"] == "candidate", "Resource must remain candidate")

    assert_false(plugin["security"], (
        "secret_export", "private_identity_export", "protected_kernel_export", "service_role_access_from_widget",
        "arbitrary_command_execution", "opaque_native_binary_generation", "provider_write_enabled", "direct_main_merge",
        "originator_self_certification", "D3_auto", "sovereign_vote_effect",
    ), "plugin.security")
    assert_false(runtime["runtime_controls"], (
        "arbitrary_command_execution", "opaque_native_binary_execution", "provider_write_enabled", "direct_main_merge",
        "secret_export", "private_identity_export", "protected_kernel_export", "service_role_access_from_widget",
        "D3_auto", "sovereign_vote_effect",
    ), "runtime.runtime_controls")
    assert_false(app["execution"], (
        "arbitrary_command_execution", "opaque_native_binary_generation", "provider_write_enabled", "direct_main_merge",
        "D3_auto", "sovereign_vote_effect",
    ), "app.execution")
    assert_false(submission["execution"], (
        "arbitrary_command_execution", "opaque_native_binary_generation", "provider_write_enabled", "direct_main_merge",
        "D3_auto", "sovereign_vote_effect",
    ), "submission.execution")

    assert_false(plugin["commerce"], ("checkout_enabled", "entitlement_active", "exact_prices_authorized", "seller_payouts_authorized"), "plugin.commerce")
    assert_false(app["commerce"], ("checkout_enabled", "entitlement_active", "exact_prices_authorized", "seller_payouts_authorized"), "app.commerce")
    assert_false(submission["commerce"], ("checkout_enabled", "entitlement_active", "exact_prices_authorized", "seller_payouts_authorized"), "submission.commerce")

    require(set(plugin["tools"]) == EXPECTED_TOOLS, "Plugin tool set drift")
    require({tool["name"] for tool in tools["tools"]} == EXPECTED_TOOLS, "Tool-contract set drift")
    require({tool["name"] for tool in app["tools"]} == EXPECTED_TOOLS, "App tool set drift")
    require(set(submission["read_tools"]) | set(submission["governed_tools"]) == EXPECTED_TOOLS, "Submission tool set drift")

    for tool in tools["tools"]:
        annotations = tool["annotations"]
        require(annotations["destructiveHint"] is False, f"Destructive hint enabled: {tool['name']}")
        require(annotations["idempotentHint"] is True, f"Idempotency hint missing: {tool['name']}")
        require(annotations["openWorldHint"] is False, f"Open-world hint enabled: {tool['name']}")
        require(tool["input_schema"].get("additionalProperties") is False, f"Tool schema is not closed: {tool['name']}")

    require(runtime["deployment_readback"]["function_status"] == "ACTIVE", "Edge function record must be active")
    require(runtime["deployment_readback"]["authenticated_external_canary"] == "pending", "External canary must not be fabricated")
    require(runtime["deployment_readback"]["authenticated_resource_readback"] == "pending", "Resource canary must not be fabricated")
    require(runtime["lifecycle"]["installed"] is False, "Runtime installation cannot be claimed")
    require(runtime["lifecycle"]["submitted"] is False, "Runtime submission cannot be claimed")
    require(runtime["lifecycle"]["published"] is False, "Runtime publication cannot be claimed")

    require(resource["resource_uri"] == runtime["resource_uri"] == app["widget_resource_uri"] == submission["widget_resource_uri"], "Resource URI mismatch")
    require(resource["security"]["connect_domains"] == [], "Widget connect domains must be empty")
    require(resource["security"]["resource_domains"] == [], "Widget resource domains must be empty")
    assert_false(resource["security"], (
        "secret_access", "service_role_access", "private_identity_access", "protected_kernel_access", "direct_database_access",
    ), "resource.security")
    require(resource["submission"]["submitted"] is False and resource["submission"]["published"] is False, "Widget cannot be submitted or published")

    for token in ("SUPABASE_SERVICE_ROLE_KEY", "OPENAI_API_KEY", "vault.decrypted_secrets", "private_subject_ids", "Authorization: Bearer", "child_process", "subprocess"):
        require(token not in widget, f"Widget contains forbidden implementation token: {token}")
    require("window.openai" in widget, "Widget must use the host bridge")
    require("fetch(" not in widget, "Widget must not issue direct network requests")
    require("aria-live" in widget, "Widget live status missing")
    require("prefers-reduced-motion" in widget, "Widget reduced-motion support missing")

    require(plugin["estate"]["candidate_blueprints"] == 4000, "Plugin blueprint count drift")
    require(plugin["estate"]["curated_asset_records"] == 456, "Plugin curated-asset count drift")
    require(plugin["estate"]["plugins"] == 32 and plugin["estate"]["pallets"] == 24 and plugin["estate"]["kernels"] == 16, "Core package counts drift")

    print("CrownThrive Institutional Asset Fabric plugin package invariants: PASS")
    print("authenticated_external_canary=pending")
    print("submission_state=candidate_not_submitted")
    print("provider_write_enabled=false")
    print("arbitrary_command_execution=false")


if __name__ == "__main__":
    main()
