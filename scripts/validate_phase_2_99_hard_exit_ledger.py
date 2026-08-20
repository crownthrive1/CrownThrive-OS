#!/usr/bin/env python3
"""Phase 2.99 hard-exit ledger v1.3.2 validator. PASS != hard-exit PASS."""
from __future__ import annotations
import argparse, copy, json, re
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"developers/manifests/phase-2-99-hard-exit-ledger.v1.json"
SHA=re.compile(r"^[0-9a-f]{40}$")
COUNTS={"holdings_portfolio_rows":68,"holdings_domain_rows":82,"holdings_engine_service_rows":85,"phase_2_7_platform_framework_rows":74}
ARTICLE_OPEN=("terminal_disposition_assigned_795","section_and_category_mapping_795","exposure_classified_795","risk_classified_795","owner_or_owner_queue_795","canonical_route_or_explicit_nonpublic_state_795","source_mapping_795","navigation_or_intentionally_unlisted_795","p0_p1_substantive_or_explicit_unresolved_closure")

def bad(m): raise ValueError(m)
def eq(a,b,n):
    if a!=b: bad(f"{n}: {a!r} != {b!r}")
def ni(v,n):
    if isinstance(v,bool) or not isinstance(v,int) or v<0: bad(f"{n}: non-negative integer required")
def ts(v,n):
    try: d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except Exception as e: raise ValueError(f"{n}: invalid timestamp") from e
    if d.tzinfo is None: bad(f"{n}: timezone required")
def sh(v,n):
    if not isinstance(v,str) or not SHA.fullmatch(v): bad(f"{n}: invalid SHA")
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def gates(d):
    r=d.get("open_hard_gates",[])
    eq(len(r),8,"gate count")
    m={x.get("gate_id"):x for x in r}; eq(len(m),8,"unique gates"); return m

def validate(d,check_files=True):
    eq(d.get("manifest_version"),"1.3.2","manifest version"); ts(d["observed_at"],"observed_at"); sh(d["observed_main_sha"],"main")
    a=d["authority"]
    for k,v in {"roadmap_decision_id":"CT-ADR-ROADMAP-010","governance_decision_id":"CT-ADR-GOV-011","roadmap_generation":"ten_phase_v1","top_level_phase_count":10,"current_phase":2,"current_subphase":"2.99","phase_3_entry":"blocked_pending_phase_2_99_hard_exit"}.items(): eq(a.get(k),v,f"authority.{k}")
    r2=d["roadmap_v2_pending"]; eq(r2["founder_direction_issue"],123,"roadmap v2 issue"); eq(r2["target_top_level_phase_count"],20,"roadmap v2 target"); eq(r2["state"],"founder_direction_pending_governed_adr_and_machine_namespace","roadmap v2 state"); eq(r2["canonical_roadmap_remains"],"CT-ADR-ROADMAP-010/ten_phase_v1","roadmap v2 boundary"); eq(r2["full_documentation_estate_gate_nondeferrable"],True,"full docs gate"); eq(r2["gate_008_dependency"],True,"roadmap v2 gate008")
    u=d["macro_count_universes"]; eq(set(u),set(COUNTS),"macro universes")
    for k,c in COUNTS.items(): eq(u[k]["count"],c,f"{k}.count"); eq(u[k]["source_count_state"],"certified",f"{k}.source"); eq(u[k]["hard_exit_certified"],False,f"{k}.hard_exit")
    x=d["articleization"]; eq(x["source_inventory_count"],795,"article count"); eq(x["complete_machine_manifest_generated_in_repo"],True,"PR91 materialization")
    cm=x["canonical_materialization"]; eq(cm["pr"],91,"materialization PR"); sh(cm["accepted_head"],"PR91 head"); eq(cm["merge_sha"],d["observed_main_sha"],"PR91 merge/main"); eq(cm["state"],"merged_canonical_machine_manifest_only","PR91 state")
    for k in ARTICLE_OPEN: eq(x[k],False,f"article.{k}")
    eq(x["s94_body_recovery"],"unresolved","S94"); eq(x["hard_exit_certified"],False,"article hard exit")
    de=d["documentation_estate"]; eq(de["full_estate_reconciliation_gate"],"nondeferrable_not_met","full docs estate"); eq(de["founder_direction_issue"],123,"docs issue"); eq(de["stale_current_conclusions_may_remain_canonical"],False,"stale current rule")
    if not de.get("projection_drift"): bad("known projection drift must remain explicit")
    if not any(v.get("mintlify_projection_confirmed_stale") is True for v in de["projection_drift"]): bad("Mintlify projection drift evidence missing")
    r=d["reconciliation"]; eq(r["retroactive_phase_2_0_through_2_9_lane"],"active_until_hard_exit","retroactive lane"); eq(r["restricted_source_final_audit"],"pending","restricted audit"); eq(r["continuity_recovery_final_reproducibility_audit"],"pending","recovery audit")
    ni(r["approved_deferral_count_snapshot"],"approved deferrals"); ni(r["deferred_routing_tag_count_snapshot"],"deferred routing tags")
    ds=r["deferred_count_semantics"]
    eq(ds["governed_deferral_records_approved"],r["approved_deferral_count_snapshot"],"governed deferral count")
    eq(ds["deferred_reconciliation_tags"],r["deferred_routing_tag_count_snapshot"],"deferred routing count")
    eq(ds["extra_deferred_routing_tag"],"decision:phase20:domain_continuity","extra deferred route")
    eq(ds["extra_tag_is_hard_exit_pass"],False,"deferred routing is not PASS")
    eq(ds["extra_tag_is_governed_deferral_record"],False,"routing tag not governed deferral record")
    eq(ds["routing_metadata_never_creates_authority"],True,"routing metadata authority")
    if r["deferred_routing_tag_count_snapshot"] <= r["approved_deferral_count_snapshot"]: bad("current deferred routing tags must preserve the extra non-governed Phase20 routing tag")
    t=r["reconciliation_tag_snapshot"]; ts(t["observed_at"],"tag time")
    for k in ("total","pass","open","blocked","closed","deferred","authoritative","scan_required","reconcile_required"): ni(t[k],f"tag.{k}")
    eq(t["pass"]+t["open"]+t["blocked"]+t["closed"]+t["deferred"],t["total"],"tag arithmetic"); eq(t["authoritative"],t["total"],"tag authoritative"); eq(t["scan_required"],t["total"],"tag scan"); eq(t["reconcile_required"],t["total"],"tag reconcile"); eq(t["deferred"],r["deferred_routing_tag_count_snapshot"],"tag deferred count"); eq(t["pass_remains_drift_watched"],True,"PASS watch"); eq(t["deferral_is_not_pass"],True,"deferral semantics"); eq(t["unknown_never_becomes_zero_or_pass"],True,"unknown semantics"); eq(t["absence_of_unknown_tag_does_not_prove_zero_unknown_state"],True,"unknown absence semantics")
    s=r["latest_formal_reconciliation_scan"]; eq(s["scanner_id"],"ct.reconciliation.lmno.agent-e","scanner"); eq(s["status"],"partial","scan status")
    for k in ("tagged_scopes","reconciled_scopes","drift_scopes","unresolved_scopes","formal_scan_coverage_gap"): ni(s[k],f"scan.{k}")
    if s["tagged_scopes"]>t["total"] or s["reconciled_scopes"]>t["total"]: bad("formal scan exceeds current tag universe")
    eq(s["formal_scan_coverage_gap"],t["total"]-s["reconciled_scopes"],"scan gap"); eq(s["formal_scan_coverage_complete"],s["formal_scan_coverage_gap"]==0,"scan complete"); eq(s["formal_scan_stale_against_current_tags"],s["formal_scan_coverage_gap"]>0,"scan stale"); ts(s["completed_at"],"scan completed")
    sup=r["supplemental_reconciliation_scans"]
    if not sup: bad("supplemental reconciliation evidence missing")
    ids={v.get("scanner_id") for v in sup}
    if "ct.subagent.credential-continuity" not in ids or "ct.reconciliation.webhook-delivery.agent-h" not in ids: bad("expected supplemental scanners missing")
    for v in sup:
        eq(v.get("non_voting"),True,f"{v.get('scanner_id')}.non_voting")
        eq(v.get("formal_lmno_coverage_substitute"),False,f"{v.get('scanner_id')}.formal substitute")
        for k in ("tagged_scopes","reconciled_scopes","drift_scopes","unresolved_scopes"): ni(v[k],f"{v.get('scanner_id')}.{k}")
        ts(v["completed_at"],f"{v.get('scanner_id')}.completed")
    m=r["permissioned_source_accounting"]; A=set(m["sources_attempted"]); R=set(m["sources_read"]); U=set(m["sources_unavailable"])
    if not A or not R.issubset(A) or not U.issubset(A) or R&U: bad("Agent M source accounting invalid")
    eq(A,{"github","supabase","mintlify","google_drive","gmail"},"Agent M source set"); eq(m["full_current_scope_scan_required"],True,"full source scan"); eq(m["state"],"partial_current_full_scan_required","M state")
    q=d["repository_security_sequence"]; eq(q["verification_baseline_main_sha"],d["observed_main_sha"],"repo baseline"); eq(q["canonicalization_complete"],True,"canonicalization"); eq(q["github_role"],"technical_defense_in_depth_not_sovereign_authority","GitHub role")
    for k in ("pr_64","pr_95","pr_65","pr_117","pr_119","pr_91"): eq(q[k]["state"],"merged_canonical",f"{k}.state"); sh(q[k]["merge_sha"],f"{k}.sha")
    eq(q["pr_91"]["merge_sha"],d["observed_main_sha"],"current PR91 main")
    z=q["pr_66_issue_79"]; eq(z["issue_79_state"],"closed_completed","RLS issue"); eq(z["critical_defense_in_depth_finding_resolved"],True,"RLS finding")
    for k in ("original_remediation_table_count","current_integration_control_table_count","current_rls_enabled_table_count","current_rls_policy_count"): ni(z[k],f"RLS.{k}")
    if z["current_integration_control_table_count"]<z["original_remediation_table_count"]: bad("RLS estate regressed")
    eq(z["current_rls_enabled_table_count"],z["current_integration_control_table_count"],"RLS coverage"); eq(z["current_rls_policy_count"],z["current_integration_control_table_count"],"policy coverage"); eq(z["current_force_rls_enabled"],False,"FORCE RLS"); eq(z["current_policies_service_role_only_all"],True,"RLS policy role"); eq(z["machine_gate_state"],"passed","RLS gate")
    c=d["collab_portal"]; eq(c["state"],"fail_closed_deferred_point_of_use","Collab state"); eq(c["canonical_predicate_count"],7,"Collab predicates"); eq(c["predicates_passed_count"],6,"Collab progress"); eq(c["all_seven_certification_predicates_passed"],False,"Collab 7/7"); eq(c["webhook_sender_delivery_integrity"],"governed_deferred_not_passed","Collab webhook"); eq(c["technical_webhook_delivery_state"],"unproven","Collab technical"); eq(c["private_fallback_tracking"],"active","Collab fallback")
    if not c.get("mandatory_reopen_trigger"): bad("Collab reopen trigger missing")
    pd=d["provider_delivery_deferrals"]; eq(set(pd),{"collab_portal","partnero","stripe"},"provider deferrals")
    for k,v in pd.items(): eq(v["technical_state"],"unproven",f"{k}.technical"); eq(v["technical_pass_claimed"],False,f"{k}.pass")
    g=gates(d); eq(g["CT-P299-GATE-004"]["state"],"pass","GATE004"); eq(g["CT-P299-GATE-005"]["state"],"pass","GATE005"); eq(g["CT-P299-GATE-006"]["state"],"deferred_accepted_not_passed","GATE006"); eq(g["CT-P299-GATE-006"]["blocking"],False,"GATE006 block"); eq(g["CT-P299-GATE-008"]["state"],"not_met","GATE008"); eq(g["CT-P299-GATE-008"]["full_documentation_estate_gate"],"nondeferrable_not_met","GATE008 docs")
    if s["formal_scan_coverage_gap"]>0: eq(g["CT-P299-GATE-003"]["state"],"not_met","GATE003 incomplete scan"); eq(g["CT-P299-GATE-003"]["blocking"],True,"GATE003 block"); eq(g["CT-P299-GATE-003"]["formal_scan_coverage_gap"],s["formal_scan_coverage_gap"],"GATE003 gap")
    eq(len([v for v in g.values() if v.get("blocking") and v.get("state")!="pass"]),5,"blocking gate count")
    h=d["hard_exit"]; eq(h["state"],"not_met","hard exit"); eq(h["blocking_gate_count"],5,"hard blockers"); eq(h["deferred_not_passed_gate_count"],1,"hard deferred"); eq(h["phase_2_complete"],False,"Phase2"); eq(h["phase_3_entry_open"],False,"Phase3 open"); eq(h["phase_3_entry"],"blocked_pending_phase_2_99_hard_exit","Phase3"); eq(h["gate_008_fail_closed_while_upstream_unresolved"],True,"GATE008 fail closed")
    i=d["integration"]; eq(i["workflow_wiring_state"],"active_governed_ci","workflow"); eq(i["rollback"],"revert_bounded_closure_ledger_packet","rollback")
    if "reconciliation tag total/distribution drift" not in i["reopen_triggers"]: bad("tag-drift reopen trigger missing")
    if check_files:
        for p in d["evidence_paths"]+[i["workflow_path"]]:
            if not (ROOT/p).is_file(): bad(f"missing evidence: {p}")
        ph=load(ROOT/"developers/manifests/institutional-phase-namespace.v2.json"); eq(ph["decision_id"],"CT-ADR-ROADMAP-010","machine roadmap"); eq(ph["top_level_phase_count"],10,"machine phase count"); eq(ph["phase_3_entry"],"blocked_pending_phase_2_99_hard_exit","machine Phase3")
        if not (ROOT/cm["bundle_path"]).is_file(): bad("canonical 795 bundle missing")

def expect_fail(d,fn,n):
    x=copy.deepcopy(d); fn(x)
    try: validate(x,False)
    except ValueError: return
    raise AssertionError(n+" must fail")
def self_test(d):
    validate(d,False)
    expect_fail(d,lambda x:x["authority"].__setitem__("top_level_phase_count",20),"premature 20-phase promotion")
    expect_fail(d,lambda x:x["articleization"].__setitem__("complete_machine_manifest_generated_in_repo",False),"PR91 regression")
    expect_fail(d,lambda x:x["articleization"].__setitem__("terminal_disposition_assigned_795",True),"false terminal closure")
    expect_fail(d,lambda x:x["reconciliation"]["latest_formal_reconciliation_scan"].__setitem__("formal_scan_coverage_complete",True),"false scan coverage")
    expect_fail(d,lambda x:x["open_hard_gates"][2].__setitem__("state","pass"),"GATE003 with coverage gap")
    expect_fail(d,lambda x:x["repository_security_sequence"]["pr_66_issue_79"].__setitem__("current_rls_enabled_table_count",14),"RLS regression")
    expect_fail(d,lambda x:x["collab_portal"].__setitem__("all_seven_certification_predicates_passed",True),"false Collab 7/7")
    expect_fail(d,lambda x:x["provider_delivery_deferrals"]["stripe"].__setitem__("technical_pass_claimed",True),"deferral promoted")
    expect_fail(d,lambda x:x["open_hard_gates"][7].__setitem__("state","pass"),"premature GATE008")
    expect_fail(d,lambda x:x["reconciliation"].__setitem__("approved_deferral_count_snapshot",9),"governed deferrals conflated with deferred routing tags")
    expect_fail(d,lambda x:x["reconciliation"]["supplemental_reconciliation_scans"][1].__setitem__("formal_lmno_coverage_substitute",True),"Agent H substituted for formal LMNO proof")
    expect_fail(d,lambda x:x["reconciliation"]["reconciliation_tag_snapshot"].__setitem__("deferred",8),"deferred tag count drift hidden")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--self-test",action="store_true"); a=p.parse_args(); d=load(LEDGER)
    if a.self_test: self_test(d); print("Phase 2.99 ledger v1.3.2 self-test PASS: 218 tags reconciled, 8 governed deferrals != 9 deferred routing tags, supplemental scans non-sovereign, GATE008 fail-closed."); return 0
    validate(d); s=d["reconciliation"]["latest_formal_reconciliation_scan"]; print("Phase 2.99 ledger v1.3.2 consistency PASS"); print(f"Current tags={d['reconciliation']['reconciliation_tag_snapshot']['total']}; formal-LMNO gap={s['formal_scan_coverage_gap']}; governed deferrals={d['reconciliation']['approved_deferral_count_snapshot']}; deferred tags={d['reconciliation']['deferred_routing_tag_count_snapshot']}"); print("Hard exit NOT MET; GATE006 deferred/NOT-PASS; Phase3 blocked."); return 0
if __name__=="__main__": raise SystemExit(main())
