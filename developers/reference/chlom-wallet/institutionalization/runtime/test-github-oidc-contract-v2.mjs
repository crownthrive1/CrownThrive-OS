import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
  CROWNTHRIVE_REPOSITORY,
  GITHUB_OIDC_ISSUER,
  INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD,
  INSTITUTIONALIZATION_V2_MANIFEST_PATH,
  INSTITUTIONALIZATION_V2_SOURCE_BRANCH,
  INSTITUTIONALIZATION_V2_TARGET_BRANCH,
  assertNoAuthorityEscalation,
  base64urlEncode,
  canonicalize,
  sha256Hex,
  validateGithubOidcClaimsV2,
  validateInstitutionalizationManifestV2,
  verifyGithubOidcJwtV2,
  verifyRepositorySnapshotV2,
} from './github-oidc-contract-v2.mjs';

const encoder = new TextEncoder();
const now = Math.floor(Date.now() / 1000);
const keyPair = await crypto.subtle.generateKey(
  { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
  true,
  ['sign', 'verify'],
);
const publicJwk = await crypto.subtle.exportKey('jwk', keyPair.publicKey);
Object.assign(publicJwk, { kid: 'ct-test-kid-v2', alg: 'RS256', use: 'sig' });

function claims(overrides = {}) {
  return {
    iss: GITHUB_OIDC_ISSUER,
    aud: CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
    sub: 'repo:crownthrive1@315660018/CrownThrive-Support@1336348391:pull_request',
    exp: now + 300,
    nbf: now - 5,
    iat: now - 5,
    jti: 'ct-test-jti-v2-0001',
    repository: CROWNTHRIVE_REPOSITORY,
    repository_id: '1336348391',
    repository_owner: 'crownthrive1',
    repository_owner_id: '315660018',
    repository_visibility: 'public',
    event_name: 'pull_request',
    workflow: 'CHLOM Institutionalization Package v2',
    workflow_ref: `${CROWNTHRIVE_REPOSITORY}/.github/workflows/chlom-wallet-institutionalization-v2.yml@refs/heads/${INSTITUTIONALIZATION_V2_SOURCE_BRANCH}`,
    workflow_sha: 'a'.repeat(40),
    sha: 'b'.repeat(40),
    run_id: '32592885085',
    run_number: '77',
    run_attempt: '1',
    actor: 'crownthrive1',
    actor_id: '315660018',
    runner_environment: 'github-hosted',
    ref: 'refs/pull/233/merge',
    head_ref: INSTITUTIONALIZATION_V2_SOURCE_BRANCH,
    base_ref: INSTITUTIONALIZATION_V2_TARGET_BRANCH,
    ...overrides,
  };
}

async function signJwt(payload, { mutateSignature = false } = {}) {
  const header = { alg: 'RS256', typ: 'JWT', kid: 'ct-test-kid-v2' };
  const headerPart = base64urlEncode(encoder.encode(JSON.stringify(header)));
  const payloadPart = base64urlEncode(encoder.encode(JSON.stringify(payload)));
  const signingInput = `${headerPart}.${payloadPart}`;
  const signature = new Uint8Array(await crypto.subtle.sign('RSASSA-PKCS1-v1_5', keyPair.privateKey, encoder.encode(signingInput)));
  if (mutateSignature) signature[0] ^= 0xff;
  return `${signingInput}.${base64urlEncode(signature)}`;
}

function jsonResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, async json() { return body; } };
}

const jwksFetch = async (url) => {
  assert.equal(url, 'https://token.actions.githubusercontent.com/.well-known/jwks');
  return jsonResponse({ keys: [publicJwk] });
};

const immutableClaims = claims();
const immutableToken = await signJwt(immutableClaims);
const verified = await verifyGithubOidcJwtV2(immutableToken, { fetchImpl: jwksFetch, nowSeconds: now });
assert.equal(verified.claims.sub, immutableClaims.sub);

const legacyClaims = claims({ sub: 'repo:crownthrive1/CrownThrive-Support:pull_request', jti: 'ct-test-jti-v2-0002' });
assert.equal(validateGithubOidcClaimsV2(legacyClaims, { nowSeconds: now }).sub, legacyClaims.sub);

const dispatchClaims = claims({
  event_name: 'workflow_dispatch',
  ref: `refs/heads/${INSTITUTIONALIZATION_V2_SOURCE_BRANCH}`,
  head_ref: '',
  base_ref: '',
  sub: `repo:crownthrive1@315660018/CrownThrive-Support@1336348391:ref:refs/heads/${INSTITUTIONALIZATION_V2_SOURCE_BRANCH}`,
  jti: 'ct-test-jti-v2-0003',
});
assert.equal(validateGithubOidcClaimsV2(dispatchClaims, { nowSeconds: now }).event_name, 'workflow_dispatch');

for (const [code, override] of [
  ['oidc_audience_invalid', { aud: 'wrong-audience' }],
  ['oidc_repository_invalid', { repository: 'wrong/repo' }],
  ['oidc_repository_id_invalid', { repository_id: '999' }],
  ['oidc_actor_not_authorized', { actor: 'someone-else', actor_id: '999' }],
  ['oidc_workflow_name_invalid', { workflow: 'Wrong Workflow' }],
  ['oidc_pull_branch_claim_mismatch', { head_ref: 'wrong-branch' }],
  ['oidc_subject_invalid', { sub: 'repo:crownthrive1@999/CrownThrive-Support@1336348391:pull_request' }],
]) {
  assert.throws(() => validateGithubOidcClaimsV2(claims(override), { nowSeconds: now }), new RegExp(code));
}
assert.throws(() => validateGithubOidcClaimsV2(claims({ exp: now - 120 }), { nowSeconds: now }), /oidc_token_expired/);
await assert.rejects(
  verifyGithubOidcJwtV2(await signJwt(claims({ jti: 'ct-test-jti-v2-tampered' }), { mutateSignature: true }), { fetchImpl: jwksFetch, nowSeconds: now }),
  /oidc_signature_invalid/,
);
assert.throws(() => assertNoAuthorityEscalation({ money_movement: true }), /authority_field_money_movement_must_be_false/);
assert.equal(assertNoAuthorityEscalation({ money_movement: false, provider_write: false }), true);
assert.equal(await sha256Hex(canonicalize({ b: 2, a: 1 })), await sha256Hex('{"a":1,"b":2}'));

let fullRepositoryBindingTested = false;
const here = dirname(fileURLToPath(import.meta.url));
const candidateRoots = [resolve(here, '../../../../../../'), process.cwd()];
for (const root of candidateRoots) {
  const manifestPath = join(root, INSTITUTIONALIZATION_V2_MANIFEST_PATH);
  if (!existsSync(manifestPath)) continue;
  const manifestRaw = readFileSync(manifestPath);
  const manifest = JSON.parse(manifestRaw.toString('utf8'));
  await validateInstitutionalizationManifestV2(manifest);
  const currentHead = 'c'.repeat(40);
  const contentBase64 = Buffer.from(manifestRaw).toString('base64');
  const repositoryFetch = async (url) => {
    if (url === 'https://token.actions.githubusercontent.com/.well-known/jwks') return jsonResponse({ keys: [publicJwk] });
    if (url.endsWith('/pulls/233')) return jsonResponse({
      state: 'open',
      head: { sha: currentHead, ref: INSTITUTIONALIZATION_V2_SOURCE_BRANCH, repo: { full_name: CROWNTHRIVE_REPOSITORY } },
      base: { sha: 'd'.repeat(40), ref: INSTITUTIONALIZATION_V2_TARGET_BRANCH },
    });
    if (url.includes(`/compare/${INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD}...${currentHead}`)) return jsonResponse({
      status: 'ahead',
      behind_by: 0,
      merge_base_commit: { sha: INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD },
    });
    if (url.includes('/contents/') && url.endsWith(`?ref=${currentHead}`)) return jsonResponse({
      type: 'file', encoding: 'base64', content: contentBase64, sha: 'e'.repeat(40),
    });
    throw new Error(`unexpected_mock_url:${url}`);
  };
  const result = await verifyRepositorySnapshotV2({ claims: immutableClaims, manifest, fetchImpl: repositoryFetch, nowSeconds: now });
  assert.equal(result.verified_current_head_sha, currentHead);
  assert.equal(result.verified_source_head_sha, INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD);
  assert.equal(result.source_head_ancestor_verified, true);
  assert.equal(result.manifest_package_digest_sha256, manifest.package_digest_sha256);
  assert.equal(result.money_movement, false);
  fullRepositoryBindingTested = true;
  break;
}

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_INSTITUTIONALIZATION_OIDC_V2_UNIT_CONTRACT',
  rs256_signature_verified: true,
  immutable_subject_accepted: true,
  legacy_subject_accepted: true,
  workflow_dispatch_subject_accepted: true,
  negative_claim_cases: 8,
  tampered_signature_rejected: true,
  authority_escalation_rejected: true,
  canonicalization_deterministic: true,
  full_repository_binding_tested: fullRepositoryBindingTested,
  token_value_persisted: false,
  provider_write: false,
  money_movement: false,
  chain_broadcast: false,
}));
