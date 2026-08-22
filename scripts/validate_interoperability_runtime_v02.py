#!/usr/bin/env python3
"""Validate the runtime-0.2 and non-operative submission boundaries."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "developers/manifests/crownthrive-interoperability-runtime.v0.2.json"
SUBMISSION = ROOT / "apps/crownthrive-interoperability-plugin/chatgpt-app-submission.candidate.json"
RESOURCE = ROOT / "apps/crownthrive-interoperability-plugin/mcp-resource-manifest.json"
PLUGIN = ROOT / "developers/manifests/crownthrive-interoperability-plugin.v1.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    submission = json.loads(SUBMISSION.read_text(encoding="utf-8"))
    resource = json.loads(RESOURCE.read_text(encoding="utf-8"))
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))

    require(runtime["runtime_version"] == "0.2.0", "runtime version drift")
    require(runtime["plugin_version"] == "0.1.0", "plugin/runtime version relation drift")
    require(runtime["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "runtime must remain controlled-test/HOLD")
    require(runtime["authentication"]["required"] is True, "runtime authentication must be required")
    require(runtime["authentication"]["anonymous_access"] is False, "anonymous access must be disabled")
    require("interop.gaps.scan" in runtime["tools"], "gap scanner tool missing")
    require(runtime["security"]["secret_export"] is False, "secret export must be disabled")
    require(runtime["security"]["private_identity_export"] is False, "private identity export must be disabled")
    require(runtime["security"]["provider_write_inherited"] is False, "provider write cannot be inherited")
    require(runtime["current_proof"]["plugin_installed"] is False, "installation must not be claimed")
    require(runtime["current_proof"]["plugin_submitted"] is False, "submission must not be claimed")

    require(submission["state"] == "candidate_not_submitted", "submission packet must remain a candidate")
    require(submission["submitted"] is False, "submission must remain false")
    require(submission["published"] is False, "published must remain false")
    require(submission["installation_claimed"] is False, "installation claim must remain false")
    require(submission["privacy"]["secret_export"] is False, "submission cannot export secrets")
    require(submission["privacy"]["private_identity_export"] is False, "submission cannot export private identities")
    require(submission["governance"]["d3_auto"] is False, "D3 automation must remain false")
    require(submission["governance"]["sovereign_vote_effect"] is False, "submission cannot create votes")
    require(submission["commerce"]["checkout_enabled"] is False, "checkout must remain false")
    require(submission["commerce"]["entitlement_active"] is False, "entitlements must remain false")

    require(resource["resource_uri"].startswith("ui://"), "widget resource must use the UI resource scheme")
    require(resource["state"] == "candidate", "widget resource must remain candidate")
    require(resource["security"]["secret_access"] is False, "widget cannot access secrets")
    require(resource["security"]["service_role_access"] is False, "widget cannot access service role")
    require(resource["security"]["private_identity_access"] is False, "widget cannot access private identities")
    require(resource["submission"]["submitted"] is False, "resource submission must remain false")
    require(resource["submission"]["published"] is False, "resource publication must remain false")

    require(plugin["plugin_id"] == runtime["plugin_id"] == submission["plugin_id"] == resource["plugin_id"], "plugin ID mismatch")
    require(plugin["checkout_enabled"] is False and plugin["entitlement_active"] is False, "plugin commerce must remain disabled")

    print("CrownThrive Interoperability Runtime 0.2 invariants: PASS")


if __name__ == "__main__":
    main()
