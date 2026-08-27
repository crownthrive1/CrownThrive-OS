export const STRIPE_SIGNATURE_TOLERANCE_SECONDS = 300;

export type StripeWebhookSecret = {
  versionRef: string;
  secret: string;
  environment: "test" | "live";
  accountRef?: string;
  activeFrom?: string;
  activeUntil?: string;
};

export type StripeVerificationResult = {
  versionRef: string;
  environment: "test" | "live";
  accountRef?: string;
  signatureTimestamp: number;
  signedPayloadSha256: string;
};

export class StripeConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StripeConfigurationError";
  }
}

export class StripeVerificationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StripeVerificationError";
  }
}

const encoder = new TextEncoder();

function containsStripeCredential(value: string): boolean {
  return /(?:^|[^A-Za-z0-9])(?:whsec_|(?:s|r|p)k_(?:live|test)_)/i.test(value);
}

function parseDate(value: unknown, field: string): number | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || value.length === 0) {
    throw new StripeConfigurationError(`${field}_invalid`);
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    throw new StripeConfigurationError(`${field}_invalid`);
  }
  return parsed;
}

export function parseWebhookSecrets(
  raw: string | undefined,
  nowMs = Date.now(),
): StripeWebhookSecret[] {
  if (!raw) throw new StripeConfigurationError("secret_set_missing");

  let decoded: unknown;
  try {
    decoded = JSON.parse(raw);
  } catch {
    throw new StripeConfigurationError("secret_set_invalid_json");
  }
  if (!Array.isArray(decoded) || decoded.length === 0 || decoded.length > 8) {
    throw new StripeConfigurationError("secret_set_size_invalid");
  }

  const versionRefs = new Set<string>();
  const secretValues = new Set<string>();
  const active: StripeWebhookSecret[] = [];
  for (const candidate of decoded) {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
      throw new StripeConfigurationError("secret_entry_invalid");
    }
    const entry = candidate as Record<string, unknown>;
    const versionRef = entry.version_ref;
    const secret = entry.secret;
    const environment = entry.environment;
    const accountRef = entry.account_ref;

    if (
      typeof versionRef !== "string" ||
      !/^[A-Za-z0-9._:/-]{1,160}$/.test(versionRef) ||
      containsStripeCredential(versionRef) ||
      versionRefs.has(versionRef)
    ) {
      throw new StripeConfigurationError("secret_version_ref_invalid");
    }
    if (
      typeof secret !== "string" ||
      !/^whsec_[A-Za-z0-9_+/=-]{1,506}$/.test(secret) ||
      secretValues.has(secret)
    ) {
      throw new StripeConfigurationError("secret_material_invalid");
    }
    if (environment !== "test" && environment !== "live") {
      throw new StripeConfigurationError("secret_environment_invalid");
    }
    if (
      accountRef !== undefined &&
      (
        typeof accountRef !== "string" ||
        accountRef.length === 0 ||
        accountRef.length > 255 ||
        containsStripeCredential(accountRef)
      )
    ) {
      throw new StripeConfigurationError("secret_account_ref_invalid");
    }

    const activeFrom = parseDate(entry.active_from, "active_from");
    const activeUntil = parseDate(entry.active_until, "active_until");
    if (activeFrom !== undefined && activeUntil !== undefined && activeUntil <= activeFrom) {
      throw new StripeConfigurationError("secret_activation_window_invalid");
    }
    versionRefs.add(versionRef);
    secretValues.add(secret);
    if (
      (activeFrom === undefined || activeFrom <= nowMs) &&
      (activeUntil === undefined || activeUntil >= nowMs)
    ) {
      active.push({
        versionRef,
        secret,
        environment,
        ...(accountRef === undefined ? {} : { accountRef: accountRef as string }),
        ...(activeFrom === undefined ? {} : { activeFrom: entry.active_from as string }),
        ...(activeUntil === undefined ? {} : { activeUntil: entry.active_until as string }),
      });
    }
  }

  if (active.length === 0) throw new StripeConfigurationError("no_active_secret");
  return active;
}

type ParsedSignatureHeader = {
  timestamp: number;
  signatures: Uint8Array[];
};

function hexToBytes(value: string): Uint8Array {
  const output = new Uint8Array(value.length / 2);
  for (let index = 0; index < value.length; index += 2) {
    output[index / 2] = Number.parseInt(value.slice(index, index + 2), 16);
  }
  return output;
}

export function parseStripeSignatureHeader(header: string): ParsedSignatureHeader {
  if (header.length === 0 || encoder.encode(header).byteLength > 8192) {
    throw new StripeVerificationError("signature_header_invalid");
  }
  const timestamps: number[] = [];
  const signatures: Uint8Array[] = [];
  for (const component of header.split(",")) {
    const separator = component.indexOf("=");
    if (separator <= 0) continue;
    const key = component.slice(0, separator).trim();
    const value = component.slice(separator + 1).trim();
    if (key === "t" && /^\d{1,12}$/.test(value)) {
      const timestamp = Number(value);
      if (Number.isSafeInteger(timestamp)) timestamps.push(timestamp);
    } else if (key === "v1" && /^[0-9a-f]{64}$/i.test(value)) {
      if (signatures.length >= 16) {
        throw new StripeVerificationError("signature_header_invalid");
      }
      signatures.push(hexToBytes(value));
    }
  }

  if (timestamps.length !== 1 || signatures.length === 0) {
    throw new StripeVerificationError("signature_header_invalid");
  }
  return { timestamp: timestamps[0], signatures };
}

export async function sha256Hex(input: Uint8Array): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", input));
  return [...digest].map((value) => value.toString(16).padStart(2, "0")).join("");
}

export function stripeSignedPayload(timestamp: number, rawBody: Uint8Array): Uint8Array {
  const prefix = encoder.encode(`${timestamp}.`);
  const signed = new Uint8Array(prefix.length + rawBody.length);
  signed.set(prefix, 0);
  signed.set(rawBody, prefix.length);
  return signed;
}

export async function verifyStripeSignature(input: {
  rawBody: Uint8Array;
  signatureHeader: string;
  secrets: StripeWebhookSecret[];
  nowMs?: number;
  toleranceSeconds?: number;
}): Promise<StripeVerificationResult> {
  const parsed = parseStripeSignatureHeader(input.signatureHeader);
  const nowMs = input.nowMs ?? Date.now();
  const toleranceSeconds = input.toleranceSeconds ?? STRIPE_SIGNATURE_TOLERANCE_SECONDS;
  if (toleranceSeconds !== STRIPE_SIGNATURE_TOLERANCE_SECONDS) {
    throw new StripeConfigurationError("signature_tolerance_must_be_300_seconds");
  }
  if (Math.abs(Math.floor(nowMs / 1000) - parsed.timestamp) > toleranceSeconds) {
    throw new StripeVerificationError("signature_timestamp_outside_tolerance");
  }

  const signedPayload = stripeSignedPayload(parsed.timestamp, input.rawBody);
  let matched: StripeWebhookSecret | undefined;

  // Evaluate every active secret/signature combination. This supports endpoint
  // secret rotation and every v1 value in Stripe's signature header. WebCrypto's
  // HMAC verify primitive performs the digest comparison without application-level
  // early-return byte comparisons.
  for (const candidate of input.secrets) {
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(candidate.secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"],
    );
    for (const signature of parsed.signatures) {
      const valid = await crypto.subtle.verify("HMAC", key, signature, signedPayload);
      if (valid && matched === undefined) matched = candidate;
    }
  }

  if (!matched) throw new StripeVerificationError("signature_verification_failed");
  return {
    versionRef: matched.versionRef,
    environment: matched.environment,
    ...(matched.accountRef === undefined ? {} : { accountRef: matched.accountRef }),
    signatureTimestamp: parsed.timestamp,
    signedPayloadSha256: await sha256Hex(signedPayload),
  };
}
