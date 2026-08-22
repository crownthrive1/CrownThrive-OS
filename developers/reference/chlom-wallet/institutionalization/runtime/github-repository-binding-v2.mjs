import {
  decoder,
  asObject,
  requireString,
  base64Decode,
  canonicalize,
  sha256Hex,
  validateInstitutionalizationManifestV2,
  CROWNTHRIVE_REPOSITORY,
  CROWNTHRIVE_REPOSITORY_ID,
  CROWNTHRIVE_REPOSITORY_OWNER,
  CROWNTHRIVE_REPOSITORY_OWNER_ID,
  CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
  INSTITUTIONALIZATION_V2_SOURCE_BRANCH,
  INSTITUTIONALIZATION_V2_TARGET_BRANCH,
  INSTITUTIONALIZATION_V2_PR_NUMBER,
  INSTITUTIONALIZATION_V2_MANIFEST_PATH,
  INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD,
} from './oidc-runtime-utils-v2.mjs';
import { validateGithubOidcClaimsV2, fetchJson } from './oidc-jwt-verifier-v2.mjs';

async function fetchCurrentPullSnapshot({ fetchImpl }) {
  const pull = await fetchJson(`https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/pulls/${INSTITUTIONALIZATION_V2_PR_NUMBER}`, { fetchImpl });
  if (pull?.head?.repo?.full_name !== CROWNTHRIVE_REPOSITORY) throw new Error('github_fork_pull_request_rejected');
  if (pull?.head?.ref !== INSTITUTIONALIZATION_V2_SOURCE_BRANCH) throw new Error('github_pull_source_branch_invalid');
  if (pull?.base?.ref !== INSTITUTIONALIZATION_V2_TARGET_BRANCH) throw new Error('github_pull_target_branch_invalid');
  if (pull?.state !== 'open') throw new Error('github_pull_not_open');
  return {
    currentHeadSha: requireString(pull?.head?.sha, 'github_pull_head_invalid', /^[0-9a-f]{40}$/),
    targetBaseSha: requireString(pull?.base?.sha, 'github_pull_base_invalid', /^[0-9a-f]{40}$/),
    sourceBranch: pull.head.ref,
    targetBranch: pull.base.ref,
    pullRequestNumber: INSTITUTIONALIZATION_V2_PR_NUMBER,
  };
}

async function fetchCurrentBranchSnapshot({ fetchImpl }) {
  const encodedBranch = encodeURIComponent(INSTITUTIONALIZATION_V2_SOURCE_BRANCH);
  const branch = await fetchJson(`https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/branches/${encodedBranch}`, { fetchImpl });
  return {
    currentHeadSha: requireString(branch?.commit?.sha, 'github_branch_head_invalid', /^[0-9a-f]{40}$/),
    targetBaseSha: null,
    sourceBranch: INSTITUTIONALIZATION_V2_SOURCE_BRANCH,
    targetBranch: null,
    pullRequestNumber: null,
  };
}

async function verifyFrozenSourceAncestry(currentHeadSha, { fetchImpl }) {
  const compare = await fetchJson(`https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/compare/${INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD}...${currentHeadSha}`, { fetchImpl });
  if (!['ahead', 'identical'].includes(compare?.status)) throw new Error('github_source_head_not_ancestor');
  if (compare?.merge_base_commit?.sha !== INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD) throw new Error('github_source_merge_base_invalid');
  if (Number(compare?.behind_by ?? 0) !== 0) throw new Error('github_source_ancestry_behind');
  return true;
}

async function fetchCommittedManifest(currentHeadSha, { fetchImpl }) {
  const encodedPath = INSTITUTIONALIZATION_V2_MANIFEST_PATH.split('/').map(encodeURIComponent).join('/');
  const content = await fetchJson(`https://api.github.com/repos/${CROWNTHRIVE_REPOSITORY}/contents/${encodedPath}?ref=${currentHeadSha}`, { fetchImpl });
  if (content?.type !== 'file' || content?.encoding !== 'base64') throw new Error('github_manifest_content_invalid');
  const rawBytes = base64Decode(requireString(content.content, 'github_manifest_base64_invalid', null, 3_000_000), { maxBytes: 2_000_000 });
  let parsed;
  try {
    parsed = asObject(JSON.parse(decoder.decode(rawBytes)), 'github_manifest_json_invalid');
  } catch (error) {
    if (error instanceof Error && error.message === 'github_manifest_json_invalid') throw error;
    throw new Error('github_manifest_json_invalid');
  }
  return {
    parsed,
    rawBytes,
    contentSha: requireString(content.sha, 'github_manifest_blob_sha_invalid', /^[0-9a-f]{40}$/),
  };
}

export async function verifyRepositorySnapshotV2({ claims, manifest, fetchImpl = fetch, nowSeconds = Math.floor(Date.now() / 1000) }) {
  const c = validateGithubOidcClaimsV2(claims, { nowSeconds });
  const m = await validateInstitutionalizationManifestV2(manifest);
  const repositorySnapshot = c.event_name === 'pull_request'
    ? await fetchCurrentPullSnapshot({ fetchImpl })
    : await fetchCurrentBranchSnapshot({ fetchImpl });

  if (c.event_name === 'pull_request') {
    const match = /^refs\/pull\/(\d+)\/merge$/.exec(c.ref);
    if (!match || Number(match[1]) !== INSTITUTIONALIZATION_V2_PR_NUMBER) throw new Error('oidc_pull_request_ref_invalid');
    if (c.head_ref !== repositorySnapshot.sourceBranch || c.base_ref !== repositorySnapshot.targetBranch) throw new Error('oidc_pull_branch_claim_mismatch');
  }
  await verifyFrozenSourceAncestry(repositorySnapshot.currentHeadSha, { fetchImpl });
  const committed = await fetchCommittedManifest(repositorySnapshot.currentHeadSha, { fetchImpl });
  await validateInstitutionalizationManifestV2(committed.parsed);
  if (canonicalize(committed.parsed) !== canonicalize(m)) throw new Error('submitted_manifest_not_committed_manifest');
  const manifestContentSha256 = await sha256Hex(committed.rawBytes);
  const manifestCanonicalSha256 = await sha256Hex(canonicalize(committed.parsed));

  return {
    repository: CROWNTHRIVE_REPOSITORY,
    repository_id: CROWNTHRIVE_REPOSITORY_ID,
    repository_owner: CROWNTHRIVE_REPOSITORY_OWNER,
    repository_owner_id: CROWNTHRIVE_REPOSITORY_OWNER_ID,
    repository_visibility: c.repository_visibility,
    event_name: c.event_name,
    ref: c.ref,
    head_ref: c.head_ref ?? null,
    base_ref: c.base_ref ?? null,
    source_branch: repositorySnapshot.sourceBranch,
    target_branch: repositorySnapshot.targetBranch,
    pull_request_number: repositorySnapshot.pullRequestNumber === null ? null : String(repositorySnapshot.pullRequestNumber),
    verified_current_head_sha: repositorySnapshot.currentHeadSha,
    verified_source_head_sha: INSTITUTIONALIZATION_V2_FROZEN_SOURCE_HEAD,
    source_head_ancestor_verified: true,
    manifest_path: INSTITUTIONALIZATION_V2_MANIFEST_PATH,
    manifest_blob_sha1: committed.contentSha,
    manifest_content_sha256: manifestContentSha256,
    manifest_canonical_sha256: manifestCanonicalSha256,
    manifest_package_digest_sha256: m.package_digest_sha256,
    workflow: c.workflow,
    workflow_ref: c.workflow_ref,
    workflow_sha: c.workflow_sha,
    github_event_sha: c.sha,
    github_run_id: String(c.run_id),
    github_run_number: String(c.run_number ?? ''),
    github_run_attempt: String(c.run_attempt),
    github_actor: c.actor,
    github_actor_id: String(c.actor_id),
    oidc_jti: c.jti,
    oidc_issuer: c.iss,
    oidc_audience: CHLOM_INSTITUTIONALIZATION_V2_AUDIENCE,
    oidc_subject: c.sub,
    runner_environment: c.runner_environment,
    manifest_binding_verified: true,
    provider_write: false,
    credential_access: false,
    effective_offer: false,
    stripe_objects_created: false,
    checkout_enabled: false,
    custody: false,
    token_issuance: false,
    money_movement: false,
    rights_grant: false,
    production_rights_grant: false,
    chain_broadcast: false,
    phase_advancement: false,
    merge_authorized: false,
    automatic_profile_promotion: false,
  };
}
