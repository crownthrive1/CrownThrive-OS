import assert from "node:assert/strict";
import test from "node:test";

import {
  parseStripeSignatureHeader,
  parseWebhookSecrets,
  StripeConfigurationError,
  StripeVerificationError,
  verifyStripeSignature,
} from "./stripe_signature.ts";

const UTF8 = new TextEncoder();
const NOW_SECONDS = 1_800_000_000;
const RAW = UTF8.encode('{\n  "id": "evt_exact"\n}');

function hex(bytes: Uint8Array): string {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}

async function signature(secret: string, raw = RAW): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    UTF8.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const prefix = UTF8.encode(`${NOW_SECONDS}.`);
  const signed = new Uint8Array(prefix.length + raw.length);
  signed.set(prefix);
  signed.set(raw, prefix.length);
  return hex(new Uint8Array(await crypto.subtle.sign("HMAC", key, signed)));
}

test("constant-work verifier supports rotation and multiple v1 values", async () => {
  const oldSecret = "whsec_test_fixture_rotated_nonsecret";
  const header = `t=${NOW_SECONDS},v1=${"0".repeat(64)},v1=${await signature(oldSecret)}`;
  const result = await verifyStripeSignature({
    rawBody: RAW,
    signatureHeader: header,
    secrets: [
      { versionRef: "vault:new", secret: "whsec_new_rotation", environment: "test" },
      { versionRef: "vault:old", secret: oldSecret, environment: "test" },
    ],
    nowMs: NOW_SECONDS * 1000,
  });
  assert.equal(result.versionRef, "vault:old");
  assert.match(result.signedPayloadSha256, /^[0-9a-f]{64}$/);
  assert.doesNotMatch(JSON.stringify(result), /whsec_/);
});

test("signature parser rejects ambiguity and excessive signature candidates", () => {
  assert.throws(
    () => parseStripeSignatureHeader(`t=1,t=2,v1=${"0".repeat(64)}`),
    StripeVerificationError,
  );
  assert.throws(
    () => parseStripeSignatureHeader(`t=1,t=1,v1=${"0".repeat(64)}`),
    StripeVerificationError,
  );
  const excessive = `t=1,${Array.from({ length: 17 }, () => `v1=${"0".repeat(64)}`).join(",")}`;
  assert.throws(() => parseStripeSignatureHeader(excessive), StripeVerificationError);
});

test("secret parser accepts active overlap but rejects API-key confusion", () => {
  const active = parseWebhookSecrets(JSON.stringify([
    {
      version_ref: "vault:old",
      secret: "whsec_old",
      environment: "test",
      active_until: "2030-01-01T00:00:00Z",
    },
    {
      version_ref: "vault:new",
      secret: "whsec_new",
      environment: "test",
      active_from: "2020-01-01T00:00:00Z",
    },
  ]), 1_800_000_000_000);
  assert.deepEqual(active.map((item) => item.versionRef), ["vault:old", "vault:new"]);

  assert.throws(
    () => parseWebhookSecrets(JSON.stringify([{
      version_ref: "vault:wrong",
      secret: "sk_live_api_key_not_webhook_secret",
      environment: "live",
    }])),
    StripeConfigurationError,
  );
  assert.throws(
    () => parseWebhookSecrets(JSON.stringify([{
      version_ref: "sk_live_secret-bearing-reference",
      secret: "whsec_endpoint",
      environment: "live",
    }])),
    StripeConfigurationError,
  );
  assert.throws(
    () => parseWebhookSecrets(JSON.stringify([
      { version_ref: "vault:a", secret: "whsec_same", environment: "test" },
      { version_ref: "vault:b", secret: "whsec_same", environment: "test" },
    ])),
    StripeConfigurationError,
  );
});
