import assert from 'node:assert/strict';
import {
  createHash,
  generateKeyPairSync,
  sign,
} from 'node:crypto';
import { verifyWebAuthnAssertion } from './webauthn-assertion-verifier.mjs';

const sha256 = (value) => createHash('sha256').update(value).digest();
const rpId = 'crownthrive.com';
const origin = 'https://wallet.crownthrive.com';
const challenge = Buffer.from('CHLOM-Wallet-Controlled-Test-Challenge-0001').toString('base64url');
const { publicKey, privateKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
const publicJwk = publicKey.export({ format: 'jwk' });

function buildAssertion({
  challengeValue = challenge,
  originValue = origin,
  flags = 0x05,
  signCount = 1,
  rpHash = sha256(Buffer.from(rpId, 'utf8')),
} = {}) {
  const clientDataBytes = Buffer.from(JSON.stringify({
    type: 'webauthn.get',
    challenge: challengeValue,
    origin: originValue,
    crossOrigin: false,
  }), 'utf8');
  const authenticatorData = Buffer.alloc(37);
  rpHash.copy(authenticatorData, 0);
  authenticatorData[32] = flags;
  authenticatorData.writeUInt32BE(signCount, 33);
  const signedBytes = Buffer.concat([authenticatorData, sha256(clientDataBytes)]);
  const signature = sign('sha256', signedBytes, privateKey);
  return {
    expected_challenge: challenge,
    expected_origin: origin,
    expected_rp_id: rpId,
    client_data_json: clientDataBytes.toString('base64url'),
    authenticator_data: authenticatorData.toString('base64url'),
    signature: signature.toString('base64url'),
    public_key_jwk: publicJwk,
    stored_sign_count: 0,
    require_user_verification: true,
  };
}

const valid = buildAssertion();
const verified = verifyWebAuthnAssertion(valid);
assert.equal(verified.ok, true);
assert.equal(verified.state, 'VERIFIED_CONTROLLED_TEST');
assert.equal(verified.user_present, true);
assert.equal(verified.user_verified, true);
assert.equal(verified.sign_count, 1);
assert.equal(verified.counter_state, 'advanced');
assert.equal(verified.private_key_material_present, false);
assert.equal(verified.credential_activation_authorized, false);
assert.equal(verified.smart_account_deployment_authorized, false);

const wrongChallenge = verifyWebAuthnAssertion(buildAssertion({ challengeValue: Buffer.from('wrong challenge').toString('base64url') }));
assert.equal(wrongChallenge.ok, false);
assert.equal(wrongChallenge.reason, 'challenge_mismatch');

const wrongOrigin = verifyWebAuthnAssertion(buildAssertion({ originValue: 'https://evil.example' }));
assert.equal(wrongOrigin.ok, false);
assert.equal(wrongOrigin.reason, 'origin_mismatch');

const wrongRpHash = Buffer.from(sha256(Buffer.from('other.example')));
const rpMismatch = verifyWebAuthnAssertion(buildAssertion({ rpHash: wrongRpHash }));
assert.equal(rpMismatch.ok, false);
assert.equal(rpMismatch.reason, 'rp_id_hash_mismatch');

const noUv = verifyWebAuthnAssertion(buildAssertion({ flags: 0x01 }));
assert.equal(noUv.ok, false);
assert.equal(noUv.reason, 'user_verification_required');

const counterRollback = verifyWebAuthnAssertion({ ...valid, stored_sign_count: 1 });
assert.equal(counterRollback.ok, false);
assert.equal(counterRollback.reason, 'signature_counter_not_advanced');

const tamperedSignatureBytes = Buffer.from(valid.signature, 'base64url');
tamperedSignatureBytes[tamperedSignatureBytes.length - 1] ^= 0x01;
const badSignature = verifyWebAuthnAssertion({ ...valid, signature: tamperedSignatureBytes.toString('base64url') });
assert.equal(badSignature.ok, false);
assert.equal(badSignature.reason, 'signature_invalid');

const privateJwk = privateKey.export({ format: 'jwk' });
const privateKeyAttempt = verifyWebAuthnAssertion({ ...valid, public_key_jwk: privateJwk });
assert.equal(privateKeyAttempt.ok, false);
assert.equal(privateKeyAttempt.reason, 'private_key_material_forbidden');

const zeroCounterAssertion = buildAssertion({ signCount: 0 });
const zeroCounter = verifyWebAuthnAssertion(zeroCounterAssertion);
assert.equal(zeroCounter.ok, true);
assert.equal(zeroCounter.counter_state, 'not_supported_or_zero');

console.log(JSON.stringify({
  result: 'PASS_WEBAUTHN_ASSERTION_CRYPTO',
  es256_p256_signature_verified: true,
  challenge_bound: true,
  origin_bound: true,
  rp_id_hash_bound: true,
  user_presence_required: true,
  user_verification_required: true,
  counter_rollback_rejected: true,
  tamper_rejected: true,
  private_jwk_rejected: true,
  zero_counter_supported_without_false_claim: true,
  production_credential_activation: false,
  smart_account_deployment: false,
}));
