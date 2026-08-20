#!/usr/bin/env python3
"""Fail-closed validator for the CrownThrive Website Surface control packet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/website-surface-control.v1.json"
REQUIRED_DOCS = [
    ROOT / "technology/web-surface-contact-interaction-automation.mdx",
    ROOT / "automation/website-surface-interaction-agent.mdx",
    ROOT / "standards/website-surface-automation-phase-amendment.mdx",
    ROOT / "changelog/phase-2-99-website-surface-sites-contact-automation.mdx",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    if not MANIFEST.exists():
        fail(f"missing manifest: {MANIFEST.relative_to(ROOT)}")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if data.get("stable_id") != "ct.manifest.website-surface-control.v1":
        fail("stable manifest identity changed")

    program = data.get("program", {})
    if program.get("current_subphase") != "2.99":
        fail("website control packet must remain Phase 2.99 scoped")
    if program.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
        fail("website control packet may not promote Phase 3")

    service = data.get("service", {})
    if service.get("service_id") != "website_surface_control":
        fail("service identity mismatch")
    if service.get("agent_id") != "ct.agent.website-surface-interaction":
        fail("website specialist agent identity mismatch")
    if service.get("external_mutation_allowed") is not False:
        fail("external website mutation must remain fail-closed")
    if service.get("central_mcp_federation") != "registered_disabled_until_dispatch_certification":
        fail("central MCP federation state must remain explicit and disabled")
    if service.get("provider_write_adapter") != "not_certified":
        fail("provider write adapter must remain un-certified in this packet")

    security = data.get("security", {})
    if security.get("rls_required") is not True or security.get("policy") != "service_role_only":
        fail("website control private tables require service-role-only RLS")
    if security.get("ordinary_monitoring_submits_live_forms") is not False:
        fail("ordinary monitoring must not submit live customer forms")
    if security.get("ordinary_monitoring_retains_contact_payloads") is not False:
        fail("ordinary monitoring must not retain contact payloads")
    if security.get("operational_contact_implies_marketing_consent") is not False:
        fail("operational contact may not imply marketing consent")

    required_tables = {
        "integration_control.website_surfaces",
        "integration_control.creative_asset_routes",
        "integration_control.site_interaction_checks",
        "integration_control.site_interaction_check_results",
        "integration_control.site_update_queue",
    }
    if set(data.get("private_tables", [])) != required_tables:
        fail("private website-control table set changed")

    direct_tools = {x.get("name"): x for x in data.get("direct_mcp", {}).get("tools", [])}
    expected_direct = {
        "sites.surface.list": "D0",
        "sites.interaction.check": "D0",
        "sites.asset_routes.list": "D0",
        "sites.update_queue.list": "D0",
        "sites.update.plan": "D1",
    }
    if {name: value.get("risk_class") for name, value in direct_tools.items()} != expected_direct:
        fail("direct MCP tool/risk contract changed")
    if data.get("direct_mcp", {}).get("protocol_version") != "2026-07-28":
        fail("direct MCP protocol target changed")
    if data.get("direct_mcp", {}).get("verify_jwt") is not True:
        fail("Website Surface MCP must require JWT verification")

    central = {x.get("name"): x for x in data.get("central_registry_tools", [])}
    expected_central = set(expected_direct) | {"sites.update.apply"}
    if set(central) != expected_central:
        fail("central website MCP registry tool set changed")
    if any(item.get("enabled") is not False for item in central.values()):
        fail("central website MCP tools must remain disabled until dispatch certification")
    apply_tool = central["sites.update.apply"]
    if apply_tool.get("risk_class") != "D2" or apply_tool.get("requires_human_approval") is not True:
        fail("external update tool must remain D2 approval-gated")

    queues = set(data.get("queue_classes", []))
    expected_queues = {
        "website_surface_health",
        "contact_interaction_drift",
        "creative_asset_distribution",
        "site_update_remediation",
        "public_claim_namespace_drift",
    }
    if queues != expected_queues:
        fail("website agent queue contract changed")

    surfaces = {x.get("surface_id"): x for x in data.get("surfaces", [])}
    for required in ("ct.surface.crownthrive.production", "ct.surface.kjv-visualized.production"):
        if required not in surfaces:
            fail(f"missing required seed surface: {required}")
        if surfaces[required].get("external_mutation_allowed") is not False:
            fail(f"seed surface may not enable mutation: {required}")
    kjv = surfaces["ct.surface.kjv-visualized.production"]
    if kjv.get("provider") != "Sites" or not kjv.get("provider_project_ref"):
        fail("KJV Sites project lineage must remain explicit")

    routes = {x.get("route_id"): x for x in data.get("creative_routes", [])}
    required_routes = {
        "ct.asset-route.crownthrive.figma-global",
        "ct.asset-route.crownthrive.canva-brand-kit",
        "ct.asset-route.crownthrive.canva-dark-brand-kit",
    }
    if set(routes) != required_routes:
        fail("initial creative-route set changed")
    if any(route.get("auto_sync_allowed") is not False for route in routes.values()):
        fail("creative routes must default to no automatic production sync")

    phase_keys = set(data.get("phase_inheritance", {}))
    if phase_keys != {"2.99", "3", "4", "5", "6", "7", "8", "9", "10"}:
        fail("website-control phase inheritance must cover 2.99 and 3-10")

    no_go = set(data.get("absolute_no_go", []))
    required_no_go = {
        "rendered_site_equals_write_integration",
        "registered_mcp_tool_equals_central_dispatch_certification",
        "ordinary_health_check_submits_real_customer_form",
        "operational_contact_equals_marketing_consent",
        "unregistered_figma_or_canva_asset_auto_published",
        "unverified_design_token_promoted_by_site_automation",
        "claim_or_phase_rewritten_without_namespace_evidence",
        "provider_write_without_rollback_and_read_after_write",
        "agent_self_approves_consequential_site_mutation",
    }
    if no_go != required_no_go:
        fail("absolute no-go set changed")

    for doc in REQUIRED_DOCS:
        if not doc.exists():
            fail(f"missing controlling document: {doc.relative_to(ROOT)}")
        if doc.stat().st_size < 1000:
            fail(f"controlling document is unexpectedly thin: {doc.relative_to(ROOT)}")

    print("Website Surface control validation: PASS")
    print(f"  surfaces={len(surfaces)} direct_tools={len(direct_tools)} queues={len(queues)}")
    print("  external_site_mutation=false central_dispatch=false live_form_monitoring=false")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"Website Surface control validation: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
