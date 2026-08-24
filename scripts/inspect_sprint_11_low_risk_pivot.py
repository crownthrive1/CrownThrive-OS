#!/usr/bin/env python3
"""Inspect low-count remaining P0 families after Waves 1-4 for a safe Sprint 11 pivot.

Diagnostic only. This script cannot qualify, activate, or terminally dispose records.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave1 as wave1
import build_substantive_rebuild_wave2 as wave2
import build_substantive_rebuild_wave3 as wave3
import build_substantive_rebuild_wave4 as wave4

TARGET_STATES = {
    "io_surface_and_machine_contract_reconciliation",
    "long_tail_current_state_reconciliation",
    "current_successor_exists",
    "current_governance_reconciliation",
    "cie_framework_reconciliation",
}

rows = wave1.aggregate_candidate_rows()
prior = set()
for built in (wave1.build(), wave2.build(), wave3.build(), wave4.build()):
    prior.update(str(row["inventory_id"]) for row in built["selected_records"])

candidates = [
    row for row in rows
    if row.get("priority") == "P0"
    and str(row["inventory_id"]) not in prior
    and row.get("current_state_candidate") in TARGET_STATES
]

print("PASS_SPRINT_11_LOW_RISK_PIVOT_INSPECTION")
print(f"candidate_count={len(candidates)}")
for row in candidates:
    payload = {
        "inventory_id": row["inventory_id"],
        "legacy_section": row.get("legacy_section"),
        "legacy_subcategory": row.get("legacy_subcategory"),
        "legacy_title": row.get("legacy_title"),
        "priority": row.get("priority"),
        "current_state_candidate": row.get("current_state_candidate"),
        "candidate_disposition": row.get("disposition_candidate"),
        "flags": row.get("flags", []),
        "target_routes": row.get("target_routes", []),
        "missing_target_routes": row.get("missing_target_routes", []),
    }
    print("PIVOT_CANDIDATE=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
