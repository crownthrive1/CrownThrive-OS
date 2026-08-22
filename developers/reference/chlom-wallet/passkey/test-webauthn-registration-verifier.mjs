import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync } from 'node:crypto';
import { encode } from 'cbor-x';
import { verifyWebAuthnRegistration } from './webauthn-registration-verifier.mjs';

const sha256 = (value) => createHash('sha256').update(value).digest();
const rpId = 'crownthrive.com';
const origin = 'https://wallet.crownthrive.com';
const challenge = Buffer.from('CHLOM-Wallet-Registration-Challenge-0001').toString('base64url');
const { publicKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
const jwk = publicKey.export({ format: 'jwk' });
const x = Buffer.from(jwk.x, 'base64url');
const y = Buffer.from(jwk.y, 'base64url');
const credentialId = Buffer.from('CHLOM-controlled-registration-credential-001');

function coseKey({ alg = -7, crv = 1, kty = 2 } = {}) {
  return new Map([
    [1, kty],
    [3, alg],
    [-1, crv],
    [-2, x],
    [-3, y],
  ]);
}

function buildRegistration({
  challengeValue = challenge,
  originValue = origin,
  rpIdValue = rpId,
  flags = 0x45,
  fmt = 'none',
  attStmt = {},
  cose = coseKey(),
} = {}) {
  const clientData = Buffer.from(JSON.stringify({
    type: 'webauthn.create',
    challenge: challengeValue,
    origin: originValue,
    crossOrigin: false,
  }), 'utf8');
  const coseBytes = Buffer.from(encode(cose));
  const authData = Buffer.alloc(55 + credentialId.length + coseBytes.length);
  sha256(Buffer.from(rpIdValue, 'utf8')).copy(authData, 0);
  authData[32] = flags;
  authData.writeUInt32BE(0, 33);
  Buffer.alloc(16, 0).copy(authData, 37); // all-zero AAGUID is valid for privacy-preserving authenticators
  authData.writeUInt16BE(credentialId.length, 53);
  credentialId.copy(authData, 55);
  coseBytes.copy(authData, 55 + credentialId.length);
  const attestationObject = Buffer.from(encode({ fmt, authData, attStmt }));
  return {
    expected_challenge: challenge,
    expected_origin: origin,
    expected_rp_id: rpId,
    client_data_json: clientData.toString('base64url'),
    attestation_object: attestationObject.toString('base64url'),
    require_user_verification: true,
  };
}

const valid = verifyWebAuthnRegistration(buildRegistration());
assert.equal(valid.ok, true);
assert.equal(valid.state, 'VERIFIED_REGISTRATION_CONTROLLED_TEST');
assert.equal(valid.attestation_format, 'none');
assert.equal(valid.user_present, true);
assert.equal(valid.user_verified, true);
assert.equal(valid.public_key_jwk.kty, 'EC');
assert.equal(valid.public_key_jwk.crv, 'P-256');
assert.equal(valid.public_key_jwk.alg, 'ES256');
assert.equal(valid.credential_commitment_sha256.length, 64);
assert.equal(valid.private_key_material_present, false);
assert.equal(valid.attestation_trust_claimed, false);
assert.equal(valid.production_credential_activation_authorized, false);
assert.equal(valid.smart_account_deployment_authorized, false);

const same = verifyWebAuthnRegistration(buildRegistration());
assert.equal(same.credential_commitment_sha256, valid.credential_commitment_sha256);

const wrongChallenge = verifyWebAuthnRegistration(buildRegistration({ challengeValue: Buffer.from('wrong-registration-challenge').toString('base64url') }));
assert.equal(wrongChallenge.ok, false);
assert.equal(wrongChallenge.reason, 'challenge_mismatch');

const wrongOrigin = verifyWebAuthnRegistration(buildRegistration({ originValue: 'https://evil.example' }));
assert.equal(wrongOrigin.ok, false);
assert.equal(wrongOrigin.reason, 'origin_mismatch');

const wrongRpHash = verifyWebAuthnRegistration(buildRegistration({ rpIdValue: 'other.example' }));
assert.equal(wrongRpHash.ok, false);
assert.equal(wrongRpHash.reason, 'rp_id_hash_mismatch');

const noUv = verifyWebAuthnRegistration(buildRegistration({ flags: 0x41 }));
assert.equal(noUv.ok, false);
assert.equal(noUv.reason, 'user_verification_required');

const noAttestedCredential = verifyWebAuthnRegistration(buildRegistration({ flags: 0x05 }));
assert.equal(noAttestedCredential.ok, false);
assert.equal(noAttestedCredential.reason, 'attested_credential_data_required');

const packed = verifyWebAuthnRegistration(buildRegistration({ fmt: 'packed' }));
assert.equal(packed.ok, false);
assert.equal(packed.reason, 'attestation_format_not_allowed_in_controlled_profile');

const noneWithStatement = verifyWebAuthnRegistration(buildRegistration({ attStmt: { alg: -7 } }));
assert.equal(noneWithStatement.ok, false);
assert.equal(noneWithStatement.reason, 'none_attestation_statement_must_be_empty');

const wrongAlg = verifyWebAuthnRegistration(buildRegistration({ cose: coseKey({ alg: -257 }) }));
assert.equal(wrongAlg.ok, false);
assert.equal(wrongAlg.reason, 'only_es256_p256_registration_supported');

console.log(JSON.stringify({
  result: 'PASS_WEBAUTHN_REGISTRATION_CONTROLLED_TEST',
  attestation_profile: 'none',
  cbor_attestation_parsed: true,
  rp_id_hash_bound: true,
  challenge_bound: true,
  origin_bound: true,
  user_presence_required: true,
  user_verification_required: true,
  es256_p256_cose_key_required: true,
  deterministic_credential_commitment: true,
  attestation_trust_claimed: false,
  production_credential_activation: false,
  smart_account_deployment: false,
}));
