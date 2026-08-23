import { canonicalize, sha256Hex, assertAsciiIdentifier, secretShapePresent } from '../common/canonical-json.mjs';

const SEVERITY = Object.freeze({ ECAC:0, HOLD:1, DENY:2 });
const MAX_TEXT = 1200;
function obj(v,c){ if(!v||typeof v!=='object'||Array.isArray(v)) throw new Error(c); return v; }
function text(v,c,max=MAX_TEXT){ if(typeof v!=='string'||v.length<1||v.length>max) throw new Error(c); return v; }

export function applyAiCounselFirewall(deterministicDecision, advisoryInput) {
  const d=obj(deterministicDecision,'deterministic_decision_required');
  if (!(d.disposition in SEVERITY) || typeof d.receipt_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(d.receipt_sha256)) throw new Error('deterministic_decision_invalid');
  const a=obj(advisoryInput,'ai_advisory_required');
  const model_ref=assertAsciiIdentifier(a.model_ref,'model_ref_invalid',160);
  const advisory_id=assertAsciiIdentifier(a.advisory_id,'advisory_id_invalid',160);
  const proposed_disposition=String(a.proposed_disposition ?? 'HOLD');
  if (!(proposed_disposition in SEVERITY)) throw new Error('ai_proposed_disposition_invalid');
  const rationale=text(a.rationale ?? 'no_rationale','ai_rationale_invalid');
  const signals=Array.isArray(a.signals)?a.signals.map((s)=>text(String(s),'ai_signal_invalid',200)).slice(0,32):[];
  const sanitized={ advisory_id, model_ref, proposed_disposition, rationale, signals };
  if (secretShapePresent(sanitized)) throw new Error('ai_advisory_secret_shape_detected');
  const attempted_upgrade = SEVERITY[proposed_disposition] < SEVERITY[d.disposition];
  const conflict = proposed_disposition !== d.disposition;
  const accepted_as_final = false;
  const effective_disposition = d.disposition;
  const advisory_digest_sha256=sha256Hex(canonicalize(sanitized));
  const firewallCore={
    firewall_contract:'ct.contract.chlom-wallet.ai-counsel-firewall.v1',
    deterministic_receipt_sha256:d.receipt_sha256,
    advisory_id,
    model_ref,
    proposed_disposition,
    deterministic_disposition:d.disposition,
    effective_disposition,
    attempted_upgrade,
    conflict,
    accepted_as_final,
    ai_final_authority:false,
    note:'AI output is advisory evidence only and cannot weaken or replace deterministic policy.'
  };
  return Object.freeze({ ...firewallCore, advisory_digest_sha256, firewall_receipt_sha256:sha256Hex(canonicalize(firewallCore)) });
}

export function assertAiCannotUpgrade(deterministicDecision, advisories) {
  if(!Array.isArray(advisories)) throw new Error('advisories_array_required');
  return advisories.map((a)=>{
    const r=applyAiCounselFirewall(deterministicDecision,a);
    if(r.effective_disposition!==deterministicDecision.disposition||r.accepted_as_final||r.ai_final_authority) throw new Error('ai_authority_boundary_broken');
    return r;
  });
}
