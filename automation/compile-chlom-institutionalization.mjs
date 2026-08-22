#!/usr/bin/env node
import {
  lstatSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  writeFileSync,
} from 'node:fs';
import { dirname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonicalize, secretShapePresent, sha256Hex } from '../developers/reference/chlom-wallet/common/canonical-json.mjs';
import { resolveInstitutionalizationGaps } from './chlom-institutionalization-gap-resolver.mjs';

const IDENTIFIER = /^[A-Za-z0-9._:@/-]{3,220}$/;
const HEX40 = /^[0-9a-f]{40}$/;
const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const CLASSIFICATIONS = new Set(['public', 'internal', 'restricted']);
const ARTIFACT_STATUSES = new Set(['CONTROLLED_TEST', 'HOLD', 'REFERENCE', 'CANDIDATE', 'VERIFIED_TEST']);
const FORBIDDEN_PUBLIC_KEY = /"(?:private_fingerprint(?:_sha256)?|private_key|seed_phrase|mnemonic|credential_value|secret_manager_ref|provider_credential)"\s*:\s*"(?!REDACTED|PROHIBITED)/i;

function fail(code) {
  throw new Error(code);
}

function assertIdentifier(value, code) {
  if (typeof value !== 'string' || !IDENTIFIER.test(value)) fail(code);
  return value;
}

function assertPlainObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) fail(code);
  return value;
}

function sortDeep(value) {
  if (Array.isArray(value)) return value.map(sortDeep);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortDeep(value[key])]));
  }
  return value;
}

function stableJson(value) {
  return `${JSON.stringify(sortDeep(value), null, 2)}\n`;
}

function safeArtifactPath(repoRoot, artifactPath) {
  if (typeof artifactPath !== 'string' || artifactPath.length < 1 || artifactPath.length > 500) fail('artifact_path_invalid');
  if (isAbsolute(artifactPath) || artifactPath.includes('\\') || artifactPath.split('/').includes('..')) fail('artifact_path_escape');
  const rootReal = realpathSync(repoRoot);
  const candidate = resolve(rootReal, artifactPath);
  const stats = lstatSync(candidate);
  if (stats.isSymbolicLink()) fail('artifact_symlink_forbidden');
  if (!stats.isFile()) fail('artifact_regular_file_required');
  const candidateReal = realpathSync(candidate);
  const rel = relative(rootReal, candidateReal);
  if (rel.startsWith('..') || isAbsolute(rel)) fail('artifact_path_escape');
  return { absolutePath: candidateReal, stats };
}

function validateSpec(spec) {
  assertPlainObject(spec, 'institutionalization_spec_object_required');
  assertIdentifier(spec.package_id, 'package_id_invalid');
  if (typeof spec.semantic_version !== 'string' || !SEMVER.test(spec.semantic_version)) fail('semantic_version_invalid');
  if (spec.state !== 'CONTROLLED_TEST') fail('spec_state_must_be_controlled_test');
  assertPlainObject(spec.source_snapshot, 'source_snapshot_required');
  assertIdentifier(spec.source_snapshot.repository, 'source_repository_invalid');
  assertIdentifier(spec.source_snapshot.branch, 'source_branch_invalid');
  if (typeof spec.source_snapshot.head_sha !== 'string' || !HEX40.test(spec.source_snapshot.head_sha)) fail('source_head_sha_invalid');
  if (typeof spec.source_snapshot.observed_on !== 'string' || !DATE.test(spec.source_snapshot.observed_on)) fail('source_observed_on_invalid');
  if (!Array.isArray(spec.artifacts) || spec.artifacts.length < 1) fail('artifacts_required');
  if (!Array.isArray(spec.algorithms) || spec.algorithms.length < 1) fail('algorithms_required');
  if (!spec.output_contract || typeof spec.output_contract.path !== 'string') fail('output_contract_required');
  assertPlainObject(spec.hard_boundaries, 'hard_boundaries_required');
  for (const [key, value] of Object.entries(spec.hard_boundaries)) {
    if (value !== false) fail(`hard_boundary_must_be_false:${key}`);
  }
  assertPlainObject(spec.ai_governance, 'ai_governance_required');
  if (spec.ai_governance.advisory_only !== true || spec.ai_governance.decision_authority !== false || spec.ai_governance.write_authority !== false) {
    fail('ai_governance_boundary_invalid');
  }
}

function compileArtifacts(spec, repoRoot) {
  const ids = new Set();
  const paths = new Set();
  return spec.artifacts.map((artifact) => {
    assertPlainObject(artifact, 'artifact_object_required');
    assertIdentifier(artifact.artifact_id, 'artifact_id_invalid');
    if (ids.has(artifact.artifact_id)) fail('duplicate_artifact_id');
    ids.add(artifact.artifact_id);
    if (paths.has(artifact.path)) fail('duplicate_artifact_path');
    paths.add(artifact.path);
    assertIdentifier(artifact.owner_agent_id, 'artifact_owner_agent_id_invalid');
    if (!CLASSIFICATIONS.has(artifact.classification)) fail('artifact_classification_invalid');
    if (!ARTIFACT_STATUSES.has(artifact.status)) fail('artifact_status_invalid');
    if (typeof artifact.kind !== 'string' || artifact.kind.length < 2 || artifact.kind.length > 80) fail('artifact_kind_invalid');
    if (typeof artifact.public_projection !== 'boolean') fail('artifact_public_projection_boolean_required');
    if (artifact.public_projection && artifact.classification !== 'public') fail('restricted_artifact_public_projection_forbidden');

    const { absolutePath, stats } = safeArtifactPath(repoRoot, artifact.path);
    const bytes = readFileSync(absolutePath);
    const text = bytes.toString('utf8');
    const secretDetected = secretShapePresent(text);
    if (secretDetected) fail(`secret_shape_detected:${artifact.artifact_id}`);
    if (artifact.public_projection && FORBIDDEN_PUBLIC_KEY.test(text)) fail(`forbidden_public_identity_field:${artifact.artifact_id}`);

    return {
      artifact_id: artifact.artifact_id,
      path: artifact.path,
      kind: artifact.kind,
      classification: artifact.classification,
      owner_agent_id: artifact.owner_agent_id,
      status: artifact.status,
      public_projection: artifact.public_projection,
      sha256: sha256Hex(bytes),
      size_bytes: stats.size,
      secret_shape_detected: false,
      source_ref: `github:${spec.source_snapshot.repository}:${spec.source_snapshot.branch}:${artifact.path}`,
    };
  }).sort((a, b) => a.artifact_id.localeCompare(b.artifact_id));
}

function compileAlgorithms(spec, artifactInventory) {
  const artifactPaths = new Set(artifactInventory.map((artifact) => artifact.path));
  const ids = new Set();
  return spec.algorithms.map((algorithm) => {
    assertPlainObject(algorithm, 'algorithm_object_required');
    assertIdentifier(algorithm.algorithm_id, 'algorithm_id_invalid');
    if (ids.has(algorithm.algorithm_id)) fail('duplicate_algorithm_id');
    ids.add(algorithm.algorithm_id);
    if (typeof algorithm.semantic_version !== 'string' || !SEMVER.test(algorithm.semantic_version)) fail('algorithm_semantic_version_invalid');
    if (!Array.isArray(algorithm.source_paths) || algorithm.source_paths.length < 1) fail('algorithm_source_paths_required');
    for (const sourcePath of algorithm.source_paths) {
      if (!artifactPaths.has(sourcePath)) fail(`algorithm_source_not_in_inventory:${algorithm.algorithm_id}`);
    }
    if (!Array.isArray(algorithm.invariants) || algorithm.invariants.length < 1) fail('algorithm_invariants_required');
    return sortDeep({
      ...algorithm,
      authority_effect: 'none',
      provider_write: false,
      money_movement: false,
      rights_grant: false,
      chain_broadcast: false,
    });
  }).sort((a, b) => a.algorithm_id.localeCompare(b.algorithm_id));
}

export function compileInstitutionalizationPackage(spec, repoRoot) {
  validateSpec(spec);
  const artifactInventory = compileArtifacts(spec, repoRoot);
  const algorithmRegistry = compileAlgorithms(spec, artifactInventory);
  const gapAnalysis = resolveInstitutionalizationGaps(spec, artifactInventory);
  const packageWithoutDigest = {
    schema_version: '1.0.0',
    package_id: spec.package_id,
    semantic_version: spec.semantic_version,
    state: gapAnalysis.disposition,
    source_snapshot: sortDeep(spec.source_snapshot),
    compiler: {
      tool_id: 'ct.tool.chlom-institutionalization-compiler',
      algorithm_id: 'ct.algorithm.chlom.institutionalization-compiler.v1',
      semantic_version: '1.0.0',
      deterministic: true,
      canonicalization: 'RFC8785-inspired-sorted-JSON-with-finite-number-gate',
      hash: 'SHA-256',
      network_access: false,
      signing: false,
      provider_write: false,
      chain_broadcast: false,
      money_movement: false,
    },
    artifact_inventory: artifactInventory,
    artifact_counts: {
      total: artifactInventory.length,
      public: artifactInventory.filter((artifact) => artifact.classification === 'public').length,
      internal: artifactInventory.filter((artifact) => artifact.classification === 'internal').length,
      restricted: artifactInventory.filter((artifact) => artifact.classification === 'restricted').length,
      public_projection: artifactInventory.filter((artifact) => artifact.public_projection).length,
    },
    algorithm_registry: algorithmRegistry,
    docs_impact: sortDeep(spec.docs_impact),
    security: sortDeep(spec.security),
    privacy: sortDeep(spec.privacy),
    rights: sortDeep(spec.rights),
    commercialization: sortDeep(spec.commercialization),
    rollback: sortDeep(spec.rollback),
    scheduler: sortDeep(spec.scheduler),
    provenance: sortDeep(spec.provenance),
    third_party_dependencies: sortDeep(spec.third_party_dependencies),
    ai_governance: sortDeep(spec.ai_governance),
    gap_analysis: gapAnalysis,
    output_contract: sortDeep(spec.output_contract),
    hard_boundaries: sortDeep(spec.hard_boundaries),
  };
  const packageDigest = sha256Hex(canonicalize(packageWithoutDigest));
  return sortDeep({ ...packageWithoutDigest, package_digest_sha256: packageDigest });
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith('--')) fail('cli_argument_invalid');
    const value = argv[i + 1];
    if (!value || value.startsWith('--')) fail(`cli_argument_value_missing:${key}`);
    args[key.slice(2)] = value;
    i += 1;
  }
  for (const required of ['spec', 'repo-root', 'output']) {
    if (!args[required]) fail(`cli_${required}_required`);
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const spec = JSON.parse(readFileSync(resolve(args.spec), 'utf8'));
  const output = compileInstitutionalizationPackage(spec, resolve(args['repo-root']));
  const outputPath = resolve(args.output);
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, stableJson(output), 'utf8');
  process.stdout.write(JSON.stringify({
    result: output.state,
    package_id: output.package_id,
    package_digest_sha256: output.package_digest_sha256,
    artifact_count: output.artifact_counts.total,
    algorithm_count: output.algorithm_registry.length,
    completeness_score: output.gap_analysis.completeness_score,
    gap_count: output.gap_analysis.gap_count,
    output: outputPath,
    network_access: false,
    signing: false,
    provider_write: false,
    money_movement: false,
    chain_broadcast: false,
  }) + '\n');
}

const isCli = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isCli) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}

export { stableJson };
