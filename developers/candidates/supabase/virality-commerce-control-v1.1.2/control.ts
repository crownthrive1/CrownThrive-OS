export const ALLOWED_ORIGIN = "https://vm.crownthrive.com";
export const MAX_BODY_BYTES = 4_096;

export const MUTATION_AUTHORITY = Object.freeze({
  economic_mutation_authorized: false,
  provider_mutation_authorized: false,
  wallet_signing_authorized: false,
  native_site_mutation_authorized: false,
  generalized_dispatch_authorized: false,
  raw_secret_export: false,
});

export type ManifestReader = () => Promise<unknown>;

export type DispatchRegistryEvidence = Readonly<{
  read_state: "READABLE" | "UNREADABLE";
  row: Record<string, unknown> | null;
}>;

export type DispatchRegistryControl = Readonly<{
  state:
    | "HOLD_REGISTRY_FLAG_TRUE_UNAUTHORIZED"
    | "HOLD_REGISTRY_DISABLED_BY_POLICY"
    | "HOLD_REGISTRY_STATE_MISSING_OR_UNREADABLE";
  state_basis:
    | "GENERALIZED_DISPATCH_REGISTRY_FLAG_TRUE_UNAUTHORIZED"
    | "GENERALIZED_DISPATCH_DISABLED_BY_POLICY"
    | "GENERALIZED_DISPATCH_REGISTRY_STATE_MISSING_OR_UNREADABLE";
  registry_read_state: "READABLE" | "UNREADABLE";
  registry_enabled_evidence: boolean | null;
  effective_enabled: false;
  execution_authorized: false;
}>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function classifyDispatchRegistry(
  evidence: DispatchRegistryEvidence,
): DispatchRegistryControl {
  if (
    evidence.read_state !== "READABLE" ||
    !isRecord(evidence.row) ||
    typeof evidence.row.enabled !== "boolean"
  ) {
    return Object.freeze({
      state: "HOLD_REGISTRY_STATE_MISSING_OR_UNREADABLE",
      state_basis:
        "GENERALIZED_DISPATCH_REGISTRY_STATE_MISSING_OR_UNREADABLE",
      registry_read_state: evidence.read_state,
      registry_enabled_evidence: null,
      effective_enabled: false,
      execution_authorized: false,
    });
  }

  if (evidence.row.enabled === true) {
    return Object.freeze({
      state: "HOLD_REGISTRY_FLAG_TRUE_UNAUTHORIZED",
      state_basis: "GENERALIZED_DISPATCH_REGISTRY_FLAG_TRUE_UNAUTHORIZED",
      registry_read_state: "READABLE",
      registry_enabled_evidence: true,
      effective_enabled: false,
      execution_authorized: false,
    });
  }

  return Object.freeze({
    state: "HOLD_REGISTRY_DISABLED_BY_POLICY",
    state_basis: "GENERALIZED_DISPATCH_DISABLED_BY_POLICY",
    registry_read_state: "READABLE",
    registry_enabled_evidence: false,
    effective_enabled: false,
    execution_authorized: false,
  });
}

export function requestOrigin(request: Request) {
  return request.headers.get("origin")?.trim() ?? "";
}

function originPolicyError(request: Request) {
  const origin = requestOrigin(request);

  if (request.method === "GET") {
    return origin === "" || origin === ALLOWED_ORIGIN
      ? null
      : "origin_not_allowed";
  }

  if (request.method === "POST" || request.method === "OPTIONS") {
    if (origin === "") return "origin_required";
    return origin === ALLOWED_ORIGIN ? null : "origin_not_allowed";
  }

  return origin !== "" && origin !== ALLOWED_ORIGIN
    ? "origin_not_allowed"
    : null;
}

export function responseHeaders(request: Request) {
  const headers: Record<string, string> = {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, max-age=0",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "vary": "Origin",
  };
  if (requestOrigin(request) === ALLOWED_ORIGIN) {
    headers["access-control-allow-origin"] = ALLOWED_ORIGIN;
    headers["access-control-allow-methods"] = "GET, POST, OPTIONS";
    headers["access-control-allow-headers"] = "content-type";
    headers["access-control-max-age"] = "600";
  }
  return headers;
}

function reply(request: Request, body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(request),
  });
}

function hasExactKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
) {
  const actual = Object.keys(value).sort();
  const expected = [...allowed].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

async function cancelBody(
  body: ReadableStream<Uint8Array> | null,
  reason: string,
) {
  if (!body || body.locked) return;
  try {
    await body.cancel(reason);
  } catch {
    // Cancellation is best-effort; the request remains rejected fail-closed.
  }
}

export async function readJson(request: Request) {
  const lengthHeader = request.headers.get("content-length");
  if (lengthHeader !== null) {
    const normalizedLength = lengthHeader.trim();
    const declaredLength = Number(normalizedLength);
    if (
      !/^(0|[1-9][0-9]*)$/.test(normalizedLength) ||
      !Number.isSafeInteger(declaredLength) ||
      declaredLength > MAX_BODY_BYTES
    ) {
      await cancelBody(request.body, "payload_too_large");
      throw new Error("payload_too_large");
    }
  }

  if (request.body === null) throw new Error("invalid_json");

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let totalBytes = 0;

  try {
    while (true) {
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch {
        try {
          await reader.cancel("request_body_unreadable");
        } catch {
          // Preserve the original read failure and reject fail-closed.
        }
        throw new Error("request_body_unreadable");
      }

      if (result.done) break;
      const chunk = result.value;
      if (!(chunk instanceof Uint8Array)) {
        try {
          await reader.cancel("request_body_unreadable");
        } catch {
          // Reject even if the producer does not support cancellation.
        }
        throw new Error("request_body_unreadable");
      }

      totalBytes += chunk.byteLength;
      if (totalBytes > MAX_BODY_BYTES) {
        try {
          await reader.cancel("payload_too_large");
        } catch {
          // Reject even if the producer does not support cancellation.
        }
        throw new Error("payload_too_large");
      }
      chunks.push(chunk);
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // The body is already rejected or consumed; no further read is allowed.
    }
  }

  const bytes = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new Error("invalid_json");
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new Error("invalid_json");
  }
}

export function createHandler(readManifest: ManifestReader) {
  return async (request: Request) => {
    const originError = originPolicyError(request);
    if (originError) {
      return reply(request, { error: originError }, 403);
    }

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: responseHeaders(request),
      });
    }

    try {
      if (request.method === "GET") {
        return reply(request, await readManifest());
      }
      if (request.method !== "POST") {
        return reply(request, { error: "method_not_allowed" }, 405);
      }

      const body = await readJson(request);
      if (!isRecord(body) || typeof body.action !== "string") {
        return reply(request, { error: "invalid_request" }, 400);
      }

      if (body.action === "manifest" || body.action === "health") {
        if (!hasExactKeys(body, ["action"])) {
          return reply(request, { error: "invalid_request_shape" }, 400);
        }
        return reply(request, await readManifest());
      }

      if (body.action === "convert_virality_credits") {
        if (!hasExactKeys(body, ["action", "amount"])) {
          return reply(request, { error: "invalid_request_shape" }, 400);
        }
        const amount = body.amount;
        if (
          typeof amount !== "number" ||
          !Number.isSafeInteger(amount) ||
          amount < 0 ||
          amount > Math.floor(Number.MAX_SAFE_INTEGER / 25)
        ) {
          return reply(request, { error: "invalid_amount" }, 400);
        }
        return reply(request, {
          from: "Virality Credits",
          amount,
          to: "Crown Credits",
          canonical_amount: amount * 25,
          ratio: "1 Virality Credit = 25 Crown Credits",
          ledger_mutation: false,
          historical_balance_rewrite: false,
        });
      }

      return reply(request, { error: "unknown_action" }, 400);
    } catch (error) {
      const code = error instanceof Error ? error.message : "operation_failed";
      if (code === "payload_too_large") {
        return reply(request, { error: code, raw_secret_export: false }, 413);
      }
      if (code === "invalid_json" || code === "request_body_unreadable") {
        return reply(request, { error: code, raw_secret_export: false }, 400);
      }
      return reply(
        request,
        { error: "control_readback_unavailable", raw_secret_export: false },
        503,
      );
    }
  };
}
