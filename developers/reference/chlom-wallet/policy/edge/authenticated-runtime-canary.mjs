import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  assessWalletIntent,
  compileRulepack,
  sha256Hex,
  verifyDecisionReceipt,
} from './engine.mjs';

const EDGE_URL = process.env.CHLOM_WALLET_POLICY_EDGE_URL ?? '';
const EDGE_JWT = process.env.CHLOM_WALLET_POLICY_EDGE_JWT ?? '';
const ENABLE_EVALUATE = process.env.CHLOM_POLICY_CANARY_ENABLE_EVALUATE === 'true';
const EXPECTED_DISPOSITION = process.env.CHLOM_POLICY_CANARY_EXPECTED_DISPOSITION ?? '';
const ORIGIN = 'https://wallet.crownthrive.com';
const TIMEOUT_MS = 20_000;

if (!/^https:\/\/[a-z0-9-]+[.]supabase[.]co\/functions\/v1\/chlom-wallet-policy-assurance$/.test(EDGE_URL)) {
  throw new Error('policy_edge_url_invalid_or_missing');
}
if (EDGE_JWT.split('.').length !== 3 || EDGE_JWT.length < 80) {
  throw new Error('policy_edge_jwt_invalid_or_missing');
}
if (EXPECTED_DISPOSITION && !['ECAC', 'HOLD', 'DENY'].includes(EXPECTED_DISPOSITION)) {
  throw new Error('policy_expected_disposition_invalid');
}

const headers = {
  authorization: `Bearer ${EDGE_JWT}`,
  origin: ORIGIN,
  'content-type': 'application/json',
};

async function request(method, body = null, correlationId = null) {
  const response = await fetch(EDGE_URL, {
    method,
    headers: {
      ...headers,
      ...(correlationId ? { 'x-crownthrive-correlation-id': correlationId } : {}),
    },
    body: body == null ? null : JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const text = await response.text();
  let json;
  try {
    json = JSON.parse(text || '{}');
  } catch {
    throw new Error(`policy_edge_non_json_response:${response.status}`);
  }
  return { response, json };
}

const statusResult = await request('GET');
assert.equal(statusResult.response.status, 200);
assert.equal(statusResult.json.ok, true);
assert.equal(statusResult.json.service_id, 'ct.service.chlom-wallet-policy-assurance');
assert.equal(statusResult.json.state, 'CONTROLLED_TEST_ACTIVE');
assert.equal(statusResult.json.engine_id, 'ct.engine.chlom-wallet-policy-assurance.v1');
assert.equal(statusResult.json.engine_version, '1.0.0');
assert.equal(statusResult.json.rulepack_id, 'ct.rulepack.chlom-wallet.policy-assurance.v1');
assert.equal(statusResult.json.rulepack_version, '1.0.0');
assert.equal(statusResult.json.rulepack_sha256, 'c20767aaa8cce230d8b50af9c7a2b86e83bd7ffb65704c9af75f7d196da6a90b');
assert.deepEqual(statusResult.json.capabilities, ['status', 'evaluate', 'verify-receipt']);
assert.ok(Object.values(statusResult.json.hard_boundaries).every((value) => value === false));
assert.equal(statusResult.json.ai_advisory.enabled, false);
assert.equal(statusResult.json.ai_advisory.final_authority, false);

const rulepack = JSON.parse(readFileSync(new URL('../baseline-rulepack.v1.json', import.meta.url), 'utf8'));
const compiled = compileRulepack(rulepack);
const localIntent = {
  intent_id: 'ct.wallet.intent.runtime-canary.verify-receipt',
  action_type: 'provider_event_translate',
  value_class: 'money',
  environment: 'controlled_test',
  authority: {
    agent_id: 'ct.agent.chlom-wallet-settlement',
    autonomy_class: 'A2',
    decision_class: 'D2',
    self_approval: false,
    vote_effect: 'none',
    heartbeat_fresh: true,
    exact_head_bound: true,
  },
  evidence: ['provider_signature_verified', 'replay_state_verified', 'provider_event_allowlisted'].map((evidence_type) => ({
    evidence_type,
    state: 'verified',
    digest_sha256: sha256Hex(`runtime-canary:${evidence_type}`),
    source_ref: `runtime-canary:${evidence_type}`,
  })),
  requested_effects: {
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
  provider: { livemode: false, signature_verified: true, exact_replay: false, replay_state: 'UNIQUE' },
  semantics: {},
  passkey: {},
  chain: {},
  governance: {
    independent_review_required: false,
    phase_gate_required: false,
    rollback_plan_present: true,
    evidence_digest_bound: true,
  },
};
const localReceipt = assessWalletIntent(localIntent, compiled);
assert.equal(localReceipt.disposition, 'ECAC');
assert.equal(verifyDecisionReceipt(localReceipt).valid, true);

const verificationResult = await request('POST', { action: 'verify-receipt', receipt: localReceipt });
assert.equal(verificationResult.response.status, 200);
assert.equal(verificationResult.json.ok, true);
assert.equal(verificationResult.json.valid, true);
assert.ok(Object.values(verificationResult.json.hard_boundaries).every((value) => value === false));

const tampered = structuredClone(localReceipt);
tampered.risk_score = 100;
const tamperResult = await request('POST', { action: 'verify-receipt', receipt: tampered });
assert.equal(tamperResult.response.status, 422);
assert.equal(tamperResult.json.ok, false);
assert.equal(tamperResult.json.valid, false);

let evaluateEvidence = null;
if (ENABLE_EVALUATE) {
  const correlationId = `ct.wallet.policy.runtime-canary.${crypto.randomUUID()}`;
  const body = {
    action: 'evaluate',
    intent: {
      intent_id: `ct.wallet.intent.runtime-canary.evaluate.${crypto.randomUUID()}`,
      action_type: 'provider_event_translate',
      value_class: 'money',
      environment: 'controlled_test',
      evidence: localIntent.evidence,
      requested_effects: localIntent.requested_effects,
      provider: localIntent.provider,
      semantics: {},
      passkey: {},
      chain: {},
      governance: {
        independent_review_required: false,
        phase_gate_required: false,
        rollback_plan_present: true,
        evidence_digest_bound: true,
      },
    },
  };
  const first = await request('POST', body, correlationId);
  assert.equal(first.response.status, 200);
  assert.equal(first.json.ok, true);
  assert.equal(first.json.state, 'CONTROLLED_TEST_DECISION_RECORDED');
  assert.ok(['ECAC', 'HOLD', 'DENY'].includes(first.json.receipt.disposition));
  if (EXPECTED_DISPOSITION) assert.equal(first.json.receipt.disposition, EXPECTED_DISPOSITION);
  assert.equal(first.json.persistence.duplicate, false);
  assert.ok(Object.values(first.json.hard_boundaries).every((value) => value === false));

  const replay = await request('POST', body, correlationId);
  assert.equal(replay.response.status, 200);
  assert.equal(replay.json.ok, true);
  assert.equal(replay.json.persistence.duplicate, true);
  assert.equal(replay.json.persistence.receipt_sha256, first.json.persistence.receipt_sha256);
  evaluateEvidence = {
    disposition: first.json.receipt.disposition,
    correlation_id_sha256: sha256Hex(correlationId),
    receipt_sha256: first.json.receipt.receipt_sha256,
    exact_replay_duplicate: true,
  };
}

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_POLICY_AUTHENTICATED_RUNTIME_CANARY',
  service_id: 'ct.service.chlom-wallet-policy-assurance',
  status_verified: true,
  verify_receipt_verified: true,
  tampered_receipt_rejected: true,
  evaluate_enabled: ENABLE_EVALUATE,
  evaluate_evidence: evaluateEvidence,
  jwt_value_logged: false,
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
}));
