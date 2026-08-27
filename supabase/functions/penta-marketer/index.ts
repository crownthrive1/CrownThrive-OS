import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const VERSION = "1.0.0";
const SERVER = {
  name: "PentaMarketer",
  service: "ct.penta.marketer.locticians.v1",
  canonicalAgent: "ct.ops.agent.email-attention",
  version: VERSION,
  production: true,
};

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

function headers() {
  return {
    apikey: SERVICE,
    authorization: `Bearer ${SERVICE}`,
    "content-type": "application/json",
  };
}

async function rpc(name: string, body: Record<string, unknown> = {}) {
  const response = await fetch(`${BASE}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data: unknown = text;
  try { data = text ? JSON.parse(text) : null; } catch { /* bounded text retained */ }
  if (!response.ok) {
    throw new Error(`${name}:${response.status}:${typeof data === "string" ? data.slice(0, 500) : JSON.stringify(data).slice(0, 500)}`);
  }
  return data;
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return respond({ ok: false, error: "POST_required", server: SERVER }, 405);
    const token = req.headers.get("x-penta-marketer-token") ?? "";
    if (!token || await rpc("penta_marketer_edge_authorize_v1", { p_token: token }) !== true) {
      return respond({ ok: false, error: "penta_marketer_authorization_required", server: SERVER }, 403);
    }
    const body = await req.json().catch(() => ({}));
    const action = String((body as any)?.action ?? "status").toLowerCase();
    if (action === "status") {
      return respond({ ok: true, server: SERVER, status: await rpc("penta_marketer_status_v1"), raw_secret_exposed: false });
    }
    if (action === "plan") {
      return respond({ ok: true, server: SERVER, plan: await rpc("penta_marketer_plan_v1"), raw_secret_exposed: false });
    }
    if (action === "schedule") {
      return respond({ ok: true, server: SERVER, scheduler: await rpc("penta_marketer_tick_v1"), raw_secret_exposed: false });
    }
    return respond({ ok: false, error: "unsupported_action", allowed: ["status", "plan", "schedule"], server: SERVER }, 400);
  } catch (error) {
    return respond({ ok: false, service: SERVER.service, error: error instanceof Error ? error.message : String(error), raw_secret_exposed: false }, 500);
  }
});
