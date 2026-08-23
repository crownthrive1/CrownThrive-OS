import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import rulepack from "./rulepack.ts";
// @ts-ignore: source-controlled JavaScript module is validated independently by Node CI.
import {
  ALGORITHMS,
  ENGINE_ID,
  ENGINE_VERSION,
  assessWalletIntent,
  buildPolicyAssuranceStatus,
  compileRulepack,
  verifyDecisionReceipt,
} from "./engine.mjs";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ALLOWED_ORIGIN = "https://wallet.crownthrive.com";
const MAX_BODY_BYTES = 131_072;
const SOURCE_REF = "service:ct.service.chlom-wallet-policy-assurance";
const compiledRulepack = compileRulepack(rulepack);

const FALSE_EFFECTS = Object.freeze({
  production_activation: false,
  provider_write: false,
  custody: false,
  token_issuance: false,
  money_movement: false,
  production_rights_grant: false,
  chain_broadcast: false,
  effective_price_publication: false,
  checkout_activation: false,
  phase_advancement: false,
  merge_authorized: false,
});

type Json = Record<string, unknown>;

type AuthorityContext = {
  agent_id: string;
  autonomy_class: string;
  decision_class: string;
  self_approval: boolean;
  vote_effect: string;
  head_sha: string;
  exact_head_bound: boolean;
  heartbeat_at: string | null;
  heartbeat_ttl_seconds: number | null;
  heartbeat_fresh: boolean;
  did_uri: string;
  public_identity_digest_sha256: string;
  phase: string;
};

function headers(origin = ALLOWED_ORIGIN) {
  return {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, max-age=0",
    "pragma": "no-cache",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "authorization,content-type,x-crownthrive-correlation-id",
    "access-control-max-age": "600",
    "vary": "Origin",
  };
}

function response(req: Request, body: unknown, status = 200) {
  const origin = req.headers.get("origin") === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : ALLOWED_ORIGIN;
  return new Response(JSON.stringify(body), { status, headers: headers(origin) });
}

function safeCorrelation(req: Request): string {
  const value = req.headers.get("x-crownthrive-correlation-id");
  if (value && /^[A-Za-z0-9._:-]{8,160}$/.test(value)) return value;
  return `ct.wallet.policy.${crypto.randomUUID()}`;
}

function decodeJwtSubject(req: Request): { sub: string; subject_ref: string } {
  const authorization = req.headers.get("authorization") ?? "";
  const match = /^Bearer\s+(.+)$/i.exec(authorization);
  if (!match) throw new Error("authorization_required");
  const parts = match[1].split(".");
  if (parts.length !== 3) throw new Error("jwt_shape_invalid");
  const base = parts[1].replaceAll("-", "+").replaceAll("_", "/");
  let payload: Json;
  try {
    payload = JSON.parse(atob(base + "===".slice((base.length + 3) % 4)));
  } catch {
    throw new Error("jwt_payload_invalid");
  }
  const sub = String(payload.sub ?? "");
  if (!/^[A-Za-z0-9._:@-]{6,200}$/.test(sub)) throw new Error("jwt_subject_invalid");
  const exp = Number(payload.exp ?? 0);
  if (!Number.isFinite(exp) || exp <= Math.floor(Date.now() / 1000)) throw new Error("jwt_expired");
  return { sub, subject_ref: `auth:${sub}` };
}

async function rpc<T>(name: string, body: Json = {}): Promise<T> {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) throw new Error("server_configuration_hold");
  const result = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "apikey": SERVICE_ROLE_KEY,
      "authorization": `Bearer ${SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12_000),
  });
  const text = await result.text();
  if (!result.ok) {
    let reason = `rpc_${name}_${result.status}`;
    try {
      const parsed = JSON.parse(text);
      const candidate = String(parsed?.message ?? "");
      if (/^[A-Za-z0-9_:-]{1,160}$/.test(candidate)) reason = candidate;
    } catch {
      // Keep bounded HTTP-derived error code.
    }
    throw new Error(reason);
  }
  return (text ? JSON.parse(text) : null) as T;
}

function buildServerBoundIntent(body: Json, authority: AuthorityContext): Json {
  const input = body.intent;
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("intent_object_required");
  const candidate = structuredClone(input as Json);
  const requested = candidate.requested_effects && typeof candidate.requested_effects === "object" && !Array.isArray(candidate.requested_effects)
    ? candidate.requested_effects as Json
    : {};
  const governance = candidate.governance && typeof candidate.governance === "object" && !Array.isArray(candidate.governance)
    ? candidate.governance as Json
    : {};
  return {
    ...candidate,
    intent_id: candidate.intent_id ?? `ct.wallet.intent.edge.${crypto.randomUUID()}`,
    environment: candidate.environment ?? "controlled_test",
    authority: {
      agent_id: authority.agent_id,
      autonomy_class: authority.autonomy_class,
      decision_class: authority.decision_class,
      self_approval: false,
      vote_effect: "none",
      heartbeat_fresh: authority.heartbeat_fresh,
      exact_head_bound: authority.exact_head_bound,
    },
    requested_effects: { ...FALSE_EFFECTS, ...requested },
    governance: {
      independent_review_required: false,
      phase_gate_required: false,
      rollback_plan_present: false,
      evidence_digest_bound: false,
      ...governance,
      authority_head_sha: authority.head_sha,
      authority_phase: authority.phase,
    },
  };
}

async function statusPayload() {
  const databaseStatus = await rpc<Json>("chlom_wallet_policy_assurance_status_v1");
  return {
    ok: true,
    service_id: "ct.service.chlom-wallet-policy-assurance",
    agent_id: "ct.agent.chlom-wallet-settlement",
    state: "CONTROLLED_TEST_ACTIVE",
    engine_id: ENGINE_ID,
    engine_version: ENGINE_VERSION,
    rulepack_id: compiledRulepack.rulepack_id,
    rulepack_version: compiledRulepack.semantic_version,
    rulepack_sha256: compiledRulepack.rulepack_sha256,
    algorithms: Object.values(ALGORITHMS),
    capabilities: ["status", "evaluate", "verify-receipt"],
    database_status: databaseStatus,
    hard_boundaries: FALSE_EFFECTS,
    ai_advisory: { enabled: false, final_authority: false },
  };
}

Deno.serve(async (req: Request) => {
  const origin = req.headers.get("origin");
  if (origin && origin !== ALLOWED_ORIGIN) return response(req, { ok: false, error: "origin_not_allowed" }, 403);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: headers() });

  let subject: { sub: string; subject_ref: string };
  try {
    subject = decodeJwtSubject(req);
  } catch (error) {
    return response(req, { ok: false, error: error instanceof Error ? error.message : "authorization_failed" }, 401);
  }

  if (req.method === "GET") {
    try {
      return response(req, await statusPayload());
    } catch (error) {
      return response(req, { ok: false, state: "HOLD", error: error instanceof Error ? error.message : "status_failed" }, 503);
    }
  }
  if (req.method !== "POST") return response(req, { ok: false, error: "method_not_allowed" }, 405);

  const raw = await req.text();
  if (raw.length > MAX_BODY_BYTES) return response(req, { ok: false, error: "payload_too_large" }, 413);
  let body: Json;
  try {
    body = JSON.parse(raw || "{}");
  } catch {
    return response(req, { ok: false, error: "invalid_json" }, 400);
  }

  const action = String(body.action ?? "");
  try {
    if (action === "status") return response(req, await statusPayload());
    if (action === "verify-receipt") {
      const result = verifyDecisionReceipt(body.receipt);
      return response(req, { ok: result.valid, ...result, hard_boundaries: FALSE_EFFECTS }, result.valid ? 200 : 422);
    }
    if (action !== "evaluate") return response(req, { ok: false, error: "unsupported_action" }, 400);

    const authority = await rpc<AuthorityContext>("chlom_wallet_policy_authority_context_v1");
    const intent = buildServerBoundIntent(body, authority);
    const receipt = assessWalletIntent(intent, compiledRulepack);
    const correlationId = safeCorrelation(req);
    const persisted = await rpc<Json>("chlom_wallet_record_policy_decision_receipt_v1", {
      p_subject_ref: subject.subject_ref,
      p_correlation_id: correlationId,
      p_decision: receipt,
      p_source_ref: SOURCE_REF,
    });

    return response(req, {
      ok: true,
      state: "CONTROLLED_TEST_DECISION_RECORDED",
      correlation_id: correlationId,
      authority: {
        agent_id: authority.agent_id,
        head_sha: authority.head_sha,
        heartbeat_fresh: authority.heartbeat_fresh,
        did_uri: authority.did_uri,
        public_identity_digest_sha256: authority.public_identity_digest_sha256,
        phase: authority.phase,
      },
      receipt,
      persistence: persisted,
      hard_boundaries: FALSE_EFFECTS,
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "policy_assurance_failed";
    return response(req, {
      ok: false,
      state: "HOLD",
      error: reason,
      hard_boundaries: FALSE_EFFECTS,
    }, reason.includes("not_registered") || reason.includes("missing") ? 503 : 422);
  }
});
