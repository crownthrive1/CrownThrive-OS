import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  assertNoAuthorityEscalation,
  canonicalize,
  sha256Hex,
  verifyGithubOidcJwtV2,
  verifyRepositorySnapshotV2,
} from "./github-oidc-contract-v2.mjs";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const MAX_BODY_BYTES = 2_000_000;

function responseHeaders() {
  return {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, max-age=0",
    "pragma": "no-cache",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: responseHeaders() });
}

function errorCode(error: unknown) {
  const value = error instanceof Error ? error.message : String(error);
  return /^[A-Za-z0-9_:-]{1,200}$/.test(value) ? value : "institutionalization_v2_ingest_failed";
}

async function rpc(name: string, body: Record<string, unknown>) {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) throw new Error("server_configuration_hold");
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "apikey": SERVICE_ROLE_KEY,
      "authorization": `Bearer ${SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
  const text = await response.text();
  if (!response.ok) {
    try {
      const parsed = JSON.parse(text);
      const message = String(parsed?.message ?? "");
      if (/^[A-Za-z0-9_:-]{1,200}$/.test(message)) throw new Error(message);
    } catch (error) {
      if (error instanceof Error && !error.message.startsWith("Unexpected")) throw error;
    }
    throw new Error(`institutionalization_v2_rpc_${response.status}`);
  }
  return text ? JSON.parse(text) : null;
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  const authorization = request.headers.get("authorization") ?? "";
  const tokenMatch = /^Bearer\s+(.+)$/i.exec(authorization);
  if (!tokenMatch) return json({ ok: false, error: "github_oidc_bearer_required" }, 401);

  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) {
    return json({ ok: false, error: "payload_too_large" }, 413);
  }

  let body: Record<string, unknown>;
  try {
    body = JSON.parse(raw || "{}");
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }
  if (!body.manifest || typeof body.manifest !== "object" || Array.isArray(body.manifest)) {
    return json({ ok: false, error: "manifest_object_required" }, 400);
  }

  try {
    const token = tokenMatch[1];
    const verifiedToken = await verifyGithubOidcJwtV2(token);
    const verifiedClaims = await verifyRepositorySnapshotV2({
      claims: verifiedToken.claims,
      manifest: body.manifest,
    });
    assertNoAuthorityEscalation(verifiedClaims);
    const tokenFingerprint = await sha256Hex(token);
    const requestDigest = await sha256Hex(canonicalize({
      manifest: body.manifest,
      verified_claims: verifiedClaims,
    }));
    const result = await rpc("chlom_wallet_ingest_institutionalization_package_v2", {
      p_manifest: body.manifest,
      p_claims: verifiedClaims,
      p_token_fingerprint_sha256: tokenFingerprint,
      p_request_digest_sha256: requestDigest,
    });
    return json({
      ok: true,
      service_id: "ct.service.chlom-wallet-institutionalize-v2",
      state: "RECORDED_CONTROLLED_TEST_EVIDENCE",
      result,
      token_value_persisted: false,
      raw_artifact_body_persisted: false,
      provider_write: false,
      credential_access: false,
      effective_offer: false,
      stripe_objects_created: false,
      checkout_enabled: false,
      custody: false,
      token_issuance: false,
      money_movement: false,
      production_rights_grant: false,
      chain_broadcast: false,
      phase_advancement: false,
      merge_authorized: false,
    });
  } catch (error) {
    return json({
      ok: false,
      service_id: "ct.service.chlom-wallet-institutionalize-v2",
      state: "HOLD_INSTITUTIONALIZATION_INGEST_V2",
      error: errorCode(error),
      token_value_persisted: false,
      raw_artifact_body_persisted: false,
      provider_write: false,
      credential_access: false,
      effective_offer: false,
      stripe_objects_created: false,
      checkout_enabled: false,
      custody: false,
      token_issuance: false,
      money_movement: false,
      production_rights_grant: false,
      chain_broadcast: false,
      phase_advancement: false,
      merge_authorized: false,
    }, 422);
  }
});
