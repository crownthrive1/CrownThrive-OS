import assert from "node:assert/strict";
import test from "node:test";

import {
  ADMISSION_HMAC_KEY_ENV,
  buildAdmissionStatement,
  computeAdmissionMac,
  createDailExternalIngressHandler,
  INGEST_RPC,
  parseStripeEventSummary,
  STRIPE_SECRET_SET_ENV,
  StripeEventSchemaError,
  type IngestRpcArguments,
  type RpcResult,
} from "./handler.ts";
import { sha256Hex } from "./stripe_signature.ts";

const NOW_SECONDS = 1_800_000_000;
const NOW_MS = NOW_SECONDS * 1000;
const WEBHOOK_SECRET = "whsec_test_fixture_current_nonsecret";
const OLD_WEBHOOK_SECRET = "whsec_test_fixture_old_nonsecret";
const ADMISSION_KEY = "admission-test-key-with-at-least-32-bytes";
const UTF8 = new TextEncoder();

type CapturedCall = { name: string; args: IngestRpcArguments };

function eventBody(overrides: Record<string, unknown> = {}): Uint8Array {
  return UTF8.encode(JSON.stringify({
    id: "evt_123",
    object: "event",
    type: "payment_intent.succeeded",
    api_version: "2026-08-01",
    created: NOW_SECONDS - 10,
    livemode: false,
    pending_webhooks: 1,
    request: { id: "req_123", idempotency_key: "not-projected" },
    account: "acct_123",
    data: {
      object: {
        id: "pi_123",
        object: "payment_intent",
        metadata: { private: "not-projected" },
      },
      previous_attributes: { private: "not-projected" },
    },
    ...overrides,
  }));
}

function hex(bytes: Uint8Array): string {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}

async function stripeHeader(
  rawBody: Uint8Array,
  secret = WEBHOOK_SECRET,
  timestamp = NOW_SECONDS,
): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    UTF8.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const prefix = UTF8.encode(`${timestamp}.`);
  const payload = new Uint8Array(prefix.length + rawBody.length);
  payload.set(prefix);
  payload.set(rawBody, prefix.length);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC", key, payload));
  return `t=${timestamp},v1=${"0".repeat(64)},v1=${hex(signature)}`;
}

function secretSet(): string {
  return JSON.stringify([
    {
      version_ref: "vault:stripe:endpoint:new",
      secret: WEBHOOK_SECRET,
      environment: "test",
    },
    {
      version_ref: "vault:stripe:endpoint:old",
      secret: OLD_WEBHOOK_SECRET,
      environment: "test",
    },
    {
      version_ref: "vault:stripe:endpoint:live",
      secret: "whsec_live_only",
      environment: "live",
    },
  ]);
}

function makeHandler(input: {
  rpcResult?: RpcResult;
  env?: Record<string, string | undefined>;
  calls?: CapturedCall[];
} = {}) {
  const calls = input.calls ?? [];
  const env: Record<string, string | undefined> = {
    [STRIPE_SECRET_SET_ENV]: secretSet(),
    [ADMISSION_HMAC_KEY_ENV]: ADMISSION_KEY,
    SUPABASE_URL: "https://example.supabase.co",
    SUPABASE_SERVICE_ROLE_KEY: "service-role-test-value",
    ...input.env,
  };
  const handler = createDailExternalIngressHandler({
    nowMs: () => NOW_MS,
    getEnv: (name) => env[name],
    createRpcClient: () => ({
      rpc: async (name, args) => {
        calls.push({ name, args });
        return input.rpcResult ?? { data: { ok: true, duplicate: false }, error: null };
      },
    }),
  });
  return { calls, handler };
}

async function post(rawBody: Uint8Array, signature: string): Promise<Request> {
  return new Request("https://example.invalid/dail-external-ingress", {
    method: "POST",
    headers: { "stripe-signature": signature, "content-type": "application/json" },
    body: rawBody,
  });
}

test("valid exact bytes produce only the narrow RPC admission projection", async () => {
  const rawBody = eventBody();
  const signature = await stripeHeader(rawBody, OLD_WEBHOOK_SECRET);
  const { calls, handler } = makeHandler();
  const result = await handler(await post(rawBody, signature));

  assert.equal(result.status, 200);
  assert.deepEqual(await result.json(), { ok: true, duplicate: false });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].name, INGEST_RPC);
  assert.equal(calls[0].args.p_secret_version_ref, "vault:stripe:endpoint:old");
  assert.equal(calls[0].args.p_source_event_id, "evt_123");
  assert.equal(calls[0].args.p_provider_object_id, "pi_123");
  assert.equal(calls[0].args.p_raw_body_sha256, await sha256Hex(rawBody));
  assert.match(calls[0].args.p_signature_header_sha256, /^[0-9a-f]{64}$/);
  assert.match(calls[0].args.p_signed_payload_sha256, /^[0-9a-f]{64}$/);
  assert.match(calls[0].args.p_admission_mac, /^[0-9a-f]{64}$/);

  const serializedArgs = JSON.stringify(calls[0].args);
  assert.doesNotMatch(serializedArgs, /whsec_/);
  assert.doesNotMatch(serializedArgs, /private/);
  assert.doesNotMatch(serializedArgs, /stripe-signature/i);
  assert.doesNotMatch(serializedArgs, new RegExp(ADMISSION_KEY));
});

test("duplicate RPC result is a small successful response", async () => {
  const rawBody = eventBody();
  const { handler } = makeHandler({
    rpcResult: { data: { ok: true, duplicate: true, event_id: "not-returned" }, error: null },
  });
  const result = await handler(await post(rawBody, await stripeHeader(rawBody)));
  assert.equal(result.status, 200);
  assert.deepEqual(await result.json(), { ok: true, duplicate: true });
});

test("mutated bytes, stale timestamps, and environment mismatch are rejected", async () => {
  const rawBody = eventBody();
  const signature = await stripeHeader(rawBody);
  const mutated = new Uint8Array([...rawBody, 0x0a]);
  const first = makeHandler();
  assert.equal((await first.handler(await post(mutated, signature))).status, 400);
  assert.equal(first.calls.length, 0);

  const stale = makeHandler();
  const staleHeader = await stripeHeader(rawBody, WEBHOOK_SECRET, NOW_SECONDS - 301);
  assert.equal((await stale.handler(await post(rawBody, staleHeader))).status, 400);
  assert.equal(stale.calls.length, 0);

  const liveBody = eventBody({ livemode: true });
  const mismatch = makeHandler();
  assert.equal(
    (await mismatch.handler(await post(liveBody, await stripeHeader(liveBody)))).status,
    400,
  );
  assert.equal(mismatch.calls.length, 0);
});

test("method, signature, schema, and database failure use stable public errors", async () => {
  const { handler } = makeHandler();
  const method = await handler(new Request("https://example.invalid", { method: "GET" }));
  assert.equal(method.status, 405);
  assert.equal(method.headers.get("allow"), "POST");

  const missingHeader = await handler(new Request("https://example.invalid", {
    method: "POST",
    body: eventBody(),
  }));
  assert.equal(missingHeader.status, 400);

  const invalid = UTF8.encode('{"id":"evt_123"}');
  const invalidSchema = await handler(await post(invalid, await stripeHeader(invalid)));
  assert.equal(invalidSchema.status, 400);

  const rawBody = eventBody();
  const database = makeHandler({
    rpcResult: { data: null, error: { message: "sensitive database detail" } },
  });
  const databaseResult = await database.handler(
    await post(rawBody, await stripeHeader(rawBody)),
  );
  assert.equal(databaseResult.status, 503);
  assert.deepEqual(await databaseResult.json(), {
    ok: false,
    error: "temporarily_unavailable",
  });
});

test("unconfigured or credential-confused secrets fail closed with 503", async () => {
  const rawBody = eventBody();
  const signature = await stripeHeader(rawBody);

  const missingAdmission = makeHandler({ env: { [ADMISSION_HMAC_KEY_ENV]: undefined } });
  assert.equal(
    (await missingAdmission.handler(await post(rawBody, signature))).status,
    503,
  );

  const stripeAdmission = makeHandler({
    env: { [ADMISSION_HMAC_KEY_ENV]: "whsec_not-an-admission-key-of-adequate-length" },
  });
  assert.equal(
    (await stripeAdmission.handler(await post(rawBody, signature))).status,
    503,
  );

  const apiKeyAsWebhookSecret = makeHandler({
    env: {
      [STRIPE_SECRET_SET_ENV]: JSON.stringify([{
        version_ref: "vault:stripe:wrong-kind",
        secret: "sk_test_not_a_webhook_endpoint_secret",
        environment: "test",
      }]),
    },
  });
  assert.equal(
    (await apiKeyAsWebhookSecret.handler(await post(rawBody, signature))).status,
    503,
  );
});

test("event parser requires plausible Stripe event identity and timestamps", () => {
  assert.equal(parseStripeEventSummary(eventBody(), NOW_MS).objectId, "pi_123");
  assert.throws(
    () => parseStripeEventSummary(eventBody({ id: "not-an-event" }), NOW_MS),
    StripeEventSchemaError,
  );
  assert.throws(
    () => parseStripeEventSummary(eventBody({ created: NOW_SECONDS + 301 }), NOW_MS),
    StripeEventSchemaError,
  );
  assert.throws(
    () => parseStripeEventSummary(eventBody({ pending_webhooks: -1 }), NOW_MS),
    StripeEventSchemaError,
  );
});

test("admission helper uses the exact v2 statement and deterministic HMAC", async () => {
  const input = {
    eventId: "evt_123",
    rawBodySha256: "a".repeat(64),
    signatureTimestamp: NOW_SECONDS,
    matchedSecretVersionRef: "vault:stripe:endpoint:old",
  };
  assert.equal(
    buildAdmissionStatement(input),
    `dail-external-ingress-v2|evt_123|${"a".repeat(64)}|${NOW_SECONDS}|vault:stripe:endpoint:old`,
  );
  assert.equal(
    await computeAdmissionMac(ADMISSION_KEY, input),
    "9e367442a681dbff8c5d6886ab04a310c9c7438009ea2b65f6f245d81118e369",
  );
});
