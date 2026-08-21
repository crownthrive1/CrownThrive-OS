#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'developers/manifests/agent-generation-6-priority-delegation.v1.json').read_text())

assert manifest['generation'] == 6
assert manifest['state'] == 'CONTROLLED_TEST_EMERGENCY_PATCH_GOVERNED_PRODUCTION_HOLD'
assert manifest['sovereign_voters'] == [
    'ct.relay.agent-a','ct.relay.agent-b','ct.relay.agent-c','ct.relay.agent-d','ct.relay.agent-s'
]
assert manifest['required_approvals'] == 4
assert manifest['mandatory_voter'] == 'ct.relay.agent-d'
assert manifest['d3_human_reserved'] is True
assert manifest['no_delete'] is True
assert manifest['no_force_push'] is True
assert manifest['no_direct_main_write'] is True

patch = manifest['emergency_patch']
assert patch['signer_name'] == 'Kavonte Jones'
assert patch['signature_role'] == 'Founder Override'
assert patch['signature_type'] == 'typed_name_attestation'
assert patch['cryptographic_nonrepudiation'] is False
assert patch['statement_fingerprint_id'].startswith('ctfp:v1:sha256:')
assert patch['professional_and_unrelated_d3_boundaries_preserved'] is True

agent_a = manifest['agent_a_upgrade']
assert agent_a['authority_ceiling'] == 'D2'
assert agent_a['default_max_parallel_packets'] == 4
assert agent_a['hard_max_parallel_packets'] <= 6
assert agent_a['active_scheduler_contract'] == 'portfolio_wip_4'
assert agent_a['old_single_packet_rule'].startswith('superseded')
assert agent_a['originator_verifier_separation'] is True
assert agent_a['live_schedule_mutation'] is False

runtime = manifest['agentic_runtime']
assert runtime['update_mode'] == 'agentic_controlled_test'
assert runtime['self_assessment_required'] is True
assert runtime['bounded_self_healing'] is True
assert runtime['multidimensional_execution'] is True
assert runtime['adaptive_replanning'] is True
assert runtime['no_gate_weakening'] is True
assert runtime['no_authority_creation'] is True
assert runtime['no_self_certification'] is True

agents = manifest['internal_agents']
assert [a['agent_id'] for a in agents] == [f'ct.gen6.agent-{x}' for x in 'lmnop']
for agent in agents:
    assert agent['vote_eligible'] is False
    assert agent['scheduler_slot'] is False
    assert agent['authority_ceiling'] in {'D0','D1','D2'}
    assert agent['self_healing'] is True

for forbidden in ('delete','force_push','direct_main_write','credential_mutation','money_movement','rights_grant','d3_execution','sovereign_vote_creation','self_approval','gate_weakening'):
    assert forbidden in manifest['forbidden_capabilities']

algs = {a['algorithm_id']: a for a in manifest['algorithms']}
for aid in ('ct.alg.gen6.pdis','ct.alg.gen6.hrds','ct.alg.gen6.acbs','ct.alg.gen6.snrs'):
    assert aid in algs
    assert len(algs[aid]['public_contract_digest']) == 64
    assert algs[aid]['implementation'] == 'RESTRICTED_INSTITUTIONAL'
    assert algs[aid]['invocation_state'] == 'controlled_test'
    assert algs[aid]['continuity_state'] == 'BOUND_CONTROLLED_TEST_N_S_PRODUCTION_VERIFICATION_PENDING'

bundle = manifest['protected_bundle']
assert bundle['state'] == 'bound_controlled_test'
assert len(bundle['public_digest_sha256']) == 64
assert bundle['body_public'] is False
assert bundle['production_requires_independent_n_s_verification'] is True

telemetry = manifest['telemetry']
assert telemetry['packet_lifecycle'][:5] == ['planned','running','verifying','done','blocked']
assert telemetry['first_class_agent_heartbeat'] is True
assert telemetry['original_pdis_targets'] == 5
assert telemetry['canary']['state'] == 'PASS'
assert telemetry['canary']['owner'] != telemetry['canary']['verifier']
assert telemetry['canary']['excluded_from_live_throughput'] is True

oracle = manifest['oracle_adjudication']
assert oracle['state'] == 'test'
assert oracle['sovereign'] is False
assert oracle['max_rounds'] == 2
assert oracle['d2_requires_independent_governed_resolution'] is True
assert oracle['d3_human_reserved'] is True
assert oracle['qualified_professional_boundary'] is True
assert oracle['first_disposition']['state'] == 'resolved_auto'
assert oracle['first_disposition']['authority_class'] == 'D1'
assert oracle['first_disposition']['disagreement'] == 0

assert manifest['test_surface']['exposes_proprietary_weights'] is False
assert manifest['test_surface']['exposes_vault_content'] is False
assert manifest['test_surface']['exposes_credentials'] is False
assert manifest['test_surface']['mutation_authority'] is False

assert manifest['cie']['may_score_people'] is False
assert manifest['cie']['may_create_vote'] is False
assert manifest['cie']['may_override_hard_block'] is False
assert manifest['skill_factory']['child_vote_inheritance'] is False
assert manifest['skill_factory']['commercial_activation'] is False
assert manifest['schedule_governance']['live_mutation_enabled'] is False
assert manifest['schedule_governance']['future_schedule_governor_requires_separate_constitutional_packet'] is True
assert manifest['dail_post_patch']['failure_count'] == 0
assert manifest['dail_post_patch']['checked_events'] >= 90

print('Gen-6 emergency patch manifest invariants: PASS')
