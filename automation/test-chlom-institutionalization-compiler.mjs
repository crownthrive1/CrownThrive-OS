import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { compileInstitutionalizationPackage, stableJson } from './compile-chlom-institutionalization.mjs';
import { REQUIRED_ARTIFACT_KINDS, REQUIRED_CONTROL_SECTIONS } from './chlom-institutionalization-gap-resolver.mjs';

function makeRepo() {
  const root = mkdtempSync(join(tmpdir(), 'cicc-test-'));
  mkdirSync(join(root, 'artifacts'), { recursive: true });
  const artifacts = REQUIRED_ARTIFACT_KINDS.map((kind, index) => {
    const path = `artifacts/${String(index).padStart(2, '0')}-${kind}.txt`;
    writeFileSync(join(root, path), `controlled-test ${kind} artifact ${index}\n`, 'utf8');
    return {
      artifact_id: `ct.artifact.cicc.test.${kind}`,
      path,
      kind,
      classification: 'public',
      owner_agent_id: 'ct.agent.chlom-wallet-settlement',
      status: 'CONTROLLED_TEST',
      public_projection: true,
    };
  });
  return { root, artifacts };
}

function baseSpec(artifacts) {
  return {
    package_id: 'ct.package.chlom-wallet.test.institutionalization.v1',
    semantic_version: '1.0.0',
    state: 'CONTROLLED_TEST',
    source_snapshot: {
      repository: 'crownthrive1/CrownThrive-Support',
      branch: 'chlom-wallet/test',
      head_sha: '1'.repeat(40),
      observed_on: '2026-08-22',
    },
    artifacts,
    algorithms: [{
      algorithm_id: 'ct.algorithm.chlom.test.v1',
      semantic_version: '1.0.0',
      classification: 'proprietary_controlled_test',
      source_paths: [artifacts.find((artifact) => artifact.kind === 'algorithm').path],
      invariants: ['deterministic', 'no authority'],
      proprietary_scope: 'test',
      external_dependencies: [],
    }],
    output_contract: { path: 'developers/manifests/test.json', committed_manifest_required: true, deterministic_rebuild_required: true },
    hard_boundaries: {
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
    ...Object.fromEntries(REQUIRED_CONTROL_SECTIONS.filter((section) => section !== 'ai_governance').map((section) => [section, section === 'third_party_dependencies' ? [{ name: 'Node.js', version: '22' }] : { state: 'CONTROLLED_TEST' }])),
    ai_governance: { advisory_only: true, decision_authority: false, write_authority: false, output_requires_independent_review: true },
  };
}

const positive = makeRepo();
const spec = baseSpec(positive.artifacts);
const first = compileInstitutionalizationPackage(spec, positive.root);
const second = compileInstitutionalizationPackage(spec, positive.root);
assert.deepEqual(first, second);
assert.equal(stableJson(first), stableJson(second));
assert.equal(first.state, 'PASS_CONTROLLED_TEST_INSTITUTIONALIZATION');
assert.equal(first.gap_analysis.completeness_score, 100);
assert.match(first.package_digest_sha256, /^[0-9a-f]{64}$/);
assert.equal(first.artifact_counts.total, REQUIRED_ARTIFACT_KINDS.length);
assert.equal(first.compiler.network_access, false);
assert.equal(first.compiler.provider_write, false);
assert.equal(first.compiler.money_movement, false);
assert.ok(first.artifact_inventory.every((artifact) => artifact.secret_shape_detected === false));

const missingTest = compileInstitutionalizationPackage({ ...spec, artifacts: spec.artifacts.filter((artifact) => artifact.kind !== 'test') }, positive.root);
assert.equal(missingTest.state, 'HOLD_INSTITUTIONALIZATION_GAPS');
assert.ok(missingTest.gap_analysis.gaps.some((gap) => gap.code === 'MISSING_ARTIFACT_KIND_TEST'));

assert.throws(() => compileInstitutionalizationPackage({ ...spec, artifacts: [...spec.artifacts, { ...spec.artifacts[0] }] }, positive.root), /duplicate_artifact_id/);
assert.throws(() => compileInstitutionalizationPackage({ ...spec, source_snapshot: { ...spec.source_snapshot, head_sha: 'not-a-sha' } }, positive.root), /source_head_sha_invalid/);
assert.throws(() => compileInstitutionalizationPackage({ ...spec, hard_boundaries: { ...spec.hard_boundaries, money_movement: true } }, positive.root), /hard_boundary_must_be_false:money_movement/);
assert.throws(() => compileInstitutionalizationPackage({ ...spec, ai_governance: { ...spec.ai_governance, decision_authority: true } }, positive.root), /ai_governance_boundary_invalid/);

const secretRepo = makeRepo();
const secretArtifact = secretRepo.artifacts[0];
const syntheticSecret = ['sk', 'live', '1234567890abcdef'].join('_');
writeFileSync(join(secretRepo.root, secretArtifact.path), `forbidden shape ${syntheticSecret}\n`, 'utf8');
assert.throws(() => compileInstitutionalizationPackage(baseSpec(secretRepo.artifacts), secretRepo.root), /secret_shape_detected/);

const restrictedRepo = makeRepo();
const restrictedArtifacts = restrictedRepo.artifacts.map((artifact, index) => index === 0 ? { ...artifact, classification: 'restricted', public_projection: true } : artifact);
assert.throws(() => compileInstitutionalizationPackage(baseSpec(restrictedArtifacts), restrictedRepo.root), /restricted_artifact_public_projection_forbidden/);

const escapeRepo = makeRepo();
const escapeArtifacts = escapeRepo.artifacts.map((artifact, index) => index === 0 ? { ...artifact, path: '../escape.txt' } : artifact);
assert.throws(() => compileInstitutionalizationPackage(baseSpec(escapeArtifacts), escapeRepo.root), /artifact_path_escape/);

const symlinkRepo = makeRepo();
writeFileSync(join(symlinkRepo.root, 'target.txt'), 'target\n', 'utf8');
symlinkSync(join(symlinkRepo.root, 'target.txt'), join(symlinkRepo.root, 'artifacts', 'symlink.txt'));
const symlinkArtifacts = symlinkRepo.artifacts.map((artifact, index) => index === 0 ? { ...artifact, path: 'artifacts/symlink.txt' } : artifact);
assert.throws(() => compileInstitutionalizationPackage(baseSpec(symlinkArtifacts), symlinkRepo.root), /artifact_symlink_forbidden/);

const digestBefore = first.package_digest_sha256;
writeFileSync(join(positive.root, spec.artifacts[0].path), `${readFileSync(join(positive.root, spec.artifacts[0].path), 'utf8')}mutation\n`, 'utf8');
const mutated = compileInstitutionalizationPackage(spec, positive.root);
assert.notEqual(mutated.package_digest_sha256, digestBefore);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_INSTITUTIONALIZATION_COMPILER',
  deterministic_rebuild: true,
  artifact_count: first.artifact_counts.total,
  package_digest_sha256: first.package_digest_sha256,
  missing_test_holds: true,
  duplicate_id_rejected: true,
  invalid_head_rejected: true,
  live_boundary_rejected: true,
  ai_authority_rejected: true,
  secret_shape_rejected: true,
  restricted_public_projection_rejected: true,
  path_escape_rejected: true,
  symlink_rejected: true,
  content_drift_changes_digest: true,
  provider_write: false,
  money_movement: false,
  chain_broadcast: false,
}));
