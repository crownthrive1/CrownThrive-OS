import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import solc from 'solc';

const ROOT = dirname(fileURLToPath(import.meta.url));
const FILES = [
  'ChlomAnchorRegistry.sol',
  'ChlomEntitlementRegistry.sol',
  'ChlomSplitPolicyRegistry.sol',
  'ThriveFundObligationRegistry.sol',
];
const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const canonical = (value) => JSON.stringify(value);

const sources = {};
for (const file of FILES) {
  const content = readFileSync(join(ROOT, file), 'utf8');
  sources[file] = { content };
}

const input = {
  language: 'Solidity',
  sources,
  settings: {
    optimizer: { enabled: true, runs: 200 },
    metadata: { bytecodeHash: 'none', appendCBOR: true },
    outputSelection: {
      '*': {
        '*': [
          'abi',
          'evm.bytecode.object',
          'evm.deployedBytecode.object',
          'metadata',
        ],
      },
    },
  },
};
const output = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (output.errors ?? []).filter((entry) => entry.severity === 'error');
if (errors.length) throw new Error(errors.map((entry) => entry.formattedMessage).join('\n'));

const contracts = [];
for (const file of FILES) {
  const names = Object.keys(output.contracts?.[file] ?? {}).sort();
  if (names.length !== 1) throw new Error(`expected_one_contract:${file}`);
  const name = names[0];
  const artifact = output.contracts[file][name];
  const source = sources[file].content;
  const creationBytecode = artifact.evm.bytecode.object;
  const runtimeBytecode = artifact.evm.deployedBytecode.object;
  if (!creationBytecode || !runtimeBytecode) throw new Error(`empty_bytecode:${name}`);
  contracts.push({
    name,
    source_file: file,
    source_sha256: sha256(source),
    abi_sha256: sha256(canonical(artifact.abi)),
    creation_bytecode_sha256: sha256(Buffer.from(creationBytecode, 'hex')),
    runtime_bytecode_sha256: sha256(Buffer.from(runtimeBytecode, 'hex')),
    creation_bytecode_bytes: creationBytecode.length / 2,
    runtime_bytecode_bytes: runtimeBytecode.length / 2,
    compiler_metadata_sha256: sha256(artifact.metadata),
    value_movement_surface: false,
  });
}
contracts.sort((a, b) => a.name.localeCompare(b.name));

const manifest = {
  schema_version: '1.0.0',
  manifest_id: 'ct.wallet.contract-artifacts.controlled-test.v1',
  state: 'CONTROLLED_TEST_BUILD_EVIDENCE',
  compiler: {
    package: 'solc',
    version: solc.version(),
    optimizer_enabled: true,
    optimizer_runs: 200,
    metadata_bytecode_hash: 'none',
  },
  contracts,
  no_external_rpc: true,
  no_signer: true,
  no_deployment: true,
  no_money_movement: true,
};
const bodyWithoutDigest = `${JSON.stringify(manifest, null, 2)}\n`;
manifest.manifest_sha256 = sha256(bodyWithoutDigest);
const finalBody = `${JSON.stringify(manifest, null, 2)}\n`;
const out = resolve(process.argv[2] ?? '/tmp/chlom-wallet-contract-artifacts.json');
writeFileSync(out, finalBody);
console.log(JSON.stringify({
  result: 'PASS_ARTIFACT_MANIFEST_BUILD',
  output: out,
  compiler: manifest.compiler.version,
  contract_count: contracts.length,
  manifest_sha256: manifest.manifest_sha256,
  creation_bytecode_bytes: contracts.reduce((sum, item) => sum + item.creation_bytecode_bytes, 0),
  runtime_bytecode_bytes: contracts.reduce((sum, item) => sum + item.runtime_bytecode_bytes, 0),
}));
