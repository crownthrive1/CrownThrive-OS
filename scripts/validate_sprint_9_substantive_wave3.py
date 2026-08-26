#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave3 as wave3
import substantive_rebuild_current_snapshot as current_snapshot

EXPECTED_P0 = 449
EXPECTED_WAVE1 = 16
EXPECTED_WAVE2 = 19
EXPECTED_WAVE3 = 17
EXPECTED_CUMULATIVE = 52
EXPECTED_REMAINING = 397
EXPECTED_WAVE_SHA = "e7b5c56af1a698d3466259fafc2a8fbceee76220d1befe2cd1be96a6c123fe12"
EXPECTED_VAULT_SHA = "2948eeb882d0d5e4bd3f7db439e27853cb7a8575e1af7512ce303ea29c8a8da6"
EXPECTED_STATE_COUNTS = {
    "evidence_audit_reconciliation": 6,
    "identity_trust_reconciliation": 11,
}
EXPECTED_ANCHOR_COUNTS = {
    "/chlom/evidence-audit-reconciliation-contract": 6,
    "/chlom/identity-trust-reconciliation-contract": 11,
}


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


result = wave3.build()
semantic_snapshot = current_snapshot.load_snapshot()
current_wave_1 = semantic_snapshot["current_waves"]["1"]
current_wave_2 = semantic_snapshot["current_waves"]["2"]
current_wave = semantic_snapshot["current_waves"]["3"]
policy = result["policy"]
errors: list[str] = current_snapshot.validate_current_wave(result, 3, semantic_snapshot)

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != EXPECTED_P0:
    errors.append(f"expected {EXPECTED_P0} P0 candidates, found {result['p0_candidate_count']}")
if result["wave_1_selected_count"] != current_wave_1["selected_count"]:
    errors.append(f"current Wave 1 selected-count drift: {result['wave_1_selected_count']}")
if result["wave_2_selected_count"] != current_wave_2["selected_count"]:
    errors.append(f"current Wave 2 selected-count drift: {result['wave_2_selected_count']}")
if result["prior_wave_selected_count"] != (
    current_wave_1["selected_count"] + current_wave_2["selected_count"]
):
    errors.append("prior-wave selected count drift")
if result["selected_count"] != current_wave["selected_count"]:
    errors.append(
        f"expected current semantic Wave 3 selection of {current_wave['selected_count']}, "
        f"found {result['selected_count']}"
    )
if result["prior_wave_overlap_count"] != 0:
    errors.append("Wave 3 may not overlap prior waves")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held must equal 795")
if result["cumulative_machine_qualified_p0_count"] != current_wave["cumulative_machine_qualified_p0_count"]:
    errors.append("cumulative P0 qualified count drift")
if result["p0_outside_waves_1_2_3_count"] != current_wave["p0_outside_current_waves_count"]:
    errors.append("remaining P0 count drift")
if result["selected_state_counts"] != current_wave["selected_state_counts"]:
    errors.append(f"Wave 3 state-count drift: {result['selected_state_counts']}")
if result["selected_anchor_counts"] != current_wave["selected_anchor_counts"]:
    errors.append(f"Wave 3 anchor-count drift: {result['selected_anchor_counts']}")
if result["selected_section_counts"] != current_wave["selected_section_counts"]:
    errors.append(f"Wave 3 section-count drift: {result['selected_section_counts']}")
if result["wave_sha256"] != current_wave["wave_sha256"]:
    errors.append(f"current semantic Wave 3 digest drift: {result['wave_sha256']}")

allowed_states = set(policy["allowed_state_families"])
anchor_map = dict(policy["state_anchor_routes"])
for row in result["selected_records"]:
    if row["priority"] != "P0":
        errors.append(f"non-P0 row selected: {row['inventory_id']}")
    if row["candidate_disposition"] != "merged_successor":
        errors.append(f"non-merged-successor selected: {row['inventory_id']}")
    if row["current_state_candidate"] not in allowed_states:
        errors.append(f"state outside Wave 3 lane: {row['inventory_id']}")
    if row["canonical_anchor_route"] != anchor_map[row["current_state_candidate"]]:
        errors.append(f"incorrect state anchor: {row['inventory_id']}")
    if not row["continuity_matches"]:
        errors.append(f"missing continuity match: {row['inventory_id']}")
    quality = row["canonical_anchor_quality"]
    if quality["body_characters"] < policy["minimum_anchor_body_characters"]:
        errors.append(f"anchor body too small: {row['inventory_id']}")
    if quality["internal_link_count"] < policy["minimum_anchor_internal_links"]:
        errors.append(f"anchor continuity too weak: {row['inventory_id']}")
    if row["terminal_disposition_accepted"] is not False:
        errors.append(f"terminal disposition self-authorized: {row['inventory_id']}")
    if row["parent_certification_required"] is not True:
        errors.append(f"parent certification missing: {row['inventory_id']}")

for path in [
    ROOT / "chlom/identity-trust-reconciliation-contract.mdx",
    ROOT / "chlom/evidence-audit-reconciliation-contract.mdx",
]:
    if not path.is_file():
        errors.append(f"missing substantive successor: {path.relative_to(ROOT)}")

for key in [
    "historical_body_recovery_claimed",
    "terminal_disposition_self_authorized",
    "legal_policy_activation_created",
    "investment_or_securities_authority_created",
    "patent_status_authority_created",
    "franchise_or_license_activation_created",
    "rights_or_economic_activation_created",
    "token_exchange_or_settlement_authority_created",
    "provider_write_expansion_created",
    "production_activation_created",
]:
    if result["guardrails"][key] is not False:
        errors.append(f"guardrail must remain false: {key}")
if result["guardrails"]["parent_certification_required"] is not True:
    errors.append("parent certification must remain required")
if result["guardrails"]["d3_human_reserved"] is not True:
    errors.append("D3 must remain human-reserved")
if result["guardrails"]["phase_3_entry"] != "blocked_pending_phase_2_99_hard_exit":
    errors.append("Phase 3 entry state changed")
if result["guardrails"]["phase_11_20_state"] != "reserved_definition_required":
    errors.append("Phase 11-20 state changed")
if result["guardrails"]["canonical_brand"] != "CrownThrive":
    errors.append("canonical brand drift")

pass_a = load_json("data/documentation/sprint-9-pass-a-receipt.v1.json")
gap = load_json("data/documentation/substantive-rebuild-wave-3-gap-closure.v1.json")
pass_b = load_json("data/documentation/sprint-9-pass-b-receipt.v1.json")
package = load_json("frameworks/documentation-reconciliation-continuity/sprint-9-substantive-wave3-package.v1.json")

for label, obj in [("pass_a", pass_a), ("gap", gap), ("pass_b", pass_b), ("package", package)]:
    if obj.get("wave_sha256") != EXPECTED_WAVE_SHA:
        errors.append(f"{label} Wave 3 digest mismatch")

if pass_a.get("wave_3_selected_count") != EXPECTED_WAVE3:
    errors.append("Pass A Wave 3 selected count mismatch")
if pass_a.get("selected_state_counts") != EXPECTED_STATE_COUNTS:
    errors.append("Pass A state-count mismatch")
if gap.get("machine_qualified_current_successor_count") != EXPECTED_WAVE3:
    errors.append("gap-closure Wave 3 selected count mismatch")
if gap.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("gap-closure cumulative count mismatch")
if gap.get("p0_outside_waves_1_2_3_count") != EXPECTED_REMAINING:
    errors.append("gap-closure remaining count mismatch")
if pass_b.get("wave_3_machine_qualified") != EXPECTED_WAVE3:
    errors.append("Pass B Wave 3 selected count mismatch")
if pass_b.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("Pass B cumulative count mismatch")
if pass_b.get("p0_outside_waves_1_2_3_count") != EXPECTED_REMAINING:
    errors.append("Pass B remaining count mismatch")
if pass_b.get("selected_state_counts") != EXPECTED_STATE_COUNTS:
    errors.append("Pass B state-count mismatch")
if pass_b.get("selected_anchor_counts") != EXPECTED_ANCHOR_COUNTS:
    errors.append("Pass B anchor-count mismatch")
if pass_b.get("vault_closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Pass B Vault closure digest mismatch")
if package.get("wave_3_selected_count") != EXPECTED_WAVE3:
    errors.append("package Wave 3 selected count mismatch")
if package.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("package cumulative count mismatch")
if package.get("p0_outside_waves_1_2_3_count") != EXPECTED_REMAINING:
    errors.append("package remaining count mismatch")
if package.get("selected_state_counts") != EXPECTED_STATE_COUNTS:
    errors.append("package state-count mismatch")
if package.get("selected_anchor_counts") != EXPECTED_ANCHOR_COUNTS:
    errors.append("package anchor-count mismatch")
if package.get("vault", {}).get("binding_state") != "vault_bound":
    errors.append("Sprint 9 package is not Vault-bound")
if package.get("vault", {}).get("closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Sprint 9 package Vault closure digest mismatch")
if package.get("authority", {}).get("parent_certification_state") != "pending":
    errors.append("parent certification state must remain pending")
if package.get("authority", {}).get("operationally_enabled") is not False:
    errors.append("package may not be operationally enabled")
if package.get("authority", {}).get("public_activation_allowed") is not False:
    errors.append("package may not allow public activation")

public_page = (ROOT / "knowledge/documentation-substantive-rebuild-wave-3.mdx").read_text(encoding="utf-8")
changelog = (ROOT / "changelog/docs-substantive-rebuild-sprint-9-wave-3-2026-08-23.mdx").read_text(encoding="utf-8")
gap_register = (ROOT / "knowledge/documentation-gap-article-rebuild-register.mdx").read_text(encoding="utf-8")

for required in [
    "449",
    "17",
    "52",
    "397",
    EXPECTED_WAVE_SHA,
    "substantive_current_successor_machine_verified_parent_review",
    "/chlom/identity-trust-reconciliation-contract",
    "/chlom/evidence-audit-reconciliation-contract",
]:
    if required not in public_page:
        errors.append(f"public Wave 3 register missing required marker: {required}")
for required in [EXPECTED_WAVE_SHA, EXPECTED_VAULT_SHA, "parent_certification_required: true"]:
    if required not in changelog:
        errors.append(f"Sprint 9 changelog missing required marker: {required}")
for required in [
    "cumulative_machine_qualified_p0: 52",
    "p0_outside_waves_1_2_3: 397",
    "/knowledge/documentation-substantive-rebuild-wave-3",
]:
    if required not in gap_register:
        errors.append(f"gap register missing Sprint 9 marker: {required}")

if errors:
    print("FAIL_SPRINT_9_SUBSTANTIVE_WAVE3")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_9_SUBSTANTIVE_WAVE3")
print(f"p0_candidate_count={result['p0_candidate_count']}")
print(f"wave_1_selected_count={result['wave_1_selected_count']}")
print(f"wave_2_selected_count={result['wave_2_selected_count']}")
print(f"selected_count={result['selected_count']}")
print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
print(f"p0_outside_waves_1_2_3_count={result['p0_outside_waves_1_2_3_count']}")
print("selected_section_counts=" + str(result["selected_section_counts"]))
print("selected_state_counts=" + str(result["selected_state_counts"]))
print("selected_anchor_counts=" + str(result["selected_anchor_counts"]))
print("current_wave_sha256=" + result["wave_sha256"])
print("historical_wave_sha256=" + EXPECTED_WAVE_SHA)
print("vault_closure_sha256=" + EXPECTED_VAULT_SHA)
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
