#!/usr/bin/env python3
"""Validate repository/runtime boundaries for the CrownThrive Asset Fabric."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "developers/manifests/crownthrive-plugin-pallet-kernel-asset-fabric.v1.json"
PLUGIN = ROOT / "plugins/crownthrive-asset-fabric/plugin.manifest.json"
TOOLS = ROOT / "plugins/crownthrive-asset-fabric/tool-contracts.json"
APP = ROOT / "apps/crownthrive-asset-fabric/app-manifest.json"
RESOURCE = ROOT / "apps/crownthrive-asset-fabric/mcp-resource-manifest.v0.1.json"
SUBMISSION = ROOT / "apps/crownthrive-asset-fabric/chatgpt-app-submission.candidate.v0.1.json"
EDGE = ROOT / "apps/crownthrive-asset-fabric/edge/index.ts"
WIDGET = ROOT / "apps/crownthrive-asset-fabric/widget/index.html"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    tools = json.loads(TOOLS.read_text(encoding="utf-8"))
    app = json.loads(APP.read_text(encoding="utf-8"))
    resource = json.loads(RESOURCE.read_text(encoding="utf-8"))
    submission = json.loads(SUBMISSION.read_text(encoding="utf-8"))
    edge = EDGE.read_text(encoding="utf-8")
    widget = WIDGET.read_text(encoding="utf-8")

    require(suite["catalog"]["candidate_asset_records"] == 5760, "catalog count drift")
    require(suite["extends"]["authoritative_asset_count_delta"] == 0, "authoritative count delta must be zero")
    require(len(suite["agents"]) == 7, "seven agents required")
    require(all(agent["authority_ceiling"] == "D2" for agent in suite["agents"]), "D2 maximum required")
    require(all(agent["vote_eligible"] is False for agent in suite["agents"]), "agents must be non-voting")
    require(all(agent["self_approval"] is False for agent in suite["agents"]), "self-approval prohibited")
    require(len(suite["tool_surface"]) == 20, "20 tools required")

    require(plugin["plugin_id"] == app["plugin_id"] == resource["plugin_id"] == submission["plugin_id"], "plugin ID mismatch")
    require(plugin["server_id"] == app["mcp_server_id"] == submission["mcp_server_id"], "server ID mismatch")
    require(plugin["catalog_root_sha256"] == suite["catalog"]["catalog_root_sha256"], "catalog root mismatch")
    for key in ("installed","submitted","published","checkout_enabled","entitlement_active","provider_write_enabled","D3_auto","sovereign_vote_effect","direct_main_merge","raw_secret_export","private_identity_export","protected_body_export"):
        require(plugin[key] is False, f"{key} must remain false")
    require(plugin["public_submission_state"] == "not_submitted", "public submission cannot be claimed")
    require(resource["state"] == "candidate_not_submitted", "resource must remain candidate")
    require(resource["security"]["connect_domains"] == [] and resource["security"]["resource_domains"] == [], "widget network allowlist must be empty")
    require(resource["security"]["secret_access"] is False and resource["security"]["service_role_access"] is False, "widget privileged access prohibited")
    require(submission["state"] == "candidate_not_submitted", "submission must remain candidate")
    require(submission["submitted"] is False and submission["published"] is False, "submission/publication cannot be claimed")

    expected_tools = set(plugin["tools"])
    contract_tools = {item["name"] for item in tools["tools"]}
    submission_tools = set(submission["tools"])
    require(expected_tools == contract_tools == submission_tools, "tool surfaces drifted")
    for item in tools["tools"]:
        annotations = item["annotations"]
        require(annotations["destructiveHint"] is False, "destructive tool prohibited")
        require(annotations["idempotentHint"] is True, "idempotent hint required")
        require(annotations["openWorldHint"] is False, "open-world tool prohibited")
        require(item["risk_class"] in {"D0", "D1", "D2"}, "D0-D2 only")
        require(item["input_schema"].get("additionalProperties") is False, "closed input schema required")

    for required in ("server/discover","tools/list","tools/call","resources/list","resources/read","assets.gaps.scan","assets.scrutinize","SERVICE_ROLE"):
        require(required in edge, f"edge runtime missing {required}")
    for forbidden in ("sk-proj-","whsec_","BEGIN PRIVATE KEY","private_subject_ids","vault.decrypted_secrets"):
        require(forbidden not in edge and forbidden not in widget, f"forbidden token present: {forbidden}")
    require("window.openai" in widget, "widget host bridge missing")
    require("aria-live" in widget and "prefers-reduced-motion" in widget, "widget accessibility scaffold incomplete")
    print("CrownThrive Asset Fabric runtime invariants: PASS")


if __name__ == "__main__":
    main()
