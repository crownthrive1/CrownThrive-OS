#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/framework-production-promotion.v1.json"
MIGRATION = ROOT / "supabase/migrations/20260823235410_framework_production_promotion_and_cie_activation_v1.sql"
REPAIR = ROOT / "supabase/migrations/20260824001624_framework_production_ask_first_confirmation_repair_v2.sql"
CHAIN_V2 = ROOT / "supabase/migrations/20260824044508_append_chain_event_production_authority_v2.sql"
CHAIN_V3 = ROOT / "supabase/migrations/20260824044725_append_chain_event_parent_hosted_child_package_v3.sql"
STANDARD = ROOT / "standards/framework-production-promotion-and-rollback.md"

errors=[]
for path in (MANIFEST,MIGRATION,REPAIR,CHAIN_V2,CHAIN_V3,STANDARD):
    if not path.is_file(): errors.append(f"missing:{path.relative_to(ROOT)}")
if errors:
    raise SystemExit("\n".join(errors))

m=json.loads(MANIFEST.read_text())
s=MIGRATION.read_text(); r=REPAIR.read_text(); c2=CHAIN_V2.read_text(); c3=CHAIN_V3.read_text()
combined="\n".join((s,r,c2,c3))

required_functions=[
  "confirm_founder_override_deadlock_preflight_v1",
  "framework_production_authority_v1",
  "activate_repository_guardian_production_v1",
  "activate_cie_production_v1",
  "rollback_framework_production_v1",
  "append_chain_event"
]
for name in required_functions:
    if name not in combined: errors.append("missing_function:"+name)

required_controls=[
  "framework_production_receipts_v1",
  "force row level security",
  "revoke all on function",
  "service_role_required",
  "agent_d_certification_required",
  "public_activation_allowed=false",
  "production_limited",
  "commercial_state='hold'",
  "rollback_framework_production_v1"
]
for needle in required_controls:
    if needle.lower() not in combined.lower(): errors.append("missing_control:"+needle)

repair_required=[
  "founder_confirmation_state='confirmed_external'",
  "override_executable=false",
  "f.override_executable",
  "separate_exact_founder_continuity_request",
  "execution_authority_source",
  "confirmed_external_exact_deadlock_preflight_required"
]
for needle in repair_required:
    if needle.lower() not in r.lower(): errors.append("missing_repair_control:"+needle)
if "founder_confirmation_state='confirmed'" in r or "override_executable=true" in r:
    errors.append("preflight_must_never_become_executable")

chain_v3_required=[
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
]
for needle in chain_v3_required:
    if needle.lower() not in c3.lower(): errors.append("missing_chain_v3_control:"+needle)

if "canonical_host_repo_id=p_repo_id" in c3.replace(" ",""):
    errors.append("stale_same_repo_package_host_assumption")

if m["schema_version"] != "1.0.2": errors.append("manifest_schema_version")
if len(m["migrations"]) < 4: errors.append("migration_registry_incomplete")
if m["production_state_model"]["authority_expansion"] is not False: errors.append("authority_expansion")
a=m["authority_modes"]
if a["founder_ask_first_required"] is not True: errors.append("ask_first")
if a["preflight_confirmation_state"] != "confirmed_external": errors.append("confirmation_state")
if a["preflight_override_executable"] is not False: errors.append("preflight_executable")
if a["execution_authority_source_after_founder_confirmation"] != "separate_exact_founder_continuity_request": errors.append("execution_authority_source")
if a["silence_is_authority"] is not False: errors.append("silence_authority")
if a["surrogate_production_activation"] is not False: errors.append("surrogate_activation")
if m["guardian"]["merge_authority"] or m["guardian"]["delete_authority"] or m["guardian"]["child_self_activation"]: errors.append("guardian_authority")
cie=m["cie"]
if cie["public_activation"] or cie["commerce_activation"]: errors.append("cie_public_or_commerce")
if cie["accepted_public_contract_digest"] != "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2": errors.append("cie_digest")
if cie["parent_repository_id"] != "ct.repo.crownthrive-support": errors.append("cie_parent_repo")
if cie["parent_hosted_package_allowed_only_with_exact_link"] is not True: errors.append("cie_parent_host_exact_link")
if cie["founder_override_chain_evidence_requires_exact_production_authority_verifier"] is not True: errors.append("cie_founder_chain_authority")
if not all([m["security"]["security_definer_fixed_search_path"],m["security"]["service_role_only"],m["security"]["forced_rls_receipts"],m["security"]["append_only_receipts"]]): errors.append("security_contract")
if m["security"]["anon_execute"] or m["security"]["authenticated_execute"] or m["security"]["raw_secret_export"]: errors.append("security_exposure")

if errors:
    print("\n".join("FAIL: "+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({
  "status":"PASS",
  "control_id":m["control_id"],
  "ask_first":True,
  "preflight_override_executable":False,
  "execution_authority_source":"separate_exact_founder_continuity_request",
  "parent_hosted_child_package_requires_exact_link":True,
  "production_limited_chain_evidence":True,
  "guardian_authority_expansion":False,
  "cie_public_activation":False,
  "cie_commerce_activation":False,
  "rollback_required":True
},sort_keys=True))
