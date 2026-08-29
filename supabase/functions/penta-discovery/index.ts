import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const VERSION = "2.0.0";
const STABLE_CONTRACT_VERSION = "1.0.0";
const ECONOMIC_VERSION = "2.0.0";
const PACKET_PROTOCOL_VERSION = "3.0.0";
const MAX_REQUEST_BYTES = 128 * 1024;
const MAX_FETCH_BYTES = 1_000_000;
const MAX_REDIRECTS = 3;
const HTTP_TIMEOUT_MS = 15_000;

type JsonRecord = Record<string, unknown>;

class SafeError extends Error {
  readonly code: string;
  readonly status: number;
  readonly detail?: JsonRecord;

  constructor(code: string, status = 400, detail?: JsonRecord) {
    super(code);
    this.name = "SafeError";
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}

const CONTRACT = Object.freeze({
  name: "PentaDiscovery",
  service: "ct.penta.discovery.family.v2",
  stable_contract_version: STABLE_CONTRACT_VERSION,
  economic_version: ECONOMIC_VERSION,
  packet_protocol_version: PACKET_PROTOCOL_VERSION,
  packet_contract: "crownthrive.penta.event.v1",
  fabric_contract: "crownthrive.pentafabric.v1",
  chlom_bridge: "crownthrive.chlom.pentafabric.economy.v2",
  smart_treasury: "penta.treasury",
  penta_pay: "penta.pay",
  version: VERSION,
  authority_created: false,
  provider_money_movement_inherited: false,
});

function responseJson(body: unknown, status = 200, requestId?: string): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
      "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
      ...(requestId ? { "x-request-id": requestId } : {}),
    },
  });
}

function serviceHeaders(schema = "public"): HeadersInit {
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

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
  return atob(padded);
}

function assertServiceRole(req: Request): void {
  const auth = req.headers.get("authorization") ?? "";
  if (!auth.toLowerCase().startsWith("bearer ")) {
    throw new SafeError("service_role_authorization_required", 403);
  }
  const token = auth.slice(7).trim();
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new SafeError("service_role_authorization_required", 403);
  }

  let payload: JsonRecord;
  try {
    payload = JSON.parse(decodeBase64Url(parts[1])) as JsonRecord;
  } catch {
    throw new SafeError("service_role_authorization_required", 403);
  }
  if (payload.role !== "service_role") {
    throw new SafeError("service_role_authorization_required", 403);
  }
}

async function readStream(
  stream: ReadableStream<Uint8Array> | null,
  maxBytes: number,
  limitCode: string,
): Promise<string> {
  if (!stream) return "";
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        throw new SafeError(limitCode, 413);
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

async function readBody(req: Request): Promise<JsonRecord> {
  const declared = Number(req.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_REQUEST_BYTES) {
    throw new SafeError("request_body_limit_exceeded", 413);
  }
  const text = await readStream(req.body, MAX_REQUEST_BYTES, "request_body_limit_exceeded");
  if (!text) return {};
  try {
    const value = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new SafeError("request_json_object_required", 400);
    }
    return value as JsonRecord;
  } catch (error) {
    if (error instanceof SafeError) throw error;
    throw new SafeError("invalid_json", 400);
  }
}

async function parseProviderResponse(response: Response): Promise<unknown> {
  const text = await readStream(
    response.body,
    512 * 1024,
    "provider_response_limit_exceeded",
  ).catch(() => "");
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function rpc(
  name: string,
  body: JsonRecord = {},
  schema = "penta_runtime",
): Promise<unknown> {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
    throw new SafeError("runtime_configuration_unavailable", 503);
  }
  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/rpc/${encodeURIComponent(name)}`,
    {
      method: "POST",
      headers: serviceHeaders(schema),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    },
  ).catch(() => {
    throw new SafeError("database_transport_error", 502, { operation: name });
  });

  const requestId = response.headers.get("x-request-id") ??
    response.headers.get("sb-request-id");
  const data = await parseProviderResponse(response);
  if (!response.ok) {
    throw new SafeError("database_operation_rejected", 502, {
      operation: name,
      provider_status: response.status,
      ...(requestId ? { provider_request_id: requestId } : {}),
    });
  }
  return data;
}

async function selectRows(
  schema: string,
  table: string,
  params: URLSearchParams,
): Promise<JsonRecord[]> {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
    throw new SafeError("runtime_configuration_unavailable", 503);
  }
  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/${encodeURIComponent(table)}?${params.toString()}`,
    {
      headers: serviceHeaders(schema),
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    },
  ).catch(() => {
    throw new SafeError("database_transport_error", 502, { table });
  });
  const data = await parseProviderResponse(response);
  if (!response.ok || !Array.isArray(data)) {
    throw new SafeError("database_query_rejected", 502, {
      table,
      provider_status: response.status,
    });
  }
  return data as JsonRecord[];
}

function stringValue(
  value: unknown,
  field: string,
  maxLength = 500,
  required = true,
): string {
  if (typeof value !== "string") {
    if (required) throw new SafeError(`${field}_required`, 400);
    return "";
  }
  const normalized = value.trim();
  if (required && !normalized) throw new SafeError(`${field}_required`, 400);
  if (normalized.length > maxLength) {
    throw new SafeError(`${field}_too_long`, 400);
  }
  return normalized;
}

function intValue(
  value: unknown,
  field: string,
  minimum: number,
  maximum: number,
  fallback?: number,
): number {
  if (value === undefined || value === null) {
    if (fallback !== undefined) return fallback;
    throw new SafeError(`${field}_required`, 400);
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new SafeError(`${field}_invalid`, 400);
  }
  return parsed;
}

function numberValue(
  value: unknown,
  field: string,
  minimum: number,
  maximum: number,
  fallback?: number,
): number {
  if (value === undefined || value === null) {
    if (fallback !== undefined) return fallback;
    throw new SafeError(`${field}_required`, 400);
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < minimum || parsed > maximum) {
    throw new SafeError(`${field}_invalid`, 400);
  }
  return parsed;
}

function objectValue(value: unknown, field: string): JsonRecord {
  if (value === undefined || value === null) return {};
  if (typeof value !== "object" || Array.isArray(value)) {
    throw new SafeError(`${field}_object_required`, 400);
  }
  return value as JsonRecord;
}

function uuidValue(value: unknown, field: string): string {
  const uuid = stringValue(value, field, 64);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(uuid)) {
    throw new SafeError(`${field}_invalid`, 400);
  }
  return uuid;
}

function safeSearch(value: unknown): string {
  const raw = stringValue(value, "query", 120);
  const normalized = raw.normalize("NFKC").replace(/[^\p{L}\p{N}\s_.:/-]/gu, " ");
  return normalized.replace(/\s+/g, " ").trim();
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function normalizeHost(value: string): string {
  return value.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
}

function parseV4(value: string): number[] | null {
  const parts = value.split(".");
  if (parts.length !== 4) return null;
  const parsed = parts.map((part) => Number(part));
  return parsed.every((part) =>
      Number.isInteger(part) && part >= 0 && part <= 255
    )
    ? parsed
    : null;
}

function unsafeV4(value: string): boolean {
  const p = parseV4(value);
  if (!p) return false;
  const [a, b] = p;
  return a === 0 ||
    a === 10 ||
    a === 127 ||
    (a === 100 && b >= 64 && b <= 127) ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 0) ||
    (a === 192 && b === 168) ||
    (a === 198 && (b === 18 || b === 19 || b === 51)) ||
    a === 203 ||
    a >= 224;
}

function unsafeV6(value: string): boolean {
  const host = normalizeHost(value);
  if (!host.includes(":")) return false;
  if (host === "::" || host === "::1") return true;
  if (/^(fc|fd)/.test(host)) return true;
  if (/^fe[89ab]/.test(host)) return true;
  if (host.startsWith("ff")) return true;
  if (host.startsWith("2001:db8:")) return true;
  if (host.startsWith("::ffff:")) {
    const mapped = host.slice("::ffff:".length);
    return parseV4(mapped) ? unsafeV4(mapped) : true;
  }
  return false;
}

const BLOCKED_HOSTS = new Set([
  "localhost",
  "localhost.localdomain",
  "metadata.google.internal",
  "metadata.google.com",
  "instance-data.ec2.internal",
  "169.254.169.254",
]);

async function checkedUrl(raw: string): Promise<URL> {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new SafeError("invalid_url", 400);
  }
  if (url.protocol !== "https:") {
    throw new SafeError("https_required", 400);
  }
  if (url.username || url.password) {
    throw new SafeError("url_credentials_forbidden", 400);
  }
  if (url.port && url.port !== "443") {
    throw new SafeError("nonstandard_port_forbidden", 400);
  }

  const host = normalizeHost(url.hostname);
  if (
    !host ||
    BLOCKED_HOSTS.has(host) ||
    host.endsWith(".local") ||
    host.endsWith(".internal") ||
    host.endsWith(".localhost") ||
    unsafeV4(host) ||
    unsafeV6(host)
  ) {
    throw new SafeError("private_or_local_target_forbidden", 403);
  }

  const resolved = new Set<string>();
  try {
    for (const address of await Deno.resolveDns(host, "A")) resolved.add(address);
  } catch {
    // A record is optional when a safe AAAA record exists.
  }
  try {
    for (const address of await Deno.resolveDns(host, "AAAA")) resolved.add(address);
  } catch {
    // AAAA record is optional when a safe A record exists.
  }
  if (resolved.size === 0) {
    throw new SafeError("dns_resolution_unavailable", 502);
  }
  for (const address of resolved) {
    if (unsafeV4(address) || unsafeV6(address)) {
      throw new SafeError("resolved_private_target_forbidden", 403);
    }
  }

  url.hash = "";
  return url;
}

async function boundedFetch(raw: string): Promise<JsonRecord> {
  let url = await checkedUrl(raw);
  for (let redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {
    const response = await fetch(url, {
      redirect: "manual",
      headers: {
        "user-agent": "CrownThrive-PentaDiscovery/2.0 (+https://crownthrive.com)",
        accept: "text/html,text/plain,application/json,application/xml,text/xml;q=0.8",
      },
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    }).catch(() => {
      throw new SafeError("target_fetch_failed", 502);
    });

    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("location");
      if (!location) throw new SafeError("redirect_without_location", 502);
      if (redirect >= MAX_REDIRECTS) {
        throw new SafeError("redirect_limit_exceeded", 502);
      }
      url = await checkedUrl(new URL(location, url).toString());
      continue;
    }

    if (!response.ok) {
      throw new SafeError("target_http_error", 502, {
        provider_status: response.status,
      });
    }
    const contentType = (response.headers.get("content-type") ?? "")
      .split(";")[0]
      .trim()
      .toLowerCase();
    const allowed = new Set([
      "text/html",
      "text/plain",
      "application/json",
      "application/xml",
      "text/xml",
    ]);
    if (contentType && !allowed.has(contentType)) {
      throw new SafeError("unsupported_content_type", 415);
    }

    const content = await readStream(
      response.body,
      MAX_FETCH_BYTES,
      "target_response_limit_exceeded",
    );
    return {
      url: url.toString(),
      content_type: contentType || "application/octet-stream",
      byte_length: new TextEncoder().encode(content).byteLength,
      content_sha256: await sha256(content),
      content,
    };
  }
  throw new SafeError("redirect_limit_exceeded", 502);
}

function normalizeParsedContent(content: string): unknown {
  try {
    return JSON.parse(content);
  } catch {
    const lines = content.split(/\r?\n/).slice(0, 1000);
    const record: JsonRecord = {};
    let matched = 0;
    for (const line of lines) {
      const separator = line.indexOf(":");
      if (separator <= 0) continue;
      const key = line.slice(0, separator).trim();
      const value = line.slice(separator + 1).trim();
      if (!key || key.length > 100 || !value) continue;
      record[key] = value.slice(0, 2000);
      matched++;
    }
    return matched > 0
      ? record
      : content.replace(/\s+/g, " ").trim().slice(0, 16_000);
  }
}

async function familyRows(): Promise<JsonRecord[]> {
  const params = new URLSearchParams({
    select:
      "member_key,canonical_name,family_role,execution_role,lifecycle_state,packet_contract,fabric_contract,authority_manufacture,metadata,updated_at",
    lifecycle_state: "eq.active",
    order: "member_key.asc",
    limit: "50",
  });
  return await selectRows("penta_discovery", "family_registry_v1", params);
}

async function systemRows(): Promise<JsonRecord[]> {
  const params = new URLSearchParams({
    select:
      "system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,runtime_ref,metadata,last_verified_at,updated_at",
    order: "system_key.asc",
    limit: "250",
  });
  return await selectRows("public", "penta_system_registry", params);
}

async function handleAction(action: string, body: JsonRecord): Promise<unknown> {
  switch (action) {
    case "health":
    case "status": {
      const [status, crawler] = await Promise.all([
        rpc("penta_discovery_status_v2", {}, "penta_runtime"),
        rpc("penta_crawler_status_v3", {}, "public"),
      ]);
      return { contract: CONTRACT, status, crawler };
    }

    case "family":
      return { contract: CONTRACT, members: await familyRows() };

    case "observe": {
      const observation = objectValue(body.observation, "observation");
      return await rpc("intake_v1", {
        p_source_ref: stringValue(body.source_ref, "source_ref", 1000),
        p_source_kind: stringValue(body.source_kind, "source_kind", 100),
        p_observed_subject: stringValue(
          body.observed_subject,
          "observed_subject",
          1000,
        ),
        p_observation: observation,
        p_confidence: numberValue(body.confidence, "confidence", 0, 1, 0.75),
        p_receiver_penta_ref: stringValue(
          body.receiver_penta_ref ?? "penta.census",
          "receiver_penta_ref",
          200,
        ),
        p_objective: stringValue(
          body.objective ?? "classify_register_route",
          "objective",
          500,
        ),
        p_route_class: stringValue(
          body.route_class ?? "local_internal",
          "route_class",
          100,
        ),
      }, "penta_discovery");
    }

    case "search": {
      const query = safeSearch(body.query).toLowerCase();
      const limit = intValue(body.limit, "limit", 1, 100, 25);
      const systems = await systemRows();
      const matches = systems.filter((row) => {
        const text = [
          row.system_key,
          row.canonical_name,
          row.category,
          row.purpose,
          row.runtime_ref,
          JSON.stringify(row.metadata ?? {}),
        ].join(" ").toLowerCase();
        return text.includes(query);
      }).slice(0, limit);
      return { query, count: matches.length, results: matches };
    }

    case "get": {
      const systemKey = stringValue(body.system_key, "system_key", 300);
      const params = new URLSearchParams({
        select: "*",
        system_key: `eq.${systemKey}`,
        limit: "1",
      });
      const rows = await selectRows("public", "penta_system_registry", params);
      if (rows.length === 0) throw new SafeError("system_not_found", 404);
      return rows[0];
    }

    case "resolve": {
      const identity = safeSearch(
        body.identity ?? body.query ?? body.system_key,
      ).toLowerCase();
      const [systems, members] = await Promise.all([systemRows(), familyRows()]);
      const exactSystem = systems.find((row) =>
        String(row.system_key ?? "").toLowerCase() === identity ||
        String(row.canonical_name ?? "").toLowerCase() === identity
      );
      const exactMember = members.find((row) =>
        String(row.member_key ?? "").toLowerCase() === identity ||
        String(row.canonical_name ?? "").toLowerCase() === identity
      );
      if (exactSystem || exactMember) {
        return {
          identity,
          confidence: 1,
          resolved: exactSystem ?? exactMember,
          source: exactSystem ? "system_registry" : "family_registry",
        };
      }
      const candidates = [...systems, ...members].filter((row) =>
        JSON.stringify(row).toLowerCase().includes(identity)
      ).slice(0, 10);
      return {
        identity,
        confidence: candidates.length === 1 ? 0.85 : 0.5,
        candidates,
      };
    }

    case "parse": {
      const content = stringValue(body.content, "content", 64 * 1024);
      return {
        content_sha256: await sha256(content),
        parsed: normalizeParsedContent(content),
      };
    }

    case "fetch": {
      const fetched = await boundedFetch(
        stringValue(body.url, "url", 2000),
      );
      const content = String(fetched.content ?? "");
      const preserve = body.preserve === true;
      let intake: unknown = null;
      if (preserve) {
        intake = await rpc("intake_v1", {
          p_source_ref: fetched.url,
          p_source_kind: "public_web",
          p_observed_subject: fetched.url,
          p_observation: {
            content_type: fetched.content_type,
            byte_length: fetched.byte_length,
            content_sha256: fetched.content_sha256,
            excerpt: content.replace(/\s+/g, " ").trim().slice(0, 5000),
            acquisition: {
              bounded: true,
              https_only: true,
              dns_rebinding_checks: true,
              raw_body_archived: false,
            },
          },
          p_confidence: numberValue(body.confidence, "confidence", 0, 1, 0.7),
          p_receiver_penta_ref: stringValue(
            body.receiver_penta_ref ?? "penta.census",
            "receiver_penta_ref",
            200,
          ),
          p_objective: "classify_register_route",
          p_route_class: stringValue(
            body.route_class ?? "provider_read",
            "route_class",
            100,
          ),
        }, "penta_discovery");
      }
      return {
        url: fetched.url,
        content_type: fetched.content_type,
        byte_length: fetched.byte_length,
        content_sha256: fetched.content_sha256,
        excerpt: content.replace(/\s+/g, " ").trim().slice(0, 16_000),
        preserved: preserve,
        intake,
      };
    }

    case "crawl_status":
      return await rpc("penta_crawler_status_v3", {}, "public");

    case "crawl_tick":
      return await rpc("penta_crawler_roam_v1", {
        p_limit: intValue(body.limit, "limit", 1, 500, 100),
      }, "public");

    case "economics_ensure":
      return await rpc("ensure_penta_packet_economics_v2", {
        p_packet_id: uuidValue(body.packet_id, "packet_id"),
      });

    case "economics_finalize":
      return await rpc("finalize_penta_packet_economics_v2", {
        p_packet_id: uuidValue(body.packet_id, "packet_id"),
        p_terminal_state: stringValue(
          body.terminal_state,
          "terminal_state",
          100,
        ),
      });

    case "economics_backfill":
      return await rpc("backfill_penta_packet_economics_v2", {
        p_limit: intValue(body.limit, "limit", 1, 500, 100),
      });

    case "signal":
      return await rpc("penta_route_ingest_signal_v2", {
        p_source_penta_ref: stringValue(
          body.source_penta_ref,
          "source_penta_ref",
          200,
        ),
        p_signal_kind: stringValue(body.signal_kind, "signal_kind", 100),
        p_numeric_value: numberValue(
          body.numeric_value,
          "numeric_value",
          -1_000_000_000,
          1_000_000_000,
        ),
        p_confidence: numberValue(body.confidence, "confidence", 0, 1),
        p_evidence_refs: objectValue(body.evidence_refs, "evidence_refs"),
        p_route_class: stringValue(body.route_class, "route_class", 100),
        p_subject_penta_ref: stringValue(
          body.subject_penta_ref,
          "subject_penta_ref",
          200,
        ),
        p_receiver_penta_ref: stringValue(
          body.receiver_penta_ref,
          "receiver_penta_ref",
          200,
        ),
        p_currency: stringValue(body.currency ?? "USD", "currency", 3),
        p_ttl_seconds: intValue(body.ttl_seconds, "ttl_seconds", 60, 604800, 3600),
        p_signal_key: stringValue(
          body.signal_key ?? crypto.randomUUID(),
          "signal_key",
          300,
        ),
        p_metadata: objectValue(body.metadata, "metadata"),
      });

    case "refresh_signals":
      return await rpc("penta_route_refresh_operational_signals_v2");

    case "evaluate_abuse":
      return await rpc("penta_route_evaluate_abuse_v2");

    case "pay_materialize":
      return await rpc("materialize_route_penta_pay_v2", {
        p_obligation_id: uuidValue(body.obligation_id, "obligation_id"),
      });

    case "governance_reconcile":
      return await rpc("reconcile_route_pay_signal_v1", {
        p_policy_key: stringValue(body.policy_key, "policy_key", 300),
        p_source_penta_ref: stringValue(
          body.source_penta_ref,
          "source_penta_ref",
          200,
        ),
        p_requested_change_pct: numberValue(
          body.requested_change_pct,
          "requested_change_pct",
          -0.9,
          10,
        ),
        p_confidence: numberValue(body.confidence, "confidence", 0, 1),
        p_evidence_refs: objectValue(body.evidence_refs, "evidence_refs"),
        p_executive_ref: body.executive_ref
          ? stringValue(body.executive_ref, "executive_ref", 500)
          : null,
        p_legislative_ref: body.legislative_ref
          ? stringValue(body.legislative_ref, "legislative_ref", 500)
          : null,
        p_judicial_ref: body.judicial_ref
          ? stringValue(body.judicial_ref, "judicial_ref", 500)
          : null,
      });

    // Stable v1 compatibility aliases. They preserve caller contracts while
    // the automatic packet triggers use the v2 economic path.
    case "reserve":
      return await rpc("reserve_penta_route_v1", {
        p_quote_id: uuidValue(body.quote_id, "quote_id"),
        p_authority_evidence: objectValue(
          body.authority_evidence,
          "authority_evidence",
        ),
      });

    case "usage":
      return await rpc("record_penta_route_usage_v1", {
        p_reservation_id: uuidValue(body.reservation_id, "reservation_id"),
        p_hop_no: intValue(body.hop_no, "hop_no", 1, 100),
        p_route_edge_ref: stringValue(
          body.route_edge_ref,
          "route_edge_ref",
          500,
        ),
        p_disposition: stringValue(body.disposition, "disposition", 100),
        p_actual_internal_units: intValue(
          body.actual_internal_units,
          "actual_internal_units",
          0,
          1_000_000_000,
        ),
        p_actual_provider_cost_minor: intValue(
          body.actual_provider_cost_minor,
          "actual_provider_cost_minor",
          0,
          1_000_000_000,
        ),
        p_currency: stringValue(body.currency ?? "USD", "currency", 3),
        p_metadata: objectValue(body.metadata, "metadata"),
      });

    case "reconcile":
      return await rpc("reconcile_penta_route_v1", {
        p_reservation_id: uuidValue(body.reservation_id, "reservation_id"),
        p_beneficiary_ref: stringValue(
          body.beneficiary_ref,
          "beneficiary_ref",
          300,
        ),
        p_pay_rate_minor_per_1000_units: intValue(
          body.pay_rate_minor_per_1000_units,
          "pay_rate_minor_per_1000_units",
          0,
          1_000_000_000,
        ),
        p_chlom_authority_ref: stringValue(
          body.chlom_authority_ref,
          "chlom_authority_ref",
          1000,
        ),
        p_dail_evidence_ref: stringValue(
          body.dail_evidence_ref,
          "dail_evidence_ref",
          1000,
        ),
      });

    default:
      throw new SafeError("unsupported_action", 404, { action });
  }
}

Deno.serve(async (req: Request) => {
  const requestId = crypto.randomUUID();
  try {
    if (req.method === "OPTIONS") {
      return responseJson({ ok: true }, 200, requestId);
    }
    if (req.method !== "POST" && req.method !== "GET") {
      throw new SafeError("method_not_allowed", 405);
    }

    // Supabase verify_jwt is enabled for this function. The explicit role
    // assertion prevents ordinary authenticated JWTs from reaching the
    // internal control plane.
    assertServiceRole(req);

    const url = new URL(req.url);
    const body = req.method === "GET" ? {} : await readBody(req);
    const action = stringValue(
      body.action ?? url.searchParams.get("action") ?? "health",
      "action",
      100,
    ).toLowerCase();

    const result = await handleAction(action, body);
    return responseJson({
      ok: true,
      request_id: requestId,
      action,
      contract: CONTRACT,
      result,
      at: new Date().toISOString(),
    }, 200, requestId);
  } catch (error) {
    if (error instanceof SafeError) {
      return responseJson({
        ok: false,
        request_id: requestId,
        error: error.code,
        ...(error.detail ? { detail: error.detail } : {}),
      }, error.status, requestId);
    }
    console.error("PentaDiscovery unhandled error", {
      request_id: requestId,
      error: error instanceof Error ? error.message : "unknown",
    });
    return responseJson({
      ok: false,
      request_id: requestId,
      error: "internal_error",
    }, 500, requestId);
  }
});
