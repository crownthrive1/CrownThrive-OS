#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'developers/manifests/framework-production-promotion.v1.json'
CONTRACT=ROOT/'developers/contracts/cie-production/founder-direct-production.contract.v1.json'
DEPLOYMENT=ROOT/'developers/manifests/cie-production-deployment.v1.json'
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
for p in [MANIFEST,CONTRACT,DEPLOYMENT,*MIGRATIONS,STANDARD,RUNBOOK]:
    if not p.is_file(): errors.append(f'missing:{p.relative_to(ROOT)}')
if errors: raise SystemExit('\n'.join(errors))
m=json.loads(MANIFEST.read_text()); c=json.loads(CONTRACT.read_text()); d=json.loads(DEPLOYMENT.read_text())
texts={p.name:p.read_text() for p in MIGRATIONS}; combined='\n'.join(texts.values())

for needle in ['framework_production_receipts_v1','framework_production_authority_v1','activate_cie_production_v1','rollback_framework_production_v1','append_chain_event','service_role_required','production_limited']:
    if needle.lower() not in combined.lower(): errors.append('missing_control:'+needle)

v4=texts['20260824050824_framework_production_founder_direct_authority_v4.sql']
for needle in ["p_authority_mode='founder_direct'",'founder_direct_d2_a2_required','founder_direct_surrogate_must_be_ineligible','CIE_GOVERNED_INTERNAL_PRODUCTION','founder_direct_rollback_not_ready','explicit_human_founder',"v_mode not in ('founder_override','founder_direct')"]:
    if needle.lower() not in v4.lower(): errors.append('missing_founder_direct_control:'+needle)

v5=texts['20260824052111_framework_production_receipt_founder_direct_mode_v5.sql']
for needle in ['framework_production_receipts_v1_authority_mode_check',"'agent_d_certification'::text","'founder_override'::text","'founder_direct'::text","'rollback_only'::text"]:
    if needle.lower() not in v5.lower(): errors.append('missing_receipt_v5_control:'+needle)

expected=['agent_d_certification','founder_override','founder_direct','rollback_only']
if m.get('schema_version')!='1.0.4' or len(m.get('migrations',[]))<6: errors.append('manifest_version_or_migrations')
a=m['authority_modes']
if a.get('receipt_authority_vocabulary')!=expected: errors.append('manifest_receipt_vocabulary')
if a.get('direct_human')!='founder_direct' or a.get('founder_direct_human_only') is not True or a.get('founder_direct_surrogate_ineligible') is not True: errors.append('founder_direct_boundary')
if a.get('founder_direct_required_authority_class')!='D2' or a.get('founder_direct_required_autonomy_class')!='A2' or a.get('founder_direct_required_scope')!='CIE_GOVERNED_INTERNAL_PRODUCTION': errors.append('founder_direct_class_scope')
if a.get('silence_is_authority') is not False or a.get('surrogate_production_activation') is not False or a.get('d3_human_reserved') is not True: errors.append('authority_boundary')

receipt=c.get('production_receipt',{})
if receipt.get('authority_mode_vocabulary')!=expected or receipt.get('founder_direct_must_be_recordable') is not True: errors.append('contract_receipt_vocabulary')
fd=c['authority_modes']['founder_direct']
if fd.get('production_receipt_authority_mode')!='founder_direct' or fd.get('surrogate_allowed') is not False or fd.get('authority_class_required')!='D2' or fd.get('autonomy_class_required')!='A2': errors.append('contract_founder_direct')
ps=c['production_state']
if any(ps[k] for k in ['public_activation','commerce_activation','provider_write_effect','rights_effect','economic_effect','vote_effect','d3_auto']): errors.append('illicit_contract_effect')

if d.get('schema_version')!='1.0.0' or d.get('state')!='production_active': errors.append('deployment_state')
if d.get('platform_id')!='ct.platform.cie' or d.get('package_id')!='ct.framework-package.cie': errors.append('deployment_identity')
if d['authority'].get('mode')!='founder_direct' or d['authority'].get('surrogate_used') is not False or d['authority'].get('authority_class')!='D2' or d['authority'].get('autonomy_class')!='A2': errors.append('deployment_authority')
if d['authority'].get('agent_d_certification_created') or d['authority'].get('agent_q_certification_created'): errors.append('deployment_fabricated_independent_certification')
pr=d['production_receipt']
if not isinstance(pr.get('receipt_sha256'),str) or len(pr['receipt_sha256'])!=64 or pr.get('append_only_verified') is not True or pr.get('rollback_state')!='ready': errors.append('deployment_receipt')
if pr.get('raw_internal_receipt_id_public') or pr.get('raw_founder_request_id_public'): errors.append('deployment_internal_id_exposure')
canary=d['canary']
if canary.get('verdict')!='PASS' or canary.get('score')!='100.00' or canary.get('private_policy_body_returned') is not False: errors.append('deployment_canary')
rt=d['runtime']
if rt.get('repository_governance_state')!='linked_governed' or rt.get('package_state')!='maintained' or rt.get('operationally_enabled') is not True or rt.get('algorithm_invocation_state')!='production_limited': errors.append('deployment_runtime')
if any(rt[k] for k in ['public_activation','commerce_activation','provider_write_effect','rights_effect','economic_effect','vote_effect','d3_auto']): errors.append('deployment_illicit_effect')
if d['certification_dimensions']!={'total':16,'pass':12,'not_applicable':4,'open':0}: errors.append('deployment_dimensions')
interop=d['separate_interop_assurance_lane']
if interop.get('route_certification_state')!='candidate' or interop.get('composition_ceiling')!='COMPOSED_READY_NON_EXECUTING' or interop.get('production_core_blocking') is not False: errors.append('interop_assurance_truth')
if any(interop[k] for k in ['provider_write_authorized','economic_activation_authorized','d3_authorized','sovereign_vote_effect']): errors.append('interop_illicit_effect')
if d['ecosystem_boundary'].get('phase3')!='blocked' or d['ecosystem_boundary'].get('phase_advance_created_by_cie_production') is not False: errors.append('ecosystem_phase_claim')
if d['restricted_evidence'].get('public_document_contains_secrets') or d['restricted_evidence'].get('public_document_contains_private_policy_body'): errors.append('public_docs_secret_boundary')

runbook=RUNBOOK.read_text()
for needle in ['Current verified CIE production deployment — 2026-08-24','state: production_active','production_receipt_sha256: 27bec7a168bbbe66709652c048f6e083d4dc8092daae9ae8daa45a53542f62ed','canary_score: 100.00','COMPOSED_READY_NON_EXECUTING']:
    if needle not in runbook: errors.append('runbook_missing:'+needle)

if errors:
    print('\n'.join('FAIL: '+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({'status':'PASS','control_id':m['control_id'],'cie_deployment':'production_active','receipt_append_only':True,'canary':'PASS_100.00','dimensions':'16/16','founder_direct_human_only':True,'public_activation':False,'commerce_activation':False,'interop_assurance_lane':'candidate_non_executing','phase3_advanced':False},sort_keys=True))
