#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave4 as wave4

EXPECTED_P0 = 449
EXPECTED_SELECTED = 5
EXPECTED_CUMULATIVE = 57
EXPECTED_REMAINING = 392
EXPECTED_WAVE_SHA = "d688f197103c89495fed775fe3334c495f1a0769818db00570359f45179709a1"
EXPECTED_VAULT_SHA = "c4e7ea0f1cc1267164e9bdbe502c5d72c0fd54e351c22575436c1ee08c7ba9af"
EXPECTED_ANCHOR = "/chlom/component-framework-reconciliation-contract"


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


result = wave4.build()
policy = result["policy"]
errors: list[str] = []

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != EXPECTED_P0:
    errors.append(f"expected {EXPECTED_P0} P0 candidates, found {result['p0_candidate_count']}")
if result["wave_1_selected_count"] != 16:
    errors.append("Wave 1 count drift")
if result["wave_2_selected_count"] != 19:
    errors.append("Wave 2 count drift")
if result["wave_3_selected_count"] != 17:
    errors.append("Wave 3 count drift")
if result["prior_wave_selected_count"] != 52:
    errors.append("prior-wave cumulative count drift")
if result["prior_wave_overlap_count"] != 0:
    errors.append("Wave 4 may not overlap prior waves")
if result["selected_count"] != EXPECTED_SELECTED:
    errors.append(f"expected exact Wave 4 selection of {EXPECTED_SELECTED}, found {result['selected_count']}")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held must equal 795")
if result["cumulative_machine_qualified_p0_count"] != EXPECTED_CUMULATIVE:
    errors.append("cumulative qualified count mismatch")
if result["p0_outside_waves_1_2_3_4_count"] != EXPECTED_REMAINING:
    errors.append("remaining P0 count mismatch")
if result["wave_sha256"] != EXPECTED_WAVE_SHA:
    errors.append(f"Wave 4 digest drift: {result['wave_sha256']}")
if result["selected_section_counts"] != {"CHLOM": EXPECTED_SELECTED}:
    errors.append("Wave 4 section count drift")
if result["selected_state_counts"] != {"component_framework_reconciliation": EXPECTED_SELECTED}:
    errors.append("Wave 4 state count drift")
if result["selected_anchor_counts"] != {EXPECTED_ANCHOR: EXPECTED_SELECTED}:
    errors.append("Wave 4 anchor count drift")

for row in result["selected_records"]:
    if row["priority"] != "P0":
        errors.append(f"non-P0 selected: {row['inventory_id']}")
    if row["candidate_disposition"] != "merged_successor":
        errors.append(f"non-merged-successor selected: {row['inventory_id']}")
    if row["current_state_candidate"] != "component_framework_reconciliation":
        errors.append(f"state outside Wave 4: {row['inventory_id']}")
    if row["canonical_anchor_route"] != EXPECTED_ANCHOR:
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
    errors.append("Phase 3 entry changed")
if result["guardrails"]["phase_11_20_state"] != "reserved_definition_required":
    errors.append("Phase 11-20 definition state changed")
if result["guardrails"]["canonical_brand"] != "CrownThrive":
    errors.append("canonical brand drift")

pass_a = load_json("data/documentation/sprint-10-pass-a-receipt.v1.json")
gap = load_json("data/documentation/substantive-rebuild-wave-4-gap-closure.v1.json")
pass_b = load_json("data/documentation/sprint-10-pass-b-receipt.v1.json")
package = load_json("frameworks/documentation-reconciliation-continuity/sprint-10-substantive-wave4-package.v1.json")

for label, obj in [("pass_a", pass_a), ("gap", gap), ("pass_b", pass_b), ("package", package)]:
    if obj.get("wave_sha256") != EXPECTED_WAVE_SHA:
        errors.append(f"{label} Wave 4 digest mismatch")

if pass_a.get("wave_4_machine_qualified_candidate_count") != EXPECTED_SELECTED:
    errors.append("Pass A selected count mismatch")
if pass_a.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("Pass A cumulative count mismatch")
if gap.get("machine_qualified_current_successor_count") != EXPECTED_SELECTED:
    errors.append("gap-closure selected count mismatch")
if gap.get("p0_outside_waves_1_2_3_4_count") != EXPECTED_REMAINING:
    errors.append("gap-closure remaining count mismatch")
if pass_b.get("wave_4_machine_qualified") != EXPECTED_SELECTED:
    errors.append("Pass B selected count mismatch")
if pass_b.get("vault_closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Pass B Vault closure digest mismatch")
if package.get("wave_4_selected_count") != EXPECTED_SELECTED:
    errors.append("package selected count mismatch")
if package.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("package cumulative count mismatch")
if package.get("p0_outside_waves_1_2_3_4_count") != EXPECTED_REMAINING:
    errors.append("package remaining count mismatch")
if package.get("vault", {}).get("binding_state") != "vault_bound":
    errors.append("Sprint 10 package is not Vault-bound")
if package.get("vault", {}).get("closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Sprint 10 package Vault closure digest mismatch")
if package.get("authority", {}).get("parent_certification_state") != "pending":
    errors.append("parent certification state must remain pending")
if package.get("authority", {}).get("operationally_enabled") is not False:
    errors.append("package may not be operationally enabled")
if package.get("authority", {}).get("public_activation_allowed") is not False:
    errors.append("package may not allow public activation")

anchor = ROOT / "chlom/component-framework-reconciliation-contract.mdx"
if not anchor.is_file():
    errors.append("component/framework successor contract missing")

public_page = (ROOT / "knowledge/documentation-substantive-rebuild-wave-4.mdx").read_text(encoding="utf-8")
changelog = (ROOT / "changelog/docs-substantive-rebuild-sprint-10-wave-4-2026-08-24.mdx").read_text(encoding="utf-8")
gap_register = (ROOT / "knowledge/documentation-gap-article-rebuild-register.mdx").read_text(encoding="utf-8")
census = (ROOT / "knowledge/documentation-rebuild-coverage-census.mdx").read_text(encoding="utf-8")
for required in ["449", "5", "57", "392", EXPECTED_WAVE_SHA, EXPECTED_ANCHOR, "terminal_disposition_accepted: false"]:
    if required not in public_page:
        errors.append(f"public Wave 4 page missing marker: {required}")
for required in [EXPECTED_WAVE_SHA, "wave_4_machine_qualified: 5", "cumulative_machine_qualified_p0: 57"]:
    if required not in changelog:
        errors.append(f"Sprint 10 changelog missing marker: {required}")
for required in ["Sprint 10 substantive rebuild state", "57", "392", EXPECTED_WAVE_SHA]:
    if required not in gap_register:
        errors.append(f"gap register missing Sprint 10 marker: {required}")
for required in ["Substantive P0 wave progress", "57", "392", "795"]:
    if required not in census:
        errors.append(f"coverage census missing Sprint 10 marker: {required}")

if errors:
    print("FAIL_SPRINT_10_SUBSTANTIVE_WAVE4")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_10_SUBSTANTIVE_WAVE4")
print(f"p0_candidate_count={result['p0_candidate_count']}")
print(f"wave_1_selected_count={result['wave_1_selected_count']}")
print(f"wave_2_selected_count={result['wave_2_selected_count']}")
print(f"wave_3_selected_count={result['wave_3_selected_count']}")
print(f"selected_count={result['selected_count']}")
print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
print(f"p0_outside_waves_1_2_3_4_count={result['p0_outside_waves_1_2_3_4_count']}")
print("selected_section_counts=" + str(result["selected_section_counts"]))
print("selected_state_counts=" + str(result["selected_state_counts"]))
print("selected_anchor_counts=" + str(result["selected_anchor_counts"]))
print("wave_sha256=" + result["wave_sha256"])
print("vault_closure_sha256=" + EXPECTED_VAULT_SHA)
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
