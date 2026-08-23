import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
const manifest=JSON.parse(fs.readFileSync(new URL('../../../manifests/chlom-wallet-execution-envelope-v1.json',import.meta.url),'utf8'));
for(const entry of manifest.source_blobs){
  const actual=execFileSync('git',['hash-object',entry.path],{encoding:'utf8'}).trim();
  if(actual!==entry.git_blob_sha) throw new Error(`execution_manifest_blob_mismatch:${entry.path}:${actual}`);
}
if(manifest.closure.wallet_skill_profiles!==23||manifest.closure.walletkit_pallets!==12) throw new Error('execution_manifest_closure_invalid');
if(manifest.closure.pending_aliases_executable!==false) throw new Error('pending_alias_execution_must_be_false');
for(const [k,v] of Object.entries(manifest.governance)){
  if(['provider_write','custody','token_issuance','money_movement','production_rights_grant','chain_broadcast','effective_price_publication','checkout_activation','merge_authorized','phase_advancement','ai_final_authority','self_approval','independent_review_receipts_created_by_wallet','independent_reviewer_heartbeats_created_by_wallet'].includes(k)&&v!==false) throw new Error(`execution_manifest_boundary_not_false:${k}`);
}
console.log(JSON.stringify({result:'PASS_CHLOM_WALLET_EXECUTION_MANIFEST_V1',source_blobs:manifest.source_blobs.length,profiles:manifest.closure.wallet_skill_profiles,pallets:manifest.closure.walletkit_pallets,runtime_state:manifest.runtime.migration_apply_state,ci_state:manifest.ci.exact_head_state}));
