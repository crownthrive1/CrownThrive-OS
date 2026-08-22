#!/usr/bin/env python3
"""Validate plugin 0.1.1, runtime 0.3 and submission packet 0.3."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "developers/manifests/crownthrive-interoperability-plugin.v1.1.json"
RUNTIME = ROOT / "developers/manifests/crownthrive-interoperability-runtime.v0.3.json"
SUBMISSION = ROOT / "apps/crownthrive-interoperability-plugin/chatgpt-app-submission.candidate.v0.3.json"
RESOURCE = ROOT / "apps/crownthrive-interoperability-plugin/mcp-resource-manifest.v0.3.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    submission = json.loads(SUBMISSION.read_text(encoding="utf-8"))
    resource = json.loads(RESOURCE.read_text(encoding="utf-8"))

    require(plugin["version"] == "0.1.1", "plugin version drift")
    require(plugin["supersedes_plugin_version"] == "0.1.0", "plugin supersession missing")
    require(plugin["runtime_version"] == runtime["runtime_version"] == submission["runtime_version"] == resource["runtime_version"] == "0.3.0", "runtime version mismatch")
    require(plugin["plugin_id"] == runtime["plugin_id"] == submission["plugin_id"] == resource["plugin_id"], "plugin ID mismatch")
    require(plugin["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "plugin must remain controlled-test/HOLD")
    require(plugin["installed"] is False and plugin["submitted"] is False and plugin["published"] is False, "lifecycle activation cannot be claimed")
    require(plugin["checkout_enabled"] is False and plugin["entitlement_active"] is False, "commerce must remain disabled")
    require(len(plugin["tools"]) == 10, "plugin 0.1.1 must bind ten tools")
    require(any(tool["name"] == "interop.gaps.scan" for tool in plugin["tools"]), "gap scanner missing from plugin")
    require(plugin["commercialization"]["unit_economics_models"] is True, "unit-economics models missing")
    require(plugin["commercialization"]["exact_prices_authorized"] is False, "exact prices cannot be authorized")
    require(plugin["commercialization"]["seller_payouts_authorized"] is False, "seller payouts cannot be authorized")
    require(plugin["governance"]["d3_human_reserved"] is True, "D3 must remain human-reserved")
    require(plugin["governance"]["originator_self_certification"] is False, "self-certification prohibited")
    require(plugin["governance"]["provider_write_inherited"] is False, "provider write cannot be inherited")

    require(submission["submission_packet_id"] == "ct.plugin-submission.interoperability-chatgpt.v0.3", "unexpected submission packet")
    require(submission["supersedes"] == "ct.plugin-submission.interoperability-chatgpt.v0.2", "submission supersession missing")
    require(submission["plugin_version"] == "0.1.1", "submission/plugin mismatch")
    require(submission["state"] == "candidate_not_submitted", "submission must remain candidate")
    require(submission["submitted"] is False and submission["published"] is False, "submission/publication cannot be claimed")
    require(submission["commerce"]["checkout_enabled"] is False, "submission checkout must remain disabled")
    require(submission["commerce"]["entitlement_active"] is False, "submission entitlement must remain inactive")
    require(resource["resource_manifest_version"] == "0.3.0", "resource version mismatch")

    print("CrownThrive Interoperability Plugin 0.1.1 invariants: PASS")


if __name__ == "__main__":
    main()
