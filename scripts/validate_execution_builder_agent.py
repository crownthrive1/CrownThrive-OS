#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'developers/manifests/execution-builder-agent.v1.json').read_text())
req=json.loads((ROOT/'developers/contracts/agent-build-request.v1.schema.json').read_text())
rec=json.loads((ROOT/'developers/contracts/agent-build-receipt.v1.schema.json').read_text())
errors=[]
if manifest['agent_id']!='ct.agent.execution-builder': errors.append('agent_id')
if manifest['parent_agent_id']!='ct.relay.agent-c': errors.append('parent')
if manifest['agent_class']!='builder' or manifest['autonomy_class']!='A3': errors.append('class')
if manifest['authority_ceiling']!='D2' or manifest['vote_eligible'] or manifest['quorum_eligible'] or not manifest['d3_human_reserved']: errors.append('authority')
if manifest['independent_certifier'] is not False or manifest['no_self_approval'] is not True: errors.append('separation')
for x in ['direct_main_write','force_push','self_merge','self_certification','sovereign_vote','d3_action','trade_secret_publication','credential_or_raw_secret_export']:
    if x not in manifest['prohibited']: errors.append('missing_prohibition:'+x)
if rec['properties']['receipt_state']['const']!='BUILT_PENDING_INDEPENDENT_VERIFICATION': errors.append('receipt_state')
if rec['properties']['certification_effect']['const'] is not False or rec['properties']['sovereign_vote_created']['const'] is not False or rec['properties']['operational_activation']['const'] is not False: errors.append('receipt_authority')
if req['properties']['authority_ceiling']['enum']!=['D0','D1','D2'] or req['properties']['d3_allowed']['const'] is not False: errors.append('request_authority')
pre=(ROOT/'supabase/migrations/20260823203546_execution_builder_capability_contract_identity_v1.sql').read_text().lower()
for token in ['vaulted_capability_registry','trade_secret_assets','hold_capability_view_storage_drift','hold_capability_base_primary_key_missing']:
    if token not in pre: errors.append('capability_storage_preflight:'+token)
if 'create unique index' in pre or 'drop index' in pre: errors.append('view_index_mutation_prohibited')
sql=(ROOT/'supabase/migrations/20260823203649_execution_builder_agent_v1_0_1.sql').read_text()
low=sql.lower()
for token in ['ct.agent.execution-builder','vaulted_capability_registry','trade_secret_assets','agent_build_requests','agent_build_receipts','route_construction_work_to_execution_builder','route_capability_execution_to_execution_builder','complete_agent_build_request','built_pending_independent_verification']:
    if token not in low: errors.append('migration_missing:'+token)
if "'build_execution'" in low: errors.append('invalid_capability_kind')
if re.search(r'(?i)grant\s+.*\s+to\s+(anon|authenticated)\b',sql): errors.append('client_grant')
for forbidden in ['direct_main_write,true','force_push,true','self_merge,true','d3_allowed,true','sovereign_vote_created,true','certification_effect,true']:
    if forbidden in low.replace(' ',''): errors.append('forbidden_true:'+forbidden)
rollback=(ROOT/'supabase/rollback/20260823203100_execution_builder_agent_v1_0_1.rollback.sql').read_text().lower()
if 'delete from chlom_runtime.agent_build_receipts' in rollback or 'drop table if exists chlom_runtime.agent_build_receipts' in rollback: errors.append('receipt_history_delete')
if "invocation_state='revoked'" not in rollback or "lifecycle_state='superseded'" not in rollback: errors.append('rollback_disable_state')
workflow=(ROOT/'.github/workflows/execution-builder-governance.yml').read_text()
if re.search(r'(?m)^\s*id-token:\s*write|^\s*(contents|pull-requests|actions|packages|security-events):\s*write',workflow): errors.append('workflow_write_authority')
if errors:
    print('\n'.join('FAIL: '+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({'status':'PASS','agent':'ct.agent.execution-builder','parent':'ct.relay.agent-c','authority':'D2','non_voting':True,'request_sources':2,'runtime_version':'1.0.1','receipt_state':'BUILT_PENDING_INDEPENDENT_VERIFICATION'},sort_keys=True))
