import { canonicalize, sha256Hex, assertAsciiIdentifier, secretShapePresent } from '../common/canonical-json.mjs';

export const DISPOSITIONS = Object.freeze({ ECAC: 'ECAC', HOLD: 'HOLD', DENY: 'DENY' });
const A_LEVEL = Object.freeze({ A0:0, A1:1, A2:2, A3:3, A4:4 });
const D_LEVEL = Object.freeze({ D0:0, D1:1, D2:2, D3:3, D4:4 });
const HARD_BOUNDARY_FIELDS = Object.freeze([
  'production_activation','provider_write','custody','token_issuance','money_movement',
  'production_rights_grant','chain_broadcast','effective_price_publication','checkout_activation',
  'phase_advancement','merge_authorized','ai_final_authority'
]);

function requiredObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
  return value;
}
function requiredBool(value, code) { if (typeof value !== 'boolean') throw new Error(code); return value; }
function requiredString(value, code, max=160) { return assertAsciiIdentifier(value, code, max); }
function normalizeList(value, code, max=64) {
  if (!Array.isArray(value) || value.length > max) throw new Error(code);
  return [...new Set(value.map((x) => requiredString(x, code, 180)))].sort();
}
function level(map, value, code) { if (!(value in map)) throw new Error(code); return map[value]; }

export function compileRulepack(source) {
  const rp = requiredObject(source, 'rulepack_object_required');
  requiredString(rp.rulepack_ref, 'rulepack_ref_invalid', 200);
  requiredString(rp.rulepack_id, 'rulepack_id_invalid', 180);
  requiredString(rp.semantic_version, 'rulepack_version_invalid', 32);
  requiredString(rp.state, 'rulepack_state_invalid', 48);
  const authority = requiredObject(rp.authority, 'rulepack_authority_required');
  level(A_LEVEL, authority.autonomy_ceiling, 'rulepack_autonomy_ceiling_invalid');
  level(D_LEVEL, authority.decision_ceiling, 'rulepack_decision_ceiling_invalid');
  if (authority.ai_final_authority !== false || authority.self_approval !== false || authority.pending_role_aliases_executable !== false) {
    throw new Error('rulepack_authority_boundary_invalid');
  }
  const compiled = {
    rulepack_ref: rp.rulepack_ref,
    rulepack_id: rp.rulepack_id,
    semantic_version: rp.semantic_version,
    state: rp.state,
    authority: {
      autonomy_ceiling: authority.autonomy_ceiling,
      decision_ceiling: authority.decision_ceiling,
      ai_final_authority: false,
      self_approval: false,
      pending_role_aliases_executable: false
    },
    allowed_environments: normalizeList(rp.allowed_environments, 'allowed_environments_invalid'),
    production_activation: false,
    hard_deny_actions: normalizeList(rp.hard_deny_actions, 'hard_deny_actions_invalid'),
    controlled_test_boundary_actions: normalizeList(rp.controlled_test_boundary_actions, 'boundary_actions_invalid'),
    ecac_candidate_actions: normalizeList(rp.ecac_candidate_actions, 'ecac_candidate_actions_invalid'),
    required_for_ecac: normalizeList(rp.required_for_ecac, 'required_for_ecac_invalid'),
    value_classes: normalizeList(rp.value_classes, 'value_classes_invalid'),
    risk_thresholds: requiredObject(rp.risk_thresholds, 'risk_thresholds_required'),
    risk_weights: requiredObject(rp.risk_weights, 'risk_weights_required'),
    invariants: Array.isArray(rp.invariants) ? rp.invariants.map(String) : []
  };
  for (const [key,value] of Object.entries(compiled.risk_weights)) {
    if (!Number.isInteger(value) || value < 0 || value > 100) throw new Error(`risk_weight_invalid:${key}`);
  }
  if (secretShapePresent(compiled)) throw new Error('rulepack_secret_shape_detected');
  const source_sha256 = sha256Hex(canonicalize(rp));
  const compiled_sha256 = sha256Hex(canonicalize(compiled));
  return Object.freeze({ ...compiled, source_sha256, compiled_sha256 });
}

export function normalizeIntent(input) {
  const intent = requiredObject(input, 'intent_object_required');
  const authority = requiredObject(intent.authority, 'intent_authority_required');
  const evidence = requiredObject(intent.evidence, 'intent_evidence_required');
  const normalized = {
    schema_version: requiredString(intent.schema_version ?? '2.0.0', 'intent_schema_invalid', 32),
    intent_id: requiredString(intent.intent_id, 'intent_id_invalid'),
    correlation_id: requiredString(intent.correlation_id, 'correlation_id_invalid'),
    subject_ref: requiredString(intent.subject_ref, 'subject_ref_invalid'),
    originator_agent_id: requiredString(intent.originator_agent_id, 'originator_agent_id_invalid'),
    reviewer_agent_id: requiredString(intent.reviewer_agent_id, 'reviewer_agent_id_invalid'),
    action_type: requiredString(intent.action_type, 'action_type_invalid', 80),
    value_class: requiredString(intent.value_class, 'value_class_invalid', 32),
    environment: requiredString(intent.environment, 'environment_invalid', 40),
    skill_id: requiredString(intent.skill_id, 'skill_id_invalid', 180),
    pallet_ids: normalizeList(intent.pallet_ids ?? [], 'pallet_ids_invalid', 32),
    authority: {
      autonomy_level: requiredString(authority.autonomy_level, 'authority_autonomy_invalid', 8),
      decision_level: requiredString(authority.decision_level, 'authority_decision_invalid', 8),
      exact_head_verified: requiredBool(authority.exact_head_verified, 'exact_head_verified_invalid'),
      heartbeat_fresh: requiredBool(authority.heartbeat_fresh, 'heartbeat_fresh_invalid'),
      pending_alias_dependency: requiredBool(authority.pending_alias_dependency ?? false, 'pending_alias_dependency_invalid')
    },
    evidence: {
      source_fresh: requiredBool(evidence.source_fresh, 'source_fresh_invalid'),
      rollback_ready: requiredBool(evidence.rollback_ready, 'rollback_ready_invalid'),
      security_review: requiredBool(evidence.security_review ?? false, 'security_review_invalid'),
      rights_review: requiredBool(evidence.rights_review ?? false, 'rights_review_invalid'),
      finance_review: requiredBool(evidence.finance_review ?? false, 'finance_review_invalid'),
      recovery_review: requiredBool(evidence.recovery_review ?? false, 'recovery_review_invalid')
    },
    requested_effects: {}
  };
  for (const field of HARD_BOUNDARY_FIELDS) normalized.requested_effects[field] = Boolean(intent.requested_effects?.[field]);
  level(A_LEVEL, normalized.authority.autonomy_level, 'authority_autonomy_invalid');
  level(D_LEVEL, normalized.authority.decision_level, 'authority_decision_invalid');
  if (secretShapePresent(normalized)) throw new Error('intent_secret_shape_detected');
  return Object.freeze(normalized);
}

export function valueClassLattice(intent, rulepack) {
  const allowed = new Set(rulepack.value_classes);
  if (!allowed.has(intent.value_class)) return { state:'UNKNOWN', penalty:50, reasons:['value_class_unknown'] };
  if (intent.value_class === 'Mixed') return { state:'MIXED', penalty:rulepack.risk_weights.mixed_value_class ?? 15, reasons:['mixed_value_class_requires_independent_semantic_checks'] };
  return { state:'SINGLE', penalty:0, reasons:[] };
}

export function authorityIntegrityResolver(intent, rulepack) {
  const reasons=[]; let penalty=0; let hardDeny=false;
  const a = level(A_LEVEL, intent.authority.autonomy_level, 'authority_autonomy_invalid');
  const d = level(D_LEVEL, intent.authority.decision_level, 'authority_decision_invalid');
  if (a > level(A_LEVEL, rulepack.authority.autonomy_ceiling, 'rulepack_autonomy_ceiling_invalid') || d > level(D_LEVEL, rulepack.authority.decision_ceiling, 'rulepack_decision_ceiling_invalid')) {
    hardDeny=true; reasons.push('authority_ceiling_exceeded'); penalty += 100;
  }
  if (!intent.authority.exact_head_verified) { reasons.push('exact_head_missing'); penalty += rulepack.risk_weights.missing_exact_head ?? 40; }
  if (!intent.authority.heartbeat_fresh) { reasons.push('heartbeat_stale'); penalty += rulepack.risk_weights.stale_heartbeat ?? 30; }
  if (intent.authority.pending_alias_dependency) { reasons.push('pending_alias_dependency'); penalty += rulepack.risk_weights.pending_alias_dependency ?? 35; }
  if (intent.originator_agent_id === intent.reviewer_agent_id) { reasons.push('originator_reviewer_not_separated'); penalty += rulepack.risk_weights.self_review ?? 60; }
  return { hard_deny:hardDeny, penalty, reasons };
}

export function evidenceAwareGateResolver(intent, rulepack) {
  const reasons=[]; let penalty=0;
  if (!intent.evidence.source_fresh) { reasons.push('source_stale'); penalty += rulepack.risk_weights.stale_source ?? 25; }
  if (!intent.evidence.rollback_ready) { reasons.push('rollback_not_ready'); penalty += rulepack.risk_weights.missing_rollback ?? 20; }
  const action = intent.action_type;
  if (['LOCAL_EVM_TEST','CONTROLLED_TEST_COMPUTE','PROVIDER_WRITE','CHAIN_BROADCAST'].includes(action) && !intent.evidence.security_review) {
    reasons.push('security_review_missing'); penalty += rulepack.risk_weights.missing_security_review ?? 20;
  }
  if (['RIGHTS_GRANT','SANITIZED_PUBLIC_PROJECTION'].includes(action) && !intent.evidence.rights_review) {
    reasons.push('rights_review_missing'); penalty += rulepack.risk_weights.missing_rights_review ?? 20;
  }
  if (['MONEY_MOVEMENT','EFFECTIVE_PRICE_PUBLICATION','CHECKOUT_ACTIVATION'].includes(action) && !intent.evidence.finance_review) {
    reasons.push('finance_review_missing'); penalty += rulepack.risk_weights.missing_finance_review ?? 15;
  }
  if (['PROVIDER_WRITE','MONEY_MOVEMENT','RIGHTS_GRANT','CHAIN_BROADCAST'].includes(action) && !intent.evidence.recovery_review) {
    reasons.push('recovery_review_missing'); penalty += rulepack.risk_weights.missing_recovery_review ?? 15;
  }
  return { penalty, reasons };
}

export function riskInvariantGuard(intent, rulepack, components) {
  const reasons=[...components.vcl.reasons, ...components.air.reasons, ...components.eagr.reasons];
  let riskScore = components.vcl.penalty + components.air.penalty + components.eagr.penalty;
  let disposition = DISPOSITIONS.HOLD;
  const hardDenyActions = new Set(rulepack.hard_deny_actions);
  const boundaryActions = new Set(rulepack.controlled_test_boundary_actions);
  const ecacActions = new Set(rulepack.ecac_candidate_actions);
  if (!rulepack.allowed_environments.includes(intent.environment)) { reasons.push('environment_not_allowed'); riskScore += 100; disposition = DISPOSITIONS.DENY; }
  if (hardDenyActions.has(intent.action_type)) { reasons.push('hard_deny_action'); riskScore += 100; disposition = DISPOSITIONS.DENY; }
  if (boundaryActions.has(intent.action_type)) { reasons.push('controlled_test_boundary_action_prohibited'); riskScore += rulepack.risk_weights.commercial_activation_attempt ?? 70; disposition = DISPOSITIONS.DENY; }
  for (const [field,requested] of Object.entries(intent.requested_effects)) {
    if (requested) { reasons.push(`hard_boundary_effect_requested:${field}`); riskScore += 100; disposition = DISPOSITIONS.DENY; }
  }
  if (components.air.hard_deny) disposition = DISPOSITIONS.DENY;
  const missingCore = !intent.authority.exact_head_verified || !intent.authority.heartbeat_fresh || !intent.evidence.source_fresh || !intent.evidence.rollback_ready || intent.originator_agent_id === intent.reviewer_agent_id || intent.authority.pending_alias_dependency;
  if (disposition !== DISPOSITIONS.DENY && ecacActions.has(intent.action_type) && !missingCore && components.vcl.state !== 'UNKNOWN') {
    disposition = riskScore >= 50 ? DISPOSITIONS.HOLD : DISPOSITIONS.ECAC;
  }
  if (disposition !== DISPOSITIONS.DENY && !ecacActions.has(intent.action_type)) {
    reasons.push('action_not_ecac_candidate'); riskScore += rulepack.risk_weights.unknown_action ?? 50;
    disposition = DISPOSITIONS.HOLD;
  }
  riskScore = Math.min(999, riskScore);
  const t=rulepack.risk_thresholds;
  const riskBand = riskScore <= t.low_max ? 'LOW' : riskScore <= t.medium_max ? 'MEDIUM' : riskScore <= t.high_max ? 'HIGH' : 'CRITICAL';
  return { disposition, risk_score:riskScore, risk_band:riskBand, reasons:[...new Set(reasons)].sort() };
}

export function evaluatePolicyIntent(input, compiledRulepack) {
  const intent = normalizeIntent(input);
  const rulepack = compiledRulepack;
  const components = {
    vcl: valueClassLattice(intent, rulepack),
    air: authorityIntegrityResolver(intent, rulepack),
    eagr: evidenceAwareGateResolver(intent, rulepack)
  };
  const outcome = riskInvariantGuard(intent, rulepack, components);
  const intent_sha256 = sha256Hex(canonicalize(intent));
  const decisionCore = {
    policy_contract: 'ct.contract.chlom-wallet.policy-assurance.v2',
    intent_id: intent.intent_id,
    correlation_id: intent.correlation_id,
    subject_ref: intent.subject_ref,
    skill_id: intent.skill_id,
    pallet_ids: intent.pallet_ids,
    action_type: intent.action_type,
    value_class: intent.value_class,
    environment: intent.environment,
    disposition: outcome.disposition,
    risk_score: outcome.risk_score,
    risk_band: outcome.risk_band,
    reasons: outcome.reasons,
    intent_sha256,
    rulepack_ref: rulepack.rulepack_ref,
    rulepack_sha256: rulepack.compiled_sha256,
    ai_final_authority: false,
    controlled_test_only: true,
    hard_boundaries: Object.fromEntries(HARD_BOUNDARY_FIELDS.map((f)=>[f,false]))
  };
  const receipt_sha256 = sha256Hex(canonicalize(decisionCore));
  return Object.freeze({ ...decisionCore, receipt_sha256 });
}

export function verifyDeterminism(input, compiledRulepack, iterations=5) {
  const first = evaluatePolicyIntent(input, compiledRulepack);
  for (let i=1;i<iterations;i++) {
    const next=evaluatePolicyIntent(structuredClone(input), compiledRulepack);
    if (next.receipt_sha256 !== first.receipt_sha256) throw new Error('policy_decision_nondeterministic');
  }
  return first;
}
