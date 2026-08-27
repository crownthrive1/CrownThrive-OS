import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "postgres";
import { createRemoteJWKSet, jwtVerify } from "jose";

const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "crownthrive-repository-federation";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const REPOSITORY = "crownthrive1/CrownThrive-OS";
const REPOSITORY_ID = "1336348391";
const REPOSITORY_OWNER = "crownthrive1";
const REPOSITORY_OWNER_ID = "315660018";
const REF = "refs/heads/main";
const WORKFLOW_REF = `${REPOSITORY}/.github/workflows/penta-governed-release-vote-oidc.yml@${REF}`;
const EVENT_NAME = "repository_dispatch";
const RELEASE_ID = "5615a39d-67e6-4558-9c08-0530e8e82768";
const EXACT_VERSION_REF = "1.0.0+edge.v5";
const CONTENT_SHA256 = "5f31680b3aced8ee88d45814fa03dba5fc8e9d9150bf948742487c2e734269c0";
const ALLOWED_VOTERS = new Set([
  "ct.relay.agent-a",
  "ct.relay.agent-b",
  "ct.relay.agent-c",
  "ct.relay.agent-d",
  "ct.relay.agent-s",
]);
const IMMUTABLE_SUB = `repo:${REPOSITORY_OWNER}@${REPOSITORY_OWNER_ID}/CrownThrive-OS@${REPOSITORY_ID}:ref:${REF}`;
const LEGACY_SUB = `repo:${REPOSITORY}:ref:${REF}`;

let pg: ReturnType<typeof postgres> | null = null;
function db() {
  const url = Deno.env.get("SUPABASE_DB_URL") ?? "";
  if (!url) throw new Error("database_unavailable");
  pg ??= postgres(url, { max: 2, idle_timeout: 10, prepare: false });
  return pg;
}

function headers(contentType = "application/json; charset=utf-8") {
  return {
    "content-type": contentType,
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
  };
}
function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: headers() });
}
function stable(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${stable(object[key])}`).join(",")}}`;
}
function hex(bytes: Uint8Array) {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}
async function sha256(value: string) {
  return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value))));
}
function claimString(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function safeClaims(payload: Record<string, unknown>) {
  const keys = [
    "iss", "aud", "sub", "jti", "repository", "repository_id", "repository_owner",
    "repository_owner_id", "repository_visibility", "ref", "ref_type", "sha", "workflow",
    "workflow_ref", "workflow_sha", "job_workflow_ref", "job_workflow_sha", "event_name",
    "run_id", "run_number", "run_attempt", "actor", "actor_id", "runner_environment",
    "check_run_id", "iat", "nbf", "exp",
  ];
  return Object.fromEntries(keys.filter((key) => payload[key] !== undefined).map((key) => [key, payload[key]]));
}

async function proof() {
  const rows = await db()<Array<{ proof: Record<string, unknown> | null }>>`
    select integration_control.github_oidc_governed_release_proof_v1(${RELEASE_ID}::uuid) as proof
  `;
  return rows[0]?.proof ?? { state: "release_not_found" };
}

async function verifyToken(token: string) {
  const { payload, protectedHeader } = await jwtVerify(token, JWKS, {
    issuer: ISSUER,
    audience: AUDIENCE,
    algorithms: ["RS256"],
    clockTolerance: 30,
  });
  if (protectedHeader.typ && protectedHeader.typ !== "JWT") throw new Error("oidc_type_invalid");
  const claims = payload as Record<string, unknown>;
  if (claimString(claims, "repository") !== REPOSITORY) throw new Error("oidc_repository_invalid");
  if (claimString(claims, "repository_id") !== REPOSITORY_ID) throw new Error("oidc_repository_id_invalid");
  if (claimString(claims, "repository_owner") !== REPOSITORY_OWNER) throw new Error("oidc_repository_owner_invalid");
  if (claimString(claims, "repository_owner_id") !== REPOSITORY_OWNER_ID) throw new Error("oidc_repository_owner_id_invalid");
  if (claimString(claims, "repository_visibility") !== "public") throw new Error("oidc_repository_visibility_invalid");
  if (claimString(claims, "ref") !== REF || claimString(claims, "ref_type") !== "branch") throw new Error("oidc_ref_invalid");
  if (claimString(claims, "workflow_ref") !== WORKFLOW_REF) throw new Error("oidc_workflow_ref_invalid");
  if (claimString(claims, "event_name") !== EVENT_NAME) throw new Error("oidc_event_invalid");
  if (claimString(claims, "runner_environment") !== "github-hosted") throw new Error("oidc_runner_environment_invalid");
  const subject = claimString(claims, "sub");
  if (subject !== IMMUTABLE_SUB && subject !== LEGACY_SUB) throw new Error("oidc_subject_invalid");
  const workflowSha = claimString(claims, "workflow_sha");
  if (!/^[0-9a-f]{40}$/i.test(workflowSha)) throw new Error("oidc_workflow_sha_invalid");
  const runId = claimString(claims, "run_id");
  const runAttempt = claimString(claims, "run_attempt");
  const jti = claimString(claims, "jti");
  if (!/^\d+$/.test(runId) || !/^\d+$/.test(runAttempt) || !jti) throw new Error("oidc_run_or_jti_invalid");
  if (typeof payload.exp !== "number" || typeof payload.iat !== "number") throw new Error("oidc_time_claims_missing");
  if (payload.exp * 1000 <= Date.now()) throw new Error("oidc_token_expired");
  return claims;
}

async function recordVote(token: string, body: Record<string, unknown>) {
  const voterAgentId = String(body.voter_agent_id ?? "");
  if (!ALLOWED_VOTERS.has(voterAgentId)) throw new Error("voter_agent_not_allowed");
  if (String(body.release_id ?? "") !== RELEASE_ID
      || String(body.exact_version_ref ?? "") !== EXACT_VERSION_REF
      || String(body.content_sha256 ?? "") !== CONTENT_SHA256) {
    throw new Error("request_exact_snapshot_mismatch");
  }

  const claims = await verifyToken(token);
  const tokenSha256 = await sha256(token);
  const claimSubset = safeClaims(claims);
  const receiptDigest = await sha256(stable({
    contract: "ct.github-actions-oidc-governed-vote.v1",
    release_id: RELEASE_ID,
    voter_agent_id: voterAgentId,
    exact_version_ref: EXACT_VERSION_REF,
    content_sha256: CONTENT_SHA256,
    oidc_issuer: ISSUER,
    oidc_audience: AUDIENCE,
    repository_id: REPOSITORY_ID,
    repository: REPOSITORY,
    ref: REF,
    workflow_ref: WORKFLOW_REF,
    workflow_sha: claimString(claims, "workflow_sha"),
    run_id: claimString(claims, "run_id"),
    run_attempt: claimString(claims, "run_attempt"),
    jti: claimString(claims, "jti"),
    token_sha256: tokenSha256,
  }));

  const verifiedAt = new Date().toISOString();
  const expiresAt = new Date(Number(claims.exp) * 1000).toISOString();
  const rows = await db()<Array<{ result: Record<string, unknown> }>>`
    select integration_control.record_github_oidc_governed_vote_v1(
      ${RELEASE_ID}::uuid,
      ${voterAgentId},
      ${EXACT_VERSION_REF},
      ${CONTENT_SHA256},
      ${ISSUER},
      ${AUDIENCE},
      ${Number(REPOSITORY_ID)}::bigint,
      ${REPOSITORY},
      ${REPOSITORY_OWNER},
      ${Number(REPOSITORY_OWNER_ID)}::bigint,
      ${REF},
      ${WORKFLOW_REF},
      ${claimString(claims, "workflow_sha")},
      ${claimString(claims, "run_id")},
      ${claimString(claims, "run_attempt")},
      ${claimString(claims, "event_name")},
      ${claimString(claims, "jti")},
      ${claimString(claims, "sub")},
      ${claimString(claims, "actor")},
      ${claimString(claims, "actor_id")},
      ${tokenSha256},
      ${receiptDigest},
      ${verifiedAt}::timestamptz,
      ${expiresAt}::timestamptz,
      ${db().json(claimSubset)}::jsonb
    ) as result
  `;
  return rows[0]?.result ?? { authenticated: false, state: "vote_record_missing" };
}

async function finalize(token: string, body: Record<string, unknown>) {
  if (String(body.release_id ?? "") !== RELEASE_ID
      || String(body.exact_version_ref ?? "") !== EXACT_VERSION_REF
      || String(body.content_sha256 ?? "") !== CONTENT_SHA256) {
    throw new Error("request_exact_snapshot_mismatch");
  }
  const claims = await verifyToken(token);
  const rows = await db()<Array<{ recompute: Record<string, unknown>; dispatch: Record<string, unknown>; proof: Record<string, unknown> }>>`
    select
      integration_control.recompute_governed_release(${RELEASE_ID}::uuid) as recompute,
      integration_control.dispatch_dynamic_feed_publications(25) as dispatch,
      integration_control.github_oidc_governed_release_proof_v1(${RELEASE_ID}::uuid) as proof
  `;
  return {
    authenticated: true,
    mode: "finalize",
    workflow_sha: claimString(claims, "workflow_sha"),
    run_id: claimString(claims, "run_id"),
    run_attempt: claimString(claims, "run_attempt"),
    ...(rows[0] ?? {}),
    raw_token_persisted: false,
    authority_manufactured: false,
    self_vote_created: false,
    money_movement: false,
    checkout_activation: false,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "GET") {
    try {
      return json({
        service: "ct.penta-governed-release-vote-oidc.v1",
        release_id: RELEASE_ID,
        proof: await proof(),
        raw_token_persisted: false,
        money_movement: false,
        checkout_activation: false,
      });
    } catch (error) {
      return json({ error: "proof_read_failed", error_class: error instanceof Error ? error.message : "unknown_error" }, 503);
    }
  }
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const authorization = req.headers.get("authorization") ?? "";
  const token = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  if (!token) return json({ error: "github_oidc_bearer_required" }, 401);

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  try {
    const mode = String(body.mode ?? "vote");
    if (mode === "vote") return json(await recordVote(token, body));
    if (mode === "finalize") return json(await finalize(token, body));
    return json({ error: "unsupported_mode" }, 400);
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown_error";
    const authFailure = message.startsWith("oidc_") || message.includes("JWT") || message.includes("signature") || message.includes("audience") || message.includes("issuer");
    return json({
      error: authFailure ? "github_oidc_verification_failed" : "governed_vote_rejected",
      detail: message.slice(0, 240),
      raw_token_persisted: false,
      authority_manufactured: false,
      money_movement: false,
      checkout_activation: false,
    }, authFailure ? 401 : 409);
  }
});
