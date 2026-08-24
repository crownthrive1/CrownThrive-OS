#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave3 as wave3

result = wave3.build()
policy = result["policy"]
errors: list[str] = []

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != 449:
    errors.append(f"expected 449 P0 candidates, found {result['p0_candidate_count']}")
if result["wave_1_selected_count"] != 16:
    errors.append(f"expected 16 Wave 1 selected records, found {result['wave_1_selected_count']}")
if result["wave_2_selected_count"] != 19:
    errors.append(f"expected 19 Wave 2 selected records, found {result['wave_2_selected_count']}")
if result["prior_wave_selected_count"] != 35:
    errors.append(f"expected 35 prior-wave selected records, found {result['prior_wave_selected_count']}")
if result["prior_wave_overlap_count"] != 0:
    errors.append("Wave 3 may not overlap prior waves")
if result["selected_count"] <= 0:
    errors.append("Wave 3 must select a nonzero bounded cohort")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held must equal 795")
if result["cumulative_machine_qualified_p0_count"] != 35 + result["selected_count"]:
    errors.append("cumulative P0 qualified count mismatch")
if result["p0_outside_waves_1_2_3_count"] != 449 - result["cumulative_machine_qualified_p0_count"]:
    errors.append("remaining P0 count mismatch")

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
print("wave_sha256=" + result["wave_sha256"])
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
