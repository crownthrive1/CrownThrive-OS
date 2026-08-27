import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
const DOMAIN = "relay.crownthrive.com";
const ROUTE = `mailgun:${DOMAIN}`;
const POLICY_ID = "ct.pentamailer.policy.mailgun-delivery-resilience.v1";
const POLICY_VERSION = "1.0.0";
const AUTHORITY_REF = "ct-founder-directive-pentamail-provider-probation-20260826-v1";
const PUBLIC_ADMIN_EMAILS = new Set(["contact@crownthrive.com"]);
const FROM_LOCAL = new Set(["thivebase", "heartbeat", "notifications", "noreply", "pentamail"]);

type JsonRecord = Record<string, unknown>;

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

async function rpc<T = JsonRecord>(name: string, body: JsonRecord = {}): Promise<T> {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: SERVICE_ROLE_KEY,
      authorization: `Bearer ${SERVICE_ROLE_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data: unknown = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // Retain a bounded error string only.
  }
  if (!response.ok) {
    throw new Error(`${name}:${response.status}:${typeof data === "string" ? data.slice(0, 300) : JSON.stringify(data)}`);
  }
  return data as T;
}

async function actor(req: Request) {
  const raw = req.headers.get("authorization") ?? "";
  const token = raw.toLowerCase().startsWith("bearer ") ? raw.slice(7).trim() : "";
  if (!token) return null;
  if (token === SERVICE_ROLE_KEY) return { email: "service_role", service: true };
  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: ANON_KEY, authorization: `Bearer ${token}` },
  });
  if (!response.ok) return null;
  const user = await response.json();
  const email = String(user?.email ?? "").toLowerCase();
  try {
    const allowed = PUBLIC_ADMIN_EMAILS.has(email) || await rpc<boolean>(
      "penta_mail_admin_allowed_v1",
      { p_recipient: email },
    );
    return allowed ? { email, service: false } : null;
  } catch {
    return null;
  }
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((part) => part.toString(16).padStart(2, "0")).join("");
}

function retryAfterSeconds(value: string) {
  const match = value.match(/enabled\s+in\s+(\d{1,6})\s+seconds?/i);
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

async function secret() {
  const value = await rpc("mailgun_relay_adapter_secret");
  const credential = String(value?.credential ?? "");
  if (!credential) throw new Error("credential_missing");
  return credential;
}

async function providerHealth() {
  const credential = await secret();
  const started = Date.now();
  const response = await fetch(`https://api.mailgun.net/v3/domains/${DOMAIN}/sending_queues`, {
    headers: { authorization: `Basic ${btoa(`api:${credential}`)}` },
    signal: AbortSignal.timeout(15000),
  });
  const text = await response.text();
  let provider: JsonRecord = {};
  try {
    provider = text ? JSON.parse(text) : {};
  } catch {
    provider = {};
  }
  const regularDisabled = provider?.regular && typeof provider.regular === "object"
    ? (provider.regular as JsonRecord).is_disabled !== false
    : true;
  const scheduledDisabled = provider?.scheduled && typeof provider.scheduled === "object"
    ? (provider.scheduled as JsonRecord).is_disabled !== false
    : true;
  const enabled = response.ok && !regularDisabled && !scheduledDisabled;
  const responseSha = await sha256(`${response.status}\n${text}`);
  const readbackEventId = `mailgun-sending-queues:${crypto.randomUUID()}`;
  const readback = await rpc("penta_mail_record_mailgun_readback_v3", {
    p_readback_event_id: readbackEventId,
    p_enabled: enabled,
    p_regular_disabled: regularDisabled,
    p_scheduled_disabled: scheduledDisabled,
    p_provider_http_status: response.status,
    p_response_sha256: responseSha,
    p_adapter_context: {
      readback_event_id: readbackEventId,
      provider_route_id: ROUTE,
      domain: DOMAIN,
      region: "us",
      api_base: "https://api.mailgun.net",
      probe_started_at: new Date(started).toISOString(),
      observed_at: new Date().toISOString(),
      latency_ms: Date.now() - started,
      provider_call_made: true,
      rate_limit: {
        limit: response.headers.get("x-ratelimit-limit"),
        remaining: response.headers.get("x-ratelimit-remaining"),
        reset: response.headers.get("x-ratelimit-reset"),
      },
    },
  });
  return {
    ok: response.ok,
    provider_status: response.status,
    enabled,
    regular_disabled: regularDisabled,
    scheduled_disabled: scheduledDisabled,
    response_sha256: responseSha,
    control: readback,
    raw_provider_body_retained: false,
    raw_secret_exposed: false,
  };
}

Deno.serve(async (req: Request) => {
  let providerCallMade = false;
  try {
    if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    const authenticated = await actor(req);
    if (!authenticated) return json({ error: "admin_required" }, 403);
    const body = await req.json().catch(() => ({}));
    const action = String(body?.action ?? "");

    if (action === "health") {
      const control = await rpc("penta_mail_provider_status_v1", { p_trigger_ref: null });
      return json({
        service: "mailgun-relay-control",
        version: "1.2.0",
        stage: "production_internal",
        domain: DOMAIN,
        provider_route_id: ROUTE,
        send_scope: "internal_allowlist_only",
        rolling_hour_limit: 10,
        rate_identity: "global Mailgun route + causal trigger",
        policy_id: POLICY_ID,
        policy_version: POLICY_VERSION,
        control,
        raw_secret_exposed: false,
      });
    }

    if (action === "provider_health") return json(await providerHealth());
    if (action !== "send_internal") return json({ error: "unknown_action" }, 400);

    const to = String(body?.to ?? "").toLowerCase().trim();
    const local = String(body?.from_local ?? "thivebase").toLowerCase().trim();
    const subject = String(body?.subject ?? "").trim();
    const messageText = String(body?.text ?? "").trim();
    const triggerRef = String(body?.trigger_ref ?? `mailgun-relay:${local}`).trim();
    const requestKey = String(body?.request_key ?? `edge:${crypto.randomUUID()}`).trim();

    const recipientAllowed = await rpc<boolean>("penta_mail_recipient_allowed_v1", { p_recipient: to });
    if (!recipientAllowed) return json({ error: "recipient_not_allowlisted" }, 403);
    if (!FROM_LOCAL.has(local)) return json({ error: "from_local_not_allowlisted" }, 403);
    if (!subject || subject.length > 180 || !messageText || messageText.length > 60000) {
      return json({ error: "invalid_message_shape" }, 400);
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$/.test(triggerRef)) {
      return json({ error: "invalid_trigger_ref" }, 400);
    }
    if (!requestKey || requestKey.length > 240) return json({ error: "invalid_request_key" }, 400);

    const reservation = await rpc("penta_mail_reserve_mailgun_rate_v2", {
      p_request_key: requestKey,
      p_trigger_ref: triggerRef,
    });
    if (reservation?.allowed !== true) {
      const reason = String(reservation?.reason ?? "rate_or_control_denied");
      const status = ["rolling_hour_limit", "controlled_release_batch_limit"].includes(reason) ? 429 : reason === "trigger_probation" ? 423 : 503;
      return json({
        ok: false,
        error: reason,
        control: reservation,
        trigger_ref: triggerRef,
        provider_call_made: false,
        raw_secret_exposed: false,
      }, status);
    }

    const credential = await secret();
    const form = new FormData();
    form.set("from", `CrownThrive ${local} <${local}@${DOMAIN}>`);
    form.set("to", to);
    form.set("subject", subject);
    form.set("text", messageText);
    const payloadSha = await sha256(JSON.stringify({
      domain: DOMAIN,
      from_local: local,
      recipient: to,
      subject,
      text: messageText,
      trigger_ref: triggerRef,
    }));
    const providerAttemptId = crypto.randomUUID();
    const attemptStart = await rpc("penta_mail_start_mailgun_attempt_v1", {
      p_request_key: requestKey,
      p_trigger_ref: triggerRef,
      p_payload_sha256: payloadSha,
      p_attempt_id: providerAttemptId,
    });
    if (attemptStart?.allowed !== true) {
      return json({
        ok: false,
        error: String(attemptStart?.reason ?? "provider_attempt_not_authorized"),
        control: attemptStart,
        trigger_ref: triggerRef,
        provider_call_made: false,
        reconciliation_required: attemptStart?.reconciliation_required === true,
        raw_secret_exposed: false,
      }, 503);
    }
    const started = Date.now();
    providerCallMade = true;
    let response: Response;
    try {
      response = await fetch(`https://api.mailgun.net/v3/${DOMAIN}/messages`, {
        method: "POST",
        headers: { authorization: `Basic ${btoa(`api:${credential}`)}` },
        body: form,
        signal: AbortSignal.timeout(30000),
      });
    } catch {
      const outcomeSha = await sha256(`provider_outcome_unknown|${providerAttemptId}|${payloadSha}`);
      await rpc("penta_mail_record_mailgun_attempt_outcome_v1", {
        p_attempt_id: providerAttemptId,
        p_outcome_state: "ambiguous",
        p_provider_http_status: null,
        p_provider_message_id: null,
        p_response_sha256: outcomeSha,
        p_details: { reason_code: "provider_outcome_unknown", timeout_ms: 30000 },
      });
      return json({
        ok: false,
        error: "provider_outcome_unknown",
        provider_attempt_id: providerAttemptId,
        trigger_ref: triggerRef,
        provider_call_made: true,
        reconciliation_required: true,
        response_sha256: outcomeSha,
        raw_secret_exposed: false,
      }, 504);
    }
    const responseText = await response.text();
    let provider: JsonRecord = {};
    try {
      provider = responseText ? JSON.parse(responseText) : {};
    } catch {
      provider = { message: responseText.slice(0, 300) };
    }
    const providerMessage = String(provider?.message ?? "").slice(0, 300);
    const providerId = String(provider?.id ?? "").slice(0, 500) || null;
    const responseSha = await sha256(`${response.status}\n${responseText}`);
    const probation = authenticatedMailgunProbation(response.status, providerMessage);
    let probationControl: JsonRecord | null = null;
    if (probation) {
      probationControl = await rpc("penta_mail_accept_mailgun_probation_v3", {
        p_provider_event_id: `mailgun-api:${providerAttemptId}`,
        p_provider_event_sha256: responseSha,
        p_trigger_ref: triggerRef,
        p_retry_after_seconds: probation.retry_after_seconds,
        p_evidence_kind: "authenticated_provider_response",
        p_authority_ref: AUTHORITY_REF,
      });
    }
    await rpc("penta_mail_record_mailgun_attempt_outcome_v1", {
      p_attempt_id: providerAttemptId,
      p_outcome_state: probation ? "probation_detected" : response.ok ? "provider_accepted" : "definitive_failure",
      p_provider_http_status: response.status,
      p_provider_message_id: providerId,
      p_response_sha256: responseSha,
      p_details: {
        reason_code: probation ? "mailgun_account_probation_temporarily_disabled" : response.ok ? "provider_accepted" : "provider_rejected",
        retry_after_seconds: probation?.retry_after_seconds ?? null,
        latency_ms: Date.now() - started,
        rate_limit: {
          limit: response.headers.get("x-ratelimit-limit"),
          remaining: response.headers.get("x-ratelimit-remaining"),
          reset: response.headers.get("x-ratelimit-reset"),
        },
      },
    });
    await rpc("integration_record_request", {
      p_service_id: "mailgun_relay",
      p_operation_key: "messages.send_internal",
      p_http_method: "POST",
      p_path_template: `/v3/${DOMAIN}/messages`,
      p_http_status: response.status,
      p_success: response.ok,
      p_actor: `${authenticated.email}:${local}`,
      p_latency_ms: Date.now() - started,
      p_response_sha256: responseSha,
      p_notes: `internal_allowlist_only:${local}:global_limit=10/hour:trigger=${triggerRef}`,
    });
    return json({
      ok: response.ok,
      provider_status: response.status,
      id: providerId,
      provider_reason_code: probation ? "mailgun_account_probation_temporarily_disabled" : response.ok ? "provider_accepted" : "provider_rejected",
      retry_after_seconds: probation?.retry_after_seconds ?? null,
      provider_attempt_id: providerAttemptId,
      trigger_ref: triggerRef,
      provider_call_made: true,
      provider_probation_detected: probation !== null,
      control: probationControl,
      response_sha256: responseSha,
      raw_secret_exposed: false,
    }, response.ok ? 200 : 502);
  } catch (error) {
    return json({
      ok: false,
      error: error instanceof Error ? error.message : "mailgun_relay_error",
      provider_call_made: providerCallMade,
      raw_secret_exposed: false,
    }, 500);
  }
});
