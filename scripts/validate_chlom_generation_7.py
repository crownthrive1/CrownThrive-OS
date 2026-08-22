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
assert m['local_monthly_request_budget_semantics']['-1']=='unlimited_local_ceiling'
assert m['local_monthly_request_budget_semantics']['0']=='disabled'
assert m['local_monthly_request_budget_semantics']['provider_throttles_and_billing_still_apply'] is True
assert len(m['algorithms'])==6
assert all(a['implementation']=='RESTRICTED_VAULT' for a in m['algorithms'])
assert any(a['id']=='ct.alg.gen7.gds' and a.get('d3_auto') is False for a in m['algorithms'])
assert [a['id'] for a in m['support_agents']]==['ct.gen7.agent-q','ct.gen7.agent-r','ct.gen7.agent-t']
assert all(not a['vote_eligible'] and not a['scheduler_slot'] and a['authority_ceiling']=='D2' for a in m['support_agents'])
assert m['commercialization']['checkout_enabled'] is False
assert m['commercialization']['stripe_objects_created'] is False
assert m['commercialization']['protected_kernel_transfer'] is False
assert m['identity']['provisional_did_is_not_public_chain_proof'] is True
print('CHLOM Generation 7 manifest invariants: PASS')
