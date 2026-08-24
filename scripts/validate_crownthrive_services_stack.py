#!/usr/bin/env python3
"""Validate the public-safe CrownThrive Services Stack and CHLOM CaaS package."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "developers/manifests/crownthrive-services-stack.v1.json"
LANES = ROOT / "developers/manifests/css-service-lanes.v1.json"
CONTROLS = ROOT / "developers/manifests/css-caas-controls.v1.json"
PLUGIN = ROOT / "plugins/crownthrive-services-stack/plugin.manifest.json"
TOOLS = ROOT / "plugins/crownthrive-services-stack/tool-contracts.json"
APP = ROOT / "apps/crownthrive-services-stack/app-manifest.json"
SUBMISSION = ROOT / "apps/crownthrive-services-stack/chatgpt-app-submission.candidate.v0.1.json"
RESOURCE = ROOT / "apps/crownthrive-services-stack/mcp-resource-manifest.v0.1.json"
EDGE = ROOT / "apps/crownthrive-services-stack/edge/index.ts"
WIDGET = ROOT / "apps/crownthrive-services-stack/widget/index.html"
PLATFORM = ROOT / "platforms/crownthrive-services-stack.mdx"
CAAS = ROOT / "chlom/compliance-as-a-service.mdx"
AGENTS = ROOT / "automation/crownthrive-services-stack-agent-mesh.mdx"
SKILL = ROOT / "skills/crownthrive-services-stack/SKILL.md"

EXPECTED_LANES = {
    "identity", "authentication", "authorization", "billing", "licensing", "analytics", "notifications",
    "crm", "ticketing", "search", "commerce", "routing", "rewards", "documentation",
}
EXPECTED_TOOLS = {
    "css.status", "css.services.list", "css.services.get", "css.providers.list", "css.contracts.list",
    "css.controls.list", "css.routes.list", "css.readiness.evaluate", "css.controls.map", "css.gaps.scan",
    "css.bind.plan", "css.failover.plan", "css.certification.submit", "css.receipts.list",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    stack = load(STACK)
    lanes = load(LANES)
    controls = load(CONTROLS)
    plugin = load(PLUGIN)
    tools = load(TOOLS)
    app = load(APP)
    submission = load(SUBMISSION)
    resource = load(RESOURCE)
    edge = EDGE.read_text(encoding="utf-8")
    widget = WIDGET.read_text(encoding="utf-8")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (PLATFORM, CAAS, AGENTS, SKILL))

    require(stack["stack_id"] == "ct.stack.crownthrive-services-stack", "stack ID drift")
    require(stack["platform_id"] == "ct.platform.chlom-caas", "CaaS platform ID drift")
    require(stack["plugin_id"] == "ct.plugin.crownthrive-services-stack", "plugin ID drift")
    require(stack["service_lane_count"] == 14, "fourteen lanes required")
    require(stack["caas_controls"] == 28, "twenty-eight controls required")
    require(len(stack["protected_algorithms"]) == 4, "four protected algorithms required")
    require(len(stack["protected_kernels"]) == 8, "eight protected kernels required")
    require(len(stack["agents"]) == 7, "seven agents required")
    require(len(stack["mcp_tools"]) == 14, "fourteen MCP tools required")
    require(stack["derived_asset_projection"]["candidate_records"] == 672, "672 CSS asset projections required")
    require(stack["derived_asset_projection"]["authoritative_asset_count_delta"] == 0, "source asset count delta must remain zero")
    require(all(agent["authority_ceiling"] == "D2" for agent in stack["agents"]), "agent authority must be D2 maximum")
    require(all(agent["vote_eligible"] is False and agent["self_approval"] is False for agent in stack["agents"]), "agents must be non-voting and no-self-approval")

    lane_keys = {lane["service_key"] for lane in lanes["lanes"]}
    require(lane_keys == EXPECTED_LANES, "service-lane set drift")
    require(len(lanes["lanes"]) == 14, "lane count mismatch")
    require(all(lane["authority_ceiling"] == "D2" for lane in lanes["lanes"]), "lane authority must be D2")
    require(all(lane["provider_candidates"] for lane in lanes["lanes"]), "every lane needs provider candidates")

    require(controls["control_count"] == 28 and len(controls["controls"]) == 28, "control catalog mismatch")
    require({control["lane_id"] for control in controls["controls"]} == {lane["lane_id"] for lane in lanes["lanes"]}, "every lane must have controls")
    counts: dict[str, int] = {}
    for control in controls["controls"]:
        counts[control["lane_id"]] = counts.get(control["lane_id"], 0) + 1
    require(all(value == 2 for value in counts.values()), "every lane requires exactly two foundational controls")
    require("not legal" in controls["professional_authority_firewall"].lower(), "professional-authority firewall missing")

    require(plugin["plugin_id"] == app["plugin_id"] == submission["plugin_id"] == resource["plugin_id"], "plugin identity mismatch")
    require(plugin["server_id"] == app["mcp_server_id"] == submission["mcp_server_id"], "MCP identity mismatch")
    require(plugin["service_lane_count"] == 14 and plugin["caas_control_count"] == 28, "plugin coverage mismatch")
    require(plugin["derived_asset_candidates"] == 672 and plugin["authoritative_asset_count_delta"] == 0, "plugin asset projection mismatch")
    require(set(plugin["tools"]) == EXPECTED_TOOLS, "plugin tool set drift")
    require({item["name"] for item in tools["tools"]} == EXPECTED_TOOLS, "tool-contract set drift")
    for item in tools["tools"]:
        annotations = item["annotations"]
        require(item["risk_class"] in {"D0", "D1", "D2"}, "D0-D2 only")
        require(item["input_schema"].get("additionalProperties") is False, f"closed input schema required: {item['name']}")
        require(annotations["destructiveHint"] is False and annotations["idempotentHint"] is True and annotations["openWorldHint"] is False, f"unsafe annotations: {item['name']}")

    for document in (plugin, app, submission):
        for key in ("submitted", "published"):
            require(document[key] is False, f"{key} must remain false")
    require(plugin["installed"] is False and app["installed"] is False and submission["installation_claimed"] is False, "installation cannot be claimed")
    for key in ("provider_write_enabled", "checkout_enabled", "entitlement_active", "D3_auto", "sovereign_vote_effect", "direct_main_merge", "raw_secret_export", "private_identity_export", "protected_implementation_export"):
        require(plugin[key] is False, f"plugin {key} must remain false")
    require(plugin["readiness_is_professional_certification"] is False, "readiness cannot be professional certification")
    require(submission["state"] == "candidate_not_submitted", "submission must remain candidate")
    require(submission["professional_authority"]["readiness_is_professional_certification"] is False, "submission firewall missing")

    require(resource["state"] == "candidate_not_submitted", "resource must remain a candidate")
    require(resource["security"]["connect_domains"] == [] and resource["security"]["resource_domains"] == [], "widget network allowlist must be empty")
    require(resource["security"]["secret_access"] is False and resource["security"]["service_role_access"] is False, "widget privileged access prohibited")
    require(resource["security"]["private_identity_access"] is False and resource["security"]["protected_implementation_access"] is False, "widget protected access prohibited")

    for method in ("server/discover", "tools/list", "tools/call", "resources/list", "resources/read"):
        require(method in edge, f"edge runtime missing {method}")
    for tool in EXPECTED_TOOLS:
        require(tool in edge, f"edge runtime missing {tool}")
    for forbidden in ("sk-proj-", "whsec_", "BEGIN PRIVATE KEY", "private_subject_ids", "vault.decrypted_secrets"):
        require(forbidden not in edge and forbidden not in widget, f"forbidden token present: {forbidden}")
    require("window.openai" in widget, "widget host bridge missing")
    require("aria-live" in widget and "prefers-reduced-motion" in widget, "widget accessibility scaffold incomplete")

    text = docs.lower()
    for phrase in ("provider capability does not prove crownthrive deployment", "readiness", "professional certification", "no silent deletion", "d2"):
        require(phrase in text, f"documentation missing invariant: {phrase}")

    print("CrownThrive Services Stack and CHLOM CaaS invariants: PASS")


if __name__ == "__main__":
    main()
