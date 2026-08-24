#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_substantive_rebuild_wave1 as wave1

EXPECTED_SELECTED = 16
EXPECTED_P0 = 449
EXPECTED_WAVE_SHA = "2f43fa90fccf295a1695d9a5e63342d5c386c84ee3b4b5cdfb4661cff0f5d998"
EXPECTED_VAULT_SHA = "d03bc3e8e0052fb2091dac16703bbef233f9a8df4fec57df45f4c5f80d2ec7d9"


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


result = wave1.build()
policy = result["policy"]
errors: list[str] = []

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != EXPECTED_P0:
    errors.append(f"expected {EXPECTED_P0} P0 candidates across completed map, found {result['p0_candidate_count']}")
if result["selected_count"] != EXPECTED_SELECTED:
    errors.append(f"expected stable Wave 1 selection of {EXPECTED_SELECTED}, found {result['selected_count']}")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held rows must equal the 795-row source universe")
if result["wave_sha256"] != EXPECTED_WAVE_SHA:
    errors.append(f"Wave 1 digest drift: {result['wave_sha256']}")

for row in result["selected_records"]:
    if row["priority"] != "P0":
        errors.append(f"non-P0 row selected: {row['inventory_id']}")
    if row["candidate_disposition"] != "merged_successor":
        errors.append(f"non-merged-successor row selected: {row['inventory_id']}")
    if row["terminal_disposition_accepted"] is not False:
        errors.append(f"terminal disposition self-authorized: {row['inventory_id']}")
    if row["parent_certification_required"] is not True:
        errors.append(f"parent certification missing: {row['inventory_id']}")
    q = row["canonical_anchor_quality"]
    if q["body_characters"] < policy["minimum_anchor_body_characters"]:
        errors.append(f"anchor body too small: {row['inventory_id']}")
    if q["internal_link_count"] < policy["minimum_anchor_internal_links"]:
        errors.append(f"anchor continuity too weak: {row['inventory_id']}")

if result["guardrails"]["historical_body_recovery_claimed"] is not False:
    errors.append("historical body recovery may not be claimed")
if result["guardrails"]["terminal_disposition_self_authorized"] is not False:
    errors.append("terminal disposition may not self-authorize")
if result["guardrails"]["parent_certification_required"] is not True:
    errors.append("parent certification must remain required")
if result["guardrails"]["phase_3_entry"] != "blocked_pending_phase_2_99_hard_exit":
    errors.append("Phase 3 entry state changed")
if result["guardrails"]["phase_11_20_state"] != "reserved_definition_required":
    errors.append("Phase 11-20 state changed")
if result["guardrails"]["canonical_brand"] != "CrownThrive":
    errors.append("canonical brand drift")

pass_a = load_json("data/documentation/sprint-7-pass-a-receipt.v1.json")
gap = load_json("data/documentation/substantive-rebuild-wave-1-gap-closure.v1.json")
pass_b = load_json("data/documentation/sprint-7-pass-b-receipt.v1.json")
package = load_json("frameworks/documentation-reconciliation-continuity/sprint-7-substantive-wave1-package.v1.json")

for label, obj in [("pass_a", pass_a), ("gap", gap), ("pass_b", pass_b), ("package", package)]:
    if obj.get("wave_sha256") != EXPECTED_WAVE_SHA:
        errors.append(f"{label} Wave 1 digest mismatch")

if pass_a.get("selected_count") != EXPECTED_SELECTED or pass_a.get("p0_candidate_count") != EXPECTED_P0:
    errors.append("Pass A receipt count mismatch")
if gap.get("machine_qualified_current_successor_count") != EXPECTED_SELECTED:
    errors.append("gap-closure selected count mismatch")
if pass_b.get("machine_qualified_substantive_current_successors_wave1") != EXPECTED_SELECTED:
    errors.append("Pass B selected count mismatch")
if pass_b.get("vault_closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Pass B Vault closure digest mismatch")
if package.get("vault", {}).get("binding_state") != "vault_bound":
    errors.append("Sprint 7 package is not Vault-bound")
if package.get("vault", {}).get("closure_sha256") != EXPECTED_VAULT_SHA:
    errors.append("Sprint 7 package Vault closure digest mismatch")
if package.get("authority", {}).get("parent_certification_state") != "pending":
    errors.append("parent certification state must remain pending")
if package.get("authority", {}).get("operationally_enabled") is not False:
    errors.append("package may not be operationally enabled")
if package.get("authority", {}).get("public_activation_allowed") is not False:
    errors.append("package may not allow public activation")

public_page = (ROOT / "knowledge/documentation-substantive-rebuild-wave-1.mdx").read_text(encoding="utf-8")
changelog = (ROOT / "changelog/docs-substantive-rebuild-sprint-7-wave-1-2026-08-23.mdx").read_text(encoding="utf-8")
for required in [
    "449",
    "16",
    "433",
    EXPECTED_WAVE_SHA,
    "substantive_current_successor_machine_verified_parent_review",
    "/technology/security-privacy-continuity",
    "/technology/phase-3-readiness-gate",
]:
    if required not in public_page:
        errors.append(f"public Wave 1 register missing required marker: {required}")
if EXPECTED_WAVE_SHA not in changelog or "parent_certification_required: true" not in changelog:
    errors.append("Sprint 7 changelog is missing deterministic receipt markers")

if errors:
    print("FAIL_SPRINT_7_SUBSTANTIVE_WAVE1")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_7_SUBSTANTIVE_WAVE1")
print(f"p0_candidate_count={result['p0_candidate_count']}")
print(f"selected_count={result['selected_count']}")
print(f"held_count={result['held_count']}")
print("selected_section_counts=" + str(result["selected_section_counts"]))
print("selected_anchor_counts=" + str(result["selected_anchor_counts"]))
print("wave_sha256=" + result["wave_sha256"])
print("vault_closure_sha256=" + EXPECTED_VAULT_SHA)
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
