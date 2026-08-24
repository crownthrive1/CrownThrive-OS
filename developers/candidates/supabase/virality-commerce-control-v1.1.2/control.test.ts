import assert from "node:assert/strict";
import test from "node:test";

import {
  ALLOWED_ORIGIN,
  classifyDispatchRegistry,
  createHandler,
  MAX_BODY_BYTES,
  MUTATION_AUTHORITY,
} from "./control.ts";

const endpoint =
  "https://example.supabase.co/functions/v1/virality-commerce-control";
const handler = createHandler(async () => ({
  service: "ct.virality-commerce-control",
  overall_state: "HOLD",
  raw_secret_export: false,
}));

function headers(origin?: string) {
  const value = new Headers({ "content-type": "application/json" });
  if (origin !== undefined) value.set("origin", origin);
  return value;
}

function post(origin: string | undefined, body = { action: "health" }) {
  return new Request(endpoint, {
    method: "POST",
    headers: headers(origin),
    body: JSON.stringify(body),
  });
}

test("public least-data GET may omit Origin", async () => {
  const response = await handler(new Request(endpoint));
  assert.equal(response.status, 200);
  assert.equal((await response.json()).overall_state, "HOLD");
});

test("GET rejects a non-canonical Origin", async () => {
  const response = await handler(
    new Request(endpoint, { headers: { origin: "https://crownthrive.com" } }),
  );
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "origin_not_allowed" });
});

test("POST rejects a missing Origin", async () => {
  const response = await handler(post(undefined));
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "origin_required" });
});

test("POST rejects an alternate CrownThrive Origin", async () => {
  const response = await handler(post("https://kjvsermontoolkit.crownthrive.com"));
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "origin_not_allowed" });
});

test("POST accepts the exact VM Origin for a read-only conversion", async () => {
  const response = await handler(
    post(ALLOWED_ORIGIN, {
      action: "convert_virality_credits",
      amount: 2,
    }),
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN);
  assert.deepEqual(await response.json(), {
    from: "Virality Credits",
    amount: 2,
    to: "Crown Credits",
    canonical_amount: 50,
    ratio: "1 Virality Credit = 25 Crown Credits",
    ledger_mutation: false,
    historical_balance_rewrite: false,
  });
});

test("OPTIONS rejects a missing Origin", async () => {
  const response = await handler(new Request(endpoint, { method: "OPTIONS" }));
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "origin_required" });
});

test("OPTIONS rejects a wrong Origin", async () => {
  const response = await handler(
    new Request(endpoint, {
      method: "OPTIONS",
      headers: { origin: "https://evil.example" },
    }),
  );
  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { error: "origin_not_allowed" });
});

test("OPTIONS accepts the exact VM Origin", async () => {
  const response = await handler(
    new Request(endpoint, {
      method: "OPTIONS",
      headers: { origin: ALLOWED_ORIGIN },
    }),
  );
  assert.equal(response.status, 204);
  assert.equal(response.headers.get("access-control-allow-origin"), ALLOWED_ORIGIN);
});

test("chunked overflow is canceled and rejected at 4 KiB", async () => {
  let canceledWith: unknown = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new Uint8Array(MAX_BODY_BYTES));
      controller.enqueue(new Uint8Array([0x7b]));
    },
    cancel(reason) {
      canceledWith = reason;
    },
  });
  const request = new Request(endpoint, {
    method: "POST",
    headers: headers(ALLOWED_ORIGIN),
    body: stream,
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  const response = await handler(request);
  assert.equal(response.status, 413);
  assert.deepEqual(await response.json(), {
    error: "payload_too_large",
    raw_secret_export: false,
  });
  assert.equal(canceledWith, "payload_too_large");
});

test("streamed request within the cap remains valid", async () => {
  const encoded = new TextEncoder().encode(
    JSON.stringify({ action: "convert_virality_credits", amount: 1 }),
  );
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoded.subarray(0, 8));
      controller.enqueue(encoded.subarray(8));
      controller.close();
    },
  });
  const request = new Request(endpoint, {
    method: "POST",
    headers: headers(ALLOWED_ORIGIN),
    body: stream,
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  const response = await handler(request);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).canonical_amount, 25);
});

test("dispatch registry true is an explicit non-authorizing HOLD", () => {
  const control = classifyDispatchRegistry({
    read_state: "READABLE",
    row: { enabled: true },
  });
  assert.equal(control.state, "HOLD_REGISTRY_FLAG_TRUE_UNAUTHORIZED");
  assert.equal(control.effective_enabled, false);
  assert.equal(control.execution_authorized, false);
});

test("dispatch registry missing is an explicit HOLD", () => {
  const control = classifyDispatchRegistry({
    read_state: "READABLE",
    row: null,
  });
  assert.equal(control.state, "HOLD_REGISTRY_STATE_MISSING_OR_UNREADABLE");
  assert.equal(control.registry_enabled_evidence, null);
  assert.equal(control.execution_authorized, false);
});

test("dispatch registry unreadable is an explicit HOLD", () => {
  const control = classifyDispatchRegistry({
    read_state: "UNREADABLE",
    row: null,
  });
  assert.equal(control.state, "HOLD_REGISTRY_STATE_MISSING_OR_UNREADABLE");
  assert.equal(control.registry_read_state, "UNREADABLE");
  assert.equal(control.execution_authorized, false);
});

test("dispatch registry false stays disabled and held", () => {
  const control = classifyDispatchRegistry({
    read_state: "READABLE",
    row: { enabled: false },
  });
  assert.equal(control.state, "HOLD_REGISTRY_DISABLED_BY_POLICY");
  assert.equal(control.effective_enabled, false);
  assert.equal(control.execution_authorized, false);
});

test("every exported mutation and secret authority remains false", () => {
  assert.ok(Object.keys(MUTATION_AUTHORITY).length >= 6);
  assert.ok(Object.values(MUTATION_AUTHORITY).every((value) => value === false));
});
