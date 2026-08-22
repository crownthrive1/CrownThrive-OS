import assert from 'node:assert/strict';
import {
  CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
  CROWNTHRIVE_REPOSITORY,
  EXPECTED_SOURCE_BRANCH,
  EXPECTED_TARGET_BRANCH,
  GITHUB_OIDC_JWKS_URL,
  INSTITUTIONALIZATION_V2_WORKFLOW_NAME,
  INSTITUTIONALIZATION_V2_WORKFLOW_PATH,
  assertNoAuthorityEscalation,
  base64urlEncode,
  canonicalize,
  sha256Hex,
  validateGithubOidcClaims,
  validateManifestShape,
  verifyGithubOidcJwt,
  verifyRepositorySnapshot,
} from './github-oidc-v2.mjs';

const encoder = new TextEncoder();
const nowSeconds = 1_787_421_600;
const sourceHead = 'a'.repeat(40);
const currentHead = 'b'.repeat(40);
const workflowSha = 'c'.repeat(40);
const eventSha = 'd'.repeat(40);

async function buildManifest() {
  const body = {
    schema_version: '1.0.0',
    package_id: 'ct.package.chlom-wallet.phase-c.institutionalization.v1',
    semantic_version: '1.0.0',
    state: 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION',
    source_snapshot: {
      repository: CROWNTHRIVE_REPOSITORY,
      branch: EXPECTED_SOURCE_BRANCH,
      head_sha: sourceHead,
      observed_on: '2026-08-22',
    },
    hard_boundaries: {
      originator_self_approval: false,
      automatic_authority_grant: false,
      automatic_reviewer_heartbeat: false,
      automatic_review_receipt: false,
      provider_write: false,
      signing: false,
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
  };
  return { ...body, package_digest_sha256: await sha256Hex(canonicalize(body)) };
}

function baseClaims() {
  return {
    iss: 'https://token.actions.githubusercontent.com',
    aud: CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
    exp: nowSeconds + 300,
    nbf: nowSeconds - 10,
    iat: nowSeconds - 10,
    jti: 'cicc-v2-test-jti-0001',
    repository: CROWNTHRIVE_REPOSITORY,
    repository_id: '1336348391',
    repository_owner: 'crownthrive1',
    repository_owner_id: '315660018',
    repository_visibility: 'public',
    event_name: 'pull_request',
    workflow: INSTITUTIONALIZATION_V2_WORKFLOW_NAME,
    workflow_ref: `${CROWNTHRIVE_REPOSITORY}/${INSTITUTIONALIZATION_V2_WORKFLOW_PATH}@refs/pull/233/merge`,
    workflow_sha: workflowSha,
    sha: eventSha,
    run_id: '32590000000',
    run_number: '70',
    run_attempt: '1',
    actor: 'crownthrive1',
    actor_id: '315660018',
    sub: `repo:${CROWNTHRIVE_REPOSITORY}:pull_request`,
    runner_environment: 'github-hosted',
    ref: 'refs/pull/233/merge',
    head_ref: EXPECTED_SOURCE_BRANCH,
    base_ref: EXPECTED_TARGET_BRANCH,
  };
}

async function signJwt(claims) {
  const keyPair = await crypto.subtle.generateKey(
    {
      name: 'RSASSA-PKCS1-v1_5',
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256',
    },
    true,
    ['sign', 'verify'],
  );
  const publicJwk = await crypto.subtle.exportKey('jwk', keyPair.publicKey);
  Object.assign(publicJwk, { kid: 'cicc-v2-test-key', use: 'sig', alg: 'RS256' });
  const header = base64urlEncode(encoder.encode(JSON.stringify({ alg: 'RS256', typ: 'JWT', kid: publicJwk.kid })));
  const payload = base64urlEncode(encoder.encode(JSON.stringify(claims)));
  const signingInput = `${header}.${payload}`;
  const signature = await crypto.subtle.sign(
    { name: 'RSASSA-PKCS1-v1_5' },
    keyPair.privateKey,
    encoder.encode(signingInput),
  );
  return { token: `${signingInput}.${base64urlEncode(new Uint8Array(signature))}`, publicJwk };
}

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function createFetch({ publicJwk, manifest, fork = false, compareStatus = 'ahead', committedManifest = manifest }) {
  const committedText = `${JSON.stringify(committedManifest, null, 2)}\n`;
  return async (url) => {
    const value = String(url);
    if (value === GITHUB_OIDC_JWKS_URL) return jsonResponse({ keys: [publicJwk] });
    if (value.endsWith('/pulls/233')) {
      return jsonResponse({
        head: {
          sha: currentHead,
          ref: EXPECTED_SOURCE_BRANCH,
          repo: { full_name: fork ? 'other/fork' : CROWNTHRIVE_REPOSITORY },
        },
        base: { ref: EXPECTED_TARGET_BRANCH },
      });
    }
    if (value.includes(`/compare/${sourceHead}...${currentHead}`)) {
      return jsonResponse({
        status: compareStatus,
        ahead_by: compareStatus === 'identical' ? 0 : 12,
        behind_by: compareStatus === 'diverged' ? 1 : 0,
        base_commit: { sha: sourceHead },
      });
    }
    if (value.includes('/contents/developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json')) {
      return jsonResponse({
        type: 'file',
        encoding: 'base64',
        content: Buffer.from(committedText, 'utf8').toString('base64'),
        sha: 'e'.repeat(40),
      });
    }
    return jsonResponse({ message: 'not found' }, 404);
  };
}

const manifest = await buildManifest();
await validateManifestShape(manifest);
const claims = baseClaims();
validateGithubOidcClaims(claims, { nowSeconds });
const signed = await signJwt(claims);
const fetchImpl = createFetch({ publicJwk: signed.publicJwk, manifest });

const verifiedJwt = await verifyGithubOidcJwt(signed.token, { fetchImpl, nowSeconds });
assert.equal(verifiedJwt.claims.repository, CROWNTHRIVE_REPOSITORY);

const verifiedSnapshot = await verifyRepositorySnapshot({
  claims: verifiedJwt.claims,
  manifest,
  fetchImpl,
  nowSeconds,
});
assert.equal(verifiedSnapshot.verified_current_head_sha, currentHead);
assert.equal(verifiedSnapshot.verified_source_head_sha, sourceHead);
assert.equal(verifiedSnapshot.source_head_ancestor_verified, true);
assert.equal(verifiedSnapshot.source_branch, EXPECTED_SOURCE_BRANCH);
assert.equal(verifiedSnapshot.target_branch, EXPECTED_TARGET_BRANCH);
assert.equal(verifiedSnapshot.pull_request_number, '233');
assert.match(verifiedSnapshot.manifest_content_sha256, /^[0-9a-f]{64}$/);
assert.match(verifiedSnapshot.manifest_canonical_sha256, /^[0-9a-f]{64}$/);
assert.equal(verifiedSnapshot.manifest_package_digest_sha256, manifest.package_digest_sha256);
assertNoAuthorityEscalation(verifiedSnapshot);

await assert.rejects(
  verifyGithubOidcJwt((await signJwt({ ...claims, aud: 'wrong-audience' })).token, {
    fetchImpl: createFetch({ publicJwk: signed.publicJwk, manifest }),
    nowSeconds,
  }),
);

await assert.rejects(
  verifyRepositorySnapshot({
    claims,
    manifest,
    fetchImpl: createFetch({ publicJwk: signed.publicJwk, manifest, fork: true }),
    nowSeconds,
  }),
  /fork_pull_request_rejected/,
);

await assert.rejects(
  verifyRepositorySnapshot({
    claims,
    manifest,
    fetchImpl: createFetch({ publicJwk: signed.publicJwk, manifest, compareStatus: 'diverged' }),
    nowSeconds,
  }),
  /manifest_source_head_not_ancestor/,
);

const changedManifest = { ...manifest, semantic_version: '1.0.1' };
await assert.rejects(
  verifyRepositorySnapshot({
    claims,
    manifest,
    fetchImpl: createFetch({ publicJwk: signed.publicJwk, manifest, committedManifest: changedManifest }),
    nowSeconds,
  }),
  /submitted_manifest_not_current_committed_manifest/,
);

const badDigest = { ...manifest, package_digest_sha256: 'f'.repeat(64) };
await assert.rejects(validateManifestShape(badDigest), /manifest_package_digest_recompute_mismatch/);
assert.throws(
  () => assertNoAuthorityEscalation({ ...verifiedSnapshot, money_movement: true }),
  /authority_field_money_movement_must_be_false/,
);
assert.throws(
  () => validateGithubOidcClaims({ ...claims, repository: 'other/repository' }, { nowSeconds }),
  /oidc_repository_invalid/,
);
assert.throws(
  () => validateGithubOidcClaims({ ...claims, exp: nowSeconds - 1000 }, { nowSeconds }),
  /oidc_token_expired/,
);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_INSTITUTIONALIZATION_GITHUB_OIDC_V2',
  rs256_signature_verified: true,
  repository_bound: true,
  pull_request_bound: true,
  workflow_bound: true,
  current_head_bound: true,
  frozen_source_ancestor_verified: true,
  committed_manifest_bound: true,
  package_digest_recomputed: true,
  fork_rejected: true,
  source_divergence_rejected: true,
  committed_manifest_drift_rejected: true,
  authority_escalation_rejected: true,
  token_value_persisted: false,
  provider_write: false,
  money_movement: false,
  chain_broadcast: false,
}));
