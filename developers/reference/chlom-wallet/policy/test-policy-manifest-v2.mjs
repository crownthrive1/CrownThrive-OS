import fs from 'node:fs';
import crypto from 'node:crypto';
const manifestPath=new URL('../../../manifests/chlom-wallet-policy-assurance-v2.json',import.meta.url);
const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
for(const entry of manifest.source_files){ const bytes=fs.readFileSync(new URL(`../../../../${entry.path}`,import.meta.url)); const actual=crypto.createHash('sha256').update(bytes).digest('hex'); if(actual!==entry.sha256) throw new Error(`manifest_source_hash_mismatch:${entry.path}`); }
if(manifest.controlled_test_evidence.invariant_failures!==0) throw new Error('manifest_invariant_failures_nonzero');
for(const [k,v] of Object.entries(manifest.governance)){ if(['production_activation','provider_write','custody','token_issuance','money_movement','production_rights_grant','chain_broadcast','effective_price_publication','checkout_activation','phase_advancement','merge_authorized','ai_final_authority'].includes(k)&&v!==false) throw new Error(`manifest_boundary_not_false:${k}`); }
console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_POLICY_MANIFEST_V2',source_files:manifest.source_files.length,algorithms:manifest.algorithm_registry.length}));
