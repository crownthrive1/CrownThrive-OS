import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const read = (path) => readFile(new URL(path, root), 'utf8');

test('every loader route receives the external v3.1 executive extension', async () => {
  const source = await read('command-loader.js');
  assert.match(source, /VERSION = '3\.1\.0'/);
  assert.match(source, /ct\.command\.executive-pulse\.v3\.1\.0\.20260910/);
  assert.match(source, /command-enhancements\.css/);
  assert.match(source, /command-enhancements\.js/);
  assert.match(source, /credentials: 'same-origin'/);
  assert.match(source, /command_shell_contract_invalid/);
  assert.doesNotMatch(source, /<style>/i);
  assert.doesNotMatch(source, /<script>(?![^<]*src=)/i);
});

test('executive pulse reads all four public-safe production projections', async () => {
  const source = await read('command-enhancements.js');
  assert.match(source, /\/api\/command\?limit=12/);
  assert.match(source, /\/api\/catalog/);
  assert.match(source, /\/api\/operations/);
  assert.match(source, /\/api\/health/);
  assert.match(source, /Promise\.allSettled/);
  assert.match(source, /REFRESH_MS = 30_000/);
});

test('extension exposes current wallet, DAIL, operations, and catalog predicates', async () => {
  const source = await read('command-enhancements.js');
  for (const predicate of [
    'gate_receipts',
    'service_bindings',
    'verified_internal_accounts',
    'latest_canary',
    'sequence_span_lag',
    'verified_through_sequence_id',
    'current_head_sequence_id',
    'v4_segment_count',
    'penta_super_runs',
    'active_product_count',
    'active_checkout_count',
    'physical_products_excluded',
    'duplicate_active_links_collapsed',
    'chlom_chain_evidence',
    'max_unattended_value_minor'
  ]) assert.match(source, new RegExp(predicate));
  assert.doesNotMatch(source, /Open 59 Digital Products|59 PRODUCTS/);
});

test('command extension stays read-only and does not manufacture a pass', async () => {
  const source = await read('command-enhancements.js');
  assert.doesNotMatch(source, /method:\s*['"]POST['"]/);
  assert.doesNotMatch(source, /authorization\s*:/i);
  assert.doesNotMatch(source, /wallet_address|account_balance|private_key|secret_key/i);
  assert.match(source, /Partial remains partial/);
  assert.match(source, /No chain-broadcast success is claimed/);
  assert.match(source, /Economic mutations.*remain outside this interface/);
});

test('release contract preserves external-rail and privacy boundaries', async () => {
  const release = JSON.parse(await read('command-release-v31.json'));
  assert.equal(release.version, '3.1.0');
  assert.equal(release.control_contract.read_only_projection, true);
  assert.equal(release.control_contract.economic_mutations_exposed, false);
  assert.equal(release.control_contract.external_money_movement_exposed, false);
  assert.equal(release.control_contract.credential_material_exposed, false);
  assert.equal(release.control_contract.wallet_identifiers_exposed, false);
  assert.equal(release.control_contract.balances_exposed, false);
  assert.equal(release.control_contract.pass_manufactured, false);
  assert.equal(release.preserved_boundaries.card_issuing, 'provider_contract_required');
  assert.equal(release.preserved_boundaries.stablecoin_checkout, 'HOLD');
  assert.equal(release.preserved_boundaries.agent_unattended_external_value_minor, 0);
});

test('extension styles remain isolated and responsive', async () => {
  const css = await read('command-enhancements.css');
  assert.match(css, /\.ct-pulse-grid/);
  assert.match(css, /\.ct-assurance-panel/);
  assert.match(css, /\.ct-market-grid/);
  assert.match(css, /@media\(max-width:620px\)/);
  assert.match(css, /prefers-reduced-motion/);
  assert.doesNotMatch(css, /url\(https?:/i);
});
