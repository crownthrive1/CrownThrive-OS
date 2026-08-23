import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';

const root = process.cwd();
const manifestPath = path.join(root, 'developers/manifests/chlom-wallet-continuity-runtime-api-mcp-v1.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

if (!Array.isArray(manifest.artifacts) || manifest.artifacts.length === 0) throw new Error('runtime_manifest_has_no_artifacts');

const entries = [];
for (const relative of [...manifest.artifacts].sort()) {
  const absolute = path.resolve(root, relative);
  if (!absolute.startsWith(root + path.sep)) throw new Error(`runtime_manifest_path_escape:${relative}`);
  if (!fs.existsSync(absolute)) throw new Error(`runtime_manifest_artifact_missing:${relative}`);
  const stat = fs.statSync(absolute);
  if (!stat.isFile()) throw new Error(`runtime_manifest_artifact_not_file:${relative}`);
  entries.push({ path: relative, sha256: sha256(fs.readFileSync(absolute)), bytes: stat.size });
}

const manifestRoot = sha256(entries.map(e => `${e.path}|${e.sha256}|${e.bytes}`).join('\n'));
console.log(JSON.stringify({
  result:'PASS_CHLOM_WALLET_CONTINUITY_RUNTIME_SOURCE_MANIFEST_V1',
  artifact_count:entries.length,
  manifest_root_sha256:manifestRoot,
  mcp_protocol_version:manifest.mcp_protocol_version,
  authorization_mode:manifest.authorization_mode,
  production_activation:false,
  authority_granted:false,
  artifacts:entries
},null,2));
