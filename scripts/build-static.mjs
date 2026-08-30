import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(process.cwd());
const out = resolve(root, 'dist');

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const copy = (source, destination = source) => {
  const from = resolve(root, source);
  const to = resolve(out, destination);
  if (!existsSync(from)) throw new Error(`Required static source missing: ${source}`);
  cpSync(from, to, { recursive: true });
};

copy('index.html');
copy('assets');
copy('favicon.svg');
copy('robots.txt');
copy('sitemap.xml');

const commit = process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA || 'local';
const branch = process.env.VERCEL_GIT_COMMIT_REF || process.env.GITHUB_REF_NAME || 'local';
const environment = process.env.VERCEL_ENV || 'local';
const repository = process.env.VERCEL_GIT_REPO_SLUG || 'CrownThrive-OS';
const builtAt = new Date().toISOString();

const proof = {
  schema: 'ct.vercel.projection-proof.v1',
  osReleaseFamily: '3.x',
  institutionalGeneration: 'Phase 3 — Execute',
  lifecycle: ['Discover', 'Govern', 'Execute', 'Verify', 'Preserve'],
  repository,
  branch,
  commit,
  environment,
  builtAt
};

writeFileSync(resolve(out, 'build.json'), `${JSON.stringify(proof, null, 2)}\n`);

const html = readFileSync(resolve(out, 'index.html'), 'utf8');
if (!html.includes('data-crownthrive-os="3.x"')) {
  throw new Error('CrownThrive OS shell marker missing; refusing projection build.');
}
if (!html.includes('/build.json')) {
  throw new Error('Deployment proof surface is not linked from the OS shell.');
}

console.log(`CrownThrive OS static projection built for ${branch}@${commit.slice(0, 12)} (${environment}).`);
