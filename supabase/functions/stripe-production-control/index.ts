import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "npm:postgres@3.4.3";

const DB_URL = Deno.env.get("SUPABASE_DB_URL") ?? "";
let client: ReturnType<typeof postgres> | null = null;

function db() {
  if (!DB_URL) throw new Error("database_unavailable");
  client ??= postgres(DB_URL, { max: 2, idle_timeout: 10, prepare: false });
  return client;
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

async function vault(name: string) {
  const sql = db();
  const rows = await sql<Array<{ v: string }>>`
    select decrypted_secret as v
    from vault.decrypted_secrets
    where name = ${name}
    limit 1
  `;
  return rows[0]?.v ?? "";
}

async function authorize(req: Request) {
  const expected = await vault("stripe_production_control_gateway_secret_v1");
  return !!expected && (req.headers.get("x-ct-stripe-control-secret") ?? "") === expected;
}

async function stripe(
  path: string,
  key: string,
  account?: string,
  method = "GET",
  body?: URLSearchParams,
  idempotencyKey?: string,
) {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${key}`,
    "User-Agent": "CrownThrive-Stripe-Control/1.2.1",
  };
  if (account) headers["Stripe-Account"] = account;
  if (body) headers["Content-Type"] = "application/x-www-form-urlencoded";
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  const response = await fetch(`https://api.stripe.com${path}`, {
    method,
    headers,
    body: body?.toString(),
    signal: AbortSignal.timeout(20000),
  });
  const text = await response.text();
  let data: any = {};
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw_response: true };
  }
  return { status: response.status, data };
}

function safeAccount(account: any) {
  return {
    id: account?.id ?? null,
    type: account?.type ?? null,
    country: account?.country ?? null,
    default_currency: account?.default_currency ?? null,
    charges_enabled: !!account?.charges_enabled,
    payouts_enabled: !!account?.payouts_enabled,
    details_submitted: !!account?.details_submitted,
    capabilities: account?.capabilities ?? {},
    requirements: {
      currently_due: account?.requirements?.currently_due ?? [],
      past_due: account?.requirements?.past_due ?? [],
      pending_verification: account?.requirements?.pending_verification ?? [],
      disabled_reason: account?.requirements?.disabled_reason ?? null,
    },
  };
}

function safeTransfer(transfer: any) {
  return {
    id: transfer?.id ?? null,
    amount: transfer?.amount ?? null,
    currency: transfer?.currency ?? null,
    destination: typeof transfer?.destination === "string"
      ? transfer.destination
      : transfer?.destination?.id ?? null,
    reversed: !!transfer?.reversed,
    amount_reversed: transfer?.amount_reversed ?? 0,
    transfer_group: transfer?.transfer_group ?? null,
    created: transfer?.created ?? null,
  };
}

async function authorizedRoute() {
  const sql = db();
  const rows = await sql<Array<any>>`
    select route_key, provider_ref, state, health_state, internal_only,
           provider_capable, money_movement_authorized
    from public.ct_self_funding_settlement_routes
    where route_key = 'sfe.stripe.crownthrive.hot.v1'
    limit 1
  `;
  const route = rows[0];
  return route &&
      route.state === "active" &&
      route.health_state === "green" &&
      route.internal_only === true &&
      route.provider_capable === true &&
      route.money_movement_authorized === true
    ? route
    : null;
}

Deno.serve(async (req) => {
  try {
    if (req.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "content-type,x-ct-stripe-control-secret",
        },
      });
    }

    if (req.method === "GET") {
      const sql = db();
      const rows = await sql<Array<any>>`
        select service_id, integration_state, write_gate, monthly_request_limit, metadata
        from integration_control.services
        where service_id = 'stripe'
        limit 1
      `;
      const metadata = rows[0]?.metadata ?? {};
      return json({
        service: "stripe-production-control",
        version: "1.2.1",
        environment: "production",
        platform_account_id: metadata.account_id ?? null,
        connected_account_id: metadata.connected_account_id ?? null,
        credential_state: "vaulted",
        provider_readback_available: true,
        provider_write_available: true,
        write_scope: "CrownThrive-internal connected account only; route authority required",
        raw_secret_export: false,
      });
    }

    if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    if (!(await authorize(req))) return json({ error: "internal_authorization_required" }, 403);

    const body: any = await req.json().catch(() => ({}));
    const action = String(body.action ?? "");
    const key = await vault("stripe_connect_live_secret_key_v1");
    if (!key.startsWith("sk_live_")) return json({ error: "stripe_live_secret_unavailable" }, 503);

    const sql = db();
    const services = await sql<Array<any>>`
      select metadata from integration_control.services where service_id = 'stripe' limit 1
    `;
    const metadata = services[0]?.metadata ?? {};
    const connected = String(metadata.connected_account_id ?? "");
    if (!connected) return json({ error: "connected_account_missing" }, 409);

    let result: any;

    if (action === "platform_account") result = await stripe("/v1/account", key);
    else if (action === "connected_account") result = await stripe(`/v1/accounts/${encodeURIComponent(connected)}`, key);
    else if (action === "payment_method_configurations") result = await stripe("/v1/payment_method_configurations?limit=20", key, body.connected === true ? connected : undefined);
    else if (action === "product") {
      const id = String(body.id ?? "");
      if (!/^prod_[A-Za-z0-9]+$/.test(id)) return json({ error: "invalid_product_id" }, 400);
      result = await stripe(`/v1/products/${id}`, key, body.connected === true ? connected : undefined);
    } else if (action === "price") {
      const id = String(body.id ?? "");
      if (!/^price_[A-Za-z0-9]+$/.test(id)) return json({ error: "invalid_price_id" }, 400);
      result = await stripe(`/v1/prices/${id}`, key, body.connected === true ? connected : undefined);
    } else if (action === "payment_intent") {
      const id = String(body.id ?? "");
      if (!/^pi_[A-Za-z0-9]+$/.test(id)) return json({ error: "invalid_payment_intent_id" }, 400);
      result = await stripe(`/v1/payment_intents/${id}`, key, body.connected === true ? connected : undefined);
    } else if (action === "transfer_readback") {
      const id = String(body.transfer_id ?? "");
      if (!/^tr_[A-Za-z0-9]+$/.test(id)) return json({ error: "invalid_transfer_id" }, 400);
      result = await stripe(`/v1/transfers/${id}`, key);
    } else if (action === "create_transfer") {
      const route = await authorizedRoute();
      if (!route) return json({ error: "route_authority_not_active", money_movement: false }, 423);

      const amount = Number(body.amount);
      const currency = String(body.currency ?? "usd").toLowerCase();
      const destination = String(body.destination ?? connected);
      const idempotencyKey = String(body.idempotency_key ?? "");
      if (!Number.isSafeInteger(amount) || amount <= 0) return json({ error: "amount_must_be_positive_minor_units" }, 400);
      if (!/^[a-z]{3}$/.test(currency)) return json({ error: "invalid_currency" }, 400);
      if (destination !== connected) return json({ error: "destination_not_authorized" }, 403);
      if (idempotencyKey.length < 12 || idempotencyKey.length > 255) return json({ error: "idempotency_key_required" }, 400);

      const form = new URLSearchParams({ amount: String(amount), currency, destination });
      if (body.transfer_group) form.set("transfer_group", String(body.transfer_group));
      if (body.source_transaction) form.set("source_transaction", String(body.source_transaction));

      result = await stripe("/v1/transfers", key, undefined, "POST", form, idempotencyKey);
      if (result.status >= 200 && result.status < 300) {
        const readback = await stripe(`/v1/transfers/${encodeURIComponent(result.data.id)}`, key);
        if (readback.status < 200 || readback.status >= 300) {
          return json({ error: "transfer_created_readback_failed", provider_http_status: readback.status, transfer_id: result.data.id, money_movement: true }, 502);
        }
        return json({
          service: "stripe-production-control",
          version: "1.2.1",
          action,
          provider_http_status: result.status,
          provider_write_performed: true,
          money_movement: true,
          route_key: route.route_key,
          readback_pass: true,
          result: safeTransfer(readback.data),
          raw_secret_export: false,
        });
      }
    } else if (action === "reverse_transfer") {
      const route = await authorizedRoute();
      if (!route) return json({ error: "route_authority_not_active", money_movement: false }, 423);

      const id = String(body.transfer_id ?? "");
      const idempotencyKey = String(body.idempotency_key ?? "");
      if (!/^tr_[A-Za-z0-9]+$/.test(id)) return json({ error: "invalid_transfer_id" }, 400);
      if (idempotencyKey.length < 12 || idempotencyKey.length > 255) return json({ error: "idempotency_key_required" }, 400);

      const original = await stripe(`/v1/transfers/${id}`, key);
      if (original.status < 200 || original.status >= 300) return json({ error: "transfer_readback_failed", provider_http_status: original.status }, 502);
      const destination = typeof original.data.destination === "string" ? original.data.destination : original.data.destination?.id;
      if (destination !== connected) return json({ error: "transfer_destination_not_authorized_for_reversal" }, 403);

      const form = new URLSearchParams();
      if (body.amount !== undefined) {
        const amount = Number(body.amount);
        if (!Number.isSafeInteger(amount) || amount <= 0) return json({ error: "invalid_reversal_amount" }, 400);
        form.set("amount", String(amount));
      }

      result = await stripe(`/v1/transfers/${id}/reversals`, key, undefined, "POST", form, idempotencyKey);
      if (result.status >= 200 && result.status < 300) {
        const readback = await stripe(`/v1/transfers/${id}`, key);
        return json({
          service: "stripe-production-control",
          version: "1.2.1",
          action,
          provider_http_status: result.status,
          provider_write_performed: true,
          money_movement: true,
          route_key: route.route_key,
          readback_pass: readback.status >= 200 && readback.status < 300,
          result: readback.status >= 200 && readback.status < 300 ? safeTransfer(readback.data) : { transfer_id: id },
          reversal_id: result.data?.id ?? null,
          raw_secret_export: false,
        });
      }
    } else {
      return json({
        error: "unsupported_action",
        allowed: ["platform_account", "connected_account", "payment_method_configurations", "product", "price", "payment_intent", "transfer_readback", "create_transfer", "reverse_transfer"],
      }, 400);
    }

    if (result.status < 200 || result.status >= 300) {
      return json({
        service: "stripe-production-control",
        action,
        provider_http_status: result.status,
        error: result.data?.error?.type ?? "provider_operation_failed",
        message: result.data?.error?.message ?? null,
        raw_secret_export: false,
      }, 502);
    }

    let safe = result.data;
    if (action === "platform_account" || action === "connected_account") safe = safeAccount(result.data);
    if (action === "transfer_readback") safe = safeTransfer(result.data);
    return json({
      service: "stripe-production-control",
      version: "1.2.1",
      action,
      provider_http_status: result.status,
      result: safe,
      provider_write_performed: false,
      money_movement: false,
      raw_secret_export: false,
    });
  } catch (error) {
    return json({ error: "stripe_control_failed", detail: error instanceof Error ? error.message : "unknown", raw_secret_export: false }, 500);
  }
});
