import fs from 'node:fs';
import { sha256Hex } from '../common/canonical-json.mjs';
import { compileRulepack } from '../policy/chlom-wallet-policy-assurance-v2.mjs';
import { compileHandoffRegistry } from './handoff-evidence-router-v1.mjs';
import { compileExecutionProfiles, compileExecutionEnvelope } from './execution-envelope-v1.mjs';
const parse=(u)=>JSON.parse(fs.readFileSync(new URL(u,import.meta.url),'utf8'));
const handoffRegistry=compileHandoffRegistry(parse('../../../../automation/chlom-wallet-agent-handoff-crosswalk.v1.json'));
const profiles=compileExecutionProfiles(parse('./execution-envelope-profiles.v1.json'),handoffRegistry);
const compiledRulepack=compileRulepack(parse('../policy/policy-rulepack.v2.json'));
const ctx={profiles,handoffRegistry,compiledRulepack};
const profileList=[...profiles.profiles.values()];
const HEAD='c'.repeat(40);
let seed=0x29f4a7c1; const rnd=()=>{ seed=(Math.imul(seed^seed>>>15,1|seed)+0x6d2b79f5)|0; let t=Math.imul(seed^seed>>>7,61|seed)^seed; return ((t^t>>>14)>>>0)/4294967296; }; const pick=(a)=>a[Math.floor(rnd()*a.length)];
function receiptsFor(profile,i){ return profile.required_handoffs.map((id)=>{const b=handoffRegistry.verified.get(id);return {receipt_id:`ct.receipt.chaos.${i}.${id}`,reviewer_agent_id:id,role:b.role,scope:`execution_chaos:${profile.skill_id}`,source_head_sha:HEAD,heartbeat_fresh:true,independent:true,decision:'PASS',receipt_sha256:sha256Hex(`receipt:${i}:${id}`)};}); }
function intentFor(profile,i){ return {schema_version:'2.0.0',intent_id:`ct.intent.exec-chaos.${i}`,correlation_id:`ct.corr.exec-chaos.${i}`,subject_ref:'ct.wallet.execution-chaos',originator_agent_id:'ct.agent.chlom-wallet-settlement',reviewer_agent_id:'ct.agent.qa-security',action_type:profile.action_types[0],value_class:profile.value_classes[0],environment:'controlled_test',skill_id:profile.skill_id,pallet_ids:[profile.pallet_ids[0]],source_head_sha:HEAD,authority:{autonomy_level:'A2',decision_level:'D2',exact_head_verified:true,heartbeat_fresh:true,pending_alias_dependency:false},evidence:{source_fresh:true,rollback_ready:true,security_review:true,rights_review:true,finance_review:true,recovery_review:true},requested_effects:{}}; }
const mutations=['missing_receipt','stale_head','stale_heartbeat','handoff_hold','handoff_deny','wrong_pallet','wrong_action','wrong_value','A3','D3','production','money_effect','self_handoff','source_stale','rollback_missing','pending_alias'];
let cases=30000,ecac=0,hold=0,deny=0,invariantFailures=0;
for(let i=0;i<cases;i++){
  const profile=pick(profileList); let intent=intentFor(profile,i); let receipts=receiptsFor(profile,i); const mutation=pick(mutations);
  const first=receipts[0];
  if(mutation==='missing_receipt') receipts=receipts.slice(1);
  else if(mutation==='stale_head') receipts=receipts.map((r,j)=>j? r:{...r,source_head_sha:'d'.repeat(40)});
  else if(mutation==='stale_heartbeat') receipts=receipts.map((r,j)=>j? r:{...r,heartbeat_fresh:false});
  else if(mutation==='handoff_hold') receipts=receipts.map((r,j)=>j? r:{...r,decision:'HOLD'});
  else if(mutation==='handoff_deny') receipts=receipts.map((r,j)=>j? r:{...r,decision:'DENY'});
  else if(mutation==='wrong_pallet') intent={...intent,pallet_ids:['ct.pallet.invalid-chaos.v1']};
  else if(mutation==='wrong_action') intent={...intent,action_type:'MERGE_AUTHORIZATION'};
  else if(mutation==='wrong_value') intent={...intent,value_class:'Unknown'};
  else if(mutation==='A3') intent={...intent,authority:{...intent.authority,autonomy_level:'A3'}};
  else if(mutation==='D3') intent={...intent,authority:{...intent.authority,decision_level:'D3'}};
  else if(mutation==='production') intent={...intent,environment:'production'};
  else if(mutation==='money_effect') intent={...intent,requested_effects:{money_movement:true}};
  else if(mutation==='self_handoff') intent={...intent,originator_agent_id:first.reviewer_agent_id};
  else if(mutation==='source_stale') intent={...intent,evidence:{...intent.evidence,source_fresh:false}};
  else if(mutation==='rollback_missing') intent={...intent,evidence:{...intent.evidence,rollback_ready:false}};
  else if(mutation==='pending_alias') {
    if(profile.pending_role_aliases.length){ const alias=profile.pending_role_aliases[0]; receipts=[...receipts,{receipt_id:`ct.receipt.chaos.alias.${i}`,reviewer_agent_id:alias,role:'pending_alias',scope:'execution_chaos',source_head_sha:HEAD,heartbeat_fresh:true,independent:true,decision:'PASS',receipt_sha256:sha256Hex(`alias:${i}`)}]; }
    else receipts=receipts.slice(1);
  }
  const result=compileExecutionEnvelope({intent,handoff_receipts:receipts},ctx);
  if(result.disposition==='ECAC'){ ecac++; invariantFailures++; }
  else if(result.disposition==='HOLD') hold++; else deny++;
}
if(invariantFailures) throw new Error(`execution_envelope_chaos_invariant_failure:${invariantFailures}`);
console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_EXECUTION_ENVELOPE_CHAOS_V1',cases,ecac,hold,deny,invariant_failures:invariantFailures,authority_granted:false,capability_grant_created:false,provider_write:false,money_movement:false,rights_grant:false,chain_broadcast:false,effective_price_publication:false,checkout_activation:false,phase_advancement:false,merge_authorized:false}));
