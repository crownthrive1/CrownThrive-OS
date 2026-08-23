import { canonicalize, sha256Hex, assertAsciiIdentifier, secretShapePresent } from '../common/canonical-json.mjs';

const RECEIPT_DECISIONS = new Set(['PASS','HOLD','DENY']);
const ROUTE_STATE = Object.freeze({ SATISFIED:'SATISFIED', HOLD:'HOLD', DENY:'DENY' });
function obj(v,c){ if(!v||typeof v!=='object'||Array.isArray(v)) throw new Error(c); return v; }
function hash(v,c){ if(typeof v!=='string'||!/^[0-9a-f]{64}$/.test(v)) throw new Error(c); return v; }
function head(v,c){ if(typeof v!=='string'||!/^[0-9a-f]{40}$/.test(v)) throw new Error(c); return v; }
function text(v,c,max=180){ return assertAsciiIdentifier(v,c,max); }

export function compileHandoffRegistry(crosswalk) {
  const c=obj(crosswalk,'handoff_crosswalk_required');
  const verified=new Map();
  for(const row of c.verified_handoffs ?? []){
    const id=text(row.stable_agent_id,'stable_agent_id_invalid');
    if(verified.has(id)) throw new Error(`duplicate_stable_handoff:${id}`);
    verified.set(id,Object.freeze({
      stable_agent_id:id,
      role:text(row.role,'handoff_role_invalid'),
      identity_state:text(row.identity_state,'identity_state_invalid'),
      registry_binding_state:text(row.registry_binding_state,'binding_state_invalid'),
      authority_ceiling:text(row.authority_ceiling,'authority_ceiling_invalid',8),
      vote_effect:String(row.vote_effect ?? 'none')
    }));
  }
  const pending=new Map();
  for(const row of c.pending_role_aliases ?? []){
    const alias=text(row.legacy_alias,'pending_alias_invalid');
    pending.set(alias,Object.freeze({
      legacy_alias:alias,
      role_alias:text(row.role_alias,'role_alias_invalid'),
      identity_state:text(row.identity_state,'pending_identity_state_invalid'),
      allowed_use:String(row.allowed_use ?? 'non_executing_handoff_label_only'),
      authority_granted:Boolean(row.authority_granted),
      capability_grant_created:Boolean(row.capability_grant_created),
      heartbeat_binding_created:Boolean(row.heartbeat_binding_created)
    }));
  }
  if(secretShapePresent({verified:[...verified.values()],pending:[...pending.values()]})) throw new Error('handoff_registry_secret_shape_detected');
  return Object.freeze({ crosswalk_id:text(c.crosswalk_id,'crosswalk_id_invalid'), verified, pending });
}

function normalizeReceipt(receipt) {
  const r=obj(receipt,'handoff_receipt_invalid');
  const decision=String(r.decision);
  if(!RECEIPT_DECISIONS.has(decision)) throw new Error('handoff_receipt_decision_invalid');
  return Object.freeze({
    receipt_id:text(r.receipt_id,'handoff_receipt_id_invalid'),
    reviewer_agent_id:text(r.reviewer_agent_id,'handoff_reviewer_invalid'),
    role:text(r.role,'handoff_receipt_role_invalid'),
    scope:text(r.scope,'handoff_scope_invalid',240),
    source_head_sha:head(r.source_head_sha,'handoff_source_head_invalid'),
    heartbeat_fresh:r.heartbeat_fresh === true,
    independent:r.independent === true,
    decision,
    receipt_sha256:hash(r.receipt_sha256,'handoff_receipt_sha_invalid')
  });
}

export function routeHandoffEvidence({originator_agent_id, source_head_sha, required_handoffs, pending_role_aliases=[], receipts=[]}, registry) {
  const originator=text(originator_agent_id,'originator_agent_id_invalid');
  const expectedHead=head(source_head_sha,'source_head_sha_invalid');
  if(!Array.isArray(required_handoffs)||required_handoffs.length===0) throw new Error('required_handoffs_missing');
  if(!Array.isArray(receipts)) throw new Error('handoff_receipts_array_required');
  const normalizedReceipts=receipts.map(normalizeReceipt);
  if(secretShapePresent(normalizedReceipts)) throw new Error('handoff_receipt_secret_shape_detected');
  const byReviewer=new Map();
  for(const r of normalizedReceipts){ if(byReviewer.has(r.reviewer_agent_id)) throw new Error(`duplicate_handoff_receipt:${r.reviewer_agent_id}`); byReviewer.set(r.reviewer_agent_id,r); }

  const reasons=[]; const missing=[]; const stale=[]; const accepted=[]; const denied=[];
  let state=ROUTE_STATE.SATISFIED;

  for(const alias of pending_role_aliases){
    if(!registry.pending.has(alias)){ state=ROUTE_STATE.DENY; reasons.push(`unknown_pending_alias:${alias}`); continue; }
    if(byReviewer.has(alias)){ state=ROUTE_STATE.DENY; reasons.push(`pending_alias_receipt_not_executable:${alias}`); denied.push(alias); }
  }

  for(const reviewerId of [...new Set(required_handoffs)].sort()){
    const binding=registry.verified.get(reviewerId);
    if(!binding){ state=ROUTE_STATE.DENY; reasons.push(`required_handoff_not_verified:${reviewerId}`); denied.push(reviewerId); continue; }
    if(binding.registry_binding_state !== 'active'){
      if(state!==ROUTE_STATE.DENY) state=ROUTE_STATE.HOLD;
      reasons.push(`required_handoff_not_active:${reviewerId}`); stale.push(reviewerId); continue;
    }
    const r=byReviewer.get(reviewerId);
    if(!r){ if(state!==ROUTE_STATE.DENY) state=ROUTE_STATE.HOLD; reasons.push(`handoff_receipt_missing:${reviewerId}`); missing.push(reviewerId); continue; }
    if(r.reviewer_agent_id===originator || !r.independent){ state=ROUTE_STATE.DENY; reasons.push(`handoff_not_independent:${reviewerId}`); denied.push(reviewerId); continue; }
    if(r.role!==binding.role){ state=ROUTE_STATE.DENY; reasons.push(`handoff_role_mismatch:${reviewerId}`); denied.push(reviewerId); continue; }
    if(r.source_head_sha!==expectedHead){ if(state!==ROUTE_STATE.DENY) state=ROUTE_STATE.HOLD; reasons.push(`handoff_head_stale:${reviewerId}`); stale.push(reviewerId); continue; }
    if(!r.heartbeat_fresh){ if(state!==ROUTE_STATE.DENY) state=ROUTE_STATE.HOLD; reasons.push(`handoff_heartbeat_stale:${reviewerId}`); stale.push(reviewerId); continue; }
    if(r.decision==='DENY'){ state=ROUTE_STATE.DENY; reasons.push(`handoff_denied:${reviewerId}`); denied.push(reviewerId); continue; }
    if(r.decision==='HOLD'){ if(state!==ROUTE_STATE.DENY) state=ROUTE_STATE.HOLD; reasons.push(`handoff_held:${reviewerId}`); stale.push(reviewerId); continue; }
    accepted.push(reviewerId);
  }

  const core={
    router_contract:'ct.contract.chlom-wallet.handoff-evidence-router.v1',
    crosswalk_id:registry.crosswalk_id,
    originator_agent_id:originator,
    source_head_sha:expectedHead,
    required_handoffs:[...new Set(required_handoffs)].sort(),
    pending_role_aliases:[...new Set(pending_role_aliases)].sort(),
    route_state:state,
    accepted_reviewers:accepted.sort(),
    missing_reviewers:missing.sort(),
    stale_or_held_reviewers:[...new Set(stale)].sort(),
    denied_reviewers:[...new Set(denied)].sort(),
    reasons:[...new Set(reasons)].sort(),
    authority_granted:false,
    capability_grant_created:false,
    heartbeat_created:false,
    receipt_created_for_reviewer:false
  };
  return Object.freeze({ ...core, router_receipt_sha256:sha256Hex(canonicalize(core)) });
}
