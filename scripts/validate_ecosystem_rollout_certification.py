#!/usr/bin/env python3
"""Fail-closed validator for the public rollout/credit-governance projection."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/ecosystem-rollout-certification.v1.json"
TECH_PATH = ROOT / "technology/ecosystem-rollout-certification-and-credit-commerce.mdx"
AGENT_PATH = ROOT / "automation/ecosystem-rollout-certifier-agent.mdx"
PHASE_PATH = ROOT / "standards/ecosystem-rollout-certification-phase-amendment.mdx"
CHANGELOG_PATH = ROOT / "changelog/phase-2-99-ecosystem-rollout-credit-certification.mdx"

EXPECTED_DIMENSIONS = {
    "stable_identity", "source_evidence", "provider_mapping", "auth_boundary",
    "read_capability", "write_capability", "design_brand_provenance",
    "interaction_accessibility", "rights_chain_of_title",
    "credit_commerce_eligibility", "fulfillment_delivery",
    "refund_dispute_reversal", "observability_dail", "recovery_provider_exit",
    "public_docs_claims", "lifecycle_release",
}

FORBIDDEN_PUBLIC_TOKENS = {
    "credits_per_usd",
    "topup_tiers",
    "100 credits per USD",
    "100 credits per USD $1",
    "1,000-credit",
    "ecosystem_rollout_control",
    "rollout.program.snapshot",
    "rollout.platform.list",
    "rollout.certification.matrix",
    "rollout.commerce.queue",
    "rollout.asset_release.list",
    "rollout.canaries.list",
    "rollout.plan.next",
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
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON manifest: {exc}")

    program = manifest.get("program", {})
    projection = manifest.get("public_projection", {})
    snapshot = manifest.get("runtime_snapshot", {})
    credit = manifest.get("credit_program", {})
    interface = manifest.get("private_interface", {})
    stack = manifest.get("stack", {})

    require(manifest.get("schema_version") == "1.1.0", "unexpected manifest schema version")
    require(manifest.get("stable_id") == "ct.manifest.ecosystem-rollout-certification.v1", "stable manifest ID drift")
    require(program.get("current_phase") == "2.99", "this packet may not advance the current phase")
    require("blocked" in str(program.get("phase_3_entry", "")), "Phase 3 must remain blocked")
    require(program.get("sovereign_vote_created") is False, "rollout agent may not create a sovereign vote")

    require(projection.get("issue_131_disposition") == "hold_pending_exact_artifact_acceptance", "#131 HOLD must remain explicit")
    require(projection.get("economic_calibration") == "restricted_private_runtime", "economic calibration must remain private")
    require(projection.get("economic_tier_projection") == "not_published", "economic tiers must not be public")
    require(projection.get("protected_runtime_topology") == "not_published", "private runtime topology must not be public")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(projection.get("private_contract_digest", ""))) is not None, "private contract digest missing or malformed")

    require(snapshot.get("security_advisor_state") == "hold_current_finding_present", "current security-advisor HOLD must remain visible")
    require(snapshot.get("identity_control_rls_state") == "hold_private_defense_in_depth_review", "identity-control RLS HOLD must remain visible")
    require(set(manifest.get("certification_dimensions", [])) == EXPECTED_DIMENSIONS, "certification-dimension contract drift")

    require(credit.get("program_id") == "ct.credit.store.v1", "credit program ID drift")
    require(credit.get("active") is False, "Store Credits may not be represented live")
    require(credit.get("exact_price_authorized") is False, "exact pricing must remain unauthorized")
    require(credit.get("checkout_enabled") is False, "checkout must remain disabled")
    require(credit.get("economic_calibration") == "restricted_private_runtime", "credit economics must remain private")
    require(credit.get("economic_tier_projection") == "not_published", "credit tiers must remain unpublished")
    require(credit.get("legal_tax_state") == "specialist_review_required_before_live_activation", "legal/tax HOLD must remain explicit")
    require(credit.get("transferable") is False, "Store Credits must not become transferable")
    require(credit.get("cash_redeemable") is False, "Store Credits must not become cash redeemable")
    require(credit.get("interest_bearing") is False, "Store Credits must not become interest bearing")
    require(credit.get("crypto_or_token_authority") is False, "Store Credits must not become token/crypto authority")

    require(stack.get("current_main_reconciliation_required_before_promotion") is True, "current-main reconciliation cannot be waived")
    require(interface.get("central_dispatch") == "registered_disabled_until_certified", "central dispatch must remain disabled")
    require(interface.get("external_provider_mutation") is False, "private interface may not mutate external providers")
    require(interface.get("phase_advancement") is False, "private interface may not advance phases")

    public_text = "\n".join([
        manifest_text,
        read_text(TECH_PATH),
        read_text(AGENT_PATH),
        read_text(PHASE_PATH),
        read_text(CHANGELOG_PATH),
    ])
    for token in FORBIDDEN_PUBLIC_TOKENS:
        require(token not in public_text, f"restricted economic or runtime topology leaked into public projection: {token}")

    tech = read_text(TECH_PATH)
    require("restricted private custody" in tech.lower(), "technology standard must state the private custody boundary")
    require("Phase 3" in tech and "blocked" in tech.lower(), "technology standard must preserve blocked Phase 3")

    agent = read_text(AGENT_PATH)
    require("non-voting" in agent, "agent contract must remain non-voting")
    require("self-certify" in agent, "agent contract must prohibit self-certification")

    phase = read_text(PHASE_PATH)
    for label in ["Phase 2.99", "Phase 3", "Phase 4", "Phase 5", "Phase 6", "Phase 7", "Phase 8", "Phase 9", "Phase 10", "Phase 20"]:
        require(label in phase, f"phase amendment missing inherited phase: {label}")

    print("Ecosystem rollout public projection: PASS")
    print("- exact economics and private topology are absent")
    print("- #131, security, legal/tax and pricing gates remain HOLD")
    print("- Store Credits remain inactive and checkout-disabled")
    print("- Phase 3 remains blocked")


if __name__ == "__main__":
    main()
