import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const VERSION = "2.0.0";
const MAX_BYTES = 2 * 1024 * 1024;
const TOLERANCE_SECONDS = 300;
const encoder = new TextEncoder();

function respond(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

async function rpc(name: string, body: Record<string, unknown> = {}) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      authorization: `Bearer ${SERVICE_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data: unknown = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  return data as any;
}

async function readBoundedBody(request: Request) {
  const declared = Number(request.headers.get("content-length") || "0");
  if (declared > MAX_BYTES) throw new Error("request_too_large");
  if (!request.body) throw new Error("body_required");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const part = await reader.read();
    if (part.done) break;
    if (!part.value) continue;
    total += part.value.byteLength;
    if (total > MAX_BYTES) {
      try { await reader.cancel(); } catch {}
      throw new Error("request_too_large");
    }
    chunks.push(part.value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { bytes, text: new TextDecoder().decode(bytes) };
}

function bytesToHex(bytes: Uint8Array) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(bytes: Uint8Array) {
  return bytesToHex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)));
}

async function hmacHex(secret: string, message: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return bytesToHex(new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(message))));
}

function constantTimeEqual(a: string, b: string) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function parseStripeSignature(header: string) {
  let timestamp: number | null = null;
  const signatures: string[] = [];
  for (const component of header.split(",")) {
    const [rawKey, ...rawValue] = component.trim().split("=");
    const value = rawValue.join("=");
    if (rawKey === "t") timestamp = Number(value);
    if (rawKey === "v1" && value) signatures.push(value);
  }
  if (!timestamp || signatures.length === 0) throw new Error("invalid_stripe_signature_header");
  return { timestamp, signatures };
}

async function verifySignature(secret: string, rawBody: string, signatureHeader: string) {
  const parsed = parseStripeSignature(signatureHeader);
  const age = Math.abs(Math.floor(Date.now() / 1000) - parsed.timestamp);
  if (age > TOLERANCE_SECONDS) throw new Error("stripe_signature_timestamp_outside_tolerance");
  const expected = await hmacHex(secret, `${parsed.timestamp}.${rawBody}`);
  if (!parsed.signatures.some((candidate) => constantTimeEqual(candidate, expected))) {
    throw new Error("stripe_signature_verification_failed");
  }
  return parsed.timestamp;
}

Deno.serve(async (request: Request) => {
  try {
    if (request.method !== "POST") return respond(405, { ok: false, error: "POST_required", version: VERSION });
    const path = new URL(request.url).pathname.split("/").filter(Boolean);
    const target = path[path.length - 1];
    if (!new Set(["thrivetickets", "sermon_toolkit"]).has(target)) {
      return respond(404, { ok: false, error: "unknown_webhook_target", version: VERSION });
    }

    const config = await rpc("stripe_webhook_target_config_v2", { p_target_key: target });
    if (!config?.signing_secret_alias) throw new Error("target_configuration_missing");
    const signingSecret = await rpc("get_runtime_secret", { secret_name: String(config.signing_secret_alias) });
    if (typeof signingSecret !== "string" || !signingSecret.startsWith("whsec_")) {
      throw new Error("stripe_signing_secret_unavailable");
    }

    const signatureHeader = request.headers.get("stripe-signature") ?? "";
    if (!signatureHeader) throw new Error("stripe_signature_required");
    const body = await readBoundedBody(request);
    const signatureTimestamp = await verifySignature(signingSecret, body.text, signatureHeader);
    let event: any;
    try { event = JSON.parse(body.text); } catch { throw new Error("invalid_event_json"); }
    const payloadSha = await sha256(body.bytes);
    const sourceKind = request.headers.get("x-crownthrive-bootstrap-canary") === "1"
      ? "bootstrap_canary"
      : "stripe_provider";
    const recorded = await rpc("stripe_webhook_record_event_v2", {
      p_target_key: target,
      p_event: event,
      p_payload_sha256: payloadSha,
      p_signature_timestamp: signatureTimestamp,
      p_signature_verified: true,
      p_source_kind: sourceKind,
    });

    return respond(200, {
      received: true,
      duplicate: Boolean(recorded?.duplicate),
      target,
      event_id: recorded?.event_id ?? null,
      processing_state: recorded?.processing_state ?? "QUEUED",
      version: VERSION,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const status = message === "request_too_large" ? 413
      : message.includes("signature") || message === "invalid_event_json" ? 400
      : message.includes("unavailable") || message.includes("configuration") ? 503
      : 500;
    return respond(status, {
      ok: false,
      error: message,
      provider_event_accepted: false,
      secret_exposed: false,
      version: VERSION,
    });
  }
});
