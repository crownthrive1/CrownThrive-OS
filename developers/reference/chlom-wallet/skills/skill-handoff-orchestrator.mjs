import { createHash } from 'node:crypto';

// CONTROLLED-TEST REFERENCE IMPLEMENTATION.
// Produces a deterministic, non-executing route plan only. It never creates
// authority, schedules work, accesses credentials, writes providers, moves
// money, grants rights, broadcasts, publishes prices, activates checkout,
// advances phases, authorizes merges, or casts votes.

export const ORCHESTRATION_VERSION = '1.0.0';
export const ORCHESTRATION_ENGINE_ID = 'ct.engine.chlom-wallet-skill-handoff-orchestration.v1';
export const POLICY_ENGINE_ID = 'ct.engine.chlom-wallet-policy-assurance.v1';

const SHA40 = /^[a-f0-9]{40}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const STABLE_ID = /^[A-Za-z0-9._:-]{3,160}$/;
const D_RANK = Object.freeze({ D0: 0, D1: 1, D2: 2, D3: 3 });
const A_RANK = Object.freeze({ A0: 0, A1: 1, A2: 2, A3: 3 });
const FORBIDDEN_EFFECTS = Object.freeze([
  'authority_grant', 'capability_grant', 'certification_authority',
  'checkout_activation', 'chain_broadcast', 'credential_access', 'custody',
  'effective_price_publication', 'merge_authorized', 'money_movement',
  'phase_advancement', 'production_activation', 'production_rights_grant',
  'provider_write', 'self_approval', 'sync_agents_authority', 'token_issuance',
  'vote_effect',
]);

// Deterministic lexical candidates. This is advisory classification, not AI authority.
const LEXICON = Object.freeze({
  'ct.skill.chlom-wallet.identity-stewardship.v1': ['wallet identity', 'stable wallet id', 'provider alias', 'identity binding', 'portability'],
  'ct.skill.chlom-wallet.provider-event-verification.v1': ['provider event', 'webhook signature', 'stripe event', 'raw body', 'replay protection'],
  'ct.skill.chlom-wallet.value-class-translation.v1': ['value class', 'semantic translation', 'money rights rewards impact proof'],
  'ct.skill.chlom-wallet.rights-eligibility.v1': ['rights eligibility', 'entitlement decision', 'license eligibility', 'terms version'],
  'ct.skill.chlom-wallet.allocation-preview.v1': ['allocation preview', 'basis points', 'economic split', 'settlement preview'],
  'ct.skill.chlom-wallet.thrivefund-obligation.v1': ['thrivefund obligation', 'impact obligation', 'impact evidence routing'],
  'ct.skill.chlom-wallet.unified-value-receipt.v1': ['unified value receipt', 'five lane receipt', 'customer receipt'],
  'ct.skill.chlom-wallet.ledger-chain-verification.v1': ['ledger chain', 'append only ledger', 'hash linkage', 'event sequence'],
  'ct.skill.chlom-wallet.passkey-registration.v1': ['passkey registration', 'webauthn registration', 'credential registration', 'attestation'],
  'ct.skill.chlom-wallet.passkey-assertion.v1': ['passkey assertion', 'webauthn assertion', 'credential assertion', 'counter policy'],
  'ct.skill.chlom-wallet.passkey-recovery.v1': ['passkey recovery', 'credential recovery', 'cooldown', 'replacement credential'],
  'ct.skill.chlom-wallet.erc4337-source-profile.v1': ['erc 4337 source', 'entrypoint source profile', 'source pinning', 'artifact lineage'],
  'ct.skill.chlom-wallet.chain-code-preflight.v1': ['chain code preflight', 'runtime codehash', 'read only chain', 'eth getcode'],
  'ct.skill.chlom-wallet.contract-verification.v1': ['contract verification', 'local evm', 'solidity compile', 'contract fuzz'],
  'ct.skill.chlom-wallet.provider-exit.v1': ['provider exit', 'provider portability', 'exit drill', 'paer'],
  'ct.skill.chlom-wallet.sdk-api-packaging.v1': ['sdk api packaging', 'openapi packaging', 'schema packaging', 'developer package'],
  'ct.skill.chlom-wallet.customer-projection.v1': ['customer wallet projection', 'wallet user interface', 'five lane wallet', 'accessibility'],
  'ct.skill.chlom-wallet.pricing-handoff.v1': ['pricing handoff', 'independent price review', 'price certification'],
  'ct.skill.chlom-wallet.incident-pause-rollback.v1': ['incident pause', 'wallet rollback', 'recovery rollback', 'emergency hold'],
  'ct.skill.chlom-wallet.security-threat-model.v1': ['security threat model', 'wallet threat model', 'security review', 'supply chain threat'],
});

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function sha256(value) {
  return createHash('sha256').update(typeof value === 'string' ? value : canonicalJson(value)).digest('hex');
}

function normalizeText(value) {
  return String(value ?? '').normalize('NFKC').toLowerCase()
    .replace(/[^a-z0-9._:-]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function assertObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
}

function assertId(value, code) {
  if (typeof value !== 'string' || !STABLE_ID.test(value)) throw new Error(code);
}

function normalizeSkill(raw) {
  assertObject(raw, 'skill_record_invalid');
  const handoffs = raw.primary_handoffs ?? raw.handoff_labels;
  assertId(raw.skill_id, 'skill_id_invalid');
  if (!Array.isArray(handoffs) || handoffs.length === 0 || handoffs.some((x) => typeof x !== 'string')) {
    throw new Error('skill_handoffs_invalid');
  }
  return {
    skill_id: raw.skill_id,
    name: raw.name ?? raw.skill_name ?? raw.skill_id,
    purpose: raw.purpose ?? '',
    skill_state: raw.skill_state ?? raw.state ?? 'CONTROLLED_TEST',
    authority_ceiling: raw.authority_ceiling ?? 'D2',
    primary_handoffs: [...handoffs],
  };
}

function normalizeCrosswalk(raw) {
  assertObject(raw, 'handoff_crosswalk_invalid');
  const rows = [];
  for (const item of raw.verified_handoffs ?? []) {
    rows.push({
      handoff_key: item.stable_agent_id,
      stable_agent_id: item.stable_agent_id,
      identity_state: item.identity_state,
      registry_binding_state: item.registry_binding_state,
      authority_ceiling: item.authority_ceiling,
      verified: true,
      allowed_use: 'bounded_non_voting_specialist_handoff',
    });
  }
  for (const item of raw.pending_role_aliases ?? []) {
    rows.push({
      handoff_key: item.legacy_alias,
      stable_agent_id: null,
      identity_state: item.identity_state,
      registry_binding_state: null,
      authority_ceiling: null,
      verified: false,
      allowed_use: item.allowed_use ?? 'non_executing_handoff_label_only',
    });
  }
  if (Array.isArray(raw.rows)) rows.push(...raw.rows);
  const index = new Map();
  for (const row of rows) {
    assertId(row.handoff_key, 'handoff_key_invalid');
    if (index.has(row.handoff_key)) throw new Error('duplicate_handoff_key');
    index.set(row.handoff_key, { ...row });
  }
  if (index.size === 0) throw new Error('handoff_crosswalk_empty');
  return index;
}

export function buildRegistryIndex(skillSuite, handoffCrosswalk) {
  assertObject(skillSuite, 'skill_suite_invalid');
  const rawSkills = skillSuite.skills ?? skillSuite.skill_definitions;
  if (!Array.isArray(rawSkills) || rawSkills.length === 0) throw new Error('skill_suite_empty');
  const skillIndex = new Map();
  for (const raw of rawSkills) {
    const skill = normalizeSkill(raw);
    if (skillIndex.has(skill.skill_id)) throw new Error('duplicate_skill_id');
    skillIndex.set(skill.skill_id, skill);
  }
  return {
    suite_id: skillSuite.suite_id ?? 'ct.skill-suite.chlom-wallet.v2',
    canonical_agent_id: skillSuite.canonical_agent_id ?? skillSuite.canonical_wallet_agent_id ?? 'ct.agent.chlom-wallet-settlement',
    skill_index: skillIndex,
    handoff_index: normalizeCrosswalk(handoffCrosswalk),
  };
}

export function classifyIntentAdvisory(intentText) {
  const normalized = normalizeText(intentText);
  const tokens = new Set(normalized.split(' ').filter(Boolean));
  const scores = [];
  for (const [skillId, terms] of Object.entries(LEXICON)) {
    let score = 0;
    const matched = [];
    for (const term of terms) {
      const normalizedTerm = normalizeText(term);
      if (normalized.includes(normalizedTerm)) {
        score += normalizedTerm.includes(' ') ? 5 : 2;
        matched.push(term);
      } else {
        const parts = normalizedTerm.split(' ');
        const tokenMatches = parts.filter((part) => tokens.has(part)).length;
        if (tokenMatches > 0) score += tokenMatches;
      }
    }
    if (score > 0) scores.push({ skill_id: skillId, score, matched_terms: [...new Set(matched)].sort() });
  }
  scores.sort((a, b) => b.score - a.score || a.skill_id.localeCompare(b.skill_id));
  const top = scores[0];
  const tied = top ? scores.filter((x) => x.score === top.score) : [];
  const disposition = !top ? 'HOLD_NO_SKILL_CANDIDATE' : tied.length > 1 ? 'HOLD_AMBIGUOUS_SKILL_CANDIDATE' : 'ADVISORY_CANDIDATE';
  const selected = disposition === 'ADVISORY_CANDIDATE' ? top.skill_id : null;
  const total = scores.reduce((sum, x) => sum + x.score, 0);
  return {
    algorithm_id: 'ct.algorithm.chlom-wallet.wisc.v1',
    disposition,
    selected_skill_id: selected,
    confidence_bps: selected && total > 0 ? Math.floor((top.score * 10000) / total) : 0,
    candidates: scores.slice(0, 5),
    normalized_intent_sha256: sha256(normalized),
    advisory_only: true,
    final_authority: false,
    creates_authority: false,
    creates_evidence: false,
    schedules_work: false,
  };
}

function validateRequest(request, exactHeadSha) {
  assertObject(request, 'route_request_invalid');
  assertId(request.request_id, 'request_id_invalid');
  if (!SHA40.test(exactHeadSha ?? '')) throw new Error('exact_head_sha_invalid');
  if (!SHA40.test(request.source_head_sha ?? '')) throw new Error('source_head_sha_invalid');
  const mode = request.requested_mode ?? 'PLAN_ONLY';
  const autonomy = request.requested_autonomy_ceiling ?? 'A0';
  const decision = request.requested_decision_ceiling ?? 'D0';
  if (!(autonomy in A_RANK) || !(decision in D_RANK)) throw new Error('authority_ceiling_invalid');
  if (mode !== 'PLAN_ONLY') return { autonomy, decision, hard_deny: 'DENY_NON_PLAN_MODE' };
  if (autonomy === 'A3' || decision === 'D3') return { autonomy, decision, hard_deny: 'DENY_HUMAN_RESERVED_AUTHORITY' };
  const requestedEffects = request.requested_effects ?? {};
  assertObject(requestedEffects, 'requested_effects_invalid');
  const crossed = FORBIDDEN_EFFECTS.filter((key) => requestedEffects[key] === true).sort();
  if (crossed.length > 0) return { autonomy, decision, hard_deny: 'DENY_FORBIDDEN_EFFECT_REQUEST', crossed_effects: crossed };
  return { autonomy, decision, hard_deny: null, crossed_effects: [] };
}

function heartbeatFresh(snapshot, now, freshnessSeconds) {
  if (snapshot.heartbeat_state !== 'FRESH') return false;
  const observed = Date.parse(snapshot.heartbeat_observed_at ?? '');
  const current = Date.parse(now);
  if (!Number.isFinite(observed) || !Number.isFinite(current) || observed > current) return false;
  return current - observed <= freshnessSeconds * 1000;
}

function assessOneHandoff(label, row, snapshotMap, exactHeadSha, requestedDecisionCeiling, now, freshnessSeconds) {
  if (!row) return { handoff_label: label, stable_agent_id: null, state: 'DENY_HANDOFF_NOT_REGISTERED', points: 0, execution_eligible: false };
  if (!row.verified || !row.stable_agent_id) {
    return { handoff_label: label, stable_agent_id: null, state: 'HOLD_PENDING_STABLE_ID_CROSSWALK', points: 0, execution_eligible: false, identity_state: row.identity_state };
  }
  if (row.registry_binding_state !== 'active') {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'HOLD_NON_ACTIVE_REGISTRY_BINDING', points: 20, execution_eligible: false, registry_binding_state: row.registry_binding_state };
  }
  const snapshot = snapshotMap?.[row.stable_agent_id];
  if (!snapshot) return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'HOLD_IDENTITY_EVIDENCE_MISSING', points: 20, execution_eligible: false };
  if (typeof snapshot.did_uri !== 'string' || !snapshot.did_uri.startsWith('did:')) {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'HOLD_DID_MISSING', points: 20, execution_eligible: false };
  }
  if (!SHA256.test(snapshot.public_identity_digest_sha256 ?? '')) {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'DENY_PUBLIC_IDENTITY_DIGEST_INVALID', points: 0, execution_eligible: false };
  }
  if (snapshot.head_sha !== exactHeadSha) {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'HOLD_HANDOFF_EXACT_HEAD_MISMATCH', points: 0, execution_eligible: false, observed_head_sha: snapshot.head_sha ?? null };
  }
  if (!heartbeatFresh(snapshot, now, freshnessSeconds)) {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'HOLD_HEARTBEAT_STALE_OR_MISSING', points: 30, execution_eligible: false, heartbeat_observed_at: snapshot.heartbeat_observed_at ?? null };
  }
  const registryCeiling = row.authority_ceiling;
  const observedCeiling = snapshot.authority_ceiling ?? registryCeiling;
  if (!(registryCeiling in D_RANK) || !(observedCeiling in D_RANK)) {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'DENY_HANDOFF_AUTHORITY_UNKNOWN', points: 0, execution_eligible: false };
  }
  if (D_RANK[registryCeiling] < D_RANK[requestedDecisionCeiling] || D_RANK[observedCeiling] < D_RANK[requestedDecisionCeiling]) {
    return { handoff_label: label, stable_agent_id: row.stable_agent_id, state: 'DENY_HANDOFF_AUTHORITY_CEILING', points: 0, execution_eligible: false };
  }
  return {
    handoff_label: label,
    stable_agent_id: row.stable_agent_id,
    state: 'READY_VERIFIED_ACTIVE_FRESH_EXACT_HEAD',
    points: 100,
    execution_eligible: false,
    plan_eligible: true,
    did_uri: snapshot.did_uri,
    public_identity_digest_sha256: snapshot.public_identity_digest_sha256,
    heartbeat_observed_at: snapshot.heartbeat_observed_at,
    authority_ceiling: observedCeiling,
  };
}

export function assessHandoffReadiness({ skill, handoffIndex, identitySnapshot = {}, exactHeadSha, requestedDecisionCeiling = 'D0', now, freshnessSeconds = 900 }) {
  const normalizedSkill = normalizeSkill(skill);
  if (!(requestedDecisionCeiling in D_RANK)) throw new Error('requested_decision_ceiling_invalid');
  if (!Number.isInteger(freshnessSeconds) || freshnessSeconds < 60 || freshnessSeconds > 86400) throw new Error('freshness_seconds_invalid');
  const assessments = normalizedSkill.primary_handoffs.map((label) => assessOneHandoff(
    label, handoffIndex.get(label), identitySnapshot, exactHeadSha,
    requestedDecisionCeiling, now, freshnessSeconds,
  ));
  const deny = assessments.some((x) => x.state.startsWith('DENY_'));
  const hold = assessments.some((x) => x.state.startsWith('HOLD_'));
  return {
    algorithm_id: 'ct.algorithm.chlom-wallet.harp.v1',
    disposition: deny ? 'DENY' : hold ? 'HOLD' : 'READY_FOR_POLICY_EVALUATION',
    readiness_score: assessments.length ? Math.floor(assessments.reduce((sum, x) => sum + x.points, 0) / assessments.length) : 0,
    handoff_count: assessments.length,
    ready_count: assessments.filter((x) => x.state.startsWith('READY_')).length,
    hold_count: assessments.filter((x) => x.state.startsWith('HOLD_')).length,
    deny_count: assessments.filter((x) => x.state.startsWith('DENY_')).length,
    assessments,
  };
}

function finalize(body) {
  return { ...body, route_digest_sha256: sha256(body) };
}

export function routeSkillHandoffPlan({ request, skillSuite, handoffCrosswalk, identitySnapshot = {}, exactHeadSha, now = new Date().toISOString(), freshnessSeconds = 900 }) {
  const registry = buildRegistryIndex(skillSuite, handoffCrosswalk);
  const validation = validateRequest(request, exactHeadSha);
  const base = {
    contract_version: ORCHESTRATION_VERSION,
    orchestration_engine_id: ORCHESTRATION_ENGINE_ID,
    downstream_policy_engine_id: POLICY_ENGINE_ID,
    request_id: request.request_id,
    suite_id: registry.suite_id,
    canonical_agent_id: registry.canonical_agent_id,
    source_head_sha: request.source_head_sha,
    exact_head_sha: exactHeadSha,
    observed_at: now,
    requested_mode: request.requested_mode ?? 'PLAN_ONLY',
    requested_autonomy_ceiling: validation.autonomy,
    requested_decision_ceiling: validation.decision,
    policy_evaluation_required: true,
    plan_only: true,
    execution_authorized: false,
    schedule_slot_created: false,
    capability_grant_created: false,
    authority_granted: false,
    certification_authority: false,
    credential_access: false,
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
    vote_effect: 'none',
    ai_final_authority: false,
  };
  if (validation.hard_deny) {
    return finalize({ ...base, disposition: 'DENY', reason_codes: [validation.hard_deny], crossed_effects: validation.crossed_effects ?? [], advisory: null, selected_skill: null, handoff_readiness: null });
  }
  if (request.source_head_sha !== exactHeadSha) {
    return finalize({ ...base, disposition: 'HOLD', reason_codes: ['HOLD_REQUEST_EXACT_HEAD_MISMATCH'], crossed_effects: [], advisory: null, selected_skill: null, handoff_readiness: null });
  }
  let advisory = null;
  let selectedSkillId = request.requested_skill_id ?? null;
  if (!selectedSkillId) {
    advisory = classifyIntentAdvisory(request.intent_text ?? '');
    if (advisory.disposition !== 'ADVISORY_CANDIDATE') {
      return finalize({ ...base, disposition: 'HOLD', reason_codes: [advisory.disposition], crossed_effects: [], advisory, selected_skill: null, handoff_readiness: null });
    }
    selectedSkillId = advisory.selected_skill_id;
  }
  assertId(selectedSkillId, 'requested_skill_id_invalid');
  const skill = registry.skill_index.get(selectedSkillId);
  if (!skill) return finalize({ ...base, disposition: 'DENY', reason_codes: ['DENY_UNKNOWN_SKILL_ID'], crossed_effects: [], advisory, selected_skill: { skill_id: selectedSkillId }, handoff_readiness: null });
  if (skill.skill_state !== 'CONTROLLED_TEST') return finalize({ ...base, disposition: 'HOLD', reason_codes: ['HOLD_SKILL_NOT_CONTROLLED_TEST'], crossed_effects: [], advisory, selected_skill: skill, handoff_readiness: null });
  if (!(skill.authority_ceiling in D_RANK) || D_RANK[skill.authority_ceiling] < D_RANK[validation.decision]) {
    return finalize({ ...base, disposition: 'DENY', reason_codes: ['DENY_SKILL_AUTHORITY_CEILING'], crossed_effects: [], advisory, selected_skill: skill, handoff_readiness: null });
  }
  const readiness = assessHandoffReadiness({ skill, handoffIndex: registry.handoff_index, identitySnapshot, exactHeadSha, requestedDecisionCeiling: validation.decision, now, freshnessSeconds });
  const reasons = readiness.assessments.filter((x) => !x.state.startsWith('READY_')).map((x) => x.state).sort();
  if (reasons.length === 0) reasons.push('READY_FOR_POLICY_ASSURANCE');
  return finalize({ ...base, disposition: readiness.disposition, reason_codes: [...new Set(reasons)], crossed_effects: [], advisory, selected_skill: skill, handoff_readiness: readiness });
}

export function verifyRouteReceipt(receipt) {
  assertObject(receipt, 'route_receipt_invalid');
  const { route_digest_sha256: digest, ...body } = receipt;
  if (!SHA256.test(digest ?? '')) return { valid: false, reason: 'route_digest_invalid_format' };
  if (sha256(body) !== digest) return { valid: false, reason: 'route_digest_mismatch' };
  const booleans = [
    'execution_authorized', 'schedule_slot_created', 'capability_grant_created',
    'authority_granted', 'certification_authority', 'credential_access',
    'provider_write', 'custody', 'token_issuance', 'money_movement',
    'production_rights_grant', 'chain_broadcast', 'effective_price_publication',
    'checkout_activation', 'phase_advancement', 'merge_authorized', 'ai_final_authority',
  ];
  const crossed = booleans.filter((key) => receipt[key] !== false);
  if (receipt.vote_effect !== 'none') crossed.push('vote_effect');
  return crossed.length > 0
    ? { valid: false, reason: 'route_boundary_crossed', crossed: crossed.sort() }
    : { valid: true, reason: 'PASS_CHLOM_WALLET_SKILL_HANDOFF_ROUTE_RECEIPT' };
}
