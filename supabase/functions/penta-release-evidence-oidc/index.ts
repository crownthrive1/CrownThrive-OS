import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "postgres";
import { createRemoteJWKSet, jwtVerify } from "jose";

const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "crownthrive-pentarelease";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const REPOSITORY = "crownthrive1/CrownThrive-OS";
const REPOSITORY_ID = "1336348391";
const REPOSITORY_OWNER = "crownthrive1";
const REPOSITORY_OWNER_ID = "315660018";
const REF = "refs/heads/main";
const ALLOWED_WORKFLOWS = new Set([
  `${REPOSITORY}/.github/workflows/pentarelease-autonomous-awareness.yml@${REF}`,
  `${REPOSITORY}/.github/workflows/pentarelease-economic-cie-convergence.yml@${REF}`,
  `${REPOSITORY}/.github/workflows/pentarelease-release-intelligence-v3.yml@${REF}`,
]);
const ALLOWED_EVENTS = new Set(["push", "schedule", "workflow_dispatch", "workflow_run"]);
const IMMUTABLE_SUB = `repo:${REPOSITORY_OWNER}@${REPOSITORY_OWNER_ID}/CrownThrive-OS@${REPOSITORY_ID}:ref:${REF}`;
const LEGACY_SUB = `repo:${REPOSITORY}:ref:${REF}`;

let pg: ReturnType<typeof postgres> | null = null;
function db() {
  const url = Deno.env.get("SUPABASE_DB_URL") ?? "";
  if (!url) throw new Error("database_unavailable");
  pg ??= postgres(url, { max: 2, idle_timeout: 10, prepare: false });
  return pg;
}
function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}
function claim(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

type FailureStage =
  | "authorization"
  | "oidc_verification"
  | "request_validation"
  | "database_connect"
  | "resolve_release_evidence_bundle"
  | "enqueue_release_projection"
  | "dispatch_release_footer";

type DiagnosticCode =
  | "github_oidc_bearer_required"
  | "github_oidc_verification_failed"
  | "method_not_allowed"
  | "request_body_invalid"
  | "request_validation_rejected"
  | "database_unavailable"
  | "database_connection_failed"
  | "database_unique_conflict"
  | "database_foreign_key_conflict"
  | "database_constraint_rejected"
  | "database_permission_denied"
  | "database_contract_missing"
  | "database_timeout_or_lock"
  | "database_serialization_conflict"
  | "database_value_rejected"
  | "database_capacity_exhausted"
  | "database_application_exception"
  | "database_provider_error";

function safeDiagnosticCode(error: unknown): DiagnosticCode {
  const message = error instanceof Error ? error.message : "";
  if (message === "database_unavailable") return "database_unavailable";
  if (message === "request_body_invalid" || error instanceof SyntaxError) return "request_body_invalid";
  if (message.startsWith("oidc_") || message.includes("JWT") || message.includes("signature") || message.includes("audience") || message.includes("issuer")) {
    return "github_oidc_verification_failed";
  }
  if (["release_version_invalid", "release_tag_mismatch", "pr_number_invalid", "payload_bytes_invalid"].includes(message)) {
    return "request_validation_rejected";
  }
  const candidateCode = typeof error === "object" && error !== null
    ? (error as { code?: unknown }).code
    : undefined;
  const sqlState = typeof candidateCode === "string" ? candidateCode : "";
  switch (sqlState) {
    case "23505": return "database_unique_conflict";
    case "23503": return "database_foreign_key_conflict";
    case "23514":
    case "23502": return "database_constraint_rejected";
    case "42501": return "database_permission_denied";
    case "42883":
    case "42P01":
    case "3F000": return "database_contract_missing";
    case "57014":
    case "55P03": return "database_timeout_or_lock";
    case "40001": return "database_serialization_conflict";
    case "22P02":
    case "22003": return "database_value_rejected";
    case "53300": return "database_capacity_exhausted";
    case "08000":
    case "08001":
    case "08003":
    case "08006":
    case "57P03": return "database_connection_failed";
    case "P0001": return "database_application_exception";
    default: return "database_provider_error";
  }
}

async function verifyGitHubOidc(token: string) {
  const { payload } = await jwtVerify(token, JWKS, {
    issuer: ISSUER,
    audience: AUDIENCE,
    algorithms: ["RS256"],
    clockTolerance: 30,
  });
  const c = payload as Record<string, unknown>;
  if (claim(c, "repository") !== REPOSITORY || claim(c, "repository_id") !== REPOSITORY_ID) throw new Error("oidc_repository_invalid");
  if (claim(c, "repository_owner") !== REPOSITORY_OWNER || claim(c, "repository_owner_id") !== REPOSITORY_OWNER_ID) throw new Error("oidc_owner_invalid");
  if (claim(c, "repository_visibility") !== "public") throw new Error("oidc_visibility_invalid");
  if (claim(c, "ref") !== REF || claim(c, "ref_type") !== "branch") throw new Error("oidc_ref_invalid");
  if (!ALLOWED_WORKFLOWS.has(claim(c, "workflow_ref"))) throw new Error("oidc_workflow_ref_invalid");
  if (!ALLOWED_EVENTS.has(claim(c, "event_name"))) throw new Error("oidc_event_invalid");
  if (claim(c, "runner_environment") !== "github-hosted") throw new Error("oidc_runner_invalid");
  const sub = claim(c, "sub");
  if (sub !== IMMUTABLE_SUB && sub !== LEGACY_SUB) throw new Error("oidc_subject_invalid");
  if (!/^\d+$/.test(claim(c, "run_id")) || !/^\d+$/.test(claim(c, "run_attempt"))) throw new Error("oidc_run_invalid");
  if (!/^[0-9a-f]{40}$/i.test(claim(c, "workflow_sha"))) throw new Error("oidc_workflow_sha_invalid");
  return c;
}

Deno.serve(async (req: Request) => {
  if (req.method === "GET") return json({ service: "ct.pentarelease.evidence-oidc.v1", production: true, audience: AUDIENCE, repository: REPOSITORY, raw_token_persisted: false });
  if (req.method !== "POST") return json({ error: "method_not_allowed", diagnostic_version: 1, diagnostic_stage: "request_validation", diagnostic_code: "method_not_allowed", raw_token_persisted: false }, 405);
  const auth = req.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!token) return json({ error: "github_oidc_bearer_required", diagnostic_version: 1, diagnostic_stage: "authorization", diagnostic_code: "github_oidc_bearer_required", raw_token_persisted: false }, 401);
  let failureStage: FailureStage = "oidc_verification";
  try {
    const claims = await verifyGitHubOidc(token);
    failureStage = "request_validation";
    const rawBody: unknown = await req.json();
    if (!rawBody || typeof rawBody !== "object" || Array.isArray(rawBody)) {
      throw new Error("request_body_invalid");
    }
    const body = rawBody as Record<string, unknown>;
    const releaseVersion = String(body.release_version ?? "").trim();
    const releaseTag = String(body.release_tag ?? "").trim();
    if (typeof body.pr_number === "boolean") throw new Error("pr_number_invalid");
    const prNumber = body.pr_number == null || body.pr_number === "" ? null : Number(body.pr_number);
    if (typeof body.payload_bytes === "boolean") throw new Error("payload_bytes_invalid");
    const payloadBytes = Number(body.payload_bytes ?? 0);
    const cieSubject = body.cie_subject && typeof body.cie_subject === "object" && !Array.isArray(body.cie_subject)
      ? body.cie_subject as Record<string, unknown>
      : null;
    if (!/^\d+\.\d+\.\d+\.\d+$/.test(releaseVersion)) throw new Error("release_version_invalid");
    if (releaseTag !== `v${releaseVersion}`) throw new Error("release_tag_mismatch");
    if (prNumber !== null && (!Number.isSafeInteger(prNumber) || prNumber <= 0)) throw new Error("pr_number_invalid");
    if (!Number.isSafeInteger(payloadBytes) || payloadBytes < 0) throw new Error("payload_bytes_invalid");

    failureStage = "database_connect";
    const sql = db();
    const result = await sql.begin(async (tx) => {
      failureStage = "resolve_release_evidence_bundle";
      const resolved = await tx<Array<{ result: Record<string, unknown> }>>`
        select penta_os20.resolve_release_evidence_bundle_v1(
          ${releaseVersion},
          ${payloadBytes}::bigint,
          ${cieSubject ? tx.json(cieSubject) : null}::jsonb
        ) as result`;
      failureStage = "enqueue_release_projection";
      const provenance = {
        source: "github_actions_oidc",
        repository: REPOSITORY,
        workflow_ref: claim(claims, "workflow_ref"),
        workflow_sha: claim(claims, "workflow_sha"),
        run_id: claim(claims, "run_id"),
        run_attempt: claim(claims, "run_attempt"),
        event_name: claim(claims, "event_name"),
        actor: claim(claims, "actor"),
        raw_token_persisted: false,
      };
      const projected = await tx<Array<{ result: Record<string, unknown> }>>`
        select penta_os20.enqueue_release_projection(
          ${releaseVersion},
          ${releaseTag},
          ${tx.json(provenance)}::jsonb
        ) as result`;
      let prDispatch: Record<string, unknown> | null = null;
      if (prNumber !== null) {
        failureStage = "dispatch_release_footer";
        const rows = await tx<Array<{ result: Record<string, unknown> }>>`
          select penta_os20.dispatch_release_footer_to_github_v1(
            ${releaseVersion},
            null,
            ${prNumber}
          ) as result`;
        prDispatch = rows[0]?.result ?? null;
      }
      return { resolved: resolved[0]?.result ?? null, projected: projected[0]?.result ?? null, pr_dispatch: prDispatch };
    });
    return json({ ok: true, service: "ct.pentarelease.evidence-oidc.v1", release_version: releaseVersion, release_tag: releaseTag, pr_number: prNumber, result, raw_token_persisted: false, authority_manufactured: false });
  } catch (error) {
    const diagnosticCode = safeDiagnosticCode(error);
    const authFailure = diagnosticCode === "github_oidc_verification_failed";
    return json({
      ok: false,
      error: authFailure ? "github_oidc_verification_failed" : "release_evidence_projection_rejected",
      diagnostic_version: 1,
      diagnostic_stage: failureStage,
      diagnostic_code: diagnosticCode,
      raw_token_persisted: false,
    }, authFailure ? 401 : 409);
  }
});
