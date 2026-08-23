import fs from 'node:fs';
import { compileRulepack, evaluatePolicyIntent } from './chlom-wallet-policy-assurance-v2.mjs';
import { applyAiCounselFirewall } from './ai-counsel-firewall-v1.mjs';
const rulepack=compileRulepack(JSON.parse(fs.readFileSync(new URL('./policy-rulepack.v2.json',import.meta.url),'utf8')));
let state=0x6d2b79f5; const rnd=()=>{ state=(Math.imul(state^state>>>15,1|state)+0x6d2b79f5)|0; let t=Math.imul(state^state>>>7,61|state)^state; return ((t^t>>>14)>>>0)/4294967296; };
const pick=(a)=>a[Math.floor(rnd()*a.length)];
const actions=['READ_ONLY','CONTROLLED_TEST_COMPUTE','DRY_RUN_PACKAGE','EVIDENCE_VERIFY','LOCAL_EVM_TEST','SANITIZED_PUBLIC_PROJECTION','PROVIDER_WRITE','MONEY_MOVEMENT','RIGHTS_GRANT','CHAIN_BROADCAST','EFFECTIVE_PRICE_PUBLICATION','CHECKOUT_ACTIVATION','PHASE_ADVANCEMENT','MERGE_AUTHORIZATION','CUSTODY','TOKEN_ISSUANCE','PRODUCTION_ACTIVATION','UNKNOWN_ACTION'];
const values=['Money','Rights','Rewards','Impact','Proof','Mixed','Unknown'];
const envs=['local','ci','controlled_test','sandbox','production','unknown'];
let ecac=0,hold=0,deny=0,aiAttempts=0,invariantFailures=0;
const cases=50000;
for(let i=0;i<cases;i++){
 const action=pick(actions); const requested={}; if(rnd()<0.08) requested.money_movement=true; if(rnd()<0.05) requested.chain_broadcast=true; if(rnd()<0.05) requested.production_rights_grant=true; if(rnd()<0.03) requested.effective_price_publication=true;
 const input={schema_version:'2.0.0',intent_id:`ct.intent.chaos.${i}`,correlation_id:`ct.corr.chaos.${i}`,subject_ref:'ct.wallet.chaos',originator_agent_id:'ct.agent.chlom-wallet-settlement',reviewer_agent_id:rnd()<0.07?'ct.agent.chlom-wallet-settlement':'ct.agent.qa-security',action_type:action,value_class:pick(values),environment:pick(envs),skill_id:'ct.skill.chlom-wallet.security-threat-model.v1',pallet_ids:['ct.pallet.chlom-wallet-enterprise-control-plane.v1'],authority:{autonomy_level:pick(['A0','A1','A2','A3']),decision_level:pick(['D0','D1','D2','D3']),exact_head_verified:rnd()>0.1,heartbeat_fresh:rnd()>0.15,pending_alias_dependency:rnd()<0.07},evidence:{source_fresh:rnd()>0.1,rollback_ready:rnd()>0.12,security_review:rnd()>0.25,rights_review:rnd()>0.25,finance_review:rnd()>0.25,recovery_review:rnd()>0.25},requested_effects:requested};
 const d=evaluatePolicyIntent(input,rulepack); if(d.disposition==='ECAC') ecac++; else if(d.disposition==='HOLD') hold++; else deny++;
 const boundary=rulepack.hard_deny_actions.includes(action)||rulepack.controlled_test_boundary_actions.includes(action)||Object.values(requested).some(Boolean)||input.environment==='production'||input.authority.autonomy_level==='A3'||input.authority.decision_level==='D3'||input.authority.pending_alias_dependency||input.originator_agent_id===input.reviewer_agent_id;
 if(boundary && d.disposition==='ECAC') invariantFailures++;
 if(rnd()<0.2){ aiAttempts++; const ai=applyAiCounselFirewall(d,{advisory_id:`ct.ai.chaos.${i}`,model_ref:'ct.model.synthetic-advisory',proposed_disposition:'ECAC',rationale:'Synthetic adversarial upgrade attempt.',signals:['chaos','upgrade_attempt']}); if(ai.effective_disposition!==d.disposition||ai.accepted_as_final) invariantFailures++; }
}
if(invariantFailures) throw new Error(`policy_chaos_invariant_failures:${invariantFailures}`);
console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_POLICY_CHAOS_V2',cases,ecac,hold,deny,ai_advisory_attempts:aiAttempts,invariant_failures:invariantFailures,production_activation:false,provider_write:false,custody:false,token_issuance:false,money_movement:false,production_rights_grant:false,chain_broadcast:false,effective_price_publication:false,checkout_activation:false,phase_advancement:false,merge_authorized:false,ai_final_authority:false}));
