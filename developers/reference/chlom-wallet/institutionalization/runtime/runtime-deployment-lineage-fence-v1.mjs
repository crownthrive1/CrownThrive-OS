import { canonicalize, sha256Hex } from './oidc-runtime-utils-v2.mjs';

function asObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
  return value;
}

function exactString(value, expected, code) {
  if (value !== expected) throw new Error(code);
  return value;
}

function boolFalse(value, code) {
  if (value !== false) throw new Error(code);
  return false;
}

function positiveInteger(value, code) {
  if (!Number.isSafeInteger(value) || value < 1) throw new Error(code);
  return value;
}

function sha1(value, code) {
  if (typeof value !== 'string' || !/^[0-9a-f]{40}$/.test(value)) throw new Error(code);
  return value;
}

function sha256(value, code) {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) throw new Error(code);
  return value;
}

const AUTHORITY_FIELDS = Object.freeze([
  'provider_write',
  'credential_access',
  'effective_offer',
  'stripe_objects_created',
  'checkout_enabled',
  'signing',
  'custody',
  'token_issuance',
  'money_movement',
  'production_rights_grant',
  'chain_broadcast',
  'automatic_profile_promotion',
  'phase_advancement',
  'merge_authorized',
]);

export const RUNTIME_DEPLOYMENT_LINEAGE_FENCE = Object.freeze({
  algorithm_id: 'ct.algorithm.chlom.runtime-deployment-lineage-fence.v1',
  short_name: 'RDLF',
  semantic_version: '1.0.0',
  service_id: 'ct.service.chlom-wallet-institutionalize-v2',
  function_id: 'a9fa1f5d-908d-4807-9d35-20c95d161507',
  required_runtime_utils_blob_sha1: '33a74f3c294947ab6df04a2a1710697e7563bfeb',
  required_exports: ['encoder', 'decoder'],
  corrected_minimum_version: 4,
  corrected_ezbr_sha256: '9dfec88ed84103fb43e332a11b1877d87f01fb3eae2b280b1125434b4a711b4f',
  frozen_package_id: 'ct.package.chlom-wallet.phase-c.institutionalization.v1',
  frozen_package_digest_sha256: '7b3be50d5541fff14127bfdd24724eb9b8b9f9ffd4b165a380dee02f2a1ef957',
});

export async function evaluateRuntimeDeploymentLineageV1(input) {
  const root = asObject(input, 'rdlf_input_object_required');
  const source = asObject(root.source, 'rdlf_source_required');
  const deployment = asObject(root.deployment, 'rdlf_deployment_required');
  const liveness = asObject(root.liveness, 'rdlf_liveness_required');
  const ingest = asObject(root.ingest, 'rdlf_ingest_required');
  const boundaries = asObject(root.hard_boundaries, 'rdlf_boundaries_required');

  exactString(deployment.service_id, RUNTIME_DEPLOYMENT_LINEAGE_FENCE.service_id, 'rdlf_service_id_mismatch');
  exactString(deployment.function_id, RUNTIME_DEPLOYMENT_LINEAGE_FENCE.function_id, 'rdlf_function_id_mismatch');
  if (positiveInteger(deployment.version, 'rdlf_version_invalid') < RUNTIME_DEPLOYMENT_LINEAGE_FENCE.corrected_minimum_version) {
    throw new Error('rdlf_deployment_version_stale');
  }
  exactString(deployment.status, 'ACTIVE', 'rdlf_deployment_not_active');
  if (deployment.verify_jwt !== false) throw new Error('rdlf_platform_jwt_mode_drift');
  exactString(deployment.authentication_mode, 'INTERNAL_GITHUB_OIDC_RS256_JWKS_VERIFICATION', 'rdlf_authentication_mode_drift');
  exactString(sha256(deployment.ezbr_sha256, 'rdlf_ezbr_invalid'), RUNTIME_DEPLOYMENT_LINEAGE_FENCE.corrected_ezbr_sha256, 'rdlf_ezbr_mismatch');

  exactString(sha1(source.runtime_utils_blob_sha1, 'rdlf_runtime_utils_blob_invalid'), RUNTIME_DEPLOYMENT_LINEAGE_FENCE.required_runtime_utils_blob_sha1, 'rdlf_source_blob_mismatch');
  if (!Array.isArray(source.exports)) throw new Error('rdlf_source_exports_invalid');
  for (const requiredExport of RUNTIME_DEPLOYMENT_LINEAGE_FENCE.required_exports) {
    if (!source.exports.includes(requiredExport)) throw new Error(`rdlf_required_export_missing_${requiredExport}`);
  }
  if (source.module_linkage_result !== 'PASS_CHLOM_INSTITUTIONALIZATION_RUNTIME_MODULE_LINKAGE_V2') {
    throw new Error('rdlf_module_linkage_not_pass');
  }

  if (liveness.unauthenticated_http_status !== 401) throw new Error('rdlf_unauthenticated_status_not_401');
  exactString(liveness.unauthenticated_error, 'github_oidc_bearer_required', 'rdlf_unauthenticated_error_drift');
  if (liveness.fail_closed !== true) throw new Error('rdlf_liveness_not_fail_closed');

  exactString(ingest.package_id, RUNTIME_DEPLOYMENT_LINEAGE_FENCE.frozen_package_id, 'rdlf_package_id_mismatch');
  exactString(sha256(ingest.package_digest_sha256, 'rdlf_package_digest_invalid'), RUNTIME_DEPLOYMENT_LINEAGE_FENCE.frozen_package_digest_sha256, 'rdlf_package_digest_mismatch');
  if (ingest.real_package_recorded !== true) throw new Error('rdlf_real_package_missing');
  if (ingest.real_oidc_ingest_receipt_recorded !== true) throw new Error('rdlf_real_oidc_receipt_missing');
  if (ingest.source_head_ancestor_verified !== true) throw new Error('rdlf_source_ancestry_not_verified');
  if (ingest.token_value_persisted !== false) throw new Error('rdlf_token_value_persisted');
  if (ingest.raw_artifact_body_persisted !== false) throw new Error('rdlf_raw_artifact_body_persisted');

  for (const field of AUTHORITY_FIELDS) boolFalse(boundaries[field], `rdlf_boundary_${field}_must_be_false`);

  const evidence = {
    algorithm_id: RUNTIME_DEPLOYMENT_LINEAGE_FENCE.algorithm_id,
    semantic_version: RUNTIME_DEPLOYMENT_LINEAGE_FENCE.semantic_version,
    result: 'PASS_CHLOM_RUNTIME_DEPLOYMENT_LINEAGE_FENCE_V1',
    source: {
      runtime_utils_blob_sha1: source.runtime_utils_blob_sha1,
      required_exports: [...RUNTIME_DEPLOYMENT_LINEAGE_FENCE.required_exports],
      module_linkage_result: source.module_linkage_result,
    },
    deployment: {
      service_id: deployment.service_id,
      function_id: deployment.function_id,
      version: deployment.version,
      status: deployment.status,
      verify_jwt: deployment.verify_jwt,
      authentication_mode: deployment.authentication_mode,
      ezbr_sha256: deployment.ezbr_sha256,
    },
    liveness: {
      unauthenticated_http_status: liveness.unauthenticated_http_status,
      unauthenticated_error: liveness.unauthenticated_error,
      fail_closed: liveness.fail_closed,
    },
    ingest: {
      package_id: ingest.package_id,
      package_digest_sha256: ingest.package_digest_sha256,
      real_package_recorded: true,
      real_oidc_ingest_receipt_recorded: true,
      source_head_ancestor_verified: true,
      token_value_persisted: false,
      raw_artifact_body_persisted: false,
    },
    hard_boundaries: Object.fromEntries(AUTHORITY_FIELDS.map((field) => [field, false])),
  };

  return {
    ...evidence,
    evidence_digest_sha256: await sha256Hex(canonicalize(evidence)),
  };
}
