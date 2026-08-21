#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'developers/manifests/agent-generation-6-priority-delegation.v1.json').read_text())

assert manifest['generation'] == 6
assert manifest['state'] == 'CONTROLLED_TEST_GOVERNED_HOLD'
assert manifest['sovereign_voters'] == [
    'ct.relay.agent-a','ct.relay.agent-b','ct.relay.agent-c','ct.relay.agent-d','ct.relay.agent-s'
]
assert manifest['required_approvals'] == 4
assert manifest['mandatory_voter'] == 'ct.relay.agent-d'
assert manifest['d3_human_reserved'] is True
assert manifest['no_delete'] is True
assert manifest['no_force_push'] is True
assert manifest['no_direct_main_write'] is True
assert manifest['agent_a_upgrade']['authority_ceiling'] == 'D2'
assert manifest['agent_a_upgrade']['hard_max_parallel_packets'] <= 6
assert manifest['agent_a_upgrade']['originator_verifier_separation'] is True

agents = manifest['internal_agents']
assert [a['agent_id'] for a in agents] == [f'ct.gen6.agent-{x}' for x in 'lmnop']
for agent in agents:
    assert agent['vote_eligible'] is False
    assert agent['scheduler_slot'] is False
    assert agent['authority_ceiling'] in {'D0','D1','D2'}

for forbidden in ('delete','force_push','direct_main_write','credential_mutation','money_movement','rights_grant','d3_execution','sovereign_vote_creation','self_approval'):
    assert forbidden in manifest['forbidden_capabilities']

algs = {a['algorithm_id']: a for a in manifest['algorithms']}
for aid in ('ct.alg.gen6.pdis','ct.alg.gen6.hrds','ct.alg.gen6.acbs','ct.alg.gen6.snrs'):
    assert aid in algs
    assert len(algs[aid]['public_contract_digest']) == 64
    assert algs[aid]['invocation_state'] == 'controlled_test'

assert manifest['cie']['may_score_people'] is False
assert manifest['cie']['may_create_vote'] is False
assert manifest['cie']['may_override_hard_block'] is False
assert manifest['skill_factory']['child_vote_inheritance'] is False
assert manifest['skill_factory']['commercial_activation'] is False
assert manifest['schedule_governance']['live_mutation_enabled'] is False
assert manifest['schedule_governance']['future_schedule_governor_requires_separate_constitutional_packet'] is True

print('Gen-6 manifest invariants: PASS')
