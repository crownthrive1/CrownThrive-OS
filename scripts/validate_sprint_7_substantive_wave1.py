#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_substantive_rebuild_wave1 as wave1

result = wave1.build()
policy = result["policy"]
errors: list[str] = []

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != 449:
    errors.append(f"expected 449 P0 candidates across completed map, found {result['p0_candidate_count']}")
if not (0 < result["selected_count"] < result["p0_candidate_count"]):
    errors.append("wave 1 must select a bounded nonzero subset of the P0 estate")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held rows must equal the 795-row source universe")

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
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
