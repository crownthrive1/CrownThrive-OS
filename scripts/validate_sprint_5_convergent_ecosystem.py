#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from build_help_center_convergent_ecosystem_crosswalk import build

GAP = ROOT / "data/documentation/sprint-5-convergent-ecosystem-gap-closure.v1.json"
PASS_A = ROOT / "data/documentation/sprint-5-pass-a-receipt.v1.json"
EXPECTED_SHA = "684a61d8c88a13068ff221df83591c236da246e882d1278fc2cc3bf9b4d5719a"
errors = []

result = build()
if result["record_count"] != 206:
    errors.append("record_count_must_be_206")
if result["summary"]["priority_counts"] != {"P0":71,"P1":130,"P2":5}:
    errors.append("priority_counts_mismatch")
if result["summary"]["disposition_candidate_counts"] != {"merged_successor":199,"restricted_record":1,"superseded_history":6}:
    errors.append("candidate_disposition_counts_mismatch")
if result["summary"]["missing_target_route_rows"] != 0:
    errors.append("missing_target_route_rows_nonzero")
if result["summary"]["specific_registry_fallback_rows"] != 0:
    errors.append("specific_registry_fallback_rows_nonzero")
if result["candidate_crosswalk_sha256"] != EXPECTED_SHA:
    errors.append("candidate_crosswalk_sha256_mismatch")
if result["guardrails"].get("historical_body_recovery_claimed") is not False:
    errors.append("historical_body_recovery_must_be_false")
if result["guardrails"].get("terminal_disposition_self_authorized") is not False:
    errors.append("terminal_disposition_self_authorized")
if result["guardrails"].get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
    errors.append("phase_3_gate_widened")
if result["guardrails"].get("phase_11_20_state") != "reserved_definition_required":
    errors.append("phase_11_20_state_invalid")

for path in (GAP, PASS_A):
    if not path.exists():
        errors.append(f"missing:{path.relative_to(ROOT)}")

gap = json.loads(GAP.read_text(encoding="utf-8")) if GAP.exists() else {}
pa = json.loads(PASS_A.read_text(encoding="utf-8")) if PASS_A.exists() else {}
if gap.get("record_count") != 206:
    errors.append("gap_record_count_mismatch")
if gap.get("continuity_result", {}).get("specific_registry_fallback_rows_after") != 0:
    errors.append("gap_closure_fallback_not_zero")
if gap.get("continuity_result", {}).get("invented_dedicated_registry_pages") != 0:
    errors.append("unexpected_invented_registry_page")
if gap.get("rebuild_progress", {}).get("mapped_candidate_titles_after_sprint_5") != 701:
    errors.append("mapped_candidate_titles_must_be_701")
if gap.get("rebuild_progress", {}).get("remaining_titles") != 94:
    errors.append("remaining_titles_must_be_94")
if gap.get("restricted_candidate", {}).get("count") != 1:
    errors.append("restricted_candidate_count_mismatch")
if pa.get("candidate_crosswalk_sha256") != EXPECTED_SHA:
    errors.append("pass_a_sha_mismatch")
if pa.get("source_preservation", {}).get("canonical_current_brand") != "CrownThrive":
    errors.append("canonical_brand_mismatch")

# Verify canonical routes chosen specifically to close the nine Pass A fallback rows.
for route in ("ecosystem/platform-registry.mdx", "platforms/media-federation-institutional-registry.mdx"):
    if not (ROOT / route).is_file():
        errors.append(f"missing_canonical_gap_closure_route:{route}")

if errors:
    print("FAIL_SPRINT_5_CONVERGENT_ECOSYSTEM")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_5_CONVERGENT_ECOSYSTEM")
print("records=206")
print("priority=P0:71,P1:130,P2:5")
print("candidate_disposition=merged_successor:199,restricted_record:1,superseded_history:6")
print("missing_target_route_rows=0")
print("specific_registry_fallback_rows=0")
print(f"candidate_crosswalk_sha256={EXPECTED_SHA}")
print("mapped_candidate_titles=701")
print("remaining_titles=94")
print("historical_body_recovery_claimed=false")
print("terminal_disposition_self_authorized=false")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
print("phase_11_20_state=reserved_definition_required")
