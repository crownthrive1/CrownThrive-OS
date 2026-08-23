import { createHash } from 'node:crypto';

export const POLICY_COMPILER_VERSION = 'ct.cwpx.compiler.v1.0.0';
export const DECISION_PRECEDENCE = Object.freeze({ DENY: 3, HOLD: 2, ALLOW: 1 });
const VALID_EFFECTS = new Set(Object.keys(DECISION_PRECEDENCE));
const VALID_OPERATORS = new Set([
  'eq', 'neq', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte',
  'exists', 'prefix', 'contains',
]);
const TRI = Object.freeze({ TRUE: 'TRUE', FALSE: 'FALSE', UNKNOWN: 'UNKNOWN' });

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function canonicalize(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  if (isPlainObject(value)) {
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
  }
  if (typeof value === 'bigint') return JSON.stringify(value.toString());
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('non_finite_number_forbidden');
  return JSON.stringify(value);
}

export function sha256Hex(value) {
  const bytes = value instanceof Uint8Array || Buffer.isBuffer(value)
    ? value
    : Buffer.from(String(value), 'utf8');
  return createHash('sha256').update(bytes).digest('hex');
}

function normalizePath(path) {
  if (typeof path !== 'string' || !/^[A-Za-z][A-Za-z0-9_.-]{0,159}$/.test(path)) {
    throw new Error('condition_field_invalid');
  }
  return path.split('.');
}

function normalizeLeaf(condition) {
  if (!isPlainObject(condition)) throw new Error('condition_leaf_object_required');
  const keys = Object.keys(condition);
  const allowed = new Set(['field', 'op', 'value']);
  if (keys.some((key) => !allowed.has(key))) throw new Error('condition_leaf_unknown_field');
  const field = condition.field;
  const op = condition.op;
  if (typeof op !== 'string' || !VALID_OPERATORS.has(op)) throw new Error('condition_operator_unsupported');
  const normalized = { field: normalizePath(field).join('.'), op };
  if (op !== 'exists') {
    if (!Object.hasOwn(condition, 'value')) throw new Error('condition_value_required');
    normalized.value = condition.value;
  } else if (Object.hasOwn(condition, 'value') && typeof condition.value !== 'boolean') {
    throw new Error('exists_condition_value_must_be_boolean');
  } else {
    normalized.value = Object.hasOwn(condition, 'value') ? condition.value : true;
  }
  if ((op === 'in' || op === 'not_in') && (!Array.isArray(normalized.value) || normalized.value.length === 0)) {
    throw new Error('membership_condition_requires_nonempty_array');
  }
  return normalized;
}

export function normalizeCondition(condition, depth = 0) {
  if (depth > 12) throw new Error('condition_depth_exceeded');
  if (!isPlainObject(condition)) throw new Error('condition_object_required');
  const structuralKeys = ['all', 'any', 'not'].filter((key) => Object.hasOwn(condition, key));
  if (structuralKeys.length > 1) throw new Error('condition_multiple_structural_operators');
  if (structuralKeys.length === 0) return normalizeLeaf(condition);
  const key = structuralKeys[0];
  if (Object.keys(condition).some((candidate) => candidate !== key)) throw new Error('condition_structural_mixed_fields');
  if (key === 'not') return { not: normalizeCondition(condition.not, depth + 1) };
  if (!Array.isArray(condition[key]) || condition[key].length === 0 || condition[key].length > 64) {
    throw new Error('condition_group_size_invalid');
  }
  return { [key]: condition[key].map((child) => normalizeCondition(child, depth + 1)) };
}

function validateRule(rule) {
  if (!isPlainObject(rule)) throw new Error('policy_rule_object_required');
  if (typeof rule.rule_id !== 'string' || !/^ct[.]rule[.][a-z0-9._-]{3,180}$/.test(rule.rule_id)) {
    throw new Error('policy_rule_id_invalid');
  }
  if (!Number.isSafeInteger(rule.priority) || rule.priority < 0 || rule.priority > 1_000_000) {
    throw new Error('policy_rule_priority_invalid');
  }
  if (!VALID_EFFECTS.has(rule.effect)) throw new Error('policy_rule_effect_invalid');
  if (typeof rule.reason_code !== 'string' || !/^[A-Z][A-Z0-9_]{2,120}$/.test(rule.reason_code)) {
    throw new Error('policy_rule_reason_code_invalid');
  }
  return {
    rule_id: rule.rule_id,
    priority: rule.priority,
    effect: rule.effect,
    reason_code: rule.reason_code,
    when: normalizeCondition(rule.when),
    metadata: isPlainObject(rule.metadata) ? rule.metadata : {},
  };
}

function validateHardBoundaries(boundaries) {
  const required = [
    'provider_write', 'production_rights_grant', 'credential_activation',
    'chain_broadcast', 'custody', 'money_movement', 'effective_price_publication',
    'checkout_activation', 'phase_advancement', 'merge_authorized',
  ];
  if (!isPlainObject(boundaries)) throw new Error('policy_hard_boundaries_required');
  for (const key of required) {
    if (boundaries[key] !== false) throw new Error(`policy_boundary_must_be_false:${key}`);
  }
  return Object.fromEntries(required.map((key) => [key, false]));
}

export function validatePolicyPackage(source) {
  if (!isPlainObject(source)) throw new Error('policy_package_object_required');
  if (source.schema_version !== '1.0.0') throw new Error('policy_schema_version_unsupported');
  if (typeof source.policy_id !== 'string' || !/^ct[.]policy[.][a-z0-9._-]{3,180}$/.test(source.policy_id)) {
    throw new Error('policy_id_invalid');
  }
  if (typeof source.semantic_version !== 'string' || !/^\d+\.\d+\.\d+$/.test(source.semantic_version)) {
    throw new Error('policy_semantic_version_invalid');
  }
  if (source.state !== 'CONTROLLED_TEST') throw new Error('policy_state_not_controlled_test');
  if (!isPlainObject(source.scope)) throw new Error('policy_scope_required');
  if (typeof source.scope.tenant_ref !== 'string' || source.scope.tenant_ref.length < 3 || source.scope.tenant_ref.length > 180) {
    throw new Error('policy_tenant_ref_invalid');
  }
  if (!Array.isArray(source.scope.pallets) || source.scope.pallets.length === 0 || source.scope.pallets.length > 64) {
    throw new Error('policy_pallet_scope_invalid');
  }
  if (new Set(source.scope.pallets).size !== source.scope.pallets.length) throw new Error('policy_pallet_scope_duplicate');
  if (!isPlainObject(source.defaults) || !VALID_EFFECTS.has(source.defaults.decision)) throw new Error('policy_default_decision_invalid');
  if (source.defaults.unknown !== 'HOLD') throw new Error('policy_unknown_must_hold');
  if (!Array.isArray(source.rules) || source.rules.length === 0 || source.rules.length > 500) throw new Error('policy_rules_invalid');
  const normalizedRules = source.rules.map(validateRule);
  const ids = normalizedRules.map((rule) => rule.rule_id);
  if (new Set(ids).size !== ids.length) throw new Error('policy_rule_id_duplicate');
  const hardBoundaries = validateHardBoundaries(source.hard_boundaries);
  return {
    schema_version: source.schema_version,
    policy_id: source.policy_id,
    semantic_version: source.semantic_version,
    state: source.state,
    scope: {
      tenant_ref: source.scope.tenant_ref,
      pallets: [...source.scope.pallets].sort(),
    },
    defaults: { decision: source.defaults.decision, unknown: 'HOLD' },
    rules: normalizedRules,
    metadata: isPlainObject(source.metadata) ? source.metadata : {},
    hard_boundaries: hardBoundaries,
  };
}

export function compilePolicyPackage(source) {
  const normalized = validatePolicyPackage(source);
  const sourceDigest = sha256Hex(canonicalize(normalized));
  const conflicts = [];
  const signatureMap = new Map();
  for (const rule of normalized.rules) {
    const signature = `${rule.priority}:${sha256Hex(canonicalize(rule.when))}`;
    const prior = signatureMap.get(signature);
    if (prior && prior.effect !== rule.effect) {
      conflicts.push({
        conflict_type: 'SAME_PRIORITY_SAME_CONDITION_DIFFERENT_EFFECT',
        first_rule_id: prior.rule_id,
        second_rule_id: rule.rule_id,
      });
    } else if (!prior) {
      signatureMap.set(signature, rule);
    }
  }
  if (conflicts.length > 0) {
    const error = new Error('policy_compile_conflict');
    error.conflicts = conflicts;
    throw error;
  }
  const compiledRules = [...normalized.rules]
    .sort((a, b) => b.priority - a.priority || a.rule_id.localeCompare(b.rule_id))
    .map((rule, index) => ({
      instruction: index,
      ...rule,
      condition_digest_sha256: sha256Hex(canonicalize(rule.when)),
    }));
  const artifactBody = {
    compiler_version: POLICY_COMPILER_VERSION,
    policy_id: normalized.policy_id,
    semantic_version: normalized.semantic_version,
    source_digest_sha256: sourceDigest,
    scope: normalized.scope,
    defaults: normalized.defaults,
    decision_precedence: ['DENY', 'HOLD', 'ALLOW'],
    rules: compiledRules,
    hard_boundaries: normalized.hard_boundaries,
  };
  return {
    ...artifactBody,
    compiled_digest_sha256: sha256Hex(canonicalize(artifactBody)),
  };
}

function getPath(context, path) {
  let current = context;
  for (const segment of path.split('.')) {
    if (current === null || current === undefined || typeof current !== 'object' || !Object.hasOwn(current, segment)) {
      return { exists: false, value: undefined };
    }
    current = current[segment];
  }
  return { exists: true, value: current };
}

function compareLeaf(condition, context) {
  const observed = getPath(context, condition.field);
  if (condition.op === 'exists') return (observed.exists === condition.value) ? TRI.TRUE : TRI.FALSE;
  if (!observed.exists || observed.value === null || observed.value === undefined) return TRI.UNKNOWN;
  const expected = condition.value;
  switch (condition.op) {
    case 'eq': return Object.is(observed.value, expected) ? TRI.TRUE : TRI.FALSE;
    case 'neq': return !Object.is(observed.value, expected) ? TRI.TRUE : TRI.FALSE;
    case 'in': return expected.some((item) => Object.is(item, observed.value)) ? TRI.TRUE : TRI.FALSE;
    case 'not_in': return expected.some((item) => Object.is(item, observed.value)) ? TRI.FALSE : TRI.TRUE;
    case 'gt':
    case 'gte':
    case 'lt':
    case 'lte': {
      if (typeof observed.value !== 'number' || typeof expected !== 'number' || !Number.isFinite(observed.value) || !Number.isFinite(expected)) return TRI.UNKNOWN;
      if (condition.op === 'gt') return observed.value > expected ? TRI.TRUE : TRI.FALSE;
      if (condition.op === 'gte') return observed.value >= expected ? TRI.TRUE : TRI.FALSE;
      if (condition.op === 'lt') return observed.value < expected ? TRI.TRUE : TRI.FALSE;
      return observed.value <= expected ? TRI.TRUE : TRI.FALSE;
    }
    case 'prefix': {
      if (typeof observed.value !== 'string' || typeof expected !== 'string') return TRI.UNKNOWN;
      return observed.value.startsWith(expected) ? TRI.TRUE : TRI.FALSE;
    }
    case 'contains': {
      if (typeof observed.value === 'string' && typeof expected === 'string') return observed.value.includes(expected) ? TRI.TRUE : TRI.FALSE;
      if (Array.isArray(observed.value)) return observed.value.some((item) => Object.is(item, expected)) ? TRI.TRUE : TRI.FALSE;
      return TRI.UNKNOWN;
    }
    default: throw new Error('condition_operator_runtime_unsupported');
  }
}

export function evaluateCondition(condition, context) {
  if (Object.hasOwn(condition, 'all')) {
    let unknown = false;
    for (const child of condition.all) {
      const result = evaluateCondition(child, context);
      if (result === TRI.FALSE) return TRI.FALSE;
      if (result === TRI.UNKNOWN) unknown = true;
    }
    return unknown ? TRI.UNKNOWN : TRI.TRUE;
  }
  if (Object.hasOwn(condition, 'any')) {
    let unknown = false;
    for (const child of condition.any) {
      const result = evaluateCondition(child, context);
      if (result === TRI.TRUE) return TRI.TRUE;
      if (result === TRI.UNKNOWN) unknown = true;
    }
    return unknown ? TRI.UNKNOWN : TRI.FALSE;
  }
  if (Object.hasOwn(condition, 'not')) {
    const result = evaluateCondition(condition.not, context);
    if (result === TRI.UNKNOWN) return TRI.UNKNOWN;
    return result === TRI.TRUE ? TRI.FALSE : TRI.TRUE;
  }
  return compareLeaf(condition, context);
}

export function evaluateCompiledPolicy(artifact, context, options = {}) {
  if (!isPlainObject(artifact) || artifact.compiler_version !== POLICY_COMPILER_VERSION) throw new Error('compiled_policy_artifact_invalid');
  if (!isPlainObject(context)) throw new Error('policy_context_object_required');
  const contextDigest = sha256Hex(canonicalize(context));
  const evaluations = artifact.rules.map((rule) => ({
    instruction: rule.instruction,
    rule_id: rule.rule_id,
    priority: rule.priority,
    effect: rule.effect,
    reason_code: rule.reason_code,
    result: evaluateCondition(rule.when, context),
  }));
  const trueRules = evaluations.filter((entry) => entry.result === TRI.TRUE);
  const unknownRules = evaluations.filter((entry) => entry.result === TRI.UNKNOWN);
  let decision;
  let reasonCode;
  let decisiveRuleIds = [];
  const trueDenies = trueRules.filter((entry) => entry.effect === 'DENY');
  const unknownDeniesOrHolds = unknownRules.filter((entry) => entry.effect === 'DENY' || entry.effect === 'HOLD');
  const trueHolds = trueRules.filter((entry) => entry.effect === 'HOLD');
  const unknownAllows = unknownRules.filter((entry) => entry.effect === 'ALLOW');
  const trueAllows = trueRules.filter((entry) => entry.effect === 'ALLOW');
  if (trueDenies.length > 0) {
    decision = 'DENY';
    reasonCode = trueDenies[0].reason_code;
    decisiveRuleIds = trueDenies.map((entry) => entry.rule_id);
  } else if (unknownDeniesOrHolds.length > 0) {
    decision = 'HOLD';
    reasonCode = 'POLICY_INPUT_UNKNOWN';
    decisiveRuleIds = unknownDeniesOrHolds.map((entry) => entry.rule_id);
  } else if (trueHolds.length > 0) {
    decision = 'HOLD';
    reasonCode = trueHolds[0].reason_code;
    decisiveRuleIds = trueHolds.map((entry) => entry.rule_id);
  } else if (unknownAllows.length > 0) {
    decision = 'HOLD';
    reasonCode = 'ALLOW_RULE_INPUT_UNKNOWN';
    decisiveRuleIds = unknownAllows.map((entry) => entry.rule_id);
  } else if (trueAllows.length > 0) {
    decision = 'ALLOW';
    reasonCode = trueAllows[0].reason_code;
    decisiveRuleIds = trueAllows.map((entry) => entry.rule_id);
  } else {
    decision = artifact.defaults.decision;
    reasonCode = `DEFAULT_${decision}`;
  }
  const receiptBody = {
    contract: 'ct.wallet.policy-decision-receipt.v1',
    policy_id: artifact.policy_id,
    policy_version: artifact.semantic_version,
    compiled_digest_sha256: artifact.compiled_digest_sha256,
    input_digest_sha256: contextDigest,
    decision,
    reason_code: reasonCode,
    decisive_rule_ids: decisiveRuleIds,
    rule_evaluations: options.includeRuleEvaluations === false ? [] : evaluations,
    hard_boundaries: {
      provider_write: false,
      production_rights_grant: false,
      credential_activation: false,
      chain_broadcast: false,
      custody: false,
      money_movement: false,
      effective_price_publication: false,
      checkout_activation: false,
      phase_advancement: false,
      merge_authorized: false,
    },
  };
  return {
    ...receiptBody,
    decision_digest_sha256: sha256Hex(canonicalize(receiptBody)),
  };
}

export function runScenarioMatrix(artifact, scenarios) {
  if (!Array.isArray(scenarios) || scenarios.length === 0 || scenarios.length > 100_000) throw new Error('scenario_matrix_size_invalid');
  const coverage = new Map(artifact.rules.map((rule) => [rule.rule_id, { true: 0, false: 0, unknown: 0 }]));
  const decisions = { ALLOW: 0, HOLD: 0, DENY: 0 };
  const reasonCounts = new Map();
  const receipts = scenarios.map((scenario, index) => {
    const receipt = evaluateCompiledPolicy(artifact, scenario, { includeRuleEvaluations: true });
    decisions[receipt.decision] += 1;
    reasonCounts.set(receipt.reason_code, (reasonCounts.get(receipt.reason_code) ?? 0) + 1);
    for (const result of receipt.rule_evaluations) {
      const bucket = coverage.get(result.rule_id);
      if (result.result === TRI.TRUE) bucket.true += 1;
      else if (result.result === TRI.FALSE) bucket.false += 1;
      else bucket.unknown += 1;
    }
    return { scenario_index: index, decision: receipt.decision, reason_code: receipt.reason_code, decision_digest_sha256: receipt.decision_digest_sha256 };
  });
  const summaryBody = {
    contract: 'ct.wallet.policy-simulation-summary.v1',
    policy_id: artifact.policy_id,
    compiled_digest_sha256: artifact.compiled_digest_sha256,
    scenario_count: scenarios.length,
    decisions,
    reason_counts: Object.fromEntries([...reasonCounts].sort(([a], [b]) => a.localeCompare(b))),
    rule_coverage: Object.fromEntries([...coverage].sort(([a], [b]) => a.localeCompare(b))),
    unreachable_rule_ids: [...coverage].filter(([, value]) => value.true === 0).map(([key]) => key),
    receipts,
    hard_boundaries: {
      provider_write: false,
      credential_activation: false,
      chain_broadcast: false,
      custody: false,
      money_movement: false,
      phase_advancement: false,
    },
  };
  return { ...summaryBody, simulation_digest_sha256: sha256Hex(canonicalize(summaryBody)) };
}

export { TRI };
