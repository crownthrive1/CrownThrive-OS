import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const read = (path) => readFile(new URL(path, root), 'utf8');

test('estate route loads the canonical Command shell', async () => {
  const html = await read('estate.html');
  assert.match(html, /Governed Estate Atlas/);
  assert.match(html, /command-loader\.js/);
  assert.match(html, /DAIL systems, wallets, ledgers, fabrics, factories, plugins, software, contracts, runtimes/i);
  assert.doesNotMatch(html, /<script>(?![^<]*src=)/i);
});

test('Command loader publishes v4 and loads both executive and estate extensions', async () => {
  const source = await read('command-loader.js');
  assert.match(source, /VERSION = '4\.0\.0'/);
  assert.match(source, /ct\.command\.governed-estate\.v4\.0\.0\.20260910/);
  assert.match(source, /command-enhancements\.css/);
  assert.match(source, /command-enhancements\.js/);
  assert.match(source, /command-estate\.css/);
  assert.match(source, /command-estate\.js/);
  assert.match(source, /href=\"\/estate\" data-estate-link/);
  assert.match(source, /credentials: 'same-origin'/);
});

test('estate API is read-only, searchable, and explicitly partial', async () => {
  const source = await read('api/estate.js');
  assert.match(source, /ct\.command\.estate-api\.v4/);
  assert.match(source, /status: 'PARTIAL'/);
  assert.match(source, /COMPLETE_FAMILY_CENSUS_WITH_BOUNDED_SOURCE_SAMPLES_AND_RESTRICTED_PRIVATE_CONTENT/);
  assert.match(source, /request\.method !== 'GET'/);
  assert.match(source, /Allow', 'GET, HEAD'/);
  assert.match(source, /search\.get\('q'\)/);
  assert.match(source, /search\.get\('family'\)/);
  assert.match(source, /search\.get\('source'\)/);
  assert.match(source, /search\.get\('visibility'\)/);
  assert.doesNotMatch(source, /method:\s*['"]POST['"]/);
  assert.doesNotMatch(source, /process\.env|Authorization|Bearer\s|serviceRoleKey|sk_live_|eyJ[A-Za-z0-9_-]{20}/);
});

test('estate manifest preserves authoritative census totals and overlap warning', async () => {
  const release = JSON.parse(await read('command-release-v4.json'));
  assert.equal(release.version, '4.0.0');
  assert.equal(release.census.schemas, 79);
  assert.equal(release.census.tables, 2770);
  assert.equal(release.census.routines, 4827);
  assert.equal(release.census.cron_jobs_active, 297);
  assert.equal(release.census.storage_buckets, 193);
  assert.equal(release.census.github_repositories_observed, 100);
  assert.equal(release.census.capability_providers_discoverable, 44);
  assert.equal(release.indexed_object_families.fabric_mesh_bridge_router, 1062);
  assert.equal(release.indexed_object_families.agent_penta_oracle, 2065);
  assert.equal(release.indexed_object_families.overlapping_counts, true);
});

test('visibility contract keeps protected values restricted', async () => {
  const release = JSON.parse(await read('command-release-v4.json'));
  assert.equal(release.visibility_contract.raw_private_content_public, false);
  assert.equal(release.visibility_contract.credential_material_exposed, false);
  assert.equal(release.visibility_contract.wallet_identifiers_exposed, false);
  assert.equal(release.visibility_contract.balances_exposed, false);
  assert.equal(release.visibility_contract.private_communications_exposed, false);
  assert.equal(release.visibility_contract.private_document_bodies_exposed, false);
  assert.equal(release.control_contract.read_only_projection, true);
  assert.equal(release.control_contract.economic_mutations_exposed, false);
  assert.equal(release.control_contract.external_money_movement_exposed, false);
  assert.equal(release.control_contract.pass_manufactured, false);
});

test('estate UI combines census and live overlays without posting mutations', async () => {
  const source = await read('command-estate.js');
  for (const endpoint of ['/api/estate?limit=1000','/api/command?limit=12','/api/operations?window=24','/api/catalog','/api/health']) {
    assert.match(source, new RegExp(endpoint.replace(/[?]/g, '\\?')));
  }
  assert.match(source, /Promise\.allSettled/);
  assert.match(source, /ct-estate-visibility-pill/);
  assert.match(source, /state\.family/);
  assert.match(source, /state\.source/);
  assert.match(source, /state\.visibility/);
  assert.match(source, /Restricted records disclose the protected class—not the protected value/);
  assert.match(source, /No exceptions does not mean no security/);
  assert.doesNotMatch(source, /method:\s*['"]POST['"]/);
  assert.doesNotMatch(source, /authorization\s*:|wallet_address|account_balance|private_key|service_role/i);
});

test('estate styles are isolated, responsive, and reduced-motion aware', async () => {
  const css = await read('command-estate.css');
  assert.match(css, /\.ct-estate-page/);
  assert.match(css, /\.ct-estate-records/);
  assert.match(css, /\.ct-estate-visibility-pill/);
  assert.match(css, /@media\(max-width:720px\)/);
  assert.match(css, /prefers-reduced-motion/);
  assert.doesNotMatch(css, /url\(https?:/i);
});
