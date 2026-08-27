import {
  parseWebhookSecrets,
  sha256Hex,
  STRIPE_SIGNATURE_TOLERANCE_SECONDS,
  StripeConfigurationError,
  StripeVerificationError,
  type StripeVerificationResult,
  verifyStripeSignature,
} from "./stripe_signature.ts";

export const STRIPE_SECRET_SET_ENV = "DAIL_STRIPE_WEBHOOK_SECRETS_JSON";
export const ADMISSION_HMAC_KEY_ENV = "DAIL_INGRESS_ADMISSION_HMAC_KEY";
export const INGEST_RPC = "dail_ingest_verified_external_event_v2";

const VERIFIER_ID = "ct.edge.dail-external-ingress.stripe.v1";
const VERIFIER_TOOL_VERSION = "1.0.0";
const VERIFIER_TRUST_DOMAIN = "crownthrive.edge.dail-ingress";
const PRODUCER_TRUST_DOMAIN = "stripe.com";
const MAX_RAW_BODY_BYTES = 1_048_576;
const UTF8 = new TextEncoder();

export type StripeEventSummary = {
  id: string;
  type: string;
  objectType: string;
  objectId: string;
  created: number;
  livemode: boolean;
  pendingWebhooks: number;
  apiVersion: string | null;
  requestRef: string | null;
  accountRef: string | null;
};

export type IngestRpcArguments = {
  p_provider: "stripe";
  p_source_event_id: string;
  p_provider_event_type: string;
  p_provider_object_type: string;
  p_provider_object_id: string;
  p_api_version: string | null;
  p_livemode: boolean;
  p_pending_webhooks: number;
  p_provider_request_ref: string | null;
  p_provider_account_ref: string | null;
  p_raw_body_sha256: string;
  p_signed_payload_sha256: string;
  p_signature_header_sha256: string;
  p_signature_timestamp: number;
  p_signature_tolerance_seconds: 300;
  p_secret_version_ref: string;
  p_admission_mac: string;
  p_verifier_id: string;
  p_verifier_tool_version: string;
  p_verifier_trust_domain: string;
  p_producer_trust_domain: string;
  p_received_at: string;
};

export type RpcResult = {
  data: unknown;
  error: unknown | null;
};

export type IngressRpcClient = {
  rpc(name: string, args: IngestRpcArguments): Promise<RpcResult>;
};

export type IngressHandlerDependencies = {
  getEnv(name: string): string | undefined;
  createRpcClient(url: string, serviceRoleKey: string): IngressRpcClient;
  nowMs?: () => number;
};

export class StripeEventSchemaError extends Error {
  constructor() {
    super("stripe_event_schema_invalid");
    this.name = "StripeEventSchemaError";
  }
}

export class AdmissionConfigurationError extends Error {
  constructor() {
    super("admission_hmac_key_invalid");
    this.name = "AdmissionConfigurationError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function invalidSchema(): never {
  throw new StripeEventSchemaError();
}

function boundedString(
  value: unknown,
  maximumLength: number,
  pattern: RegExp,
): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximumLength ||
    !pattern.test(value)
  ) {
    return invalidSchema();
  }
  return value;
}

function optionalApiVersion(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  return boundedString(value, 64, /^[A-Za-z0-9._-]+$/);
}

function optionalRequestRef(value: unknown): string | null {
  if (!isRecord(value) || value.id === undefined || value.id === null) return null;
  return boundedString(value.id, 255, /^req_[A-Za-z0-9]+$/);
}

function optionalAccountRef(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  return boundedString(value, 255, /^acct_[A-Za-z0-9]+$/);
}

/**
 * Parse an already-captured exact request body into only the Stripe fields that
 * the admission RPC needs. The returned value deliberately cannot carry the
 * full provider payload.
 */
export function parseStripeEventSummary(
  rawBody: Uint8Array,
  nowMs = Date.now(),
): StripeEventSummary {
  if (rawBody.byteLength === 0 || rawBody.byteLength > MAX_RAW_BODY_BYTES) {
    return invalidSchema();
  }

  let decoded: unknown;
  try {
    decoded = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(rawBody));
  } catch {
    return invalidSchema();
  }
  if (!isRecord(decoded) || !isRecord(decoded.data) || !isRecord(decoded.data.object)) {
    return invalidSchema();
  }

  const providerObject = decoded.data.object;
  const created = decoded.created;
  const pendingWebhooks = decoded.pending_webhooks;
  if (
    !Number.isSafeInteger(created) ||
    (created as number) < 946_684_800 ||
    (created as number) > Math.floor(nowMs / 1000) + STRIPE_SIGNATURE_TOLERANCE_SECONDS ||
    typeof decoded.livemode !== "boolean" ||
    !Number.isSafeInteger(pendingWebhooks) ||
    (pendingWebhooks as number) < 0 ||
    (pendingWebhooks as number) > 100_000
  ) {
    return invalidSchema();
  }

  if (decoded.object !== undefined && decoded.object !== "event") {
    return invalidSchema();
  }

  return {
    id: boundedString(decoded.id, 255, /^evt_[A-Za-z0-9]+$/),
    type: boundedString(decoded.type, 160, /^[a-z0-9][a-z0-9_.]*$/),
    objectType: boundedString(providerObject.object, 100, /^[a-z0-9][a-z0-9_.]*$/),
    objectId: boundedString(providerObject.id, 255, /^[A-Za-z0-9][A-Za-z0-9_.:/-]*$/),
    created: created as number,
    livemode: decoded.livemode,
    pendingWebhooks: pendingWebhooks as number,
    apiVersion: optionalApiVersion(decoded.api_version),
    requestRef: optionalRequestRef(decoded.request),
    accountRef: optionalAccountRef(decoded.account),
  };
}

/** The exact admission statement authenticated to the database verifier. */
export function buildAdmissionStatement(input: {
  eventId: string;
  rawBodySha256: string;
  signatureTimestamp: number;
  matchedSecretVersionRef: string;
}): string {
  return [
    "dail-external-ingress-v2",
    input.eventId,
    input.rawBodySha256,
    String(input.signatureTimestamp),
    input.matchedSecretVersionRef,
  ].join("|");
}

/**
 * Authenticate the narrow admission statement with a database-shared key that
 * is deliberately distinct from Stripe endpoint secrets and API credentials.
 */
export async function computeAdmissionMac(
  admissionKey: string | undefined,
  input: {
    eventId: string;
    rawBodySha256: string;
    signatureTimestamp: number;
    matchedSecretVersionRef: string;
  },
): Promise<string> {
  if (
    typeof admissionKey !== "string" ||
    UTF8.encode(admissionKey).byteLength < 32 ||
    admissionKey.length > 1024 ||
    /^(?:whsec_|(?:s|r|p)k_(?:live|test)_)/i.test(admissionKey)
  ) {
    throw new AdmissionConfigurationError();
  }
  const key = await crypto.subtle.importKey(
    "raw",
    UTF8.encode(admissionKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = new Uint8Array(await crypto.subtle.sign(
    "HMAC",
    key,
    UTF8.encode(buildAdmissionStatement(input)),
  ));
  return [...mac].map((value) => value.toString(16).padStart(2, "0")).join("");
}

export function buildIngestRpcArguments(input: {
  event: StripeEventSummary;
  verification: StripeVerificationResult;
  rawBodySha256: string;
  signatureHeaderSha256: string;
  admissionMac: string;
  receivedAt: string;
}): IngestRpcArguments {
  return {
    p_provider: "stripe",
    p_source_event_id: input.event.id,
    p_provider_event_type: input.event.type,
    p_provider_object_type: input.event.objectType,
    p_provider_object_id: input.event.objectId,
    p_api_version: input.event.apiVersion,
    p_livemode: input.event.livemode,
    p_pending_webhooks: input.event.pendingWebhooks,
    p_provider_request_ref: input.event.requestRef,
    p_provider_account_ref: input.event.accountRef ?? input.verification.accountRef ?? null,
    p_raw_body_sha256: input.rawBodySha256,
    p_signed_payload_sha256: input.verification.signedPayloadSha256,
    p_signature_header_sha256: input.signatureHeaderSha256,
    p_signature_timestamp: input.verification.signatureTimestamp,
    p_signature_tolerance_seconds: STRIPE_SIGNATURE_TOLERANCE_SECONDS,
    p_secret_version_ref: input.verification.versionRef,
    p_admission_mac: input.admissionMac,
    p_verifier_id: VERIFIER_ID,
    p_verifier_tool_version: VERIFIER_TOOL_VERSION,
    p_verifier_trust_domain: VERIFIER_TRUST_DOMAIN,
    p_producer_trust_domain: PRODUCER_TRUST_DOMAIN,
    p_received_at: input.receivedAt,
  };
}

function response(body: unknown, status: number, extraHeaders?: HeadersInit): Response {
  const headers = new Headers(extraHeaders);
  headers.set("content-type", "application/json; charset=utf-8");
  headers.set("cache-control", "no-store");
  return new Response(JSON.stringify(body), { status, headers });
}

function invalidRequest(): Response {
  return response({ ok: false, error: "invalid_request" }, 400);
}

function unavailable(): Response {
  return response({ ok: false, error: "temporarily_unavailable" }, 503);
}

function successfulRpcResult(value: unknown): value is { ok: true; duplicate: boolean } {
  return isRecord(value) && value.ok === true && typeof value.duplicate === "boolean";
}

/** Create the POST-only Stripe ingress handler with injectable runtime edges. */
export function createDailExternalIngressHandler(
  dependencies: IngressHandlerDependencies,
): (request: Request) => Promise<Response> {
  return async (request: Request): Promise<Response> => {
    if (request.method !== "POST") {
      return response(
        { ok: false, error: "method_not_allowed" },
        405,
        { allow: "POST" },
      );
    }

    const signatureHeader = request.headers.get("stripe-signature");
    if (!signatureHeader) return invalidRequest();

    const nowMs = dependencies.nowMs?.() ?? Date.now();
    const receivedAt = new Date(nowMs).toISOString();

    // Capture the exact bytes once. JSON parsing below operates on this copy;
    // request.json()/request.text() are intentionally never used.
    let rawBody: Uint8Array;
    try {
      rawBody = new Uint8Array(await request.arrayBuffer());
    } catch {
      return invalidRequest();
    }

    let event: StripeEventSummary;
    try {
      event = parseStripeEventSummary(rawBody, nowMs);
    } catch (error) {
      if (error instanceof StripeEventSchemaError) return invalidRequest();
      return invalidRequest();
    }

    let secrets;
    try {
      secrets = parseWebhookSecrets(dependencies.getEnv(STRIPE_SECRET_SET_ENV), nowMs);
    } catch (error) {
      if (error instanceof StripeConfigurationError) return unavailable();
      return unavailable();
    }

    // Verify against every active rotation candidate so match position does not
    // change the number of HMAC operations. The matched secret's test/live label
    // must independently agree with the signed event payload.
    const expectedEnvironment = event.livemode ? "live" : "test";

    let verification: StripeVerificationResult;
    try {
      verification = await verifyStripeSignature({
        rawBody,
        signatureHeader,
        secrets,
        nowMs,
        toleranceSeconds: STRIPE_SIGNATURE_TOLERANCE_SECONDS,
      });
    } catch (error) {
      if (error instanceof StripeConfigurationError) return unavailable();
      if (error instanceof StripeVerificationError) return invalidRequest();
      return invalidRequest();
    }
    if (verification.environment !== expectedEnvironment) return invalidRequest();

    let rawBodySha256: string;
    let signatureHeaderSha256: string;
    try {
      [rawBodySha256, signatureHeaderSha256] = await Promise.all([
        sha256Hex(rawBody),
        sha256Hex(UTF8.encode(signatureHeader)),
      ]);
    } catch {
      return unavailable();
    }

    let admissionMac: string;
    try {
      admissionMac = await computeAdmissionMac(
        dependencies.getEnv(ADMISSION_HMAC_KEY_ENV),
        {
          eventId: event.id,
          rawBodySha256,
          signatureTimestamp: verification.signatureTimestamp,
          matchedSecretVersionRef: verification.versionRef,
        },
      );
    } catch {
      return unavailable();
    }

    let supabaseUrl: string | undefined;
    let serviceRoleKey: string | undefined;
    try {
      supabaseUrl = dependencies.getEnv("SUPABASE_URL");
      serviceRoleKey = dependencies.getEnv("SUPABASE_SERVICE_ROLE_KEY");
    } catch {
      return unavailable();
    }
    if (!supabaseUrl || !serviceRoleKey) return unavailable();

    const args = buildIngestRpcArguments({
      event,
      verification,
      rawBodySha256,
      signatureHeaderSha256,
      admissionMac,
      receivedAt,
    });

    let result: RpcResult;
    try {
      const client = dependencies.createRpcClient(supabaseUrl, serviceRoleKey);
      result = await client.rpc(INGEST_RPC, args);
    } catch {
      return unavailable();
    }
    if (result.error !== null || !successfulRpcResult(result.data)) return unavailable();

    // Duplicate deliveries have already been authenticated and digest-checked
    // atomically by the RPC. A small generic success response ends Stripe retry.
    return response({ ok: true, duplicate: result.data.duplicate }, 200);
  };
}
