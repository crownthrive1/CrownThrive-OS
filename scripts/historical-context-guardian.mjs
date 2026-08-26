#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const CHECK_EXTENSIONS = new Set(['.md', '.mdx']);
const SKIP_DIRS = new Set(['.git', 'node_modules', '.next', 'dist', 'build']);

const REQUIRED_FILES = [
  'knowledge/historical-context-boundary.mdx',
  'knowledge/historical-source-pack-2026-08-26.mdx',
  'knowledge/source-authority-hierarchy.mdx',
  'start-here/operating-principles.mdx',
  'data/documentation/historical-context-policy.v1.json',
  'data/documentation/historical-source-pack-2026-08-26.v1.json',
  'developers/manifests/historical-context-guardian.v1.json'
];

const HISTORICAL_PATH_PATTERNS = [
  /(^|\/)historical[-_/]/i,
  /(^|\/)archive[-_/]/i,
  /(^|\/)legacy[-_/]/i,
  /superseded/i
];

const HISTORICAL_BODY_PATTERNS = [
  /record_type:\s*["']?historical/i,
  /context_mode:\s*["']?historical_only/i,
  /current_authority:\s*["']?none/i,
  /implementation_authority:\s*["']?none/i,
  /\bsource[-_ ]era\b/i,
  /\bhistorical (?:record|source|architecture|build|research|design|guide)\b/i
];

const DANGEROUS_BOOLEAN_KEYS = [
  'production_proof',
  'current_state_proof',
  'implementation_allowed',
  'execution_allowed'
];

const AUTHORITY_KEYS = [
  'implementation_authority',
  'execution_authority',
  'current_authority'
];

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, files);
      continue;
    }
    if (CHECK_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) files.push(full);
  }
  return files;
}

function rel(file) {
  return path.relative(ROOT, file).split(path.sep).join('/');
}

function isHistorical(filePath, body) {
  return HISTORICAL_PATH_PATTERNS.some((pattern) => pattern.test(filePath)) ||
    HISTORICAL_BODY_PATTERNS.some((pattern) => pattern.test(body));
}

function findKeyValue(body, key) {
  const pattern = new RegExp(`^\\s*${key}\\s*:\\s*([^#\\n\\r]+)`, 'im');
  const match = body.match(pattern);
  return match ? match[1].trim().replace(/^['"]|['"]$/g, '').toLowerCase() : null;
}

function evaluateHistoricalFile(filePath, body) {
  const violations = [];

  for (const key of DANGEROUS_BOOLEAN_KEYS) {
    const value = findKeyValue(body, key);
    if (value === 'true' || value === 'yes' || value === 'allowed') {
      violations.push(`${filePath}: historical source declares ${key}=${value}`);
    }
  }

  for (const key of AUTHORITY_KEYS) {
    const value = findKeyValue(body, key);
    if (value && !['none', 'false', 'context_only', 'historical_only', 'architecture_history_and_design_input'].includes(value)) {
      violations.push(`${filePath}: historical source declares ${key}=${value}; authority must be none/context-only`);
    }
  }

  return violations;
}

function checkRequiredFiles() {
  return REQUIRED_FILES
    .filter((file) => !fs.existsSync(path.join(ROOT, file)))
    .map((file) => `required file missing: ${file}`);
}

function checkSourceManifest() {
  const manifestPath = path.join(ROOT, 'data/documentation/historical-source-pack-2026-08-26.v1.json');
  if (!fs.existsSync(manifestPath)) return { violations: [], count: 0 };

  const violations = [];
  let data;
  try {
    data = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (error) {
    return { violations: [`historical source manifest is invalid JSON: ${error.message}`], count: 0 };
  }

  const sources = Array.isArray(data.sources) ? data.sources : [];
  if (sources.length !== 24) violations.push(`historical source manifest must contain 24 records; found ${sources.length}`);

  for (const source of sources) {
    if (source.implementation_authority !== 'none') {
      violations.push(`${source.source_id || 'unknown-source'}: implementation_authority must be none`);
    }
    if (source.execution_authority !== 'none') {
      violations.push(`${source.source_id || 'unknown-source'}: execution_authority must be none`);
    }
    if (source.public_body === true && ['RESTRICTED_HISTORICAL', 'PRIVATE_CONTEXT'].includes(source.disposition)) {
      violations.push(`${source.source_id || 'unknown-source'}: restricted/private source cannot publish its body`);
    }
  }

  return { violations, count: sources.length };
}

const files = walk(ROOT);
const historicalFiles = [];
const violations = [...checkRequiredFiles()];

for (const file of files) {
  const filePath = rel(file);
  const body = fs.readFileSync(file, 'utf8');
  if (!isHistorical(filePath, body)) continue;
  historicalFiles.push(filePath);
  violations.push(...evaluateHistoricalFile(filePath, body));
}

const sourceManifest = checkSourceManifest();
violations.push(...sourceManifest.violations);

const result = {
  schema_version: '1.0.0',
  guardian_id: 'ct.agent.historical-context-guardian',
  checked_at: new Date().toISOString(),
  mode: 'context_only_non_executable',
  scanned_document_count: files.length,
  historical_document_count: historicalFiles.length,
  registered_source_count: sourceManifest.count,
  violation_count: violations.length,
  complete: violations.length === 0 && sourceManifest.count === 24,
  historical_documents: historicalFiles.sort(),
  violations
};

console.log(JSON.stringify(result, null, 2));
process.exit(result.complete ? 0 : 2);
