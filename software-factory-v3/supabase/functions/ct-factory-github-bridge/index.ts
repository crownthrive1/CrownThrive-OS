import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5.9.6";
import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(SUPABASE_URL, KEY, { auth: { persistSession: false } });
const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "ct-factory-github";
const REPOSITORY = "crownthrive1/CrownThrive-OS";
const REPOSITORY_ID = "1336348391";
const REPOSITORY_OWNER_ID = "315660018";
const JWKS = createRemoteJWKSet(new globalThis.URL(`${ISSUER}/.well-known/jwks`));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json", "cache-control": "no-store" },
});

async function actor(req: Request) {
  const raw = req.headers.get("authorization") ?? "";
  const token = raw.toLowerCase().startsWith("bearer ") ? raw.slice(7).trim() : "";
  if (!token) throw new Error("oidc_required");
  const { payload } = await jwtVerify(token, JWKS, {
    issuer: ISSUER,
    audience: AUDIENCE,
    algorithms: ["RS256"],
    clockTolerance: 10,
  });
  if (String(payload.repository ?? "") !== REPOSITORY) throw new Error("repository_not_allowed");
  if (String(payload.repository_id ?? "") !== REPOSITORY_ID) throw new Error("repository_id_not_allowed");
  if (String(payload.repository_owner_id ?? "") !== REPOSITORY_OWNER_ID) throw new Error("repository_owner_id_not_allowed");
  const eventName = String(payload.event_name ?? "");
  if (!["schedule", "workflow_dispatch", "push"].includes(eventName)) throw new Error("event_not_allowed");
  return {
    repository: REPOSITORY,
    repository_id: REPOSITORY_ID,
    run_id: String(payload.run_id ?? ""),
    sha: String(payload.sha ?? ""),
    ref: String(payload.ref ?? ""),
    actor: String(payload.actor ?? ""),
    event_name: eventName,
  };
}

Deno.serve(async (req) => {
  let stage = "start";
  try {
    if (req.method !== "POST") return json({ error: "POST required" }, 405);
    stage = "oidc";
    const authenticatedActor = await actor(req);
    stage = "body";
    const payload = await req.json().catch(() => ({}));
    const action = String(payload.action ?? "claim");

    if (action === "claim") {
      stage = "claim_rpc";
      const { data, error } = await db.rpc("ct_factory_claim_provider_job", {
        p_adapter_key: "ct.adapter.github.actions.v1",
      });
      if (error) throw new Error(`claim_rpc:${error.message}`);
      const work = data?.[0];
      if (!work) return json({ ok: true, claimed: false, actor: authenticatedActor });
      stage = "artifact_read";
      const { data: artifacts, error: artifactError } = await db
        .from("ct_factory_artifacts")
        .select("asset_key,sha256,metadata")
        .eq("build_run_id", work.build_run_id)
        .eq("artifact_type", "source_file")
        .order("asset_key");
      if (artifactError) throw new Error(`artifact_read:${artifactError.message}`);
      const files = (artifacts ?? []).map((item: any) => ({
        path: item.asset_key,
        sha256: item.sha256,
        content: String(item.metadata?.content ?? ""),
      }));
      return json({
        ok: true,
        claimed: true,
        job: {
          id: work.job_id,
          build_run_id: work.build_run_id,
          target_id: work.target_id,
          operation: work.operation,
          request: work.request,
        },
        files,
        actor: authenticatedActor,
      });
    }

    if (action === "complete") {
      stage = "complete_validate";
      const jobId = String(payload.job_id ?? "");
      if (!jobId) throw new Error("job_id_required");
      const response = {
        provider: "GitHub",
        repository: REPOSITORY,
        repository_id: REPOSITORY_ID,
        commit_sha: String(payload.commit_sha ?? ""),
        branch: String(payload.branch ?? "main"),
        workflow_run_id: authenticatedActor.run_id,
        event_name: authenticatedActor.event_name,
      };
      const readback = {
        commit_url: String(payload.commit_url ?? ""),
        file_count: Number(payload.file_count ?? 0),
        head_sha: String(payload.head_sha ?? payload.commit_sha ?? ""),
      };
      stage = "complete_rpc";
      const { data, error } = await db.rpc("ct_factory_provider_job_implemented", {
        p_job_id: jobId,
        p_response: response,
        p_readback: readback,
        p_rollback_ref: String(payload.rollback_ref ?? ""),
      });
      if (error) throw new Error(`complete_rpc:${error.message}`);
      await db
        .from("ct_factory_provider_adapters")
        .update({ verification_state: "verified", last_verified_at: new Date().toISOString(), updated_at: new Date().toISOString() })
        .eq("adapter_key", "ct.adapter.github.actions.v1");
      return json({ ok: true, result: data, actor: authenticatedActor });
    }

    return json({ error: "unsupported_action" }, 400);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const status = message.includes("oidc") || message.includes("JWT")
      ? 401
      : message.includes("not_allowed")
      ? 403
      : 500;
    return json({ ok: false, error: message, stage }, status);
  }
});
