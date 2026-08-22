import assert from 'node:assert/strict';
import { resolveInstitutionalizationGaps, REQUIRED_ARTIFACT_KINDS, REQUIRED_CONTROL_SECTIONS } from './chlom-institutionalization-gap-resolver.mjs';

const artifacts = REQUIRED_ARTIFACT_KINDS.map((kind, index) => ({
  artifact_id: `ct.artifact.test.${index}`,
  kind,
  classification: 'public',
  public_projection: true,
  secret_shape_detected: false,
}));
const spec = {
  algorithms: [{ algorithm_id: 'ct.algorithm.test.v1' }],
  hard_boundaries: { provider_write: false, money_movement: false, phase_advancement: false },
  ...Object.fromEntries(REQUIRED_CONTROL_SECTIONS.filter((section) => section !== 'ai_governance').map((section) => [section, section === 'third_party_dependencies' ? [{ name: 'example' }] : { state: 'present' }])),
  ai_governance: { advisory_only: true, decision_authority: false, write_authority: false },
};

const pass = resolveInstitutionalizationGaps(spec, artifacts);
assert.equal(pass.disposition, 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION');
assert.equal(pass.gap_count, 0);
assert.equal(pass.completeness_score, 100);
assert.equal(pass.authority_effect, 'none');
assert.equal(pass.automatic_release, false);

const missingTest = resolveInstitutionalizationGaps(spec, artifacts.filter((artifact) => artifact.kind !== 'test'));
assert.equal(missingTest.disposition, 'HOLD_INSTITUTIONALIZATION_GAPS');
assert.ok(missingTest.gaps.some((gap) => gap.code === 'MISSING_ARTIFACT_KIND_TEST'));

const duplicateAlgorithm = resolveInstitutionalizationGaps({
  ...spec,
  algorithms: [{ algorithm_id: 'ct.algorithm.duplicate' }, { algorithm_id: 'ct.algorithm.duplicate' }],
}, artifacts);
assert.ok(duplicateAlgorithm.gaps.some((gap) => gap.code === 'DUPLICATE_ALGORITHM_ID'));

const publicLeak = resolveInstitutionalizationGaps(spec, artifacts.map((artifact, index) => index === 0 ? { ...artifact, classification: 'restricted' } : artifact));
assert.ok(publicLeak.gaps.some((gap) => gap.code === 'NONPUBLIC_ARTIFACT_IN_PUBLIC_PROJECTION'));

const secret = resolveInstitutionalizationGaps(spec, artifacts.map((artifact, index) => index === 0 ? { ...artifact, secret_shape_detected: true } : artifact));
assert.ok(secret.gaps.some((gap) => gap.code === 'SECRET_SHAPE_DETECTED'));

const live = resolveInstitutionalizationGaps({ ...spec, hard_boundaries: { provider_write: true } }, artifacts);
assert.ok(live.gaps.some((gap) => gap.code === 'HARD_BOUNDARY_NOT_FALSE'));

const aiAuthority = resolveInstitutionalizationGaps({ ...spec, ai_governance: { advisory_only: true, decision_authority: true, write_authority: false } }, artifacts);
assert.ok(aiAuthority.gaps.some((gap) => gap.code === 'AI_GOVERNANCE_BOUNDARY_INVALID'));

console.log(JSON.stringify({
  result: 'PASS_CHLOM_INSTITUTIONALIZATION_GAP_RESOLVER',
  required_artifact_kinds: REQUIRED_ARTIFACT_KINDS.length,
  required_control_sections: REQUIRED_CONTROL_SECTIONS.length,
  missing_test_holds: true,
  duplicate_algorithm_holds: true,
  public_restricted_leak_holds: true,
  secret_shape_holds: true,
  live_boundary_holds: true,
  ai_authority_holds: true,
  automatic_release: false,
}));
