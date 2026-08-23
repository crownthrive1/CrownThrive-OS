import { applyAiCounselFirewall } from './ai-counsel-firewall-v1.mjs';
const decisions=['ECAC','HOLD','DENY'].map((disposition,i)=>({disposition,receipt_sha256:`${String(i+1).repeat(64)}`.slice(0,64)}));
let conflicts=0,upgrades=0;
for(const d of decisions){ for(const proposed of ['ECAC','HOLD','DENY']){ const r=applyAiCounselFirewall(d,{advisory_id:`ct.ai.test.${d.disposition}.${proposed}`,model_ref:'ct.model.synthetic-advisory',proposed_disposition:proposed,rationale:'Contract test rationale.',signals:['contract_test']}); if(r.conflict) conflicts++; if(r.attempted_upgrade) upgrades++; if(r.effective_disposition!==d.disposition||r.accepted_as_final||r.ai_final_authority) throw new Error('ai_final_authority_breach'); }}
console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_AI_COUNSEL_FIREWALL_V1',decisions:decisions.length,cases:9,conflicts,upgrade_attempts:upgrades,ai_final_authority:false}));
