#!/usr/bin/env python3
"""Validate CrownThrive-Support repository governance enforcement state.

This validator makes the observed S106 control-plane state machine-addressable and
prevents documentation from promoting automated governance monitoring to
fail-closed merge enforcement before GitHub enforcement evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/repository-governance-enforcement-state.v1.json"
WORKFLOW = ROOT / ".github/workflows/docs-governance.yml"
SOURCE_REGISTER = ROOT / "knowledge/source-register.mdx"
STANDARD = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"
TOPOLOGY = ROOT / "changelog/phase-2-99-workstream-1-repository-source-topology.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"
CHARTER = ROOT / "standards/ten-phase-institutional-program-charter.mdx"
RELAY = ROOT / "automation/institutional-hourly-agent-relay.mdx"
CHANGELOG = ROOT / "changelog/phase-2-99-governance-as-code-enforcement-audit.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def text(path: Path) -> str:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(path: Path, fragment: str) -> None:
    if fragment not in text(path):
        fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")


def main() -> int:
    if not MANIFEST.is_file():
        fail(f"Missing manifest: {MANIFEST.relative_to(ROOT)}")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    expected_scalars = {
        "manifest_version": "1.0.0",
        "manifest_id": "ct.manifest.repository-governance-enforcement.v1",
        "source_id": "S106",
        "phase": "2.99",
        "repository": "crownthrive1/CrownThrive-Support",
        "branch": "main",
        "current_state": "monitoring_plus_post_merge_defense_in_depth",
        "merge_gate_enforced": False,
        "policy_transition_enforcement": "partial_validator_layer_only",
        "docs_impact": "docs_updated",
        "phase_3_entry_effect": "blocking_until_merge_gate_enforcement_is_proven",
    }
    for key, expected in expected_scalars.items():
        if data.get(key) != expected:
            fail(f"{key} drifted: {data.get(key)!r} != {expected!r}")

    workflow = data.get("workflow", {})
    if workflow != {
        "name": "Documentation Governance",
        "job": "Validate institutional documentation",
        "pull_request_validation": True,
        "push_to_main_revalidation": True,
    }:
        fail(f"Workflow state drifted: {workflow!r}")

    observed = data.get("observed_enforcement", {})
    if observed.get("branch_protected") is not False:
        fail("S106 currently requires branch_protected=false")
    if observed.get("classic_branch_protection_enabled") is not False:
        fail("S106 currently requires classic_branch_protection_enabled=false")
    if observed.get("required_status_checks_enforcement") != "off":
        fail("S106 currently requires required_status_checks_enforcement=off")
    if observed.get("required_contexts") != [] or observed.get("required_checks") != []:
        fail("S106 current observation must not fabricate required contexts/checks")
    if observed.get("ruleset_inventory") != "not_directly_enumerated_by_current_connector":
        fail("Ruleset inventory uncertainty must remain explicit")

    target = data.get("target", {})
    if target.get("branch") != "main":
        fail("Target branch must remain main")
    if target.get("required_check") != "Validate institutional documentation":
        fail("Target institutional validation check drifted")
    if target.get("failed_check_mergeability") != "blocked":
        fail("Target must require failed checks to block merge")
    if target.get("post_merge_revalidation") is not True:
        fail("Post-merge main revalidation must remain required")
    if target.get("bypass_authority") != "explicit_D3_decision":
        fail("Bypass authority must remain an explicit D3 decision")

    required_promotions = {
        "effective_main_ruleset_or_branch_policy_evidence",
        "exact_required_status_check_evidence",
        "blocked_failing_check_merge_test_or_equivalent",
        "documented_bypass_authority",
    }
    if set(data.get("promotion_requirements", [])) != required_promotions:
        fail("Promotion requirements drifted")

    forbidden = set(data.get("forbidden_promotions", []))
    must_forbid = {
        "monitoring_only_to_merge_gate_enforced_without_control_plane_evidence",
        "historical_to_current_without_effective_source_authority",
        "unverified_to_production_verified_without_runtime_evidence",
        "provider_capability_to_crownthrive_deployed_without_account_deployment_evidence",
        "payment_to_entitlement_without_fulfillment_evidence",
        "product_listing_to_rights_granted_without_valid_license_rights_evidence",
        "source_active_domain_to_current_secure_canonical_host_without_registrar_dns_tls_runtime_evidence",
    }
    if forbidden != must_forbid:
        fail("Forbidden-promotion policy drifted")

    workflow_text = text(WORKFLOW)
    for fragment in (
        "name: Documentation Governance",
        "name: Validate institutional documentation",
        "pull_request:",
        "push:",
        "- main",
        "python scripts/validate_docs.py",
    ):
        if fragment not in workflow_text:
            fail(f"Governance workflow missing expected fragment: {fragment!r}")

    require(SOURCE_REGISTER, "| `S106` | CrownThrive-Support GitHub governance-enforcement audit")
    require(STANDARD, "## Governance-as-code enforcement tiers")
    require(STANDARD, "fail_closed_required_check_enforcement: not_established")
    require(TOPOLOGY, "hard Phase 2.99 repository-governance gap")
    require(PLAN, "fail-closed repository governance for `main`")
    require(GATE, "repository-enforcement checkpoint is reopened and blocking")
    require(GATE, "validator output alone is insufficient for Phase 3 fail-closed governance")
    require(CHARTER, "Downstream update — CrownThrive-Support governance-as-code enforcement audit")
    require(RELAY, "## Repository governance enforcement state")
    require(CHANGELOG, "current_classification: monitoring_plus_defense_in_depth")

    # Critical anti-promotion invariant: while S106 says main is unprotected/off,
    # the machine state is forbidden from claiming fail-closed enforcement.
    if observed.get("branch_protected") is False and data.get("merge_gate_enforced") is not False:
        fail("Cannot promote to merge_gate_enforced while branch_protected=false")
    if observed.get("required_status_checks_enforcement") == "off" and data.get("merge_gate_enforced"):
        fail("Cannot promote to merge_gate_enforced while required status checks are off")

    print("Repository governance enforcement state validation passed.")
    print("Current state: monitoring_plus_post_merge_defense_in_depth")
    print("Merge gate enforced: false")
    print("Phase 3 effect: blocking until effective required-check enforcement is proven")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
