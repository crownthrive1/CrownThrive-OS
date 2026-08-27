import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BASE = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const DOMAIN = "relay.crownthrive.com";
const VERSION = "1.0.0";
const AUTHORITY_REF = "ct-founder-directive-pentamarketer-locticians-20260827-v1";
const SERVER = {
  name: "PentaMarketer Delivery",
  service: "ct.penta.marketer.delivery.locticians.v1",
  canonicalAgent: "ct.ops.agent.email-attention",
  version: VERSION,
  production: true,
};

type JsonRecord = Record<string, unknown>;

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

function headers() {
  return {
    apikey: SERVICE,
    authorization: `Bearer ${SERVICE}`,
    "content-type": "application/json",
  };
}

async function rpc(name: string, body: JsonRecord = {}) {
  const response = await fetch(`${BASE}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data: any = text;
  try { data = text ? JSON.parse(text) : null; } catch { /* bounded text retained */ }
  if (!response.ok) throw new Error(`${name}:${response.status}:${typeof data === "string" ? data.slice(0, 500) : JSON.stringify(data).slice(0, 500)}`);
  return data;
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((part) => part.toString(16).padStart(2, "0")).join("");
}

function asText(value: unknown, max = 1000) {
  try { return JSON.stringify(value).slice(0, max); } catch { return String(value).slice(0, max); }
}

function retryAfterSeconds(message: string) {
  const match = message.match(/enabled\s+in\s+(\d{1,6})\s+seconds?/i);
  if (!match) return null;
  const seconds = Number(match[1]);
  return Number.isInteger(seconds) && seconds >= 1 && seconds <= 86400 ? seconds : null;
}

function authenticatedMailgunProbation(status: number, message: string) {
  if (![401, 403, 429].includes(status)) return null;
  const normalized = message.toLowerCase().replace(/\s+/g, " ").trim();
  const probation = normalized.includes("account is on probation") || normalized.includes("account on probation");
  const disabled = normalized.includes("temporarily disabled");
  const limit = normalized.includes("100 messages / hour") || normalized.includes("100 messages per hour");
  const retry = retryAfterSeconds(normalized);
  if (!(probation && disabled && limit) || retry === null) return null;
  return { retry_after_seconds: retry };
}

async function mailgunSecret() {
  const value = await rpc("mailgun_relay_adapter_secret");
  const credential = String(value?.credential ?? "");
  if (!credential) throw new Error("mailgun_credential_missing");
  return credential;
}

async function complete(message: any, ok: boolean, providerCallMade: boolean, providerStatus: number | null, providerId: string | null, error: string | null, retry = 900) {
  return await rpc("penta_mail_complete_outbox_v3", {
    p_message_id: message.message_id,
    p_lease_id: message.lease_id,
    p_ok: ok,
    p_provider_call_made: providerCallMade,
    p_provider_http_status: providerStatus,
    p_provider_message_id: providerId,
    p_error: error,
    p_retry_after_seconds: retry,
  });
}

async function sendOne(message: any, credential: string) {
  const authorization = await rpc("penta_marketer_delivery_authorized_v1", {
    p_message_id: message.message_id,
    p_recipient: message.recipient,
  });
  if (authorization?.authorized !== true) {
    const hold = await rpc("penta_marketer_hold_outbox_v1", {
      p_message_id: message.message_id,
      p_reason: "penta_marketer_delivery_authorization_denied",
      p_control: authorization ?? {},
    });
    return { message_id: message.message_id, ok: false, provider_call_made: false, state: "held", authorization, hold };
  }

  const requestKey = `penta-marketer:${message.message_id}`;
  const triggerRef = String(message.trigger_ref ?? "penta-marketer-locticians-claim");
  const reservation = await rpc("penta_mail_reserve_mailgun_rate_v2", {
    p_request_key: requestKey,
    p_trigger_ref: triggerRef,
  });
  if (reservation?.allowed !== true) {
    const reason = String(reservation?.reason ?? "rate_or_control_denied");
    const retryAt = Date.parse(String(reservation?.retry_at ?? ""));
    const retry = Number.isFinite(retryAt) && retryAt > Date.now() ? Math.max(60, Math.ceil((retryAt - Date.now()) / 1000)) : reason === "controlled_release_batch_limit" ? 60 : 900;
    const completion = await complete(message, false, false, null, null, asText({ error: reason, control: reservation }), retry);
    return { message_id: message.message_id, ok: false, provider_call_made: false, state: completion?.state, control: reservation };
  }

  const payloadSha = await sha256(JSON.stringify({
    domain: DOMAIN,
    from_local: "outreach",
    recipient: message.recipient,
    subject: message.subject,
    text: message.body_text,
    trigger_ref: triggerRef,
    campaign_ref: message.metadata?.campaign_ref ?? null,
  }));
  const attemptId = crypto.randomUUID();
  const attemptStart = await rpc("penta_mail_start_mailgun_attempt_v1", {
    p_request_key: requestKey,
    p_trigger_ref: triggerRef,
    p_payload_sha256: payloadSha,
    p_attempt_id: attemptId,
  });
  if (attemptStart?.allowed !== true) {
    const error = asText({ error: String(attemptStart?.reason ?? "provider_attempt_not_authorized"), control: attemptStart, reconciliation_required: attemptStart?.reconciliation_required === true });
    const completion = await complete(message, false, false, null, null, error, 900);
    return { message_id: message.message_id, ok: false, provider_call_made: false, state: completion?.state, control: attemptStart };
  }

  const form = new FormData();
  form.set("from", `CrownThrive <outreach@${DOMAIN}>`);
  form.set("to", String(message.recipient));
  form.set("subject", String(message.subject));
  form.set("text", String(message.body_text));
  form.set("h:Reply-To", "contact@crownthrive.com");
  form.set("h:List-Unsubscribe", "<mailto:contact@crownthrive.com?subject=OPT%20OUT>");
  form.set("o:tag", "locticians-claim");
  form.set("v:campaign_ref", String(message.metadata?.campaign_ref ?? "ct.pentamarketer.locticians.claim.20260827.v1"));
  form.set("v:schedule_id", String(message.metadata?.schedule_id ?? ""));

  const started = Date.now();
  let response: Response;
  try {
    response = await fetch(`https://api.mailgun.net/v3/${DOMAIN}/messages`, {
      method: "POST",
      headers: { authorization: `Basic ${btoa(`api:${credential}`)}` },
      body: form,
      signal: AbortSignal.timeout(30000),
    });
  } catch {
    const outcomeSha = await sha256(`provider_outcome_unknown|${attemptId}|${payloadSha}`);
    await rpc("penta_mail_record_mailgun_attempt_outcome_v1", {
      p_attempt_id: attemptId,
      p_outcome_state: "ambiguous",
      p_provider_http_status: null,
      p_provider_message_id: null,
      p_response_sha256: outcomeSha,
      p_details: { reason_code: "provider_outcome_unknown", timeout_ms: 30000, route: "PentaMarketer" },
    });
    const completion = await complete(message, false, true, null, null, asText({ error: "provider_outcome_unknown", reconciliation_required: true, provider_attempt_id: attemptId }), 900);
    return { message_id: message.message_id, ok: false, provider_call_made: true, state: completion?.state, reconciliation_required: true, provider_attempt_id: attemptId };
  }

  const responseText = await response.text();
  let provider: JsonRecord = {};
  try { provider = responseText ? JSON.parse(responseText) : {}; } catch { provider = { message: responseText.slice(0, 300) }; }
  const providerMessage = String(provider?.message ?? "").slice(0, 300);
  const providerId = String(provider?.id ?? "").slice(0, 500) || null;
  const responseSha = await sha256(`${response.status}\n${responseText}`);
  const probation = authenticatedMailgunProbation(response.status, providerMessage);
  let probationControl: JsonRecord | null = null;
  if (probation) {
    probationControl = await rpc("penta_mail_accept_mailgun_probation_v3", {
      p_provider_event_id: `mailgun-api:${attemptId}`,
      p_provider_event_sha256: responseSha,
      p_trigger_ref: triggerRef,
      p_retry_after_seconds: probation.retry_after_seconds,
      p_evidence_kind: "authenticated_provider_response",
      p_authority_ref: AUTHORITY_REF,
    });
  }
  await rpc("penta_mail_record_mailgun_attempt_outcome_v1", {
    p_attempt_id: attemptId,
    p_outcome_state: probation ? "probation_detected" : response.ok ? "provider_accepted" : "definitive_failure",
    p_provider_http_status: response.status,
    p_provider_message_id: providerId,
    p_response_sha256: responseSha,
    p_details: {
      reason_code: probation ? "mailgun_account_probation_temporarily_disabled" : response.ok ? "provider_accepted" : "provider_rejected",
      retry_after_seconds: probation?.retry_after_seconds ?? null,
      latency_ms: Date.now() - started,
      route: "PentaMarketer",
      campaign_ref: message.metadata?.campaign_ref ?? null,
      rate_limit: {
        limit: response.headers.get("x-ratelimit-limit"),
        remaining: response.headers.get("x-ratelimit-remaining"),
        reset: response.headers.get("x-ratelimit-reset"),
      },
    },
  });
  await rpc("integration_record_request", {
    p_service_id: "mailgun_relay",
    p_operation_key: "messages.send_locticians_claim",
    p_http_method: "POST",
    p_path_template: `/v3/${DOMAIN}/messages`,
    p_http_status: response.status,
    p_success: response.ok,
    p_actor: "ct.ops.agent.email-attention:PentaMarketer",
    p_latency_ms: Date.now() - started,
    p_response_sha256: responseSha,
    p_notes: `bounded_pentamarketer:daily_cap=10:campaign=${message.metadata?.campaign_ref ?? "unknown"}:trigger=${triggerRef}`,
  });
  const completion = await complete(message, response.ok, true, response.status, providerId, response.ok ? null : asText({ error: "provider_rejected", provider_reason_code: probation ? "mailgun_account_probation_temporarily_disabled" : "provider_rejected", control: probationControl }), probation?.retry_after_seconds ?? 900);
  return {
    message_id: message.message_id,
    schedule_id: message.metadata?.schedule_id ?? null,
    recipient_ref: await sha256(String(message.recipient).toLowerCase()),
    ok: response.ok,
    provider_call_made: true,
    provider_status: response.status,
    provider_message_id: providerId,
    provider_attempt_id: attemptId,
    provider_probation_detected: probation !== null,
    state: completion?.state,
    raw_recipient_logged: false,
  };
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return respond({ ok: false, error: "POST_required", server: SERVER }, 405);
    const token = req.headers.get("x-penta-marketer-token") ?? "";
    if (!token || await rpc("penta_marketer_edge_authorize_v1", { p_token: token }) !== true) {
      return respond({ ok: false, error: "penta_marketer_authorization_required", server: SERVER }, 403);
    }
    const body = await req.json().catch(() => ({}));
    const action = String(body?.action ?? "deliver").toLowerCase();
    if (action !== "deliver") return respond({ ok: false, error: "unsupported_action", allowed: ["deliver"], server: SERVER }, 400);
    const batch = Math.max(1, Math.min(Number(body?.batch ?? 2) || 2, 2));
    const claimed = await rpc("penta_marketer_claim_outbox_v1", { p_limit: batch });
    const messages = Array.isArray(claimed) ? claimed : [];
    if (!messages.length) {
      return respond({ ok: true, server: SERVER, action, claimed: 0, processed: 0, results: [], state: "NO_DUE_AUTHORIZED_MESSAGES", at: new Date().toISOString() });
    }
    const credential = await mailgunSecret();
    const results: unknown[] = [];
    for (const message of messages) {
      const result = await sendOne(message, credential);
      results.push(result);
      if ((result as any)?.provider_probation_detected === true) break;
    }
    return respond({ ok: true, server: SERVER, action, claimed: messages.length, processed: results.length, results, raw_secret_exposed: false, raw_recipient_logged: false, at: new Date().toISOString() });
  } catch (error) {
    return respond({ ok: false, service: SERVER.service, error: error instanceof Error ? error.message : String(error), raw_secret_exposed: false }, 500);
  }
});
