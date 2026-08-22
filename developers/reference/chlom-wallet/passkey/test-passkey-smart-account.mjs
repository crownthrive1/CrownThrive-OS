import assert from 'node:assert/strict';
import {
  normalizeCaip2,
  normalizeCaip10,
  normalizeCredentialDescriptor,
  credentialCommitment,
  buildSmartAccountRegistrationIntent,
  bindDeployedAccountCandidate,
} from './passkey-smart-account.mjs';

assert.equal(normalizeCaip2('eip155', '11155111'), 'eip155:11155111');
assert.equal(normalizeCaip10('eip155:11155111', '0x1111111111111111111111111111111111111111'), 'eip155:11155111:0x1111111111111111111111111111111111111111');
assert.throws(() => normalizeCaip2('EIP155', '1'), /invalid_caip2/);
assert.throws(() => normalizeCaip10('eip155:1', 'not:valid'), /invalid_caip10/);

const credential = {
  credential_id: 'AQIDBAUGBwgJCgsMDQ4PEA_controlled_test',
  rp_id: 'wallet.crownthrive.com',
  origin: 'https://wallet.crownthrive.com',
  transports: ['internal', 'hybrid', 'internal'],
  cose_algorithm: -7,
  resident_key: true,
  user_verification: true,
};
const normalized = normalizeCredentialDescriptor(credential);
assert.deepEqual(normalized.transports, ['hybrid', 'internal']);
assert.equal(normalized.origin, 'https://wallet.crownthrive.com');

const commitment1 = credentialCommitment(credential);
const commitment2 = credentialCommitment({ ...credential, transports: ['hybrid', 'internal'] });
assert.equal(commitment1.commitment, commitment2.commitment);
assert.equal(commitment1.commitment.length, 64);
assert.equal(commitment1.raw_credential_exported, false);

const intent = buildSmartAccountRegistrationIntent({
  wallet_stable_id: 'ct.wallet.person.controlled-test',
  chain_namespace: 'eip155',
  chain_reference: '11155111',
  account_standard: 'ERC-7579',
  credential,
  factory_ref: 'ct.contract.factory.controlled-test',
  entrypoint_ref: 'ct.contract.entrypoint.controlled-test',
});
assert.equal(intent.chain_id, 'eip155:11155111');
assert.equal(intent.broadcast, false);
assert.equal(intent.deploy, false);
assert.equal(intent.money_movement, false);
assert.equal(intent.intent_digest.length, 64);

const bound = bindDeployedAccountCandidate(intent, '0x2222222222222222222222222222222222222222');
assert.equal(bound.chain_account_id, 'eip155:11155111:0x2222222222222222222222222222222222222222');
assert.equal(bound.verification_state, 'candidate_unverified');
assert.match(bound.authority_state, /^HOLD_/);

assert.throws(() => normalizeCredentialDescriptor({ ...credential, origin: 'http://wallet.crownthrive.com' }), /https_origin_required/);
assert.throws(() => normalizeCredentialDescriptor({ ...credential, origin: 'https://evil.example' }), /origin_rp_mismatch/);
assert.throws(() => buildSmartAccountRegistrationIntent({
  wallet_stable_id: 'ct.wallet.bad', chain_reference: '1', account_standard: 'UNKNOWN', credential,
}), /unsupported_account_standard/);

console.log(JSON.stringify({
  result: 'PASS',
  caip2: true,
  caip10: true,
  deterministic_credential_commitment: true,
  passkey_origin_binding: true,
  smart_account_intent_only: true,
  broadcast: false,
  deployment: false,
}));
