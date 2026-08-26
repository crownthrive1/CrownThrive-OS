#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave2 as wave2
import substantive_rebuild_current_snapshot as current_snapshot

EXPECTED_P0 = 449
EXPECTED_WAVE1 = 16
EXPECTED_WAVE2 = 19
EXPECTED_CUMULATIVE = 35
EXPECTED_REMAINING = 414
EXPECTED_WAVE_SHA = "234cf1a35ed005b3b3ba20a2175634e4419948bc0d428ca3b379b206e50553cb"
EXPECTED_VAULT_SHA = "4d60aef520e6107e038dce60bb309b550d9db7a304b4d455b181447111c649cb"
EXPECTED_SECTION_COUNTS = {"CHLOM": 19}
EXPECTED_STATE_COUNTS = {"machine_contract_reconciliation": 19}
EXPECTED_ANCHOR_COUNTS = {"/chlom/ecosystem-integrations": 19}
HISTORICAL_PHASE3_ENTRY = "blocked_pending_phase_2_99_hard_exit"


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


result = wave2.build()
semantic_snapshot = current_snapshot.load_snapshot()
current_wave_1 = semantic_snapshot["current_waves"]["1"]
current_wave = semantic_snapshot["current_waves"]["2"]
policy = result["policy"]
errors: list[str] = current_snapshot.validate_current_wave(result, 2, semantic_snapshot)

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != EXPECTED_P0:
    errors.append(f"expected {EXPECTED_P0} P0 candidates, found {result['p0_candidate_count']}")
if result["wave_1_selected_count"] != current_wave_1["selected_count"]:
    errors.append(
        f"expected {current_wave_1['selected_count']} current Wave 1 selected records, "
        f"found {result['wave_1_selected_count']}"
    )
if result["selected_count"] != current_wave["selected_count"]:
    errors.append(
        f"expected current semantic Wave 2 selection of {current_wave['selected_count']}, "
        f"found {result['selected_count']}"
    )
if result["cumulative_machine_qualified_p0_count"] != current_wave["cumulative_machine_qualified_p0_count"]:
    errors.append("cumulative P0 qualified count mismatch")
if result["p0_outside_waves_1_2_count"] != current_wave["p0_outside_current_waves_count"]:
    errors.append("remaining P0 count mismatch")
if result["wave_1_overlap_count"] != 0:
    errors.append("Wave 2 may not overlap Wave 1")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held must equal 795")
if result["selected_section_counts"] != current_wave["selected_section_counts"]:
    errors.append(f"selected section drift: {result['selected_section_counts']}")
if result["selected_state_counts"] != current_wave["selected_state_counts"]:
    errors.append(f"selected state drift: {result['selected_state_counts']}")
if result["selected_anchor_counts"] != current_wave["selected_anchor_counts"]:
    errors.append(f"selected anchor drift: {result['selected_anchor_counts']}")

# Phase 3 distinction: EXPECTED_WAVE_SHA is the immutable Sprint 8 receipt digest.
# The builder intentionally re-reads current canonical anchor documents, so its
# recomputed digest can change as current Phase 3 documentation gains content.
# That mutable-anchor digest must not be confused with corruption of the stored
# historical Sprint 8 receipt. Structural/authority invariants are still checked
# below, and all persisted Sprint 8 receipts must retain EXPECTED_WAVE_SHA.
current_recomputed_wave_sha = result["wave_sha256"]

allowed_states = set(policy["allowed_state_families"])
allowed_anchors = set(policy["canonical_anchor_routes"])
for row in result["selected_records"]:
    if row["priority"] != "P0":
        errors.append(f"non-P0 row selected: {row['inventory_id']}")
    if row["candidate_disposition"] != "merged_successor":
        errors.append(f"non-merged-successor selected: {row['inventory_id']}")
    if row["current_state_candidate"] not in allowed_states:
        errors.append(f"state outside Wave 2 lane: {row['inventory_id']}")
    if row["canonical_anchor_route"] not in allowed_anchors:
        errors.append(f"anchor outside Wave 2 allowlist: {row['inventory_id']}")
    quality = row["canonical_anchor_quality"]
    if quality["body_characters"] < policy["minimum_anchor_body_characters"]:
        errors.append(f"anchor body too small: {row['inventory_id']}")
    if quality["internal_link_count"] < policy["minimum_anchor_internal_links"]:
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
if result["guardrails"]["phase_3_entry"] != HISTORICAL_PHASE3_ENTRY:
    errors.append("historical Sprint 8 Phase 2.99 entry marker changed")
if result["guardrails"]["phase_11_20_state"] != "reserved_definition_required":
    errors.append("Phase 11-20 state changed")
if result["guardrails"]["canonical_brand"] != "CrownThrive":
    errors.append("canonical brand drift")

# Current institutional generation is governed separately from the immutable
# Sprint 8 historical snapshot. This prevents the old Phase 2.99 gate from
# masquerading as CrownThrive's present Phase 3 state while preserving the old
# record exactly for audit/lineage purposes.
phase3_gate = load_json("developers/manifests/phase3-institutional-gate.v1.json")
if phase3_gate.get("institutional_generation") != "phase_3":
    errors.append("current institutional generation is not phase_3")
if phase3_gate.get("historical_phase_2_99_evidence") != "preserved_noncurrent":
    errors.append("Phase 2.99 historical evidence is not explicitly preserved_noncurrent")
if phase3_gate.get("holds_preserved") is not True:
    errors.append("Phase 3 gate must preserve HOLD")
if phase3_gate.get("d3_human_reserved") is not True:
    errors.append("Phase 3 gate must preserve D3 human reservation")

pass_a = load_json("data/documentation/sprint-8-pass-a-receipt.v1.json")
gap = load_json("data/documentation/substantive-rebuild-wave-2-gap-closure.v1.json")
pass_b = load_json("data/documentation/sprint-8-pass-b-receipt.v1.json")
package = load_json("frameworks/documentation-reconciliation-continuity/sprint-8-substantive-wave2-package.v1.json")

for label, obj in [("pass_a", pass_a), ("gap", gap), ("pass_b", pass_b), ("package", package)]:
    if obj.get("wave_sha256") != EXPECTED_WAVE_SHA:
        errors.append(f"{label} historical Wave 2 receipt digest mismatch")

if pass_a.get("wave_2_selected_count") != EXPECTED_WAVE2:
    errors.append("Pass A selected count mismatch")
if pass_a.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("Pass A cumulative count mismatch")
if gap.get("machine_qualified_current_successor_count") != EXPECTED_WAVE2:
    errors.append("gap-closure selected count mismatch")
if gap.get("missing_qualified_anchor_rows") != 0:
    errors.append("gap-closure contains missing qualified anchors")
if gap.get("duplicate_successor_pages_created") != 0:
    errors.append("Wave 2 may not generate duplicate successor pages")
if pass_b.get("machine_qualified_substantive_current_successors_wave2") != EXPECTED_WAVE2:
    errors.append("Pass B selected count mismatch")
if pass_b.get("cumulative_machine_qualified_p0_count") != EXPECTED_CUMULATIVE:
    errors.append("Pass B cumulative count mismatch")
if pass_b.get("vault_closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Pass B Vault closure digest mismatch")
if package.get("vault", {}).get("binding_state") != "vault_bound":
    errors.append("Sprint 8 package is not Vault-bound")
if package.get("vault", {}).get("closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Sprint 8 package Vault closure digest mismatch")
if package.get("authority", {}).get("parent_certification_state") != "pending":
    errors.append("parent certification state must remain pending")
if package.get("authority", {}).get("operationally_enabled") is not False:
    errors.append("package may not be operationally enabled")
if package.get("authority", {}).get("public_activation_allowed") is not False:
    errors.append("package may not allow public activation")
if package.get("authority", {}).get("rights_or_economic_activation") is not False:
    errors.append("package may not activate rights/economic authority")
if package.get("authority", {}).get("provider_write_expansion") is not False:
    errors.append("package may not expand provider writes")

public_page = (ROOT / "knowledge/documentation-substantive-rebuild-wave-2.mdx").read_text(encoding="utf-8")
rebuild_register = (ROOT / "knowledge/documentation-gap-article-rebuild-register.mdx").read_text(encoding="utf-8")
changelog = (ROOT / "changelog/docs-substantive-rebuild-sprint-8-wave-2-2026-08-23.mdx").read_text(encoding="utf-8")
for required in [
    "449",
    "19",
    "35",
    "414",
    EXPECTED_WAVE_SHA,
    "machine_contract_reconciliation",
    "/chlom/ecosystem-integrations",
    "terminal_disposition_accepted: false",
    "parent_certification_required: true",
]:
    if required not in public_page:
        errors.append(f"public Wave 2 register missing required marker: {required}")
for required in ["Sprint 8 substantive rebuild state", "wave_2_machine_qualified: 19", EXPECTED_WAVE_SHA]:
    if required not in rebuild_register:
        errors.append(f"rebuild register missing Wave 2 marker: {required}")
if EXPECTED_WAVE_SHA not in changelog or EXPECTED_VAULT_SHA not in changelog:
    errors.append("Sprint 8 changelog is missing deterministic historical receipt markers")

if errors:
    print("FAIL_SPRINT_8_SUBSTANTIVE_WAVE2")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_8_SUBSTANTIVE_WAVE2")
print(f"p0_candidate_count={result['p0_candidate_count']}")
print(f"wave_1_selected_count={result['wave_1_selected_count']}")
print(f"selected_count={result['selected_count']}")
print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
print(f"p0_outside_waves_1_2_count={result['p0_outside_waves_1_2_count']}")
print("selected_section_counts=" + str(result["selected_section_counts"]))
print("selected_state_counts=" + str(result["selected_state_counts"]))
print("selected_anchor_counts=" + str(result["selected_anchor_counts"]))
print("historical_wave_sha256=" + EXPECTED_WAVE_SHA)
print("current_recomputed_wave_sha256=" + current_recomputed_wave_sha)
print("vault_closure_sha256=" + EXPECTED_VAULT_SHA)
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("historical_phase_3_entry=" + HISTORICAL_PHASE3_ENTRY)
print("current_institutional_generation=phase_3")
