import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, x-client-info, apikey, content-type",
  "access-control-allow-methods": "GET, OPTIONS",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "GET") return jsonResponse({ error: "method_not_allowed" }, 405);

  const authorization = req.headers.get("authorization") ?? "";
  if (!authorization.toLowerCase().startsWith("bearer ")) {
    return jsonResponse({ error: "authorization_required" }, 401);
  }
  const token = authorization.slice(7).trim();
  const claims = decodeJwtPayload(token);
  const role = String(claims?.role ?? "");
  const subject = String(claims?.sub ?? "");
  const authorizedRole = role === "service_role" || (role === "authenticated" && subject.length > 0);
  if (!authorizedRole) {
    return jsonResponse({ error: "authenticated_principal_required" }, 403);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return jsonResponse({ error: "runtime_configuration_unavailable" }, 503);
  }

  const admin = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { "x-crownthrive-service": "commercial-release-factory-status-v2" } },
  });

  const url = new URL(req.url);
  const sku = (url.searchParams.get("sku") ?? "").trim();
  if (sku && !/^CT-(LAUNCH|READY|PROCURE)-[A-Z0-9-]+$/.test(sku)) {
    return jsonResponse({ error: "invalid_sku" }, 400);
  }

  const rpcName = sku ? "commercial_release_package_status_v2" : "commercial_release_factory_status_v2";
  const rpcArgs = sku ? { p_sku: sku } : undefined;
  const { data, error } = await admin.rpc(rpcName, rpcArgs);
  if (error) {
    console.error("commercial_release_factory_status_query_failed", { code: error.code });
    return jsonResponse({ error: "status_unavailable", code: error.code }, 503);
  }
  return jsonResponse(data);
});
