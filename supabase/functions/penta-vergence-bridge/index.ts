import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5.9.6";
import { createClient } from "npm:@supabase/supabase-js@2";

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "penta-vergence";
const ALLOWED_REPOS = new Set(["crownthrive1/CrownThrive-OS", "crownthrive1/CrownThrive-CIE", "crownthrive1/chlom-protocol"]);
const CANONICAL_OS_REPOSITORY_ID = "1336348391";
const CANONICAL_OWNER_ID = "315660018";
const ALLOWED_EVENTS = new Set(["schedule", "workflow_dispatch", "push", "workflow_run"]);
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const SERVER = { name: "PentaVergence", version: "1.0.1", contract: "ct.penta.vergence.bridge.v1" };
const j = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

async function actor(req: Request) {
  const raw = req.headers.get("authorization") ?? "";
  const token = raw.toLowerCase().startsWith("bearer ") ? raw.slice(7).trim() : "";
  if (!token) throw new Error("oidc_required");
  const { payload } = await jwtVerify(token, JWKS, { issuer: ISSUER, audience: AUDIENCE, algorithms: ["RS256"], clockTolerance: 10 });
  const repository = String(payload.repository ?? "");
  const repositoryId = String(payload.repository_id ?? "");
  const repositoryOwnerId = String(payload.repository_owner_id ?? "");
  const eventName = String(payload.event_name ?? "");
  if (!ALLOWED_REPOS.has(repository)) throw new Error("repository_not_allowed");
  if (repository === "crownthrive1/CrownThrive-OS" && (repositoryId !== CANONICAL_OS_REPOSITORY_ID || repositoryOwnerId !== CANONICAL_OWNER_ID)) {
    throw new Error("canonical_os_repository_identity_not_allowed");
  }
  if (!ALLOWED_EVENTS.has(eventName)) throw new Error("event_not_allowed");
  return {
    repository,
    repository_id: repositoryId,
    repository_owner_id: repositoryOwnerId,
    event_name: eventName,
    run_id: String(payload.run_id ?? ""),
    sha: String(payload.sha ?? ""),
    ref: String(payload.ref ?? ""),
    actor: String(payload.actor ?? ""),
  };
}

Deno.serve(async (req: Request) => {
  let stage = "start";
  try {
    if (req.method !== "POST") return j({ error: "POST required", server: SERVER }, 405);
    stage = "oidc";
    const a = await actor(req);
    stage = "body";
    const body = await req.json().catch(() => ({}));
    const action = String(body.action ?? "claim");
    if (action === "claim") {
      const { data, error } = await db.schema("penta_runtime").rpc("penta_vergence_claim_v1", { p_repository: a.repository, p_worker_run_id: a.run_id });
      if (error) throw new Error(`claim:${error.message}`);
      return j({ ok: true, server: SERVER, actor: a, job: data });
    }
    if (action === "complete") {
      const jobId = String(body.job_id ?? "");
      if (!jobId) throw new Error("job_id_required");
      const report = body.report ?? {};
      if (String(report.repository ?? "") !== a.repository) throw new Error("report_repository_mismatch");
      const { data, error } = await db.schema("penta_runtime").rpc("penta_vergence_complete_v1", { p_job_id: jobId, p_report: report, p_evidence_sha256: body.evidence_sha256 ? String(body.evidence_sha256) : null });
      if (error) throw new Error(`complete:${error.message}`);
      return j({ ok: true, server: SERVER, actor: a, result: data });
    }
    if (action === "release") {
      const jobId = String(body.job_id ?? "");
      if (!jobId) throw new Error("job_id_required");
      const { data, error } = await db.schema("penta_runtime").rpc("penta_vergence_release_v1", { p_job_id: jobId, p_error: String(body.error ?? "worker_failed").slice(0, 1000) });
      if (error) throw new Error(`release:${error.message}`);
      return j({ ok: true, server: SERVER, actor: a, result: data });
    }
    return j({ error: "unsupported_action", server: SERVER }, 400);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    const status = message.includes("oidc") || message.includes("JWT") ? 401 : message.includes("not_allowed") || message.includes("mismatch") ? 403 : 500;
    return j({ ok: false, error: message, stage, server: SERVER }, status);
  }
});
