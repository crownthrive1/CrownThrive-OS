#!/usr/bin/env python3
"""Validate public-safe CrownThrive Interoperability Fabric invariants."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/crownthrive-interoperability-plugin.v1.json"
APP = ROOT / "apps/crownthrive-interoperability-plugin/app-manifest.json"
WIDGET = ROOT / "apps/crownthrive-interoperability-plugin/widget/index.html"
DOC = ROOT / "developers/crownthrive-interoperability-fabric.mdx"
AGENTS = ROOT / "automation/interoperability-agent-mesh.mdx"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    app = json.loads(APP.read_text(encoding="utf-8"))
    widget = WIDGET.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    agents_doc = AGENTS.read_text(encoding="utf-8")

    require(manifest["plugin_id"] == "ct.plugin.crownthrive-interoperability-fabric", "unexpected plugin ID")
    require(manifest["version"] == "0.1.0", "unexpected plugin version")
    require(manifest["state"] == "CONTROLLED_TEST_GOVERNED_HOLD", "plugin must remain controlled-test/HOLD")
    require(manifest["installed"] is False, "installation must not be claimed")
    require(manifest["submitted"] is False, "submission must not be claimed")
    require(manifest["public_listing"] is False, "public listing must not be claimed")
    require(manifest["checkout_enabled"] is False, "checkout must remain disabled")
    require(manifest["entitlement_active"] is False, "entitlement must remain inactive")
    require(manifest["algorithm"]["id"] == "ct.alg.gen7.ics", "ICS algorithm must be bound")
    require(manifest["algorithm"]["weights"] == "VAULT_ONLY", "algorithm weights must stay Vault-only")
    require(manifest["algorithm"]["person_scoring"] is False, "people must not be scored")
    require(manifest["algorithm"]["d3_auto"] is False, "D3 automation must be disabled")
    require(manifest["governance"]["d3_human_reserved"] is True, "D3 must remain human-reserved")
    require(manifest["governance"]["originator_self_certification"] is False, "self-certification must be disabled")
    require(manifest["governance"]["direct_main_merge"] is False, "direct-main merge must be disabled")
    require(manifest["governance"]["provider_write_inherited"] is False, "provider write cannot be inherited")
    require(manifest["commercialization"]["exact_prices_authorized"] is False, "exact prices must remain unauthorized")
    require(manifest["commercialization"]["protected_kernel_transfer"] is False, "protected kernel cannot transfer")
    require(manifest["commercialization"]["seller_payouts_authorized"] is False, "seller payouts must remain unauthorized")

    tools = {tool["name"]: tool for tool in manifest["tools"]}
    expected = {
        "interop.status", "interop.systems.list", "interop.contracts.list", "interop.routes.list",
        "interop.compatibility.evaluate", "interop.mapping.propose", "interop.route.plan",
        "interop.certification.submit", "plugins.catalog",
    }
    require(set(tools) == expected, "tool contract set drifted")
    require(all(tool.get("provider_write") is not True for tool in tools.values()), "no tool may claim provider-write authority")

    agents = manifest["agents"]
    require(len(agents) == 5, "five interoperability agents are required")
    require(all(agent["authority_ceiling"] == "D2" for agent in agents), "agent authority must be D2 maximum")
    require(all(agent["vote_eligible"] is False for agent in agents), "interoperability agents must be non-voting")
    require(any(agent["role"] == "independent_verifier" for agent in agents), "independent verifier missing")

    require(app["plugin_id"] == manifest["plugin_id"], "app/plugin ID mismatch")
    require(app["state"] == "candidate", "app must remain a candidate")
    require(app["submission"]["ready"] is False, "submission readiness must not be claimed")
    require(app["submission"]["submitted"] is False, "submission must not be claimed")
    require(app["privacy"]["secret_export"] is False, "secret export must be disabled")
    require(app["privacy"]["private_identity_export"] is False, "private identity export must be disabled")

    for forbidden in ("SUPABASE_SERVICE_ROLE_KEY", "OPENAI_API_KEY", "Authorization: Bearer", "vault.decrypted_secrets"):
        require(forbidden not in widget, f"widget contains forbidden implementation detail: {forbidden}")
    require("window.openai" in widget, "widget candidate must consume host tool output")
    require("aria-live" in widget and "prefers-reduced-motion" in widget, "basic accessibility scaffolding missing")

    for token in ("ct.alg.gen7.ics", "ct.interop.agent-certifier", "controlled test", "not installed"):
        require(token.lower() in (doc + agents_doc).lower(), f"public-safe documentation missing {token}")

    print("CrownThrive Interoperability Fabric invariants: PASS")


if __name__ == "__main__":
    main()
