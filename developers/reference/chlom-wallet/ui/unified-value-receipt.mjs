import { createHash } from 'node:crypto';

const sha256 = (value) => createHash('sha256').update(value).digest('hex');

const STATES = Object.freeze({
  money: new Set(['initiated', 'provider_pending', 'provider_succeeded', 'reconciled', 'allocated', 'externally_settled', 'refunded', 'disputed', 'held', 'not_applicable']),
  rights: new Set(['candidate', 'active', 'held', 'expired', 'revoked', 'superseded', 'not_applicable']),
  rewards: new Set(['candidate', 'earned', 'redeemed', 'reversed', 'expired', 'held', 'not_applicable']),
  impact: new Set(['calculated', 'approved', 'held', 'externally_settled', 'evidence_verified', 'reversed', 'cancelled', 'not_applicable']),
  proof: new Set(['not_anchored', 'candidate', 'confirmed_test', 'confirmed_production', 'failed', 'not_applicable']),
});

function requireState(leg, state) {
  if (!STATES[leg]?.has(state)) throw new Error(`${leg}_state_invalid`);
  return state;
}

export function buildUnifiedValueReceiptView(input) {
  if (!input || typeof input !== 'object') throw new Error('receipt_input_required');
  const stableId = String(input.stable_id ?? '');
  const walletId = String(input.wallet_id ?? '');
  if (!/^ct\.uvr\.[A-Za-z0-9._-]{1,128}$/.test(stableId)) throw new Error('stable_id_invalid');
  if (!/^ct\.wallet\.[A-Za-z0-9._-]{1,128}$/.test(walletId)) throw new Error('wallet_id_invalid');

  const money = {
    label: 'Money',
    asset: input.money?.asset ?? null,
    amount_minor: input.money?.amount_minor ?? null,
    state: requireState('money', String(input.money?.state ?? 'not_applicable')),
    provider_ref_visible: false,
  };
  const rights = {
    label: 'Rights',
    entitlement_ref: input.rights?.entitlement_ref ?? null,
    license_ref: input.rights?.license_ref ?? null,
    state: requireState('rights', String(input.rights?.state ?? 'not_applicable')),
  };
  const rewards = {
    label: 'Rewards',
    reward_ref: input.rewards?.reward_ref ?? null,
    state: requireState('rewards', String(input.rewards?.state ?? 'not_applicable')),
    cash_equivalent_inferred: false,
  };
  const impact = {
    label: 'Impact',
    obligation_ref: input.impact?.obligation_ref ?? null,
    state: requireState('impact', String(input.impact?.state ?? 'not_applicable')),
    disbursement_inferred: false,
  };
  const proof = {
    label: 'Proof',
    state: requireState('proof', String(input.proof?.state ?? 'not_anchored')),
    digest: input.proof?.digest ?? null,
    network_id: input.proof?.network_id ?? null,
    transaction_ref: input.proof?.transaction_ref ?? null,
  };

  if (rights.state === 'active' && !rights.entitlement_ref) throw new Error('active_rights_require_entitlement_ref');
  if (impact.state === 'externally_settled' && !input.impact?.settlement_evidence_ref) throw new Error('settled_impact_requires_evidence');
  if (proof.state.startsWith('confirmed_') && (!proof.digest || !proof.transaction_ref)) throw new Error('confirmed_proof_requires_digest_and_transaction');

  const canonical = {
    stable_id: stableId,
    wallet_id: walletId,
    source_event_ref: input.source_event_ref ?? null,
    money,
    rights,
    rewards,
    impact: { ...impact, settlement_evidence_ref: input.impact?.settlement_evidence_ref ?? null },
    proof,
    policy_version: String(input.policy_version ?? 'ct.policy.uvr.v1'),
  };
  return {
    ...canonical,
    receipt_digest: sha256(JSON.stringify(canonical)),
    semantic_merge: false,
    customer_explanation_ready: true,
  };
}

export function summarizeUnifiedValueReceipt(view) {
  if (!view?.receipt_digest) throw new Error('validated_receipt_view_required');
  return {
    title: 'CHLOM Value Receipt',
    sections: [view.money, view.rights, view.rewards, view.impact, view.proof],
    receipt_digest: view.receipt_digest,
    disclaimer: 'Each value class remains governed by its authoritative underlying record.',
  };
}
