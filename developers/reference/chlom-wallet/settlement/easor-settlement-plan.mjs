import {
  assertAsciiIdentifier,
  assertHex64,
  assertIsoTimestamp,
  canonicalize,
  frameAscii,
  sha256Hex,
} from '../common/canonical-json.mjs';

// EASOR v1 — Economic Allocation Schedule & Obligation Resolver.
// CONTROLLED TEST: compiles obligation previews only. It never transfers, settles, grants rights, or disburses impact funds.

export const EASOR_SCHEMA_VERSION = '1.0.0';
const PLAN_DOMAIN = 'CHLOM:EASOR:PLAN:v1';
const REVERSAL_DOMAIN = 'CHLOM:EASOR:REVERSAL:v1';
const LEG_CLASSES = new Set(['platform', 'creator', 'tax_reserve', 'impact_obligation', 'affiliate', 'service', 'other']);
const SETTLEMENT_MODES = new Set(['external_settlement_candidate', 'internal_obligation', 'hold_only']);

function assertMinorAmount(value, code) {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(code);
  return value;
}

function normalizeRule(rule) {
  if (!rule || typeof rule !== 'object' || Array.isArray(rule)) throw new Error('easor_rule_object_required');
  const allowed = new Set(['leg_code', 'bps', 'beneficiary_ref', 'leg_class', 'settlement_mode', 'program_ref']);
  for (const key of Object.keys(rule)) if (!allowed.has(key)) throw new Error(`easor_rule_key_not_allowed:${key}`);
  const leg_code = assertAsciiIdentifier(rule.leg_code, 'easor_leg_code_invalid', 64);
  if (!Number.isInteger(rule.bps) || rule.bps < 0 || rule.bps > 10_000) throw new Error('easor_bps_invalid');
  const beneficiary_ref = assertAsciiIdentifier(rule.beneficiary_ref, 'easor_beneficiary_ref_invalid', 160);
  if (!LEG_CLASSES.has(rule.leg_class)) throw new Error('easor_leg_class_invalid');
  if (!SETTLEMENT_MODES.has(rule.settlement_mode)) throw new Error('easor_settlement_mode_invalid');
  const program_ref = rule.program_ref == null ? null : assertAsciiIdentifier(rule.program_ref, 'easor_program_ref_invalid', 160);
  if (rule.leg_class === 'impact_obligation' && !program_ref) throw new Error('easor_impact_program_ref_required');
  return { leg_code, bps: rule.bps, beneficiary_ref, leg_class: rule.leg_class, settlement_mode: rule.settlement_mode, program_ref };
}

export function normalizeEasorRules(rules) {
  if (!Array.isArray(rules) || rules.length < 1 || rules.length > 64) throw new Error('easor_rule_count_invalid');
  const normalized = rules.map(normalizeRule).sort((a, b) => a.leg_code.localeCompare(b.leg_code));
  let totalBps = 0;
  for (let index = 0; index < normalized.length; index++) {
    if (index > 0 && normalized[index - 1].leg_code === normalized[index].leg_code) throw new Error('easor_duplicate_leg_code');
    totalBps += normalized[index].bps;
  }
  if (totalBps !== 10_000) throw new Error('easor_allocation_bps_must_sum_to_10000');
  return normalized;
}

export function allocateLargestRemainder(grossMinor, rules) {
  const gross = assertMinorAmount(grossMinor, 'easor_gross_minor_invalid');
  const normalized = normalizeEasorRules(rules);
  const grossBig = BigInt(gross);
  const rows = normalized.map((rule) => {
    const numerator = grossBig * BigInt(rule.bps);
    return {
      ...rule,
      amount_minor: Number(numerator / 10_000n),
      _remainder: numerator % 10_000n,
    };
  });
  let allocated = rows.reduce((sum, row) => sum + row.amount_minor, 0);
  let remaining = gross - allocated;
  const priority = [...rows].sort((a, b) => {
    if (a._remainder === b._remainder) return a.leg_code.localeCompare(b.leg_code);
    return a._remainder > b._remainder ? -1 : 1;
  });
  for (let index = 0; index < remaining; index++) priority[index].amount_minor += 1;
  allocated = rows.reduce((sum, row) => sum + row.amount_minor, 0);
  if (allocated !== gross) throw new Error('easor_internal_conservation_failure');
  return rows.map(({ _remainder, ...row }) => row).sort((a, b) => a.leg_code.localeCompare(b.leg_code));
}

function normalizeRights(rights = []) {
  if (!Array.isArray(rights) || rights.length > 64) throw new Error('easor_rights_count_invalid');
  return rights.map((right) => {
    if (!right || typeof right !== 'object' || Array.isArray(right)) throw new Error('easor_right_object_required');
    const entitlement_candidate_ref = assertAsciiIdentifier(right.entitlement_candidate_ref, 'easor_entitlement_ref_invalid', 160);
    const asset_ref = assertAsciiIdentifier(right.asset_ref, 'easor_right_asset_ref_invalid', 160);
    const terms_digest = assertHex64(right.terms_digest, 'easor_right_terms_digest_invalid');
    return {
      entitlement_candidate_ref,
      asset_ref,
      terms_digest,
      state: 'HOLD_INDEPENDENT_RIGHTS_REQUIRED',
      rights_granted: false,
    };
  }).sort((a, b) => a.entitlement_candidate_ref.localeCompare(b.entitlement_candidate_ref));
}

function normalizeRewards(rewards = []) {
  if (!Array.isArray(rewards) || rewards.length > 64) throw new Error('easor_rewards_count_invalid');
  return rewards.map((reward) => {
    if (!reward || typeof reward !== 'object' || Array.isArray(reward)) throw new Error('easor_reward_object_required');
    const program_ref = assertAsciiIdentifier(reward.program_ref, 'easor_reward_program_ref_invalid', 160);
    const unit_code = assertAsciiIdentifier(reward.unit_code, 'easor_reward_unit_code_invalid', 64);
    const units = assertMinorAmount(reward.units, 'easor_reward_units_invalid');
    return {
      program_ref,
      unit_code,
      units,
      state: 'non_cash_candidate',
      cash_equivalent_inferred: false,
    };
  }).sort((a, b) => `${a.program_ref}:${a.unit_code}`.localeCompare(`${b.program_ref}:${b.unit_code}`));
}

export function compileSettlementPlan({
  plan_id,
  wallet_stable_id,
  asset_code,
  gross_minor,
  rules,
  rights = [],
  rewards = [],
  policy_version,
  created_at,
}) {
  const normalizedPlanId = assertAsciiIdentifier(plan_id, 'easor_plan_id_invalid', 160);
  const normalizedWalletId = assertAsciiIdentifier(wallet_stable_id, 'easor_wallet_stable_id_invalid', 160);
  const normalizedAsset = assertAsciiIdentifier(asset_code, 'easor_asset_code_invalid', 32);
  const normalizedPolicyVersion = assertAsciiIdentifier(policy_version, 'easor_policy_version_invalid', 96);
  const normalizedCreatedAt = assertIsoTimestamp(created_at, 'easor_created_at_invalid');
  const gross = assertMinorAmount(gross_minor, 'easor_gross_minor_invalid');
  const normalizedRules = normalizeEasorRules(rules);
  const legs = allocateLargestRemainder(gross, normalizedRules).map((leg) => ({
    ...leg,
    asset_code: normalizedAsset,
    obligation_state: 'calculated_hold',
    externally_settled: false,
  }));
  const rights_obligations = normalizeRights(rights);
  const reward_obligations = normalizeRewards(rewards);
  const impact_obligations = legs
    .filter((leg) => leg.leg_class === 'impact_obligation')
    .map((leg) => ({
      obligation_ref: `${normalizedPlanId}:${leg.leg_code}`,
      program_ref: leg.program_ref,
      asset_code: normalizedAsset,
      amount_minor: leg.amount_minor,
      state: 'calculated_not_settled',
      settlement_evidence_ref: null,
      impact_disbursed: false,
    }));
  const planCore = {
    schema_version: EASOR_SCHEMA_VERSION,
    plan_id: normalizedPlanId,
    wallet_stable_id: normalizedWalletId,
    asset_code: normalizedAsset,
    gross_minor: gross,
    policy_version: normalizedPolicyVersion,
    created_at: normalizedCreatedAt,
    rules: normalizedRules,
    legs,
    rights_obligations,
    reward_obligations,
    impact_obligations,
    execution_state: 'PREVIEW_HOLD',
    money_movement: false,
    provider_write: false,
    rights_granted: false,
    impact_disbursed: false,
  };
  const plan_digest = sha256Hex(frameAscii([PLAN_DOMAIN, sha256Hex(canonicalize(planCore))]));
  return { ...planCore, plan_digest };
}

function allocateAgainstCaps(totalMinor, originalLegs) {
  const total = assertMinorAmount(totalMinor, 'easor_reversal_minor_invalid');
  const caps = originalLegs.map((leg) => ({
    leg_code: leg.leg_code,
    cap: assertMinorAmount(leg.amount_minor, 'easor_original_leg_amount_invalid'),
  })).sort((a, b) => a.leg_code.localeCompare(b.leg_code));
  const originalTotal = caps.reduce((sum, row) => sum + row.cap, 0);
  if (total > originalTotal) throw new Error('easor_reversal_exceeds_original');
  if (originalTotal === 0) {
    if (total !== 0) throw new Error('easor_reversal_exceeds_original');
    return caps.map((row) => ({ leg_code: row.leg_code, reversal_amount_minor: 0 }));
  }
  const totalBig = BigInt(total);
  const originalBig = BigInt(originalTotal);
  const rows = caps.map((row) => {
    const numerator = totalBig * BigInt(row.cap);
    return {
      ...row,
      reversal_amount_minor: Number(numerator / originalBig),
      _remainder: numerator % originalBig,
    };
  });
  let allocated = rows.reduce((sum, row) => sum + row.reversal_amount_minor, 0);
  let remaining = total - allocated;
  const priority = [...rows].sort((a, b) => {
    if (a._remainder === b._remainder) return a.leg_code.localeCompare(b.leg_code);
    return a._remainder > b._remainder ? -1 : 1;
  });
  let cursor = 0;
  while (remaining > 0) {
    const row = priority[cursor % priority.length];
    if (row.reversal_amount_minor < row.cap) {
      row.reversal_amount_minor += 1;
      remaining -= 1;
    }
    cursor += 1;
    if (cursor > priority.length * 2 && remaining > 0 && priority.every((entry) => entry.reversal_amount_minor >= entry.cap)) {
      throw new Error('easor_reversal_capacity_failure');
    }
  }
  allocated = rows.reduce((sum, row) => sum + row.reversal_amount_minor, 0);
  if (allocated !== total || rows.some((row) => row.reversal_amount_minor > row.cap)) throw new Error('easor_reversal_conservation_failure');
  return rows.map(({ cap, _remainder, ...row }) => row).sort((a, b) => a.leg_code.localeCompare(b.leg_code));
}

export function compileReversalPlan({ reversal_id, original_plan, reversal_minor, reason_digest, created_at }) {
  const normalizedReversalId = assertAsciiIdentifier(reversal_id, 'easor_reversal_id_invalid', 160);
  if (!original_plan || typeof original_plan !== 'object') throw new Error('easor_original_plan_required');
  if (original_plan.schema_version !== EASOR_SCHEMA_VERSION || original_plan.execution_state !== 'PREVIEW_HOLD') throw new Error('easor_original_plan_invalid');
  assertHex64(original_plan.plan_digest, 'easor_original_plan_digest_invalid');
  const originalCore = { ...original_plan };
  delete originalCore.plan_digest;
  const expectedPlanDigest = sha256Hex(frameAscii([PLAN_DOMAIN, sha256Hex(canonicalize(originalCore))]));
  if (expectedPlanDigest !== original_plan.plan_digest) throw new Error('easor_original_plan_tampered');
  const reversal = assertMinorAmount(reversal_minor, 'easor_reversal_minor_invalid');
  if (reversal > original_plan.gross_minor) throw new Error('easor_reversal_exceeds_original');
  const reason = assertHex64(reason_digest, 'easor_reversal_reason_digest_invalid');
  const normalizedCreatedAt = assertIsoTimestamp(created_at, 'easor_reversal_created_at_invalid');
  const reversal_legs = allocateAgainstCaps(reversal, original_plan.legs).map((leg) => ({ ...leg, state: 'reversal_preview_hold' }));
  const core = {
    schema_version: EASOR_SCHEMA_VERSION,
    reversal_id: normalizedReversalId,
    original_plan_id: original_plan.plan_id,
    original_plan_digest: original_plan.plan_digest,
    asset_code: original_plan.asset_code,
    reversal_minor: reversal,
    reason_digest: reason,
    created_at: normalizedCreatedAt,
    reversal_legs,
    execution_state: 'PREVIEW_HOLD',
    provider_write: false,
    money_movement: false,
    rights_mutation: false,
    impact_settlement_mutation: false,
  };
  const reversal_digest = sha256Hex(frameAscii([REVERSAL_DOMAIN, sha256Hex(canonicalize(core))]));
  return { ...core, reversal_digest };
}
