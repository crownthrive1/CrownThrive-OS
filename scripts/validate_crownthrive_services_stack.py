#!/usr/bin/env python3
"""Validate public-safe CrownThrive Services Stack invariants."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/crownthrive-services-stack.v1.json"
COMMERCIAL = ROOT / "developers/manifests/crownthrive-services-stack-commercialization.v1.json"
PLUGIN = ROOT / "plugins/crownthrive-services-stack/plugin.manifest.json"
TOOLS = ROOT / "plugins/crownthrive-services-stack/tool-contracts.json"
APP = ROOT / "apps/crownthrive-services-stack/app-manifest.json"
RESOURCE = ROOT / "apps/crownthrive-services-stack/mcp-resource-manifest.v0.1.json"
SUBMISSION = ROOT / "apps/crownthrive-services-stack/chatgpt-app-submission.candidate.v0.1.json"
EVIDENCE = ROOT / "data/css/css-controlled-test-evidence.v1.json"
WIDGET = ROOT / "apps/crownthrive-services-stack/widget/index.html"
EDGE = ROOT / "apps/crownthrive-services-stack/edge/index.ts"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    commercial = json.loads(COMMERCIAL.read_text())
    plugin = json.loads(PLUGIN.read_text())
    tools = json.loads(TOOLS.read_text())
    app = json.loads(APP.read_text())
    resource = json.loads(RESOURCE.read_text())
    submission = json.loads(SUBMISSION.read_text())
    evidence = json.loads(EVIDENCE.read_text())
    widget = WIDGET.read_text()
    edge = EDGE.read_text()

    require(manifest["framework_id"] == "ct.framework.crownthrive-services-stack", "framework ID drift")
    require(manifest["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "framework must remain controlled-test/HOLD")
    require(len(manifest["service_ids"]) == 14, "fourteen services required")
    expected = {"services":14,"contracts":14,"provider_bindings":32,"service_dependencies":35,"profiles":5,"profile_modules":57,"platform_profile_bindings":29,"service_assets":120,"vault_assets":22,"vaulted_service_assets":48,"algorithms":2,"agents":7,"skills":7,"mcp_tools":13,"provider_exit_plans":32}
    for key, value in expected.items():
        require(manifest["counts"][key] == value, f"count drift: {key}")
    for key in ("public_activation","installed","submitted","published","provider_write_enabled","checkout_enabled","entitlement_active","legal_compliance_certification","professional_certification","D3_auto","sovereign_vote_effect","direct_main_merge"):
        require(manifest[key] is False, f"{key} must remain false")
    require(manifest["security_suite"]["passed"] == 12 and manifest["security_suite"]["failed"] == 0, "security suite mismatch")
    require(manifest["caas_canaries"] == {"ALLOW":1,"HOLD":1,"DENY":1,"authority_leaks":0}, "CaaS canary mismatch")
    require(plugin["plugin_id"] == app["plugin_id"] == resource["plugin_id"] == submission["plugin_id"], "plugin ID mismatch")
    require(plugin["server_id"] == app["mcp_server_id"] == submission["mcp_server_id"], "MCP server mismatch")
    require(plugin["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "plugin state drift")
    for key in ("installed","submitted","published","checkout_enabled","entitlement_active","provider_write_enabled","raw_secret_export","private_identity_export","protected_policy_export","D3_auto","sovereign_vote_effect","direct_main_merge"):
        require(plugin[key] is False, f"plugin {key} must remain false")
    tool_names = {item["name"] for item in tools["tools"]}
    require(tool_names == set(plugin["tools"]) == set(app["tools"]) == set(submission["tools"]), "tool surfaces drifted")
    require(len(tool_names) == 13, "thirteen tools required")
    for tool in tools["tools"]:
        require(tool["risk"] in {"D0","D1","D2"}, "D0-D2 only")
        require(tool["destructive"] is False and tool["idempotent"] is True and tool["open_world"] is False, "unsafe tool annotation")
    require(commercial["exact_prices_authorized"] is False and commercial["operative_license"] is False and commercial["checkout_enabled"] is False, "commercial activation prohibited")
    require(resource["security"]["connect_domains"] == [] and resource["security"]["resource_domains"] == [], "widget network allowlist must be empty")
    require(resource["security"]["secret_access"] is False and resource["security"]["service_role_access"] is False, "widget privileged access prohibited")
    require(submission["state"] == "candidate_not_submitted" and submission["submitted"] is False and submission["published"] is False, "submission must remain non-operative")
    require(evidence["security_suite"]["passed"] == 12 and evidence["security_suite"]["failed"] == 0, "evidence security mismatch")
    forbidden = ("sk-proj-", "whsec_", "BEGIN PRIVATE KEY", "vault.decrypted_secrets", "private_subject_ids")
    for token in forbidden:
        require(token not in widget and token not in edge, f"forbidden token: {token}")
    require("window.openai" in widget and "aria-live" in widget and "prefers-reduced-motion" in widget, "widget bridge/accessibility scaffold incomplete")
    for method in ("server/discover","tools/list","tools/call","resources/list","resources/read"):
        require(method in edge, f"MCP method missing: {method}")
    print("CrownThrive Services Stack invariants: PASS")


if __name__ == "__main__":
    main()
