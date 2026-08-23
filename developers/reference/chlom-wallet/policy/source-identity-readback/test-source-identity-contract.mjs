import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, parse, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const contract = JSON.parse(readFileSync(join(HERE, 'runtime-contract.v1.json'), 'utf8'));

function discoverRepoRoot(start) {
  let candidate = resolve(start);
  const filesystemRoot = parse(candidate).root;
  while (candidate !== filesystemRoot) {
    if (
      existsSync(join(candidate, '.git'))
      && existsSync(join(candidate, 'docs.json'))
      && existsSync(join(candidate, 'developers'))
    ) {
      return candidate;
    }
    candidate = dirname(candidate);
  }
  throw new Error(`Unable to discover repository root from ${start}`);
}

const repoRoot = discoverRepoRoot(HERE);
const sourcePath = resolve(repoRoot, contract.fixed_source.path);
assert.equal(sourcePath.startsWith(`${repoRoot}/`), true);
const sourceBytes = readFileSync(sourcePath);
const gitHeader = Buffer.from(`blob ${sourceBytes.length}\0`, 'utf8');
const gitBlobSha1 = createHash('sha1').update(gitHeader).update(sourceBytes).digest('hex');
const sourceSha256 = createHash('sha256').update(sourceBytes).digest('hex');

assert.equal(contract.contract_id, 'ct.runtime.chlom-wallet-source-identity-readback.v1');
assert.equal(contract.semantic_version, '1.0.0');
assert.equal(contract.state, 'CONTROLLED_TEST_ACTIVE');
assert.equal(contract.phase, '2.99');
assert.equal(contract.edge_function.slug, 'chlom-wallet-source-identity-readback');
assert.equal(contract.edge_function.version, 2);
assert.equal(contract.edge_function.verify_jwt, false);
assert.deepEqual(contract.edge_function.method_allowlist, ['GET']);
assert.equal(contract.edge_function.arbitrary_url_input, false);
assert.equal(contract.edge_function.fixed_source_only, true);
assert.equal(contract.fixed_source.commit_sha, '0261e0b4d3bfa5f041b59efd9bf78bc6e1f76591');
assert.equal(contract.fixed_source.path, 'developers/reference/chlom-wallet/policy/chlom-wallet-policy-assurance.mjs');
assert.equal(sourceBytes.length, contract.fixed_source.expected_size_bytes);
assert.equal(gitBlobSha1, contract.fixed_source.expected_git_blob_sha1);
assert.match(sourceSha256, /^[0-9a-f]{64}$/);
assert.equal(sourceSha256, '1fc7892cbfbbaa8a737c63e12f52ddaeac829089b0a9f283d8209ceb674f7867');
assert.equal(contract.fixed_source.content_sha256_state, 'DYNAMIC_FIXED_SOURCE_OBSERVATION');
assert.equal(contract.persistence.append_only, true);
assert.equal(contract.persistence.rls_deny_all, true);
assert.equal(contract.persistence.idempotent_replay, true);
assert.ok(Object.values(contract.hard_boundaries).every((value) => value === false));

const indexSource = readFileSync(join(HERE, 'index.ts'), 'utf8');
assert.match(indexSource, /const RAW_URL = `https:\/\/raw\.githubusercontent\.com\/\$\{SOURCE\.repository\}\/\$\{SOURCE\.commit_sha\}\/\$\{SOURCE\.path\}`/);
assert.match(indexSource, /expected_git_blob_sha1/);
assert.match(indexSource, /expected_size_bytes/);
assert.match(indexSource, /chlom_wallet_record_policy_source_identity_observation_v1/);
assert.doesNotMatch(indexSource, /request\.url.*searchParams|new URL\(request\.url\).*searchParams/);
assert.doesNotMatch(indexSource, /eth_send|wallet_sendCalls|private[_ -]?key|mnemonic|seed phrase/i);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_FIXED_SOURCE_IDENTITY_CONTRACT',
  repository_root_discovered: true,
  source_size_bytes: sourceBytes.length,
  git_blob_sha1: gitBlobSha1,
  source_sha256: sourceSha256,
  fixed_source_only: true,
  arbitrary_url_input: false,
  append_only_observation: true,
  credential_value_exposed: false,
  provider_write: false,
  money_movement: false,
  chain_broadcast: false,
  phase_advancement: false,
  merge_authorized: false,
}));
