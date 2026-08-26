import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "pragma": "no-cache",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
  "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
};

function json(status: number, body: Record<string, unknown>, extra: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { ...HEADERS, ...extra } });
}

function base64Url(bytes: Uint8Array) {
  let value = "";
  for (const byte of bytes) value += String.fromCharCode(byte);
  return btoa(value).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

async function sha256Hex(input: string) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input)));
  return Array.from(digest).map((value) => value.toString(16).padStart(2, "0")).join("");
}

async function rpc(name: string, args: Record<string, unknown> = {}) {
  if (!BASE || !SERVICE) throw new Error("runtime_unavailable");
  const response = await fetch(`${BASE}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      apikey: SERVICE,
      authorization: `Bearer ${SERVICE}`,
    },
    body: JSON.stringify(args),
    signal: AbortSignal.timeout(30000),
  });
  const text = await response.text();
  if (!response.ok) {
    let safe: Record<string, unknown> = {};
    try {
      const payload = JSON.parse(text);
      safe = { code: payload?.code, message: payload?.message };
    } catch {
      safe = { message: "rpc_failed" };
    }
    throw new Error(`${name}:${response.status}:${safe.message ?? safe.code ?? "failed"}`);
  }
  return text ? JSON.parse(text) : null;
}

Deno.serve(async (request: Request) => {
  if (request.method !== "GET") {
    return json(405, {
      ok: false,
      service: "ct.crown-connect.github-oauth",
      error: "method_not_allowed",
      provider_request: false,
      secret_material_returned: false,
    });
  }

  try {
    const url = new URL(request.url);
    const action = String(url.searchParams.get("action") ?? "").toLowerCase();
    const hasOAuthPayload = url.searchParams.has("code") || url.searchParams.has("state") || url.searchParams.has("error");

    if (!hasOAuthPayload && action !== "start" && action !== "authorize") {
      const status = await rpc("crown_connect_github_oauth_status_v1");
      return json(200, {
        ...status,
        service: "ct.crown-connect.github-oauth",
        provider: "GitHub",
        state: status?.oauth_client_secret_bound ? "READY" : "HOLD_PENTACREDENTIALS_CLIENT_BINDING",
        credential_plane: "PentaCredentials",
        device_flow_required: false,
        secret_material_returned: false,
      });
    }

    if (!hasOAuthPayload && (action === "start" || action === "authorize")) {
      const rawState = base64Url(crypto.getRandomValues(new Uint8Array(32)));
      const stateDigest = await sha256Hex(rawState);
      const returnTo = url.searchParams.get("return_to") || "https://crownthrive.com/?crown_connect=connected";
      const state = await rpc("crown_connect_github_oauth_create_state_v1", {
        p_state_digest: stateDigest,
        p_return_to: returnTo,
      });
      const authorize = new URL("https://github.com/login/oauth/authorize");
      authorize.searchParams.set("client_id", String(state.client_id));
      authorize.searchParams.set("redirect_uri", String(state.callback_url));
      authorize.searchParams.set("state", rawState);
      const scopes = Array.isArray(state.scopes) ? state.scopes.map(String) : [];
      if (scopes.length) authorize.searchParams.set("scope", scopes.join(" "));
      authorize.searchParams.set("allow_signup", "false");
      return new Response(null, {
        status: 302,
        headers: {
          location: authorize.toString(),
          "cache-control": "no-store",
          pragma: "no-cache",
          "referrer-policy": "no-referrer",
          "x-content-type-options": "nosniff",
        },
      });
    }

    if (url.searchParams.has("error")) {
      return json(400, {
        ok: false,
        service: "ct.crown-connect.github-oauth",
        state: "PROVIDER_AUTHORIZATION_DECLINED_OR_FAILED",
        provider_error_received: true,
        provider_error_echoed: false,
        provider_request: false,
        secret_material_returned: false,
      });
    }

    const code = url.searchParams.get("code") ?? "";
    const state = url.searchParams.get("state") ?? "";
    if (code.length < 8 || state.length < 32) {
      return json(400, {
        ok: false,
        service: "ct.crown-connect.github-oauth",
        error: "oauth_code_and_state_required",
        authorization_code_echoed: false,
        state_echoed: false,
        secret_material_returned: false,
      });
    }

    const stateDigest = await sha256Hex(state);
    const result = await rpc("crown_connect_github_oauth_exchange_v1", {
      p_code: code,
      p_state_digest: stateDigest,
    });
    return json(200, {
      ...result,
      service: "ct.crown-connect.github-oauth",
      application: "Crown Connect",
      provider: "GitHub",
      authorization_code_echoed: false,
      state_echoed: false,
      credential_plane: "PentaCredentials",
      secret_material_returned: false,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "oauth_runtime_error";
    return json(500, {
      ok: false,
      service: "ct.crown-connect.github-oauth",
      state: "HOLD_FAIL_CLOSED",
      error_class: message.split(":")[0],
      provider_token_returned: false,
      client_secret_returned: false,
      secret_material_returned: false,
    });
  }
});
