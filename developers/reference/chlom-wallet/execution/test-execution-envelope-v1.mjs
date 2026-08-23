import fs from 'node:fs';
import { sha256Hex } from '../common/canonical-json.mjs';
import { compileRulepack } from '../policy/chlom-wallet-policy-assurance-v2.mjs';
import { compileHandoffRegistry } from './handoff-evidence-router-v1.mjs';
import { compileExecutionProfiles, compileExecutionEnvelope } from './execution-envelope-v1.mjs';

const parse=(u)=>JSON.parse(fs.readFileSync(new URL(u,import.meta.url),'utf8'));
const crosswalk=parse('../../../../automation/chlom-wallet-agent-handoff-crosswalk.v1.json');
const profileSource=parse('./execution-envelope-profiles.v1.json');
const rulepack=compileRulepack(parse('../policy/policy-rulepack.v2.json'));
const handoffRegistry=compileHandoffRegistry(crosswalk);
const profiles=compileExecutionProfiles(profileSource,handoffRegistry);
const HEAD='a'.repeat(40);

function receiptsFor(profile,{stale=null,decision=null}={}){
  return profile.required_handoffs.map((id)=>{
    const binding=handoffRegistry.verified.get(id);
    return {receipt_id:`ct.receipt.test.${id}`,reviewer_agent_id:id,role:binding.role,scope:`controlled_test_review:${profile.skill_id}`,source_head_sha:stale===id?'b'.repeat(40):HEAD,heartbeat_fresh:true,independent:true,decision:decision?.id===id?decision.value:'PASS',receipt_sha256:sha256Hex(`receipt:${profile.skill_id}:${id}:${stale===id?'stale':'fresh'}:${decision?.id===id?decision.value:'PASS'}`)};
  });
}
function baseIntent(profile,index=0){ return {schema_version:'2.0.0',intent_id:`ct.intent.envelope.${index}`,correlation_id:`ct.corr.envelope.${index}`,subject_ref:'ct.wallet.execution-envelope',originator_agent_id:'ct.agent.chlom-wallet-settlement',reviewer_agent_id:'ct.agent.qa-security',action_type:profile.action_types[0],value_class:profile.value_classes[0],environment:'controlled_test',skill_id:profile.skill_id,pallet_ids:[profile.pallet_ids[0]],source_head_sha:HEAD,authority:{autonomy_level:'A2',decision_level:'D2',exact_head_verified:true,heartbeat_fresh:true,pending_alias_dependency:false},evidence:{source_fresh:true,rollback_ready:true,security_review:true,rights_review:true,finance_review:true,recovery_review:true},requested_effects:{}}; }
const ctx={profiles,handoffRegistry,compiledRulepack:rulepack};
let valid=0;
for(const [skillId,profile] of profiles.profiles.entries()){
  const e=compileExecutionEnvelope({intent:baseIntent(profile,valid),handoff_receipts:receiptsFor(profile)},ctx);
  if(e.disposition!=='ECAC') throw new Error(`expected_ecac:${skillId}:${e.disposition}:${e.reasons.join(',')}`);
  valid++;
}
if(valid!==23) throw new Error(`expected_23_profiles:${valid}`);

const ledger=profiles.profiles.get('ct.skill.chlom-wallet.ledger-chain-verification.v1');
const missing=compileExecutionEnvelope({intent:{...baseIntent(ledger,101),intent_id:'ct.intent.envelope.missing'},handoff_receipts:receiptsFor(ledger).slice(0,-1)},ctx);
if(missing.disposition!=='HOLD') throw new Error(`missing_receipt_must_hold:${missing.disposition}`);
const staleId=ledger.required_handoffs[0];
const stale=compileExecutionEnvelope({intent:{...baseIntent(ledger,102),intent_id:'ct.intent.envelope.stale'},handoff_receipts:receiptsFor(ledger,{stale:staleId})},ctx);
if(stale.disposition!=='HOLD') throw new Error(`stale_receipt_must_hold:${stale.disposition}`);
const denied=compileExecutionEnvelope({intent:{...baseIntent(ledger,103),intent_id:'ct.intent.envelope.denied'},handoff_receipts:receiptsFor(ledger,{decision:{id:staleId,value:'DENY'}})},ctx);
if(denied.disposition!=='DENY') throw new Error(`deny_receipt_must_deny:${denied.disposition}`);
const wrongPallet=compileExecutionEnvelope({intent:{...baseIntent(ledger,104),intent_id:'ct.intent.envelope.pallet',pallet_ids:['ct.pallet.chlom-passkey-identity.v1']},handoff_receipts:receiptsFor(ledger)},ctx);
if(wrongPallet.disposition!=='DENY') throw new Error(`wrong_pallet_must_deny:${wrongPallet.disposition}`);
const wrongAction=compileExecutionEnvelope({intent:{...baseIntent(ledger,105),intent_id:'ct.intent.envelope.action',action_type:'SANITIZED_PUBLIC_PROJECTION'},handoff_receipts:receiptsFor(ledger)},ctx);
if(wrongAction.disposition!=='DENY') throw new Error(`wrong_action_must_deny:${wrongAction.disposition}`);
const provider=profiles.profiles.get('ct.skill.chlom-wallet.provider-event-verification.v1');
const providerReceipts=receiptsFor(provider);
providerReceipts.push({receipt_id:'ct.receipt.test.pending-alias',reviewer_agent_id:'ct.agent.webhook-delivery',role:'webhook_delivery',scope:'controlled_test_review',source_head_sha:HEAD,heartbeat_fresh:true,independent:true,decision:'PASS',receipt_sha256:sha256Hex('pending-alias')});
const alias=compileExecutionEnvelope({intent:{...baseIntent(provider,106),intent_id:'ct.intent.envelope.alias'},handoff_receipts:providerReceipts},ctx);
if(alias.disposition!=='DENY') throw new Error(`pending_alias_receipt_must_deny:${alias.disposition}`);
const selfReview=compileExecutionEnvelope({intent:{...baseIntent(ledger,107),intent_id:'ct.intent.envelope.self',originator_agent_id:ledger.required_handoffs[0]},handoff_receipts:receiptsFor(ledger)},ctx);
if(selfReview.disposition!=='DENY') throw new Error(`self_handoff_must_deny:${selfReview.disposition}`);

console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_EXECUTION_ENVELOPE_V1',profiles:profiles.profiles.size,valid_ecac_profiles:valid,missing_handoff:missing.disposition,stale_handoff:stale.disposition,denied_handoff:denied.disposition,wrong_pallet:wrongPallet.disposition,wrong_action:wrongAction.disposition,pending_alias_receipt:alias.disposition,self_handoff:selfReview.disposition,authority_granted:false,capability_grant_created:false}));
