import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

// Public responses intentionally expose stable error classes, never provider or exception messages.
const url = Deno.env.get("SUPABASE_URL")!;
const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(url, serviceKey, { auth: { persistSession: false } });
const COOKIE = "ct_penta_nurture";

const json = (body: unknown, status = 200, cookie?: string) => {
  const headers = new Headers({
    "content-type": "application/json",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  if (cookie) headers.append("set-cookie", `${COOKIE}=${cookie}; Path=/; Max-Age=2592000; Secure; HttpOnly; SameSite=Lax`);
  return new Response(JSON.stringify(body), { status, headers });
};

const cookieValue = (req: Request) => {
  const raw = req.headers.get("cookie") ?? "";
  const m = raw.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([0-9a-fA-F-]{36})(?:;|$)`));
  return m?.[1] ?? crypto.randomUUID();
};

const sha256 = async (value: string) => {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
};

const serviceRole = (req: Request) => {
  try {
    const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
    const part = token.split(".")[1];
    if (!part) return false;
    const padded = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
    return JSON.parse(atob(padded))?.role === "service_role";
  } catch {
    return false;
  }
};

Deno.serve(async (req) => {
  const session = cookieValue(req);
  const sessionHash = await sha256(session);
  try {
    if (!serviceRole(req)) return json({ ok: false, error: "service_role_required" }, 403, session);
    if (req.method !== "GET" && req.method !== "POST") return json({ ok: false, error: "GET_or_POST_required" }, 405, session);

    let body: Record<string, unknown> = {};
    if (req.method === "POST") {
      try { body = await req.json(); } catch { body = {}; }
    }
    const u = new URL(req.url);
    const action = String(body.action ?? u.searchParams.get("action") ?? "status");
    const surfaceId = body.surface_id ? String(body.surface_id) : null;
    const providerSystem = body.provider_system ? String(body.provider_system) : null;

    const allowed = new Set(["status", "nurture", "reconcile", "heartbeat"]);
    if (!allowed.has(action)) return json({ ok: false, error: "unsupported_action", allowed: [...allowed] }, 400, session);

    let result: unknown;
    if (action === "nurture" || action === "reconcile") {
      const { data, error } = await db.rpc("penta_nurture_tick_v1");
      if (error) throw new Error("nurture_tick_failed");
      result = data;
    } else {
      const { data, error } = await db.rpc("penta_nurture_status_v1");
      if (error) throw new Error("nurture_status_failed");
      result = data;
    }

    const metadata = {
      action,
      method: req.method,
      runtime: "penta-nurture.edge.v1",
      software_priority: true,
      secret_material_exposed: false,
    };
    const { error: telemetryError } = await db.rpc("penta_nurture_record_cookie_event_v1", {
      p_cookie_sha256: sessionHash,
      p_event_type: `penta.nurture.${action}`,
      p_surface_id: surfaceId,
      p_provider_system: providerSystem,
      p_consent_state: "necessary",
      p_actor_class: "software",
      p_metadata: metadata,
    });
    if (telemetryError) throw new Error("nurture_telemetry_failed");

    return json({ ok: true, service: "PentaNurture", action, result, telemetry: { cookie_value_stored: false, server_hash: "SHA-256" } }, 200, session);
  } catch {
    return json({ ok: false, service: "PentaNurture", error: "internal_runtime_error" }, 500, session);
  }
});
