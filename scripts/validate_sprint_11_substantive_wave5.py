#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave5 as wave5

result = wave5.build()
policy = result["policy"]
errors: list[str] = []

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != 449:
    errors.append(f"expected 449 P0 candidates, found {result['p0_candidate_count']}")
for key, expected in [
    ("wave_1_selected_count", 16),
    ("wave_2_selected_count", 19),
    ("wave_3_selected_count", 17),
    ("wave_4_selected_count", 5),
]:
    if result[key] != expected:
        errors.append(f"{key} drift: expected {expected}, found {result[key]}")
if result["prior_wave_selected_count"] != 57:
    errors.append("prior-wave cumulative count drift")
if result["prior_wave_overlap_count"] != 0:
    errors.append("Wave 5 may not overlap prior waves")
if not (0 < result["selected_count"] < result["p0_candidate_count"]):
    errors.append("Wave 5 must select a bounded nonzero P0 subset")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held must equal 795")
if result["cumulative_machine_qualified_p0_count"] != 57 + result["selected_count"]:
    errors.append("cumulative qualified count mismatch")
if result["p0_outside_waves_1_2_3_4_5_count"] != 449 - result["cumulative_machine_qualified_p0_count"]:
    errors.append("remaining P0 count mismatch")

for row in result["selected_records"]:
    if row["priority"] != "P0":
        errors.append(f"non-P0 selected: {row['inventory_id']}")
    if row["candidate_disposition"] != "merged_successor":
        errors.append(f"non-merged-successor selected: {row['inventory_id']}")
    if row["current_state_candidate"] != "interface_surface_reconciliation":
        errors.append(f"state outside Wave 5: {row['inventory_id']}")
    if row["canonical_anchor_route"] != "/chlom/interface-surface-reconciliation-contract":
        errors.append(f"wrong anchor: {row['inventory_id']}")
    if not row["continuity_matches"]:
        errors.append(f"missing source continuity: {row['inventory_id']}")
    q = row["canonical_anchor_quality"]
    if q["body_characters"] < policy["minimum_anchor_body_characters"]:
        errors.append(f"anchor body too small: {row['inventory_id']}")
    if q["internal_link_count"] < policy["minimum_anchor_internal_links"]:
        errors.append(f"anchor continuity too weak: {row['inventory_id']}")
    if row["terminal_disposition_accepted"] is not False:
        errors.append(f"terminal disposition self-authorized: {row['inventory_id']}")
    if row["parent_certification_required"] is not True:
        errors.append(f"parent certification missing: {row['inventory_id']}")

for key in [
    "historical_body_recovery_claimed",
    "terminal_disposition_self_authorized",
    "legal_policy_activation_created",
    "investment_or_securities_authority_created",
    "patent_status_authority_created",
    "franchise_or_license_activation_created",
    "rights_or_economic_activation_created",
    "identity_or_credential_activation_created",
    "evidence_or_attestation_authority_created",
    "provider_write_expansion_created",
    "interface_runtime_activation_created",
    "token_exchange_or_settlement_authority_created",
    "production_activation_created",
]:
    if result["guardrails"][key] is not False:
        errors.append(f"guardrail must remain false: {key}")
if result["guardrails"]["parent_certification_required"] is not True:
    errors.append("parent certification must remain required")
if result["guardrails"]["d3_human_reserved"] is not True:
    errors.append("D3 must remain human-reserved")
if result["guardrails"]["phase_3_entry"] != "blocked_pending_phase_2_99_hard_exit":
    errors.append("Phase 3 entry changed")
if result["guardrails"]["phase_11_20_state"] != "reserved_definition_required":
    errors.append("Phase 11-20 definition state changed")
if result["guardrails"]["canonical_brand"] != "CrownThrive":
    errors.append("canonical brand drift")

anchor = ROOT / "chlom/interface-surface-reconciliation-contract.mdx"
if not anchor.is_file():
    errors.append("interface-surface successor contract missing")

if errors:
    print("FAIL_SPRINT_11_SUBSTANTIVE_WAVE5")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_11_SUBSTANTIVE_WAVE5")
print(f"p0_candidate_count={result['p0_candidate_count']}")
print(f"wave_1_selected_count={result['wave_1_selected_count']}")
print(f"wave_2_selected_count={result['wave_2_selected_count']}")
print(f"wave_3_selected_count={result['wave_3_selected_count']}")
print(f"wave_4_selected_count={result['wave_4_selected_count']}")
print(f"selected_count={result['selected_count']}")
print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
print(f"p0_outside_waves_1_2_3_4_5_count={result['p0_outside_waves_1_2_3_4_5_count']}")
print("selected_section_counts=" + str(result["selected_section_counts"]))
print("selected_state_counts=" + str(result["selected_state_counts"]))
print("selected_anchor_counts=" + str(result["selected_anchor_counts"]))
print("wave_sha256=" + result["wave_sha256"])
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
