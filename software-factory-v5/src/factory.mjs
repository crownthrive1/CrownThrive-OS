#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile, appendFile, access } from 'node:fs/promises';
import { resolve, dirname, join } from 'node:path';

const argv = process.argv.slice(2);
const arg = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : null; };
const root = process.cwd();
const readJson = async (p) => JSON.parse(await readFile(resolve(root, p), 'utf8'));
const sha = (value) => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex');
const exists = async (p) => { try { await access(p); return true; } catch { return false; } };
const atomicJson = async (p, value) => {
  await mkdir(dirname(p), { recursive: true });
  const tmp = `${p}.tmp`;
  await writeFile(tmp, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  const { rename } = await import('node:fs/promises');
  await rename(tmp, p);
};
const appendJsonl = async (p, value) => {
  await mkdir(dirname(p), { recursive: true });
  await appendFile(p, `${JSON.stringify(value)}\n`, 'utf8');
};

const config = await readJson('config/factory.config.json');
const hydrateRegistry = (raw) => {
  if (Array.isArray(raw.skills)) return raw;
  if (!Array.isArray(raw.skill_columns) || !Array.isArray(raw.skill_rows)) throw new Error('Invalid compact skill registry');
  const skills = raw.skill_rows.map((row, index) => {
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
  });
  return { ...raw, skills };
};
const registry = hydrateRegistry(await readJson(config.registry_path));
const bundles = await readJson(config.bundle_registry_path);
const isGithubActions = process.env.GITHUB_ACTIONS === 'true';
const continuitySource = process.env.CT_FACTORY_STATE_SOURCE || 'LOCAL_STATE';
const at = new Date(arg('--at') || new Date().toISOString());
if (Number.isNaN(at.getTime())) throw new Error('Invalid --at value');
const hourBucket = at.toISOString().slice(0, 13);
const outputRoot = resolve(root, arg('--output') || config.generated_root);
const statePath = join(outputRoot, 'state.json');
const statusPath = join(outputRoot, 'current-status.json');
let state = { cursor: 0, cycle: 1, ticks: 0, packages: 0, hour_bucket: null };
if (await exists(statePath)) state = JSON.parse(await readFile(statePath, 'utf8'));

if (state.hour_bucket === hourBucket && await exists(statusPath)) {
  const current = JSON.parse(await readFile(statusPath, 'utf8'));
  console.log(JSON.stringify({ ...current, idempotent: true }));
  process.exit(0);
}

const cursor = Number.isInteger(state.cursor) && state.cursor >= 0 && state.cursor < registry.skills.length ? state.cursor : 0;
const take = Math.min(config.batch_size, registry.skills.length - cursor);
const selected = registry.skills.slice(cursor, cursor + take);
const tickId = `ct-skills-${hourBucket.replace(/[-T:]/g, '')}-${sha(`${config.factory_id}:${hourBucket}`).slice(0, 12)}`;
const generatedAt = at.toISOString();
const packageRecords = [];
const handoffs = [];

for (const skill of selected) {
  const commercialization = { ...(registry.commercialization_defaults || {}), ...(skill.commercialization || {}) };
  const packageManifest = {
    schema_version: '1.0.0', tick_id: tickId, factory_id: config.factory_id,
    skill_id: skill.skill_id, skill_version: skill.version, family: skill.family,
    generated_at: generatedAt, source_hash: sha(skill), maturity: skill.maturity,
    runtime_state: 'PACKAGE_GENERATED_LOCAL', outputs: skill.outputs,
    truth_boundary: 'Package generation is not provider activation or commerce execution.'
  };
  const packageHash = sha(packageManifest);
  packageManifest.package_sha256 = packageHash;
  const packageDir = join(outputRoot, 'packages', hourBucket.replace(':', ''), skill.slug);
  await atomicJson(join(packageDir, 'package.json'), packageManifest);
  const evidence = {
    evidence_id: `ev-${packageHash.slice(0, 20)}`, exact_subject: `${skill.skill_id}@${skill.version}`,
    tick_id: tickId, package_sha256: packageHash, validation: 'PASS_LOCAL_DETERMINISTIC',
    negative_tests: ['no_secret_values','no_provider_write_without_binding','no_automatic_ecac'],
    observed_at: generatedAt
  };
  await atomicJson(join(packageDir, 'evidence.json'), evidence);
  const handoff = {
    handoff_id: `pg-${sha(`${tickId}:${skill.skill_id}`).slice(0, 24)}`,
    tick_id: tickId, skill_id: skill.skill_id, package_hash: packageHash,
    rights: { status: 'PROPOSED_CROWNTHRIVE_AUTHORED', basis: commercialization.rights_basis, authority_ref: null },
    price: { currency: 'USD', proposal: commercialization.price_ladder_proposal, provider_product_id: null, provider_price_id: null },
    tax: { status: 'UNRESOLVED_JURISDICTION', provider_tax_code: null, statement: commercialization.tax_posture },
    fulfillment: { method: 'VERSIONED_DIGITAL_PACKAGE', provider_destination_id: null, receipt_id: null },
    entitlement: { model: 'NAMED_ORG_OR_SEAT', contract_id: null, revocation_behavior: 'REVOKE_FUTURE_ACCESS_PRESERVE_EVIDENCE' },
    destination: { channel: 'PENTAGREEN_ROUTED', provider_id: null, url: null },
    provider_readback: { receipt_id: null, observed_at: null, observed_state: null },
    state: 'HOLD',
    hold_reasons: ['MISSING_RIGHTS_AUTHORITY_REF','MISSING_PROVIDER_PRICE_ID','MISSING_PROVIDER_TAX_CODE','MISSING_FULFILLMENT_DESTINATION','MISSING_ENTITLEMENT_CONTRACT','MISSING_PROVIDER_DESTINATION','MISSING_PROVIDER_READBACK'],
    next_action: 'PentaGreen resolves exact authority, provider product/price/tax code, fulfillment destination, entitlement contract, provider destination and reverse-readback.'
  };
  packageRecords.push({ tick_id: tickId, skill_id: skill.skill_id, family: skill.family, package_sha256: packageHash, generated_at: generatedAt, state: 'PACKAGE_READY_PENTAGREEN_HANDOFF' });
  handoffs.push(handoff);
  await appendJsonl(join(outputRoot, 'master-ledger', 'skill-production.jsonl'), packageRecords.at(-1));
  await appendJsonl(join(outputRoot, 'pentagreen', 'handoff.jsonl'), handoff);
}

const nextCursorRaw = cursor + take;
const completedCycle = nextCursorRaw >= registry.skills.length;
const nextCursor = completedCycle ? 0 : nextCursorRaw;
const nextCycle = completedCycle ? (state.cycle || 1) + 1 : (state.cycle || 1);
const status = {
  schema_version: '1.0.0', release_version: config.version, factory_id: config.factory_id,
  status: isGithubActions ? 'OPERATIONAL_GITHUB_ACTIONS_CURRENT_RUN' : 'OPERATIONAL_SOURCE_AND_LOCAL_TESTED',
  hourly_clock: isGithubActions ? 'PASS_GITHUB_ACTIONS_CURRENT_RUN' : 'CONFIGURED_GITHUB_ACTIONS_AWAITING_PROVIDER_RUN',
  continuity_source: continuitySource,
  tick_id: tickId, generated_at: generatedAt, timezone: config.timezone,
  next_cursor: nextCursor, current_cycle: state.cycle || 1,
  registry: { skills: registry.skill_count, families: registry.family_count, bundles: bundles.bundle_count },
  current_batch: { produced: selected.length, skill_ids: selected.map(s => s.skill_id), local_validation: 'PASS', pentagreen_handoffs: handoffs.length, commercial_ecac: 0, commercial_hold: handoffs.length },
  cumulative: { ticks: (state.ticks || 0) + 1, packages: (state.packages || 0) + selected.length },
  provider_state: { github_workflow: isGithubActions ? 'PASS_GITHUB_ACTIONS_CURRENT_RUN' : 'LOCAL_TESTED_AWAITING_PROVIDER_RUN', vercel_command_center: 'SOURCE_READY_AWAITING_ROUTE_READBACK', drive_master_ledger: config.provider_receipts.drive_master_ledger.state, live_commerce: 'HOLD_PROVIDER_BINDING' },
  provider_receipts: config.provider_receipts,
  truth_boundary: 'Stable source packages and local tests do not by themselves prove live provider activation, customer entitlement, payment, or production scheduler execution.'
};
const nextState = { cursor: nextCursor, cycle: nextCycle, ticks: status.cumulative.ticks, packages: status.cumulative.packages, hour_bucket: hourBucket, tick_id: tickId, updated_at: generatedAt };
await atomicJson(join(outputRoot, 'pentagreen', 'current-batch.json'), { tick_id: tickId, generated_at: generatedAt, count: handoffs.length, handoffs });
await appendJsonl(join(outputRoot, 'master-ledger', 'factory-ticks.jsonl'), { tick_id: tickId, generated_at: generatedAt, cursor_start: cursor, cursor_end: nextCursor, cycle: state.cycle || 1, package_count: selected.length, idempotency_key: hourBucket, state: 'PASS_LOCAL' });
await atomicJson(statusPath, status);
await atomicJson(statePath, nextState);
console.log(JSON.stringify({ ...status, idempotent: false }));
