#!/usr/bin/env python3
"""Validate the public-safe CrownThrive Interoperability Fabric artifacts.

This repository validator does not certify provider connectivity, external
connector installation, public plugin submission, provider writes, commerce,
or production readiness.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "manifest": ROOT / "developers/manifests/crownthrive-interoperability-fabric.v1.json",
    "plugin": ROOT / "plugins/crownthrive-interoperability/plugin.manifest.json",
    "tools": ROOT / "plugins/crownthrive-interoperability/tool-contracts.json",
    "readme": ROOT / "plugins/crownthrive-interoperability/README.md",
    "docs": ROOT / "developers/crownthrive-interoperability-fabric.mdx",
    "agents": ROOT / "automation/crownthrive-interoperability-agents.mdx",
    "changelog": ROOT / "changelog/crownthrive-interoperability-fabric-2026-08-22.mdx",
}

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


def load_json(name: str) -> dict[str, Any]:
    path = FILES[name]
    assert path.is_file(), f"Missing artifact: {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_tool_annotations(tool: dict[str, Any]) -> None:
    annotations = tool.get("annotations", {})
    assert annotations.get("readOnlyHint") is True
    assert annotations.get("destructiveHint") is False
    assert annotations.get("idempotentHint") is True
    assert annotations.get("openWorldHint") is False


def validate_manifest(manifest: dict[str, Any]) -> None:
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["plugin_id"] == "ct.plugin.crownthrive-interoperability-fabric"
    assert manifest["semantic_version"] == "1.0.0"
    assert manifest["generation"] == 7
    assert manifest["state"] == "CONTROLLED_TEST_GOVERNED_HOLD"
    assert manifest["archetype"] == "tool_only"
    assert manifest["server_id"] == "ct.mcp.crownthrive-interoperability"
    assert manifest["public_submission_state"] == "not_submitted"

    for key in (
        "provider_write_enabled",
        "checkout_enabled",
        "entitlement_active",
        "D3_auto",
        "sovereign_vote_effect",
        "direct_main_merge",
        "secret_exposed",
        "private_identity_exposed",
        "weights_exposed",
    ):
        assert manifest[key] is False, key

    budget = manifest["budget_semantics"]
    assert budget["-1"] == "unlimited_local_ceiling"
    assert budget["0"] == "disabled"
    assert budget["positive"] == "local_monthly_ceiling"
    assert budget["null"] == "unresolved_fail_closed"
    assert budget["provider_limits_billing_quotas_separate"] is True

    counts = manifest["counts"]
    minimums = {
        "plugin_packages": 21,
        "capabilities": 39,
        "canonical_contracts": 13,
        "bindings": 42,
        "routes": 15,
        "agents": 6,
        "protected_algorithms": 2,
        "independent_tests_passed": 9,
        "pricing_candidates": 10,
    }
    for key, minimum in minimums.items():
        assert counts[key] >= minimum, (key, counts[key], minimum)

    assert [tool["name"] for tool in manifest["root_tools"]] == EXPECTED_TOOLS
    for tool in manifest["root_tools"]:
        assert tool["risk_class"] in {"D0", "D1"}
        assert tool["read_only"] is True
        assert tool["destructive"] is False
        assert tool["idempotent"] is True
        assert tool["open_world"] is False

    assert manifest["canonical_contracts"] == EXPECTED_CONTRACTS
    assert len(manifest["agents"]) == 6
    for agent in manifest["agents"]:
        assert agent["authority_ceiling"] == "D2"
        assert agent["vote_eligible"] is False
        assert agent["scheduler_slot"] is False

    algorithms = {entry["id"]: entry for entry in manifest["algorithms"]}
    assert set(algorithms) == {"ct.alg.gen7.icrs", "ct.alg.gen7.arrs"}
    for algorithm in algorithms.values():
        assert algorithm["implementation"] == "RESTRICTED_VAULT"
        assert algorithm["state"] == "controlled_test"
        assert algorithm["person_scoring"] is False
        assert algorithm["D3_auto"] is False

    validation = manifest["validation"]
    assert validation["package_state"] == "pass"
    assert validation["positive_compatibility"]["score"] >= 85
    assert validation["positive_compatibility"]["state"] == "pass"
    assert validation["positive_route"]["score"] >= 85
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
        assert tool["risk_class"] in {"D0", "D1"}
        assert_tool_annotations(tool)

    assert plugin["agents"]["authority_ceiling"] == "D2"
    assert plugin["agents"]["vote_eligible"] is False
    assert plugin["validation"]["package_state"] == "pass"
    assert plugin["validation"]["pass_tests"] >= 9
    assert plugin["validation"]["fail_tests"] == 0

    commercialization = plugin["commercialization"]
    for key in (
        "checkout_enabled",
        "stripe_objects_created",
        "entitlement_active",
        "operative_license",
        "public_distribution",
    ):
        assert commercialization[key] is False, key

    security = plugin["security"]
    for key in (
        "provider_write_enabled",
        "D3_auto",
        "sovereign_vote_effect",
        "direct_main_merge",
        "credentials_returned",
        "protected_weights_returned",
        "private_identity_returned",
    ):
        assert security[key] is False, key


def validate_tool_contracts(contracts: dict[str, Any]) -> None:
    assert contracts["schema_version"] == "1.0.0"
    assert contracts["server_id"] == "ct.mcp.crownthrive-interoperability"
    assert contracts["server_version"] == "1.0.0"
    assert [tool["name"] for tool in contracts["tools"]] == EXPECTED_TOOLS
    for tool in contracts["tools"]:
        assert tool["risk_class"] in {"D0", "D1"}
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False
        assert_tool_annotations(tool)

    invariants = contracts["global_invariants"]
    for key in (
        "provider_write_enabled",
        "checkout_enabled",
        "D3_auto",
        "sovereign_vote_effect",
        "credentials_returned",
        "protected_weights_returned",
        "private_identity_returned",
    ):
        assert invariants[key] is False, key


def validate_public_text() -> None:
    paths = [FILES["readme"], FILES["docs"], FILES["agents"], FILES["changelog"]]
    corpus_parts: list[str] = []
    for path in paths:
        assert path.is_file(), f"Missing artifact: {path.relative_to(ROOT)}"
        text = path.read_text(encoding="utf-8")
        corpus_parts.append(text)
        assert "controlled test" in text.lower()
        assert "D3" in text
        assert "vote" in text.lower()
        assert "credential" in text.lower()

    corpus = "\n".join(corpus_parts).lower()
    for phrase in (
        "not submitted",
        "provider write",
        "checkout",
        "authenticated external",
    ):
        assert phrase in corpus, phrase
    assert "no new external scheduler slot" in corpus or "zero new external" in corpus
    assert "history" in corpus or "silent deletion" in corpus or "silently delete" in corpus


def validate_no_sensitive_literals() -> None:
    # Construct sensitive sentinels from fragments so this validator cannot
    # self-trigger the repository-wide credential-pattern scanner.
    sentinels = [
        "SUPABASE_" + "SERVICE_ROLE_KEY=",
        "OPENAI_" + "API_KEY=",
        "-----BEGIN " + "PRIVATE KEY-----",
        "decrypted_" + "secret",
        "private_" + "subject_id\": \"ctpriv:",
        "sk-" + "proj-",
        "Bearer " + "n78-",
    ]
    paths = list(FILES.values())
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        for sentinel in sentinels:
            assert sentinel.lower() not in text, (path.relative_to(ROOT), "sensitive literal")


def main() -> None:
    manifest = load_json("manifest")
    plugin = load_json("plugin")
    contracts = load_json("tools")
    validate_manifest(manifest)
    validate_plugin(plugin)
    validate_tool_contracts(contracts)
    validate_public_text()
    validate_no_sensitive_literals()

    print("CrownThrive Interoperability Fabric repository invariants: PASS")
    print(f"manifest_sha256={sha256(FILES['manifest'])}")
    print(f"plugin_manifest_sha256={sha256(FILES['plugin'])}")
    print(f"tool_contracts_sha256={sha256(FILES['tools'])}")


if __name__ == "__main__":
    main()
