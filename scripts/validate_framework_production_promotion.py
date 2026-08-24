#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'developers/manifests/framework-production-promotion.v1.json'
CONTRACT=ROOT/'developers/contracts/cie-production/founder-direct-production.contract.v1.json'
MIGRATIONS=[
 ROOT/'supabase/migrations/20260823235410_framework_production_promotion_and_cie_activation_v1.sql',
 ROOT/'supabase/migrations/20260824001624_framework_production_ask_first_confirmation_repair_v2.sql',
 ROOT/'supabase/migrations/20260824044508_append_chain_event_production_authority_v2.sql',
 ROOT/'supabase/migrations/20260824044725_append_chain_event_parent_hosted_child_package_v3.sql',
 ROOT/'supabase/migrations/20260824050824_framework_production_founder_direct_authority_v4.sql',
 ROOT/'supabase/migrations/20260824052111_framework_production_receipt_founder_direct_mode_v5.sql',
]
STANDARD=ROOT/'standards/framework-production-promotion-and-rollback.md'
RUNBOOK=ROOT/'runbooks/production-deployment-and-rollback.mdx'
errors=[]
for p in [MANIFEST,CONTRACT,*MIGRATIONS,STANDARD,RUNBOOK]:
    if not p.is_file(): errors.append(f'missing:{p.relative_to(ROOT)}')
if errors: raise SystemExit('\n'.join(errors))
m=json.loads(MANIFEST.read_text()); c=json.loads(CONTRACT.read_text())
texts={p.name:p.read_text() for p in MIGRATIONS}; combined='\n'.join(texts.values())

for needle in ['framework_production_receipts_v1','framework_production_authority_v1','activate_cie_production_v1','rollback_framework_production_v1','append_chain_event','service_role_required','production_limited']:
    if needle.lower() not in combined.lower(): errors.append('missing_control:'+needle)

v4=texts['20260824050824_framework_production_founder_direct_authority_v4.sql']
for needle in ["p_authority_mode='founder_direct'",'founder_direct_d2_a2_required','founder_direct_surrogate_must_be_ineligible','CIE_GOVERNED_INTERNAL_PRODUCTION','founder_direct_rollback_not_ready','explicit_human_founder',"v_mode not in ('founder_override','founder_direct')"]:
    if needle.lower() not in v4.lower(): errors.append('missing_founder_direct_control:'+needle)

v5=texts['20260824052111_framework_production_receipt_founder_direct_mode_v5.sql']
for needle in ['framework_production_receipts_v1_authority_mode_check',"'agent_d_certification'::text","'founder_override'::text","'founder_direct'::text","'rollback_only'::text"]:
    if needle.lower() not in v5.lower(): errors.append('missing_receipt_v5_control:'+needle)

if m.get('schema_version')!='1.0.4': errors.append('manifest_schema_version')
if len(m.get('migrations',[]))<6: errors.append('migration_registry_incomplete')
a=m['authority_modes']
expected=['agent_d_certification','founder_override','founder_direct','rollback_only']
if a.get('receipt_authority_vocabulary')!=expected: errors.append('manifest_receipt_vocabulary')
if a.get('direct_human')!='founder_direct' or a.get('founder_direct_human_only') is not True or a.get('founder_direct_surrogate_ineligible') is not True: errors.append('founder_direct_boundary')
if a.get('founder_direct_required_authority_class')!='D2' or a.get('founder_direct_required_autonomy_class')!='A2': errors.append('founder_direct_class')
if a.get('founder_direct_required_scope')!='CIE_GOVERNED_INTERNAL_PRODUCTION': errors.append('founder_direct_scope')
if a.get('silence_is_authority') is not False or a.get('surrogate_production_activation') is not False or a.get('d3_human_reserved') is not True: errors.append('authority_boundary')

receipt=c.get('production_receipt',{})
if receipt.get('authority_mode_vocabulary')!=expected or receipt.get('founder_direct_must_be_recordable') is not True: errors.append('contract_receipt_vocabulary')
fd=c['authority_modes']['founder_direct']
if fd.get('production_receipt_authority_mode')!='founder_direct' or fd.get('surrogate_allowed') is not False or fd.get('authority_class_required')!='D2' or fd.get('autonomy_class_required')!='A2': errors.append('contract_founder_direct')
ps=c['production_state']
if any(ps[k] for k in ['public_activation','commerce_activation','provider_write_effect','rights_effect','economic_effect','vote_effect','d3_auto']): errors.append('illicit_production_effect')
if ps['algorithm_invocation_state']!='production_limited' or ps['api_exposure']!='governed_internal_only' or ps['mcp_exposure']!='governed_internal_only': errors.append('runtime_scope')

if errors:
    print('\n'.join('FAIL: '+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({'status':'PASS','control_id':m['control_id'],'authority_modes':expected,'founder_direct_human_only':True,'founder_direct_surrogate_ineligible':True,'production_receipt_founder_direct_recordable':True,'cie_public_activation':False,'cie_commerce_activation':False,'rollback_required':True},sort_keys=True))
