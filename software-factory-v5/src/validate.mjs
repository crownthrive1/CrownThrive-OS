#!/usr/bin/env node
import { readFile, readdir } from 'node:fs/promises';
import { resolve, join } from 'node:path';
const root = process.cwd();
const rawRegistry = JSON.parse(await readFile(resolve(root,'registry/skills.registry.json'),'utf8'));
const hydrateRegistry = (raw) => {
  if (Array.isArray(raw.skills)) return raw;
  if (!Array.isArray(raw.skill_columns) || !Array.isArray(raw.skill_rows)) throw new Error('Invalid compact skill registry');
  return {
    ...raw,
    skills: raw.skill_rows.map((row, index) => {
      const mapped = Object.fromEntries(raw.skill_columns.map((key, column) => [key, row[column]]));
      const defaults = raw.defaults || {};
      return {
        ...defaults,
        ordinal: index + 1,
        ...mapped,
        outputs: [...(defaults.outputs || [])],
        commercialization: {
          ...(defaults.commercialization || {}),
          price_ladder_proposal: { ...(defaults.commercialization?.price_ladder_proposal || {}) }
        }
      };
    })
  };
};
const registry = hydrateRegistry(rawRegistry);
const bundles = JSON.parse(await readFile(resolve(root,'registry/bundles.registry.json'),'utf8'));
const config = JSON.parse(await readFile(resolve(root,'config/factory.config.json'),'utf8'));
const assert = (condition, message) => { if (!condition) throw new Error(message); };
assert(registry.skill_count === 59 && registry.skills.length === 59, 'Expected 59 registered skills');
assert(new Set(registry.skills.map(s=>s.skill_id)).size === 59, 'Duplicate skill IDs');
assert(new Set(registry.skills.map(s=>s.slug)).size === 59, 'Duplicate skill slugs');
assert(new Set(registry.skills.map(s=>s.family)).size === 7, 'Expected seven skill families');
assert(bundles.bundle_count === 9 && bundles.bundles.length === 9, 'Expected nine commercial bundles');
for (const s of registry.skills) {
  for (const key of ['skill_id','slug','name','version','family','description','primary_brand','corridor','maturity','authority_ceiling','commercialization']) assert(s[key] !== undefined, `Missing ${key} for ${s.skill_id}`);
}
const text = JSON.stringify({registry,bundles,config});
const forbidden = [/(?:sk-proj|sk-live|rk_live)_[A-Za-z0-9_-]{16,}/, /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, /api[_-]?token\s*[:=]\s*[A-Za-z0-9_-]{20,}/i];
assert(!forbidden.some(r=>r.test(text)), 'Potential secret value detected');
console.log(JSON.stringify({status:'PASS',skills:59,families:7,bundles:9,secret_scan:'PASS'},null,2));
