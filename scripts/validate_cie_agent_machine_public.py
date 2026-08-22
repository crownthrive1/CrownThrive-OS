#!/usr/bin/env python3
"""Validate the public-safe CIE agent-machine projection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAIN = "c7f14b73cff09f00a8f94f15a8587289de18ff7b"
DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"
FILES = {
    "suite": "developers/contracts/cie-agent-suite.v1.json",
    "runtime": "developers/contracts/cie-protected-runtime-invocation.v1.json",
    "retro": "developers/contracts/cie-retroactive-scan.v1.json",
    "chlom": "developers/contracts/cie-chlom-pallet-record.v1.json",
    "commercial": "developers/manifests/cie-agent-machine-commercialization.v1.json",
}
EXPECTED_SHA = {
    "suite": "75dfe77ce643866b30d9047b33147292e6ec55a8f601aa0dbf8893706a37591b",
    "runtime": "c1d242311657be50f1126c568075af36c6ddbe0aa8f981da7e4de336d3d8571b",
    "retro": "1ded4c3fb5c7359e1c721affe2ab25ab4c394b1b5dac29b0052fe1157e66b18d",
    "chlom": "6bd98a2190d92c63ec4e39d93eb60701f965e23894552588650a2c49f077e80d",
    "commercial": "1fcbcde0f44b0c725a698edc0d00277a45dd705372ea413d5061ff25491f284d",
}
CREDENTIAL_PATTERNS = (
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
    r"\bsk-[A-Za-z0-9]{20,}\b",
)


def load(rel: str) -> dict[str, Any]:
    value = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"ERROR: object required: {rel}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main() -> int:
    for key, rel in FILES.items():
        require((ROOT / rel).is_file(), f"missing {rel}")
        require(sha(rel) == EXPECTED_SHA[key], f"digest drift: {rel}")

    manifest = load("developers/manifests/cie-current-main-interoperability.v1.json")
    require(manifest.get("manifest_version") == "1.1.0", "manifest version drift")
    require(manifest.get("canonical_main_observed") == MAIN, "canonical main drift")
    require(manifest.get("packet_author_may_self_approve") is False, "self approval enabled")
    require(manifest.get("d3_human_reserved") is True, "D3 reservation drift")

    framework = manifest.get("framework", {})
    require(framework.get("agent_suite_id") == "ct.agent-suite.cie-interoperability", "suite binding drift")
    require(framework.get("agent_machine_state") == "PRECERT_CONTRACT_VALIDATION_ONLY", "agent-machine state drift")
    require(framework.get("operationally_enabled") is False, "framework operational")
    require(framework.get("vote_eligible") is False, "framework voting")
    require(framework.get("parent_certification_agent") == "ct.relay.agent-d", "Agent D boundary drift")

    child = manifest.get("child_candidate", {})
    require(child.get("public_packet_exposes_exact_child_head") is False, "private child head exposed")
    require(child.get("current_exact_head_receipt_state") == "pending", "child receipt falsely complete")

    machine = manifest.get("agent_machine", {})
    for key in (
        "parent_vote_eligible",
        "subagent_vote_eligible",
        "subagent_quorum_eligible",
        "delegated_children_may_verify_c_originated_work",
        "operationally_enabled",
        "runtime_dispatch_enabled",
        "chlom_write_enabled",
        "retroactive_scan_execution_enabled",
        "convergent_handoff_execution_enabled",
    ):
        require(machine.get(key) is False, f"agent-machine boundary drift: {key}")
    require(machine.get("subagent_count") == 6, "subagent count drift")
    require(machine.get("d3_human_reserved") is True, "agent-machine D3 drift")
    require(machine.get("private_child_exact_head_receipt_state") == "pending_governed_private_verification", "private receipt state drift")
    require(machine.get("suite_sha256") == EXPECTED_SHA["suite"], "suite manifest digest drift")
    require(machine.get("protected_runtime_contract", {}).get("sha256") == EXPECTED_SHA["runtime"], "runtime manifest digest drift")
    require(machine.get("retroactive_scan_contract", {}).get("sha256") == EXPECTED_SHA["retro"], "retro manifest digest drift")
    require(machine.get("chlom_record_contract", {}).get("sha256") == EXPECTED_SHA["chlom"], "CHLOM manifest digest drift")
    require(machine.get("commercialization_contract", {}).get("sha256") == EXPECTED_SHA["commercial"], "commercial manifest digest drift")

    suite = load(FILES["suite"])
    require(suite.get("private_child_exact_head_evidence") == "GOVERNED_PRIVATE_RECEIPT_PENDING", "private child evidence boundary drift")
    parent = suite.get("parent_agent", {})
    require(parent.get("vote_eligible") is False and parent.get("quorum_eligible") is False, "parent agent voting")
    require(parent.get("d3_human_reserved") is True, "suite D3 drift")
    children = suite.get("subagents", [])
    require(len(children) == 6, "suite child count drift")
    for child_agent in children:
        require(child_agent.get("vote_eligible") is False, f"subagent voting: {child_agent.get('agent_id')}")
        require(child_agent.get("quorum_eligible") is False, f"subagent quorum: {child_agent.get('agent_id')}")
        require(child_agent.get("operationally_enabled") is False, f"subagent operational: {child_agent.get('agent_id')}")
    rules = suite.get("delegation_rules", {})
    for key in (
        "children_may_independently_verify_c_originated_work",
        "children_may_certify_parent_work",
        "children_may_cast_sovereign_vote",
        "children_may_create_vote_receipt",
        "children_may_change_quorum",
        "children_may_remove_agent_d",
        "children_may_exercise_d3",
        "sync_agents_allowed",
    ):
        require(rules.get(key) is False, f"delegation authority drift: {key}")

    runtime = load(FILES["runtime"])
    require(runtime.get("dispatch_enabled") is False, "runtime dispatch enabled")
    require(runtime.get("network_endpoint_public") is False, "runtime endpoint public")
    require(runtime.get("credential_locator_public") is False, "runtime credential locator public")
    require(runtime.get("private_runtime_topology_public") is False, "runtime topology public")
    require(runtime.get("algorithm", {}).get("public_contract_digest") == DIGEST, "protected algorithm digest drift")
    require(runtime.get("current_state") == "HOLD_RUNTIME_DISPATCH_NOT_CERTIFIED", "runtime HOLD drift")

    retro = load(FILES["retro"])
    require(retro.get("mode") == "PLAN_ONLY", "retro mode drift")
    require(retro.get("planning_allowed") is True, "retro planning unexpectedly disabled")
    for key in ("execution_allowed", "provider_read_allowed", "provider_write_allowed", "database_write_allowed", "customer_write_allowed"):
        require(retro.get(key) is False, f"retro execution boundary drift: {key}")
    require(retro.get("research_policy", {}).get("registry_growth_alone_is_certification_debt") is False, "registry growth treated as debt")
    require(retro.get("research_policy", {}).get("delegated_builder_may_verify_c_originated_work") is False, "delegated self verification")
    require(retro.get("downstream", {}).get("state") == "RESEARCH_CANDIDATE_SOURCE_DISCOVERY", "Convergent state drift")
    require(retro.get("downstream", {}).get("activation_allowed") is False, "Convergent activation enabled")

    chlom = load(FILES["chlom"])
    for key in ("write_enabled", "database_mutation_enabled", "provider_mutation_enabled"):
        require(chlom.get(key) is False, f"CHLOM write boundary drift: {key}")
    for key, value in chlom.get("effect_locks", {}).items():
        require(value is False, f"CHLOM effect enabled: {key}")
    require(chlom.get("current_state") == "HOLD_CHLOM_WRITE_NOT_AUTHORIZED", "CHLOM HOLD drift")

    commercial = load(FILES["commercial"])
    for key in (
        "exact_price_authorized",
        "stripe_product_created",
        "stripe_price_created",
        "checkout_enabled",
        "payment_link_active",
        "license_grant_active",
        "certification_status_active",
        "customer_entitlement_active",
        "automatic_fulfillment_enabled",
    ):
        require(commercial.get(key) is False, f"commercial activation drift: {key}")
    require(all(item.get("fulfillment_enabled") is False for item in commercial.get("candidate_offers", [])), "candidate fulfillment enabled")

    governance = manifest.get("governance", {})
    require(governance.get("sovereign_voters") == ["A", "B", "C", "D", "S"], "sovereign voter set drift")
    require(governance.get("minimum_approvals") == 4, "quorum drift")
    require(governance.get("agent_d_mandatory") is True, "Agent D no longer mandatory")

    public_files = [
        *FILES.values(),
        "developers/manifests/cie-current-main-interoperability.v1.json",
        "doctrine/cultural-imprint-engine.mdx",
        "changelog/phase-2-99-cie-current-main-interoperability.mdx",
    ]
    joined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in public_files)
    require("crownthrive1/CrownThrive-CIE" not in joined, "private child repository name exposed")
    require("github_repository_id" not in joined, "private repository identifier exposed")
    for pattern in CREDENTIAL_PATTERNS:
        require(re.search(pattern, joined) is None, "credential-shaped value detected")
    for forbidden in (
        '"vote_eligible": true',
        '"quorum_eligible": true',
        '"operationally_enabled": true',
        '"runtime_dispatch_enabled": true',
        '"checkout_enabled": true',
        '"customer_entitlement_active": true',
    ):
        require(forbidden not in joined, f"forbidden activation fragment: {forbidden}")

    workflow = (ROOT / ".github/workflows/cie-current-main-interoperability.yml").read_text(encoding="utf-8")
    require("id-token: write" not in workflow, "parent workflow granted OIDC")
    require("python3 scripts/validate_cie_agent_machine_public.py" in workflow, "agent-machine validator not wired")
    require("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1" in workflow, "checkout action not pinned")
    require("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7" in workflow, "setup-python action not pinned")

    doctrine = (ROOT / "doctrine/cultural-imprint-engine.mdx").read_text(encoding="utf-8")
    changelog = (ROOT / "changelog/phase-2-99-cie-current-main-interoperability.mdx").read_text(encoding="utf-8")
    for phrase in ("Agent-machine contract", "Retroactive ecosystem scan", "Institutionalization and commercialization boundary"):
        require(phrase in doctrine, f"doctrine section missing: {phrase}")
    require("PRECERT_CONTRACT_VALIDATION_ONLY" in changelog, "changelog state missing")

    print("CIE public agent-machine validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
