import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const VERSION = "1.0.0";
const MAX_BODY_BYTES = 256_000;
const MAX_FETCH_BYTES = 1_000_000;
const ALLOWED_FETCH_PROTOCOL = "https:";
const BLOCKED_HOST_SUFFIXES = [".local", ".internal", ".localhost"];
const BLOCKED_EXACT_HOSTS = new Set(["localhost", "0.0.0.0", "127.0.0.1", "::1", "metadata.google.internal"]);

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("INVALID_JWT_SHAPE");
  const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(parts[1].length / 4) * 4, "=");
  return JSON.parse(atob(normalized));
}

function assertServiceRole(req: Request) {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) throw new Error("AUTH_REQUIRED");
  const payload = decodeJwtPayload(auth.slice(7));
  if (payload.role !== "service_role") throw new Error("SERVICE_ROLE_REQUIRED");
}

function isPrivateIpv4(host: string) {
  const m = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return false;
  const [a, b, c, d] = m.slice(1).map(Number);
  if ([a, b, c, d].some((n) => n < 0 || n > 255)) return true;
  return a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);
}

function assertPublicHttps(raw: string) {
  const u = new URL(raw);
  const host = u.hostname.toLowerCase().replace(/\.$/, "");
  if (u.protocol !== ALLOWED_FETCH_PROTOCOL) throw new Error("HTTPS_REQUIRED");
  if (u.username || u.password) throw new Error("URL_CREDENTIALS_FORBIDDEN");
  if (BLOCKED_EXACT_HOSTS.has(host) || BLOCKED_HOST_SUFFIXES.some((s) => host.endsWith(s)) || isPrivateIpv4(host)) throw new Error("PRIVATE_DESTINATION_FORBIDDEN");
  if (host.includes(":")) throw new Error("IPV6_LITERAL_FORBIDDEN");
  return u;
}

async function sha256Text(value: string) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function boundedFetch(raw: string) {
  let url = assertPublicHttps(raw);
  for (let hop = 0; hop < 3; hop++) {
    const res = await fetch(url, { method: "GET", redirect: "manual", headers: { "user-agent": "CrownThrive-PentaDiscovery/1.0" } });
    if ([301, 302, 303, 307, 308].includes(res.status)) {
      const location = res.headers.get("location");
      if (!location) throw new Error("REDIRECT_WITHOUT_LOCATION");
      url = assertPublicHttps(new URL(location, url).toString());
      continue;
    }
    const reader = res.body?.getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    if (reader) {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (value) {
          total += value.byteLength;
          if (total > MAX_FETCH_BYTES) {
            await reader.cancel();
            throw new Error("FETCH_BODY_LIMIT_EXCEEDED");
          }
          chunks.push(value);
        }
      }
    }
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) { merged.set(chunk, offset); offset += chunk.byteLength; }
    const contentType = res.headers.get("content-type") || "application/octet-stream";
    const text = contentType.includes("text") || contentType.includes("json") || contentType.includes("xml") ? new TextDecoder().decode(merged) : null;
    return { url: url.toString(), status: res.status, content_type: contentType, bytes: total, sha256: await sha256Text(new TextDecoder().decode(merged)), text };
  }
  throw new Error("REDIRECT_LIMIT_EXCEEDED");
}

Deno.serve(async (req) => {
  const traceId = crypto.randomUUID();
  try {
    if (req.method !== "POST") return json(405, { ok: false, error: "METHOD_NOT_ALLOWED", trace_id: traceId });
    assertServiceRole(req);
    const len = Number(req.headers.get("content-length") || 0);
    if (len > MAX_BODY_BYTES) return json(413, { ok: false, error: "REQUEST_TOO_LARGE", trace_id: traceId });
    const body = await req.json();
    const action = String(body?.action || "health");
    const url = Deno.env.get("SUPABASE_URL");
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!url || !serviceKey) throw new Error("RUNTIME_BINDING_MISSING");
    const sb = createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });

    if (action === "health") {
      const { data, error } = await sb.from("penta_system_registry").select("system_key,maturity,version,last_verified_at").eq("system_key", "penta.discovery").single();
      if (error) throw error;
      return json(200, { ok: true, service: "PentaDiscovery", version: VERSION, production: data?.maturity === "production", registry: data, trace_id: traceId });
    }

    if (action === "observe") {
      const p = body?.input || {};
      const { data, error } = await sb.schema("penta_discovery").rpc("intake_v1", {
        p_source_ref: String(p.source_ref || ""), p_source_kind: String(p.source_kind || "unknown"), p_observed_subject: String(p.subject || ""),
        p_observation: p.observation ?? {}, p_confidence: Number(p.confidence ?? 0.5), p_receiver_penta_ref: String(p.receiver || "PentaCensus"),
        p_objective: String(p.objective || "classify and register discovery"), p_route_class: String(p.route_class || "local_internal"),
      });
      if (error) throw error;
      return json(200, { ok: true, result: data, trace_id: traceId });
    }

    if (action === "search") {
      const q = String(body?.input?.q || "").trim();
      if (!q) return json(400, { ok: false, error: "QUERY_REQUIRED", trace_id: traceId });
      const safe = q.replace(/[%_]/g, "\\$&").slice(0, 120);
      const { data, error } = await sb.from("penta_system_registry").select("system_key,canonical_name,category,purpose,maturity,version,last_verified_at").or(`canonical_name.ilike.%${safe}%,purpose.ilike.%${safe}%`).limit(50);
      if (error) throw error;
      return json(200, { ok: true, family_member: "PentaSearch", results: data, trace_id: traceId });
    }

    if (action === "get") {
      const key = String(body?.input?.system_key || "");
      const { data, error } = await sb.from("penta_system_registry").select("*").eq("system_key", key).maybeSingle();
      if (error) throw error;
      return json(200, { ok: true, family_member: "PentaGet", result: data, trace_id: traceId });
    }

    if (action === "query") {
      const surface = String(body?.input?.surface || "systems");
      const surfaces: Record<string, { schema?: string; table: string; select: string }> = {
        systems: { table: "penta_system_registry", select: "system_key,canonical_name,category,purpose,maturity,version,last_verified_at" },
        family: { schema: "penta_discovery", table: "family_registry_v1", select: "member_key,canonical_name,family_role,execution_role,lifecycle_state,packet_contract,fabric_contract" },
        rates: { schema: "penta_runtime", table: "penta_route_rate_policy_v1", select: "rate_key,route_class,base_internal_units,per_hop_internal_units,per_kib_internal_units,governance_state,effective_at,expires_at" },
        pay_policies: { schema: "penta_runtime", table: "penta_pay_route_compensation_policy_v1", select: "policy_key,route_class,compensation_minor_per_1000_metered_units,currency,governance_state,effective_at,expires_at" },
        receipts: { schema: "penta_runtime", table: "penta_route_receipts_v1", select: "receipt_id,packet_id,sender_penta_ref,receiver_penta_ref,route_class,actual_internal_units,provider_cost_minor,pay_amount_minor,currency,settlement_state,provider_money_movement,created_at" },
      };
      const def = surfaces[surface];
      if (!def) return json(400, { ok: false, error: "SURFACE_NOT_ALLOWED", trace_id: traceId });
      const client = def.schema ? sb.schema(def.schema) : sb;
      const { data, error } = await client.from(def.table).select(def.select).limit(Math.min(100, Math.max(1, Number(body?.input?.limit || 25))));
      if (error) throw error;
      return json(200, { ok: true, family_member: "PentaQuery", surface, results: data, trace_id: traceId });
    }

    if (action === "resolve") {
      const input = body?.input || {};
      let query = sb.schema("penta_discovery").from("entities_v1").select("*");
      if (input.entity_key) query = query.eq("entity_key", String(input.entity_key));
      else if (input.fingerprint_sha256) query = query.eq("fingerprint_sha256", String(input.fingerprint_sha256));
      else return json(400, { ok: false, error: "ENTITY_KEY_OR_FINGERPRINT_REQUIRED", trace_id: traceId });
      const { data, error } = await query.limit(10);
      if (error) throw error;
      return json(200, { ok: true, family_member: "PentaResolve", results: data, trace_id: traceId });
    }

    if (action === "parse") {
      const raw = body?.input?.value;
      const normalized = typeof raw === "string" ? raw.replace(/\s+/g, " ").trim() : JSON.parse(JSON.stringify(raw ?? null));
      return json(200, { ok: true, family_member: "PentaParse", normalized, fingerprint_sha256: await sha256Text(JSON.stringify(normalized)), trace_id: traceId });
    }

    if (action === "fetch") {
      const raw = String(body?.input?.url || "");
      if (!raw) return json(400, { ok: false, error: "URL_REQUIRED", trace_id: traceId });
      const result = await boundedFetch(raw);
      return json(200, { ok: true, family_member: "PentaFetch", result, trace_id: traceId });
    }

    if (action === "reserve") {
      const { data, error } = await sb.schema("penta_runtime").rpc("reserve_penta_route_v1", { p_quote_id: String(body?.input?.quote_id || ""), p_authority_evidence: body?.input?.authority_evidence ?? {} });
      if (error) throw error;
      return json(200, { ok: true, result: data, trace_id: traceId });
    }

    if (action === "usage") {
      const p = body?.input || {};
      const { data, error } = await sb.schema("penta_runtime").rpc("record_penta_route_usage_v1", {
        p_reservation_id: String(p.reservation_id || ""), p_hop_no: Number(p.hop_no || 0), p_route_edge_ref: String(p.route_edge_ref || ""),
        p_disposition: String(p.disposition || "delivered"), p_actual_internal_units: Number(p.actual_internal_units || 0), p_actual_provider_cost_minor: Number(p.actual_provider_cost_minor || 0),
        p_currency: String(p.currency || "USD"), p_metadata: p.metadata ?? {},
      });
      if (error) throw error;
      return json(200, { ok: true, result: data, trace_id: traceId });
    }

    if (action === "reconcile") {
      const p = body?.input || {};
      const { data, error } = await sb.schema("penta_runtime").rpc("reconcile_penta_route_v1", {
        p_reservation_id: String(p.reservation_id || ""), p_beneficiary_ref: String(p.beneficiary_ref || "PentaFabric"), p_pay_rate_minor_per_1000_units: null,
        p_chlom_authority_ref: p.chlom_authority_ref ?? null, p_dail_evidence_ref: p.dail_evidence_ref ?? null,
      });
      if (error) throw error;
      return json(200, { ok: true, result: data, trace_id: traceId });
    }

    return json(400, { ok: false, error: "ACTION_NOT_ALLOWED", allowed: ["health","observe","search","get","query","resolve","parse","fetch","reserve","usage","reconcile"], trace_id: traceId });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const status = message === "AUTH_REQUIRED" || message === "SERVICE_ROLE_REQUIRED" ? 403 : 500;
    return json(status, { ok: false, error: message.slice(0, 500), service: "PentaDiscovery", version: VERSION, trace_id: traceId });
  }
});
