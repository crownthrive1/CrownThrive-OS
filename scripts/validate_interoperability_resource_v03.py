#!/usr/bin/env python3
"""Validate the versioned interoperability MCP widget resource."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "apps/crownthrive-interoperability-plugin/mcp-resource-manifest.v0.3.json"
RUNTIME = ROOT / "developers/manifests/crownthrive-interoperability-runtime.v0.3.json"
SUBMISSION = ROOT / "apps/crownthrive-interoperability-plugin/chatgpt-app-submission.candidate.v0.2.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    resource = json.loads(RESOURCE.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    submission = json.loads(SUBMISSION.read_text(encoding="utf-8"))

    require(resource["resource_manifest_version"] == "0.3.0", "resource version drift")
    require(resource["runtime_version"] == runtime["runtime_version"] == "0.3.0", "resource/runtime mismatch")
    require(resource["plugin_id"] == runtime["plugin_id"] == submission["plugin_id"], "plugin ID mismatch")
    require(resource["resource_uri"] == runtime["mcp"]["widget_resource_uri"], "resource URI mismatch")
    require(set(resource["mcp_methods"]) == {"resources/list", "resources/read"}, "MCP resource methods incomplete")
    require(resource["state"] == "candidate", "resource must remain candidate")
    require(resource["security"]["connect_domains"] == [], "unexpected connect domains")
    require(resource["security"]["resource_domains"] == [], "unexpected resource domains")
    require(resource["security"]["secret_access"] is False, "secret access prohibited")
    require(resource["security"]["service_role_access"] is False, "service-role access prohibited")
    require(resource["security"]["private_identity_access"] is False, "private identity access prohibited")
    require(resource["security"]["protected_transform_access"] is False, "protected transform access prohibited")
    require(resource["submission"]["submitted"] is False, "submission must remain false")
    require(resource["submission"]["published"] is False, "publication must remain false")
    require(all(binding["widget_accessible"] is True for binding in resource["tool_bindings"]), "widget bindings must be explicit")

    print("CrownThrive Interoperability MCP Resource 0.3 invariants: PASS")


if __name__ == "__main__":
    main()
