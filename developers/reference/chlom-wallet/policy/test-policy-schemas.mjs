import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {
  assessWalletIntent,
  buildPolicyAssuranceStatus,
  compileRulepack,
  sha256Hex,
} from './chlom-wallet-policy-assurance.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false });
addFormats(ajv);
const load = (name) => JSON.parse(readFileSync(join(HERE, 'schemas', name), 'utf8'));
const validateRulepack = ajv.compile(load('policy-rulepack.v1.schema.json'));
const validateIntent = ajv.compile(load('policy-intent.v1.schema.json'));
const validateReceipt = ajv.compile(load('policy-decision-receipt.v1.schema.json'));
const validateStatus = ajv.compile(load('policy-assurance-status.v1.schema.json'));
const rulepack = JSON.parse(readFileSync(join(HERE, 'baseline-rulepack.v1.json'), 'utf8'));
assert.equal(validateRulepack(rulepack), true, JSON.stringify(validateRulepack.errors));

const intent = {
  intent_id: 'ct.wallet.intent.schema.controlled-test',
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
    digest_sha256: sha256Hex(evidence_type),
    source_ref: `schema:${evidence_type}`,
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
  governance: {
    independent_review_required: false,
    phase_gate_required: false,
    rollback_plan_present: true,
    evidence_digest_bound: true,
  },
  provider: { livemode: false, signature_verified: true, exact_replay: false, replay_state: 'UNIQUE' },
  semantics: {},
  passkey: {},
  chain: {},
};
assert.equal(validateIntent(intent), true, JSON.stringify(validateIntent.errors));
const compiled = compileRulepack(rulepack);
const receipt = assessWalletIntent(intent, compiled);
assert.equal(validateReceipt(receipt), true, JSON.stringify(validateReceipt.errors));
const status = buildPolicyAssuranceStatus(compiled, {
  compiled_rulepacks: 1,
  decision_receipts: 0,
  chaos_cases: 50000,
  invariant_failures: 0,
});
assert.equal(validateStatus(status), true, JSON.stringify(validateStatus.errors));

const badRulepack = structuredClone(rulepack);
badRulepack.allowed_environments.push('production');
assert.equal(validateRulepack(badRulepack), false);
const badIntent = structuredClone(intent);
badIntent.environment = 'production';
assert.equal(validateIntent(badIntent), false);
const badReceipt = structuredClone(receipt);
badReceipt.execution_envelope.money_movement = true;
assert.equal(validateReceipt(badReceipt), false);
const badStatus = structuredClone(status);
badStatus.hard_boundaries.chain_broadcast = true;
assert.equal(validateStatus(badStatus), false);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_POLICY_ASSURANCE_SCHEMAS',
  rulepack_validated: true,
  intent_validated: true,
  decision_receipt_validated: true,
  public_status_validated: true,
  production_rulepack_rejected: true,
  production_intent_rejected: true,
  money_movement_receipt_rejected: true,
  chain_broadcast_status_rejected: true,
}));
