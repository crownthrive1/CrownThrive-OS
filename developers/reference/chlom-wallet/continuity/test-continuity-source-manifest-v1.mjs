import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';

const root = process.cwd();
const manifestPath = path.join(root, 'developers/manifests/chlom-wallet-continuity-factory-v1.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

if (!Array.isArray(manifest.artifacts) || manifest.artifacts.length === 0) {
  throw new Error('continuity_manifest_has_no_artifacts');
}

const entries = [];
for (const relative of [...manifest.artifacts].sort()) {
  const absolute = path.resolve(root, relative);
  if (!absolute.startsWith(root + path.sep)) throw new Error(`manifest_path_escape:${relative}`);
  if (!fs.existsSync(absolute)) throw new Error(`manifest_artifact_missing:${relative}`);
  const stat = fs.statSync(absolute);
  if (!stat.isFile()) throw new Error(`manifest_artifact_not_file:${relative}`);
  entries.push({ path: relative, sha256: sha256(fs.readFileSync(absolute)), bytes: stat.size });
}

const manifestRoot = sha256(entries.map(e => `${e.path}|${e.sha256}|${e.bytes}`).join('\n'));
if (!/^[a-f0-9]{64}$/.test(manifestRoot)) throw new Error('invalid_manifest_root');

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_CONTINUITY_SOURCE_MANIFEST_V1',
  artifact_count: entries.length,
  manifest_root_sha256: manifestRoot,
  source_head_binding: manifest.source_head_binding,
  production_activation: false,
  authority_granted: false,
  artifacts: entries
}, null, 2));
