import {
  canonicalize,
  sha256Hex,
  asObject,
} from './oidc-runtime-utils-v2.mjs';

export const INSTITUTIONALIZATION_V3_AUDIENCE = 'chlom-wallet-institutionalization-v3';
export const INSTITUTIONALIZATION_V3_SOURCE_BRANCH = 'chlom-wallet/phase-c-proof-portability-20260822';
export const INSTITUTIONALIZATION_V3_TARGET_BRANCH = 'chlom-wallet/phase-b-webhook-passkey-contracts-20260822';
export const INSTITUTIONALIZATION_V3_PR_NUMBER = 233;

const COMMON = Object.freeze({
  repository: 'crownthrive1/CrownThrive-Support',
  repository_id: '1336348391',
  repository_owner: 'crownthrive1',
  repository_owner_id: '315660018',
  source_branch: INSTITUTIONALIZATION_V3_SOURCE_BRANCH,
  target_branch: INSTITUTIONALIZATION_V3_TARGET_BRANCH,
  pull_request_number: INSTITUTIONALIZATION_V3_PR_NUMBER,
  repository_visibility: 'public',
});

export const PACKAGE_CONTRACTS_V3 = Object.freeze({
  'ct.package.chlom-wallet.phase-c.institutionalization.v1@1.0.0': Object.freeze({
    ...COMMON,
    package_id: 'ct.package.chlom-wallet.phase-c.institutionalization.v1',
    semantic_version: '1.0.0',
    package_digest_sha256: '7b3be50d5541fff14127bfdd24724eb9b8b9f9ffd4b165a380dee02f2a1ef957',
    frozen_source_head: '64118e61c7671a78b43999ac5f17f9eddd1226b1',
    manifest_path: 'developers/manifests/chlom-wallet-phase-c-institutionalization.v1.json',
    artifact_count: 17,
    algorithm_count: 5,
    gap_count: 0,
    completeness_score: 100,
    workflow_name: 'CHLOM Institutionalization Package v2',
    workflow_path: '.github/workflows/chlom-wallet-institutionalization-v2.yml',
    oidc_audience: 'chlom-wallet-institutionalization-v2',
    predecessor_package_id: null,
    predecessor_digest_sha256: null,
  }),
  'ct.package.chlom-wallet.phase-c.institutionalization.v2@2.0.0': Object.freeze({
    ...COMMON,
    package_id: 'ct.package.chlom-wallet.phase-c.institutionalization.v2',
    semantic_version: '2.0.0',
    package_digest_sha256: 'c3433c0cc3f97003a8fbe75a5308edf68bf3b2bd19882d90dfeefe2bd2e15248',
    frozen_source_head: 'd6187bd9a9a5af12cf1121d761d325943cc63daa',
    manifest_path: 'developers/manifests/chlom-wallet-phase-c-institutionalization.v2.json',
    artifact_count: 19,
    algorithm_count: 4,
    gap_count: 0,
    completeness_score: 100,
    workflow_name: 'CHLOM Institutionalization Continuity Package v3',
    workflow_path: '.github/workflows/chlom-wallet-institutionalization-continuity-v3.yml',
    oidc_audience: INSTITUTIONALIZATION_V3_AUDIENCE,
    predecessor_package_id: 'ct.package.chlom-wallet.phase-c.institutionalization.v1',
    predecessor_digest_sha256: '7b3be50d5541fff14127bfdd24724eb9b8b9f9ffd4b165a380dee02f2a1ef957',
  }),
});

const FALSE_BOUNDARIES = Object.freeze([
  'originator_self_approval',
  'automatic_authority_grant',
  'automatic_reviewer_heartbeat',
  'automatic_review_receipt',
  'provider_write',
  'credential_access',
  'signing',
  'custody',
  'token_issuance',
  'money_movement',
  'production_rights_grant',
  'chain_broadcast',
  'effective_price_publication',
  'checkout_activation',
  'phase_advancement',
  'merge_authorized',
]);

function exact(value, expected, code) {
  if (value !== expected) throw new Error(code);
}

function integer(value, code) {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(code);
  return value;
}

function validateFalseBoundaries(boundaries) {
  const object = asObject(boundaries, 'v3_hard_boundaries_required');
  for (const field of FALSE_BOUNDARIES) {
    if (object[field] !== false) throw new Error(`v3_boundary_${field}_must_be_false`);
  }
  for (const [field, value] of Object.entries(object)) {
    if (value === true) throw new Error(`v3_boundary_${field}_must_be_false`);
  }
  return true;
}

export function resolveInstitutionalizationPackageContractV3(packageId, semanticVersion) {
  const key = `${packageId}@${semanticVersion}`;
  const contract = PACKAGE_CONTRACTS_V3[key];
  if (!contract) throw new Error('v3_package_contract_not_registered');
  return contract;
}

export function packageContractKeyV3(manifest) {
  const m = asObject(manifest, 'v3_manifest_object_required');
  return `${String(m.package_id ?? '')}@${String(m.semantic_version ?? '')}`;
}

export async function validateInstitutionalizationManifestV3(manifest) {
  const m = asObject(manifest, 'v3_manifest_object_required');
  exact(m.schema_version, '1.0.0', 'v3_manifest_schema_version_invalid');
  const contract = resolveInstitutionalizationPackageContractV3(m.package_id, m.semantic_version);
  exact(m.package_digest_sha256, contract.package_digest_sha256, 'v3_package_digest_unpinned');
  exact(m.state, 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION', 'v3_manifest_not_pass');

  const snapshot = asObject(m.source_snapshot, 'v3_source_snapshot_required');
  exact(snapshot.repository, contract.repository, 'v3_repository_mismatch');
  exact(snapshot.branch, contract.source_branch, 'v3_source_branch_mismatch');
  exact(snapshot.head_sha, contract.frozen_source_head, 'v3_frozen_source_head_mismatch');

  const artifacts = Array.isArray(m.artifact_inventory) ? m.artifact_inventory : null;
  if (!artifacts || artifacts.length !== contract.artifact_count) throw new Error('v3_artifact_count_mismatch');
  if (integer(m?.artifact_counts?.total, 'v3_artifact_total_invalid') !== contract.artifact_count) throw new Error('v3_artifact_total_mismatch');
  const algorithms = Array.isArray(m.algorithm_registry) ? m.algorithm_registry : null;
  if (!algorithms || algorithms.length !== contract.algorithm_count) throw new Error('v3_algorithm_count_mismatch');
  if (integer(m?.gap_analysis?.gap_count, 'v3_gap_count_invalid') !== contract.gap_count) throw new Error('v3_gap_count_mismatch');
  if (integer(m?.gap_analysis?.completeness_score, 'v3_completeness_invalid') !== contract.completeness_score) throw new Error('v3_completeness_mismatch');

  exact(m?.docs_impact?.state, 'DOCS_UPDATED', 'v3_docs_state_mismatch');
  exact(m?.security?.state, 'CONTROLLED_TEST', 'v3_security_state_mismatch');
  exact(m?.privacy?.state, 'CONTROLLED_TEST', 'v3_privacy_state_mismatch');
  exact(m?.rights?.state, 'HOLD_INDEPENDENT_RIGHTS_REVIEW', 'v3_rights_state_mismatch');
  exact(m?.commercialization?.state, 'PRICE_REVIEW', 'v3_commercialization_state_mismatch');
  exact(m?.scheduler?.state, 'NO_NEW_EXTERNAL_SLOT', 'v3_scheduler_state_mismatch');
  if (m?.ai_governance?.advisory_only !== true) throw new Error('v3_ai_advisory_only_required');
  if (m?.ai_governance?.decision_authority !== false) throw new Error('v3_ai_decision_authority_forbidden');
  if (m?.ai_governance?.write_authority !== false) throw new Error('v3_ai_write_authority_forbidden');
  if (m?.ai_governance?.automatic_release !== false) throw new Error('v3_ai_automatic_release_forbidden');
  validateFalseBoundaries(m.hard_boundaries);

  for (const artifact of artifacts) {
    const a = asObject(artifact, 'v3_artifact_object_invalid');
    if (a.secret_shape_detected !== false) throw new Error('v3_artifact_secret_shape_detected');
    if (typeof a.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(a.sha256)) throw new Error('v3_artifact_digest_invalid');
    if (typeof a.path !== 'string' || a.path.length < 3) throw new Error('v3_artifact_path_invalid');
  }

  const withoutDigest = { ...m };
  delete withoutDigest.package_digest_sha256;
  const recomputed = await sha256Hex(canonicalize(withoutDigest));
  exact(recomputed, contract.package_digest_sha256, 'v3_package_digest_recompute_mismatch');

  return { manifest: m, contract };
}

export function allowedGithubSubjectsV3(contract, eventName) {
  if (eventName === 'pull_request') {
    return new Set([
      `repo:${contract.repository}:pull_request`,
      `repo:${contract.repository_owner}@${contract.repository_owner_id}/CrownThrive-Support@${contract.repository_id}:pull_request`,
    ]);
  }
  if (eventName === 'workflow_dispatch') {
    const suffix = `:ref:refs/heads/${contract.source_branch}`;
    return new Set([
      `repo:${contract.repository}${suffix}`,
      `repo:${contract.repository_owner}@${contract.repository_owner_id}/CrownThrive-Support@${contract.repository_id}${suffix}`,
    ]);
  }
  return new Set();
}

export function institutionalizationV3NoAuthorityFields() {
  return [...FALSE_BOUNDARIES];
}
