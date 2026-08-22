import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const headers = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers });
}

function claims(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")));
  } catch {
    return null;
  }
}

Deno.serve(async (req: Request) => {
  if (req.method !== "GET") return json(405, { error: "method_not_allowed", allowed: ["GET"] });

  const authorization = req.headers.get("authorization") ?? "";
  if (!authorization.toLowerCase().startsWith("bearer ")) return json(401, { error: "authorization_required" });
  const payload = claims(authorization.slice(7).trim());
  const role = String(payload?.role ?? "");
  const subject = String(payload?.sub ?? "");
  if (!(role === "service_role" || (role === "authenticated" && subject.length > 0))) {
    return json(403, { error: "authenticated_principal_required" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) return json(503, { error: "server_configuration_unavailable" });

  const client = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { "x-crownthrive-service": "commercial-release-package-status-v2-alias" } },
  });

  const url = new URL(req.url);
  const sku = (url.searchParams.get("sku") ?? "").trim();
  if (sku && !/^CT-(LAUNCH|READY|PROCURE)-[A-Z0-9-]+$/.test(sku)) return json(400, { error: "invalid_sku" });

  const rpc = sku ? "commercial_release_package_status_v2" : "commercial_release_factory_status_v2";
  const args = sku ? { p_sku: sku } : undefined;
  const { data, error } = await client.rpc(rpc, args);
  if (error) {
    console.error("commercial_release_status_query_failed", { code: error.code });
    return json(503, { error: "status_unavailable", code: error.code });
  }

  return json(200, {
    compatibility_alias: true,
    canonical_service_slug: "commercial-release-factory-status",
    data,
  });
});
