#!/usr/bin/env python3
"""Validate the CrownThrive agent-template / CHLOM pallet institutionalization layer."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-template-library.v1.json"
LINEAGE = ROOT / "developers/manifests/agent-lineage-archive.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require_text(path: str, *fragments: str) -> None:
    p = ROOT / path
    if not p.is_file():
        fail(f"Missing required file: {path}")
    text = p.read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in text:
            fail(f"Missing required fragment {fragment!r} in {path}")


def main() -> int:
    if not MANIFEST.is_file():
        fail("Missing agent-template library manifest")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if data.get("manifest_id") != "ct.manifest.agent-template-library.v1":
        fail("Agent-template manifest identity drifted")
    if data.get("phase") != "2.99" or data.get("roadmap_generation") != "ten_phase_v1":
        fail("Agent-template phase/roadmap identity drifted")
    if data.get("governance_decision") != "CT-ADR-GOV-011":
        fail("Agent-template system must inherit CT-ADR-GOV-011")

    expected_voters = {
        "ct.relay.agent-a",
        "ct.relay.agent-b",
        "ct.relay.agent-c",
        "ct.relay.agent-d",
        "ct.relay.agent-s",
    }
    voters = set(data.get("sovereign_voters", []))
    if voters != expected_voters:
        fail(f"Sovereign voter set drifted: {sorted(voters)}")
    if data.get("required_automatic_merge_approvals") != 4:
        fail("Automatic merge quorum must remain 4 of 5")
    if data.get("mandatory_gatekeeper") != "ct.relay.agent-d":
        fail("Agent D must remain mandatory gatekeeper")

    scheduled = data.get("scheduled_specialists", [])
    embedded = data.get("embedded_specialists", [])
    helpers = data.get("reusable_helpers", [])
    expected_scheduled = {
        "ct.specialist.agent-e", "ct.specialist.agent-f",
        "ct.specialist.agent-g", "ct.specialist.agent-h",
    }
    if {x.get("agent_id") for x in scheduled} != expected_scheduled:
        fail("Scheduled E/F/G/H specialist set drifted")
    expected_embedded = {
        "ct.subagent.continuity-recovery",
        "ct.subagent.phase3-snapshot-packet",
        "ct.subagent.roadmap-transition",
    }
    if {x.get("agent_id") for x in embedded} != expected_embedded:
        fail("Embedded I/J/K specialist set drifted")
    for row in [*scheduled, *embedded, *helpers]:
        if row.get("vote_eligible") is not False:
            fail(f"Non-voting specialist/helper became vote eligible: {row.get('agent_id')}")

    for template in data.get("source_templates", []):
        if not (ROOT / template).is_file():
            fail(f"Missing source template: {template}")

    require_text("developers/templates/README.md",
                 "Do not copy a scheduler prompt and call it an agent",
                 "Material role changes are versioned and archived",
                 "No third-party code is imported merely by the presence of these templates")
    require_text("developers/templates/agent-role-template.v1.yaml",
                 "vote_eligible: false", "may_advance_phase: false",
                 "production_write_default: false", "archive_prior_versions: true")
    require_text("developers/templates/subagent-role-template.v1.yaml",
                 "vote_eligible: false", "may_advance_phase: false",
                 "sovereign_vote", "archive_prior_versions: true")
    require_text("developers/templates/agent-pack-manifest-template.v1.json",
                 '"checkout_enabled": false', '"price_status": "not_authorized"')
    require_text("developers/templates/chlom-capability-pallet-template.v1.yaml",
                 "production_writes: false", "pricing_status: not_authorized",
                 "checkout_enabled: false")
    require_text("developers/templates/chlom-runtime-adapter-template.v1.yaml",
                 "lifecycle: RESEARCH",
                 "production_deployed: false",
                 "pii_on_public_immutable_ledger: prohibited",
                 "restricted_evidence_on_public_immutable_ledger: prohibited",
                 "production_token_sale: prohibited_by_template",
                 "earliest_activation_phase: 9",
                 "may_inherit_production_authority_from_research: false",
                 "checkout_enabled: false")
    require_text("developers/templates/third-party-attribution-template.v1.yaml",
                 "license_spdx:", "distribution_allowed: false",
                 "exact upstream license")

    chlom_families = data.get("chlom_template_families", {})
    capability = chlom_families.get("capability_pallet", {})
    runtime = chlom_families.get("runtime_adapter", {})
    if capability.get("may_imply_blockchain_deployment") is not False:
        fail("Capability pallet may not imply blockchain/runtime deployment")
    if runtime.get("earliest_activation_phase") != 9:
        fail("CHLOM runtime adapter must remain Phase-9-or-later gated")
    if runtime.get("production_deployed_by_template") is not False:
        fail("Runtime-adapter template may not imply production deployment")

    if not LINEAGE.is_file():
        fail("Missing machine-readable agent lineage archive")
    lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))
    if lineage.get("manifest_id") != "ct.manifest.agent-lineage-archive.v1":
        fail("Agent lineage archive identity drifted")
    if lineage.get("archive_policy") != "append_only_preserve_predecessors":
        fail("Agent lineage archive must remain append-only")
    generations = lineage.get("generations", [])
    expected_generations = {
        "generation_0_ad_hoc",
        "generation_1_four_role_relay",
        "generation_2_five_voter_sovereign_relay",
        "generation_3_scheduled_specialist_ring",
        "generation_4_embedded_specialists",
    }
    if {x.get("generation_id") for x in generations} != expected_generations:
        fail("Agent lineage generation set drifted")
    current = next((x for x in generations if x.get("generation_id") == "generation_4_embedded_specialists"), None)
    if not current or current.get("vote_eligible") is not False:
        fail("Embedded I/J/K generation must remain non-voting")
    continuity = lineage.get("continuity_rules", {})
    for key in (
        "stable_ids_survive_prompt_rewording",
        "scheduler_ids_are_not_institutional_identity",
        "prior_accepted_versions_remain_reconstructable",
        "retired_agents_remain_queryable_as_history",
        "commercial_and_internal_versions_are_separate",
    ):
        if continuity.get(key) is not True:
            fail(f"Agent lineage continuity invariant missing: {key}")
    if continuity.get("raw_secrets_or_restricted_evidence_in_archive") is not False:
        fail("Agent lineage archive may not contain raw secrets/restricted evidence")

    inv = data.get("default_invariants", {})
    required_true = [
        "specialists_and_subagents_non_voting",
        "self_approval_prohibited",
        "unknown_to_pass_without_evidence_prohibited",
        "secret_or_fingerprint_output_prohibited",
        "archive_prior_versions",
        "changelog_required_for_material_change",
    ]
    for key in required_true:
        if inv.get(key) is not True:
            fail(f"Required agent-template invariant missing: {key}")
    if inv.get("phase_advance_by_template") is not False:
        fail("Templates may not advance phases")
    if inv.get("production_write_default") is not False:
        fail("Agent/template production-write default must remain false")

    commerce = data.get("commercialization", {})
    if commerce.get("checkout_enabled") is not False:
        fail("Agent/template checkout must remain disabled until separately authorized")
    if commerce.get("price_status") != "not_authorized":
        fail("Agent/template price must remain not_authorized")
    if commerce.get("stripe_product_id") is not None or commerce.get("stripe_price_id") is not None:
        fail("Agent/template Stripe IDs must remain unset before commercial authorization")
    if commerce.get("internal_private_authority_sold") is not False:
        fail("Internal CrownThrive authority may not be sold through template packaging")

    rights = data.get("third_party_rights", {})
    if rights.get("third_party_code_imported_by_this_patch") is not False:
        fail("This patch must not falsely claim third-party code import")
    for key in (
        "attribution_intake_template_required",
        "exact_upstream_license_verification_required_before_distribution",
        "notice_and_source_obligations_must_be_preserved",
        "trademark_constraints_must_be_preserved",
    ):
        if rights.get(key) is not True:
            fail(f"Third-party rights invariant missing: {key}")

    docs = data.get("documentation", {})
    doc_expectations = {
        "agent_registry": ["Agent I", "Agent K", "A/B/C/D/S"],
        "relay": ["Agent E", "Agent H", "ct.subagent.phase3-snapshot-packet"],
        "permissions": ["Scheduled specialist and embedded subagent delegation"],
        "factory": ["Agent factory template system", "Agent K"],
        "templates": ["CHLOM capability pallets", "CHLOM runtime/decentralized adapter templates", "Stripe commercialization state"],
        "lineage_archive": ["Generation 4", "Template generation 1.0.1"],
        "changelog_index": ["Institutional Changelog Index", "subject-specific"],
        "major_change": ["Agent Template & Pallet Institutionalization", "stripe_checkout_enabled: false", "runtime/decentralized adapter"],
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

    print("Agent template library validation passed.")
    print("Sovereign voters: A/B/C/D/S only; E/F/G/H and I/J/K are non-voting.")
    print("Template and lineage archives are machine-readable, version-preserving and secret-safe.")
    print("CHLOM capability pallets and runtime adapters remain distinct; runtime activation is Phase-9-or-later gated.")
    print("Template/pallet commercialization remains scaffolded only: checkout disabled, price not authorized.")
    print("Third-party distribution remains fail-closed pending exact license/attribution verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
