#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/framework-production-promotion.v1.json"
CONTRACT = ROOT / "developers/contracts/cie-production/founder-direct-production.contract.v1.json"
MIGRATION = ROOT / "supabase/migrations/20260823235410_framework_production_promotion_and_cie_activation_v1.sql"
REPAIR = ROOT / "supabase/migrations/20260824001624_framework_production_ask_first_confirmation_repair_v2.sql"
CHAIN_V2 = ROOT / "supabase/migrations/20260824044508_append_chain_event_production_authority_v2.sql"
CHAIN_V3 = ROOT / "supabase/migrations/20260824044725_append_chain_event_parent_hosted_child_package_v3.sql"
DIRECT_V4 = ROOT / "supabase/migrations/20260824050824_framework_production_founder_direct_authority_v4.sql"
STANDARD = ROOT / "standards/framework-production-promotion-and-rollback.md"
RUNBOOK = ROOT / "runbooks/production-deployment-and-rollback.mdx"

errors=[]
for path in (MANIFEST,CONTRACT,MIGRATION,REPAIR,CHAIN_V2,CHAIN_V3,DIRECT_V4,STANDARD,RUNBOOK):
    if not path.is_file(): errors.append(f"missing:{path.relative_to(ROOT)}")
if errors:
    raise SystemExit("\n".join(errors))

m=json.loads(MANIFEST.read_text())
c=json.loads(CONTRACT.read_text())
s=MIGRATION.read_text(); r=REPAIR.read_text(); c2=CHAIN_V2.read_text(); c3=CHAIN_V3.read_text(); d4=DIRECT_V4.read_text()
combined="\n".join((s,r,c2,c3,d4))

for name in (
  "confirm_founder_override_deadlock_preflight_v1",
  "framework_production_authority_v1",
  "activate_repository_guardian_production_v1",
  "activate_cie_production_v1",
  "rollback_framework_production_v1",
  "append_chain_event"
):
    if name not in combined: errors.append("missing_function:"+name)

for needle in (
  "framework_production_receipts_v1",
  "force row level security",
  "revoke all on function",
  "service_role_required",
  "agent_d_certification_required",
  "public_activation_allowed=false",
  "production_limited",
  "commercial_state='hold'",
  "rollback_framework_production_v1"
):
    if needle.lower() not in combined.lower(): errors.append("missing_control:"+needle)

for needle in (
  "founder_confirmation_state='confirmed_external'",
  "override_executable=false",
  "f.override_executable",
  "separate_exact_founder_continuity_request",
  "confirmed_external_exact_deadlock_preflight_required"
):
    if needle.lower() not in r.lower(): errors.append("missing_deadlock_repair_control:"+needle)
if "founder_confirmation_state='confirmed'" in r or "override_executable=true" in r:
    errors.append("deadlock_preflight_must_never_become_executable")

for needle in (
  "repository_parent_child_link_receipts_v1",
  "v_repo.parent_repo_id is distinct from v_package.canonical_host_repo_id",
  "v_link.parent_head_sha is distinct from v_repo.last_parent_sha",
  "v_link.child_head_sha is distinct from v_repo.last_child_sha",
  "not v_link.guardian_verified",
  "not v_link.family_verified",
  "not v_link.interoperability_verified",
  "v_link.authority_effect",
  "v_link.operational_activation",
  "v_link.vote_effect",
  "v_link.child_self_activation",
  "framework_production_authority_v1",
  "production_limited"
):
    if needle.lower() not in c3.lower() and needle.lower() not in d4.lower(): errors.append("missing_chain_control:"+needle)

for needle in (
  "p_authority_mode='founder_direct'",
  "founder_direct_d2_a2_required",
  "founder_direct_surrogate_must_be_ineligible",
  "CIE_GOVERNED_INTERNAL_PRODUCTION",
  "founder_direct_rollback_not_ready",
  "founder_direct_verification_failed",
  "explicit_human_founder",
  "v_mode not in ('founder_override','founder_direct')"
):
    if needle.lower() not in d4.lower(): errors.append("missing_founder_direct_control:"+needle)

if m["schema_version"] != "1.0.3": errors.append("manifest_schema_version")
if len(m["migrations"]) < 5: errors.append("migration_registry_incomplete")
a=m["authority_modes"]
if a["direct_human"] != "founder_direct": errors.append("founder_direct_mode")
if a["founder_direct_human_only"] is not True: errors.append("founder_direct_human_only")
if a["founder_direct_surrogate_ineligible"] is not True: errors.append("founder_direct_surrogate_ineligible")
if a["founder_direct_required_authority_class"] != "D2": errors.append("founder_direct_d2")
if a["founder_direct_required_autonomy_class"] != "A2": errors.append("founder_direct_a2")
if a["founder_direct_required_scope"] != "CIE_GOVERNED_INTERNAL_PRODUCTION": errors.append("founder_direct_scope")
if a["silence_is_authority"] is not False or a["surrogate_production_activation"] is not False or a["d3_human_reserved"] is not True: errors.append("authority_boundary")
if m["production_state_model"]["authority_expansion"] is not False: errors.append("authority_expansion")

fd=c["authority_modes"]["founder_direct"]
if fd["human_required"] is not True or fd["surrogate_allowed"] is not False or fd["surrogate_state_required"] != "ineligible": errors.append("contract_founder_direct_human_boundary")
if fd["authority_class_required"] != "D2" or fd["autonomy_class_required"] != "A2": errors.append("contract_founder_direct_class")
if fd["request_metadata_required"]["founder_direct"] is not True or fd["request_metadata_required"]["direct_scope"] != "CIE_GOVERNED_INTERNAL_PRODUCTION": errors.append("contract_founder_direct_scope")
ps=c["production_state"]
if ps["public_activation"] or ps["commerce_activation"] or ps["provider_write_effect"] or ps["rights_effect"] or ps["economic_effect"] or ps["vote_effect"] or ps["d3_auto"]: errors.append("contract_illicit_production_effect")
if ps["algorithm_invocation_state"] != "production_limited" or ps["api_exposure"] != "governed_internal_only" or ps["mcp_exposure"] != "governed_internal_only": errors.append("contract_runtime_scope")

cie=m["cie"]
if cie["public_activation"] or cie["commerce_activation"]: errors.append("cie_public_or_commerce")
if cie["accepted_public_contract_digest"] != "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2": errors.append("cie_digest")
if cie["parent_repository_id"] != "ct.repo.crownthrive-support": errors.append("cie_parent_repo")
if cie["founder_direct_chain_evidence_requires_exact_production_authority_verifier"] is not True: errors.append("cie_founder_direct_chain_authority")
if not all([m["security"]["security_definer_fixed_search_path"],m["security"]["service_role_only"],m["security"]["forced_rls_receipts"],m["security"]["append_only_receipts"]]): errors.append("security_contract")
if m["security"]["anon_execute"] or m["security"]["authenticated_execute"] or m["security"]["raw_secret_export"]: errors.append("security_exposure")

if errors:
    print("\n".join("FAIL: "+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({
  "status":"PASS",
  "control_id":m["control_id"],
  "authority_modes":["agent_d_certification","founder_override","founder_direct"],
  "founder_direct_human_only":True,
  "founder_direct_surrogate_ineligible":True,
  "founder_direct_authority":"D2",
  "founder_direct_autonomy":"A2",
  "founder_direct_scope":"CIE_GOVERNED_INTERNAL_PRODUCTION",
  "parent_hosted_child_package_requires_exact_link":True,
  "production_limited_chain_evidence":True,
  "cie_public_activation":False,
  "cie_commerce_activation":False,
  "rollback_required":True
},sort_keys=True))
