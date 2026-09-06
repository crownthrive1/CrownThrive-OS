import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFile(resolve(root, path), 'utf8');

const files = await Promise.all([
  read('command-v3.html'),
  read('command-v3.css'),
  read('command-v3.js'),
  read('vercel.json'),
]);
const [html, css, javascript, vercelText] = files;
const vercel = JSON.parse(vercelText);

test('command v3 is a complete local CSP-compatible surface', () => {
  assert.match(html, /data-command-version="3\.0\.0"/);
  assert.match(html, /href="\/command-v3\.css"/);
  assert.match(html, /src="\/command-v3\.js"/);
  assert.doesNotMatch(html, /<script(?![^>]+src=)/i);
  assert.doesNotMatch(html, /\sstyle=/i);
  assert.match(css, /@media\(max-width:720px\)/);
  assert.match(css, /prefers-reduced-motion/);
});

test('all nine operating views are present and independently routable', () => {
  const routes = ['overview','wallet','dail','atlas','ops','infrastructure','commerce','evidence','integrations'];
  for (const route of routes) {
    assert.match(html, new RegExp(`data-page="${route}"`));
    assert.match(javascript, new RegExp(`${route}:\\{path:`));
  }
  assert.match(javascript, /history\.pushState/);
  assert.match(javascript, /popstate/);
  assert.match(javascript, /paletteCommands/);
});

test('certified CHLOM Wallet checkpoint and external-rail boundaries remain exact', () => {
  assert.match(javascript, /PRODUCTION_RESTRICTED_EXTERNAL_RAILS/);
  assert.match(javascript, /ct\.cert\.chlom-wallet\.v3\.20260904034831436\.fd4578817c96/);
  assert.match(javascript, /cccc5825b758eb60b2f5856e726f08c6861fe439d4a44f1b3efe860005423608/);
  assert.match(javascript, /service_bindings:627/);
  assert.match(javascript, /active_wallets:5/);
  assert.match(javascript, /verified_internal_accounts:5/);
  assert.match(javascript, /provider_contract_required/);
  assert.match(javascript, /pending_site_injection/);
  assert.match(javascript, /stablecoin_checkout:\{state:'HOLD'/);
  assert.match(javascript, /max_unattended_value_minor:0/);
  assert.match(javascript, /liveCommand/);
});

test('Three DAIL doctrine preserves one lineage with typed projections', () => {
  assert.match(html, /They are three views of one governed event lineage—not competing ledgers\./);
  assert.match(javascript, /machine:\{name:'DAIL Machine',authority:'D2'/);
  assert.match(javascript, /human:\{name:'DAIL Human',authority:'D3'/);
  assert.match(javascript, /hybrid:\{name:'DAIL Hybrid Crossover',authority:'D2'/);
  assert.match(javascript, /verified_through_sequence_id/);
  assert.match(javascript, /sequence_span_lag/);
  assert.match(javascript, /verified prefix/i);
});

test('the public browser surface has no economic or provider mutation transport', () => {
  assert.doesNotMatch(javascript, /method\s*:\s*['"](?:POST|PUT|PATCH|DELETE)['"]/i);
  assert.doesNotMatch(javascript, /checkout\.sessions|payment_intents|transfers|payouts|issuing\/cards/i);
  assert.doesNotMatch(javascript, /service_role|authorization\s*:/i);
  assert.match(javascript, /economic_mutations_exposed/);
  assert.match(javascript, /credential_material_exposed/);
  assert.match(html, /No balances, wallet identifiers, private actors, credentials, raw payloads, or economic mutations\./);
});

test('ecosystem atlas covers CrownThrive corridors and the Penta family', () => {
  const required = ['CrownThrive IO','CHLOM Wallet','Cultural Imprint Engine','Thrive Flywheel','PentaBrain','PentaGreen','PentaCertifier','PentaSecurity','PentaBalancer','PentaClock','PentaBooks','PentaPersona','PentaAds','Go Flipbooks','Locticians','Melanated Voices TV','Virality Music','CrownThriveU','CrownRewards','AdLuxe Network'];
  for (const name of required) assert.ok(javascript.includes(name), name);
  assert.match(javascript, /const ATLAS=GROUPS\.flatMap/);
  assert.match(html, /id="atlasSearch"/);
  assert.match(html, /id="atlasCorridor"/);
});

test('Vercel makes the new command surface primary while preserving APIs', () => {
  const rewrites = Object.fromEntries(vercel.rewrites.map(({ source, destination }) => [source, destination]));
  for (const route of ['/','/command','/wallet','/dail','/atlas','/ops','/infrastructure','/commerce','/evidence','/integrations']) {
    assert.equal(rewrites[route], '/command-v3.html', route);
  }
  assert.equal(rewrites['/health'], '/api/health');
  assert.equal(rewrites['/fabric'], '/api/fabric');
  assert.equal(rewrites['/mcp'], '/api/mcp');
  assert.equal(rewrites['/penta'], '/api/penta');
  assert.equal(rewrites['/chlom'], '/api/chlom');
  const csp = vercel.headers.flatMap((entry) => entry.headers).find((entry) => entry.key === 'Content-Security-Policy')?.value;
  assert.match(csp, /script-src 'self'/);
  assert.match(csp, /connect-src 'self'/);
  assert.doesNotMatch(csp, /'unsafe-inline'|'unsafe-eval'/);
});
