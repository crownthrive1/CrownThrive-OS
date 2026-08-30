import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.1.0";
import { createClient } from "npm:@supabase/supabase-js@2.57.4";

const TEAM_SLUG = "crownthrive-os";
const TEAM_ID = "team_v4xkGtBZSrZXnJtLEJhra5nd";
const PROJECT_NAME = "crownthrive-os";
const PROJECT_ID = "prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN";
const EXPECTED_AUDIENCE = `https://vercel.com/${TEAM_SLUG}`;
const ALLOWED_ISSUERS = [
  `https://oidc.vercel.com/${TEAM_SLUG}`,
  "https://oidc.vercel.com",
];
const JWKS = createRemoteJWKSet(new URL("https://oidc.vercel.com/.well-known/jwks"));

const PENTA_EVENT_CONTRACT = "crownthrive.penta.event.v1";
const PENTAFABRIC_SCHEMA = "crownthrive.pentafabric.v1";
const CHLOM_BINDING = "crownthrive.chlom.pentafabric.v1";
const SUPABASE_PROJECT_ORIGIN = "https://tzajnzshmtzjenqulehq.supabase.co";
const PROHIBITED_KEYS = new Set(["__proto__", "constructor", "prototype"]);

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store, max-age=0",
      "X-PentaFabric-Version": "1.0.0",
    },
  });
}

function stable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === "object") {
    const source = value as Record<string, unknown>;
    const result = Object.create(null) as Record<string, unknown>;
    for (const key of Object.keys(source).sort()) {
      if (PROHIBITED_KEYS.has(key)) throw new Error(`Penta contains prohibited object key: ${key}`);
      result[key] = stable(source[key]);
    }
    return result;
  }
  return value;
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function hmacSha256Hex(secret: string, bytes: Uint8Array): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, bytes);
  return Array.from(new Uint8Array(signature), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
}

async function verifyWorkload(req: Request) {
  const authorization = req.headers.get("authorization") || "";
  const token = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
  if (!token) throw new Error("missing Vercel OIDC bearer token");

  const { payload } = await jwtVerify(token, JWKS, {
    issuer: ALLOWED_ISSUERS,
    audience: EXPECTED_AUDIENCE,
    algorithms: ["RS256"],
  });

  if (payload.owner_id !== TEAM_ID) throw new Error("Vercel owner_id mismatch");
  if (payload.project_id !== PROJECT_ID) throw new Error("Vercel project_id mismatch");
  if (payload.project !== PROJECT_NAME) throw new Error("Vercel project mismatch");
  if (payload.environment !== "production") throw new Error("Vercel environment must be production");

  return {
    issuer: payload.iss,
    subject: payload.sub,
    project_id: payload.project_id,
    owner_id: payload.owner_id,
    environment: payload.environment,
  };
}

async function verifyPenta(event: Record<string, unknown>) {
  if (!event || typeof event !== "object" || Array.isArray(event)) throw new Error("Penta must be an object");
  if (event.specversion !== "1.0") throw new Error("Penta specversion mismatch");
  if (!String(event.id || "").startsWith("penta_")) throw new Error("Penta id invalid");
  if (!String(event.type || "").startsWith("penta.")) throw new Error("Penta type invalid");
  if (event.datacontenttype !== "application/json") throw new Error("Penta datacontenttype mismatch");

  const mesh = event.mesh as Record<string, unknown> | undefined;
  const fabric = mesh?.fabric as Record<string, unknown> | undefined;
  const chlom = mesh?.chlom as Record<string, unknown> | undefined;
  const trace = event.trace as Record<string, unknown> | undefined;
  const data = event.data as Record<string, unknown> | undefined;
  const integrity = event.integrity as Record<string, unknown> | undefined;

  if (mesh?.contract !== PENTA_EVENT_CONTRACT || mesh?.family !== "PentaFamily") throw new Error("Penta event contract mismatch");
  if (fabric?.schema !== PENTAFABRIC_SCHEMA || fabric?.version !== "1.0.0") throw new Error("PentaFabric schema/version mismatch");
  if (chlom?.binding !== CHLOM_BINDING || chlom?.governed !== true || !String(chlom?.intent_id || "")) throw new Error("CHLOM binding invalid");
  if (!["DELIVERED", "ADMITTED", "ACKED"].includes(String(data?.status || ""))) throw new Error("Penta delivery status invalid");
  const expiresAt = Date.parse(String(fabric?.expires_at || ""));
  if (!Number.isFinite(expiresAt) || Date.now() > expiresAt) throw new Error("Penta expired");

  const algorithm = String(integrity?.algorithm || "");
  const keyId = String(integrity?.key_id || "");
  if (algorithm !== "HMAC-SHA256") throw new Error("Penta edge ingest requires HMAC-SHA256");
  if (keyId !== "pentafabric-v1") throw new Error("Penta HMAC key_id invalid");
  const packetBuildSha = integrity?.build_sha;
  if (packetBuildSha !== null && !/^[a-f0-9]{40}$/.test(String(packetBuildSha || ""))) throw new Error("Penta build_sha invalid");
  const { digest: _digest, signature: _signature, ...signedIntegrity } = integrity || {};
  const canonical = new TextEncoder().encode(JSON.stringify(stable({
    ...event,
    integrity: signedIntegrity,
  })));
  const expectedDigest = await sha256Hex(canonical);
  const suppliedDigest = String(integrity?.digest || "");
  if (!/^[a-f0-9]{64}$/.test(suppliedDigest) || !safeEqual(suppliedDigest, expectedDigest)) throw new Error("Penta digest mismatch");
  const signingSecret = Deno.env.get("PENTAFABRIC_SIGNING_SECRET") || "";
  if (new TextEncoder().encode(signingSecret).byteLength < 32) throw new Error("PentaFabric signing secret unavailable");
  const suppliedSignature = String(integrity?.signature || "");
  const expectedSignature = await hmacSha256Hex(signingSecret, canonical);
  if (!/^[a-f0-9]{64}$/.test(suppliedSignature) || !safeEqual(suppliedSignature, expectedSignature)) {
    throw new Error("Penta HMAC signature mismatch");
  }

  const lane = String(fabric?.lane || "");
  if (!["hot", "cold"].includes(lane)) throw new Error("Penta lane invalid");
  if (!String(trace?.trace_id || "")) throw new Error("Penta trace_id required");

  return {
    penta_id: String(event.id),
    trace_id: String(trace?.trace_id),
    protocol: String(fabric?.protocol || data?.protocol || ""),
    lane,
    route: String(fabric?.route || ""),
    chlom_intent_id: String(chlom?.intent_id),
    chlom_binding: String(chlom?.binding),
    event_contract: String(mesh?.contract),
    fabric_schema: String(fabric?.schema),
    integrity_algorithm: algorithm,
    integrity_digest: suppliedDigest,
    build_sha: packetBuildSha === null ? null : String(packetBuildSha),
    event,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "GET") {
    return json(200, {
      schema: "ct.penta.supabase.ingest.20260827.v1",
      status: "OPERATIONAL",
      auth: "VERCEL_OIDC_RS256",
      expected_project_id: PROJECT_ID,
      event_contract: PENTA_EVENT_CONTRACT,
      fabric_schema: PENTAFABRIC_SCHEMA,
      chlom_binding: CHLOM_BINDING,
      event_signature_required: "HMAC-SHA256",
    });
  }
  if (req.method !== "POST") return json(405, { status: "REJECTED", error: "method_not_allowed" });

  let workload;
  try {
    workload = await verifyWorkload(req);
  } catch {
    return json(401, {
      status: "REJECTED",
      error: "pentafabric_workload_authorization_failed",
    });
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json() as Record<string, unknown>;
  } catch {
    return json(400, {
      status: "REJECTED",
      error: "pentafabric_request_body_invalid",
    });
  }

  let row;
  try {
    const penta = (body?.penta || body) as Record<string, unknown>;
    row = await verifyPenta(penta);
  } catch (error) {
    return json(400, {
      status: "REJECTED",
      error: "pentafabric_contract_failure",
      detail: String((error as Error)?.message || error).slice(0, 240),
    });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!supabaseUrl || !serviceRole) throw new Error("Supabase server-side credentials unavailable");
    if (supabaseUrl !== SUPABASE_PROJECT_ORIGIN && supabaseUrl !== `${SUPABASE_PROJECT_ORIGIN}/`) {
      throw new Error("Supabase project origin mismatch");
    }

    const client = createClient(SUPABASE_PROJECT_ORIGIN, serviceRole, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const { error } = await client.from("pentafabric_events").upsert(row, {
      onConflict: "penta_id",
      ignoreDuplicates: true,
    });
    if (error) throw new Error(`evidence insert failed: ${error.message}`);
    const { data: stored, error: readbackError } = await client
      .from("pentafabric_events")
      .select("penta_id,trace_id,integrity_digest,build_sha,event")
      .eq("penta_id", row.penta_id)
      .maybeSingle();
    if (readbackError) throw new Error(`evidence readback failed: ${readbackError.message}`);
    const exactReadback =
      stored?.penta_id === row.penta_id &&
      stored?.trace_id === row.trace_id &&
      stored?.integrity_digest === row.integrity_digest &&
      stored?.build_sha === row.build_sha &&
      JSON.stringify(stable(stored?.event)) === JSON.stringify(stable(row.event));
    if (!exactReadback) throw new Error("evidence exact readback mismatch");

    return json(202, {
      schema: "ct.penta.supabase.receipt.20260827.v1",
      status: "PERSISTED_READBACK_VERIFIED",
      penta_id: row.penta_id,
      trace_id: row.trace_id,
      integrity_digest: row.integrity_digest,
      signing_build_sha: row.build_sha,
      exact_readback: true,
      protocol: row.protocol,
      provider: "supabase-edge",
      authentication: "VERCEL_OIDC_RS256",
      workload,
      persisted_at: new Date().toISOString(),
    });
  } catch {
    return json(503, {
      status: "DELIVERY_HOLD",
      error: "pentafabric_evidence_sink_failure",
      pass_manufactured: false,
    });
  }
});
