import { spawnSync } from 'node:child_process';
import { readdir } from 'node:fs/promises';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const IGNORED_DIRECTORIES = new Set(['.vercel', 'node_modules']);
const args = new Set(process.argv.slice(2));
const allowedArgs = new Set(['--syntax-only', '--tests-only']);

for (const arg of args) {
  if (!allowedArgs.has(arg)) {
    throw new Error(`unsupported validation option: ${arg}`);
  }
}
if (args.has('--syntax-only') && args.has('--tests-only')) {
  throw new Error('--syntax-only and --tests-only are mutually exclusive');
}

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    if (entry.isDirectory() && IGNORED_DIRECTORIES.has(entry.name)) continue;
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) files.push(...await sourceFiles(path));
    else if (entry.isFile() && /\.(?:js|mjs)$/.test(entry.name)) files.push(path);
  }
  return files;
}

function runNode(arguments_) {
  const result = spawnSync(process.execPath, arguments_, {
    cwd: APP_ROOT,
    encoding: 'utf8',
    stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

const files = await sourceFiles(APP_ROOT);
const syntaxFiles = files;
const testRoot = resolve(APP_ROOT, 'tests');
const testFiles = files.filter((path) => {
  const testRelative = relative(testRoot, path);
  return testRelative && !testRelative.startsWith('..') && path.endsWith('.test.mjs');
});

if (!syntaxFiles.length) throw new Error('no JavaScript source files discovered');
if (!testFiles.length) throw new Error('no Node test files discovered');

if (!args.has('--tests-only')) {
  for (const path of syntaxFiles) runNode(['--check', relative(APP_ROOT, path)]);
  console.log(`CONTROL_PLANE_SYNTAX files=${syntaxFiles.length} status=PASS`);
}

if (!args.has('--syntax-only')) {
  runNode(['--test', ...testFiles.map((path) => relative(APP_ROOT, path))]);
  console.log(`CONTROL_PLANE_TESTS files=${testFiles.length} status=PASS`);
}
