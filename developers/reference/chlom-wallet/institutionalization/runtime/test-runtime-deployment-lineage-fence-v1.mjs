import assert from 'node:assert/strict';
import { evaluateRuntimeDeploymentLineageV1 } from './runtime-deployment-lineage-fence-v1.mjs';

const good = {
  source: {
    runtime_utils_blob_sha1: '33a74f3c294947ab6df04a2a1710697e7563bfeb',
    exports: ['encoder', 'decoder', 'canonicalize', 'sha256Hex'],
    module_linkage_result: 'PASS_CHLOM_INSTITUTIONALIZATION_RUNTIME_MODULE_LINKAGE_V2',
  },
  deployment: {
    service_id: 'ct.service.chlom-wallet-institutionalize-v2',
    function_id: 'a9fa1f5d-908d-4807-9d35-20c95d161507',
    version: 4,
    status: 'ACTIVE',
    verify_jwt: false,
    authentication_mode: 'INTERNAL_GITHUB_OIDC_RS256_JWKS_VERIFICATION',
    ezbr_sha256: '9dfec88ed84103fb43e332a11b1877d87f01fb3eae2b280b1125434b4a711b4f',
  },
  liveness: {
    unauthenticated_http_status: 401,
    unauthenticated_error: 'github_oidc_bearer_required',
    fail_closed: true,
  },
  ingest: {
    package_id: 'ct.package.chlom-wallet.phase-c.institutionalization.v1',
    package_digest_sha256: '7b3be50d5541fff14127bfdd24724eb9b8b9f9ffd4b165a380dee02f2a1ef957',
    real_package_recorded: true,
    real_oidc_ingest_receipt_recorded: true,
    source_head_ancestor_verified: true,
    token_value_persisted: false,
    raw_artifact_body_persisted: false,
  },
  hard_boundaries: {
    provider_write: false,
    credential_access: false,
    effective_offer: false,
    stripe_objects_created: false,
    checkout_enabled: false,
    signing: false,
    custody: false,
    token_issuance: false,
    money_movement: false,
    production_rights_grant: false,
    chain_broadcast: false,
    automatic_profile_promotion: false,
    phase_advancement: false,
    merge_authorized: false,
  },
};

const pass = await evaluateRuntimeDeploymentLineageV1(good);
assert.equal(pass.result, 'PASS_CHLOM_RUNTIME_DEPLOYMENT_LINEAGE_FENCE_V1');
assert.match(pass.evidence_digest_sha256, /^[0-9a-f]{64}$/);
assert.deepEqual(pass, await evaluateRuntimeDeploymentLineageV1(structuredClone(good)));

const negativeCases = [
  ['stale_version', (x) => { x.deployment.version = 3; }, /rdlf_deployment_version_stale/],
  ['inactive', (x) => { x.deployment.status = 'FAILED'; }, /rdlf_deployment_not_active/],
  ['wrong_jwt_mode', (x) => { x.deployment.verify_jwt = true; }, /rdlf_platform_jwt_mode_drift/],
  ['wrong_ezbr', (x) => { x.deployment.ezbr_sha256 = '0'.repeat(64); }, /rdlf_ezbr_mismatch/],
  ['wrong_source_blob', (x) => { x.source.runtime_utils_blob_sha1 = '0'.repeat(40); }, /rdlf_source_blob_mismatch/],
  ['missing_encoder_export', (x) => { x.source.exports = x.source.exports.filter((v) => v !== 'encoder'); }, /rdlf_required_export_missing_encoder/],
  ['missing_decoder_export', (x) => { x.source.exports = x.source.exports.filter((v) => v !== 'decoder'); }, /rdlf_required_export_missing_decoder/],
  ['linkage_not_pass', (x) => { x.source.module_linkage_result = 'HOLD'; }, /rdlf_module_linkage_not_pass/],
  ['wrong_liveness_status', (x) => { x.liveness.unauthenticated_http_status = 503; }, /rdlf_unauthenticated_status_not_401/],
  ['wrong_liveness_error', (x) => { x.liveness.unauthenticated_error = 'BOOT_ERROR'; }, /rdlf_unauthenticated_error_drift/],
  ['liveness_not_fail_closed', (x) => { x.liveness.fail_closed = false; }, /rdlf_liveness_not_fail_closed/],
  ['wrong_package', (x) => { x.ingest.package_id = 'ct.package.wrong'; }, /rdlf_package_id_mismatch/],
  ['wrong_package_digest', (x) => { x.ingest.package_digest_sha256 = '1'.repeat(64); }, /rdlf_package_digest_mismatch/],
  ['package_missing', (x) => { x.ingest.real_package_recorded = false; }, /rdlf_real_package_missing/],
  ['oidc_receipt_missing', (x) => { x.ingest.real_oidc_ingest_receipt_recorded = false; }, /rdlf_real_oidc_receipt_missing/],
  ['ancestry_missing', (x) => { x.ingest.source_head_ancestor_verified = false; }, /rdlf_source_ancestry_not_verified/],
  ['token_persisted', (x) => { x.ingest.token_value_persisted = true; }, /rdlf_token_value_persisted/],
  ['raw_artifact_persisted', (x) => { x.ingest.raw_artifact_body_persisted = true; }, /rdlf_raw_artifact_body_persisted/],
  ['provider_write', (x) => { x.hard_boundaries.provider_write = true; }, /rdlf_boundary_provider_write_must_be_false/],
  ['money_movement', (x) => { x.hard_boundaries.money_movement = true; }, /rdlf_boundary_money_movement_must_be_false/],
  ['chain_broadcast', (x) => { x.hard_boundaries.chain_broadcast = true; }, /rdlf_boundary_chain_broadcast_must_be_false/],
  ['phase_advancement', (x) => { x.hard_boundaries.phase_advancement = true; }, /rdlf_boundary_phase_advancement_must_be_false/],
];

for (const [name, mutate, expected] of negativeCases) {
  const candidate = structuredClone(good);
  mutate(candidate);
  await assert.rejects(() => evaluateRuntimeDeploymentLineageV1(candidate), expected, name);
}

console.log(JSON.stringify({
  result: 'PASS_CHLOM_RUNTIME_DEPLOYMENT_LINEAGE_FENCE_V1_TESTS',
  deterministic_pass: true,
  negative_cases: negativeCases.length,
  stale_deployment_rejected: true,
  module_export_drift_rejected: true,
  liveness_drift_rejected: true,
  missing_real_ingest_rejected: true,
  authority_escalation_rejected: true,
  network_access: false,
  provider_write: false,
  signing: false,
  money_movement: false,
  chain_broadcast: false,
  phase_advancement: false,
  merge_authorized: false
}));
