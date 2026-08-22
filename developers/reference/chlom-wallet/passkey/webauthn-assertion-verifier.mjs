import {
  createHash,
  createPublicKey,
  verify as verifySignature,
  timingSafeEqual,
} from 'node:crypto';

const MAX_CLIENT_DATA_BYTES = 16_384;
const MAX_AUTH_DATA_BYTES = 4_096;
const MAX_SIGNATURE_BYTES = 1_024;

const b64urlToBuffer = (value, maxBytes, label) => {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error(`${label}_base64url_invalid`);
  const buffer = Buffer.from(value, 'base64url');
  if (buffer.length === 0 || buffer.length > maxBytes) throw new Error(`${label}_size_invalid`);
  return buffer;
};
const sha256 = (value) => createHash('sha256').update(value).digest();
const safeEqual = (a, b) => a.length === b.length && timingSafeEqual(a, b);

export function validatePublicKeyJwk(jwk) {
  if (!jwk || typeof jwk !== 'object') throw new Error('public_key_jwk_required');
  if (jwk.kty !== 'EC' || jwk.crv !== 'P-256') throw new Error('only_es256_p256_supported');
  if (typeof jwk.x !== 'string' || typeof jwk.y !== 'string') throw new Error('public_key_coordinates_required');
  b64urlToBuffer(jwk.x, 64, 'public_key_x');
  b64urlToBuffer(jwk.y, 64, 'public_key_y');
  if (jwk.d != null) throw new Error('private_key_material_forbidden');
  return { ...jwk, alg: 'ES256', ext: true };
}

export function parseAuthenticatorData(authenticatorDataB64url) {
  const bytes = b64urlToBuffer(authenticatorDataB64url, MAX_AUTH_DATA_BYTES, 'authenticator_data');
  if (bytes.length < 37) throw new Error('authenticator_data_too_short');
  const rpIdHash = bytes.subarray(0, 32);
  const flags = bytes[32];
  const signCount = bytes.readUInt32BE(33);
  return {
    bytes,
    rp_id_hash: rpIdHash,
    flags,
    user_present: Boolean(flags & 0x01),
    user_verified: Boolean(flags & 0x04),
    backup_eligible: Boolean(flags & 0x08),
    backup_state: Boolean(flags & 0x10),
    attested_credential_data: Boolean(flags & 0x40),
    extension_data: Boolean(flags & 0x80),
    sign_count: signCount,
  };
}

export function verifyWebAuthnAssertion(input) {
  if (!input || typeof input !== 'object') throw new Error('assertion_input_required');
  const expectedChallenge = String(input.expected_challenge ?? '');
  const expectedOrigin = String(input.expected_origin ?? '');
  const expectedRpId = String(input.expected_rp_id ?? '').toLowerCase();
  if (!/^[A-Za-z0-9_-]{16,1024}$/.test(expectedChallenge)) throw new Error('expected_challenge_invalid');
  let origin;
  try { origin = new URL(expectedOrigin); } catch { throw new Error('expected_origin_invalid'); }
  if (origin.protocol !== 'https:') throw new Error('https_origin_required');
  if (!/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(expectedRpId)) throw new Error('expected_rp_id_invalid');
  if (origin.hostname !== expectedRpId && !origin.hostname.endsWith(`.${expectedRpId}`)) throw new Error('origin_rp_mismatch');

  const clientDataBytes = b64urlToBuffer(input.client_data_json, MAX_CLIENT_DATA_BYTES, 'client_data_json');
  let clientData;
  try { clientData = JSON.parse(clientDataBytes.toString('utf8')); }
  catch { return { ok: false, state: 'HOLD', reason: 'client_data_json_invalid' }; }
  if (clientData.type !== 'webauthn.get') return { ok: false, state: 'HOLD', reason: 'client_data_type_invalid' };
  if (clientData.challenge !== expectedChallenge) return { ok: false, state: 'HOLD', reason: 'challenge_mismatch' };
  if (clientData.origin !== origin.origin) return { ok: false, state: 'HOLD', reason: 'origin_mismatch' };
  if (clientData.crossOrigin === true) return { ok: false, state: 'HOLD', reason: 'cross_origin_not_allowed' };

  const auth = parseAuthenticatorData(input.authenticator_data);
  const expectedRpHash = sha256(Buffer.from(expectedRpId, 'utf8'));
  if (!safeEqual(auth.rp_id_hash, expectedRpHash)) return { ok: false, state: 'HOLD', reason: 'rp_id_hash_mismatch' };
  if (!auth.user_present) return { ok: false, state: 'HOLD', reason: 'user_presence_required' };
  if (input.require_user_verification !== false && !auth.user_verified) return { ok: false, state: 'HOLD', reason: 'user_verification_required' };

  const storedSignCount = Number(input.stored_sign_count ?? 0);
  if (!Number.isSafeInteger(storedSignCount) || storedSignCount < 0 || storedSignCount > 0xffffffff) throw new Error('stored_sign_count_invalid');
  let counterState = 'not_supported_or_zero';
  if (storedSignCount > 0 || auth.sign_count > 0) {
    if (auth.sign_count <= storedSignCount) return { ok: false, state: 'HOLD', reason: 'signature_counter_not_advanced', sign_count: auth.sign_count, stored_sign_count: storedSignCount };
    counterState = 'advanced';
  }

  let publicKey;
  try { publicKey = createPublicKey({ key: validatePublicKeyJwk(input.public_key_jwk), format: 'jwk' }); }
  catch (error) { return { ok: false, state: 'HOLD', reason: error instanceof Error ? error.message : 'public_key_invalid' }; }
  const signature = b64urlToBuffer(input.signature, MAX_SIGNATURE_BYTES, 'signature');
  const clientDataHash = sha256(clientDataBytes);
  const signedBytes = Buffer.concat([auth.bytes, clientDataHash]);
  const signatureValid = verifySignature('sha256', signedBytes, publicKey, signature);
  if (!signatureValid) return { ok: false, state: 'HOLD', reason: 'signature_invalid' };

  return {
    ok: true,
    state: 'VERIFIED_CONTROLLED_TEST',
    reason: 'assertion_verified',
    user_present: auth.user_present,
    user_verified: auth.user_verified,
    backup_eligible: auth.backup_eligible,
    backup_state: auth.backup_state,
    sign_count: auth.sign_count,
    counter_state: counterState,
    rp_id: expectedRpId,
    origin: origin.origin,
    client_data_digest: sha256(clientDataBytes).toString('hex'),
    authenticator_data_digest: sha256(auth.bytes).toString('hex'),
    signature_digest: sha256(signature).toString('hex'),
    private_key_material_present: false,
    credential_activation_authorized: false,
    smart_account_deployment_authorized: false,
  };
}
