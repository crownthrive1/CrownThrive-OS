#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JSON_PATHS=[
 'developers/manifests/cie-interoperability-control-plane.v2.json',
 'developers/manifests/chlom-cie-capability-binding.v1.json',
 'developers/manifests/framework-sequence-handoff.v1.json',
 'developers/manifests/cie-commercial-candidate-surfaces.v1.json',
 'developers/manifests/cie-retroactive-scan-contract.v1.json',
 'developers/templates/framework-child-federation-backlink.v1.json',
 'tests/fixtures/cie-interoperability-negative.v1.json',
 'developers/manifests/cie-parent-contract-manifest.v1.json',
]
def load(p):
 v=json.loads((ROOT/p).read_text(encoding='utf-8')); assert isinstance(v,dict),p; return v
for p in JSON_PATHS: load(p)
c=load(JSON_PATHS[0]); b=load(JSON_PATHS[1]); s=load(JSON_PATHS[2]); o=load(JSON_PATHS[3]); r=load(JSON_PATHS[4]); t=load(JSON_PATHS[5])
assert c['canonical_parent']['main_sha_at_reconciliation']=='c7f14b73cff09f00a8f94f15a8587289de18ff7b'
assert c['child']['candidate_head']=='6b4db00c49e3b988e664a7e1944cb77e0f064054'
assert c['child']['candidate_pr']==1 and c['child']['github_repository_id']==1341314455
assert c['child']['repository_federation_state']=='PROVISIONED_UNLINKED'
assert c['child']['operationally_enabled'] is False and c['child']['vote_eligible'] is False
assert c['constitution']['agent_d_mandatory'] is True and c['constitution']['d3_human_reserved'] is True
assert c['protected_algorithm_boundary']['algorithm_public_contract_digest']=='e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2'
assert c['protected_algorithm_boundary']['capability_digest']=='d6955a7bb0ebecdc5cd45e458af4ccb0ad911ef52e0a0634426d5199b1a89b42'
assert c['protected_algorithm_boundary']['public_contract_bundle_digest']=='12f45147dd6298ce68f28bf8e1f73e029f2711b23822c632976e316fcf08525f'
assert c['protected_algorithm_boundary']['protected_body_in_public_repository'] is False
assert all(x['parent_agent_voting'] is False for x in [c['agent_machine']])
assert all(x['voting'] is False for x in c['agent_machine']['subagents'])
assert b['candidate_additions']==['ct.framework-agent.cie','ct.subagent.cie-interoperability']
assert b['live_dispatch_enabled'] is False and b['body_exposure_allowed'] is False and b['requires_independent_verifier'] is True
assert s['frameworks'][1]['state']=='RESEARCH_CANDIDATE_ONLY' and s['frameworks'][1]['implementation_allowed'] is False
assert o['exact_price_authorized'] is False and o['stripe_objects_created'] is False and o['checkout_enabled'] is False and o['customer_entitlement_active'] is False
assert r['writes_allowed'] is False and r['automatic_certification'] is False and r['automatic_provider_mutation'] is False
assert t['fixed_invariants']['transport_identity_can_vote'] is False and t['fixed_invariants']['child_self_activation'] is False
sql=(ROOT/'supabase/cie-interoperability-registry-reconciliation-v2.sql').read_text(encoding='utf-8')
for needle in ['begin;','commit;','HOLD:capability_digest_or_safety_invariant_drift','live_dispatch_enabled',"'ct.framework-agent.cie'","'ct.subagent.cie-interoperability'",'MANUAL ROLLBACK']:
 assert needle in sql,needle
all_text='\n'.join(p.read_text(encoding='utf-8',errors='ignore') for p in ROOT.rglob('*') if p.is_file())
for pattern in [r'sk-[A-Za-z0-9_-]{16,}',r'(?i)(api[_-]?key|client[_-]?secret|password)\s*[:=]\s*["\']?[A-Za-z0-9_./+-]{12,}',r'(?i)private[_-]?(weight|calibration)\s*[:=]\s*[-+]?\d']:
 assert not re.search(pattern,all_text),pattern
contract=load('developers/manifests/cie-parent-contract-manifest.v1.json')
acc=bytearray()
for entry in contract['files']:
 actual=hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest(); assert actual==entry['sha256'],entry['path']
 acc.extend(entry['path'].encode());acc.extend(b'\0');acc.extend(actual.encode());acc.extend(b'\n')
assert hashlib.sha256(bytes(acc)).hexdigest()==contract['bundle_digest']
print(json.dumps({'ok':True,'checks':34,'bundle_digest':contract['bundle_digest']},sort_keys=True))
