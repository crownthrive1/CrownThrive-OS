import assert from 'node:assert/strict';
import {
  encoder,
  decoder,
  canonicalize,
  sha256Hex,
  validateInstitutionalizationManifestV2,
  validateGithubOidcClaimsV2,
  verifyGithubOidcJwtV2,
  verifyRepositorySnapshotV2,
} from './github-oidc-contract-v2.mjs';

assert.ok(encoder instanceof TextEncoder, 'encoder_export_missing');
assert.ok(decoder instanceof TextDecoder, 'decoder_export_missing');
assert.equal(typeof canonicalize, 'function');
assert.equal(typeof sha256Hex, 'function');
assert.equal(typeof validateInstitutionalizationManifestV2, 'function');
assert.equal(typeof validateGithubOidcClaimsV2, 'function');
assert.equal(typeof verifyGithubOidcJwtV2, 'function');
assert.equal(typeof verifyRepositorySnapshotV2, 'function');

const canonical = canonicalize({ z: 1, a: { y: false, x: 'ok' } });
assert.equal(canonical, '{"a":{"x":"ok","y":false},"z":1}');
assert.match(await sha256Hex(canonical), /^[0-9a-f]{64}$/);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_INSTITUTIONALIZATION_RUNTIME_MODULE_LINKAGE_V2',
  encoder_exported: true,
  decoder_exported: true,
  oidc_validator_exported: true,
  repository_binding_exported: true,
  canonicalization_callable: true,
  network_access: false,
  provider_write: false,
  credential_access: false,
  signing: false,
  money_movement: false,
  chain_broadcast: false,
  phase_advancement: false,
  merge_authorized: false
}));
