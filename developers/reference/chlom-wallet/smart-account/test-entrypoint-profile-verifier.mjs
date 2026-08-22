import assert from 'node:assert/strict';
import {
  assertReadOnlyRpcMethod,
  loadProfile,
  normalizeAddress,
  verifyPinnedProfile,
} from './entrypoint-profile-verifier.mjs';

const profile = loadProfile();
const verified = verifyPinnedProfile(profile);
assert.equal(verified.ok, true, JSON.stringify(verified.failures));
assert.equal(verified.failures.length, 0);
assert.equal(verified.profile_digest_sha256.length, 64);
assert.equal(verified.source_divergence_registered, true);
assert.equal(verified.external_read_only_chain_readback_completed, true);
assert.equal(verified.provider_agreement, true);
assert.equal(verified.audit_artifact_pinned, true);
assert.equal(verified.audit_bounded_extraction_completed, true);
assert.equal(verified.audited_source_lineage_to_release, true);
assert.equal(verified.release_runtime_reproduced, true);
assert.equal(verified.reproduced_runtime_matches_observed_runtime, true);
assert.equal(verified.observed_runtime_codehash, '0x280d5c7c0de94b512401eb9c4b0ef0436275ff03627aad0ce1f93ab1627187a0');
assert.equal(verified.runtime_codehash_independently_approved, false);
assert.equal(verified.runtime_codehash_verified, false);
assert.equal(verified.testnet_broadcast_authorized, false);
assert.notEqual(verified.release_address, verified.artifact_address);
assert.equal(normalizeAddress(profile.release_claim.entrypoint_address), verified.release_address);

assert.equal(assertReadOnlyRpcMethod('eth_chainId'), 'eth_chainId');
assert.equal(assertReadOnlyRpcMethod('eth_getCode'), 'eth_getCode');
assert.throws(() => assertReadOnlyRpcMethod('eth_sendRawTransaction'), /rpc_write_method_forbidden/);
assert.throws(() => assertReadOnlyRpcMethod('personal_sign'), /rpc_write_method_forbidden/);
assert.throws(() => assertReadOnlyRpcMethod('eth_getBalance'), /rpc_method_not_allowlisted/);

const falseApproval = structuredClone(profile);
falseApproval.verification.runtime_codehash_independently_approved = true;
assert.equal(verifyPinnedProfile(falseApproval).ok, false);
assert.ok(verifyPinnedProfile(falseApproval).failures.includes('false_independent_approval_claim'));

const falseVerification = structuredClone(profile);
falseVerification.verification.runtime_codehash_verified = true;
assert.equal(verifyPinnedProfile(falseVerification).ok, false);
assert.ok(verifyPinnedProfile(falseVerification).failures.includes('false_runtime_codehash_verification_claim'));

const alteredObservation = structuredClone(profile);
alteredObservation.verification.observed_runtime_codehash = `0x${'00'.repeat(32)}`;
assert.equal(verifyPinnedProfile(alteredObservation).ok, false);
assert.ok(verifyPinnedProfile(alteredObservation).failures.includes('observed_runtime_codehash_mismatch'));

const missingAudit = structuredClone(profile);
missingAudit.verification.audit_artifact_pinned = false;
assert.equal(verifyPinnedProfile(missingAudit).ok, false);
assert.ok(verifyPinnedProfile(missingAudit).failures.includes('audit_artifact_not_pinned'));

const brokenLineage = structuredClone(profile);
brokenLineage.verification.audited_entrypoint_source_blob_matches_release = false;
assert.equal(verifyPinnedProfile(brokenLineage).ok, false);
assert.ok(verifyPinnedProfile(brokenLineage).failures.includes('audited_source_lineage_missing'));

const failedReproduction = structuredClone(profile);
failedReproduction.verification.reproduced_runtime_matches_observed_runtime = false;
assert.equal(verifyPinnedProfile(failedReproduction).ok, false);
assert.ok(verifyPinnedProfile(failedReproduction).failures.includes('runtime_reproduction_mismatch'));

const removedReview = structuredClone(profile);
removedReview.verification.review_request = null;
assert.equal(verifyPinnedProfile(removedReview).ok, false);
assert.ok(verifyPinnedProfile(removedReview).failures.includes('review_request_mismatch'));

const armed = structuredClone(profile);
armed.hard_boundaries.testnet_broadcast = true;
assert.equal(verifyPinnedProfile(armed).ok, false);
assert.ok(verifyPinnedProfile(armed).failures.includes('hard_boundary_armed'));

const collapsed = structuredClone(profile);
collapsed.tagged_deployment_artifact.entrypoint_address = collapsed.release_claim.entrypoint_address;
assert.equal(verifyPinnedProfile(collapsed).ok, false);
assert.ok(verifyPinnedProfile(collapsed).failures.includes('artifact_address_mismatch'));

console.log(JSON.stringify({
  result: 'PASS_ERC4337_V09_AUDIT_RUNTIME_PROFILE_HOLD_INDEPENDENT_REVIEW',
  profile_digest_sha256: verified.profile_digest_sha256,
  official_release_pinned: true,
  tagged_artifact_pinned: true,
  source_divergence_registered: true,
  external_read_only_chain_readback_completed: true,
  provider_agreement: true,
  audit_artifact_pinned: true,
  audit_bounded_extraction_completed: true,
  audited_source_lineage_to_release: true,
  release_runtime_reproduced: true,
  reproduced_runtime_matches_observed_runtime: true,
  observed_runtime_codehash: verified.observed_runtime_codehash,
  runtime_codehash_independently_approved: false,
  runtime_codehash_verified: false,
  rpc_write_methods_rejected: true,
  testnet_broadcast_authorized: false,
}));
