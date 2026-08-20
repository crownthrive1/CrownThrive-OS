#!/usr/bin/env python3
"""Fail-closed validator for CrownThrive ecosystem rollout and credit-commerce governance."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/ecosystem-rollout-certification.v1.json"
TECH_PATH = ROOT / "technology/ecosystem-rollout-certification-and-credit-commerce.mdx"
AGENT_PATH = ROOT / "automation/ecosystem-rollout-certifier-agent.mdx"
PHASE_PATH = ROOT / "standards/ecosystem-rollout-certification-phase-amendment.mdx"

EXPECTED_DIMENSIONS = {
    "stable_identity",
    "source_evidence",
    "provider_mapping",
    "auth_boundary",
    "read_capability",
    "write_capability",
    "design_brand_provenance",
    "interaction_accessibility",
    "rights_chain_of_title",
    "credit_commerce_eligibility",
    "fulfillment_delivery",
    "refund_dispute_reversal",
    "observability_dail",
    "recovery_provider_exit",
    "public_docs_claims",
    "lifecycle_release",
}

EXPECTED_QUEUES = {
    "ecosystem_rollout_certification",
    "credit_commerce_migration",
    "asset_release_certification",
    "provider_legacy_rail_exit",
    "commerce_canary_reconciliation",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_text(path: Path) -> str:
    require(path.exists(), f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    manifest_text = read_text(MANIFEST_PATH)
    try:
        m = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON manifest: {exc}")

    program = m.get("program", {})
    snapshot = m.get("runtime_snapshot", {})
    credit = m.get("credit_program", {})
    mcp = m.get("mcp", {})
    assets = m.get("asset_release_model", {})
    canaries = m.get("wave_0_canaries", {})
    stack = m.get("stack", {})

    require(m.get("schema_version") == "1.0.0", "unexpected manifest schema version")
    require(m.get("stable_id") == "ct.manifest.ecosystem-rollout-certification.v1", "stable manifest ID drift")
    require(program.get("program_id") == "ct.program.ecosystem-rollout-certification.v1", "program ID drift")
    require(program.get("agent_id") == "ct.agent.ecosystem-rollout-certifier", "rollout agent ID drift")
    require(program.get("current_phase") == "2.99", "this packet may not advance the current phase")
    require("blocked" in str(program.get("phase_3_entry", "")), "Phase 3 must remain blocked")
    require(program.get("sovereign_vote_created") is False, "rollout agent may not create a sovereign vote")

    require(snapshot.get("platforms_registered") == 28, "dated snapshot must preserve 28 registered rollout records")
    require(snapshot.get("certification_dimension_rows") == 448, "dated snapshot must preserve 448 certification rows")
    require(snapshot.get("certification_dimensions_per_platform") == 16, "certification dimension count must remain 16")
    require(snapshot.get("stable_ids_resolved") == 4, "do not fabricate additional resolved stable IDs")
    require(snapshot.get("identity_pending") == 24, "identity-pending count must remain explicit in this dated snapshot")
    require(snapshot.get("asset_delivery_canaries_pass") == 6, "all six current downloadable delivery canaries must remain recorded")
    require(snapshot.get("asset_delivery_canaries_total") == 6, "delivery canary denominator drift")
    require(snapshot.get("security_advisor_lints") == 0, "this snapshot records a clean post-hardening security advisor")

    require(set(m.get("certification_dimensions", [])) == EXPECTED_DIMENSIONS, "certification-dimension contract drift")
    require(set(m.get("rollout_queues", [])) == EXPECTED_QUEUES, "rollout factory queue contract drift")

    require(credit.get("program_id") == "ct.credit.store.v1", "credit program ID drift")
    require(credit.get("credits_per_usd") == 100, "credit conversion reference drift")
    require(credit.get("active") is False, "Store Credits may not be represented live in this packet")
    require(credit.get("legal_tax_state") == "specialist_review_required_before_live_activation", "legal/tax HOLD must remain explicit")
    require(credit.get("transferable") is False, "Store Credits must not become transferable")
    require(credit.get("cash_redeemable") is False, "Store Credits must not become cash redeemable")
    require(credit.get("interest_bearing") is False, "Store Credits must not become interest bearing")
    require(credit.get("crypto_or_token_authority") is False, "Store Credits must not become token/crypto authority")
    require(credit.get("crownrewards_separate") is True, "Store Credits and CrownRewards must remain separate")
    require(credit.get("payment_provider_role") == "funding_and_reconciliation_only", "payment provider role drift")
    require(credit.get("license_authority") == "CHLOM_THIVEBASE", "license authority drift")

    tiers = m.get("topup_tiers", [])
    require([x.get("credits") for x in tiers] == [1000, 2500, 5000, 10000, 25000], "top-up tier contract drift")
    require(all(x.get("credits") == x.get("usd_minor") for x in tiers), "100 credits = $1 reference must remain internally consistent")

    require(canaries.get("live_provider_server_readback") == "pass", "server-side provider readback evidence missing")
    require(canaries.get("synthetic_purchase") == "pass", "synthetic purchase canary evidence missing")
    require(canaries.get("synthetic_purchase_idempotency") == "pass", "purchase idempotency canary evidence missing")
    require(canaries.get("synthetic_license_issue") == "pass", "license canary evidence missing")
    require(canaries.get("synthetic_membership") == "pass", "membership canary evidence missing")
    require(canaries.get("synthetic_refund_reversal") == "pass", "refund reversal canary evidence missing")
    require(canaries.get("private_delivery_all_current_downloadable_assets") == "pass", "delivery canary evidence missing")
    require(canaries.get("live_provider_refund_dispute_reversal") == "pending", "live provider reversal proof must not be fabricated")

    require(assets.get("package_integrity_separate") is True, "package integrity must remain an independent dimension")
    require(assets.get("rights_separate") is True, "rights state must remain independent")
    require(assets.get("license_terms_separate") is True, "license terms must remain independent")
    require(assets.get("private_delivery_separate") is True, "delivery state must remain independent")
    require(assets.get("commerce_rail_separate") is True, "commerce rail must remain independent")
    require(assets.get("current_overall_state") == "technical_pass_legal_hold", "do not promote packaged assets beyond current legal/terms authority")

    require(stack.get("design_control_pr") == 147, "design-control parent lineage drift")
    require(stack.get("website_surface_pr") == 152, "website-surface parent lineage drift")
    require(stack.get("current_main_reconciliation_required_before_promotion") is True, "current-main reconciliation cannot be waived")

    require(mcp.get("service_id") == "ecosystem_rollout_control", "rollout MCP service ID drift")
    require(mcp.get("protocol") == "2026-07-28", "rollout MCP protocol drift")
    require(mcp.get("verify_jwt") is True, "rollout MCP must require JWT")
    require(mcp.get("authenticated_end_to_end_mcp_probe") == "pending", "authenticated MCP probe may not be represented as PASS yet")
    require("disabled" in str(mcp.get("central_dispatch", "")), "central dispatch must remain disabled")
    require(mcp.get("external_provider_mutation") is False, "rollout MCP may not mutate external providers")
    require(mcp.get("phase_advancement") is False, "rollout MCP may not advance phases")

    waves = {x.get("wave"): x for x in m.get("credit_migration_waves", [])}
    require(waves.get(1, {}).get("state") == "inventory_keep_legacy_rail", "KJV/Sermon legacy rail must remain until replacement proof")
    require(waves.get(2, {}).get("state") == "inventory_keep_legacy_rail", "Virality legacy rail must remain until replacement proof")
    require(waves.get(2, {}).get("soundcloud_api") == "REMOVED_BY_FOUNDER_OVERRIDE", "SoundCloud API founder override must remain preserved")

    no_go = set(m.get("absolute_no_go", []))
    required_no_go = {
        "phase_3_entered_while_phase_2_99_blocked",
        "store_credits_live_while_legal_tax_state_not_accepted",
        "payment_provider_metadata_grants_crownthrive_license",
        "synthetic_canary_represented_as_live_provider_proof",
        "legacy_production_payment_or_webhook_retired_before_replacement_proof",
        "institutional_platform_id_invented_from_name_similarity",
        "direct_mcp_deployment_equals_central_dispatch_or_provider_write_certification",
        "rollout_agent_creates_sovereign_vote_or_self_approval",
    }
    require(required_no_go.issubset(no_go), "one or more absolute no-go rules were removed")

    tech = read_text(TECH_PATH)
    agent = read_text(AGENT_PATH)
    phase = read_text(PHASE_PATH)

    for token in [
        "technical_pass_legal_hold",
        "ct.credit.store.v1",
        "ct.agent.ecosystem-rollout-certifier",
        "Phase 3 remains blocked",
        "identity_pending",
    ]:
        require(token in tech, f"technology standard missing required control: {token}")

    for queue in EXPECTED_QUEUES:
        require(queue in agent, f"agent contract missing queue: {queue}")

    for label in ["Phase 2.99", "Phase 3", "Phase 4", "Phase 5", "Phase 6", "Phase 7", "Phase 8", "Phase 9", "Phase 10", "Phase 20"]:
        require(label in phase, f"phase amendment missing inherited phase: {label}")

    print("Ecosystem rollout certification governance: PASS")
    print("- Phase 3 remains blocked")
    print("- Store Credits remain specialist-review HOLD")
    print("- 28 rollout records / 448 certification dimensions preserved")
    print("- 6/6 private delivery canaries preserved")
    print("- legacy KJV/Virality rails retained until replacement proof")


if __name__ == "__main__":
    main()
