#!/usr/bin/env python3
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
m=json.loads((root/'developers/manifests/chlom-generation-7.v1.json').read_text())
assert m['generation']==7
assert m['state']=='CONTROLLED_TEST_GOVERNED_HOLD'
assert m['phase']=='2.99' and m['phase_3_advanced'] is False
assert m['sovereign_voters']==['ct.relay.agent-a','ct.relay.agent-b','ct.relay.agent-c','ct.relay.agent-d','ct.relay.agent-s']
assert m['required_approvals']==4 and m['mandatory_voter']=='ct.relay.agent-d'
assert m['d3_human_reserved'] is True and m['no_silent_delete'] is True
assert m['runtime_snapshot']['protected_assets']>=101
assert m['runtime_snapshot']['registered_algorithms']>=37
assert m['runtime_snapshot']['gen7_algorithms']==17
assert m['runtime_snapshot']['gen7_support_agents']==12
assert m['runtime_snapshot']['private_identity_mappings']>=6
assert m['runtime_snapshot']['archive_revision']>=7
assert m['local_monthly_request_budget_semantics']['-1']=='unlimited_local_ceiling'
assert m['local_monthly_request_budget_semantics']['0']=='disabled'
assert m['local_monthly_request_budget_semantics']['provider_throttles_and_billing_still_apply'] is True
assert len(m['algorithms'])==17
assert all(a['implementation']=='RESTRICTED_VAULT' for a in m['algorithms'])
assert any(a['id']=='ct.alg.gen7.gds' and a.get('d3_auto') is False for a in m['algorithms'])
assert any(a['id']=='ct.alg.gen7.pcas' and a.get('auto_stop') is False for a in m['algorithms'])
assert any(a['id']=='ct.alg.gen7.tis' and a.get('person_scoring') is False for a in m['algorithms'])
expected_agents=['ct.gen7.agent-q','ct.gen7.agent-r','ct.gen7.agent-t','ct.gen7.agent-u','ct.gen7.agent-v','ct.gen7.agent-w','ct.gen7.agent-x','ct.gen7.agent-y','ct.gen7.agent-z','ct.gen7.agent-red','ct.gen7.agent-blue','ct.gen7.agent-purple']
assert [a['id'] for a in m['support_agents']]==expected_agents
assert all(not a['vote_eligible'] and a['authority_ceiling'] in ('D1','D2') for a in m['support_agents'])
assert m['security_lab']['external_network'] is False
assert m['security_lab']['production_writes'] is False
assert m['security_lab']['public_vulnerability_detail'] is False
assert m['security_lab']['originator_self_verification'] is False
assert m['security_lab']['invariant_heartbeat']=='every_6_hours'
assert m['adserver_billing']['hard_usage_cap'] is False
assert m['adserver_billing']['allow_overage'] is True
assert m['adserver_billing']['local_auto_stop'] is False
assert m['mailgun']['account_api_read_verified'] is True
assert m['mailgun']['sending_key_state']=='internal_canary_passed_and_delivered'
assert m['mailgun']['write_scope']=='internal_allowlist_only'
assert m['mailgun']['raw_credentials_public'] is False
assert m['crownlytics_ingest']['provider_dispatch_default'] is False
assert m['crownlytics_ingest']['restricted_staging'] is True
assert m['crownlytics_ingest']['scoring_composition']==['ct.alg.gen7.eqs','ct.alg.gen7.dps']
assert m['commercialization']['checkout_enabled'] is False
assert m['commercialization']['stripe_objects_created'] is False
assert m['commercialization']['protected_kernel_transfer'] is False
assert m['identity']['provisional_did_is_not_public_chain_proof'] is True
print('CHLOM Generation 7 manifest invariants: PASS')
