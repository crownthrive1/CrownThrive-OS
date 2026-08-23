import { canonicalize, sha256Hex } from './policy-engine.mjs';

const PROPOSAL_TYPES = new Set([
  'RESOLVE_MISSING_POLICY_INPUTS',
  'REVIEW_ZERO_LIMIT',
  'REVIEW_LIMIT_SATURATION',
  'ADD_EXPLICIT_DENY_RULE',
  'ADD_SCENARIO_COVERAGE',
  'NO_CHANGE_RECOMMENDED',
]);

function percentage(numerator, denominator) {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0) return 0;
  return numerator / denominator;
}

export function generatePolicyAdvisorProposal({
  policy_id,
  compiled_digest_sha256,
  simulation_summary,
  meter_snapshots = [],
  risk_signals = [],
}) {
  if (typeof policy_id !== 'string' || !/^ct[.]policy[.]/.test(policy_id)) throw new Error('advisor_policy_id_invalid');
  if (!/^[0-9a-f]{64}$/.test(compiled_digest_sha256)) throw new Error('advisor_compiled_digest_invalid');
  if (!simulation_summary || typeof simulation_summary !== 'object') throw new Error('advisor_simulation_summary_required');
  if (!Array.isArray(meter_snapshots) || !Array.isArray(risk_signals)) throw new Error('advisor_inputs_invalid');

  const scenarioCount = Number(simulation_summary.scenario_count ?? 0);
  const decisions = simulation_summary.decisions ?? {};
  const reasonCounts = simulation_summary.reason_counts ?? {};
  const proposals = [];
  const unknownCount = Object.entries(reasonCounts)
    .filter(([reason]) => reason.includes('UNKNOWN') || reason.includes('UNRESOLVED'))
    .reduce((total, [, count]) => total + Number(count || 0), 0);
  const unknownRatio = percentage(unknownCount, scenarioCount);
  if (unknownRatio >= 0.01) {
    proposals.push({
      proposal_type: 'RESOLVE_MISSING_POLICY_INPUTS',
      priority_score: Math.min(100, Math.round(55 + unknownRatio * 100)),
      rationale_code: 'SIMULATION_UNKNOWN_RATIO_ABOVE_THRESHOLD',
      evidence: { unknown_count: unknownCount, scenario_count: scenarioCount, unknown_ratio: unknownRatio },
      suggested_change: { operation: 'REVIEW_REQUIRED_FIELDS_AND_DEFAULTS', auto_apply: false },
    });
  }

  for (const meter of meter_snapshots) {
    const limit = meter.limit;
    const used = Number(meter.used ?? 0);
    if (limit === 0 && used > 0) {
      proposals.push({
        proposal_type: 'REVIEW_ZERO_LIMIT',
        priority_score: 95,
        rationale_code: 'OBSERVED_USAGE_CONFLICTS_WITH_ZERO_LIMIT',
        evidence: { meter_id: meter.meter_id, limit, used },
        suggested_change: { operation: 'INVESTIGATE_USAGE_OR_LIMIT_CONFIGURATION', auto_apply: false },
      });
    } else if (Number.isSafeInteger(limit) && limit > 0 && used / limit >= 0.8) {
      proposals.push({
        proposal_type: 'REVIEW_LIMIT_SATURATION',
        priority_score: Math.min(94, Math.round(60 + (used / limit) * 35)),
        rationale_code: 'BOUNDED_LIMIT_SATURATION_ABOVE_80_PERCENT',
        evidence: { meter_id: meter.meter_id, limit, used, saturation: used / limit },
        suggested_change: { operation: 'CAPACITY_AND_PLAN_REVIEW', auto_apply: false },
      });
    } else if (limit === null) {
      proposals.push({
        proposal_type: 'RESOLVE_MISSING_POLICY_INPUTS',
        priority_score: 90,
        rationale_code: 'METER_LIMIT_UNRESOLVED_FAIL_CLOSED',
        evidence: { meter_id: meter.meter_id, limit: null, used },
        suggested_change: { operation: 'RESOLVE_LIMIT_WITH_INDEPENDENT_OFFER_REVIEW', auto_apply: false },
      });
    }
  }

  for (const signal of risk_signals) {
    if (!signal || typeof signal !== 'object') continue;
    if (signal.signal_type === 'UNMAPPED_CONSEQUENTIAL_ACTION') {
      proposals.push({
        proposal_type: 'ADD_EXPLICIT_DENY_RULE',
        priority_score: 100,
        rationale_code: 'CONSEQUENTIAL_ACTION_LACKS_EXPLICIT_RULE',
        evidence: { action: signal.action ?? 'unknown', signal_digest_sha256: signal.signal_digest_sha256 ?? null },
        suggested_change: { operation: 'ADD_DENY_OR_HOLD_RULE', auto_apply: false },
      });
    }
    if (signal.signal_type === 'UNCOVERED_RULE_PATH') {
      proposals.push({
        proposal_type: 'ADD_SCENARIO_COVERAGE',
        priority_score: 75,
        rationale_code: 'RULE_PATH_HAS_NO_TEST_SCENARIO',
        evidence: { rule_id: signal.rule_id ?? 'unknown' },
        suggested_change: { operation: 'ADD_CONTROLLED_TEST_SCENARIO', auto_apply: false },
      });
    }
  }

  if (proposals.length === 0) {
    proposals.push({
      proposal_type: 'NO_CHANGE_RECOMMENDED',
      priority_score: 1,
      rationale_code: 'NO_ACTIONABLE_GAP_IN_SUPPLIED_EVIDENCE',
      evidence: { scenario_count: scenarioCount, decisions },
      suggested_change: { operation: 'NONE', auto_apply: false },
    });
  }

  const deduped = new Map();
  for (const proposal of proposals) {
    if (!PROPOSAL_TYPES.has(proposal.proposal_type)) throw new Error('advisor_proposal_type_invalid');
    const key = `${proposal.proposal_type}:${sha256Hex(canonicalize(proposal.evidence))}`;
    const prior = deduped.get(key);
    if (!prior || proposal.priority_score > prior.priority_score) deduped.set(key, proposal);
  }
  const ranked = [...deduped.values()]
    .sort((a, b) => b.priority_score - a.priority_score || a.proposal_type.localeCompare(b.proposal_type))
    .map((proposal, index) => ({ rank: index + 1, ...proposal }));

  const body = {
    contract: 'ct.wallet.algorithmic-policy-advisor.v1',
    algorithm_id: 'ct.algorithm.chlom-wallet.aura.v1',
    policy_id,
    compiled_digest_sha256,
    proposal_state: 'SUGGESTION_ONLY',
    model_provider: null,
    external_model_call_performed: false,
    proposals: ranked,
    authority: {
      auto_apply: false,
      policy_activation: false,
      effective_offer_change: false,
      provider_write: false,
      rights_grant: false,
      chain_broadcast: false,
      money_movement: false,
      phase_advancement: false,
    },
  };
  return { ...body, proposal_digest_sha256: sha256Hex(canonicalize(body)) };
}
