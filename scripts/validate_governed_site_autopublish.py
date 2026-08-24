#!/usr/bin/env python3
"""Fail-closed validator for CrownThrive governed release auto-publish."""
from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'developers/manifests/governed-site-autopublish.v1.json'
DOC=ROOT/'commerce/governed-release-autopublish.mdx'
AGENT=ROOT/'automation/governed-release-autopublisher-agent.mdx'
PHASE=ROOT/'standards/governed-release-autopublish-phase-amendment.mdx'
CHANGELOG=ROOT/'changelog/phase-2-99-governed-site-autopublish.mdx'
VALIDATOR=ROOT/'scripts/validate_governed_site_autopublish.py'
WORKFLOW=ROOT/'.github/workflows/governed-site-autopublish.yml'

def require(x,msg):
    if not x: raise SystemExit(f'ERROR: {msg}')

def main():
    m=json.loads(MANIFEST.read_text())
    p=m['policy']; a=m['publisher_agent']; d=m['catalog_projection']; c=m['canary']; f=m['product_factory']; rb=m['rollback']; cb=m['commerce_boundaries']; pa=m['persistent_automation']
    require(m['schema_version']=='1.0.0','schema version drift')
    require(m['stable_id']=='ct.manifest.governed-site-autopublish.v1','manifest stable ID drift')
    require(m['public_projection'] is True and m['private_runtime_topology_excluded'] is True,'public/private boundary missing')
    require(p['policy_id']=='ct.site.autopublish.v1','policy ID drift')
    require(p['auto_publish_if_release_pass'] is True,'release PASS must be the auto-publish gate')
    require(p['fail_closed'] is True,'auto-publish must fail closed')
    require(p['minimum_yes_votes']==4,'current constitution requires exactly four YES votes')
    require('ct.relay.agent-d' in p['required_vote_agents'],'independent gatekeeper Agent D must remain required')
    require(p['require_no_negative_votes'] is True,'negative vote blocker removed')
    require(p['allowed_sovereign_voter_ids']==['ct.relay.agent-a','ct.relay.agent-b','ct.relay.agent-c','ct.relay.agent-d','ct.relay.agent-s'],'sovereign voter set drift')
    require(p['synthetic_votes_count_toward_quorum'] is False,'synthetic votes may not satisfy quorum')
    require(p['test_fixture_vote_identities_must_be_non_sovereign'] is True,'test fixtures may not impersonate sovereign voters')
    require(p['require_repository_agent_oidc_binding'] is True,'repository/agent/OIDC vote binding removed')
    require(p['require_exact_version_hash'] is True,'exact version/hash binding removed')
    require(p['require_certified_destination'] is True,'destination certification removed')
    require(p['require_read_after_write'] is True,'read-after-write removed')
    require(p['require_rollback'] is True,'rollback removed')
    require(p['require_human_for_d3'] is True,'D3 human reservation removed')
    require(p['hold_unknown_action']=='quarantine','HOLD/UNKNOWN may not publish')
    require(a['agent_id']=='ct.subagent.governed-release-publisher','publisher identity drift')
    require(a['parent_agent_id']=='ct.agent.ecosystem-rollout-certifier','publisher parent drift')
    require(a['vote_eligible'] is False and a['self_certification_allowed'] is False and a['phase_advancement_allowed'] is False,'publisher authority widened')
    require(d['adapter_state']=='certified','catalog projection adapter certification missing')
    for k in ('read_capability_state','write_canary_state','rollback_canary_state','read_after_write_state'):
        require(d[k]=='pass',f'catalog projection {k} must remain PASS in this dated snapshot')
    require(d['committed_write_readback'] is True,'valid committed canary missing')
    require(c['quorum_acceptance']=='hold_pending_independent_vote_isolation','synthetic quorum canary must remain HOLD')
    for k in ('pre_adapter_quarantine','automatic_queue_after_adapter_certification','automatic_publish','hold_causes_automatic_withdrawal','pass_restoration_causes_republish','append_only_attempt_history'):
        require(c[k]=='pass',f'bounded technical canary proof missing: {k}')
    require(c['production_customer_impact'] is False,'synthetic canary may not claim production impact')
    sites=m['production_sites']; require(len(sites)==3,'three Sites-backed production surfaces must be explicit')
    for s in sites:
        require(s['consumer_bootstrap_state']=='pending','do not fabricate production consumer verification')
        require(s['provider_source_write_state']=='candidate','do not fabricate Sites source-write certification')
        require(s['automatic_production_publish'] is False,'production auto-publish must stay off before bootstrap verification')
    virality=next(s for s in sites if s['platform']=='Virality Music')
    require(virality['soundcloud_api']=='REMOVED_BY_FOUNDER_OVERRIDE','SoundCloud API founder override drift')
    require(f['downloadable_asset_projection'] and f['membership_catalog_digest_projection'] and f['generic_platform_release_registration'],'product factory automation incomplete')
    require(f['current_commercial_release_state']=='quarantined_hold','current products must remain HOLD in this snapshot')
    require(f['synthetic_pass_promotes_to_live_pass'] is False,'synthetic pass may not become live pass')
    require(all(pa[k] is True for k in ('publication_dispatch','vote_request_routing','adapter_recertification','storefront_bootstrap_verification')),'persistent automation lane missing')
    require(pa['exact_cadence_public'] is False,'private scheduler cadence leaked into public manifest')
    for k in ('authorization_loss_withdraws_projection','negative_vote_can_withdraw','hold_or_fail_can_withdraw','adapter_loss_disables_bounded_auto','consumer_verification_loss_disables_bounded_auto','supersession_preserves_prior_release'):
        require(rb[k] is True,f'rollback invariant removed: {k}')
    require(rb['prior_attempts_deleted'] is False,'publication evidence must remain append-only')
    require(cb['license_authority']=='CHLOM_THIVEBASE','license authority drift')
    require(cb['payment_provider_metadata_grants_license'] is False,'payment-provider metadata may not grant CrownThrive licenses')
    require(cb['store_credit_program_live'] is False,'Store Credits may not be represented live')
    require(cb['publication_equals_commerce_activation'] is False,'publication and commerce activation must stay separate')
    require(m['phase']['current']=='2.99' and m['phase']['phase_3']=='blocked','publication automation may not advance Phase 3')
    required={'publish_hold_unknown_pending_or_fail','originator_self_vote','fabricate_independent_votes','reuse_votes_after_exact_hash_change','catalog_projection_certification_equals_provider_source_write_certification','enable_production_surface_before_consumer_verification','publish_without_rollback_and_read_after_write','payment_provider_metadata_grants_license','synthetic_canary_represented_as_live_provider_proof','phase_3_advanced_by_publication_automation'}
    require(required.issubset(set(m['absolute_no_go'])),'absolute no-go rule removed')

    doc=DOC.read_text(); agent=AGENT.read_text(); phase=PHASE.read_text(); changelog=CHANGELOG.read_text(); manifest_text=MANIFEST.read_text(); validator_text=VALIDATOR.read_text(); workflow_text=WORKFLOW.read_text()
    for token in ('HOLD','UNKNOWN','rollback'):
        require(token in doc,f'documentation contract missing {token}')
    for token in ('ct.subagent.governed-release-publisher','Vote eligible: no','Rollback authority','Kill switches'):
        require(token in agent,f'agent contract missing {token}')
    for token in ('Phase 2.99','Phase 3','Phase 4','Phase 5','Phase 6','Phase 10','Phase 14','Phase 20','auto_publish_if_release_pass=true'):
        require(token in phase,f'phase amendment missing {token}')

    public_packet='\n'.join((doc,agent,phase,changelog,manifest_text,validator_text,workflow_text))
    # Build generic detectors from fragments so the validator does not publish the
    # exact private identifiers that it is responsible for rejecting.
    forbidden_patterns=(
        r'\\bappgprj' + r'_[a-z0-9_-]+\\b',
        r'https://[a-z]{20}\\.supabase\\.co',
        r'\\b(?:integration' + r'_control|developer_' + r'commerce)\\.[a-z][a-z0-9_]*\\b',
        r'\\bsite' + r'-catalog-feed\\b',
        r'\\bgoverned_(?:site|release|dynamic)[a-z0-9_]*(?:dispatcher|router|queue|verifier|canary)\\b',
    )
    for pattern in forbidden_patterns:
        require(not re.search(pattern,public_packet,re.IGNORECASE),f'public packet exposes restricted runtime topology class: {pattern}')
    require(not re.search(r'\*/\d+\s+\*\s+\*\s+\*\s+\*',public_packet),'public packet exposes private cron cadence')
    for cadence_phrase in ('every ' + 'two minutes','every ' + 'five minutes'):
        require(cadence_phrase not in public_packet.lower(),'public packet exposes private execution cadence')

    print('Governed site auto-publish contract: PASS')
    print('- release PASS + 4-of-5 quorum including D + certified destination required')
    print('- synthetic/test votes are non-authoritative and cannot satisfy quorum')
    print('- synthetic sovereign-identity quorum canary remains HOLD pending isolation')
    print('- HOLD/UNKNOWN remain quarantined')
    print('- catalog projection write/readback/rollback canary is proven')
    print('- production Sites consumer bootstrap remains pending; automatic publication remains off')
    print('- validator and workflow sources are included in public-topology leakage checks')
    print('- private runtime topology remains excluded from the public packet')
    print('- Phase 3 remains blocked')

if __name__=='__main__': main()
