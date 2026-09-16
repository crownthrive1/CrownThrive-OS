import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { projectStorage, integer } from '../lib/storage-command-projection.js';
import { createHandler } from '../api/storage-command.js';
const AT = '2026-09-16T21:00:00.000Z';
const ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const wasabi = () => ({
  observed_at: AT, archive: { state: 'COPIED_VERIFIED', section_no: 1, exported_event_count: 510000, next_shard_no: 71, last_sequence_id: 519000, enabled: true, last_run_at: AT, last_result: { events_copied: 15000 } },
  control: { writes_enabled: true, archive_section_events: 1000000, upload_budget_bytes: 80000000000, safety_stop_at: '2026-10-14T00:00:00Z', metadata: { max_supported_binary_ticket_bytes: 536870912, largest_live_qualification_object_bytes: 34603008, dail_immutable_v2: { retention_mode: 'COMPLIANCE', retention_days: 30 }, private_token: 'DO_NOT_EXPOSE' } },
  sections: [{ section_no: 1, events: 510000, state: 'COPYING' }],
  buckets: [{ lane: 'dail', state: 'READY', bucket: 'PRIVATE_BUCKET_NAME', verified_at: AT }],
  consumers: [{ consumer_id: 'virality-masters', service_id: 'PRIVATE_SERVICE_ID', backend_state: 'READY', site_cutover_state: 'NOT_CUT_OVER', external_delivery_enabled: false }],
  objects: { verified_count: 100, registered_bytes: 900000000 }, balancer: { mode: 'NORMAL', pressure: 42 },
  source_delete_enabled: false, independent_blockchain_or_ipfs_network: false,
});
const catalog = () => ({ sales_enabled: false, activation_state: 'CATALOG_ACTIVE_CAPACITY_QUALIFICATION', offers: [{ id: 'CT-SF-ARCHIVE-1000', name: 'UNTRUSTED_NAME', billing_amount_cents: 14700, billing_interval_months: 3, currency: 'usd', included_bytes: 1000000000000, included_download_bytes: 100000000000, stripe_catalog_active: true, available: true, state: 'STRIPE_ACTIVE_FULFILLMENT_GATED' }] });
function response() { return { headers: {}, code: null, body: null, ended: false, setHeader(k, v) { this.headers[k] = v; }, status(v) { this.code = v; return this; }, json(v) { this.body = v; return this; }, end() { this.ended = true; return this; } }; }
const env = { SUPABASE_URL: ORIGIN, SUPABASE_SERVICE_ROLE_KEY: 'synthetic-service-key' };
const now = () => new Date(AT);
const goodFetch = async (url) => new Response(JSON.stringify(url.includes('ct_wasabi_status_v1') ? wasabi() : catalog()), { status: 200 });

test('actual event count differs from sequence identifier; section percent is exact', () => {
  const p = projectStorage(wasabi(), catalog(), AT);
  assert.equal(p.archive.total_archived_events, 510000);
  assert.equal(p.archive.last_archived_sequence_id, 519000);
  assert.equal(p.archive.section_progress_percent, 51);
  assert.equal(p.archive.sequence_ids_are_event_counts, false);
});
test('missing values stay unknown, never zero or pass', () => {
  const w = { archive: {}, control: {}, observed_at: AT };
  const p = projectStorage(w, null, AT);
  assert.equal(p.archive.total_archived_events, null);
  assert.equal(p.archive.section_progress_percent, null);
  assert.equal(p.archive.sealed_sections_in_status, null);
  assert.equal(p.custody.external_delivery_enabled_count, null);
  assert.equal(p.commerce, null);
  assert.equal(p.status, 'PARTIAL');
});
test('numeric coercion rejects empty, booleans, unsafe numbers and negative values', () => {
  for (const x of [null, undefined, '', true, false, -1, 1.2, {}, [], '12x', 'NaN', '1e3', 2 ** 54]) assert.equal(integer(x), null);
  assert.equal(integer('0'), 0); assert.equal(integer('1000000'), 1000000);
});
test('source secrets, private names, object keys, arbitrary metadata and payloads never escape', () => {
  const w = wasabi(); w.secrets = 'FORBIDDEN_VALUE'; w.archive.payload = 'FORBIDDEN_VALUE';
  w.control.endpoint = 'FORBIDDEN_VALUE'; w.consumers[0].object_key = 'FORBIDDEN_VALUE';
  const result = JSON.stringify(projectStorage(w, catalog(), AT));
  for (const x of ['FORBIDDEN_VALUE', 'DO_NOT_EXPOSE', 'PRIVATE_BUCKET_NAME', 'PRIVATE_SERVICE_ID', 'UNTRUSTED_NAME']) assert.equal(result.includes(x), false);
  assert.equal(projectStorage(w, catalog(), AT).privacy.signed_urls_exposed, false);
});
test('unknown enums and duplicate bucket identities cannot manufacture READY', () => {
  const w = wasabi(); w.archive.state = '<script>SECRET</script>'; w.buckets.push({ lane: 'dail', state: 'READY' });
  const p = projectStorage(w, catalog(), AT);
  assert.equal(p.archive.state, 'UNKNOWN'); assert.equal(p.custody.buckets[0].state, 'UNKNOWN');
});
test('configured upload ceiling and empirical qualification remain separate', () => {
  const p = projectStorage(wasabi(), catalog(), AT);
  assert.equal(p.controls.single_put_ceiling_bytes, 536870912);
  assert.equal(p.controls.largest_empirical_test_bytes, 34603008);
});
test('quarterly price is never mislabeled as a monthly charge', () => {
  const offer = projectStorage(wasabi(), catalog(), AT).commerce.offers[0];
  assert.equal(offer.billing_amount_cents, 14700); assert.equal(offer.billing_interval_months, 3);
  assert.equal(offer.available, false); assert.equal(offer.name, 'Archive Vault');
});
test('unknown offers are omitted and duplicate canonical offers are held', () => {
  const c = catalog(); c.offers.push({ id: 'malicious', name: 'SECRET' }, { ...c.offers[0] });
  assert.deepEqual(projectStorage(wasabi(), c, AT).commerce.offers, []);
});
test('overflowed or missing section progress is not clamped into false completeness', () => {
  const w = wasabi(); w.sections[0].events = 1000001;
  assert.equal(projectStorage(w, catalog(), AT).archive.section_progress_percent, null);
  delete w.archive.section_no;
  assert.equal(projectStorage(w, catalog(), AT).archive.section_events, null);
});
test('stale or future source observation is unavailable, not freshened by retrieval time', () => {
  for (const date of ['2026-09-16T20:00:00Z', '2026-09-17T21:00:00Z', 'invalid']) {
    const w = wasabi(); w.observed_at = date;
    assert.equal(projectStorage(w, catalog(), AT).archive, null);
    assert.equal(projectStorage(w, catalog(), AT).status, 'PARTIAL');
  }
});
test('GET executes only two fixed existing read RPCs and returns sanitized no-store JSON', async () => {
  const calls = []; const r = response();
  await createHandler({ env, now, fetcher: async (url, options) => { calls.push({ url, options }); return goodFetch(url); } })({ method: 'GET', url: '/api/storage-command?url=https://attacker.invalid' }, r);
  assert.equal(r.code, 200); assert.equal(r.body.status, 'OBSERVED'); assert.match(r.headers['Cache-Control'], /no-store/);
  assert.equal(calls.length, 2);
  for (const { url, options } of calls) { assert.ok(url.startsWith(`${ORIGIN}/rest/v1/rpc/`)); assert.equal(options.redirect, 'error'); assert.equal(options.body, '{}'); assert.equal(options.headers.apikey, env.SUPABASE_SERVICE_ROLE_KEY); }
  assert.equal(JSON.stringify(r.body).includes(env.SUPABASE_SERVICE_ROLE_KEY), false);
});
test('write methods are rejected without an upstream call', async () => {
  for (const method of ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']) {
    let calls = 0; const r = response();
    await createHandler({ env, now, fetcher: async () => { calls++; } })({ method }, r);
    assert.equal(r.code, 405); assert.equal(calls, 0); assert.equal(r.headers.Allow, 'GET, HEAD');
  }
});
test('unbound or alternate provider origins fail closed without using a key', async () => {
  for (const value of [undefined, 'http://tzajnzshmtzjenqulehq.supabase.co', `${ORIGIN}/x`, `${ORIGIN}?x=1`, `${ORIGIN}#x`, `${ORIGIN}:443`, `${ORIGIN}.evil.invalid`, 'https://user:pass@tzajnzshmtzjenqulehq.supabase.co']) {
    let calls = 0; const r = response();
    await createHandler({ env: { ...env, SUPABASE_URL: value }, now, fetcher: async () => { calls++; } })({ method: 'GET' }, r);
    assert.equal(r.code, 503); assert.equal(calls, 0); assert.equal(r.body.status, 'UNAVAILABLE');
  }
});
test('no source readback returns 503 without echoing provider errors', async () => {
  const r = response();
  await createHandler({ env, now, fetcher: async () => { throw new Error('SECRET from provider'); } })({ method: 'GET' }, r);
  assert.equal(r.code, 503); assert.equal(JSON.stringify(r.body).includes('SECRET'), false);
});
test('one unavailable source degrades only that panel', async () => {
  const r = response();
  await createHandler({ env, now, fetcher: async (url) => url.includes('ct_wasabi_status_v1') ? new Response('private error', { status: 500 }) : goodFetch(url) })({ method: 'GET' }, r);
  assert.equal(r.code, 200); assert.equal(r.body.status, 'PARTIAL'); assert.equal(r.body.archive, null); assert.equal(r.body.commerce.sales_enabled, false);
});
test('non-object, malformed and oversized responses are never trusted', async () => {
  for (const body of ['[]', 'null', 'not JSON', JSON.stringify({ padding: 'x'.repeat(2 * 1024 * 1024 + 1) })]) {
    const r = response(); await createHandler({ env, now, fetcher: async () => new Response(body) })({ method: 'GET' }, r);
    assert.equal(r.code, 503);
  }
});
test('HEAD has an empty response body', async () => {
  const r = response(); await createHandler({ env, now, fetcher: goodFetch })({ method: 'HEAD' }, r);
  assert.equal(r.code, 200); assert.equal(r.body, null); assert.equal(r.ended, true);
});
test('browser integration adds no polling interval and no upstream HTML injection', async () => {
  const source = await readFile(new URL('../storage-command.js', import.meta.url), 'utf8');
  assert.equal(source.includes('setInterval'), false); assert.equal(source.includes('innerHTML'), false);
  assert.ok(source.includes('MutationObserver')); assert.ok(source.includes('STALE / last known'));
  for (const page of ['overview', 'dail', 'infrastructure', 'commerce', 'evidence', 'integrations']) assert.ok(source.includes(`${page}: [`), page);
});

test('every canonical command route uses the extension loader; other routes and CSP remain unchanged', async () => {
  const config = JSON.parse(await readFile(new URL('../vercel.json', import.meta.url), 'utf8'));
  for (const path of ['/', '/command', '/wallet', '/dail', '/atlas', '/ops', '/infrastructure', '/commerce', '/evidence', '/integrations']) assert.equal(config.rewrites.find((r) => r.source === path)?.destination, '/index.html');
  assert.equal(config.rewrites.some((r) => r.source === '/command-v3.html'), false);
  assert.equal(config.headers[0].headers.find((h) => h.key === 'Content-Security-Policy').value.includes("script-src 'self'"), true);
});
test('loader injects storage assets without replacing existing estate and wallet code', async () => {
  const loader = await readFile(new URL('../command-loader.js', import.meta.url), 'utf8');
  assert.ok(loader.includes('/storage-command.js')); assert.ok(loader.includes('/storage-command.css'));
  assert.ok(loader.includes('data-storage-command-script')); assert.ok(loader.includes('data-storage-command-style'));
  assert.ok(loader.includes('/command-estate.js')); assert.ok(loader.includes('/command-enhancements.js'));
  assert.ok(loader.includes("const CANONICAL_SHELL = '/command-v3.html'"));
});
