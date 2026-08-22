export const encoder = new TextEncoder();
export const decoder = new TextDecoder();

export const GITHUB_OIDC_ISSUER = 'https://token.actions.githubusercontent.com';
export const GITHUB_OIDC_JWKS_URL = 'https://token.actions.githubusercontent.com/.well-known/jwks';
export const CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE = 'chlom-wallet-institutionalization-v2';
export const CROWNTHRIVE_REPOSITORY = 'crownthrive1/CrownThrive-Support';
export const CROWNTHRIVE_REPOSITORY_ID = '1336348391';
export const CROWNTHRIVE_REPOSITORY_OWNER = 'crownthrive1';
export const CROWNTHRIVE_REPOSITORY_OWNER_ID = '315660018';
export const INSTITUTIONALIZATION_V2_WORKFLOW_NAME = 'CHLOM Institutionalization Package v2';
export const INSTITUTIONALIZATION_V2_WORKFLOW_PATH = '.github/workflows/chlom-wallet-institutionalization-v2.yml';
export const INSTITUTIONALIZATION_V2_SOURCE_BRANCH = 'chlom-wallet/phase-c-proof-portability-20260822';
export const INSTITUTIONALIZATION_V2_TARGET_BRANCH = 'chlom-wallet/phase-b-webhook-passkey-contracts-20260822';
export const INSTITUTIONALIZATION_V2_PR_NUMBER = 233;
export const INSTITUTIONALIZATION_V2_MANIFEST_PATH = 'developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json';
export const INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD = '64118e61c7671a78b43999ac5f17f9eddd1226b1';
export const INSTITUTIONALIZATION_V2_PACKAGE_ID = 'ct.package.chlom-wallet.phase-c.institutionalization.v1';
export const INSTITUTIONALIZATION_V2_PACKAGE_DIGEST = '7b3be50d5541fff14127bfdd24724eb9b8b9f9ffd4b165a380dee02f2a1ef957';
export const INSTITUTIONALIZATION_V2_SEMANTIC_VERSION = '1.0.0';

export const OLD_SUBJECT_PREFIX = `repo:${CROWNTHRIVE_REPOSITORY}`;
export const IMMUTABLE_SUBJECT_PREFIX = `repo:${CROWNTHRIVE_REPOSITORY_OWNER}@${CROWNTHRIVE_REPOSITORY_OWNER_ID}/CrownThrive-Support@${CROWNTHRIVE_REPOSITORY_ID}`;

export function asObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
  return value;
}

export function requireString(value, code, pattern = null, maxLength = 2000) {
  if (typeof value !== 'string' || value.length === 0 || value.length > maxLength || (pattern && !pattern.test(value))) {
    throw new Error(code);
  }
  return value;
}

export function requireBoolean(value, code) {
  if (typeof value !== 'boolean') throw new Error(code);
  return value;
}

export function base64urlDecode(value) {
  requireString(value, 'base64url_value_invalid', /^[A-Za-z0-9_-]+$/, 100_000);
  const padded = value.replaceAll('-', '+').replaceAll('_', '/') + '==='.slice((value.length + 3) % 4);
  let binary;
  try {
    binary = atob(padded);
  } catch {
    throw new Error('base64url_decode_failed');
  }
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export function base64urlEncode(bytes) {
  const value = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let binary = '';
  for (let index = 0; index < value.length; index += 8192) {
    binary += String.fromCharCode(...value.subarray(index, Math.min(index + 8192, value.length)));
  }
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/g, '');
}

export function base64Decode(value, { maxBytes = 2_000_000 } = {}) {
  requireString(value, 'base64_value_invalid', /^[A-Za-z0-9+/=\r\n]+$/, Math.ceil(maxBytes * 1.5) + 16);
  let binary;
  try {
    binary = atob(value.replace(/\s+/g, ''));
  } catch {
    throw new Error('base64_decode_failed');
  }
  if (binary.length > maxBytes) throw new Error('decoded_content_too_large');
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export function canonicalize(value) {
  if (value === null) return 'null';
  if (typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error('canonical_number_must_be_finite');
    if (Object.is(value, -0)) return '0';
    return JSON.stringify(value);
  }
  if (typeof value === 'bigint') throw new Error('canonical_bigint_not_supported');
  if (Array.isArray(value)) return `[${value.map((entry) => canonicalize(entry)).join(',')}]`;
  if (typeof value === 'object') {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error('canonical_plain_object_required');
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
  }
  throw new Error('canonical_value_type_unsupported');
}

export async function sha256Hex(value) {
  const bytes = value instanceof Uint8Array ? value : encoder.encode(String(value));
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function parseJsonBytes(bytes, code) {
  try {
    return asObject(JSON.parse(decoder.decode(bytes)), code);
  } catch (error) {
    if (error instanceof Error && error.message === code) throw error;
    throw new Error(code);
  }
}

export function decodeJwtUnverified(token) {
  requireString(token, 'oidc_token_required', null, 32_000);
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('oidc_token_shape_invalid');
  const header = parseJsonBytes(base64urlDecode(parts[0]), 'oidc_header_invalid');
  const claims = parseJsonBytes(base64urlDecode(parts[1]), 'oidc_claims_invalid');
  return { header, claims, signingInput: `${parts[0]}.${parts[1]}`, signature: base64urlDecode(parts[2]) };
}


export function assertNoAuthorityEscalation(value) {
  const object = asObject(value, 'authority_boundary_object_required');
  const fields = [
    'provider_write','credential_access','effective_offer','stripe_objects_created','checkout_enabled',
    'custody','token_issuance','money_movement','rights_grant','production_rights_grant',
    'chain_broadcast','phase_advancement','merge_authorized','automatic_profile_promotion',
  ];
  for (const field of fields) {
    if (Object.prototype.hasOwnProperty.call(object, field)) requireBoolean(object[field], `authority_field_${field}_invalid`);
    if (object[field] === true) throw new Error(`authority_field_${field}_must_be_false`);
  }
  return true;
}

export async function validateInstitutionalizationManifestV2(manifest) {
  const m = asObject(manifest, 'manifest_object_required');
  if (m.schema_version !== '1.0.0') throw new Error('manifest_schema_version_invalid');
  if (m.package_id !== INSTITUTIONALIZATION_V2_PACKAGE_ID) throw new Error('manifest_package_id_invalid');
  if (m.semantic_version !== INSTITUTIONALIZATION_V2_SEMANTIC_VERSION) throw new Error('manifest_semantic_version_invalid');
  if (m.state !== 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION') throw new Error('manifest_not_pass');
  if (m.package_digest_sha256 !== INSTITUTIONALIZATION_V2_PACKAGE_DIGEST) throw new Error('manifest_package_digest_unpinned');
  const snapshot = asObject(m.source_snapshot, 'manifest_snapshot_invalid');
  if (snapshot.repository !== CROWNTHRIVE_REPOSITORY) throw new Error('manifest_repository_invalid');
  if (snapshot.branch !== INSTITUTIONALIZATION_V2_SOURCE_BRANCH) throw new Error('manifest_branch_invalid');
  if (snapshot.head_sha !== INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD) throw new Error('manifest_source_head_invalid');
  if (!Array.isArray(m.artifact_inventory) || m.artifact_inventory.length < 11) throw new Error('manifest_artifact_inventory_invalid');
  if (!Array.isArray(m.algorithm_registry) || m.algorithm_registry.length < 2) throw new Error('manifest_algorithm_registry_invalid');
  assertNoAuthorityEscalation(m.hard_boundaries);
  const packageWithoutDigest = { ...m };
  delete packageWithoutDigest.package_digest_sha256;
  const recomputed = await sha256Hex(canonicalize(packageWithoutDigest));
  if (recomputed !== m.package_digest_sha256) throw new Error('manifest_package_digest_recompute_mismatch');
  return m;
}
