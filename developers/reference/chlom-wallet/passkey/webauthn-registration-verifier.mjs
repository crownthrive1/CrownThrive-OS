import { createHash, createPublicKey } from 'node:crypto';
import { decode } from 'cbor-x';

const MAX_CLIENT_DATA_BYTES = 16_384;
const MAX_ATTESTATION_OBJECT_BYTES = 32_768;
const MAX_CREDENTIAL_ID_BYTES = 1024;

const sha256 = (value) => createHash('sha256').update(value).digest();
const b64urlToBuffer = (value, maxBytes, label) => {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error(`${label}_base64url_invalid`);
  const out = Buffer.from(value, 'base64url');
  if (out.length === 0 || out.length > maxBytes) throw new Error(`${label}_size_invalid`);
  return out;
};
const safeHost = (value) => /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(value);
const mapGet = (value, key) => value instanceof Map ? value.get(key) : value?.[key];

function toBuffer(value, label, expectedBytes = null) {
  const out = Buffer.isBuffer(value) ? value : value instanceof Uint8Array ? Buffer.from(value) : null;
  if (!out) throw new Error(`${label}_bytes_required`);
  if (expectedBytes !== null && out.length !== expectedBytes) throw new Error(`${label}_length_invalid`);
  return out;
}

export function parseAttestedCredentialData(authData) {
  const bytes = toBuffer(authData, 'auth_data');
  if (bytes.length < 55) throw new Error('auth_data_too_short_for_attested_credential');
  const rpIdHash = bytes.subarray(0, 32);
  const flags = bytes[32];
  const signCount = bytes.readUInt32BE(33);
  const userPresent = Boolean(flags & 0x01);
  const userVerified = Boolean(flags & 0x04);
  const attestedCredentialData = Boolean(flags & 0x40);
  if (!attestedCredentialData) throw new Error('attested_credential_data_required');
  const aaguid = bytes.subarray(37, 53);
  const credentialIdLength = bytes.readUInt16BE(53);
  if (credentialIdLength < 1 || credentialIdLength > MAX_CREDENTIAL_ID_BYTES) throw new Error('credential_id_length_invalid');
  const credentialIdStart = 55;
  const credentialIdEnd = credentialIdStart + credentialIdLength;
  if (credentialIdEnd >= bytes.length) throw new Error('credential_public_key_missing');
  const credentialId = bytes.subarray(credentialIdStart, credentialIdEnd);
  const coseBytes = bytes.subarray(credentialIdEnd);
  let cose;
  try { cose = decode(coseBytes); }
  catch { throw new Error('cose_public_key_cbor_invalid'); }

  const kty = Number(mapGet(cose, 1));
  const alg = Number(mapGet(cose, 3));
  const crv = Number(mapGet(cose, -1));
  const x = toBuffer(mapGet(cose, -2), 'cose_x', 32);
  const y = toBuffer(mapGet(cose, -3), 'cose_y', 32);
  if (kty !== 2 || alg !== -7 || crv !== 1) throw new Error('only_es256_p256_registration_supported');

  const publicJwk = {
    kty: 'EC',
    crv: 'P-256',
    x: x.toString('base64url'),
    y: y.toString('base64url'),
    alg: 'ES256',
    ext: true,
  };
  try { createPublicKey({ key: publicJwk, format: 'jwk' }); }
  catch { throw new Error('credential_public_key_invalid'); }

  return {
    rp_id_hash: rpIdHash,
    flags,
    sign_count: signCount,
    user_present: userPresent,
    user_verified: userVerified,
    aaguid,
    credential_id: credentialId,
    cose_public_key_bytes: coseBytes,
    public_key_jwk: publicJwk,
  };
}

export function verifyWebAuthnRegistration(input) {
  if (!input || typeof input !== 'object') throw new Error('registration_input_required');
  const expectedChallenge = String(input.expected_challenge ?? '');
  const expectedOrigin = String(input.expected_origin ?? '');
  const expectedRpId = String(input.expected_rp_id ?? '').toLowerCase();
  if (!/^[A-Za-z0-9_-]{16,1024}$/.test(expectedChallenge)) throw new Error('expected_challenge_invalid');
  if (!safeHost(expectedRpId)) throw new Error('expected_rp_id_invalid');
  let origin;
  try { origin = new URL(expectedOrigin); } catch { throw new Error('expected_origin_invalid'); }
  if (origin.protocol !== 'https:') throw new Error('https_origin_required');
  if (origin.hostname !== expectedRpId && !origin.hostname.endsWith(`.${expectedRpId}`)) throw new Error('origin_rp_mismatch');

  const clientDataBytes = b64urlToBuffer(input.client_data_json, MAX_CLIENT_DATA_BYTES, 'client_data_json');
  let clientData;
  try { clientData = JSON.parse(clientDataBytes.toString('utf8')); }
  catch { return { ok: false, state: 'HOLD', reason: 'client_data_json_invalid' }; }
  if (clientData.type !== 'webauthn.create') return { ok: false, state: 'HOLD', reason: 'client_data_type_invalid' };
  if (clientData.challenge !== expectedChallenge) return { ok: false, state: 'HOLD', reason: 'challenge_mismatch' };
  if (clientData.origin !== origin.origin) return { ok: false, state: 'HOLD', reason: 'origin_mismatch' };
  if (clientData.crossOrigin === true) return { ok: false, state: 'HOLD', reason: 'cross_origin_not_allowed' };

  const attestationBytes = b64urlToBuffer(input.attestation_object, MAX_ATTESTATION_OBJECT_BYTES, 'attestation_object');
  let attestation;
  try { attestation = decode(attestationBytes); }
  catch { return { ok: false, state: 'HOLD', reason: 'attestation_object_cbor_invalid' }; }
  const fmt = mapGet(attestation, 'fmt');
  const authData = mapGet(attestation, 'authData');
  const attStmt = mapGet(attestation, 'attStmt');
  if (fmt !== 'none') return { ok: false, state: 'HOLD', reason: 'attestation_format_not_allowed_in_controlled_profile' };
  const attestationStatementKeys = attStmt instanceof Map ? [...attStmt.keys()] : attStmt && typeof attStmt === 'object' ? Object.keys(attStmt) : [];
  if (attestationStatementKeys.length !== 0) return { ok: false, state: 'HOLD', reason: 'none_attestation_statement_must_be_empty' };

  let parsed;
  try { parsed = parseAttestedCredentialData(authData); }
  catch (error) { return { ok: false, state: 'HOLD', reason: error instanceof Error ? error.message : 'auth_data_invalid' }; }
  const expectedRpHash = sha256(Buffer.from(expectedRpId, 'utf8'));
  if (!parsed.rp_id_hash.equals(expectedRpHash)) return { ok: false, state: 'HOLD', reason: 'rp_id_hash_mismatch' };
  if (!parsed.user_present) return { ok: false, state: 'HOLD', reason: 'user_presence_required' };
  if (input.require_user_verification !== false && !parsed.user_verified) return { ok: false, state: 'HOLD', reason: 'user_verification_required' };

  const credentialIdB64 = parsed.credential_id.toString('base64url');
  const credentialCommitment = sha256(Buffer.concat([
    Buffer.from(expectedRpId, 'utf8'),
    Buffer.from([0]),
    parsed.credential_id,
    Buffer.from([0]),
    parsed.cose_public_key_bytes,
  ])).toString('hex');

  return {
    ok: true,
    state: 'VERIFIED_REGISTRATION_CONTROLLED_TEST',
    reason: 'none_attestation_registration_verified',
    attestation_format: 'none',
    rp_id: expectedRpId,
    origin: origin.origin,
    user_present: parsed.user_present,
    user_verified: parsed.user_verified,
    sign_count: parsed.sign_count,
    credential_id: credentialIdB64,
    credential_commitment_sha256: credentialCommitment,
    aaguid: parsed.aaguid.toString('hex'),
    public_key_jwk: parsed.public_key_jwk,
    client_data_digest: sha256(clientDataBytes).toString('hex'),
    attestation_object_digest: sha256(attestationBytes).toString('hex'),
    private_key_material_present: false,
    attestation_trust_claimed: false,
    production_credential_activation_authorized: false,
    smart_account_deployment_authorized: false,
  };
}
