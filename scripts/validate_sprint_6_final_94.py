#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SHA = "d9ef580d2a49ec80ac11731aa3a0450d2caf7452501e557cabcf0f07e3781e15"
EXPECTED_SECTIONS = {
    "CrownThrive HQ": 46,
    "Cultural Imprint Engine (CIE)": 11,
    "Hybrid Incubator": 5,
    "Investor Relations": 5,
    "MM Suites": 13,
    "Thrive Flywheel": 14,
}

spec = importlib.util.spec_from_file_location("sprint6_builder", ROOT / "scripts/build_help_center_final_94_crosswalk.py")
if spec is None or spec.loader is None:
    raise SystemExit("unable to load Sprint 6 builder")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.build()
s = result["summary"]
errors: list[str] = []

def check(cond: bool, name: str) -> None:
    if not cond:
        errors.append(name)

check(s["records"] == 94, "record_count")
check(s["section_counts"] == EXPECTED_SECTIONS, "section_counts")
check(s["priority_counts"] == {"P0": 41, "P1": 48, "P2": 5}, "priority_counts")
check(s["disposition_candidate_counts"] == {"merged_successor": 77, "restricted_record": 12, "superseded_history": 5}, "disposition_counts")
check(s["missing_target_route_rows"] == 0, "missing_target_route_rows")
check(s["restricted_candidate_rows"] == 12, "restricted_candidate_rows")
check(s["candidate_crosswalk_sha256"] == EXPECTED_SHA, "candidate_crosswalk_sha256")
check(s["mapped_candidate_titles_after_sprint_6"] == 795, "mapped_candidate_titles")
check(s["remaining_titles_after_sprint_6"] == 0, "remaining_titles")
check(s["historical_body_recovery_claimed"] is False, "historical_body_recovery_claimed")
check(s["terminal_disposition_self_authorized"] is False, "terminal_disposition_self_authorized")
check(s["phase_3_entry"] == "blocked_pending_phase_2_99_hard_exit", "phase_3_entry")
check(s["phase_11_20_state"] == "reserved_definition_required", "phase_11_20_state")

for row in result["records"]:
    check(row["body_status"] == "reconstruction_required", f"body_status:{row['inventory_id']}")
    check(row["terminal_disposition_authorized"] is False, f"terminal_authority:{row['inventory_id']}")
    check(not row["missing_target_routes"], f"missing_routes:{row['inventory_id']}")
    for phase in range(11, 21):
        check(row["phase_impact_1_20"][str(phase)] == "reserved_definition_required", f"phase_{phase}:{row['inventory_id']}")

pass_a_path = ROOT / "data/documentation/sprint-6-pass-a-receipt.v1.json"
gap_path = ROOT / "data/documentation/sprint-6-final-94-gap-closure.v1.json"
pass_b_path = ROOT / "data/documentation/sprint-6-pass-b-receipt.v1.json"
for p in (pass_a_path, gap_path, pass_b_path):
    check(p.is_file(), f"missing_receipt:{p.relative_to(ROOT)}")

if pass_a_path.is_file():
    a = json.loads(pass_a_path.read_text(encoding="utf-8"))
    check(a["record_count"] == 94, "pass_a_record_count")
    check(a["candidate_crosswalk_sha256"] == EXPECTED_SHA, "pass_a_sha")
    check(a["missing_target_route_rows"] == 0, "pass_a_routes")
if gap_path.is_file():
    g = json.loads(gap_path.read_text(encoding="utf-8"))
    check(g["gap_closure"]["mapped_candidate_titles_after_sprint_6"] == 795, "gap_mapped")
    check(g["gap_closure"]["remaining_unmapped_titles_after_sprint_6"] == 0, "gap_remaining")
    check(g["gap_closure"]["candidate_mapping_layer"] == "complete", "gap_mapping_state")
    check(g["gap_closure"]["historical_body_reconstruction"] == "incomplete", "gap_body_state")
if pass_b_path.is_file():
    b = json.loads(pass_b_path.read_text(encoding="utf-8"))
    check(b["mapped_candidate_titles"] == 795, "pass_b_mapped")
    check(b["remaining_unmapped_legacy_titles"] == 0, "pass_b_remaining")
    check(b["article_rebuild_state"]["historical_body_reconstruction"] == "incomplete", "pass_b_body_state")
    check(b["article_rebuild_state"]["terminal_disposition_acceptance"] == "incomplete", "pass_b_terminal_state")

census_path = ROOT / "knowledge/documentation-rebuild-coverage-census.mdx"
check(census_path.is_file(), "missing_census")
if census_path.is_file():
    census = census_path.read_text(encoding="utf-8")
    for marker in [
        "## Sprint 6 — final 94-title exact candidate crosswalk",
        "mapped_candidate_titles: 795",
        "remaining_unmapped_legacy_titles: 0",
        "historical_body_reconstruction: incomplete",
        "terminal_disposition_completion: incomplete",
        "blocked_pending_phase_2_99_hard_exit",
    ]:
        check(marker in census, f"census_marker:{marker}")

changelog = ROOT / "changelog/docs-freshness-sprint-6-final-94-2026-08-23.mdx"
check(changelog.is_file(), "missing_sprint6_changelog")
if changelog.is_file():
    text = changelog.read_text(encoding="utf-8")
    check("candidate_mapped_titles: 795" in text, "changelog_mapped")
    check("remaining_unmapped_titles: 0" in text, "changelog_remaining")
    check("/technology/phase-3-readiness-gate" in text, "changelog_phase3_link")
    check("/knowledge/documentation-rebuild-coverage-census" in text, "changelog_census_link")

if errors:
    print("FAIL_SPRINT_6_FINAL_94")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_6_FINAL_94")
print("records=94")
print("priority=P0:41,P1:48,P2:5")
print("candidate_disposition=merged_successor:77,restricted_record:12,superseded_history:5")
print("missing_target_route_rows=0")
print("restricted_candidate_rows=12")
print(f"candidate_crosswalk_sha256={EXPECTED_SHA}")
print("mapped_candidate_titles=795")
print("remaining_titles=0")
print("historical_body_recovery_claimed=false")
print("terminal_disposition_self_authorized=false")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
print("phase_11_20_state=reserved_definition_required")
