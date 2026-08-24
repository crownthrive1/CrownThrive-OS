#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, pathlib, re, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]; P=ROOT/'institutional-ip'
spec=importlib.util.spec_from_file_location('mid',P/'master_ip_diligence.py'); M=importlib.util.module_from_spec(spec); sys.modules[spec.name]=M; spec.loader.exec_module(M)
bundle=json.loads((P/'master-ip-diligence-v3.bundle.json').read_text()); errors=M.validate_bundle(bundle)
required=[
 P/'agent/agent-contract.v1.json',P/'agent/subagents.v1.json',P/'contracts/evidence-envelope.v1.schema.json',P/'contracts/framework-factory-intake.v1.json',P/'contracts/chlom-rights-bridge.v1.json',P/'contracts/thriveevergreen-commerce-gate.v1.json',P/'contracts/repository-federation-evidence.v1.json',P/'contracts/vault-intake.v1.json',P/'integration/institutionalization-manifest.v1.json',P/'api/openapi.v1.yaml',P/'mcp/tools.v1.json'
]
for p in required:
 if not p.is_file(): errors.append('missing:'+str(p.relative_to(ROOT)))
for p in required:
 if p.suffix=='.json': json.loads(p.read_text())
sql=(ROOT/'supabase/migrations/20260822224500_institutional_ip_registry_and_integration_candidate.sql').read_text(); low=sql.lower()
if 'candidate_not_applied' not in low or re.search(r'create\s+policy',sql,re.I): errors.append('migration_policy_or_state_drift')
if 'revoke all on all tables in schema institutional_ip from public, anon, authenticated' not in low or 'grant select, insert, update, delete on all tables in schema institutional_ip to service_role' not in low: errors.append('service_only_grant_drift')
if 'create table if not exists institutional_ip.framework_factory_intakes' not in low or 'create table if not exists institutional_ip.chlom_rights_links' not in low or 'create table if not exists institutional_ip.thriveevergreen_gate_receipts' not in low: errors.append('integration_table_missing')
nav=json.loads((ROOT/'developers/manifests/institutional-ip-navigation-patch.v2.json').read_text())
if nav['state']!='CANDIDATE_NOT_APPLIED' or nav['direct_dashboard_write_allowed'] is not False or nav['requires_current_main_match']!='1e51c4b3962e56cca1d47bf0075a6cb683ada0fa': errors.append('navigation_drift')
workflow=(ROOT/'.github/workflows/institutional-ip-diligence-v3.yml').read_text()
if re.search(r'(?m)^\s*id-token:\s*write|^\s*(contents|pull-requests|packages|actions|security-events):\s*write',workflow): errors.append('workflow_authority_drift')
for digest in ['3d3c42e5aac5ba805825da76410c181273ba90b1','5fda3b95a4ea91299a34e894583c3862153e4b97']:
 if digest not in workflow: errors.append('workflow_pin_missing:'+digest)
if errors: print('\n'.join('FAIL: '+x for x in sorted(set(errors)))); raise SystemExit(1)
print(json.dumps({'status':'PASS','lifecycle':'PREPARED_NOT_ACTIVATED','five_systems':True,'wiring_contracts':7,'asset_families':20,'title_verified':0,'valued_assets':0,'paid_customers':0,'recognized_revenue':0,'database_migration_applied':False,'mintlify_navigation_applied':False,'ECAC_created':False,'sovereign_vote_created':False},sort_keys=True))
