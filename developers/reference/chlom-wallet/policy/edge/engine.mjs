import { createHash } from 'node:crypto';

export const ENGINE_ID = 'ct.engine.chlom-wallet-policy-assurance.v1';
export const ENGINE_VERSION = '1.0.0';
export const DISPOSITIONS = Object.freeze(['ECAC', 'HOLD', 'DENY']);
export const VALUE_CLASSES = Object.freeze(['identity', 'money', 'rights', 'rewards', 'impact', 'proof', 'unknown']);
export const ENVIRONMENTS = Object.freeze(['controlled_test', 'testnet', 'production']);

export const ALGORITHMS = Object.freeze({
  CAPS: Object.freeze({ id: 'ct.algorithm.wallet.caps.v1', name: 'Canonical Authority & Policy Compiler', version: '1.0.0' }),
  EAGR: Object.freeze({ id: 'ct.algorithm.wallet.eagr.v1', name: 'Evidence-Aware Gate Resolver', version: '1.0.0' }),
  VCL: Object.freeze({ id: 'ct.algorithm.wallet.vcl.v1', name: 'Value-Class Lattice', version: '1.0.0' }),
  AIR: Object.freeze({ id: 'ct.algorithm.wallet.air.v1', name: 'Authority Integrity Resolver', version: '1.0.0' }),
  RIGOR: Object.freeze({ id: 'ct.algorithm.wallet.rigor.v1', name: 'Risk Invariant Guard & Outcome Resolver', version: '1.0.0' }),
  DRIFT: Object.freeze({ id: 'ct.algorithm.wallet.drift.v1', name: 'Deterministic Receipt & Invariant Fingerprint Trace', version: '1.0.0' }),
  CHAOS: Object.freeze({ id: 'ct.algorithm.wallet.chaos.v1', name: 'Controlled Hazard & Adversarial Outcome Simulator', version: '1.0.0' }),
});

const DECISION_RANK = Object.freeze({ D0: 0, D1: 1, D2: 2, D3: 3, D4: 4 });
const AUTONOMY_RANK = Object.freeze({ A0: 0, A1: 1, A2: 2, A3: 3, A4: 4 });
const FORBIDDEN_KEYS = Object.freeze([
  'private_key', 'privateKey', 'seed_phrase', 'seedPhrase', 'mnemonic',
  'credential_value', 'credentialValue', 'client_secret', 'clientSecret',
  'webhook_secret', 'webhookSecret', 'api_key', 'apiKey', 'secret_manager_value',
]);

const BASE_REQUIRED_EVIDENCE = Object.freeze({
  provider_event_translate: ['provider_signature_verified', 'replay_state_verified', 'provider_event_allowlisted'],
  entitlement_evaluate: ['rights_evidence_present', 'terms_version_exact'],
  allocation_preview: ['economic_schedule_exact', 'allocation_conservation_verified'],
  thrivefund_obligation: ['impact_policy_exact', 'obligation_evidence_present'],
  proof_anchor_prepare: ['evidence_digest_present', 'protected_evidence_offchain'],
  passkey_registration: ['challenge_bound', 'origin_bound', 'rp_id_bound', 'public_key_only'],
  passkey_assertion: ['challenge_bound', 'origin_bound', 'rp_id_bound', 'signature_verified', 'counter_policy_satisfied'],
  passkey_recovery: ['identity_review_complete', 'cooldown_complete', 'recovery_evidence_present'],
  smart_account_intent: ['entrypoint_source_pinned', 'chain_codehash_observed', 'unsigned_intent_exact'],
  provider_exit: ['stable_identity_preserved', 'event_replay_preserved', 'rollback_plan_present'],
  wallet_public_projection: ['public_projection_reviewed', 'private_evidence_hidden', 'semantic_lanes_separate'],
  pricing_candidate: ['candidate_snapshot_frozen', 'independent_price_review_requested'],
});

const ACTION_HANDOFFS = Object.freeze({
  provider_event_translate: ['ct.agent.webhook-delivery', 'ct.agent.qa-security'],
  entitlement_evaluate: ['ct.agent.rights-governance', 'ct.subagent.legal-regulatory'],
  allocation_preview: ['ct.subagent.finance-tax-treasury'],
  thrivefund_obligation: ['ct.agent.impact-allocation', 'ct.subagent.finance-tax-treasury'],
  proof_anchor_prepare: ['ct.subagent.blockchain-protocol', 'ct.agent.qa-security'],
  passkey_registration: ['ct.agent.qa-security', 'ct.subagent.verification-tevv'],
  passkey_assertion: ['ct.agent.qa-security', 'ct.subagent.verification-tevv'],
  passkey_recovery: ['ct.subagent.recovery-rollback', 'ct.agent.qa-security'],
  smart_account_intent: ['ct.subagent.blockchain-protocol', 'ct.agent.qa-security', 'ct.agent.phase-gate'],
  provider_exit: ['ct.subagent.operations-sre', 'ct.agent.evidence-auditor'],
  wallet_public_projection: ['ct.subagent.accessibility-consumer', 'ct.agent.rights-governance'],
  pricing_candidate: ['ct.subagent.finance-tax-treasury', 'ct.agent.phase-gate'],
});

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function canonicalize(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  if (isPlainObject(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
  }
  if (typeof value === 'bigint') return JSON.stringify(value.toString());
  return JSON.stringify(value);
}

export function sha256Hex(value) {
  const data = value instanceof Uint8Array ? value : Buffer.from(typeof value === 'string' ? value : canonicalize(value));
  return createHash('sha256').update(data).digest('hex');
}

function deepFreeze(value) {
  if (Array.isArray(value)) {
    for (const item of value) deepFreeze(item);
    return Object.freeze(value);
  }
  if (isPlainObject(value)) {
    for (const item of Object.values(value)) deepFreeze(item);
    return Object.freeze(value);
  }
  return value;
}

function clone(value) {
  return structuredClone(value);
}

function assertString(value, label, pattern = null) {
  if (typeof value !== 'string' || value.length === 0) throw new Error(`${label}_required`);
  if (pattern && !pattern.test(value)) throw new Error(`${label}_invalid`);
}

function ensureUniqueStrings(values, label) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== 'string' || value.length === 0)) {
    throw new Error(`${label}_invalid`);
  }
  if (new Set(values).size !== values.length) throw new Error(`${label}_duplicate`);
}

function containsForbiddenKey(value, path = '$') {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const found = containsForbiddenKey(value[index], `${path}[${index}]`);
      if (found) return found;
    }
    return null;
  }
  if (!isPlainObject(value)) return null;
  for (const [key, child] of Object.entries(value)) {
    if (FORBIDDEN_KEYS.includes(key)) return `${path}.${key}`;
    const found = containsForbiddenKey(child, `${path}.${key}`);
    if (found) return found;
  }
  return null;
}

function normalizeRules(rules) {
  if (!Array.isArray(rules) || rules.length === 0) throw new Error('rulepack_rules_required');
  const normalized = rules.map((rule) => {
    if (!isPlainObject(rule)) throw new Error('rule_invalid');
    assertString(rule.rule_id, 'rule_id', /^ct[.]rule[.]wallet[.][a-z0-9._-]+[.]v1$/);
    assertString(rule.effect, 'rule_effect', /^(DENY|HOLD|RISK)$/);
    assertString(rule.reason_code, 'rule_reason_code', /^[A-Z0-9_:-]{3,120}$/);
    const weight = Number(rule.weight ?? 0);
    if (!Number.isInteger(weight) || weight < 0 || weight > 100) throw new Error('rule_weight_invalid');
    return {
      rule_id: rule.rule_id,
      effect: rule.effect,
      reason_code: rule.reason_code,
      weight,
      description: String(rule.description ?? ''),
    };
  });
  normalized.sort((a, b) => a.rule_id.localeCompare(b.rule_id));
  if (new Set(normalized.map((rule) => rule.rule_id)).size !== normalized.length) throw new Error('rule_id_duplicate');
  return normalized;
}

export function compileRulepack(rulepack) {
  if (!isPlainObject(rulepack)) throw new Error('rulepack_object_required');
  assertString(rulepack.rulepack_id, 'rulepack_id', /^ct[.]rulepack[.]chlom-wallet[.][a-z0-9._-]+[.]v1$/);
  assertString(rulepack.semantic_version, 'semantic_version', /^[0-9]+[.][0-9]+[.][0-9]+$/);
  if (rulepack.state !== 'CONTROLLED_TEST') throw new Error('rulepack_state_invalid');
  ensureUniqueStrings(rulepack.allowed_actions, 'allowed_actions');
  ensureUniqueStrings(rulepack.allowed_value_classes, 'allowed_value_classes');
  ensureUniqueStrings(rulepack.allowed_environments, 'allowed_environments');
  for (const value of rulepack.allowed_value_classes) {
    if (!VALUE_CLASSES.includes(value)) throw new Error('rulepack_value_class_invalid');
  }
  for (const value of rulepack.allowed_environments) {
    if (!ENVIRONMENTS.includes(value)) throw new Error('rulepack_environment_invalid');
  }
  const forbidden = containsForbiddenKey(rulepack);
  if (forbidden) throw new Error(`rulepack_forbidden_field:${forbidden}`);

  const normalized = {
    schema_version: '1.0.0',
    compiler_id: ALGORITHMS.CAPS.id,
    compiler_version: ALGORITHMS.CAPS.version,
    rulepack_id: rulepack.rulepack_id,
    semantic_version: rulepack.semantic_version,
    state: rulepack.state,
    allowed_actions: [...rulepack.allowed_actions].sort(),
    allowed_value_classes: [...rulepack.allowed_value_classes].sort(),
    allowed_environments: [...rulepack.allowed_environments].sort(),
    authority_ceiling: {
      autonomy: rulepack.authority_ceiling?.autonomy ?? 'A2',
      decision: rulepack.authority_ceiling?.decision ?? 'D2',
    },
    risk_thresholds: {
      low_max: Number(rulepack.risk_thresholds?.low_max ?? 24),
      medium_max: Number(rulepack.risk_thresholds?.medium_max ?? 49),
      high_max: Number(rulepack.risk_thresholds?.high_max ?? 74),
    },
    rules: normalizeRules(rulepack.rules),
    required_evidence: clone(rulepack.required_evidence ?? BASE_REQUIRED_EVIDENCE),
    required_handoffs: clone(rulepack.required_handoffs ?? ACTION_HANDOFFS),
    hard_boundaries: {
      production_activation: false,
      provider_write: false,
      custody: false,
      token_issuance: false,
      money_movement: false,
      production_rights_grant: false,
      chain_broadcast: false,
      effective_price_publication: false,
      checkout_activation: false,
      phase_advancement: false,
      merge_authorized: false,
    },
  };

  if (!AUTONOMY_RANK.hasOwnProperty(normalized.authority_ceiling.autonomy)) throw new Error('rulepack_autonomy_ceiling_invalid');
  if (!DECISION_RANK.hasOwnProperty(normalized.authority_ceiling.decision)) throw new Error('rulepack_decision_ceiling_invalid');
  const { low_max: low, medium_max: medium, high_max: high } = normalized.risk_thresholds;
  if (![low, medium, high].every(Number.isInteger) || low < 0 || low >= medium || medium >= high || high >= 100) {
    throw new Error('rulepack_risk_thresholds_invalid');
  }

  const compiled = {
    ...normalized,
    rulepack_sha256: sha256Hex(normalized),
    compiled_at: 'DETERMINISTIC_NO_WALL_CLOCK',
  };
  return deepFreeze(compiled);
}

function normalizeEvidence(evidence) {
  const input = Array.isArray(evidence) ? evidence : [];
  const normalized = input.map((item) => {
    if (!isPlainObject(item)) throw new Error('evidence_item_invalid');
    assertString(item.evidence_type, 'evidence_type', /^[a-z0-9._-]{2,120}$/);
    const state = item.state ?? 'present';
    if (!['present', 'verified', 'stale', 'invalid', 'missing'].includes(state)) throw new Error('evidence_state_invalid');
    return {
      evidence_type: item.evidence_type,
      state,
      digest_sha256: item.digest_sha256 ?? null,
      source_ref: item.source_ref ?? null,
      observed_at: item.observed_at ?? null,
      expires_at: item.expires_at ?? null,
    };
  });
  normalized.sort((a, b) => a.evidence_type.localeCompare(b.evidence_type));
  return normalized;
}

function riskBand(score, thresholds) {
  if (score <= thresholds.low_max) return 'LOW';
  if (score <= thresholds.medium_max) return 'MEDIUM';
  if (score <= thresholds.high_max) return 'HIGH';
  return 'CRITICAL';
}

function uniqueSorted(values) {
  return [...new Set(values)].sort();
}

function buildExplanation(disposition, denyReasons, holdReasons, riskBandValue) {
  if (disposition === 'DENY') {
    return [
      'The requested wallet action crossed one or more nondelegable or semantic safety boundaries.',
      ...denyReasons.map((reason) => `DENY: ${reason}`),
      'No execution authority is created by this receipt.',
    ];
  }
  if (disposition === 'HOLD') {
    return [
      'The request remains bounded but lacks required evidence, freshness, reconciliation, or independent review.',
      ...holdReasons.map((reason) => `HOLD: ${reason}`),
      `Risk band: ${riskBandValue}. No authority expansion is inferred.`,
    ];
  }
  return [
    'The request may proceed only inside the compiled controlled-test authority envelope.',
    'ECAC does not authorize production activation, provider writes, custody, money movement, rights grants, chain broadcast, pricing publication, phase advancement, or merge.',
    `Risk band: ${riskBandValue}.`,
  ];
}

function requiredEvidenceFor(compiledRulepack, actionType) {
  const values = compiledRulepack.required_evidence[actionType] ?? [];
  return Array.isArray(values) ? uniqueSorted(values.map(String)) : [];
}

function requiredHandoffsFor(compiledRulepack, actionType) {
  const values = compiledRulepack.required_handoffs[actionType] ?? [];
  return Array.isArray(values) ? uniqueSorted(values.map(String)) : [];
}

export function assessWalletIntent(intent, compiledRulepack) {
  if (!isPlainObject(intent)) throw new Error('intent_object_required');
  if (!isPlainObject(compiledRulepack) || !compiledRulepack.rulepack_sha256) throw new Error('compiled_rulepack_required');
  assertString(intent.intent_id, 'intent_id', /^ct[.]wallet[.]intent[.][a-z0-9._:-]{3,160}$/);
  assertString(intent.action_type, 'action_type', /^[a-z0-9._-]{2,120}$/);
  assertString(intent.value_class, 'value_class', /^[a-z_]{2,40}$/);
  assertString(intent.environment, 'environment', /^(controlled_test|testnet|production)$/);
  if (!isPlainObject(intent.authority)) throw new Error('intent_authority_required');
  assertString(intent.authority.agent_id, 'authority_agent_id', /^ct[.][a-z0-9._-]+$/);
  assertString(intent.authority.autonomy_class, 'authority_autonomy_class', /^A[0-4]$/);
  assertString(intent.authority.decision_class, 'authority_decision_class', /^D[0-4]$/);

  const forbiddenPath = containsForbiddenKey(intent);
  const normalizedEvidence = normalizeEvidence(intent.evidence);
  const evidenceState = new Map(normalizedEvidence.map((item) => [item.evidence_type, item.state]));
  const hardDenials = [];
  const holds = [];
  const riskFactors = [];
  let riskScore = 0;

  const addRisk = (code, weight) => {
    riskScore = Math.min(100, riskScore + weight);
    riskFactors.push({ code, weight });
  };
  const deny = (code, weight = 100) => {
    hardDenials.push(code);
    addRisk(code, weight);
  };
  const hold = (code, weight = 20) => {
    holds.push(code);
    addRisk(code, weight);
  };

  if (forbiddenPath) deny(`FORBIDDEN_SECRET_BEARING_FIELD:${forbiddenPath}`);
  if (!compiledRulepack.allowed_actions.includes(intent.action_type)) hold('ACTION_TYPE_NOT_IN_COMPILED_RULEPACK', 35);
  if (!compiledRulepack.allowed_value_classes.includes(intent.value_class)) hold('VALUE_CLASS_NOT_IN_COMPILED_RULEPACK', 35);
  if (!compiledRulepack.allowed_environments.includes(intent.environment)) deny('ENVIRONMENT_NOT_ALLOWED_BY_RULEPACK');

  const autonomyRank = AUTONOMY_RANK[intent.authority.autonomy_class];
  const decisionRank = DECISION_RANK[intent.authority.decision_class];
  if (autonomyRank == null || decisionRank == null) deny('AUTHORITY_CLASS_INVALID');
  if (autonomyRank > AUTONOMY_RANK[compiledRulepack.authority_ceiling.autonomy]) deny('AUTONOMY_CEILING_EXCEEDED');
  if (decisionRank > DECISION_RANK[compiledRulepack.authority_ceiling.decision]) deny('DECISION_CEILING_EXCEEDED');
  if (intent.authority.self_approval === true) deny('ORIGINATOR_SELF_APPROVAL_FORBIDDEN');
  if (intent.authority.vote_effect && intent.authority.vote_effect !== 'none') deny('SOVEREIGN_VOTE_EFFECT_FORBIDDEN');
  if (intent.authority.heartbeat_fresh !== true) hold('AUTHORITY_HEARTBEAT_STALE_OR_MISSING', 30);
  if (intent.authority.exact_head_bound !== true) hold('AUTHORITY_NOT_BOUND_TO_EXACT_HEAD', 25);

  const requested = isPlainObject(intent.requested_effects) ? intent.requested_effects : {};
  const deniedEffects = [
    ['production_activation', 'PRODUCTION_ACTIVATION_NOT_AUTHORIZED'],
    ['provider_write', 'PROVIDER_WRITE_NOT_AUTHORIZED'],
    ['custody', 'CUSTODY_NOT_AUTHORIZED'],
    ['token_issuance', 'TOKEN_ISSUANCE_NOT_AUTHORIZED'],
    ['money_movement', 'MONEY_MOVEMENT_NOT_AUTHORIZED'],
    ['production_rights_grant', 'PRODUCTION_RIGHTS_GRANT_NOT_AUTHORIZED'],
    ['chain_broadcast', 'CHAIN_BROADCAST_NOT_AUTHORIZED'],
    ['effective_price_publication', 'EFFECTIVE_PRICE_PUBLICATION_NOT_AUTHORIZED'],
    ['checkout_activation', 'CHECKOUT_ACTIVATION_NOT_AUTHORIZED'],
    ['phase_advancement', 'PHASE_ADVANCEMENT_NOT_AUTHORIZED'],
    ['merge_authorized', 'MERGE_AUTHORITY_NOT_GRANTED'],
  ];
  for (const [key, code] of deniedEffects) {
    if (requested[key] === true) deny(code);
  }
  if (intent.environment === 'production') deny('PRODUCTION_ENVIRONMENT_CLOSED');
  if (intent.environment === 'testnet' && intent.action_type !== 'smart_account_intent') hold('TESTNET_ACTION_REQUIRES_SEPARATE_SCOPE', 35);

  const requiredEvidence = requiredEvidenceFor(compiledRulepack, intent.action_type);
  const missingEvidence = [];
  const staleEvidence = [];
  const invalidEvidence = [];
  for (const evidenceType of requiredEvidence) {
    const state = evidenceState.get(evidenceType) ?? 'missing';
    if (state === 'missing') missingEvidence.push(evidenceType);
    else if (state === 'stale') staleEvidence.push(evidenceType);
    else if (state === 'invalid') invalidEvidence.push(evidenceType);
  }
  if (missingEvidence.length) hold(`REQUIRED_EVIDENCE_MISSING:${missingEvidence.join(',')}`, Math.min(55, 8 * missingEvidence.length));
  if (staleEvidence.length) hold(`REQUIRED_EVIDENCE_STALE:${staleEvidence.join(',')}`, Math.min(60, 12 * staleEvidence.length));
  if (invalidEvidence.length) deny(`REQUIRED_EVIDENCE_INVALID:${invalidEvidence.join(',')}`);

  const semantics = isPlainObject(intent.semantics) ? intent.semantics : {};
  if (intent.value_class === 'rights' && semantics.provider_payment_is_rights_evidence === true) deny('PAYMENT_EVIDENCE_CANNOT_CREATE_RIGHTS');
  if (intent.action_type === 'entitlement_evaluate' && semantics.payment_only === true) deny('PAYMENT_ONLY_ENTITLEMENT_FORBIDDEN');
  if (intent.value_class === 'impact' && semantics.external_settlement_claimed === true && evidenceState.get('external_settlement_evidence') !== 'verified') {
    deny('IMPACT_SETTLEMENT_REQUIRES_EXTERNAL_EVIDENCE');
  }
  if (intent.value_class === 'rewards' && semantics.cash_equivalent_claimed === true && evidenceState.get('cash_equivalent_authority') !== 'verified') {
    deny('REWARD_CASH_EQUIVALENCE_NOT_AUTHORIZED');
  }
  if (intent.value_class === 'proof' && semantics.protected_evidence_body_onchain === true) deny('PROTECTED_EVIDENCE_BODY_MUST_REMAIN_OFFCHAIN');
  if (intent.value_class === 'unknown') hold('UNKNOWN_VALUE_CLASS', 40);

  const provider = isPlainObject(intent.provider) ? intent.provider : {};
  if (provider.livemode === true && intent.environment === 'controlled_test') deny('LIVE_PROVIDER_EVENT_IN_CONTROLLED_TEST');
  if (provider.signature_verified === false) hold('PROVIDER_SIGNATURE_NOT_VERIFIED', 35);
  if (provider.exact_replay === true && provider.replay_state !== 'DUPLICATE') deny('PROVIDER_REPLAY_STATE_INCONSISTENT');

  const passkey = isPlainObject(intent.passkey) ? intent.passkey : {};
  if (passkey.private_key_present === true || passkey.private_jwk_present === true) deny('PASSKEY_PRIVATE_KEY_MATERIAL_FORBIDDEN');
  if (passkey.production_activation === true) deny('PRODUCTION_CREDENTIAL_ACTIVATION_NOT_AUTHORIZED');
  if (passkey.smart_account_binding === true) hold('PASSKEY_SMART_ACCOUNT_BINDING_NOT_CERTIFIED', 45);

  const chain = isPlainObject(intent.chain) ? intent.chain : {};
  if (chain.runtime_codehash_match === false) deny('ENTRYPOINT_RUNTIME_CODEHASH_MISMATCH');
  if (chain.source_profile_pinned === false) hold('ENTRYPOINT_SOURCE_PROFILE_NOT_PINNED', 40);
  if (chain.signature_present === true) deny('SIGNED_USER_OPERATION_NOT_AUTHORIZED');
  if (chain.paymaster_present === true) deny('PAYMASTER_NOT_AUTHORIZED');
  if (chain.factory_selected === true && chain.factory_reviewed !== true) deny('UNREVIEWED_FACTORY_SELECTION');
  if (chain.account_implementation_selected === true && chain.account_implementation_reviewed !== true) deny('UNREVIEWED_ACCOUNT_IMPLEMENTATION');
  if (chain.simulation_completed === true && chain.simulation_evidence_present !== true) deny('SIMULATION_CLAIM_WITHOUT_EVIDENCE');

  const governance = isPlainObject(intent.governance) ? intent.governance : {};
  if (governance.independent_review_required === true && governance.independent_review_state !== 'PASS') {
    hold('INDEPENDENT_REVIEW_NOT_PASSED', 35);
  }
  if (governance.phase_gate_required === true && governance.phase_gate_state !== 'PASS') {
    hold('PHASE_GATE_NOT_PASSED', 35);
  }
  if (governance.rollback_plan_present !== true) hold('ROLLBACK_PLAN_MISSING', 20);
  if (governance.evidence_digest_bound !== true) hold('EVIDENCE_DIGEST_NOT_BOUND', 25);

  for (const item of normalizedEvidence) {
    if (item.state === 'invalid') addRisk(`INVALID_EVIDENCE:${item.evidence_type}`, 20);
    if (item.state === 'stale') addRisk(`STALE_EVIDENCE:${item.evidence_type}`, 8);
  }

  const denyReasons = uniqueSorted(hardDenials);
  const holdReasons = uniqueSorted(holds);
  const disposition = denyReasons.length ? 'DENY' : holdReasons.length ? 'HOLD' : 'ECAC';
  const score = Math.min(100, riskScore);
  const band = riskBand(score, compiledRulepack.risk_thresholds);
  const normalizedIntent = clone(intent);
  const intentSha256 = sha256Hex(normalizedIntent);
  const decisionBody = {
    schema_version: '1.0.0',
    engine_id: ENGINE_ID,
    engine_version: ENGINE_VERSION,
    algorithm_versions: Object.fromEntries(Object.entries(ALGORITHMS).map(([key, value]) => [key, value.version])),
    rulepack_id: compiledRulepack.rulepack_id,
    rulepack_version: compiledRulepack.semantic_version,
    rulepack_sha256: compiledRulepack.rulepack_sha256,
    intent_id: intent.intent_id,
    intent_sha256: intentSha256,
    action_type: intent.action_type,
    value_class: intent.value_class,
    environment: intent.environment,
    disposition,
    risk_score: score,
    risk_band: band,
    hard_denials: denyReasons,
    hold_reasons: holdReasons,
    required_evidence: requiredEvidence,
    missing_evidence: uniqueSorted(missingEvidence),
    stale_evidence: uniqueSorted(staleEvidence),
    invalid_evidence: uniqueSorted(invalidEvidence),
    required_handoffs: requiredHandoffsFor(compiledRulepack, intent.action_type),
    risk_factors: riskFactors.sort((a, b) => a.code.localeCompare(b.code)),
    explanation: buildExplanation(disposition, denyReasons, holdReasons, band),
    execution_envelope: {
      controlled_test_only: true,
      production_activation: false,
      provider_write: false,
      custody: false,
      token_issuance: false,
      money_movement: false,
      production_rights_grant: false,
      chain_broadcast: false,
      effective_price_publication: false,
      checkout_activation: false,
      phase_advancement: false,
      merge_authorized: false,
    },
    ai_advisory: {
      enabled: false,
      final_authority: false,
      explanation_mode: 'deterministic_reason_templates',
      future_llm_output_must_be_advisory_only: true,
    },
  };
  const receipt = {
    ...decisionBody,
    receipt_sha256: sha256Hex(decisionBody),
  };
  return deepFreeze(receipt);
}

export function verifyDecisionReceipt(receipt) {
  if (!isPlainObject(receipt)) return { valid: false, reason: 'receipt_object_required' };
  const { receipt_sha256: claimed, ...body } = receipt;
  if (typeof claimed !== 'string' || !/^[0-9a-f]{64}$/.test(claimed)) return { valid: false, reason: 'receipt_digest_invalid' };
  const computed = sha256Hex(body);
  return { valid: computed === claimed, claimed, computed, reason: computed === claimed ? null : 'receipt_digest_mismatch' };
}

export function buildPolicyAssuranceStatus(compiledRulepack, metrics = {}) {
  const body = {
    contract: 'ct.wallet.policy-assurance-status.v1',
    engine_id: ENGINE_ID,
    engine_version: ENGINE_VERSION,
    rulepack_id: compiledRulepack.rulepack_id,
    rulepack_version: compiledRulepack.semantic_version,
    rulepack_sha256: compiledRulepack.rulepack_sha256,
    algorithms: Object.values(ALGORITHMS),
    dispositions: DISPOSITIONS,
    metrics: {
      compiled_rulepacks: Number(metrics.compiled_rulepacks ?? 1),
      decision_receipts: Number(metrics.decision_receipts ?? 0),
      chaos_cases: Number(metrics.chaos_cases ?? 0),
      invariant_failures: Number(metrics.invariant_failures ?? 0),
    },
    hard_boundaries: clone(compiledRulepack.hard_boundaries),
    ai_advisory: {
      enabled: false,
      final_authority: false,
      deterministic_engine_is_authoritative_for_this_controlled_test: true,
    },
  };
  return deepFreeze({ ...body, status_sha256: sha256Hex(body) });
}
