import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function env(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`missing runtime secret: ${name}`);
  return value;
}

function requireServiceRole(req: Request): void {
  const expected = `Bearer ${env("SUPABASE_SERVICE_ROLE_KEY")}`;
  const supplied = req.headers.get("authorization") ?? "";
  if (supplied.length !== expected.length) throw new Error("unauthorized");
  let diff = 0;
  for (let i = 0; i < supplied.length; i++) diff |= supplied.charCodeAt(i) ^ expected.charCodeAt(i);
  if (diff !== 0) throw new Error("unauthorized");
}

async function rpc(name: string, args: Record<string, unknown>): Promise<Response> {
  const supabaseUrl = env("SUPABASE_URL");
  const serviceRole = env("SUPABASE_SERVICE_ROLE_KEY");
  return await fetch(`${supabaseUrl}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "apikey": serviceRole,
      "authorization": `Bearer ${serviceRole}`,
      "x-client-info": "penta-context-edge/1.0.0",
    },
    body: JSON.stringify(args),
  });
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return reply(405, { error: "method_not_allowed" });
    requireServiceRole(req);

    const body = await req.json().catch(() => null) as Record<string, unknown> | null;
    if (!body || typeof body.action !== "string") return reply(400, { error: "invalid_request" });

    let upstream: Response;
    switch (body.action) {
      case "health":
        upstream = await rpc("penta_context_health_v1", {});
        break;
      case "query": {
        if (typeof body.scope_key !== "string" || body.scope_key.trim().length < 2) {
          return reply(400, { error: "invalid_scope_key" });
        }
        upstream = await rpc("penta_context_query_v1", {
          p_scope_key: body.scope_key,
          p_query: typeof body.query === "string" ? body.query : "",
          p_limit: Number.isInteger(body.limit) ? body.limit : 8,
          p_max_chars: Number.isInteger(body.max_chars) ? body.max_chars : 12000,
          p_tags: Array.isArray(body.tags) ? body.tags : null,
          p_classification_ceiling: typeof body.classification_ceiling === "string" ? body.classification_ceiling : "internal",
          p_actor_ref: typeof body.actor_ref === "string" ? body.actor_ref : "penta.context.edge",
        });
        break;
      }
      case "ingest": {
        for (const key of ["scope_key", "source_type", "source_ref", "content"] as const) {
          if (typeof body[key] !== "string" || (body[key] as string).trim().length === 0) {
            return reply(400, { error: `invalid_${key}` });
          }
        }
        upstream = await rpc("penta_context_ingest_v1", {
          p_scope_key: body.scope_key,
          p_source_type: body.source_type,
          p_source_ref: body.source_ref,
          p_content: body.content,
          p_title: typeof body.title === "string" ? body.title : null,
          p_summary: typeof body.summary === "string" ? body.summary : null,
          p_tags: Array.isArray(body.tags) ? body.tags : [],
          p_metadata: body.metadata && typeof body.metadata === "object" ? body.metadata : {},
          p_classification: typeof body.classification === "string" ? body.classification : "internal",
          p_importance: typeof body.importance === "number" ? body.importance : 0.5,
          p_confidence: typeof body.confidence === "number" ? body.confidence : 0.7,
          p_observed_at: typeof body.observed_at === "string" ? body.observed_at : new Date().toISOString(),
          p_expires_at: typeof body.expires_at === "string" ? body.expires_at : null,
          p_actor_ref: typeof body.actor_ref === "string" ? body.actor_ref : "penta.context.edge",
        });
        break;
      }
      default:
        return reply(400, { error: "unsupported_action", allowed: ["health", "query", "ingest"] });
    }

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { ...JSON_HEADERS, "x-penta-context-version": "1.0.0" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "runtime_error";
    if (message === "unauthorized") return reply(401, { error: "unauthorized" });
    console.error("penta-context edge failure", message);
    return reply(500, { error: "internal_error" });
  }
});
