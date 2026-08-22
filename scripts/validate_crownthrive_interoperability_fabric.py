#!/usr/bin/env python3
"""Validate public-safe CrownThrive Interoperability Fabric artifacts.

This validator checks repository contracts only. It does not certify provider
connectivity, public plugin submission, commerce, or production readiness.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/crownthrive-interoperability-fabric.v1.json"
PLUGIN_PATH = ROOT / "plugins/crownthrive-interoperability/plugin.manifest.json"
TOOLS_PATH = ROOT / "plugins/crownthrive-interoperability/tool-contracts.json"
README_PATH = ROOT / "plugins/crownthrive-interoperability/README.md"
DOC_PATH = ROOT / "developers/crownthrive-interoperability-fabric.mdx"
AGENTS_PATH = ROOT / "automation/crownthrive-interoperability-agents.mdx"
CHANGELOG_PATH = ROOT / "changelog/crownthrive-interoperability-fabric-2026-08-22.mdx"

EXPECTED_TOOLS = [
    "search",
    "fetch",
    "interop.status",
    "interop.compatibility.check",
    "interop.route.plan",
    "plugins.list",
    "plugins.get",
    "plugins.install.plan",
    "plugins.package.validate",
]

EXPECTED_CONTRACTS = [
    "ct.interop.contract.identity-envelope.v1",
    "ct.interop.contract.evidence-receipt.v1",
    "ct.interop.contract.content-document.v1",
    "ct.interop.contract.product-catalog.v1",
    "ct.interop.contract.contact-profile.v1",
    "ct.interop.contract.order-transaction.v1",
    "ct.interop.contract.campaign-ad.v1",
    "ct.interop.contract.analytics-event.v1",
    "ct.interop.contract.site-release.v1",
    "ct.interop.contract.notification.v1",
    "ct.interop.contract.entitlement-license.v1",
    "ct.interop.contract.credit-value.v1",
    "ct.interop.contract.plugin-package.v1",
]

FORBIDDEN_TEXT = [
    "SUPABASE_SERVICE_ROLE_KEY=",
    "OPENAI_API_KEY=",
    "-----BEGIN PRIVATE KEY-----",
    "decrypted_secret",
    "private_subject_id\": \"ctpriv:",
    "sk-proj-",
    "Bearer n78-",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"Missing required artifact: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest: dict[str, Any]) -> None:
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["plugin_id"] == "ct.plugin.crownthrive-interoperability-fabric"
    assert manifest["semantic_version"] == "1.0.0"
    assert manifest["generation"] == 7
    assert manifest["state"] == "CONTROLLED_TEST_GOVERNED_HOLD"
    assert manifest["archetype"] == "tool_only"
    assert manifest["server_id"] == "ct.mcp.crownthrive-interoperability"
    assert manifest["public_submission_state"] == "not_submitted"
    assert manifest["provider_write_enabled"] is False
    assert manifest["checkout_enabled"] is False
    assert manifest["entitlement_active"] is False
    assert manifest["D3_auto"] is False
    assert manifest["sovereign_vote_effect"] is False
    assert manifest["direct_main_merge"] is False
    assert manifest["secret_exposed"] is False
    assert manifest["private_identity_exposed"] is False
    assert manifest["weights_exposed"] is False

    budget = manifest["budget_semantics"]
    assert budget["-1"] == "unlimited_local_ceiling"
    assert budget["0"] == "disabled"
    assert budget["provider_limits_billing_quotas_separate"] is True

    counts = manifest["counts"]
    assert counts["plugin_packages"] >= 21
    assert counts["capabilities"] >= 39
    assert counts["canonical_contracts"] == 13
    assert counts["bindings"] >= 42
    assert counts["routes"] >= 15
    assert counts["agents"] == 6
    assert counts["protected_algorithms"] == 2
    assert counts["independent_tests_passed"] >= 9
    assert counts["pricing_candidates"] >= 10

    tool_names = [tool["name"] for tool in manifest["root_tools"]]
    assert tool_names == EXPECTED_TOOLS
    for tool in manifest["root_tools"]:
        assert tool["read_only"] is True
        assert tool["destructive"] is False
        assert tool["idempotent"] is True
        assert tool["open_world"] is False
        assert tool["risk_class"] in {"D0", "D1"}

    assert manifest["canonical_contracts"] == EXPECTED_CONTRACTS
    assert len(manifest["agents"]) == 6
    for agent in manifest["agents"]:
        assert agent["authority_ceiling"] == "D2"
        assert agent["vote_eligible"] is False
        assert agent["scheduler_slot"] is False

    algorithm_ids = {algorithm["id"] for algorithm in manifest["algorithms"]}
    assert algorithm_ids == {"ct.alg.gen7.icrs", "ct.alg.gen7.arrs"}
    for algorithm in manifest["algorithms"]:
        assert algorithm["implementation"] == "RESTRICTED_VAULT"
        assert algorithm["state"] == "controlled_test"
        assert algorithm["person_scoring"] is False
        assert algorithm["D3_auto"] is False

    validation = manifest["validation"]
    assert validation["package_state"] == "pass"
    assert validation["positive_compatibility"]["state"] == "pass"
    assert validation["positive_compatibility"]["score"] >= 85
    assert validation["positive_route"]["state"] == "verified_candidate"
    assert validation["positive_route"]["execution_performed"] is False
    assert validation["positive_route"]["provider_write_performed"] is False
    assert validation["negative_route"]["state"] == "hold"
    assert set(validation["negative_route"]["required_blockers"]) == {
        "source_binding_hold",
        "route_hold",
    }

    hard_gates = manifest["hard_gates"]
    assert hard_gates["authenticated_external_canary"] == "pending"
    assert hard_gates["public_plugin_submission"] == "not_submitted"
    assert hard_gates["provider_writes"] == "disabled"
    assert hard_gates["live_commerce"] == "disabled"
    assert hard_gates["phase_3_effect"] is False
    assert manifest["history_policy"] == "append_or_supersede_never_silent_delete"


def validate_plugin(plugin: dict[str, Any]) -> None:
    assert plugin["plugin_id"] == "ct.plugin.crownthrive-interoperability-fabric"
    assert plugin["version"] == "1.0.0"
    assert plugin["archetype"] == "tool_only"
    assert plugin["state"] == "controlled_test"
    assert plugin["public_state"] == "internal"
    assert plugin["public_submission_state"] == "not_submitted"
    assert plugin["server"]["id"] == "ct.mcp.crownthrive-interoperability"
    assert plugin["server"]["verify_jwt"] is True
    assert plugin["server"]["authenticated_external_canary"] == "pending"
    assert plugin["auth"]["credentials_in_manifest"] is False
    assert plugin["auth"]["private_identity_in_manifest"] is False
    assert [tool["name"] for tool in plugin["tools"]] == EXPECTED_TOOLS
    for tool in plugin["tools"]:
        annotations = tool["annotations"]
        assert annotations == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        assert tool["risk_class"] in {"D0", "D1"}
    assert plugin["agents"]["vote_eligible"] is False
    assert plugin["agents"]["authority_ceiling"] == "D2"
    assert plugin["validation"]["package_state"] == "pass"
    assert plugin["validation"]["pass_tests"] >= 9
    assert plugin["validation"]["fail_tests"] == 0
    assert plugin["commercialization"]["checkout_enabled"] is False
    assert plugin["commercialization"]["stripe_objects_created"] is False
    assert plugin["commercialization"]["entitlement_active"] is False
    assert plugin["commercialization"]["operative_license"] is False
    assert plugin["commercialization"]["public_distribution"] is False
    for key, expected in {
        "provider_write_enabled": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "direct_main_merge": False,
        "credentials_returned": False,
        "protected_weights_returned": False,
        "private_identity_returned": False,
    }.items():
        assert plugin["security"][key] is expected


def validate_tools(tools: dict[str, Any]) -> None:
    assert tools["schema_version"] == "1.0.0"
    assert tools["server_id"] == "ct.mcp.crownthrive-interoperability"
    assert tools["server_version"] == "1.0.0"
    assert [tool["name"] for tool in tools["tools"]] == EXPECTED_TOOLS
    for tool in tools["tools"]:
        assert tool["risk_class"] in {"D0", "D1"}
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False
        annotations = tool["annotations"]
        assert annotations["readOnlyHint"] is True
        assert annotations["destructiveHint"] is False
        assert annotations["idempotentHint"] is True
        assert annotations["openWorldHint"] is False
    invariants = tools["global_invariants"]
    assert invariants["provider_write_enabled"] is False
    assert invariants["checkout_enabled"] is False
    assert invariants["D3_auto"] is False
    assert invariants["sovereign_vote_effect"] is False
    assert invariants["credentials_returned"] is False
    assert invariants["protected_weights_returned"] is False
    assert invariants["private_identity_returned"] is False


def validate_text_files() -> None:
    paths = [README_PATH, DOC_PATH, AGENTS_PATH, CHANGELOG_PATH]
    for path in paths:
        if not path.exists():
            raise AssertionError(f"Missing public-safe text artifact: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        assert "CONTROLLED TEST" in text.upper() or "controlled test" in text.lower()
        assert "not submitted" in text.lower()
        assert "provider write" in text.lower()
        assert "D3" in text


def validate_no_secret_patterns() -> None:
    paths = [MANIFEST_PATH, PLUGIN_PATH, TOOLS_PATH, README_PATH, DOC_PATH, AGENTS_PATH, CHANGELOG_PATH]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_TEXT:
            if forbidden.lower() in text.lower():
                raise AssertionError(f"Forbidden secret/private pattern in {path.relative_to(ROOT)}: {forbidden}")


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    plugin = load_json(PLUGIN_PATH)
    tools = load_json(TOOLS_PATH)
    validate_manifest(manifest)
    validate_plugin(plugin)
    validate_tools(tools)
    validate_text_files()
    validate_no_secret_patterns()

    print("CrownThrive Interoperability Fabric repository invariants: PASS")
    print(f"manifest_sha256={sha256(MANIFEST_PATH)}")
    print(f"plugin_manifest_sha256={sha256(PLUGIN_PATH)}")
    print(f"tool_contracts_sha256={sha256(TOOLS_PATH)}")


if __name__ == "__main__":
    main()
