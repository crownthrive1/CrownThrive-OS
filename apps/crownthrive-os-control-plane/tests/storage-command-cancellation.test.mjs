import test from 'node:test';
import assert from 'node:assert/strict';
import { createHandler } from '../api/storage-command.js';

const ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const env = { SUPABASE_URL: ORIGIN, SUPABASE_SERVICE_ROLE_KEY: 'synthetic-service-key' };
const now = () => new Date('2026-11-21T11:56:00.000Z');
const catalog = { sales_enabled: false, activation_state: 'UNKNOWN', offers: [] };

function response() {
  return {
    headers: {}, code: null, body: null,
    setHeader(key, value) { this.headers[key] = value; },
    status(code) { this.code = code; return this; },
    json(body) { this.body = body; return this; },
    end() { return this; },
  };
}

async function invoke(wasabiResponse) {
  const result = response();
  let timeout;
  const completed = await Promise.race([
    createHandler({
      env,
      now,
      fetcher: async (url) => url.endsWith('/ct_wasabi_status_v1')
        ? wasabiResponse
        : new Response(JSON.stringify(catalog), { status: 200 }),
    })({ method: 'GET' }, result).then(() => true),
    new Promise((resolve) => { timeout = setTimeout(() => resolve(false), 150); }),
  ]);
  clearTimeout(timeout);
  return { completed, response: result };
}

test('a non-success upstream body with a never-settling cancel hook cannot hang the read route', async () => {
  let cancelCalled = false;
  const body = new ReadableStream({
    cancel() {
      cancelCalled = true;
      return new Promise(() => {});
    },
  }, { highWaterMark: 0 });

  const outcome = await invoke(new Response(body, { status: 503 }));
  assert.equal(outcome.completed, true);
  assert.equal(cancelCalled, true);
  assert.equal(outcome.response.code, 200);
  assert.equal(outcome.response.body.status, 'PARTIAL');
  assert.equal(outcome.response.body.archive, null);
});

test('an oversized declared body with a never-settling cancel hook cannot hang the read route', async () => {
  let cancelCalled = false;
  const body = new ReadableStream({
    cancel() {
      cancelCalled = true;
      return new Promise(() => {});
    },
  }, { highWaterMark: 0 });

  const outcome = await invoke(new Response(body, {
    status: 200,
    headers: { 'Content-Length': String(2 * 1024 * 1024 + 1) },
  }));
  assert.equal(outcome.completed, true);
  assert.equal(cancelCalled, true);
  assert.equal(outcome.response.code, 200);
  assert.equal(outcome.response.body.status, 'PARTIAL');
  assert.equal(outcome.response.body.archive, null);
});

test('an oversized streamed body with a never-settling reader cancel hook cannot hang the read route', async () => {
  let cancelCalled = false;
  const body = new ReadableStream({
    pull(controller) {
      controller.enqueue(new Uint8Array(2 * 1024 * 1024 + 1));
    },
    cancel() {
      cancelCalled = true;
      return new Promise(() => {});
    },
  }, { highWaterMark: 0 });

  const outcome = await invoke(new Response(body, { status: 200 }));
  assert.equal(outcome.completed, true);
  assert.equal(cancelCalled, true);
  assert.equal(outcome.response.code, 200);
  assert.equal(outcome.response.body.status, 'PARTIAL');
  assert.equal(outcome.response.body.archive, null);
});
