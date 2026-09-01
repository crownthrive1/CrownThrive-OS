import "jsr:@supabase/functions-js/edge-runtime.d.ts";

declare const EdgeRuntime: { waitUntil(promise: Promise<unknown>): void } | undefined;

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const MAX_BODY = 1024 * 1024;
const REDACT = /(password|passcode|token|api[_-]?key|secret|authorization|cookie|session|login[_-]?token|access[_-]?token|refresh[_-]?token|card|cvv|ssn|private[_-]?key)/i;

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
}
function sanitize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitize);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = REDACT.test(k) ? "[REDACTED]" : sanitize(v);
    return out;
  }
  return value;
}
async function sha256(text: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function rpc(fn: string, body: Record<string, unknown>) {
  return fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: "POST",
    headers: { "content-type": "application/json", apikey: SERVICE_ROLE, authorization: `Bearer ${SERVICE_ROLE}` },
    body: JSON.stringify(body),
  });
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  if (req.method === "GET") return json({ ok: true, service: "locticians-bd-webhook-v1", version: "2.0.0", mode: "durable-fast-intake" });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const hook = url.searchParams.get("hook") ?? "";
  const eventHint = url.searchParams.get("event") ?? "auto";
  if (hook.length < 30) return json({ error: "unauthorized" }, 401);

  const declared = Number(req.headers.get("content-length") || "0");
  if (declared > MAX_BODY) return json({ error: "payload_too_large" }, 413);
  const raw = await req.clone().text();
  const bodyBytes = new TextEncoder().encode(raw).length;
  if (bodyBytes > MAX_BODY) return json({ error: "payload_too_large" }, 413);

  const contentType = req.headers.get("content-type") || "";
  let payload: Record<string, unknown> = {};
  try {
    if (contentType.includes("application/json")) payload = raw ? JSON.parse(raw) : {};
    else if (contentType.includes("application/x-www-form-urlencoded")) {
      const params = new URLSearchParams(raw);
      for (const [k, v] of params.entries()) payload[k] = payload[k] === undefined ? v : ([] as unknown[]).concat(payload[k] as unknown, v);
    } else if (contentType.includes("multipart/form-data")) {
      const form = await req.formData();
      for (const [k, v] of form.entries()) payload[k] = typeof v === "string" ? v : `[FILE:${v.name}:${v.size}]`;
    } else payload = raw ? { raw_text: raw.slice(0, MAX_BODY) } : {};
  } catch { return json({ error: "invalid_payload" }, 400); }

  const safePayload = sanitize(payload) as Record<string, unknown>;
  const bodySha = await sha256(raw);
  const forwarded = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || req.headers.get("cf-connecting-ip") || "unknown";
  const sourceSha = await sha256(forwarded);
  const uaSha = await sha256(req.headers.get("user-agent") || "unknown");

  const enq = await rpc("locticians_bd_webhook_enqueue_v1", {
    p_hook_token: hook,
    p_event_hint: eventHint,
    p_payload: safePayload,
    p_body_sha256: bodySha,
    p_body_bytes: bodyBytes,
    p_source_fingerprint_sha256: sourceSha,
    p_user_agent_sha256: uaSha,
  });
  const text = await enq.text();
  if (!enq.ok) {
    const unauthorized = text.includes("invalid_webhook_binding");
    return json({ error: unauthorized ? "unauthorized" : "intake_failed" }, unauthorized ? 401 : 503);
  }

  let accepted: unknown = {};
  try { accepted = text ? JSON.parse(text) : {}; } catch { accepted = {}; }
  const worker = rpc("locticians_bd_webhook_process_intake_v1", { p_limit: 25 }).then(() => undefined).catch(() => undefined);
  if (typeof EdgeRuntime !== "undefined") EdgeRuntime.waitUntil(worker);
  return json({ ok: true, accepted: true, state: "queued", intake: accepted }, 202);
});
