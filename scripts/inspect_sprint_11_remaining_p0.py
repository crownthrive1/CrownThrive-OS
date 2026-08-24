#!/usr/bin/env python3
"""Inspect the P0 estate remaining after substantive Waves 1-4.

This diagnostic does not select, qualify, or activate any records. It exists so
Sprint 11 can move to the next eligible bounded family without weakening a gate
when the proposed interface-surface lane has zero P0 admissions.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave1 as wave1
import build_substantive_rebuild_wave2 as wave2
import build_substantive_rebuild_wave3 as wave3
import build_substantive_rebuild_wave4 as wave4

rows = wave1.aggregate_candidate_rows()
prior = set()
for built in (wave1.build(), wave2.build(), wave3.build(), wave4.build()):
    prior.update(str(row["inventory_id"]) for row in built["selected_records"])

remaining = [row for row in rows if row.get("priority") == "P0" and str(row["inventory_id"]) not in prior]
state_counts = Counter(str(row.get("current_state_candidate", "")) for row in remaining)
section_counts = Counter(str(row.get("legacy_section", "")) for row in remaining)
clean_merged_counts = Counter(
    str(row.get("current_state_candidate", ""))
    for row in remaining
    if row.get("disposition_candidate") == "merged_successor" and not row.get("missing_target_routes")
)

print("PASS_SPRINT_11_REMAINING_P0_INSPECTION")
print(f"prior_wave_selected_count={len(prior)}")
print(f"remaining_p0_count={len(remaining)}")
print("remaining_p0_state_counts=" + json.dumps(dict(sorted(state_counts.items())), sort_keys=True))
print("remaining_p0_clean_merged_state_counts=" + json.dumps(dict(sorted(clean_merged_counts.items())), sort_keys=True))
print("remaining_p0_section_counts=" + json.dumps(dict(sorted(section_counts.items())), sort_keys=True))
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
