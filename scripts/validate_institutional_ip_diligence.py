#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, pathlib, re, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]; P=ROOT/'institutional-ip'
spec=importlib.util.spec_from_file_location('mid',P/'master_ip_diligence.py'); M=importlib.util.module_from_spec(spec); sys.modules[spec.name]=M; spec.loader.exec_module(M)
bundle=json.loads((P/'master-ip-diligence-v2.bundle.json').read_text()); errors=M.validate_bundle(bundle)
sql=(ROOT/'supabase/migrations/20260822213000_institutional_ip_registry_candidate.sql').read_text(); low=sql.lower()
if 'candidate_not_applied' not in low or re.search(r'create\s+policy',sql,re.I): errors.append('migration_policy_or_state_drift')
if 'revoke all on all tables in schema institutional_ip from public, anon, authenticated' not in low or 'grant select, insert, update, delete on all tables in schema institutional_ip to service_role' not in low: errors.append('service_only_grant_drift')
nav=json.loads((ROOT/'developers/manifests/institutional-ip-navigation-patch.v1.json').read_text())
if nav['state']!='CANDIDATE_NOT_APPLIED' or nav['direct_dashboard_write_allowed'] is not False: errors.append('navigation_drift')
workflow=(ROOT/'.github/workflows/institutional-ip-diligence.yml').read_text()
if re.search(r'(?m)^\s*id-token:\s*write|^\s*(contents|pull-requests|packages|actions|security-events):\s*write',workflow): errors.append('workflow_authority_drift')
for required in ['06b2ab4348248b456ee06c9e953637f55e03504f','3d3c42e5aac5ba805825da76410c181273ba90b1','5fda3b95a4ea91299a34e894583c3862153e4b97']:
 if required not in workflow: errors.append('workflow_pin_missing:'+required)
if errors: print('\n'.join('FAIL: '+x for x in sorted(set(errors)))); raise SystemExit(1)
print(json.dumps({'status':'PASS','lifecycle':'PREPARED_NOT_ACTIVATED','five_systems':True,'invention_families':20,'title_verified':0,'valued_assets':0,'paid_customers':0,'recognized_revenue':0,'database_migration_applied':False,'sovereign_vote_created':False},sort_keys=True))
