import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const STRIPE_BASE = "https://api.stripe.com/v1";
const VERSION = "2.0.0";
const encoder = new TextEncoder();

function respond(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

async function rpc(name: string, body: Record<string, unknown> = {}) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      authorization: `Bearer ${SERVICE_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data: unknown = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  return data as any;
}

async function runtimeSecret(alias: string) {
  const value = await rpc("get_runtime_secret", { secret_name: alias });
  if (typeof value !== "string" || !value) throw new Error(`secret_unavailable_${alias}`);
  return value;
}

async function stripeRequest(apiKey: string, method: string, path: string, form?: URLSearchParams) {
  const response = await fetch(`${STRIPE_BASE}${path}`, {
    method,
    headers: {
      authorization: `Bearer ${apiKey}`,
      accept: "application/json",
      ...(form ? { "content-type": "application/x-www-form-urlencoded" } : {}),
    },
    body: form?.toString(),
    signal: AbortSignal.timeout(25_000),
  });
  const text = await response.text();
  let data: any = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!response.ok) {
    const code = data?.error?.code ?? data?.error?.type ?? `http_${response.status}`;
    throw new Error(`stripe_${method}_${path}_${code}`);
  }
  return data;
}

function bytesToHex(bytes: Uint8Array) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function hmacHex(secret: string, message: string) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return bytesToHex(new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(message))));
}

function isTargetPredecessor(target: string, endpoint: any, keepId: string) {
  if (!endpoint || endpoint.id === keepId || endpoint.status !== "enabled") return false;
  const url = String(endpoint.url ?? "").toLowerCase();
  const description = String(endpoint.description ?? "").toLowerCase();
  const metadataTarget = String(endpoint.metadata?.crownthrive_target ?? "").toLowerCase();
  if (metadataTarget === target) return true;
  if (target === "thrivetickets") return url.includes("thrivetickets") || description.includes("thrivetickets");
  return url.includes("sermontoolkit") || url.includes("kjv") || description.includes("sermon toolkit") || description.includes("kjv");
}

async function providerEndpoint(apiKey: string, id: string | null) {
  if (!id) return null;
  try { return await stripeRequest(apiKey, "GET", `/webhook_endpoints/${encodeURIComponent(id)}`); }
  catch { return null; }
}

async function createEndpoint(apiKey: string, target: any) {
  const form = new URLSearchParams();
  form.set("url", String(target.endpoint_url));
  form.set("description", `CrownThrive ${target.target_key} institutional webhook ingress v2`);
  for (const event of target.desired_enabled_events ?? []) form.append("enabled_events[]", String(event));
  form.set("metadata[crownthrive_target]", String(target.target_key));
  form.set("metadata[crownthrive_contract]", "ct.stripe.webhook-ingress.v2");
  form.set("metadata[system_ref]", String(target.system_ref));
  return await stripeRequest(apiKey, "POST", "/webhook_endpoints", form);
}

async function updateEndpoint(apiKey: string, endpointId: string, target: any) {
  const form = new URLSearchParams();
  form.set("url", String(target.endpoint_url));
  form.set("description", `CrownThrive ${target.target_key} institutional webhook ingress v2`);
  for (const event of target.desired_enabled_events ?? []) form.append("enabled_events[]", String(event));
  form.set("metadata[crownthrive_target]", String(target.target_key));
  form.set("metadata[crownthrive_contract]", "ct.stripe.webhook-ingress.v2");
  form.set("metadata[system_ref]", String(target.system_ref));
  return await stripeRequest(apiKey, "POST", `/webhook_endpoints/${encodeURIComponent(endpointId)}`, form);
}

async function signedCanary(target: any, signingSecret: string) {
  const now = Math.floor(Date.now() / 1000);
  const body = JSON.stringify({
    id: `evt_ct_canary_${target.target_key}_${now}`,
    object: "event",
    api_version: "2025-12-15.clover",
    created: now,
    data: { object: { id: `ct_canary_${target.target_key}_${now}`, object: "crownthrive_canary" } },
    livemode: false,
    pending_webhooks: 1,
    request: null,
    type: "crownthrive.webhook.canary",
  });
  const signature = await hmacHex(signingSecret, `${now}.${body}`);
  const response = await fetch(String(target.endpoint_url), {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "stripe-signature": `t=${now},v1=${signature}`,
      "x-crownthrive-bootstrap-canary": "1",
    },
    body,
    signal: AbortSignal.timeout(25_000),
  });
  const text = await response.text();
  return {
    status: response.status,
    ok: response.ok,
    response_sha256: bytesToHex(new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(text)))),
  };
}

Deno.serve(async (request: Request) => {
  try {
    if (request.method !== "POST") return respond(405, { ok: false, error: "POST_required", version: VERSION });
    const suppliedControl = request.headers.get("x-crownthrive-control") ?? "";
    const expectedControl = await runtimeSecret("stripe_webhook_bootstrap_control_v2");
    if (!suppliedControl || suppliedControl !== expectedControl) return respond(401, { ok: false, error: "unauthorized", version: VERSION });

    const stripeAlias = await rpc("stripe_webhook_resolve_live_secret_alias_v2");
    if (typeof stripeAlias !== "string" || !stripeAlias) throw new Error("live_stripe_secret_alias_not_found");
    const stripeKey = await runtimeSecret(stripeAlias);
    if (!stripeKey.startsWith("sk_live_")) throw new Error("live_stripe_secret_required");
    const targets = await rpc("stripe_webhook_target_list_v2");
    if (!Array.isArray(targets) || targets.length !== 2) throw new Error("target_configuration_incomplete");

    const beforeList = await stripeRequest(stripeKey, "GET", "/webhook_endpoints?limit=100");
    const results: any[] = [];
    for (const target of targets) {
      let endpoint = await providerEndpoint(stripeKey, target.provider_endpoint_id ?? null);
      let signingSecret: string | null = null;
      if (endpoint?.status === "enabled" && endpoint?.url === target.endpoint_url) {
        try { signingSecret = await runtimeSecret(String(target.signing_secret_alias)); } catch { signingSecret = null; }
        if (signingSecret?.startsWith("whsec_")) endpoint = await updateEndpoint(stripeKey, endpoint.id, target);
      }
      if (!endpoint || endpoint.status !== "enabled" || endpoint.url !== target.endpoint_url || !signingSecret?.startsWith("whsec_")) {
        endpoint = await createEndpoint(stripeKey, target);
        signingSecret = String(endpoint.secret ?? "");
        if (!signingSecret.startsWith("whsec_")) throw new Error(`signing_secret_missing_${target.target_key}`);
        await rpc("ct_provider_secret_upsert_v2", {
          p_name: String(target.signing_secret_alias),
          p_secret: signingSecret,
          p_description: `Stripe provider-generated signing secret for ${target.target_key} institutional ingress v2. Restricted runtime custody.`,
        });
      }

      const canary = await signedCanary(target, signingSecret);
      if (!canary.ok) throw new Error(`signed_canary_failed_${target.target_key}_${canary.status}`);

      const retired: string[] = [];
      for (const oldEndpoint of beforeList?.data ?? []) {
        if (!isTargetPredecessor(String(target.target_key), oldEndpoint, String(endpoint.id))) continue;
        try {
          await stripeRequest(stripeKey, "DELETE", `/webhook_endpoints/${encodeURIComponent(oldEndpoint.id)}`);
          retired.push(String(oldEndpoint.id));
        } catch {}
      }

      const recorded = await rpc("stripe_webhook_record_bootstrap_v2", {
        p_target_key: String(target.target_key),
        p_provider_endpoint_id: String(endpoint.id),
        p_provider_state: String(endpoint.status ?? "enabled"),
        p_canary_http_status: canary.status,
        p_retired_ids: retired,
        p_evidence: {
          contract: "ct.stripe.webhook-ingress.v2",
          endpoint_url: target.endpoint_url,
          provider_endpoint_id: endpoint.id,
          provider_state: endpoint.status,
          livemode: endpoint.livemode,
          desired_events_count: Array.isArray(target.desired_enabled_events) ? target.desired_enabled_events.length : 0,
          signed_canary_http_status: canary.status,
          signed_canary_response_sha256: canary.response_sha256,
          retired_predecessor_count: retired.length,
          secret_material_stored_in_vault: true,
          secret_exposed: false,
          money_movement_authority: false,
        },
      });
      results.push({
        target_key: target.target_key,
        provider_endpoint_id: endpoint.id,
        provider_state: endpoint.status,
        signed_canary_http_status: canary.status,
        retired_predecessor_count: retired.length,
        institutional_state: recorded?.state ?? null,
      });
    }

    return respond(200, {
      ok: true,
      contract: "ct.stripe.webhook-ingress.v2",
      results,
      secret_exposed: false,
      money_movement_authority: false,
      version: VERSION,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return respond(500, {
      ok: false,
      error: message,
      provider_mutation_complete: false,
      secret_exposed: false,
      money_movement_authority: false,
      version: VERSION,
    });
  }
});
