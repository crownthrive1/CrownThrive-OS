#!/usr/bin/env python3
"""Validate CrownThrive Phase 2.99 hard-exit ledger v1.3.6. PASS != hard-exit PASS."""
from __future__ import annotations
import argparse, copy, json, re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "developers/manifests/phase-2-99-hard-exit-ledger.v1.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_COUNTS = {
    "holdings_portfolio_rows": 68,
    "holdings_domain_rows": 82,
    "holdings_engine_service_rows": 85,
    "phase_2_7_platform_framework_rows": 74,
}
EXPECTED_68 = {"S100-PORT-004","S100-PORT-016","S100-PORT-018","S100-PORT-019","S100-PORT-023","S100-PORT-063"}
EXPECTED_74 = {
    "S103-PF-012","S103-PF-013","S103-PF-014","S103-PF-017","S103-PF-020",
    "S103-PF-028","S103-PF-036","S103-PF-037","S103-PF-053","S103-PF-055",
    "S103-PF-056","S103-PF-058","S103-PF-059","S103-PF-060","S103-PF-061",
    "S103-PF-063","S103-PF-064","S103-PF-070","S103-PF-073","S103-PF-074",
}
ARTICLE_OPEN = (
    "terminal_disposition_assigned_795","section_and_category_mapping_795","exposure_classified_795",
    "risk_classified_795","owner_or_owner_queue_795","canonical_route_or_explicit_nonpublic_state_795",
    "source_mapping_795","navigation_or_intentionally_unlisted_795","p0_p1_substantive_or_explicit_unresolved_closure",
)
PROTECTED_FLAGS = (
    "contains_trade_secret_candidate_or_controlled","contains_patent_candidate_mechanism",
    "contains_restricted_institutional","contains_credentials_or_fingerprints",
    "contains_private_policy_or_economic_calibration","contains_proprietary_eval_corpora",
    "contains_private_dail_or_evidence",
)

def bad(msg): raise ValueError(msg)
def eq(actual, expected, name):
    if actual != expected: bad(f"{name}: {actual!r} != {expected!r}")
def nonneg(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0: bad(f"{name}: non-negative integer required")
def timestamp(value, name):
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as exc: raise ValueError(f"{name}: invalid timestamp") from exc
    if parsed.tzinfo is None: bad(f"{name}: timezone required")
def sha(value, name):
    if not isinstance(value, str) or not SHA.fullmatch(value): bad(f"{name}: invalid SHA")
def load(path): return json.loads(path.read_text(encoding="utf-8"))
def gates(data):
    rows = data.get("open_hard_gates", [])
    eq(len(rows), 8, "gate count")
    result = {row.get("gate_id"): row for row in rows}
    eq(len(result), 8, "unique gate count")
    return result

def validate(data, check_files=True):
    eq(data.get("manifest_version"), "1.3.6", "manifest version")
    timestamp(data["observed_at"], "observed_at")
    sha(data["observed_main_sha"], "observed main")

    authority = data["authority"]
    expected_authority = {
        "roadmap_decision_id":"CT-ADR-ROADMAP-010",
        "governance_decision_id":"CT-ADR-GOV-011",
        "roadmap_generation":"ten_phase_v1",
        "top_level_phase_count":10,
        "current_phase":2,
        "current_subphase":"2.99",
        "phase_3_entry":"blocked_pending_phase_2_99_hard_exit",
        "mandatory_gatekeeper":"D",
        "d3_authority":"human_reserved",
        "helpers_non_voting":True,
        "research_default_state":"RESEARCH_CANDIDATE",
    }
    for key, value in expected_authority.items(): eq(authority.get(key), value, f"authority.{key}")
    eq(authority["sovereign_voters"], ["A","B","C","D","S"], "sovereign voters")

    roadmap = data["roadmap_v2_pending"]
    eq(roadmap["founder_direction_issue"], 123, "roadmap-v2 issue")
    eq(roadmap["target_top_level_phase_count"], 20, "roadmap-v2 target")
    eq(roadmap["state"], "founder_direction_pending_governed_adr_and_machine_namespace", "roadmap-v2 state")
    eq(roadmap["canonical_roadmap_remains"], "CT-ADR-ROADMAP-010/ten_phase_v1", "roadmap-v2 boundary")
    eq(roadmap["full_documentation_estate_gate_nondeferrable"], True, "full docs gate")

    ip = data["ip_disclosure"]
    eq(ip["governing_issue"], 131, "IP issue")
    eq(set(ip["classification"]), {"PUBLIC_STANDARD","PUBLIC_DOCTRINE"}, "IP classification")
    eq(ip["projection"], "public_specification", "IP projection")
    eq(ip["publication_state"], "PUBLIC_SAFE", "IP publication")
    eq(ip["public_artifact_allowed"], True, "IP public allowed")
    eq(ip["uncertainty_rule"], "HOLD", "IP uncertainty")
    for flag in PROTECTED_FLAGS: eq(ip[flag], False, f"IP.{flag}")
    eq(ip["machine_enforcement_pr"], 133, "IP enforcement PR")
    eq(ip["machine_enforcement_state"], "pending_canonical", "IP enforcement state")

    commercial = data["commercialization"]
    eq(commercial["applicable"], False, "commercial applicable")
    eq(commercial["offer_state"], "not_applicable", "commercial offer")
    for key in ("exact_price_authorized","stripe_product_or_price_authorized","checkout_enabled","certification_status_created","customer_entitlement_created"):
        eq(commercial[key], False, f"commercial.{key}")

    eq(set(data["routing_tags"]), {"CT:RECONCILE","CT:DRIFT-WATCH","CT:HARD-GATE","CT:OPERATIONS","CT:NOT-PASS"}, "routing tags")

    universes = data["source_universes"]
    eq(set(universes), set(EXPECTED_COUNTS), "source universe set")
    for key, count in EXPECTED_COUNTS.items():
        eq(universes[key]["count"], count, f"{key}.count")
        eq(universes[key]["terminal_disposition_coverage"], count, f"{key}.terminal coverage")
        eq(universes[key]["technical_full_current_certification_complete"], False, f"{key}.technical certification")
    eq(universes["holdings_portfolio_rows"]["resolved_or_classified"] + universes["holdings_portfolio_rows"]["terminal_unresolved"], 68, "68 arithmetic")
    eq(set(universes["holdings_portfolio_rows"]["exception_source_rows"]), EXPECTED_68, "68 exceptions")
    eq(universes["phase_2_7_platform_framework_rows"]["resolved_or_classified"] + universes["phase_2_7_platform_framework_rows"]["terminal_unresolved"], 74, "74 arithmetic")
    eq(set(universes["phase_2_7_platform_framework_rows"]["exception_source_rows"]), EXPECTED_74, "74 exceptions")
    eq(universes["holdings_domain_rows"]["authority_issue"], 128, "domain authority")

    gate1 = data["gate_001_terminal_disposition"]
    eq(gate1["authority_issue"], 114, "GATE001 authority")
    eq(gate1["state"], "pass_terminal_macro_disposition_complete", "GATE001 state")
    eq(gate1["source_universes_preserved"], True, "GATE001 source preservation")
    eq(gate1["production_certification_claimed"], False, "GATE001 production claim")
    eq(gate1["gate_scope"], "terminal_macro_disposition_not_all_309_rows_production_verified", "GATE001 scope")
    eq(gate1["gate_001_result"], "pass", "GATE001 result")
    eq(gate1["gate_003_proof_debt_unchanged"], True, "GATE001/GATE003 separation")

    article = data["articleization"]
    eq(article["source_inventory_count"], 795, "article count")
    eq(article["source_inventory_verified"], True, "article source")
    eq(article["complete_machine_manifest_generated_in_repo"], True, "PR91 materialization")
    material = article["canonical_materialization"]
    eq(material["pr"], 91, "materialization PR")
    sha(material["accepted_head"], "materialization head")
    eq(material["merge_sha"], data["observed_main_sha"], "PR91 merge/main")
    eq(material["state"], "merged_canonical_machine_manifest_only", "materialization state")
    for key in ARTICLE_OPEN: eq(article[key], False, f"article.{key}")
    eq(article["s94_body_recovery"], "unresolved", "S94")
    eq(article["hard_exit_certified"], False, "article hard exit")

    docs = data["documentation_estate"]
    eq(docs["full_estate_reconciliation_gate"], "nondeferrable_not_met", "full docs estate")
    eq(docs["founder_direction_issue"], 123, "docs founder issue")
    eq(docs["stale_current_conclusions_may_remain_canonical"], False, "stale-current rule")
    drift = docs.get("projection_drift", [])
    if not drift or not any(item.get("mintlify_projection_confirmed_stale") is True for item in drift): bad("verified Mintlify projection drift missing")

    reconciliation = data["reconciliation"]
    eq(reconciliation["retroactive_phase_2_0_through_2_9_lane"], "active_until_hard_exit", "retroactive lane")
    eq(reconciliation["restricted_source_final_audit"], "pending", "restricted audit")
    eq(reconciliation["continuity_recovery_final_reproducibility_audit"], "pending", "recovery audit")
    eq(reconciliation["approved_deferral_count_snapshot"], 8, "approved deferrals")
    eq(reconciliation["deferred_routing_tag_count_snapshot"], 9, "deferred routing tags")

    tags = reconciliation["reconciliation_tag_snapshot"]
    timestamp(tags["observed_at"], "tag observed_at")
    expected_tags = {"total":267,"pass":149,"open":77,"blocked":15,"closed":17,"deferred":9,"authoritative":267,"scan_required":267,"reconcile_required":267,"non_reconcile_required":0}
    for key, value in expected_tags.items(): eq(tags[key], value, f"tags.{key}")
    eq(tags["pass"]+tags["open"]+tags["blocked"]+tags["closed"]+tags["deferred"], tags["total"], "tag arithmetic")
    eq(tags["formal_reconciliation_debt_basis"], "reconcile_required_only", "formal debt basis")
    eq(tags["registry_growth_alone_is_not_certification_gap"], True, "registry-growth rule")
    eq(tags["explicit_reconcile_required_controls_formal_debt"], True, "explicit debt rule")
    eq(tags["pass_remains_drift_watched"], True, "PASS drift watch")
    eq(tags["deferral_is_not_pass"], True, "deferral semantics")
    eq(tags["unknown_never_becomes_zero_or_pass"], True, "unknown semantics")

    delta = reconciliation["material_tag_delta"]
    expected_delta = {
        "prior_snapshot_total":240,"current_snapshot_total":267,"net_growth":27,
        "prior_reconcile_required_scopes_count":233,"current_reconcile_required_scopes_count":267,
        "prior_non_reconcile_required_scopes_count":7,"current_non_reconcile_required_scopes_count":0,
        "new_reconcile_required_scopes_count":27,"new_non_reconcile_required_scopes_count":0,
        "reclassified_scan_only_to_reconcile_required_count":7,
    }
    for key, value in expected_delta.items(): eq(delta[key], value, f"delta.{key}")
    eq(delta["current_snapshot_total"]-delta["prior_snapshot_total"], delta["net_growth"], "delta total growth")
    eq(delta["prior_reconcile_required_scopes_count"] + delta["new_reconcile_required_scopes_count"] + delta["reclassified_scan_only_to_reconcile_required_count"], delta["current_reconcile_required_scopes_count"], "reconcile debt growth")
    eq(delta["prior_non_reconcile_required_scopes_count"] + delta["new_non_reconcile_required_scopes_count"] - delta["reclassified_scan_only_to_reconcile_required_count"], delta["current_non_reconcile_required_scopes_count"], "scan-only reclassification")
    eq(delta["research_registry_growth_not_counted_as_certification_gap"], True, "research registry growth")

    formal = reconciliation["latest_formal_reconciliation_scan"]
    eq(formal["scanner_id"], "ct.reconciliation.lmno.agent-e", "formal scanner")
    eq(formal["status"], "partial", "formal status")
    eq(formal["tagged_scopes"], 170, "formal tagged")
    eq(formal["reconciled_scopes"], 170, "formal reconciled")
    eq(formal["drift_scopes"], 8, "formal drift")
    eq(formal["unresolved_scopes"], 73, "formal unresolved")
    eq(formal["formal_scan_coverage_gap"], tags["reconcile_required"]-formal["reconciled_scopes"], "formal gap")
    eq(formal["formal_scan_coverage_gap"], 97, "formal gap snapshot")
    eq(formal["formal_scan_coverage_complete"], False, "formal completeness")
    eq(formal["formal_scan_stale_against_current_tags"], True, "formal staleness")
    eq(formal["coverage_denominator"], "current_reconcile_required_scopes", "formal denominator")
    timestamp(formal["completed_at"], "formal completed")

    supplemental = {row["scanner_id"]: row for row in reconciliation["supplemental_reconciliation_scans"]}
    expected_supplemental = {
        "ct.subagent.credential-continuity": (266,23,3,10,"2026-08-20T04:15:47.808993Z"),
        "ct.reconciliation.webhook-delivery.agent-h": (18,18,6,11,"2026-08-20T04:32:42.653331Z"),
    }
    eq(set(supplemental), set(expected_supplemental), "supplemental scanner set")
    for scanner, expected in expected_supplemental.items():
        row=supplemental[scanner]
        eq((row["tagged_scopes"],row["reconciled_scopes"],row["drift_scopes"],row["unresolved_scopes"],row["completed_at"]), expected, f"{scanner}.snapshot")
        eq(row["non_voting"], True, f"{scanner}.non_voting")
        eq(row["formal_lmno_coverage_substitute"], False, f"{scanner}.formal_substitute")

    sources = reconciliation["current_run_source_accounting"]
    eq(set(sources["sources_attempted"]), {"github","supabase","mintlify"}, "current source attempts")
    eq(set(sources["sources_read"]), {"github","supabase","mintlify"}, "current source reads")
    eq(sources["sources_unavailable"], [], "current source unavailable")
    eq(sources["state"], "bounded_current_truth_read_complete", "current source state")

    security = data["repository_security"]
    eq(security["verification_baseline_main_sha"], data["observed_main_sha"], "security baseline")
    eq(security["github_role"], "technical_defense_in_depth_not_sovereign_authority", "GitHub role")
    eq(security["canonicalization_complete"], True, "canonicalization")
    timestamp(security["rls_observed_at"], "RLS observed")
    eq(security["integration_control_base_tables"], 15, "RLS base tables")
    eq(security["rls_enabled_tables"], 15, "RLS coverage")
    eq(security["service_role_all_policy_tables"], 15, "RLS policy coverage")
    eq(security["force_rls_enabled_tables"], 0, "FORCE RLS")
    eq(security["security_advisor_lint_count"], 0, "security advisor")
    eq(security["rls_gate_state"], "passed", "RLS gate")

    collab=data["collab_portal"]
    eq(collab["state"], "fail_closed_deferred_point_of_use", "Collab state")
    eq(collab["canonical_predicate_count"], 7, "Collab predicates")
    eq(collab["predicates_passed_count"], 6, "Collab progress")
    eq(collab["all_seven_certification_predicates_passed"], False, "Collab 7/7")
    eq(collab["webhook_sender_delivery_integrity"], "governed_deferred_not_passed", "Collab webhook")
    eq(collab["technical_webhook_delivery_state"], "unproven", "Collab technical")
    eq(collab["private_fallback_tracking"], "active", "Collab fallback")

    for name, row in data["provider_delivery_deferrals"].items():
        eq(row["technical_state"], "unproven", f"{name}.technical")
        eq(row["technical_pass_claimed"], False, f"{name}.technical_pass")

    gate = gates(data)
    eq(gate["CT-P299-GATE-001"]["state"], "pass", "GATE001")
    eq(gate["CT-P299-GATE-001"]["technical_full_current_certification_complete"], False, "GATE001 technical")
    eq(gate["CT-P299-GATE-002"]["state"], "not_met", "GATE002")
    eq(gate["CT-P299-GATE-003"]["state"], "not_met", "GATE003")
    eq(gate["CT-P299-GATE-003"]["formal_scan_coverage_gap"], 97, "GATE003 gap")
    eq(gate["CT-P299-GATE-004"]["state"], "pass", "GATE004")
    eq(gate["CT-P299-GATE-005"]["state"], "pass", "GATE005")
    eq(gate["CT-P299-GATE-006"]["state"], "deferred_accepted_not_passed", "GATE006")
    eq(gate["CT-P299-GATE-006"]["blocking"], False, "GATE006 blocking")
    eq(gate["CT-P299-GATE-006"]["technical_state"], "unproven", "GATE006 technical")
    eq(gate["CT-P299-GATE-007"]["state"], "not_met", "GATE007")
    eq(gate["CT-P299-GATE-008"]["state"], "not_met", "GATE008")
    eq(gate["CT-P299-GATE-008"]["full_documentation_estate_gate"], "nondeferrable_not_met", "GATE008 docs")
    eq(len([row for row in gate.values() if row.get("blocking") and row.get("state") != "pass"]), 4, "blocking gate count")

    hard=data["hard_exit"]
    eq(hard["state"], "not_met", "hard exit")
    eq(hard["blocking_gate_count"], 4, "hard blocker count")
    eq(hard["deferred_not_passed_gate_count"], 1, "hard deferred count")
    eq(hard["phase_2_complete"], False, "Phase2 complete")
    eq(hard["phase_3_entry_open"], False, "Phase3 open")
    eq(hard["phase_3_entry"], "blocked_pending_phase_2_99_hard_exit", "Phase3 state")
    eq(hard["final_certification_recorded"], False, "final certification")
    eq(hard["gate_008_fail_closed_while_upstream_unresolved"], True, "GATE008 fail closed")

    integration=data["integration"]
    eq(integration["workflow_wiring_state"], "active_governed_ci", "workflow state")
    eq(integration["collision_state"], "foreign_api_navigation_platform_files_removed_to_canonical_main", "collision state")
    eq(integration["rollback"], "revert_bounded_v1_3_6_refresh_and_collision_cleanup", "rollback")

    if check_files:
        for rel in data["evidence_paths"]+[integration["workflow_path"]]:
            if not (ROOT/rel).is_file(): bad(f"missing evidence path: {rel}")
        phase=load(ROOT/"developers/manifests/institutional-phase-namespace.v2.json")
        eq(phase["decision_id"], "CT-ADR-ROADMAP-010", "machine roadmap")
        eq(phase["top_level_phase_count"], 10, "machine phase count")
        eq(phase["phase_3_entry"], "blocked_pending_phase_2_99_hard_exit", "machine Phase3")
        if not (ROOT/material["bundle_path"]).is_file(): bad("canonical 795 bundle missing")

def expect_fail(data, mutate, label):
    candidate=copy.deepcopy(data); mutate(candidate)
    try: validate(candidate, False)
    except ValueError: return
    raise AssertionError(label+" must fail")

def self_test(data):
    validate(data, False)
    expect_fail(data, lambda d:d["authority"].__setitem__("top_level_phase_count",20), "premature roadmap promotion")
    expect_fail(data, lambda d:d["authority"].__setitem__("sovereign_voters",["A","B","C","D","S","L"]), "helper voter promotion")
    expect_fail(data, lambda d:d["gate_001_terminal_disposition"].__setitem__("production_certification_claimed",True), "GATE001 production inflation")
    expect_fail(data, lambda d:d["articleization"].__setitem__("complete_machine_manifest_generated_in_repo",False), "PR91 regression")
    expect_fail(data, lambda d:d["articleization"].__setitem__("terminal_disposition_assigned_795",True), "false GATE002 closure")
    expect_fail(data, lambda d:d["reconciliation"]["reconciliation_tag_snapshot"].__setitem__("total",266), "tag drift hidden")
    expect_fail(data, lambda d:d["reconciliation"]["reconciliation_tag_snapshot"].__setitem__("reconcile_required",266), "formal denominator drift hidden")
    expect_fail(data, lambda d:d["reconciliation"]["latest_formal_reconciliation_scan"].__setitem__("formal_scan_coverage_gap",96), "formal gap falsified")
    expect_fail(data, lambda d:d["reconciliation"]["supplemental_reconciliation_scans"][0].__setitem__("formal_lmno_coverage_substitute",True), "supplemental proof substitution")
    expect_fail(data, lambda d:d["repository_security"].__setitem__("rls_enabled_tables",14), "RLS regression")
    expect_fail(data, lambda d:d["repository_security"].__setitem__("service_role_all_policy_tables",14), "policy coverage regression")
    expect_fail(data, lambda d:d["collab_portal"].__setitem__("all_seven_certification_predicates_passed",True), "false Collab 7/7")
    expect_fail(data, lambda d:d["provider_delivery_deferrals"]["stripe"].__setitem__("technical_pass_claimed",True), "deferral promoted to PASS")
    expect_fail(data, lambda d:d["ip_disclosure"].__setitem__("contains_trade_secret_candidate_or_controlled",True), "protected IP projected public")
    expect_fail(data, lambda d:d["ip_disclosure"].__setitem__("publication_state","HOLD"), "uncertain IP published")
    expect_fail(data, lambda d:d["commercialization"].__setitem__("checkout_enabled",True), "commercial activation")
    expect_fail(data, lambda d:d["open_hard_gates"][7].__setitem__("state","pass"), "premature GATE008")
    expect_fail(data, lambda d:d["hard_exit"].__setitem__("phase_3_entry_open",True), "premature Phase3")

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--self-test", action="store_true"); args=parser.parse_args()
    data=load(LEDGER)
    if args.self_test:
        self_test(data)
        print("Phase 2.99 ledger v1.3.6 self-test PASS: GATE001/004/005 PASS; GATE006 deferred/NOT-PASS; four blocking gates; Phase3 closed.")
        return 0
    validate(data)
    tags=data["reconciliation"]["reconciliation_tag_snapshot"]
    formal=data["reconciliation"]["latest_formal_reconciliation_scan"]
    print("Phase 2.99 ledger v1.3.6 consistency PASS")
    print(f"Current authoritative/reconcile-required scopes={tags['total']}/{tags['reconcile_required']}; formal LMNO reconciled={formal['reconciled_scopes']}; coverage gap={formal['formal_scan_coverage_gap']}")
    print("GATE001/004/005 PASS; GATE006 governed-deferred and technically NOT-PASS; GATE002/003/007/008 NOT-MET; Phase3 blocked.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
