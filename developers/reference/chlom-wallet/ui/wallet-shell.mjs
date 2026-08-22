const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const ALLOWED_MONEY_STATES = new Set(['initiated','provider_pending','provider_succeeded','reconciled','allocated','externally_settled','refunded','disputed','held','not_applicable']);
const ALLOWED_RIGHTS_STATES = new Set(['candidate','active','held','expired','revoked','superseded','not_applicable']);
const ALLOWED_REWARD_STATES = new Set(['candidate','earned','redeemed','reversed','expired','held','not_applicable']);
const ALLOWED_IMPACT_STATES = new Set(['calculated','approved','held','externally_settled','evidence_verified','reversed','cancelled','not_applicable']);

function checkedState(value, allowed, label) {
  const state = String(value ?? 'not_applicable');
  if (!allowed.has(state)) throw new Error(`${label}_state_invalid`);
  return state;
}

function moneyDisplay(money) {
  const amountMinor = money?.amount_minor;
  const asset = String(money?.asset ?? '').toUpperCase();
  if (amountMinor == null || !asset) return null;
  if (!Number.isSafeInteger(amountMinor)) throw new Error('money_amount_minor_invalid');
  if (!/^[A-Z0-9._-]{2,16}$/.test(asset)) throw new Error('money_asset_invalid');
  if (asset === 'USD') return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amountMinor / 100);
  return `${amountMinor} ${asset}`;
}

export function createWalletShellModel(input) {
  if (!input || typeof input !== 'object') throw new Error('wallet_shell_input_required');
  const walletId = String(input.wallet_id ?? '');
  if (!/^ct\.wallet\.[A-Za-z0-9._-]{1,128}$/.test(walletId)) throw new Error('wallet_id_invalid');
  const receipts = Array.isArray(input.receipts) ? input.receipts : [];
  if (receipts.length > 100) throw new Error('receipt_window_too_large');

  const current = receipts[0] ?? {};
  const model = {
    wallet_id: walletId,
    title: String(input.title ?? 'CHLOM Wallet'),
    subtitle: String(input.subtitle ?? 'Money, rights, rewards, impact and proof in one governed view.'),
    money: {
      state: checkedState(current.money?.state, ALLOWED_MONEY_STATES, 'money'),
      display: moneyDisplay(current.money),
    },
    rights: {
      state: checkedState(current.rights?.state, ALLOWED_RIGHTS_STATES, 'rights'),
      entitlement_ref: current.rights?.entitlement_ref ?? null,
      license_ref: current.rights?.license_ref ?? null,
    },
    rewards: {
      state: checkedState(current.rewards?.state, ALLOWED_REWARD_STATES, 'rewards'),
      reward_ref: current.rewards?.reward_ref ?? null,
      cash_equivalent_inferred: false,
    },
    impact: {
      state: checkedState(current.impact?.state, ALLOWED_IMPACT_STATES, 'impact'),
      obligation_ref: current.impact?.obligation_ref ?? null,
      disbursement_inferred: false,
    },
    proof: {
      state: String(current.proof?.state ?? 'not_anchored'),
      receipt_digest: current.receipt_digest ?? null,
    },
    recent_receipts: receipts.slice(0, 10).map((receipt) => ({
      stable_id: receipt.stable_id ?? null,
      receipt_digest: receipt.receipt_digest ?? null,
      money_state: checkedState(receipt.money?.state, ALLOWED_MONEY_STATES, 'money'),
      rights_state: checkedState(receipt.rights?.state, ALLOWED_RIGHTS_STATES, 'rights'),
    })),
    provider_details_exposed: false,
    private_evidence_exposed: false,
    semantic_merge: false,
  };

  if (model.rights.state === 'active' && !model.rights.entitlement_ref) throw new Error('active_rights_require_entitlement_ref');
  if (model.impact.state === 'externally_settled' && !current.impact?.settlement_evidence_ref) throw new Error('settled_impact_requires_evidence');
  return model;
}

function card(id, title, primary, secondary) {
  return `<section class="chlom-wallet-card" aria-labelledby="${id}-title"><h2 id="${id}-title">${escapeHtml(title)}</h2><p class="chlom-wallet-primary">${escapeHtml(primary)}</p><p class="chlom-wallet-secondary">${escapeHtml(secondary)}</p></section>`;
}

export function renderWalletShell(model) {
  if (!model?.wallet_id || model.provider_details_exposed !== false || model.private_evidence_exposed !== false) {
    throw new Error('validated_public_wallet_model_required');
  }
  const rightsSecondary = model.rights.state === 'active'
    ? `Entitlement ${model.rights.entitlement_ref}`
    : 'No active right is inferred from payment status.';
  const recent = model.recent_receipts.length === 0
    ? '<p>No recent governed receipts.</p>'
    : `<ol>${model.recent_receipts.map((r) => `<li><span>${escapeHtml(r.stable_id ?? 'Receipt')}</span><span>Money: ${escapeHtml(r.money_state)}</span><span>Rights: ${escapeHtml(r.rights_state)}</span></li>`).join('')}</ol>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(model.title)}</title></head><body><main class="chlom-wallet-shell" aria-labelledby="wallet-title"><header><p class="chlom-wallet-eyebrow">CrownThrive · CHLOM</p><h1 id="wallet-title">${escapeHtml(model.title)}</h1><p>${escapeHtml(model.subtitle)}</p></header><div class="chlom-wallet-grid">${card('money','Money',model.money.display ?? 'No current money amount',`State: ${model.money.state}`)}${card('rights','Rights',`State: ${model.rights.state}`,rightsSecondary)}${card('rewards','Rewards',`State: ${model.rewards.state}`,'Rewards are not presented as cash or ownership by inference.')}${card('impact','Impact',`State: ${model.impact.state}`,'Impact obligations remain distinct from verified external settlement.')}${card('proof','Proof',`State: ${model.proof.state}`,model.proof.receipt_digest ? `Receipt fingerprint ${model.proof.receipt_digest}` : 'No anchor or receipt fingerprint is currently shown.')}</div><section aria-labelledby="recent-title"><h2 id="recent-title">Recent value receipts</h2>${recent}</section><p role="status" aria-live="polite">Wallet view loaded. Provider complexity remains behind CHLOM governance.</p></main></body></html>`;
}
