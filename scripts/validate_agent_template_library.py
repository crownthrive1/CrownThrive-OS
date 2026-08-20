#!/usr/bin/env python3
"""Validate CrownThrive agent templates, delegation policy, R&D fabric and lineage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-template-library.v1.json"
LINEAGE = ROOT / "developers/manifests/agent-lineage-archive.v1.json"
DELEGATION = ROOT / "developers/manifests/agent-factory-delegation-policy.v1.json"
RND = ROOT / "developers/manifests/agent-rnd-specialist-fabric.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Missing required JSON: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail(f"Expected object in {path.relative_to(ROOT)}")
    return data


def require_text(path: str, *fragments: str) -> None:
    p = ROOT / path
    if not p.is_file():
        fail(f"Missing required file: {path}")
    text = p.read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in text:
            fail(f"Missing required fragment {fragment!r} in {path}")


def validate_delegation_policy() -> None:
    data = load_json(DELEGATION)
    if data.get("manifest_id") != "ct.manifest.agent-factory-delegation-policy.v1":
        fail("Delegation-policy identity drifted")
    if data.get("phase") != "2.99" or data.get("roadmap_generation") != "ten_phase_v1":
        fail("Delegation policy must remain Phase 2.99 / ten_phase_v1")
    if data.get("governance_decision") != "CT-ADR-GOV-011":
        fail("Delegation policy must inherit CT-ADR-GOV-011")

    vote = data.get("sovereign_vote_invariant", {})
    expected_voters = {
        "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
        "ct.relay.agent-d", "ct.relay.agent-s",
    }
    if set(vote.get("voters", [])) != expected_voters:
        fail("Delegation policy sovereign voter set drifted")
    for key in ("children_add_votes", "confidence_adds_votes", "same_family_children_independent", "d3_by_quorum"):
        if vote.get(key) is not False:
            fail(f"Delegation vote invariant must remain false: {key}")

    child = data.get("child_contract", {})
    required_child_fields = {
        "child_run_id", "parent_agent_id", "root_agent_id", "delegation_path",
        "independence_family", "role_class", "scope_key", "source_snapshot",
        "allowed_tools", "allowed_data_classes", "authority_ceiling", "budget",
        "ttl", "output_class", "promotion_route", "termination_state",
    }
    if set(child.get("required_fields", [])) != required_child_fields:
        fail("Delegated child contract fields drifted")
    if child.get("default_vote_eligible") is not False or child.get("default_production_write") is not False:
        fail("Delegated children must default non-voting and non-writing")
    if child.get("archive_required_for_material_output") is not True:
        fail("Material child output must remain archive/reconstruction capable")

    rows = data.get("spawn_matrix", [])
    if not isinstance(rows, list):
        fail("spawn_matrix must be a list")
    by_id = {row.get("agent_id"): row for row in rows if isinstance(row, dict)}
    required_ids = {
        "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
        "ct.relay.agent-d", "ct.relay.agent-s",
        "ct.specialist.agent-e", "ct.specialist.agent-f", "ct.specialist.agent-g", "ct.specialist.agent-h",
        "ct.subagent.continuity-recovery", "ct.subagent.phase3-snapshot-packet", "ct.subagent.roadmap-transition",
        "ct.subagent.reconciliation-tag-sentinel", "ct.subagent.permissioned-source-reconciler",
        "ct.subagent.reconciliation-proof-verifier", "ct.subagent.draft-reconciliation-integrator",
        "ct.subagent.integration-heartbeat", "ct.subagent.credential-continuity", "ct.subagent.vendor-engine-watch",
        "ct.agent.domain-factory",
    }
    if not required_ids.issubset(by_id):
        fail(f"Spawn matrix missing required agents: {sorted(required_ids - set(by_id))}")
    if by_id["ct.relay.agent-d"].get("spawn_mode") != "checks_only":
        fail("Agent D must remain checks-only for delegated children")
    if by_id["ct.subagent.reconciliation-proof-verifier"].get("spawn_mode") != "deterministic_subchecks_only":
        fail("Agent N may only delegate deterministic proof subchecks")
    if by_id["ct.subagent.phase3-snapshot-packet"].get("spawn_mode") != "minimal_collection_only":
        fail("Agent J must remain minimal-collection only")
    if by_id["ct.subagent.permissioned-source-reconciler"].get("spawn_mode") != "source_family_fanout":
        fail("Agent M must preserve source-family fanout semantics")
    for probe in ("ct.subagent.integration-heartbeat", "ct.subagent.credential-continuity", "ct.subagent.vendor-engine-watch"):
        if by_id[probe].get("spawn_mode") != "none" or by_id[probe].get("max_depth") != 0:
            fail(f"Operational probe may not spawn durable children: {probe}")

    same_family = data.get("same_family_independence", {})
    for key in ("descendant_may_verify_ancestor_as_independent", "sibling_descendants_count_as_independent_of_same_root", "children_count_toward_quorum"):
        if same_family.get(key) is not False:
            fail(f"Same-family independence invariant must remain false: {key}")
    if same_family.get("independent_verifier_must_have_distinct_governed_independence_family") is not True:
        fail("Independent verifier must come from a distinct governed independence family")

    research = data.get("research_policy", {})
    if research.get("default_state") != "RESEARCH_CANDIDATE":
        fail("Research default state must remain RESEARCH_CANDIDATE")
    if research.get("direct_transition_to_pass") is not False:
        fail("Research may not transition directly to PASS")
    if research.get("registry_growth_is_certification_drift_by_default") is not False:
        fail("Research registry growth is not certification drift by count alone")
    expected_route = [
        "rnd_discovery",
        "ct.subagent.permissioned-source-reconciler",
        "ct.subagent.reconciliation-proof-verifier",
        "applicable_domain_specialist",
        "ct.relay.agent-b",
        "ct.relay.agent-c_if_implementation_required",
        "ct.relay.agent-s",
        "ct.relay.agent-d",
        "sovereign_acceptance_or_reserved_human_authority",
    ]
    if research.get("promotion_route") != expected_route:
        fail("R&D promotion route drifted")


def validate_rnd_fabric() -> None:
    data = load_json(RND)
    if data.get("manifest_id") != "ct.manifest.agent-rnd-specialist-fabric.v1":
        fail("R&D fabric identity drifted")
    if data.get("vote_eligible") is not False or data.get("direct_pass_prohibited") is not True:
        fail("R&D fabric must remain non-voting and direct-PASS prohibited")
    if data.get("default_state") != "RESEARCH_CANDIDATE":
        fail("R&D fabric default state drifted")
    expected_ids = {
        "ct.subagent.rnd.legal-regulatory",
        "ct.subagent.rnd.ip-rights-licensing",
        "ct.subagent.rnd.finance-tax-treasury",
        "ct.subagent.rnd.blockchain-cryptographic-protocol",
        "ct.subagent.rnd.accessibility-consumer-protection",
        "ct.subagent.rnd.regional-global-localization",
    }
    rows = data.get("specialists", [])
    if {row.get("agent_id") for row in rows if isinstance(row, dict)} != expected_ids:
        fail("R&D specialist set drifted")
    for row in rows:
        if row.get("vote_eligible") is not False or row.get("default_state") != "RESEARCH_CANDIDATE":
            fail(f"R&D specialist authority drift: {row.get('agent_id')}")
        if row.get("may_advance_phase") is not False or row.get("may_mark_pass") is not False:
            fail(f"R&D specialist may not advance phase or mark PASS: {row.get('agent_id')}")
        if row.get("production_write_default") is not False or row.get("max_depth") != 2:
            fail(f"R&D specialist delegation defaults drifted: {row.get('agent_id')}")
    growth = data.get("growth_accounting", {})
    if growth.get("research_registry_growth_expected") is not True:
        fail("Research registry growth must be explicitly expected")
    if growth.get("research_growth_is_formal_coverage_gap") is not False:
        fail("Research growth may not be formal coverage gap by count alone")
    promotion = data.get("promotion", {})
    if promotion.get("promotion_required_before_pass") is not True:
        fail("R&D promotion must be required before PASS")
    if promotion.get("promotion_required_before_hard_exit_coverage_accounting") is not True:
        fail("R&D promotion must precede hard-exit denominator inclusion")


def main() -> int:
    data = load_json(MANIFEST)
    if data.get("manifest_id") != "ct.manifest.agent-template-library.v1":
        fail("Agent-template manifest identity drifted")
    if data.get("phase") != "2.99" or data.get("roadmap_generation") != "ten_phase_v1":
        fail("Agent-template phase/roadmap identity drifted")
    if data.get("governance_decision") != "CT-ADR-GOV-011":
        fail("Agent-template system must inherit CT-ADR-GOV-011")

    expected_voters = {
        "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
        "ct.relay.agent-d", "ct.relay.agent-s",
    }
    if set(data.get("sovereign_voters", [])) != expected_voters:
        fail("Sovereign voter set drifted")
    if data.get("required_automatic_merge_approvals") != 4:
        fail("Automatic merge quorum must remain 4 of 5")
    if data.get("mandatory_gatekeeper") != "ct.relay.agent-d":
        fail("Agent D must remain mandatory gatekeeper")

    scheduled = data.get("scheduled_specialists", [])
    embedded = data.get("embedded_specialists", [])
    helpers = data.get("reusable_helpers", [])
    expected_scheduled = {"ct.specialist.agent-e", "ct.specialist.agent-f", "ct.specialist.agent-g", "ct.specialist.agent-h"}
    expected_embedded = {"ct.subagent.continuity-recovery", "ct.subagent.phase3-snapshot-packet", "ct.subagent.roadmap-transition"}
    if {x.get("agent_id") for x in scheduled} != expected_scheduled:
        fail("Scheduled E/F/G/H specialist set drifted")
    if {x.get("agent_id") for x in embedded} != expected_embedded:
        fail("Embedded I/J/K specialist set drifted")
    for row in [*scheduled, *embedded, *helpers]:
        if row.get("vote_eligible") is not False:
            fail(f"Non-voting specialist/helper became vote eligible: {row.get('agent_id')}")

    delegation = data.get("delegation_policy", {})
    if delegation.get("manifest") != "developers/manifests/agent-factory-delegation-policy.v1.json":
        fail("Agent library missing delegation-policy manifest")
    if delegation.get("children_add_votes") is not False or delegation.get("same_family_independence_prohibited") is not True:
        fail("Agent library delegation invariants drifted")
    if delegation.get("persistent_child_registration_required") is not True or delegation.get("ephemeral_children_require_ttl_budget_and_lineage") is not True:
        fail("Persistent/ephemeral child controls drifted")

    rnd = data.get("rnd_specialist_fabric", {})
    if rnd.get("manifest") != "developers/manifests/agent-rnd-specialist-fabric.v1.json":
        fail("Agent library missing R&D fabric manifest")
    if rnd.get("default_state") != "RESEARCH_CANDIDATE" or rnd.get("direct_pass_prohibited") is not True:
        fail("R&D library boundary drifted")
    if rnd.get("research_growth_is_formal_coverage_gap") is not False:
        fail("R&D growth may not be classified as formal proof gap by count alone")

    for template in data.get("source_templates", []):
        if not (ROOT / template).is_file():
            fail(f"Missing source template: {template}")
    require_text("developers/templates/README.md",
                 "Do not copy a scheduler prompt and call it an agent",
                 "Material role changes are versioned and archived",
                 "No third-party code is imported merely by the presence of these templates")
    require_text("developers/templates/agent-role-template.v1.yaml",
                 "template_version: 1.1.0", "independence_family:", "spawn_mode:",
                 "child_authority_ceiling:", "child_ttl_required: true", "child_budget_required: true",
                 "children_count_toward_sovereign_quorum: false", "persistent_child_registration_required: true")
    require_text("developers/templates/subagent-role-template.v1.yaml",
                 "template_version: 1.1.0", "root_agent_id:", "independence_family:",
                 "runtime_lifecycle: persistent_registered | ephemeral_child",
                 "children_count_toward_sovereign_quorum: false",
                 "research_candidate_to_pass_without_promotion")
    require_text("developers/templates/agent-pack-manifest-template.v1.json", '"checkout_enabled": false', '"price_status": "not_authorized"')
    require_text("developers/templates/chlom-capability-pallet-template.v1.yaml", "production_writes: false", "pricing_status: not_authorized", "checkout_enabled: false")
    require_text("developers/templates/chlom-runtime-adapter-template.v1.yaml",
                 "lifecycle: RESEARCH", "production_deployed: false",
                 "pii_on_public_immutable_ledger: prohibited",
                 "restricted_evidence_on_public_immutable_ledger: prohibited",
                 "production_token_sale: prohibited_by_template",
                 "earliest_activation_phase: 9",
                 "may_inherit_production_authority_from_research: false",
                 "checkout_enabled: false")
    require_text("developers/templates/third-party-attribution-template.v1.yaml", "license_spdx:", "distribution_allowed: false", "exact upstream license")

    validate_delegation_policy()
    validate_rnd_fabric()

    lineage = load_json(LINEAGE)
    if lineage.get("manifest_id") != "ct.manifest.agent-lineage-archive.v1":
        fail("Agent lineage archive identity drifted")
    if lineage.get("archive_policy") != "append_only_preserve_predecessors":
        fail("Agent lineage archive must remain append-only")
    expected_generations = {
        "generation_0_ad_hoc", "generation_1_four_role_relay",
        "generation_2_five_voter_sovereign_relay", "generation_3_scheduled_specialist_ring",
        "generation_4_embedded_specialists", "generation_5_governed_factory_rnd_fabric",
    }
    generations = lineage.get("generations", [])
    if {x.get("generation_id") for x in generations} != expected_generations:
        fail("Agent lineage generation set drifted")
    if lineage.get("current_generation") != "generation_5_governed_factory_rnd_fabric":
        fail("Current agent generation must be governed factory/R&D fabric")
    current = next((x for x in generations if x.get("generation_id") == "generation_5_governed_factory_rnd_fabric"), None)
    if not current or current.get("vote_eligible") is not False:
        fail("Governed factory/R&D generation must remain non-voting")
    if current.get("children_add_votes") is not False or current.get("same_family_independent") is not False or current.get("research_direct_pass") is not False:
        fail("Generation-5 authority invariants drifted")
    if (lineage.get("template_generation") or {}).get("version") != "1.1.0":
        fail("Template lineage must record generation 1.1.0")
    continuity = lineage.get("continuity_rules", {})
    for key in (
        "stable_ids_survive_prompt_rewording", "scheduler_ids_are_not_institutional_identity",
        "prior_accepted_versions_remain_reconstructable", "retired_agents_remain_queryable_as_history",
        "commercial_and_internal_versions_are_separate", "delegated_children_preserve_parent_root_lineage",
        "same_family_children_do_not_create_independence", "research_candidates_not_certification_by_count_alone",
    ):
        if continuity.get(key) is not True:
            fail(f"Agent lineage continuity invariant missing: {key}")
    if continuity.get("raw_secrets_or_restricted_evidence_in_archive") is not False:
        fail("Agent lineage archive may not contain raw secrets/restricted evidence")

    inv = data.get("default_invariants", {})
    for key in (
        "specialists_and_subagents_non_voting", "self_approval_prohibited",
        "unknown_to_pass_without_evidence_prohibited", "secret_or_fingerprint_output_prohibited",
        "archive_prior_versions", "changelog_required_for_material_change",
    ):
        if inv.get(key) is not True:
            fail(f"Required agent-template invariant missing: {key}")
    for key in (
        "phase_advance_by_template", "production_write_default", "children_add_sovereign_votes",
        "same_family_can_manufacture_independence", "research_candidate_can_directly_pass",
        "research_registry_growth_is_certification_drift_by_count_alone",
    ):
        if inv.get(key) is not False:
            fail(f"Required false agent-template invariant drifted: {key}")

    docs = data.get("documentation", {})
    doc_expectations = {
        "agent_registry": ["A/B/C/D/S", "Agent I", "Agent K"],
        "relay": ["Agent E", "Agent H", "ct.subagent.phase3-snapshot-packet"],
        "permissions": ["Scheduled specialist and embedded subagent delegation"],
        "factory": ["Agent factory template system", "Agent K"],
        "templates": ["Fluid cognition, rigid authority", "RESEARCH_CANDIDATE", "same governed root", "CT:CERTIFICATION-SCOPE"],
        "factory_delegation": ["Agent Factory Delegation", "independence family", "TTL", "budget"],
        "lineage_archive": ["Generation 5", "Template generation 1.1.0"],
        "tag_reconciliation": ["CT:RESEARCH-CANDIDATE", "research expansion", "certification scope"],
        "changelog_index": ["Institutional Changelog Index", "subject-specific"],
        "major_change": ["Agent Factory Delegation", "RESEARCH_CANDIDATE", "same-family", "scheduler"],
        "factory_change": ["Agent Factory Delegation", "RESEARCH_CANDIDATE", "same-family", "scheduler"],
        "chlom_pallet_map": ["chlom-capability-pallet-template.v1.yaml", "chlom-runtime-adapter-template.v1.yaml", "not automatically blockchain code"],
    }
    for key, fragments in doc_expectations.items():
        path = docs.get(key)
        if not path:
            fail(f"Missing documentation mapping: {key}")
        require_text(path, *fragments)

    phase_state = data.get("phase_state", {})
    if phase_state.get("current") != "2.99" or phase_state.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
        fail("Agent-template patch must not open Phase 3")

    commerce = data.get("commercialization", {})
    if commerce.get("checkout_enabled") is not False or commerce.get("price_status") != "not_authorized":
        fail("Agent/template commercialization must remain disabled/unpriced")
    if commerce.get("stripe_product_id") is not None or commerce.get("stripe_price_id") is not None:
        fail("Agent/template Stripe IDs must remain unset")
    if commerce.get("internal_private_authority_sold") is not False:
        fail("Internal CrownThrive authority may not be sold")

    print("Agent template library validation passed.")
    print("Sovereign voters remain A/B/C/D/S only; delegated children never add votes.")
    print("Same-family descendants cannot manufacture independent verification.")
    print("R&D defaults to RESEARCH_CANDIDATE and stays outside certification accounting until governed promotion/material touch.")
    print("Template generation 1.1.0 enforces parent/root lineage, authority ceilings, TTL/budget and termination state.")
    print("Phase 3 remains blocked; commercialization remains scaffolded only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
