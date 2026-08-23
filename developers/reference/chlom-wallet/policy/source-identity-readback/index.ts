import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const SOURCE = Object.freeze({
  repository: "crownthrive1/CrownThrive-Support",
  commit_sha: "0261e0b4d3bfa5f041b59efd9bf78bc6e1f76591",
  path: "developers/reference/chlom-wallet/policy/chlom-wallet-policy-assurance.mjs",
  expected_git_blob_sha1: "41edcecf931b6c653cda6b9f9118ea15b795c72a",
  expected_size_bytes: 24926,
});
const FUNCTION = Object.freeze({
  service_id: "ct.service.chlom-wallet-source-identity-readback",
  slug: "chlom-wallet-source-identity-readback",
  version: 2,
});
const RAW_URL = `https://raw.githubusercontent.com/${SOURCE.repository}/${SOURCE.commit_sha}/${SOURCE.path}`;
const encoder = new TextEncoder();

function hex(bytes: ArrayBuffer): string {
  return [...new Uint8Array(bytes)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

async function digest(name: "SHA-1" | "SHA-256", bytes: Uint8Array): Promise<string> {
  return hex(await crypto.subtle.digest(name, bytes));
}

function concat(a: Uint8Array, b: Uint8Array): Uint8Array {
  const output = new Uint8Array(a.length + b.length);
  output.set(a, 0);
  output.set(b, a.length);
  return output;
}

async function persistObservation(sourceSha256: string, sizeBytes: number, gitBlobSha1: string): Promise<unknown> {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) throw new Error("server_configuration_hold");
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/chlom_wallet_record_policy_source_identity_observation_v1`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "apikey": SERVICE_ROLE_KEY,
      "authorization": `Bearer ${SERVICE_ROLE_KEY}`,
    },
    body: JSON.stringify({
      p_source_sha256: sourceSha256,
      p_source_size_bytes: sizeBytes,
      p_git_blob_sha1: gitBlobSha1,
      p_observer_function_version: FUNCTION.version,
      p_source_ref: `service:${FUNCTION.service_id}`,
    }),
    signal: AbortSignal.timeout(12_000),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`observation_rpc_${response.status}`);
  return text ? JSON.parse(text) : null;
}

Deno.serve(async (request: Request) => {
  if (request.method !== "GET") {
    return new Response(JSON.stringify({ ok: false, error: "method_not_allowed" }), {
      status: 405,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }
  try {
    const upstream = await fetch(RAW_URL, {
      method: "GET",
      headers: {
        "accept": "application/octet-stream",
        "user-agent": "CHLOM-Wallet-Source-Identity-Readback/2.0",
      },
      signal: AbortSignal.timeout(15_000),
    });
    if (!upstream.ok) throw new Error(`upstream_http_${upstream.status}`);
    const bytes = new Uint8Array(await upstream.arrayBuffer());
    const gitHeader = encoder.encode(`blob ${bytes.length}\0`);
    const sourceSha256 = await digest("SHA-256", bytes);
    const gitBlobSha1 = await digest("SHA-1", concat(gitHeader, bytes));
    const identityMatch = gitBlobSha1 === SOURCE.expected_git_blob_sha1 && bytes.length === SOURCE.expected_size_bytes;

    if (!identityMatch) {
      return new Response(JSON.stringify({
        ok: false,
        result: "HOLD_CHLOM_WALLET_SOURCE_IDENTITY_MISMATCH",
        service: FUNCTION,
        source: SOURCE,
        observed: { size_bytes: bytes.length, sha256: sourceSha256, git_blob_sha1: gitBlobSha1 },
        persistence: null,
      }), {
        status: 409,
        headers: { "content-type": "application/json", "cache-control": "no-store" },
      });
    }

    const persistence = await persistObservation(sourceSha256, bytes.length, gitBlobSha1);
    return new Response(JSON.stringify({
      ok: true,
      result: "PASS_CHLOM_WALLET_SOURCE_IDENTITY_READBACK",
      service: FUNCTION,
      source: SOURCE,
      observed: { size_bytes: bytes.length, sha256: sourceSha256, git_blob_sha1: gitBlobSha1 },
      persistence,
      controls: {
        fixed_source_only: true,
        arbitrary_url_input: false,
        credential_value_exposed: false,
        provider_write: false,
        production_activation: false,
        money_movement: false,
        chain_broadcast: false,
        phase_advancement: false,
        merge_authorized: false,
      },
    }), {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store, max-age=0",
        "x-content-type-options": "nosniff",
        "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
        "access-control-allow-origin": "https://wallet.crownthrive.com",
      },
    });
  } catch (error) {
    return new Response(JSON.stringify({
      ok: false,
      result: "HOLD_CHLOM_WALLET_SOURCE_IDENTITY_READBACK_FAILED",
      error: error instanceof Error ? error.message : "unknown_failure",
      controls: {
        credential_value_exposed: false,
        provider_write: false,
        money_movement: false,
        chain_broadcast: false,
      },
    }), {
      status: 503,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }
});
