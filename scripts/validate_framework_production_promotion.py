#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/framework-production-promotion.v1.json"
MIGRATION = ROOT / "supabase/migrations/20260823235410_framework_production_promotion_and_cie_activation_v1.sql"
STANDARD = ROOT / "standards/framework-production-promotion-and-rollback.md"

errors=[]
for path in (MANIFEST,MIGRATION,STANDARD):
    if not path.is_file(): errors.append(f"missing:{path.relative_to(ROOT)}")
if errors:
    raise SystemExit("\n".join(errors))

m=json.loads(MANIFEST.read_text())
s=MIGRATION.read_text()

required_functions=[
  "confirm_founder_override_deadlock_preflight_v1",
  "framework_production_authority_v1",
  "activate_repository_guardian_production_v1",
  "activate_cie_production_v1",
  "rollback_framework_production_v1"
]
for name in required_functions:
    if name not in s: errors.append("missing_function:"+name)

required_sql=[
  "framework_production_receipts_v1",
  "force row level security",
  "revoke all on function",
  "service_role_required",
  "founder_confirmation_state='confirmed'",
  "override_executable",
  "agent_d_certification_required",
  "public_activation_allowed=false",
  "production_limited",
  "commercial_state='hold'",
  "rollback_framework_production_v1"
]
for needle in required_sql:
    if needle.lower() not in s.lower(): errors.append("missing_control:"+needle)

if m["production_state_model"]["authority_expansion"] is not False: errors.append("authority_expansion")
if m["authority_modes"]["founder_ask_first_required"] is not True: errors.append("ask_first")
if m["authority_modes"]["silence_is_authority"] is not False: errors.append("silence_authority")
if m["authority_modes"]["surrogate_production_activation"] is not False: errors.append("surrogate_activation")
if m["guardian"]["merge_authority"] or m["guardian"]["delete_authority"] or m["guardian"]["child_self_activation"]: errors.append("guardian_authority")
if m["cie"]["public_activation"] or m["cie"]["commerce_activation"]: errors.append("cie_public_or_commerce")
if m["cie"]["accepted_public_contract_digest"] != "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2": errors.append("cie_digest")
if not all([m["security"]["security_definer_fixed_search_path"],m["security"]["service_role_only"],m["security"]["forced_rls_receipts"],m["security"]["append_only_receipts"]]): errors.append("security_contract")
if m["security"]["anon_execute"] or m["security"]["authenticated_execute"] or m["security"]["raw_secret_export"]: errors.append("security_exposure")

if errors:
    print("\n".join("FAIL: "+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({"status":"PASS","control_id":m["control_id"],"ask_first":True,"guardian_authority_expansion":False,"cie_public_activation":False,"cie_commerce_activation":False,"rollback_required":True},sort_keys=True))
