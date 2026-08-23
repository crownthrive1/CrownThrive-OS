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
pre=(ROOT/'supabase/migrations/20260823202950_execution_builder_capability_contract_identity_v1.sql').read_text()
if 'hold_capability_id_duplicates' not in pre.lower() or 'create unique index if not exists capability_contracts_capability_id_uq' not in pre.lower(): errors.append('capability_identity_prerequisite')
sql=(ROOT/'supabase/migrations/20260823203000_execution_builder_agent_v1.sql').read_text()
low=sql.lower()
for token in ['ct.agent.execution-builder','agent_build_requests','agent_build_receipts','route_construction_work_to_execution_builder','route_capability_execution_to_execution_builder','complete_agent_build_request','built_pending_independent_verification']:
    if token not in low: errors.append('migration_missing:'+token)
if re.search(r'(?i)grant\s+.*\s+to\s+(anon|authenticated)\b',sql): errors.append('client_grant')
for forbidden in ['direct_main_write,true','force_push,true','self_merge,true','d3_allowed,true','sovereign_vote_created,true','certification_effect,true']:
    if forbidden in low.replace(' ',''): errors.append('forbidden_true:'+forbidden)
workflow=(ROOT/'.github/workflows/execution-builder-governance.yml').read_text()
if re.search(r'(?m)^\s*id-token:\s*write|^\s*(contents|pull-requests|actions|packages|security-events):\s*write',workflow): errors.append('workflow_write_authority')
if errors:
    print('\n'.join('FAIL: '+x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({'status':'PASS','agent':'ct.agent.execution-builder','parent':'ct.relay.agent-c','authority':'D2','non_voting':True,'request_sources':2,'receipt_state':'BUILT_PENDING_INDEPENDENT_VERIFICATION'},sort_keys=True))
