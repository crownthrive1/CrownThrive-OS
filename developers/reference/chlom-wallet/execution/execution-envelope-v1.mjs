import { canonicalize, sha256Hex, assertAsciiIdentifier, secretShapePresent } from '../common/canonical-json.mjs';
import { evaluatePolicyIntent } from '../policy/chlom-wallet-policy-assurance-v2.mjs';
import { routeHandoffEvidence } from './handoff-evidence-router-v1.mjs';

const SEVERITY=Object.freeze({ ECAC:0, HOLD:1, DENY:2 });
function text(v,c,max=180){ return assertAsciiIdentifier(v,c,max); }
function obj(v,c){ if(!v||typeof v!=='object'||Array.isArray(v)) throw new Error(c); return v; }

export function compileExecutionProfiles(source, handoffRegistry) {
  const registry=obj(source,'execution_profile_registry_required');
  const profiles=new Map();
  if(!Array.isArray(registry.profiles)||registry.profiles.length===0) throw new Error('execution_profiles_missing');
  for(const p0 of registry.profiles){
    const p=obj(p0,'execution_profile_invalid');
    const skillId=text(p.skill_id,'execution_skill_id_invalid');
    if(profiles.has(skillId)) throw new Error(`duplicate_execution_profile:${skillId}`);
    const palletIds=[...new Set((p.pallet_ids??[]).map((x)=>text(x,'execution_pallet_id_invalid')))].sort();
    const actionTypes=[...new Set((p.action_types??[]).map((x)=>text(x,'execution_action_invalid',80)))].sort();
    const valueClasses=[...new Set((p.value_classes??[]).map((x)=>text(x,'execution_value_class_invalid',32)))].sort();
    const required=[...new Set((p.required_handoffs??[]).map((x)=>text(x,'required_handoff_invalid')))].sort();
    const pending=[...new Set((p.pending_role_aliases??[]).map((x)=>text(x,'pending_alias_invalid')))].sort();
    if(!palletIds.length||!actionTypes.length||!valueClasses.length||!required.length) throw new Error(`execution_profile_incomplete:${skillId}`);
    for(const id of required) if(!handoffRegistry.verified.has(id)) throw new Error(`profile_handoff_not_verified:${skillId}:${id}`);
    for(const alias of pending) if(!handoffRegistry.pending.has(alias)) throw new Error(`profile_pending_alias_unknown:${skillId}:${alias}`);
    profiles.set(skillId,Object.freeze({skill_id:skillId,pallet_ids:palletIds,action_types:actionTypes,value_classes:valueClasses,required_handoffs:required,pending_role_aliases:pending}));
  }
  const compiled={
    registry_id:text(registry.registry_id,'execution_registry_id_invalid'),
    semantic_version:text(registry.semantic_version,'execution_registry_version_invalid',32),
    state:text(registry.state,'execution_registry_state_invalid',48),
    canonical_agent_id:text(registry.canonical_agent_id,'execution_agent_id_invalid'),
    policy_rulepack_ref:text(registry.policy_rulepack_ref,'execution_rulepack_ref_invalid',220),
    authority:obj(registry.authority,'execution_authority_required'),
    profiles
  };
  if(compiled.authority.autonomy_ceiling!=='A2'||compiled.authority.decision_ceiling!=='D2'||compiled.authority.self_approval!==false||compiled.authority.ai_final_authority!==false) throw new Error('execution_authority_boundary_invalid');
  if(secretShapePresent([...profiles.values()])) throw new Error('execution_profile_secret_shape_detected');
  return Object.freeze(compiled);
}

function profileGuard(intent, profile) {
  const reasons=[]; let disposition='ECAC';
  if(!profile){ return {disposition:'DENY',reasons:['skill_execution_profile_missing']}; }
  if(!profile.action_types.includes(intent.action_type)){ disposition='DENY'; reasons.push('action_not_allowed_for_skill'); }
  if(!profile.value_classes.includes(intent.value_class)){ disposition='DENY'; reasons.push('value_class_not_allowed_for_skill'); }
  const requested=[...new Set(intent.pallet_ids ?? [])].sort();
  if(!requested.length){ disposition='DENY'; reasons.push('pallet_binding_required'); }
  for(const p of requested) if(!profile.pallet_ids.includes(p)){ disposition='DENY'; reasons.push(`pallet_not_allowed_for_skill:${p}`); }
  return {disposition,reasons};
}

function maxDisposition(...states){ return states.reduce((a,b)=>SEVERITY[b]>SEVERITY[a]?b:a,'ECAC'); }

export function compileExecutionEnvelope({intent, handoff_receipts=[]}, {profiles, handoffRegistry, compiledRulepack}) {
  const i=obj(intent,'execution_intent_required');
  const skillId=text(i.skill_id,'execution_skill_id_invalid');
  const profile=profiles.profiles.get(skillId);
  const profileResult=profileGuard(i,profile);
  let handoffResult;
  if(profile){
    handoffResult=routeHandoffEvidence({
      originator_agent_id:i.originator_agent_id,
      source_head_sha:i.source_head_sha,
      required_handoffs:profile.required_handoffs,
      pending_role_aliases:profile.pending_role_aliases,
      receipts:handoff_receipts
    },handoffRegistry);
  } else {
    handoffResult={route_state:'DENY',router_receipt_sha256:'0'.repeat(64),reasons:['skill_execution_profile_missing'],required_handoffs:[],pending_role_aliases:[],accepted_reviewers:[],missing_reviewers:[],stale_or_held_reviewers:[],denied_reviewers:[]};
  }

  const policyInput={...i}; delete policyInput.source_head_sha;
  const policyDecision=evaluatePolicyIntent(policyInput,compiledRulepack);
  const handoffDisposition=handoffResult.route_state==='SATISFIED'?'ECAC':handoffResult.route_state;
  const disposition=maxDisposition(profileResult.disposition,handoffDisposition,policyDecision.disposition);
  const reasons=[...new Set([...profileResult.reasons,...(handoffResult.reasons??[]),...policyDecision.reasons])].sort();
  const core={
    envelope_contract:'ct.contract.chlom-wallet.execution-envelope.v1',
    registry_id:profiles.registry_id,
    policy_rulepack_ref:compiledRulepack.rulepack_ref,
    intent_id:policyDecision.intent_id,
    correlation_id:policyDecision.correlation_id,
    subject_ref:policyDecision.subject_ref,
    skill_id:skillId,
    pallet_ids:[...(i.pallet_ids??[])].sort(),
    action_type:policyDecision.action_type,
    value_class:policyDecision.value_class,
    environment:policyDecision.environment,
    source_head_sha:text(i.source_head_sha,'execution_source_head_invalid',40),
    disposition,
    policy_disposition:policyDecision.disposition,
    handoff_state:handoffResult.route_state,
    profile_disposition:profileResult.disposition,
    reasons,
    policy_receipt_sha256:policyDecision.receipt_sha256,
    handoff_router_receipt_sha256:handoffResult.router_receipt_sha256,
    required_handoffs:profile?.required_handoffs ?? [],
    accepted_handoffs:handoffResult.accepted_reviewers ?? [],
    pending_role_aliases:profile?.pending_role_aliases ?? [],
    authority_granted:false,
    capability_grant_created:false,
    provider_write:false,
    money_movement:false,
    rights_grant:false,
    chain_broadcast:false,
    effective_price_publication:false,
    checkout_activation:false,
    phase_advancement:false,
    merge_authorized:false,
    ai_final_authority:false
  };
  if(secretShapePresent(core)) throw new Error('execution_envelope_secret_shape_detected');
  return Object.freeze({ ...core, execution_envelope_sha256:sha256Hex(canonicalize(core)) });
}
