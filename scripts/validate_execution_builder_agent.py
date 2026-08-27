#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import re

from penta_runtime_custody import assert_function, assert_lineage, assert_migration, assert_object, load

ROOT = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'developers/manifests/execution-builder-agent.v1.json').read_text())
req = json.loads((ROOT / 'developers/contracts/agent-build-request.v1.schema.json').read_text())
rec = json.loads((ROOT / 'developers/contracts/agent-build-receipt.v1.schema.json').read_text())
errors: list[str] = []

if manifest['agent_id'] != 'ct.agent.execution-builder': errors.append('agent_id')
if manifest['parent_agent_id'] != 'ct.relay.agent-c': errors.append('parent')
if manifest['agent_class'] != 'builder' or manifest['autonomy_class'] != 'A3': errors.append('class')
if manifest['authority_ceiling'] != 'D2' or manifest['vote_eligible'] or manifest['quorum_eligible'] or not manifest['d3_human_reserved']: errors.append('authority')
if manifest['independent_certifier'] is not False or manifest['no_self_approval'] is not True: errors.append('separation')
for x in ['direct_main_write','force_push','self_merge','self_certification','sovereign_vote','d3_action','trade_secret_publication','credential_or_raw_secret_export']:
    if x not in manifest['prohibited']: errors.append('missing_prohibition:' + x)
if rec['properties']['receipt_state']['const'] != 'BUILT_PENDING_INDEPENDENT_VERIFICATION': errors.append('receipt_state')
if rec['properties']['certification_effect']['const'] is not False or rec['properties']['sovereign_vote_created']['const'] is not False or rec['properties']['operational_activation']['const'] is not False: errors.append('receipt_authority')
if req['properties']['authority_ceiling']['enum'] != ['D0','D1','D2'] or req['properties']['d3_allowed']['const'] is not False: errors.append('request_authority')

try:
    provider = load()
    assert_lineage(provider)
    assert_migration(provider, 'execution_builder_capability_contract_identity_v1', '20260823203546')
    assert_migration(provider, 'execution_builder_agent_v1_0_1', '20260823203649')
    for name in (
        'chlom_runtime.route_construction_work_to_execution_builder',
        'chlom_runtime.route_capability_execution_to_execution_builder',
        'chlom_runtime.complete_agent_build_request',
    ):
        assert_function(provider, name)
    for obj in (
        'chlom_runtime.vaulted_capability_registry',
        'chlom_runtime.agent_build_requests',
        'chlom_runtime.agent_build_receipts',
        'chlom_secrets.trade_secret_assets',
    ):
        assert_object(provider, obj)
except AssertionError as exc:
    errors.append('provider_runtime_custody:' + str(exc))

rollback = (ROOT / 'supabase/rollback/20260823203100_execution_builder_agent_v1_0_1.rollback.sql').read_text().lower()
if 'delete from chlom_runtime.agent_build_receipts' in rollback or 'drop table if exists chlom_runtime.agent_build_receipts' in rollback: errors.append('receipt_history_delete')
if "invocation_state='revoked'" not in rollback or "lifecycle_state='superseded'" not in rollback: errors.append('rollback_disable_state')
workflow = (ROOT / '.github/workflows/execution-builder-governance.yml').read_text()
if re.search(r'(?m)^\s*id-token:\s*write|^\s*(contents|pull-requests|actions|packages|security-events):\s*write', workflow): errors.append('workflow_write_authority')

if errors:
    print('\n'.join('FAIL: ' + x for x in sorted(set(errors))))
    raise SystemExit(1)
print(json.dumps({'status':'PASS','agent':'ct.agent.execution-builder','parent':'ct.relay.agent-c','authority':'D2','non_voting':True,'runtime_version':'1.0.1','receipt_state':'BUILT_PENDING_INDEPENDENT_VERIFICATION','provider_runtime_custody':'PASS','historical_source_sql_reconstructed':False}, sort_keys=True))
