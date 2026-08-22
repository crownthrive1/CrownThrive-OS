import {
  encoder,
  asObject,
  requireString,
  decodeJwtUnverified,
  GITHUB_OIDC_ISSUER,
  GITHUB_OIDC_JWKS_URL,
  CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
  CROWNTHRIVE_REPOSITORY,
  CROWNTHRIVE_REPOSITORY_ID,
  CROWNTHRIVE_REPOSITORY_OWNER,
  CROWNTHRIVE_REPOSITORY_OWNER_ID,
  INSTITUTIONALIZATION_V2_WORKFLOW_NAME,
  INSTITUTIONALIZATION_V2_WORKFLOW_PATH,
  INSTITUTIONALIZATION_V2_SOURCE_BRANCH,
  INSTITUTIONALIZATION_V2_TARGET_BRANCH,
  OLD_SUBJECT_PREFIX,
  IMMUTABLE_SUBJECT_PREFIX,
} from './oidc-runtime-utils-v2.mjs';

function audienceContains(aud, expected) {
  if (typeof aud === 'string') return aud === expected;
  return Array.isArray(aud) && aud.length > 0 && aud.every((item) => typeof item === 'string') && aud.includes(expected);
}

function expectedSubjects(eventName, sourceBranch) {
  if (eventName === 'pull_request') {
    return new Set([`${OLD_SUBJECT_PREFIX}:pull_request`, `${IMMUTABLE_SUBJECT_PREFIX}:pull_request`]);
  }
  if (eventName === 'workflow_dispatch') {
    const suffix = `:ref:refs/heads/${sourceBranch}`;
    return new Set([`${OLD_SUBJECT_PREFIX}${suffix}`, `${IMMUTABLE_SUBJECT_PREFIX}${suffix}`]);
  }
  return new Set();
}

export function validateGithubOidcClaimsV2(claims, { nowSeconds = Math.floor(Date.now() / 1000), clockSkewSeconds = 60 } = {}) {
  const c = asObject(claims, 'oidc_claims_invalid');
  if (c.iss !== GITHUB_OIDC_ISSUER) throw new Error('oidc_issuer_invalid');
  if (!audienceContains(c.aud, CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE)) throw new Error('oidc_audience_invalid');
  const exp = Number(c.exp);
  const nbf = Number(c.nbf);
  const iat = Number(c.iat);
  if (!Number.isFinite(exp) || exp < nowSeconds - clockSkewSeconds) throw new Error('oidc_token_expired');
  if (!Number.isFinite(nbf) || nbf > nowSeconds + clockSkewSeconds) throw new Error('oidc_token_not_yet_valid');
  if (!Number.isFinite(iat) || iat > nowSeconds + clockSkewSeconds || iat < nowSeconds - 900) throw new Error('oidc_issue_time_invalid');
  requireString(c.jti, 'oidc_jti_invalid', /^[A-Za-z0-9._:-]{8,240}$/);
  if (c.repository !== CROWNTHRIVE_REPOSITORY) throw new Error('oidc_repository_invalid');
  if (String(c.repository_id) !== CROWNTHRIVE_REPOSITORY_ID) throw new Error('oidc_repository_id_invalid');
  if (c.repository_owner !== CROWNTHRIVE_REPOSITORY_OWNER) throw new Error('oidc_repository_owner_invalid');
  if (String(c.repository_owner_id) !== CROWNTHRIVE_REPOSITORY_OWNER_ID) throw new Error('oidc_repository_owner_id_invalid');
  if (c.repository_visibility !== 'public') throw new Error('oidc_repository_visibility_invalid');
  if (!['pull_request', 'workflow_dispatch'].includes(c.event_name)) throw new Error('oidc_event_invalid');
  if (c.workflow !== INSTITUTIONALIZATION_V2_WORKFLOW_NAME) throw new Error('oidc_workflow_name_invalid');
  const workflowPrefix = `${CROWNTHRIVE_REPOSITORY}/${INSTITUTIONALIZATION_V2_WORKFLOW_PATH}@refs/`;
  if (typeof c.workflow_ref !== 'string' || !c.workflow_ref.startsWith(workflowPrefix)) throw new Error('oidc_workflow_ref_invalid');
  requireString(c.workflow_sha, 'oidc_workflow_sha_invalid', /^[0-9a-f]{40}$/);
  requireString(c.sha, 'oidc_sha_invalid', /^[0-9a-f]{40}$/);
  requireString(String(c.run_id), 'oidc_run_id_invalid', /^\d+$/);
  requireString(String(c.run_attempt), 'oidc_run_attempt_invalid', /^\d+$/);
  requireString(c.actor, 'oidc_actor_invalid', /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/);
  requireString(String(c.actor_id), 'oidc_actor_id_invalid', /^\d+$/);
  if (c.actor !== CROWNTHRIVE_REPOSITORY_OWNER || String(c.actor_id) !== CROWNTHRIVE_REPOSITORY_OWNER_ID) {
    throw new Error('oidc_actor_not_authorized');
  }
  requireString(c.sub, 'oidc_subject_invalid', /^repo:/, 600);
  if (!expectedSubjects(c.event_name, INSTITUTIONALIZATION_V2_SOURCE_BRANCH).has(c.sub)) throw new Error('oidc_subject_invalid');
  if (c.runner_environment !== 'github-hosted') throw new Error('oidc_runner_environment_invalid');
  requireString(c.ref, 'oidc_ref_invalid', /^refs\//);
  if (c.event_name === 'pull_request') {
    if (c.head_ref !== INSTITUTIONALIZATION_V2_SOURCE_BRANCH || c.base_ref !== INSTITUTIONALIZATION_V2_TARGET_BRANCH) {
      throw new Error('oidc_pull_branch_claim_mismatch');
    }
  } else {
    if (c.ref !== `refs/heads/${INSTITUTIONALIZATION_V2_SOURCE_BRANCH}`) throw new Error('oidc_dispatch_ref_invalid');
  }
  return c;
}

export async function fetchJson(url, { fetchImpl, timeoutMs = 12_000 } = {}) {
  const response = await fetchImpl(url, {
    method: 'GET',
    headers: {
      accept: 'application/vnd.github+json, application/json',
      'x-github-api-version': '2022-11-28',
      'user-agent': 'CrownThrive-CHLOM-Wallet-Institutionalizer-v2/1.0',
    },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error(`github_http_${response.status}`);
  return response.json();
}

export async function verifyGithubOidcJwtV2(token, { fetchImpl = fetch, nowSeconds = Math.floor(Date.now() / 1000) } = {}) {
  const decoded = decodeJwtUnverified(token);
  if (decoded.header.alg !== 'RS256') throw new Error('oidc_algorithm_invalid');
  if (decoded.header.typ !== undefined && decoded.header.typ !== 'JWT') throw new Error('oidc_type_invalid');
  requireString(decoded.header.kid, 'oidc_key_id_invalid', /^[A-Za-z0-9._:-]{4,240}$/);
  const jwks = await fetchJson(GITHUB_OIDC_JWKS_URL, { fetchImpl });
  if (!jwks || !Array.isArray(jwks.keys)) throw new Error('oidc_jwks_invalid');
  const jwk = jwks.keys.find((candidate) => candidate && candidate.kid === decoded.header.kid && candidate.kty === 'RSA' && (candidate.alg === undefined || candidate.alg === 'RS256'));
  if (!jwk) throw new Error('oidc_signing_key_not_found');
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const valid = await crypto.subtle.verify({ name: 'RSASSA-PKCS1-v1_5' }, key, decoded.signature, encoder.encode(decoded.signingInput));
  if (!valid) throw new Error('oidc_signature_invalid');
  const claims = validateGithubOidcClaimsV2(decoded.claims, { nowSeconds });
  return { header: decoded.header, claims };
}
