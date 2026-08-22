const encoder = new TextEncoder();
const decoder = new TextDecoder();

export const GITHUB_OIDC_ISSUER = 'https://token.actions.githubusercontent.com';
export const GITHUB_OIDC_JWKS_URL = 'https://token.actions.githubusercontent.com/.well-known/jwks';
export const CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE = 'chlom-wallet-institutionalization-v2';
export const CROWNTHRIVE_REPOSITORY = 'crownthrive1/CrownThrive-Support';
export const CROWNTHRIVE_REPOSITORY_ID = '1336348391';
export const CROWNTHRIVE_REPOSITORY_OWNER = 'crownthrive1';
export const CROWNTHRIVE_REPOSITORY_OWNER_ID = '315660018';
export const EXPECTED_SOURCE_BRANCH = 'chlom-wallet/phase-c-proof-portability-20260822';
export const EXPECTED_TARGET_BRANCH = 'chlom-wallet/phase-b-webhook-passkey-contracts-20260822';
export const INSTITUTIONALIZATION_V2_WORKFLOW_NAME = 'CHLOM Institutionalization Package v2';
export const INSTITUTIONALIZATION_V2_WORKFLOW_PATH = '.github/workflows/chlom-wallet-institutionalization-v2.yml';
export const INSTITUTIONALIZATION_V2_MANIFEST_PATH = 'developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json';

const HEX40 = /^[0-9a-f]{40}$/;
const HEX64 = /^[0-9a-f]{64}$/;

function asObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
  return value;
}

function requireString(value, code, pattern = null) {
  if (typeof value !== 'string' || value.length === 0 || (pattern && !pattern.test(value))) throw new Error(code);
  return value;
}

function requireBoolean(value, code) {
  if (typeof value !== 'boolean') throw new Error(code);
  return value;
}

export function base64urlDecode(value) {
  requireString(value, 'base64url_value_invalid', /^[A-Za-z0-9_-]+$/);
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
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  if (value && typeof value === 'object') {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error('canonical_plain_object_required');
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
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
  requireString(token, 'oidc_token_required');
  if (token.length > 24_000) throw new Error('oidc_token_too_large');
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('oidc_token_shape_invalid');
  return {
    header: parseJsonBytes(base64urlDecode(parts[0]), 'oidc_header_invalid'),
    claims: parseJsonBytes(base64urlDecode(parts[1]), 'oidc_claims_invalid'),
    signingInput: `${parts[0]}.${parts[1]}`,
    signature: base64urlDecode(parts[2]),
  };
}

function audienceContains(audience, expected) {
  if (typeof audience === 'string') return audience === expected;
  return Array.isArray(audience)
    && audience.length > 0
    && audience.every((item) => typeof item === 'string')
    && audience.includes(expected);
}

export function validateGithubOidcClaims(claims, {
  nowSeconds = Math.floor(Date.now() / 1000),
  clockSkewSeconds = 60,
} = {}) {
  const value = asObject(claims, 'oidc_claims_invalid');
  if (value.iss !== GITHUB_OIDC_ISSUER) throw new Error('oidc_issuer_invalid');
  if (!audienceContains(value.aud, CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE)) throw new Error('oidc_audience_invalid');

  const exp = Number(value.exp);
  const nbf = Number(value.nbf);
  const iat = Number(value.iat);
  if (!Number.isFinite(exp) || exp < nowSeconds - clockSkewSeconds) throw new Error('oidc_token_expired');
  if (!Number.isFinite(nbf) || nbf > nowSeconds + clockSkewSeconds) throw new Error('oidc_token_not_yet_valid');
  if (!Number.isFinite(iat) || iat > nowSeconds + clockSkewSeconds || iat < nowSeconds - 900) throw new Error('oidc_issue_time_invalid');

  requireString(value.jti, 'oidc_jti_invalid', /^[A-Za-z0-9._:-]{8,240}$/);
  if (value.repository !== CROWNTHRIVE_REPOSITORY) throw new Error('oidc_repository_invalid');
  if (String(value.repository_id) !== CROWNTHRIVE_REPOSITORY_ID) throw new Error('oidc_repository_id_invalid');
  if (value.repository_owner !== CROWNTHRIVE_REPOSITORY_OWNER) throw new Error('oidc_repository_owner_invalid');
  if (String(value.repository_owner_id) !== CROWNTHRIVE_REPOSITORY_OWNER_ID) throw new Error('oidc_repository_owner_id_invalid');
  if (value.repository_visibility !== 'public') throw new Error('oidc_repository_visibility_invalid');
  if (!['pull_request', 'workflow_dispatch'].includes(value.event_name)) throw new Error('oidc_event_invalid');
  if (value.workflow !== INSTITUTIONALIZATION_V2_WORKFLOW_NAME) throw new Error('oidc_workflow_name_invalid');
  const workflowPrefix = `${CROWNTHRIVE_REPOSITORY}/${INSTITUTIONALIZATION_V2_WORKFLOW_PATH}@`;
  if (typeof value.workflow_ref !== 'string' || !value.workflow_ref.startsWith(workflowPrefix)) throw new Error('oidc_workflow_ref_invalid');
  requireString(value.workflow_sha, 'oidc_workflow_sha_invalid', HEX40);
  requireString(value.sha, 'oidc_sha_invalid', HEX40);
  requireString(String(value.run_id), 'oidc_run_id_invalid', /^\d+$/);
  requireString(String(value.run_attempt), 'oidc_run_attempt_invalid', /^\d+$/);
  requireString(value.actor, 'oidc_actor_invalid', /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/);
  requireString(String(value.actor_id), 'oidc_actor_id_invalid', /^\d+$/);
  requireString(value.sub, 'oidc_subject_invalid', /^repo:crownthrive1\/CrownThrive-Support:/);
  if (value.runner_environment !== 'github-hosted') throw new Error('oidc_runner_environment_invalid');
  requireString(value.ref, 'oidc_ref_invalid', /^refs\//);
  return value;
}

async function fetchJson(url, { fetchImpl, timeoutMs = 12_000 } = {}) {
  const response = await fetchImpl(url, {
    method: 'GET',
    headers: {
      accept: 'application/vnd.github+json, application/json',
      'user-agent': 'CrownThrive-CHLOM-Institutionalization-v2/1.0',
    },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error(`upstream_http_${response.status}`);
  return response.json();
}

export async function verifyGithubOidcJwt(token, {
  fetchImpl = fetch,
  nowSeconds = Math.floor(Date.now() / 1000),
} = {}) {
  const decoded = decodeJwtUnverified(token);
  if (decoded.header.alg !== 'RS256') throw new Error('oidc_algorithm_invalid');
  requireString(decoded.header.kid, 'oidc_key_id_invalid', /^[A-Za-z0-9._:-]{4,240}$/);
  const jwks = await fetchJson(GITHUB_OIDC_JWKS_URL, { fetchImpl });
  if (!jwks || !Array.isArray(jwks.keys)) throw new Error('oidc_jwks_invalid');
  const jwk = jwks.keys.find((candidate) => candidate && candidate.kid === decoded.header.kid && candidate.kty === 'RSA');
  if (!jwk) throw new Error('oidc_signing_key_not_found');
  const key = await crypto.subtle.importKey(
    'jwk',
    jwk,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  );
  const valid = await crypto.subtle.verify(
    { name: 'RSASSA-PKCS1-v1_5' },
    key,
    decoded.signature,
    encoder.encode(decoded.signingInput),
  );
  if (!valid) throw new Error('oidc_signature_invalid');
  return { header: decoded.header, claims: validateGithubOidcClaims(decoded.claims, { nowSeconds }) };
}

export async function validateManifestShape(manifest) {
  const value = asObject(manifest, 'manifest_object_required');
  if (value.schema_version !== '1.0.0') throw new Error('manifest_schema_version_invalid');
  if (value.package_id !== 'ct.package.chlom-wallet.phase-c.institutionalization.v1') throw new Error('manifest_package_id_invalid');
  if (value.semantic_version !== '1.0.0') throw new Error('manifest_semantic_version_invalid');
  if (value.state !== 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION') throw new Error('manifest_state_invalid');
  requireString(value.package_digest_sha256, 'manifest_package_digest_invalid', HEX64);
  const snapshot = asObject(value.source_snapshot, 'manifest_source_snapshot_invalid');
  if (snapshot.repository !== CROWNTHRIVE_REPOSITORY) throw new Error('manifest_repository_invalid');
  if (snapshot.branch !== EXPECTED_SOURCE_BRANCH) throw new Error('manifest_source_branch_invalid');
  requireString(snapshot.head_sha, 'manifest_source_head_invalid', HEX40);
  if (snapshot.observed_on !== '2026-08-22') throw new Error('manifest_observed_on_invalid');
  const boundaries = asObject(value.hard_boundaries, 'manifest_hard_boundaries_required');
  if (Object.keys(boundaries).length < 10) throw new Error('manifest_hard_boundaries_incomplete');
  for (const [key, flag] of Object.entries(boundaries)) {
    if (flag !== false) throw new Error(`manifest_hard_boundary_${key}_must_be_false`);
  }
  const withoutDigest = { ...value };
  delete withoutDigest.package_digest_sha256;
  const expectedDigest = await sha256Hex(canonicalize(withoutDigest));
  if (expectedDigest !== value.package_digest_sha256) throw new Error('manifest_package_digest_recompute_mismatch');
  return value;
}

function decodeGithubContent(content) {
  requireString(content, 'github_manifest_content_invalid', /^[A-Za-z0-9+/=\n\r]+$/);
  let binary;
  try {
    binary = atob(content.replace(/[\n\r]/g, ''));
  } catch {
    throw new Error('github_manifest_base64_invalid');
  }
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

export async function verifyRepositorySnapshot({
  claims,
  manifest,
  fetchImpl = fetch,
  nowSeconds = Math.floor(Date.now() / 1000),
}) {
  const oidc = validateGithubOidcClaims(claims, { nowSeconds });
  const packageManifest = await validateManifestShape(manifest);
  let currentHeadSha;
  let sourceBranch;
  let targetBranch = null;
  let pullRequestNumber = null;

  if (oidc.event_name === 'pull_request') {
    const match = /^refs\/pull\/(\d+)\/merge$/.exec(oidc.ref);
    if (!match) throw new Error('oidc_pull_request_ref_invalid');
    pullRequestNumber = Number(match[1]);
    if (!Number.isSafeInteger(pullRequestNumber) || pullRequestNumber < 1) throw new Error('oidc_pull_request_number_invalid');
    const pull = await fetchJson(`https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/pulls/${pullRequestNumber}`, { fetchImpl });
    if (pull?.head?.repo?.full_name !== CROWNTHRIVE_REPOSITORY) throw new Error('fork_pull_request_rejected');
    currentHeadSha = requireString(pull?.head?.sha, 'github_pull_head_invalid', HEX40);
    sourceBranch = requireString(pull?.head?.ref, 'github_pull_head_ref_invalid');
    targetBranch = requireString(pull?.base?.ref, 'github_pull_base_ref_invalid');
    if (sourceBranch !== EXPECTED_SOURCE_BRANCH) throw new Error('github_pull_source_branch_invalid');
    if (targetBranch !== EXPECTED_TARGET_BRANCH) throw new Error('github_pull_target_branch_invalid');
    if (oidc.head_ref !== sourceBranch || oidc.base_ref !== targetBranch) throw new Error('oidc_pull_branch_claim_mismatch');
  } else {
    const match = /^refs\/heads\/(.+)$/.exec(oidc.ref);
    if (!match) throw new Error('oidc_dispatch_ref_invalid');
    sourceBranch = match[1];
    if (sourceBranch !== EXPECTED_SOURCE_BRANCH) throw new Error('oidc_dispatch_source_branch_invalid');
    const branch = await fetchJson(`https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/branches/${encodeURIComponent(sourceBranch)}`, { fetchImpl });
    currentHeadSha = requireString(branch?.commit?.sha, 'github_branch_head_invalid', HEX40);
  }

  const compare = await fetchJson(
    `https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/compare/${packageManifest.source_snapshot.head_sha}...${currentHeadSha}`,
    { fetchImpl },
  );
  if (!['ahead', 'identical'].includes(compare?.status)) throw new Error('manifest_source_head_not_ancestor');
  if (Number(compare?.behind_by ?? 1) !== 0) throw new Error('manifest_source_head_compare_behind');
  if (compare?.base_commit?.sha !== packageManifest.source_snapshot.head_sha) throw new Error('manifest_source_head_compare_base_invalid');

  const contentResponse = await fetchJson(
    `https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/contents/${INSTITUTIONALIZATION_V2_MANIFEST_PATH}?ref=${currentHeadSha}`,
    { fetchImpl },
  );
  const committedBytes = decodeGithubContent(contentResponse?.content);
  const committedText = decoder.decode(committedBytes);
  let committedManifest;
  try {
    committedManifest = JSON.parse(committedText);
  } catch {
    throw new Error('github_manifest_json_invalid');
  }
  if (canonicalize(committedManifest) !== canonicalize(packageManifest)) throw new Error('submitted_manifest_not_current_committed_manifest');

  return {
    repository: CROWNTHRIVE_REPOSITORY,
    repository_id: CROWNTHRIVE_REPOSITORY_ID,
    repository_owner: CROWNTHRIVE_REPOSITORY_OWNER,
    repository_owner_id: CROWNTHRIVE_REPOSITORY_OWNER_ID,
    repository_visibility: oidc.repository_visibility,
    event_name: oidc.event_name,
    source_branch: sourceBranch,
    target_branch: targetBranch,
    pull_request_number: pullRequestNumber == null ? '' : String(pullRequestNumber),
    verified_current_head_sha: currentHeadSha,
    verified_source_head_sha: packageManifest.source_snapshot.head_sha,
    source_head_ancestor_verified: true,
    manifest_path: INSTITUTIONALIZATION_V2_MANIFEST_PATH,
    manifest_content_sha256: await sha256Hex(committedBytes),
    manifest_canonical_sha256: await sha256Hex(canonicalize(packageManifest)),
    manifest_package_digest_sha256: packageManifest.package_digest_sha256,
    workflow: oidc.workflow,
    workflow_ref: oidc.workflow_ref,
    workflow_sha: oidc.workflow_sha,
    github_event_sha: oidc.sha,
    github_run_id: String(oidc.run_id),
    github_run_number: String(oidc.run_number ?? ''),
    github_run_attempt: String(oidc.run_attempt),
    github_actor: oidc.actor,
    github_actor_id: String(oidc.actor_id),
    oidc_jti: oidc.jti,
    oidc_issuer: oidc.iss,
    oidc_audience: CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
    oidc_subject: oidc.sub,
    runner_environment: oidc.runner_environment,
    provider_write: false,
    credential_access: false,
    effective_offer: false,
    stripe_objects_created: false,
    checkout_enabled: false,
    custody: false,
    token_issuance: false,
    money_movement: false,
    production_rights_grant: false,
    chain_broadcast: false,
    phase_advancement: false,
    merge_authorized: false,
    automatic_profile_promotion: false,
  };
}

export function assertNoAuthorityEscalation(value) {
  const object = asObject(value, 'authority_boundary_object_required');
  for (const field of [
    'provider_write','credential_access','effective_offer','stripe_objects_created',
    'checkout_enabled','custody','token_issuance','money_movement',
    'production_rights_grant','chain_broadcast','phase_advancement',
    'merge_authorized','automatic_profile_promotion',
  ]) {
    requireBoolean(object[field], `authority_field_${field}_invalid`);
    if (object[field]) throw new Error(`authority_field_${field}_must_be_false`);
  }
  return true;
}
