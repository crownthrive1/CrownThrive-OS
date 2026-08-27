#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migration_lineage/legacy_local_timestamp_drift/local_only_versions/20260824073728_cie_post_activation_assurance_watch_v1.sql"
MANIFEST = ROOT / "developers/manifests/cie-post-activation-assurance-watch.v1.json"
LIVE_RECEIPT = ROOT / "developers/manifests/cie-post-activation-assurance-watch-live-receipt-20260824.v1.json"
DOC = ROOT / "standards/cie-post-activation-assurance-watch.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def require(text: str, values: tuple[str, ...], label: str) -> None:
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"{label} missing invariants: {missing}")


def require_false_map(value: object, label: str) -> None:
    if not isinstance(value, dict) or not value:
        fail(f"{label} must be a non-empty object")
    for key, flag in value.items():
        if flag is not False:
            fail(f"{label} expanded: {key}")


def main() -> int:
    for path in (MIGRATION, MANIFEST, LIVE_RECEIPT, DOC):
        if not path.is_file():
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    sql = MIGRATION.read_text(encoding="utf-8")
    lower = sql.lower()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = json.loads(LIVE_RECEIPT.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")

    if manifest.get("watch_id") != "ct.watch.cie.post-activation-assurance.v1": fail("watch identity drift")
    if manifest.get("framework_id") != "ct.framework.cultural-imprint-engine": fail("framework identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine": fail("canonical engine name drift")
    if manifest.get("accepted_public_contract_digest") != EXPECTED_DIGEST: fail("accepted CIE contract digest drift")

    host = manifest.get("host_schedule", {})
    if host.get("schedule_id") != "ct.schedule.repository-child-guardian-30m": fail("watch must reuse Repository Child Guardian schedule")
    if host.get("cron_job_name") != "ct-repository-child-guardian-30m": fail("watch cron binding drift")
    if host.get("cron_expression") != "7,37 * * * *": fail("watch cadence drift")
    if host.get("existing_slot_reused") is not True or host.get("scheduler_slot_delta") != 0: fail("watch may not add a scheduler slot")
    if host.get("guardian_agent_id") != "ct.agent.repository-child-guardian-ad-litem": fail("watch guardian agent drift")

    evidence = manifest.get("evidence_contract", {})
    if evidence.get("sql_makes_external_network_calls") is not False: fail("SQL may not claim external network access")
    if evidence.get("fresh_service_ingested_github_observations_required") is not True: fail("fresh external GitHub observations must be required")
    if evidence.get("freshness_window_minutes") != 90: fail("external evidence freshness window drift")
    if evidence.get("support_repository_id") != 1336348391 or evidence.get("cie_repository_id") != 1341314455: fail("repository identity drift")
    if evidence.get("support_descendant_proof_required_for_auto_refresh") is not True: fail("Support descendant proof must remain required")
    if evidence.get("support_compare_status") != "ahead" or evidence.get("support_compare_behind_by") != 0: fail("Support descendant compare semantics drift")
    if evidence.get("cie_child_head_must_equal_immutable_activation_child") is not True: fail("CIE child head must remain exact activation child for auto assurance")

    auto = manifest.get("automatic_actions", {})
    if auto.get("current_assurance_noop") is not True or auto.get("support_parent_descendant_assurance_refresh") is not True: fail("bounded parent assurance behavior drift")
    for key in ("cie_child_head_auto_refresh","production_reactivation","founder_authority_rewrite","public_activation","commerce_activation","provider_write","rights_grant","vote_effect","d3_auto"):
        if auto.get(key) is not False: fail(f"forbidden automatic action enabled: {key}")

    expected_holds = {"HOLD_PRODUCTION_BOUNDARY_DRIFT","HOLD_EXTERNAL_GITHUB_EVIDENCE_STALE","HOLD_CIE_CHILD_OBSERVATION_TRUST_MISMATCH","HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED","HOLD_SUPPORT_PARENT_OBSERVATION_TRUST_MISMATCH","HOLD_SUPPORT_DESCENDANT_PROOF_REQUIRED","HOLD_ASSURANCE_REFRESH_FAILED"}
    if set(manifest.get("hold_states", [])) != expected_holds: fail("hold-state contract drift")
    require_false_map(manifest.get("hard_boundaries"), "manifest hard boundary")

    require(sql,("create or replace function chlom_runtime.cie_post_activation_assurance_watch_v1","create or replace function chlom_runtime.repository_child_guardian_family_cycle_v1","ct.cie.post-activation-assurance-watch.v1","HOLD_EXTERNAL_GITHUB_EVIDENCE_STALE","HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED","HOLD_SUPPORT_DESCENDANT_PROOF_REQUIRED","PASS_CURRENT_ASSURANCE","PASS_ASSURANCE_REFRESHED","refresh_cie_parent_child_production_assurance_v1","v_child_obs.head_sha <> v_activation_child","compare_base_sha","compare_head_sha","compare_behind_by","compare_ahead_by","POST_ACTIVATION_ASSURANCE_","NON_DESTRUCTIVE_POST_ACTIVATION_ASSURANCE_NURTURE","scheduler_slot_delta',0","external_network_call_performed',false","production_authority_rewritten',false","operational_activation',false","provider_write_effect',false","economic_effect',false","rights_effect',false","vote_effect',false","D3_auto',false","repository_child_guardian_family_cycle_v1@1.2.0",EXPECTED_DIGEST),"migration")

    forbidden=("cron.schedule(","cron.unschedule(","insert into cron.job","update cron.job","insert into chlom_runtime.agent_schedule_definitions","activate_cie_production_v1(","production_authority_request_id'=","production_exact_version_ref'=","production_content_sha256'=","public_activation_allowed=true","commercial_state='active'","checkout_enabled=true","customer_entitlement_active=true","can_vote=true","d3_human_reserved=false","invocation_state='production'")
    for fragment in forbidden:
        if fragment in lower: fail(f"forbidden watcher mutation: {fragment}")

    require(lower,("security definer","set search_path = pg_catalog","revoke all on function chlom_runtime.cie_post_activation_assurance_watch_v1","revoke all on function chlom_runtime.repository_child_guardian_family_cycle_v1","from public,anon,authenticated","grant execute on function chlom_runtime.cie_post_activation_assurance_watch_v1","grant execute on function chlom_runtime.repository_child_guardian_family_cycle_v1","to service_role"),"access control")
    require(doc,("Cultural Imprint Engine (CIE)","adds **no new cron job, no new external scheduler task, and no new agent authority**","PostgreSQL does not call GitHub","HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED","scheduler slot delta: `0`","does not pretend that database automation can independently observe GitHub"),"documentation")

    if live.get("watch_id") != manifest.get("watch_id"): fail("live receipt watch identity mismatch")
    if live.get("evidence_class") != "historical_live_runtime_certification_not_authority": fail("live receipt evidence class drift")
    if live.get("source_head_before_apply") != "97a8275cbb1a85c0cdbdbb3b3e8e88982e5d23e3": fail("live receipt source head drift")
    db=live.get("database_migration",{})
    if db.get("source_file_version")!="20260824073728" or db.get("applied_version")!="20260824074339" or db.get("apply_state")!="success": fail("live migration receipt drift")
    sched=live.get("existing_schedule",{})
    if sched.get("jobid")!=125 or sched.get("schedule")!="7,37 * * * *" or sched.get("scheduler_slot_delta")!=0 or sched.get("new_cron_job_created") is not False or sched.get("cron_command_changed") is not False: fail("live scheduler reuse evidence drift")
    real=live.get("real_watch_test",{})
    if real.get("state")!="PASS_CURRENT_ASSURANCE" or real.get("refresh_performed") is not False or real.get("current_link_receipt_id")!="93ea4068-b4a3-4858-adac-13a5e482c98c" or real.get("external_network_call_performed") is not False or real.get("production_authority_rewritten") is not False: fail("real watcher certification drift")
    family=live.get("guardian_family_cycle_test",{})
    if family.get("state")!="PASS_CONTROLLED_TEST" or family.get("runtime_version")!="1.2.0" or family.get("watch_state")!="PASS_CURRENT_ASSURANCE" or family.get("scheduler_slot_delta")!=0 or family.get("production_authority_rewritten") is not False: fail("Guardian family cycle certification drift")
    canaries=live.get("rollback_only_negative_canaries",{})
    if canaries.get("cie_child_head_change",{}).get("state")!="HOLD_CIE_CHILD_HEAD_CHANGED_REAUTH_REQUIRED": fail("child-head negative canary drift")
    if canaries.get("support_parent_missing_descendant_proof",{}).get("state")!="HOLD_SUPPORT_DESCENDANT_PROOF_REQUIRED": fail("parent-proof negative canary drift")
    rollback=canaries.get("rollback_readback",{})
    if any(rollback.get(k)!=0 for k in ("fake_child_observations","fake_parent_observations","fake_child_actions","fake_parent_actions","fake_child_dail_events","fake_parent_dail_events")): fail("rollback canary persistence detected")
    security=live.get("security_readback",{})
    if security.get("watch_security_definer") is not True or security.get("watch_pinned_search_path") is not True or security.get("guardian_wrapper_security_definer") is not True or security.get("guardian_wrapper_pinned_search_path") is not True or security.get("supabase_security_advisor_lints")!=0: fail("live security readback drift")
    authority=live.get("immutable_production_authority",{})
    if authority.get("activation_receipt_id")!="8b638a18-81e8-4f4a-b6c2-d54340d61d36" or authority.get("authority_mode")!="founder_direct" or authority.get("founder_request_id")!="8af419dd-5bdd-4f5e-be72-a8b9bc73b8ad" or authority.get("protected_canary_verdict")!="PASS" or authority.get("protected_canary_score")!="100.00" or authority.get("rollback_state")!="ready" or authority.get("authority_snapshot_rewritten") is not False: fail("immutable production authority drift")
    require_false_map(live.get("hard_boundaries"), "live receipt hard boundary")
    reuse=str(live.get("reuse_rule","")).lower()
    if "not production authority" not in reuse or "must not be used to infer current github state" not in reuse: fail("live receipt reuse boundary missing")

    joined="\n".join((sql,json.dumps(manifest,sort_keys=True),json.dumps(live,sort_keys=True),doc))
    for pattern in (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",r"\bsk-[A-Za-z0-9]{20,}\b",r"\bmint_[A-Za-z0-9_-]{16,}\b",r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"):
        if re.search(pattern,joined): fail("credential-shaped value detected")

    print("CIE post-activation assurance watch PASS: existing Guardian 30m slot reused; live watcher and rollback canaries certified; fresh external GitHub evidence required; Support descendant parent drift may auto-assure; CIE child changes require reauthorization; no activation, Founder-authority rewrite, public, provider, economic, rights, vote, D3, or scheduler-slot effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
