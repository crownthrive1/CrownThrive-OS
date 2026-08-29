import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const TARGET_URL = `${SUPABASE_URL}/functions/v1/penta-discovery`;
const MAX_RESPONSE_BYTES = 512 * 1024;
const REQUEST_TIMEOUT_MS = 20_000;

const EXPECTED = Object.freeze({
  runtime_component: "penta-discovery-edge",
  edge_slug: "penta-discovery",
  runtime_release: "ct.penta.discovery.runtime.2.0.1",
  name: "PentaDiscovery",
  service: "ct.penta.discovery.family.v2",
  contract_version: "2.0.0",
  stable_contract_version: "1.0.0",
  economic_version: "2.0.0",
  packet_protocol_version: "3.0.0",
  packet_contract: "crownthrive.penta.event.v1",
  fabric_contract: "crownthrive.pentafabric.v1",
  chlom_bridge: "crownthrive.chlom.pentafabric.economy.v2",
  smart_treasury: "penta.treasury",
  penta_pay: "penta.pay",
  auth_contract: "gateway-jwt+exact-service-role+legacy-service-role-v1",
  authority_created: false,
  provider_money_movement_inherited: false,
});

type JsonRecord = Record<string, unknown>;

function jsonResponse(status: number, body: JsonRecord, requestId: string): Response {
  return new Response(JSON.stringify({ ...body, request_id: requestId }), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
      "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
      "x-request-id": requestId,
    },
  });
}

function runtimeHeaders(schema = "public"): HeadersInit {
  return {
    apikey: SERVICE_ROLE_KEY,
    authorization: `Bearer ${SERVICE_ROLE_KEY}`,
    "content-type": "application/json",
    accept: "application/json",
    ...(schema !== "public"
      ? { "accept-profile": schema, "content-profile": schema }
      : {}),
  };
}

async function readLimited(response: Response): Promise<string> {
  const declared = Number(response.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_RESPONSE_BYTES) {
    throw new Error("TARGET_RESPONSE_TOO_LARGE");
  }
  if (!response.body) return "";
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        throw new Error("TARGET_RESPONSE_TOO_LARGE");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(output);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function rpc(name: string, body: JsonRecord): Promise<unknown> {
  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/rpc/${encodeURIComponent(name)}`,
    {
      method: "POST",
      headers: runtimeHeaders("penta_runtime"),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    },
  );
  const text = await readLimited(response);
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text.slice(0, 500);
    }
  }
  if (!response.ok) {
    throw new Error(`RUNTIME_RPC_REJECTED:${name}:${response.status}`);
  }
  return data;
}

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function validateHealth(payload: unknown, providerStatus: number): {
  passed: boolean;
  failure_code: string | null;
  observed: JsonRecord;
} {
  const root = record(payload);
  const contract = record(root.contract);
  const result = record(root.result);
  const nestedContract = record(result.contract);
  const effective = Object.keys(contract).length > 0 ? contract : nestedContract;

  const checks: JsonRecord = {
    provider_2xx: providerStatus >= 200 && providerStatus < 300,
    response_ok: root.ok === true,
    name: effective.name === EXPECTED.name,
    service: effective.service === EXPECTED.service,
    contract_version: effective.version === EXPECTED.contract_version,
    runtime_release: effective.runtime_release === EXPECTED.runtime_release,
    stable_contract_version:
      effective.stable_contract_version === EXPECTED.stable_contract_version,
    economic_version: effective.economic_version === EXPECTED.economic_version,
    packet_protocol_version:
      effective.packet_protocol_version === EXPECTED.packet_protocol_version,
    packet_contract: effective.packet_contract === EXPECTED.packet_contract,
    fabric_contract: effective.fabric_contract === EXPECTED.fabric_contract,
    chlom_bridge: effective.chlom_bridge === EXPECTED.chlom_bridge,
    smart_treasury: effective.smart_treasury === EXPECTED.smart_treasury,
    penta_pay: effective.penta_pay === EXPECTED.penta_pay,
    auth_contract: effective.auth_contract === EXPECTED.auth_contract,
    no_authority_creation: effective.authority_created === false,
    no_inherited_money_movement:
      effective.provider_money_movement_inherited === false,
  };

  const failed = Object.entries(checks)
    .filter(([, passed]) => passed !== true)
    .map(([key]) => key);

  return {
    passed: failed.length === 0,
    failure_code: failed.length === 0
      ? null
      : `RUNTIME_ATTESTATION_FAILED:${failed.join(",")}`,
    observed: {
      runtime_component: EXPECTED.runtime_component,
      edge_slug: EXPECTED.edge_slug,
      provider_status: providerStatus,
      checks,
      contract: effective,
      target_request_id:
        typeof root.request_id === "string" ? root.request_id : null,
      response_keys: Object.keys(root).sort(),
    },
  };
}

Deno.serve(async (req: Request) => {
  const requestId = crypto.randomUUID();
  if (req.method === "OPTIONS") return new Response(null, { status: 204 });
  if (req.method !== "GET" && req.method !== "POST") {
    return jsonResponse(405, { ok: false, error: "METHOD_NOT_ALLOWED" }, requestId);
  }
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
    return jsonResponse(503, { ok: false, error: "RUNTIME_BINDING_MISSING" }, requestId);
  }

  const probeKey = `penta-discovery-watchdog:${crypto.randomUUID()}`;
  const startedAt = new Date().toISOString();
  let claimed = false;

  try {
    const claim = record(await rpc("penta_discovery_watchdog_claim_probe_v1", {
      p_probe_key: probeKey,
      p_min_interval_seconds: 20,
    }));
    claimed = claim.claimed === true;
    if (!claimed) {
      return jsonResponse(200, {
        ok: true,
        state: "NOOP",
        reason: typeof claim.reason === "string" ? claim.reason : "PROBE_NOT_DUE",
        authority_created: false,
        provider_write_performed: false,
      }, requestId);
    }

    let targetStatus = 0;
    let targetText = "";
    let payload: unknown = null;
    let failureCode: string | null = null;

    try {
      const target = await fetch(TARGET_URL, {
        method: "POST",
        headers: runtimeHeaders(),
        body: JSON.stringify({ action: "health" }),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      targetStatus = target.status;
      targetText = await readLimited(target);
      try {
        payload = targetText ? JSON.parse(targetText) : null;
      } catch {
        failureCode = "TARGET_RESPONSE_NOT_JSON";
      }
    } catch (error) {
      failureCode = error instanceof Error
        ? error.message.slice(0, 200)
        : "TARGET_TRANSPORT_FAILED";
    }

    const validation = validateHealth(payload, targetStatus);
    const passed = failureCode === null && validation.passed;
    const effectiveFailure = failureCode ?? validation.failure_code;
    const completedAt = new Date().toISOString();
    const responseSha256 = await sha256(targetText);

    const guard = record(await rpc("penta_discovery_watchdog_record_probe_v1", {
      p_probe_key: probeKey,
      p_provider_status: targetStatus,
      p_passed: passed,
      p_failure_code: effectiveFailure,
      p_observed: validation.observed,
      p_response_sha256: responseSha256,
      p_target_request_id:
        typeof validation.observed.target_request_id === "string"
          ? validation.observed.target_request_id
          : null,
      p_started_at: startedAt,
      p_completed_at: completedAt,
    }));

    return jsonResponse(passed ? 200 : 503, {
      ok: passed,
      state: passed ? "PASS" : "DRIFT",
      runtime_component: EXPECTED.runtime_component,
      probe_key: probeKey,
      provider_status: targetStatus,
      failure_code: effectiveFailure,
      guard,
      authority_created: false,
      provider_write_performed: false,
      provider_money_movement: false,
    }, requestId);
  } catch (error) {
    const message = error instanceof Error ? error.message.slice(0, 300) : "WATCHDOG_FAILED";
    if (claimed) {
      try {
        await rpc("penta_discovery_watchdog_record_probe_v1", {
          p_probe_key: probeKey,
          p_provider_status: 0,
          p_passed: false,
          p_failure_code: message,
          p_observed: {
            runtime_component: EXPECTED.runtime_component,
            watchdog_failure: true,
          },
          p_response_sha256: await sha256(""),
          p_target_request_id: null,
          p_started_at: startedAt,
          p_completed_at: new Date().toISOString(),
        });
      } catch {
        // The outer response remains fail-closed even when evidence persistence fails.
      }
    }
    return jsonResponse(503, {
      ok: false,
      state: "HOLD",
      error: message,
      authority_created: false,
      provider_write_performed: false,
      provider_money_movement: false,
    }, requestId);
  }
});
