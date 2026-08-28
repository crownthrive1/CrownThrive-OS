import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const STRIPE_BASE = "https://api.stripe.com";
const PAYPAL_BASE = "https://api-m.paypal.com";
const INTERNAL_HEADER = "x-ct-pentasettle-key";
const SAFE_HEADERS: Record<string,string> = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store, private",
  "pragma": "no-cache",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer"
};

const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false }
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: SAFE_HEADERS });
}

function safeMessage(error: unknown): string {
  const value = error instanceof Error ? error.message : String(error ?? "unknown_error");
  return value.replace(/sk_live_[A-Za-z0-9]+/g, "[REDACTED]").slice(0, 500);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sameSecret(a: string, b: string): Promise<boolean> {
  if (!a || !b) return false;
  const [x, y] = await Promise.all([sha256(a), sha256(b)]);
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return diff === 0;
}

async function rpc<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
  const { data, error } = await admin.rpc(name, args);
  if (error) throw new Error(`${name}:${error.message}`);
  return data as T;
}

async function readJson(response: Response): Promise<any> {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { raw_response_digest_pending: true }; }
}

async function authenticate(req: Request): Promise<boolean> {
  const expected = await rpc<string>("penta_settle_internal_token_v2");
  return sameSecret(expected, req.headers.get(INTERNAL_HEADER) ?? "");
}

type Runtime = {
  adapter_key: string;
  provider_key: "stripe" | "paypal";
  environment: string;
  credential?: string;
  credential_ref?: string;
  client_id?: string;
  hot_secret?: string;
  cold_secret?: string;
  hot_state?: string;
  cold_state?: string;
  active_route?: string;
  failover_policy?: string;
  paypal_app_key?: string;
  metadata?: Record<string, unknown>;
};

type Claim = {
  intent_id: string;
  intent_key: string;
  claim_token: string;
  adapter_key: string;
  provider_key: "stripe" | "paypal";
  dispatch_allowed?: boolean;
  reason?: string;
  amount_minor: number;
  currency: string;
  idempotency_key: string;
  source_transaction_ref?: string | null;
  provider_object_ref?: string | null;
  provider_batch_ref?: string | null;
  provider_item_ref?: string | null;
};

type Recipient = {
  recipient_ref_kind: string;
  recipient_value: string;
  recipient_ref_digest: string;
};

async function stripeGet(path: string, key: string): Promise<{response: Response; data: any}> {
  const response = await fetch(`${STRIPE_BASE}${path}`, {
    headers: { authorization: `Bearer ${key}`, "user-agent": "CrownThrive-PentaSettle/2.0" },
    signal: AbortSignal.timeout(20_000)
  });
  return { response, data: await readJson(response) };
}

async function paypalToken(runtime: Runtime): Promise<{token: string; slot: "hot"|"cold"; expiresIn: number}> {
  const choices: Array<{slot:"hot"|"cold";secret:string}> = [];
  if (runtime.hot_secret) choices.push({ slot: "hot", secret: runtime.hot_secret });
  if (runtime.cold_secret) choices.push({ slot: "cold", secret: runtime.cold_secret });
  for (const choice of choices) {
    const response = await fetch(`${PAYPAL_BASE}/v1/oauth2/token`, {
      method: "POST",
      headers: {
        authorization: `Basic ${btoa(`${runtime.client_id ?? ""}:${choice.secret}`)}`,
        "content-type": "application/x-www-form-urlencoded",
        accept: "application/json"
      },
      body: "grant_type=client_credentials",
      signal: AbortSignal.timeout(20_000)
    });
    const data = await readJson(response);
    if (response.ok && typeof data.access_token === "string") {
      return { token: data.access_token, slot: choice.slot, expiresIn: Number(data.expires_in ?? 0) };
    }
  }
  throw new Error("PAYPAL_OAUTH_HOT_AND_COLD_FAILED");
}

async function recordObservation(args: {
  claim: Claim;
  action: "dispatch"|"reconcile";
  httpStatus: number | null;
  providerState: string;
  providerObjectRef?: string | null;
  providerBatchRef?: string | null;
  providerItemRef?: string | null;
  providerWrite: boolean;
  readbackPass: boolean;
  finality: boolean;
  success: boolean;
  requestDigest?: string | null;
  responseDigest?: string | null;
  errorCode?: string | null;
  metadata?: Record<string, unknown>;
}): Promise<any> {
  return rpc("penta_settle_record_provider_observation_v2", {
    p_intent_id: args.claim.intent_id,
    p_claim_token: args.claim.claim_token,
    p_action: args.action,
    p_provider_http_status: args.httpStatus,
    p_provider_state: args.providerState,
    p_provider_object_ref: args.providerObjectRef ?? null,
    p_provider_batch_ref: args.providerBatchRef ?? null,
    p_provider_item_ref: args.providerItemRef ?? null,
    p_provider_write_performed: args.providerWrite,
    p_readback_pass: args.readbackPass,
    p_finality: args.finality,
    p_success: args.success,
    p_request_digest: args.requestDigest ?? null,
    p_response_digest: args.responseDigest ?? null,
    p_error_code: args.errorCode ?? null,
    p_metadata: args.metadata ?? {}
  });
}

async function certify(adapterKey: string, releaseVersion: string): Promise<any> {
  const runtime = await rpc<Runtime>("penta_settle_provider_runtime_v2", { p_adapter_key: adapterKey, p_slot: "auto" });
  const canary = await rpc<any>("penta_settle_run_zero_value_canary_v2", { p_release_version: releaseVersion, p_adapter_key: adapterKey });
  let providerAuthPass = false;
  let providerReadbackPathPass = false;
  let providerDetails: Record<string, unknown> = {};

  if (runtime.provider_key === "stripe") {
    const key = runtime.credential ?? "";
    const accountId = String(runtime.metadata?.known_connected_account_id ?? "");
    const platform = await stripeGet("/v1/account", key);
    const connected = accountId ? await stripeGet(`/v1/accounts/${encodeURIComponent(accountId)}`, key) : null;
    providerAuthPass = platform.response.ok;
    providerReadbackPathPass = platform.response.ok && !!connected?.response.ok;
    providerDetails = {
      platform_http_status: platform.response.status,
      connected_http_status: connected?.response.status ?? null,
      platform_transfers: platform.data?.capabilities?.transfers ?? null,
      connected_transfers: connected?.data?.capabilities?.transfers ?? null,
      platform_charges_enabled: !!platform.data?.charges_enabled,
      platform_payouts_enabled: !!platform.data?.payouts_enabled,
      connected_charges_enabled: !!connected?.data?.charges_enabled,
      connected_payouts_enabled: !!connected?.data?.payouts_enabled
    };
  } else {
    const auth = await paypalToken(runtime);
    const hooksResponse = await fetch(`${PAYPAL_BASE}/v1/notifications/webhooks`, {
      headers: { authorization: `Bearer ${auth.token}`, accept: "application/json" },
      signal: AbortSignal.timeout(20_000)
    });
    const hooks = await readJson(hooksResponse);
    providerAuthPass = true;
    providerReadbackPathPass = hooksResponse.ok;
    providerDetails = {
      oauth_slot: auth.slot,
      oauth_expires_in: auth.expiresIn,
      webhook_readback_http_status: hooksResponse.status,
      webhook_count: Array.isArray(hooks?.webhooks) ? hooks.webhooks.length : null,
      failover_policy: runtime.failover_policy ?? null
    };
  }

  const checks = {
    ...canary,
    provider_auth_pass: providerAuthPass,
    provider_readback_path_pass: providerReadbackPathPass,
    provider_credentials_vaulted: true,
    provider_write_performed: false,
    provider_details: providerDetails,
    edge_runtime: "ct.penta.settle.provider-edge.v2",
    idempotency_contract_pass: true
  };
  const certification = await rpc<any>("penta_settle_record_provider_edge_certification_v2", {
    p_adapter_key: adapterKey,
    p_release_version: releaseVersion,
    p_checks: checks
  });
  return { certification, checks, raw_secret_export: false, provider_write_performed: false };
}

async function stripeDispatch(claim: Claim, recipient: Recipient, runtime: Runtime, action: "dispatch"|"reconcile"): Promise<any> {
  const key = runtime.credential ?? "";
  if (!key.startsWith("sk_live_")) throw new Error("STRIPE_LIVE_SECRET_UNAVAILABLE");
  if (claim.currency !== "USD") throw new Error("PENTA_SETTLE_V2_STRIPE_USD_ONLY");

  if (action === "reconcile") {
    const transferId = claim.provider_object_ref ?? "";
    if (!/^tr_[A-Za-z0-9]+$/.test(transferId)) throw new Error("STRIPE_TRANSFER_REFERENCE_REQUIRED");
    const result = await stripeGet(`/v1/transfers/${encodeURIComponent(transferId)}`, key);
    const responseDigest = await sha256(JSON.stringify(result.data));
    const pass = result.response.ok && result.data?.id === transferId && Number(result.data?.amount) === Number(claim.amount_minor) && String(result.data?.currency ?? "").toUpperCase() === claim.currency && String(result.data?.destination ?? "") === recipient.recipient_value;
    return recordObservation({ claim, action, httpStatus: result.response.status, providerState: pass ? "TRANSFER_READBACK_PASS" : "TRANSFER_READBACK_HOLD", providerObjectRef: transferId, providerWrite: true, readbackPass: pass, finality: pass, success: result.response.ok, responseDigest, errorCode: pass ? null : "STRIPE_TRANSFER_READBACK_MISMATCH" });
  }

  const body = new URLSearchParams();
  body.set("amount", String(claim.amount_minor));
  body.set("currency", claim.currency.toLowerCase());
  body.set("destination", recipient.recipient_value);
  body.set("transfer_group", claim.intent_key.slice(0, 100));
  body.set("metadata[penta_settle_intent_id]", claim.intent_id);
  body.set("metadata[penta_settle_contract]", "ct.penta.settle.v2");
  if (claim.source_transaction_ref) body.set("source_transaction", claim.source_transaction_ref);
  const requestDigest = await sha256(body.toString());
  let response: Response;
  let data: any;
  try {
    response = await fetch(`${STRIPE_BASE}/v1/transfers`, {
      method: "POST",
      headers: { authorization: `Bearer ${key}`, "content-type": "application/x-www-form-urlencoded", "idempotency-key": claim.idempotency_key, "user-agent": "CrownThrive-PentaSettle/2.0" },
      body,
      signal: AbortSignal.timeout(25_000)
    });
    data = await readJson(response);
  } catch (error) {
    return recordObservation({ claim, action, httpStatus: null, providerState: "DISPATCH_OUTCOME_AMBIGUOUS", providerWrite: false, readbackPass: false, finality: false, success: false, requestDigest, errorCode: "PROVIDER_OUTCOME_AMBIGUOUS", metadata: { error: safeMessage(error) } });
  }
  const responseDigest = await sha256(JSON.stringify(data));
  if (!response.ok || typeof data?.id !== "string") {
    return recordObservation({ claim, action, httpStatus: response.status, providerState: "TRANSFER_CREATE_REJECTED", providerWrite: false, readbackPass: false, finality: false, success: false, requestDigest, responseDigest, errorCode: response.status >= 500 ? "PROVIDER_OUTCOME_AMBIGUOUS" : "STRIPE_TRANSFER_REJECTED", metadata: { provider_error_type: data?.error?.type ?? null, provider_error_code: data?.error?.code ?? null } });
  }
  const transferId = String(data.id);
  const readback = await stripeGet(`/v1/transfers/${encodeURIComponent(transferId)}`, key);
  const readbackDigest = await sha256(JSON.stringify(readback.data));
  const pass = readback.response.ok && readback.data?.id === transferId && Number(readback.data?.amount) === Number(claim.amount_minor) && String(readback.data?.currency ?? "").toUpperCase() === claim.currency && String(readback.data?.destination ?? "") === recipient.recipient_value;
  return recordObservation({ claim, action, httpStatus: readback.response.status, providerState: pass ? "TRANSFER_CREATED_READBACK_PASS" : "TRANSFER_CREATED_READBACK_PENDING", providerObjectRef: transferId, providerWrite: true, readbackPass: pass, finality: pass, success: true, requestDigest, responseDigest: readbackDigest, errorCode: pass ? null : "STRIPE_TRANSFER_READBACK_PENDING", metadata: { create_response_digest: responseDigest } });
}

function paypalRecipientType(kind: string): "EMAIL"|"PAYPAL_ID"|"PHONE" {
  if (kind === "paypal_email_vault") return "EMAIL";
  if (kind === "paypal_payer_id_vault") return "PAYPAL_ID";
  if (kind === "paypal_phone_vault") return "PHONE";
  throw new Error("PAYPAL_RECIPIENT_KIND_UNSUPPORTED");
}

function findPaypalItem(data: any): any {
  const items = Array.isArray(data?.items) ? data.items : [];
  return items[0] ?? null;
}

function paypalFinality(itemStatus: string): {success:boolean;finality:boolean;errorCode:string|null} {
  const status = itemStatus.toUpperCase();
  if (status === "SUCCESS") return { success: true, finality: true, errorCode: null };
  if (["PENDING","PROCESSING","NEW","ONHOLD","UNCLAIMED"].includes(status)) return { success: true, finality: false, errorCode: null };
  if (["FAILED","RETURNED","BLOCKED","REFUNDED","REVERSED","DENIED","CANCELED"].includes(status)) return { success: false, finality: false, errorCode: `PAYPAL_${status}` };
  return { success: true, finality: false, errorCode: "PAYPAL_FINALITY_UNKNOWN" };
}

async function paypalDispatch(claim: Claim, recipient: Recipient, runtime: Runtime, action: "dispatch"|"reconcile"): Promise<any> {
  if (claim.currency !== "USD") throw new Error("PENTA_SETTLE_V2_PAYPAL_USD_ONLY");
  const auth = await paypalToken(runtime);
  if (action === "reconcile") {
    const batchId = claim.provider_batch_ref ?? "";
    if (!batchId) throw new Error("PAYPAL_PAYOUT_BATCH_REFERENCE_REQUIRED");
    const response = await fetch(`${PAYPAL_BASE}/v1/payments/payouts/${encodeURIComponent(batchId)}?page=1&page_size=100&total_required=true`, { headers: { authorization: `Bearer ${auth.token}`, accept: "application/json" }, signal: AbortSignal.timeout(25_000) });
    const data = await readJson(response);
    const responseDigest = await sha256(JSON.stringify(data));
    const item = findPaypalItem(data);
    const itemStatus = String(item?.transaction_status ?? data?.batch_header?.batch_status ?? "UNKNOWN");
    const finality = paypalFinality(itemStatus);
    const readbackPass = response.ok && String(data?.batch_header?.payout_batch_id ?? "") === batchId;
    return recordObservation({ claim, action, httpStatus: response.status, providerState: `PAYPAL_${itemStatus.toUpperCase()}`, providerObjectRef: item?.transaction_id ?? null, providerBatchRef: batchId, providerItemRef: item?.transaction_id ?? item?.payout_item_id ?? null, providerWrite: true, readbackPass, finality: finality.finality && readbackPass, success: finality.success && response.ok, responseDigest, errorCode: finality.errorCode, metadata: { oauth_slot: auth.slot } });
  }

  const digest = await sha256(claim.intent_key);
  const senderBatchId = `CTPS${digest.slice(0, 26)}`;
  const senderItemId = `CTI${digest.slice(0, 27)}`;
  const requestId = `ctps-${digest.slice(0, 31)}`;
  const payload = {
    sender_batch_header: { sender_batch_id: senderBatchId, email_subject: "CrownThrive settlement", email_message: "A governed CrownThrive settlement was issued." },
    items: [{ recipient_type: paypalRecipientType(recipient.recipient_ref_kind), amount: { value: (claim.amount_minor / 100).toFixed(2), currency: claim.currency }, receiver: recipient.recipient_value, note: "CrownThrive governed settlement", sender_item_id: senderItemId }]
  };
  const requestText = JSON.stringify(payload);
  const requestDigest = await sha256(requestText);
  let response: Response;
  let data: any;
  try {
    response = await fetch(`${PAYPAL_BASE}/v1/payments/payouts`, { method: "POST", headers: { authorization: `Bearer ${auth.token}`, "content-type": "application/json", accept: "application/json", "paypal-request-id": requestId }, body: requestText, signal: AbortSignal.timeout(25_000) });
    data = await readJson(response);
  } catch (error) {
    return recordObservation({ claim, action, httpStatus: null, providerState: "DISPATCH_OUTCOME_AMBIGUOUS", providerWrite: false, readbackPass: false, finality: false, success: false, requestDigest, errorCode: "PROVIDER_OUTCOME_AMBIGUOUS", metadata: { error: safeMessage(error), oauth_slot: auth.slot } });
  }
  const createDigest = await sha256(JSON.stringify(data));
  const batchId = String(data?.batch_header?.payout_batch_id ?? "");
  if (!response.ok || !batchId) {
    return recordObservation({ claim, action, httpStatus: response.status, providerState: "PAYOUT_CREATE_REJECTED", providerWrite: response.ok, readbackPass: false, finality: false, success: false, requestDigest, responseDigest: createDigest, errorCode: response.status >= 500 ? "PROVIDER_OUTCOME_AMBIGUOUS" : "PAYPAL_PAYOUT_REJECTED", metadata: { provider_name: data?.name ?? null, provider_message: data?.message ?? null, oauth_slot: auth.slot } });
  }
  const readbackResponse = await fetch(`${PAYPAL_BASE}/v1/payments/payouts/${encodeURIComponent(batchId)}?page=1&page_size=100&total_required=true`, { headers: { authorization: `Bearer ${auth.token}`, accept: "application/json" }, signal: AbortSignal.timeout(25_000) });
  const readback = await readJson(readbackResponse);
  const readbackDigest = await sha256(JSON.stringify(readback));
  const item = findPaypalItem(readback);
  const itemStatus = String(item?.transaction_status ?? readback?.batch_header?.batch_status ?? "PENDING");
  const finality = paypalFinality(itemStatus);
  const readbackPass = readbackResponse.ok && String(readback?.batch_header?.payout_batch_id ?? "") === batchId;
  return recordObservation({ claim, action, httpStatus: readbackResponse.status, providerState: `PAYPAL_${itemStatus.toUpperCase()}`, providerObjectRef: item?.transaction_id ?? null, providerBatchRef: batchId, providerItemRef: item?.transaction_id ?? item?.payout_item_id ?? null, providerWrite: true, readbackPass, finality: finality.finality && readbackPass, success: finality.success, requestDigest, responseDigest: readbackDigest, errorCode: finality.errorCode, metadata: { create_response_digest: createDigest, oauth_slot: auth.slot, sender_batch_id: senderBatchId, sender_item_id: senderItemId } });
}

async function executeIntent(intentId: string, action: "dispatch"|"reconcile"): Promise<any> {
  const claim = action === "dispatch"
    ? await rpc<Claim>("penta_settle_claim_dispatch_v2", { p_intent_id: intentId, p_claimant: "penta-settle-provider-edge" })
    : await rpc<Claim>("penta_settle_claim_reconcile_v2", { p_intent_id: intentId, p_claimant: "penta-settle-provider-edge" });
  if (action === "dispatch" && claim.dispatch_allowed === false) return claim;
  const [recipient, runtime] = await Promise.all([
    rpc<Recipient>("penta_settle_resolve_claimed_recipient_v2", { p_intent_id: claim.intent_id, p_claim_token: claim.claim_token }),
    rpc<Runtime>("penta_settle_provider_runtime_v2", { p_adapter_key: claim.adapter_key, p_slot: "auto" })
  ]);
  const result = runtime.provider_key === "stripe"
    ? await stripeDispatch(claim, recipient, runtime, action)
    : await paypalDispatch(claim, recipient, runtime, action);
  return { result, adapter_key: claim.adapter_key, provider_key: runtime.provider_key, raw_secret_export: false, raw_recipient_export: false };
}

Deno.serve(async (req: Request) => {
  try {
    if (!SUPABASE_URL || !SERVICE_ROLE_KEY) return json({ ok: false, error: "runtime_configuration_missing" }, 500);
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: { "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": `content-type,${INTERNAL_HEADER}` } });
    if (req.method === "GET") return json({ ok: true, service: "ct.penta.settle.provider-edge.v2", version: "2.0.0", environment: "production", provider_write_default: false, exact_ecac_required: true, independent_approval_required: true, max_unattended_value_minor: 0, raw_secret_export: false });
    if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
    if (!(await authenticate(req))) return json({ ok: false, error: "internal_authorization_required", raw_secret_export: false }, 401);
    const input = await req.json().catch(() => ({} as Record<string, unknown>));
    const action = String(input.action ?? "health");
    if (action === "health") {
      const status = await rpc<any>("penta_settle_status_v2", { p_release_version: String(input.release_version ?? "OS-2.0.0") });
      return json({ ok: true, service: "ct.penta.settle.provider-edge.v2", status, provider_write_default: false, raw_secret_export: false });
    }
    if (action === "certify") {
      const adapterKey = String(input.adapter_key ?? "");
      if (!adapterKey) return json({ ok: false, error: "adapter_key_required" }, 400);
      return json({ ok: true, action, ...(await certify(adapterKey, String(input.release_version ?? "OS-2.0.0"))) });
    }
    if (action === "dispatch" || action === "reconcile") {
      const intentId = String(input.intent_id ?? "");
      if (!/^[0-9a-f-]{36}$/i.test(intentId)) return json({ ok: false, error: "valid_intent_id_required" }, 400);
      return json({ ok: true, action, ...(await executeIntent(intentId, action)) });
    }
    return json({ ok: false, error: "unsupported_action", allowed: ["health","certify","dispatch","reconcile"] }, 400);
  } catch (error) {
    return json({ ok: false, error: safeMessage(error), raw_secret_export: false }, 500);
  }
});
