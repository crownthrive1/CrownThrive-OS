import fs from 'node:fs';
const parse=(u)=>JSON.parse(fs.readFileSync(new URL(u,import.meta.url),'utf8'));
const suite=parse('../../../../automation/chlom-wallet-agent-skills-v2.json');
const phaseC=parse('../../../../automation/chlom-wallet-settlement-agent-phase-c-skills.json');
const execution=parse('./execution-envelope-profiles.v1.json');
const palletClosure=parse('../policy/skill-pallet-closure.v2.json');
const expectedSkills=new Set([...(suite.skills??[]).map(x=>x.skill_id),...(phaseC.skills??[]).map(x=>x.skill_id)]);
const expectedPalletMap=new Map((palletClosure.mappings??[]).map(x=>[x.skill_id,new Set(x.pallet_ids)]));
const seen=new Set(); let palletBindings=0;
for(const p of execution.profiles??[]){
  if(seen.has(p.skill_id)) throw new Error(`duplicate_execution_profile:${p.skill_id}`);
  seen.add(p.skill_id);
  if(!expectedSkills.has(p.skill_id)) throw new Error(`unexpected_execution_skill:${p.skill_id}`);
  const allowed=expectedPalletMap.get(p.skill_id); if(!allowed) throw new Error(`missing_policy_pallet_mapping:${p.skill_id}`);
  if(!Array.isArray(p.pallet_ids)||!p.pallet_ids.length) throw new Error(`missing_execution_pallets:${p.skill_id}`);
  for(const pallet of p.pallet_ids){ if(!allowed.has(pallet)) throw new Error(`execution_pallet_not_in_policy_closure:${p.skill_id}:${pallet}`); palletBindings++; }
  if(!Array.isArray(p.required_handoffs)||!p.required_handoffs.length) throw new Error(`missing_required_handoffs:${p.skill_id}`);
  if(!Array.isArray(p.action_types)||!p.action_types.length) throw new Error(`missing_action_types:${p.skill_id}`);
  if(!Array.isArray(p.value_classes)||!p.value_classes.length) throw new Error(`missing_value_classes:${p.skill_id}`);
}
for(const skill of expectedSkills) if(!seen.has(skill)) throw new Error(`missing_execution_profile:${skill}`);
if(seen.size!==expectedSkills.size) throw new Error(`execution_profile_count_mismatch:${seen.size}:${expectedSkills.size}`);
for(const [k,v] of Object.entries(execution.hard_boundaries??{})) if(v!==false) throw new Error(`execution_hard_boundary_not_false:${k}`);
console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_EXECUTION_PROFILE_CLOSURE_V1',skills:seen.size,pallet_bindings:palletBindings,missing_profiles:0,unexpected_profiles:0}));
