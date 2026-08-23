#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_help_center_legal_depot_crosswalk import build  # noqa: E402

PASS_A = ROOT / "data/documentation/sprint-3-pass-a-receipt.v1.json"
GAP = ROOT / "data/documentation/sprint-3-legal-depot-gap-closure.v1.json"
PLAN = ROOT / "data/documentation/help-center-rebuild-sprint-plan.v1.json"

errors: list[str] = []
result = build()
pass_a = json.loads(PASS_A.read_text(encoding="utf-8"))
gap = json.loads(GAP.read_text(encoding="utf-8"))
plan = json.loads(PLAN.read_text(encoding="utf-8"))

canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
digest = hashlib.sha256(canonical).hexdigest()

if result.get("record_count") != 198:
    errors.append("legal_depot_record_count_must_equal_198")
if result.get("summary", {}).get("priority_counts") != {"P0": 131, "P1": 53, "P2": 14}:
    errors.append("priority_count_mismatch")
if result.get("summary", {}).get("disposition_candidate_counts") != {
    "canonical_article": 1,
    "merged_successor": 183,
    "superseded_history": 14,
}:
    errors.append("disposition_candidate_count_mismatch")
if result.get("summary", {}).get("missing_target_route_rows") != 0:
    errors.append("candidate_continuity_routes_missing")
if pass_a.get("section_record_count") != 198 or pass_a.get("missing_target_route_rows") != 0:
    errors.append("pass_a_receipt_mismatch")
if gap.get("record_count") != 198 or gap.get("continuity", {}).get("missing_target_route_rows") != 0:
    errors.append("pass_b_gap_packet_mismatch")

p2_from_crosswalk = {
    row["inventory_id"] for row in result["records"] if row["priority"] == "P2"
}
p2_from_gap = {row["inventory_id"] for row in gap.get("p2_historical_research_or_sunset_queue", [])}
if p2_from_crosswalk != p2_from_gap:
    errors.append("p2_review_queue_not_exact")

for row in result["records"]:
    if row.get("body_status") != "reconstruction_required":
        errors.append(f"historical_body_promoted:{row['inventory_id']}")
    if row.get("terminal_disposition_authorized") is not False:
        errors.append(f"terminal_disposition_self_authorized:{row['inventory_id']}")

sprint_counts = []
for sprint in plan.get("sprints", []):
    sprint_counts.append(int(sprint["title_count"]))
if sprint_counts != [198, 297, 206, 94] or sum(sprint_counts) != 795:
    errors.append("795_rebuild_sprint_math_invalid")
if plan.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
    errors.append("phase_3_gate_widened")
if plan.get("phase_11_20_state") != "reserved_definition_required":
    errors.append("phase_11_20_definition_invented")

if errors:
    print("FAIL_SPRINT_3_LEGAL_DEPOT")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_3_LEGAL_DEPOT")
print("records=198")
print("priority=P0:131,P1:53,P2:14")
print("candidate_disposition=canonical_article:1,merged_successor:183,superseded_history:14")
print("missing_target_route_rows=0")
print(f"candidate_crosswalk_sha256={digest}")
print("historical_body_recovery_claimed=false")
print("terminal_disposition_self_authorized=false")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
print("phase_11_20_state=reserved_definition_required")
