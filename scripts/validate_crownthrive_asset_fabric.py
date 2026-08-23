#!/usr/bin/env python3
"""Validate public-safe CrownThrive Institutional Asset Fabric artifacts.

This repository validator does not certify the deployed Edge boundary, source
materialization for all specifications, production installation, publication,
rights, pricing, fulfillment, or live commerce.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "fabric": ROOT / "developers/manifests/crownthrive-asset-fabric.v1.json",
    "suite": ROOT / "developers/manifests/crownthrive-plugin-suite.v1.json",
    "catalog": ROOT / "developers/manifests/crownthrive-asset-blueprint-catalog.v1.json",
    "app": ROOT / "apps/crownthrive-institutional-asset-fabric/app-manifest.json",
    "resource": ROOT / "apps/crownthrive-institutional-asset-fabric/mcp-resource-manifest.json",
    "widget": ROOT / "apps/crownthrive-institutional-asset-fabric/widget/index.html",
    "readme": ROOT / "apps/crownthrive-institutional-asset-fabric/README.md",
    "docs": ROOT / "developers/crownthrive-institutional-asset-fabric.mdx",
    "controller": ROOT / "automation/institutional-asset-controller.mdx",
    "generator": ROOT / "scripts/generate_crownthrive_asset_blueprints.py",
}

EXPECTED_COUNTS = {
    "domains": 40,
    "archetypes": 20,
    "deployment_profiles": 5,
    "candidate_blueprints": 4000,
    "curated_assets": 456,
    "plugins": 32,
    "pallets": 24,
    "kernels": 16,
    "script_specifications": 96,
    "workflow_specifications": 64,
    "skill_specifications": 64,
    "prompt_pack_specifications": 64,
    "test_suite_specifications": 32,
    "policy_packages": 32,
    "runbook_specifications": 32,
    "bounded_execution_plans": 160,
    "asset_bundles": 8,
    "controller_agents": 10,
    "root_mcp_tools": 11,
}

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

FORBIDDEN_PUBLIC_LITERALS = [
    "SUPABASE_" + "SERVICE_ROLE_KEY=",
    "OPENAI_" + "API_KEY=",
    "-----BEGIN " + "PRIVATE KEY-----",
    "decrypted_" + "secret",
    "private_" + "subject_ids",
    "sk-" + "proj-",
]


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def load_json(name: str) -> dict[str, Any]:
    path = FILES[name]
    require(path.is_file(), f"Missing artifact: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_generator() -> ModuleType:
    path = FILES["generator"]
    require(path.is_file(), f"Missing generator: {path.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location("asset_blueprint_generator", path)
    require(spec is not None and spec.loader is not None, "Unable to load generator module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_fabric(fabric: dict[str, Any]) -> None:
    require(fabric["schema_version"] == "1.0.0", "fabric schema drift")
    require(fabric["plugin_id"] == "ct.plugin.institutional-asset-fabric", "fabric plugin ID drift")
    require(fabric["plugin_version"] == "0.1.0", "fabric plugin version drift")
    require(fabric["runtime_version"] == "0.1.0", "fabric runtime version drift")
    require(fabric["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "fabric must remain controlled-test/HOLD")
    require(fabric["public_submission_state"] == "not_submitted", "submission must remain closed")

    for key in (
        "installed",
        "submitted",
        "published",
        "checkout_enabled",
        "entitlement_active",
        "provider_write_enabled",
        "arbitrary_native_binary_execution",
        "direct_main_merge",
        "D3_auto",
        "sovereign_vote_effect",
    ):
        require(fabric[key] is False, f"Unexpected active fabric state: {key}")

    for key, expected in EXPECTED_COUNTS.items():
        require(fabric["counts"][key] == expected, f"Count mismatch for {key}")

    require(set(fabric["asset_classes"]) == {
        "plugin", "pallet", "kernel", "executable_plan", "script", "workflow", "adapter", "skill",
        "prompt_pack", "schema", "event_contract", "test_suite", "policy", "widget", "runbook",
        "license_pack", "observability_pack", "continuity_pack", "commerce_pack", "security_pack",
    }, "Asset-class set drift")
    require(len(fabric["controller_agents"]) == 10, "Controller-agent count drift")
    require(all(agent["authority_ceiling"] == "D2" for agent in fabric["controller_agents"]), "Asset agents must be D2 maximum")
    require(all(agent["vote_eligible"] is False for agent in fabric["controller_agents"]), "Asset agents must be non-voting")
    require(set(fabric["root_tools"]) == EXPECTED_TOOLS, "Root tool set drift")
    require(fabric["controller_schedule"]["external_scheduler_slots_added"] == 0, "No external scheduler slot should be added")
    require(fabric["controller_schedule"]["first_cron_fired_cycle"] == "pending", "Cron-fired proof must not be fabricated")
    require(fabric["history_policy"] == "append_or_supersede_never_silent_delete", "History policy drift")


def validate_suite(suite: dict[str, Any]) -> None:
    require(suite["root_plugin_id"] == "ct.plugin.institutional-asset-fabric", "Suite root drift")
    require(suite["plugin_count"] == 32, "Suite plugin count drift")
    require(len(suite["plugins"]) == 32, "Plugin array count drift")
    require(len({item["plugin_id"] for item in suite["plugins"]}) == 32, "Duplicate plugin IDs")
    for count_key in ("installed_count", "submitted_count", "published_count", "checkout_enabled_count", "entitlement_active_count"):
        require(suite[count_key] == 0, f"Unexpected suite activation: {count_key}")
    invariants = suite["shared_invariants"]
    for key in (
        "provider_write_inherited",
        "arbitrary_command_execution",
        "credential_export",
        "private_identity_export",
        "protected_kernel_export",
        "originator_self_certification",
        "direct_main_merge",
        "D3_auto",
        "sovereign_vote_effect",
    ):
        require(invariants[key] is False, f"Suite invariant must remain false: {key}")
    require(suite["commercial_state"]["checkout_enabled"] is False, "Suite checkout must remain disabled")
    require(suite["commercial_state"]["exact_prices_authorized"] is False, "Exact prices must remain unauthorized")


def validate_catalog(catalog: dict[str, Any], generator: ModuleType) -> None:
    require(len(catalog["domains"]) == 40, "Domain catalog count drift")
    require(len(catalog["archetypes"]) == 20, "Archetype catalog count drift")
    require(len(catalog["deployment_profiles"]) == 5, "Profile catalog count drift")
    require(catalog["expected_matrix_size"] == 4000, "Expected matrix-size drift")
    blueprints = generator.generate(catalog)
    require(len(blueprints) == 4000, "Generator did not produce 4,000 blueprints")
    require(len({item["blueprint_id"] for item in blueprints}) == 4000, "Generated blueprint IDs are not unique")
    require(all(item["lifecycle_state"] == "candidate" for item in blueprints), "Generated blueprint state drift")
    require(all(item["manifest_template"]["source_materialized"] is False for item in blueprints), "Generator must not claim source materialization")
    require(all(item["manifest_template"]["opaque_native_binary_generation"] is False for item in blueprints), "Opaque binary generation prohibited")
    require(all(item["manifest_template"]["D3_auto"] is False for item in blueprints), "D3 automation prohibited")
    first_pass = generator.sha256_text("\n".join(item["blueprint_sha256"] for item in blueprints))
    second_pass = generator.sha256_text("\n".join(item["blueprint_sha256"] for item in generator.generate(catalog)))
    require(first_pass == second_pass, "Generator output is not deterministic")


def validate_app(app: dict[str, Any], resource: dict[str, Any]) -> None:
    require(app["plugin_id"] == "ct.plugin.institutional-asset-fabric", "App plugin ID drift")
    require(app["state"] == "candidate_not_submitted", "App must remain candidate/not submitted")
    require(app["installed"] is False and app["submitted"] is False and app["published"] is False, "App lifecycle activation cannot be claimed")
    require({tool["name"] for tool in app["tools"]} == EXPECTED_TOOLS, "App tool set drift")
    require(app["privacy"]["secret_export"] is False, "App cannot export secrets")
    require(app["privacy"]["service_role_access_from_widget"] is False, "Widget cannot access service role")
    require(app["execution"]["arbitrary_command_execution"] is False, "App cannot run arbitrary commands")
    require(app["execution"]["provider_write_enabled"] is False, "Provider writes must remain disabled")
    require(app["commerce"]["checkout_enabled"] is False, "App checkout must remain disabled")
    require(app["submission"]["ready"] is False, "Submission readiness must not be claimed")

    require(resource["resource_uri"] == app["widget_resource_uri"], "App/resource URI mismatch")
    require(resource["state"] == "candidate", "Resource must remain candidate")
    require(resource["security"]["connect_domains"] == [], "Widget external domains must be empty")
    require(resource["security"]["resource_domains"] == [], "Widget resource domains must be empty")
    for key in ("secret_access", "service_role_access", "private_identity_access", "protected_kernel_access", "direct_database_access"):
        require(resource["security"][key] is False, f"Resource access must remain false: {key}")
    require(resource["submission"]["submitted"] is False and resource["submission"]["published"] is False, "Resource cannot be submitted or published")


def validate_text_artifacts() -> None:
    for key in ("widget", "readme", "docs", "controller"):
        path = FILES[key]
        require(path.is_file(), f"Missing text artifact: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_PUBLIC_LITERALS:
            require(forbidden.lower() not in text.lower(), f"Sensitive literal in {path.relative_to(ROOT)}")

    widget = FILES["widget"].read_text(encoding="utf-8")
    require("window.openai" in widget, "Widget must consume host tool output")
    require("aria-live" in widget, "Widget live-status region missing")
    require("prefers-reduced-motion" in widget, "Widget reduced-motion support missing")
    require("fetch(" not in widget, "Widget must not make direct network requests")

    corpus = "\n".join(FILES[key].read_text(encoding="utf-8") for key in ("readme", "docs", "controller")).lower()
    for phrase in (
        "controlled test",
        "blueprint is not",
        "not installed",
        "checkout",
        "append-or-supersede",
        "arbitrary",
        "d3",
        "independent",
    ):
        require(phrase in corpus, f"Documentation boundary missing: {phrase}")


def main() -> None:
    fabric = load_json("fabric")
    suite = load_json("suite")
    catalog = load_json("catalog")
    app = load_json("app")
    resource = load_json("resource")
    generator = load_generator()

    validate_fabric(fabric)
    validate_suite(suite)
    validate_catalog(catalog, generator)
    validate_app(app, resource)
    validate_text_artifacts()

    print("CrownThrive Institutional Asset Fabric repository invariants: PASS")
    print("candidate_blueprints=4000")
    print("curated_assets=456")
    print("production_assets_claimed=0")
    print("provider_write_performed=false")
    print("arbitrary_native_binary_execution=false")
    print("checkout_enabled=false")


if __name__ == "__main__":
    main()
