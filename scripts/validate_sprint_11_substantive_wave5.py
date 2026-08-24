#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave5 as wave5

WAVE_SHA = "0c7359b03dbf17f539adf055a3ad620243a7a3ef604ef864aaf6654f04cff9a8"
VAULT_SHA = "614439bca7459554c8ecc629e40a0bd3bbb3ec803e31d1b04a361e25dae7a368"
PACKAGE_ID = "ct.framework-package.documentation-reconciliation-continuity.sprint-11-substantive-wave5.v1"
VAULT_ALIAS = "ct_framework_documentation_reconciliation_continuity_sprint_11_substantive_wave5_v1"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_yaml_int_marker(text: str, key: str) -> int | None:
    prefix = f"{key}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            value = stripped.split(":", 1)[1].strip()
            try:
                return int(value)
            except ValueError:
                return None
    return None


result = wave5.build()
policy = result["policy"]
errors: list[str] = []

if result["source_universe_count"] != 795:
    errors.append("source universe must remain exactly 795")
if result["p0_candidate_count"] != 449:
    errors.append(f"expected 449 P0 candidates, found {result['p0_candidate_count']}")
for key, expected in [
    ("wave_1_selected_count", 16),
    ("wave_2_selected_count", 19),
    ("wave_3_selected_count", 17),
    ("wave_4_selected_count", 5),
]:
    if result[key] != expected:
        errors.append(f"{key} drift: expected {expected}, found {result[key]}")
if result["prior_wave_selected_count"] != 57:
    errors.append("prior-wave cumulative count drift")
if result["prior_wave_overlap_count"] != 0:
    errors.append("Wave 5 may not overlap prior waves")

if result["primary_interface_p0_candidate_count"] != 5:
    errors.append(f"expected 5 primary interface P0 candidates, found {result['primary_interface_p0_candidate_count']}")
if result["primary_interface_selected_count"] != 0:
    errors.append("primary interface lane must remain zero-admission under unchanged D2 gate")
if result["primary_interface_zero_admission"] is not True:
    errors.append("primary interface zero-admission receipt missing")
if result["primary_interface_gate_unchanged"] is not True:
    errors.append("primary interface gate may not be weakened")
if result["primary_interface_probe"]["gate_unchanged"] is not True:
    errors.append("primary interface probe must record unchanged gate")
if result["primary_interface_probe"]["selected_count"] != 0:
    errors.append("primary interface probe selected a record unexpectedly")

collision = result["classification_collision_inspection"]
if collision["ai_agent_algorithm_p0_candidate_count"] != 35:
    errors.append("AI collision diagnostic count drift")
if collision["broad_ai_family_qualified"] is not False:
    errors.append("AI collision family may not be broadly qualified")

if result["selected_count"] != 1:
    errors.append(f"Wave 5 pivot must select exactly one bounded P0 identity, found {result['selected_count']}")
if result["selected_count"] + result["held_count"] != 795:
    errors.append("selected + held must equal 795")
if result["cumulative_machine_qualified_p0_count"] != 58:
    errors.append("cumulative qualified P0 count must be 58")
if result["p0_outside_waves_1_2_3_4_5_count"] != 391:
    errors.append("remaining P0 count must be 391")
if result["pivot_inventory_id"] != "HC-0076":
    errors.append("pivot inventory identity drift")
if result["pivot_state_family"] != "io_surface_and_machine_contract_reconciliation":
    errors.append("pivot state family drift")
if result["selected_section_counts"] != {"Convergent Ecosystem": 1}:
    errors.append("selected section counts drift")
if result["selected_state_counts"] != {"io_surface_and_machine_contract_reconciliation": 1}:
    errors.append("selected state counts drift")
if result["selected_anchor_counts"] != {"/technology/crownthrive-io-surface-machine-contract-reconciliation": 1}:
    errors.append("selected anchor counts drift")
if result["wave_sha256"] != WAVE_SHA:
    errors.append(f"Wave 5 digest drift: {result['wave_sha256']}")

selected = result["selected_records"]
if len(selected) == 1:
    row = selected[0]
    if row["inventory_id"] != "HC-0076":
        errors.append("unexpected Wave 5 selected identity")
    if row["legacy_section"] != "Convergent Ecosystem":
        errors.append("Wave 5 selected identity must remain in Convergent Ecosystem")
    if row["legacy_subcategory"] != "CrownThrive IO":
        errors.append("Wave 5 selected identity must remain in CrownThrive IO")
    if row["legacy_title"] != "CrownThrive IO BioLink Master Standard":
        errors.append("Wave 5 selected title drift")
    if row["priority"] != "P0":
        errors.append("Wave 5 selected identity must be P0")
    if row["candidate_disposition"] != "merged_successor":
        errors.append("Wave 5 selected identity must be merged_successor")
    if row["current_state_candidate"] != "io_surface_and_machine_contract_reconciliation":
        errors.append("Wave 5 selected state drift")
    if row["canonical_anchor_route"] != "/technology/crownthrive-io-surface-machine-contract-reconciliation":
        errors.append("Wave 5 selected anchor drift")
    if not row["continuity_matches"]:
        errors.append("Wave 5 selected identity lacks source continuity")
    q = row["canonical_anchor_quality"]
    if q["body_characters"] < policy["minimum_anchor_body_characters"]:
        errors.append("Wave 5 pivot anchor body too small")
    if q["internal_link_count"] < policy["minimum_anchor_internal_links"]:
        errors.append("Wave 5 pivot anchor continuity too weak")
    if row["terminal_disposition_accepted"] is not False:
        errors.append("Wave 5 terminal disposition self-authorized")
    if row["parent_certification_required"] is not True:
        errors.append("Wave 5 parent certification missing")

for key in [
    "historical_body_recovery_claimed",
    "terminal_disposition_self_authorized",
    "interface_gate_weakened",
    "ai_collision_family_broadly_qualified",
    "legal_policy_activation_created",
    "investment_or_securities_authority_created",
    "patent_status_authority_created",
    "franchise_or_license_activation_created",
    "rights_or_economic_activation_created",
    "identity_or_credential_activation_created",
    "evidence_or_attestation_authority_created",
    "provider_write_expansion_created",
    "interface_runtime_activation_created",
    "token_exchange_or_settlement_authority_created",
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

pass_a = load_json(ROOT / "data/documentation/sprint-11-pass-a-receipt.v1.json")
gap = load_json(ROOT / "data/documentation/substantive-rebuild-wave-5-gap-closure.v1.json")
pass_b = load_json(ROOT / "data/documentation/sprint-11-pass-b-receipt.v1.json")
package = load_json(ROOT / "frameworks/documentation-reconciliation-continuity/sprint-11-substantive-wave5-package.v1.json")

if pass_a["primary_interface_lane"]["p0_candidate_count"] != 5 or pass_a["primary_interface_lane"]["selected_count"] != 0:
    errors.append("Pass A interface zero-admission receipt drift")
if pass_a["classification_collision_inspection"]["p0_candidate_count"] != 35:
    errors.append("Pass A AI collision count drift")
if pass_a["bounded_pivot_diagnosis"]["selected_pivot_inventory_id"] != "HC-0076":
    errors.append("Pass A pivot identity drift")
if gap["wave_sha256"] != WAVE_SHA:
    errors.append("gap-closure wave digest drift")
if gap["result"]["wave_5_machine_qualified"] != 1 or gap["result"]["cumulative_machine_qualified_p0"] != 58:
    errors.append("gap-closure counts drift")
if pass_b["wave_sha256"] != WAVE_SHA:
    errors.append("Pass B wave digest drift")
if pass_b["vault_closure_sha256"] != VAULT_SHA:
    errors.append("Pass B Vault closure digest drift")
if pass_b["vault_binding_alias"] != VAULT_ALIAS or pass_b["vault_binding_state"] != "bound":
    errors.append("Pass B Vault binding drift")
if pass_b["framework_factory"]["parent_certification_state"] != "pending" or pass_b["framework_factory"]["activation_allowed"] is not False:
    errors.append("Pass B framework authority drift")
if package["package_id"] != PACKAGE_ID:
    errors.append("Sprint 11 package ID drift")
if package["wave_sha256"] != WAVE_SHA or package["vault_closure_sha256"] != VAULT_SHA:
    errors.append("Sprint 11 package digest drift")
if package["vault"]["binding_alias"] != VAULT_ALIAS or package["vault"]["binding_state"] != "bound":
    errors.append("Sprint 11 package Vault binding drift")
if package["qualification"]["terminal_disposition_accepted"] is not False:
    errors.append("Sprint 11 package terminal disposition drift")
if package["authority"]["operationally_enabled"] is not False or package["authority"]["public_activation_allowed"] is not False:
    errors.append("Sprint 11 package activation drift")

for path in [
    ROOT / "chlom/interface-surface-reconciliation-contract.mdx",
    ROOT / "technology/crownthrive-io-surface-machine-contract-reconciliation.mdx",
    ROOT / "knowledge/documentation-substantive-rebuild-wave-5.mdx",
    ROOT / "changelog/docs-substantive-rebuild-sprint-11-wave-5-2026-08-24.mdx",
]:
    if not path.is_file():
        errors.append(f"missing Sprint 11 artifact: {path.relative_to(ROOT)}")

public_register = (ROOT / "knowledge/documentation-substantive-rebuild-wave-5.mdx").read_text(encoding="utf-8")
gap_register = (ROOT / "knowledge/documentation-gap-article-rebuild-register.mdx").read_text(encoding="utf-8")
census = (ROOT / "knowledge/documentation-rebuild-coverage-census.mdx").read_text(encoding="utf-8")
for marker in [
    "primary_interface_p0_candidates: 5",
    "primary_interface_machine_qualified: 0",
    "wave_5_machine_qualified: 1",
    "cumulative_machine_qualified_p0: 58",
    "p0_outside_waves_1_2_3_4_5: 391",
    WAVE_SHA,
]:
    if marker not in public_register:
        errors.append(f"public Wave 5 register missing marker: {marker}")
if "/knowledge/documentation-substantive-rebuild-wave-5" not in gap_register:
    errors.append("gap register does not link Wave 5 public register")

current_qualified = extract_yaml_int_marker(census, "p0_substantive_current_successor_machine_qualified")
current_pending = extract_yaml_int_marker(census, "p0_pending_substantive_or_specialist_resolution")
if current_qualified is None or current_pending is None:
    errors.append("coverage census missing current P0 qualification/pending markers")
else:
    if current_qualified < 58:
        errors.append(f"coverage census regressed below Wave 5 qualified floor: {current_qualified}")
    if current_pending > 391:
        errors.append(f"coverage census regressed above Wave 5 pending ceiling: {current_pending}")
    if current_qualified + current_pending != 449:
        errors.append(
            "coverage census P0 conservation mismatch: "
            f"qualified={current_qualified} pending={current_pending} estate=449"
        )

if errors:
    print("FAIL_SPRINT_11_SUBSTANTIVE_WAVE5")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_11_SUBSTANTIVE_WAVE5")
print(f"p0_candidate_count={result['p0_candidate_count']}")
print(f"prior_wave_selected_count={result['prior_wave_selected_count']}")
print(f"primary_interface_p0_candidate_count={result['primary_interface_p0_candidate_count']}")
print(f"primary_interface_selected_count={result['primary_interface_selected_count']}")
print("primary_interface_gate_unchanged=true")
print("ai_collision_family_broadly_qualified=false")
print(f"selected_count={result['selected_count']}")
print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
print(f"p0_outside_waves_1_2_3_4_5_count={result['p0_outside_waves_1_2_3_4_5_count']}")
print("selected_section_counts=" + str(result["selected_section_counts"]))
print("selected_state_counts=" + str(result["selected_state_counts"]))
print("selected_anchor_counts=" + str(result["selected_anchor_counts"]))
print("wave_sha256=" + result["wave_sha256"])
print("vault_closure_sha256=" + VAULT_SHA)
print("terminal_disposition_accepted=false")
print("parent_certification_required=true")
print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
