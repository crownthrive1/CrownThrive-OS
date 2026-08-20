#!/usr/bin/env python3
"""Fail-closed validator for CrownThrive governed release auto-publish."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'developers/manifests/governed-site-autopublish.v1.json'
DOC=ROOT/'commerce/governed-release-autopublish.mdx'
AGENT=ROOT/'automation/governed-release-autopublisher-agent.mdx'
PHASE=ROOT/'standards/governed-release-autopublish-phase-amendment.mdx'

def require(x,msg):
    if not x: raise SystemExit(f'ERROR: {msg}')

def main():
    m=json.loads(MANIFEST.read_text())
    p=m['policy']; a=m['publisher_agent']; d=m['dynamic_feed']; c=m['canary']; f=m['product_factory']; rb=m['rollback']; cb=m['commerce_boundaries']
    require(m['schema_version']=='1.0.0','schema version drift')
    require(m['stable_id']=='ct.manifest.governed-site-autopublish.v1','manifest stable ID drift')
    require(p['policy_id']=='ct.site.autopublish.v1','policy ID drift')
    require(p['auto_publish_if_release_pass'] is True,'release PASS must be the auto-publish gate')
    require(p['fail_closed'] is True,'auto-publish must fail closed')
    require(p['minimum_yes_votes']>=3,'quorum must require at least three YES votes')
    require('ct.relay.agent-d' in p['required_vote_agents'],'independent gatekeeper Agent D must remain required')
    require(p['require_no_negative_votes'] is True,'negative vote blocker removed')
    require(p['require_exact_version_hash'] is True,'exact version/hash binding removed')
    require(p['require_certified_destination'] is True,'destination certification removed')
    require(p['require_read_after_write'] is True,'read-after-write removed')
    require(p['require_rollback'] is True,'rollback removed')
    require(p['require_human_for_d3'] is True,'D3 human reservation removed')
    require(p['hold_unknown_action']=='quarantine','HOLD/UNKNOWN may not publish')
    require(a['agent_id']=='ct.subagent.governed-release-publisher','publisher identity drift')
    require(a['parent_agent_id']=='ct.agent.ecosystem-rollout-certifier','publisher parent drift')
    require(a['vote_eligible'] is False,'publisher may not vote')
    require(a['self_certification_allowed'] is False,'publisher may not self-certify')
    require(a['phase_advancement_allowed'] is False,'publisher may not advance phases')
    require(d['adapter_id']=='ct.adapter.dynamic-feed.v1' and d['adapter_state']=='certified','dynamic feed certification snapshot missing')
    for k in ('read_capability_state','write_canary_state','rollback_canary_state','read_after_write_state'):
        require(d[k]=='pass',f'dynamic feed {k} must remain PASS in this dated snapshot')
    require(d['committed_write_readback'] is True and d['cache_busted_canary'] is True,'valid provider-visible feed canary missing')
    for k in ('quorum_acceptance','pre_adapter_quarantine','automatic_queue_after_adapter_certification','automatic_publish','hold_causes_automatic_withdrawal','pass_restoration_causes_republish','append_only_attempt_history'):
        require(c[k]=='pass',f'canary proof missing: {k}')
    require(c['production_customer_impact'] is False,'synthetic canary must not claim production impact')
    sites=m['production_sites']; require(len(sites)==3,'three Sites-backed production surfaces must be explicit')
    for s in sites:
        require(s['feed_consumer_state']=='pending','do not fabricate production feed-consumer verification')
        require(s['provider_mutation_adapter_state']=='candidate','do not fabricate Sites source-write certification')
        require(s['auto_update_enabled'] is False,'production auto-update must stay off before bootstrap verification')
    virality=next(s for s in sites if s['surface_id']=='ct.surface.virality-music.production')
    require(virality['soundcloud_api']=='REMOVED_BY_FOUNDER_OVERRIDE','SoundCloud API founder override drift')
    require(f['downloadable_asset_trigger'] and f['membership_catalog_digest_trigger'] and f['generic_platform_release_registration_rpc'],'product factory automation incomplete')
    require(f['developer_marketplace_seeded_releases']==7,'developer release seed count drift')
    require(f['developer_marketplace_current_release_state']=='quarantined_hold','current products must remain HOLD in this snapshot')
    require(f['synthetic_pass_promotes_to_live_pass'] is False,'synthetic pass may not become live pass')
    expected_jobs={'governed_site_autopublish_dispatcher':'*/2 * * * *','governed_release_vote_router':'*/5 * * * *','governed_dynamic_feed_adapter_canary':'57 * * * *','governed_site_feed_bootstrap_verifier':'7 * * * *'}
    require({x['job']:x['schedule'] for x in m['schedules']}==expected_jobs,'scheduler contract drift')
    for k in ('authorization_loss_withdraws_projection','negative_vote_can_withdraw','hold_or_fail_can_withdraw','adapter_loss_disables_bounded_auto','consumer_verification_loss_disables_bounded_auto','supersession_preserves_prior_release'):
        require(rb[k] is True,f'rollback invariant removed: {k}')
    require(rb['prior_attempts_deleted'] is False,'publication evidence must remain append-only')
    require(cb['license_authority']=='CHLOM_THIVEBASE','license authority drift')
    require(cb['stripe_metadata_grants_license'] is False,'Stripe metadata may not grant CrownThrive licenses')
    require(cb['store_credit_program_live'] is False,'Store Credits may not be represented live in this snapshot')
    require(cb['publication_equals_commerce_activation'] is False,'publication and commerce activation must stay separate')
    require(m['phase']['current']=='2.99' and m['phase']['phase_3']=='blocked','publication automation may not advance Phase 3')
    nogo=set(m['absolute_no_go'])
    required={'publish_hold_unknown_pending_or_fail','originator_self_vote','fabricate_independent_votes','reuse_votes_after_exact_hash_change','dynamic_feed_certification_equals_provider_source_write_certification','enable_production_surface_before_feed_consumer_verification','publish_without_rollback_and_read_after_write','payment_provider_metadata_grants_license','synthetic_canary_represented_as_live_provider_proof','phase_3_advanced_by_publication_automation'}
    require(required.issubset(nogo),'absolute no-go rule removed')
    doc=DOC.read_text(); agent=AGENT.read_text(); phase=PHASE.read_text()
    for token in ('ct.site.autopublish.v1','HOLD','UNKNOWN','ct.relay.agent-d','dynamic','rollback','Phase 3'):
        require(token in doc,f'documentation contract missing {token}')
    for token in ('ct.subagent.governed-release-publisher','Vote eligible: no','Rollback authority','Kill switches'):
        require(token in agent,f'agent contract missing {token}')
    for token in ('Phase 2.99','Phase 3','Phase 4','Phase 5','Phase 6','Phase 10','Phase 14','Phase 20','auto_publish_if_release_pass=true'):
        require(token in phase,f'phase amendment missing {token}')
    print('Governed site auto-publish contract: PASS')
    print('- release PASS + quorum + certified destination required')
    print('- HOLD/UNKNOWN remain quarantined')
    print('- dynamic-feed adapter canary and rollback are proven')
    print('- production Sites bootstrap remains pending; auto-update remains off')
    print('- Phase 3 remains blocked')

if __name__=='__main__': main()
