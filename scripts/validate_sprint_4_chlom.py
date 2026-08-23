#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_help_center_chlom_crosswalk import build

ROOT = Path(__file__).resolve().parents[1]
GAP = ROOT / "data/documentation/sprint-4-chlom-gap-closure.v1.json"
SCOPE = ROOT / "data/documentation/sprint-4-chlom-scope.v1.json"
PASS_A = ROOT / "data/documentation/sprint-4-pass-a-receipt.v1.json"

errors: list[str] = []
result = build()
gap = json.loads(GAP.read_text(encoding="utf-8"))
scope = json.loads(SCOPE.read_text(encoding="utf-8"))
pass_a = json.loads(PASS_A.read_text(encoding="utf-8"))

expected_priorities = {"P0": 206, "P1": 85, "P2": 6}
expected_dispositions = {"merged_successor": 276, "superseded_history": 21}
expected_states = {
    "ai_agent_algorithm_reconciliation": 56,
    "authority_governance_reconciliation": 20,
    "component_framework_reconciliation": 64,
    "economic_lex_reconciliation": 34,
    "evidence_audit_reconciliation": 6,
    "historical_research_reconciliation": 6,
    "identity_trust_reconciliation": 11,
    "interface_surface_reconciliation": 6,
    "machine_contract_reconciliation": 19,
    "needs_current_reconciliation": 46,
    "rights_license_reconciliation": 29,
}

if result.get("record_count") != 297:
    errors.append("record_count_must_be_297")
if result.get("source_forensic_universe") != 795:
    errors.append("source_universe_must_be_795")
if result["summary"].get("priority_counts") != expected_priorities:
    errors.append("priority_counts_changed_without_versioned_review")
if result["summary"].get("disposition_candidate_counts") != expected_dispositions:
    errors.append("candidate_dispositions_changed_without_versioned_review")
if result["summary"].get("current_state_candidate_counts") != expected_states:
    errors.append("state_counts_changed_without_versioned_review")
if result["summary"].get("missing_target_route_rows") != 0:
    errors.append("candidate_routes_must_all_resolve")
if result["guardrails"].get("historical_body_recovery_claimed") is not False:
    errors.append("historical_body_recovery_claim_prohibited")
if result["guardrails"].get("terminal_disposition_self_authorized") is not False:
    errors.append("terminal_disposition_self_authorization_prohibited")
if result["guardrails"].get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
    errors.append("phase_3_gate_widened")
if result["guardrails"].get("phase_11_20_state") != "reserved_definition_required":
    errors.append("phase_11_20_definition_state_changed")

if scope.get("forensic_title_count") != 297 or scope.get("section") != "CHLOM":
    errors.append("scope_contract_invalid")
if pass_a.get("records") != 297 or pass_a.get("missing_target_route_rows") != 0:
    errors.append("pass_a_receipt_invalid")

families = gap.get("continuity_families", [])
if sum(int(row.get("count", 0)) for row in families) != 297:
    errors.append("gap_family_counts_must_sum_to_297")
if gap.get("remaining_after_sprint_4", {}).get("mapped_candidate_titles") != 495:
    errors.append("mapped_candidate_total_must_be_495")
if gap.get("remaining_after_sprint_4", {}).get("remaining_titles") != 300:
    errors.append("remaining_title_total_must_be_300")

for route in gap.get("wave_1_source_inheritance", []):
    normalized = route.strip("/")
    if not (ROOT / f"{normalized}.mdx").is_file():
        errors.append(f"missing_wave1_source_route:{route}")

canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
digest = hashlib.sha256(canonical).hexdigest()

if errors:
    print("FAIL_SPRINT_4_CHLOM")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_4_CHLOM")
print("records=297")
print("priority=P0:206,P1:85,P2:6")
print("candidate_disposition=merged_successor:276,superseded_history:21")
print("missing_target_route_rows=0")
print(f"candidate_crosswalk_sha256={digest}")
print("mapped_candidate_titles=495")
print("remaining_titles=300")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
print("phase_11_20_state=reserved_definition_required")
