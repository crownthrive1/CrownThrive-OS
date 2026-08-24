// ThriveEvergreen Production Fabric policy reducer v1.1 — deterministic, fail-closed helpers.
//
// This module validates and evaluates exact-version candidate material. It does not
// execute provider writes, move money, grant rights, publish an effective price,
// activate an entitlement, or enable generalized dispatch. A provider success is
// evidence only. Any consequential effect still requires the separately governed
// wrapper, authority envelope, independent certification, and execution receipt.

import { createHash } from "node:crypto";

export type JsonPrimitive = null | boolean | number | string;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type Sha256 = string;
export type Uuid = string;
export type Iso4217 = string;
export type ExactVersionRef = string;
export type StableId = string;

export type EcacDecision = "ECAC" | "HOLD" | "DENY";
export type GateState = "PASS" | "HOLD" | "DENY" | "NOT_APPLICABLE";
export type RightsState = "PASS" | "HOLD" | "DENY";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256_RE = /^[0-9a-f]{64}$/;
const ISO4217_RE = /^[A-Z]{3}$/;
const STABLE_ID_RE = /^ct\.[a-z0-9]+(?:[.-][a-z0-9]+)+$/;
const EXACT_VERSION_RE = /^[A-Za-z0-9](?:[A-Za-z0-9._:+/@-]{0,254})$/;
const GATE_KEY_RE = /^[a-z][a-z0-9_]{1,63}$/;
const IDEMPOTENCY_KEY_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,254}$/;
const PROVIDER_ID_RE = /^[a-z][a-z0-9_.-]{0,63}$/;
const UTC_RFC3339_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?Z$/;

export class FabricContractViolation extends Error {
  readonly code: string;

  constructor(code: string, detail?: string) {
    super(detail ? `${code}:${detail}` : code);
    this.name = "FabricContractViolation";
    this.code = code;
  }
}

const fail = (code: string, detail?: string): never => {
  throw new FabricContractViolation(code, detail);
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
};

const assertRecord = (name: string, value: unknown): Record<string, unknown> => {
  if (!isRecord(value)) fail("invalid_object", name);
  return value;
};

const assertClosedObject = (
  name: string,
  value: unknown,
  required: readonly string[],
  optional: readonly string[] = [],
): Record<string, unknown> => {
  const object = assertRecord(name, value);
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(object)) {
    if (!allowed.has(key)) fail("unexpected_property", `${name}.${key}`);
  }
  for (const key of required) {
    if (!Object.prototype.hasOwnProperty.call(object, key)) fail("missing_property", `${name}.${key}`);
  }
  return object;
};

const assertString = (name: string, value: unknown, min = 1, max = 255): string => {
  if (typeof value !== "string" || value.length < min || value.length > max) fail("invalid_string", name);
  return value;
};

const assertBoolean = (name: string, value: unknown): boolean => {
  if (typeof value !== "boolean") fail("invalid_boolean", name);
  return value;
};

const assertStringArray = (
  name: string,
  value: unknown,
  options: { nonempty?: boolean; unique?: boolean; sorted?: boolean; pattern?: RegExp } = {},
): string[] => {
  if (!Array.isArray(value)) fail("invalid_array", name);
  if (options.nonempty && value.length === 0) fail("empty_array", name);
  const strings = value.map((entry, index) => {
    const item = assertString(`${name}[${index}]`, entry);
    if (options.pattern && !options.pattern.test(item)) fail("invalid_array_item", `${name}[${index}]`);
    return item;
  });
  if (options.unique && new Set(strings).size !== strings.length) fail("duplicate_array_item", name);
  if (options.sorted && strings.some((item, index) => index > 0 && strings[index - 1]! > item)) {
    fail("array_not_sorted", name);
  }
  return strings;
};

const assertSafeInteger = (
  name: string,
  value: unknown,
  options: { minimum?: number; maximum?: number } = {},
): number => {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) fail("invalid_safe_integer", name);
  if (options.minimum !== undefined && value < options.minimum) fail("integer_below_minimum", name);
  if (options.maximum !== undefined && value > options.maximum) fail("integer_above_maximum", name);
  return value;
};

const assertFiniteNumber = (
  name: string,
  value: unknown,
  options: { minimum?: number; maximum?: number } = {},
): number => {
  if (typeof value !== "number" || !Number.isFinite(value)) fail("invalid_finite_number", name);
  if (options.minimum !== undefined && value < options.minimum) fail("number_below_minimum", name);
  if (options.maximum !== undefined && value > options.maximum) fail("number_above_maximum", name);
  return value;
};

const assertUuid = (name: string, value: unknown): Uuid => {
  const text = assertString(name, value, 36, 36).toLowerCase();
  if (!UUID_RE.test(text)) fail("invalid_uuid", name);
  return text;
};

const assertSha256 = (name: string, value: unknown): Sha256 => {
  const text = assertString(name, value, 64, 64).toLowerCase();
  if (!SHA256_RE.test(text)) fail("invalid_sha256", name);
  return text;
};

const assertCurrency = (name: string, value: unknown): Iso4217 => {
  const text = assertString(name, value, 3, 3);
  if (!ISO4217_RE.test(text)) fail("invalid_iso4217", name);
  return text;
};

const assertStableId = (name: string, value: unknown): StableId => {
  const text = assertString(name, value);
  if (!STABLE_ID_RE.test(text)) fail("invalid_stable_id", name);
  return text;
};

const assertExactVersionRef = (name: string, value: unknown): ExactVersionRef => {
  const text = assertString(name, value);
  if (!EXACT_VERSION_RE.test(text)) fail("invalid_exact_version_ref", name);
  return text;
};

const parseUtcRfc3339 = (name: string, value: unknown): { text: string; epochNanoseconds: bigint } => {
  const text = assertString(name, value);
  const match = UTC_RFC3339_RE.exec(text);
  if (!match) fail("invalid_utc_instant", name);
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  if (year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) {
    fail("invalid_utc_instant", name);
  }
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]!;
  if (day < 1 || day > daysInMonth) fail("invalid_utc_instant", name);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(hour, minute, second, 0);
  const secondsSinceEpoch = BigInt(Math.trunc(date.getTime() / 1000));
  const fractionalNanoseconds = BigInt((match[7] ?? "").padEnd(9, "0") || "0");
  return { text, epochNanoseconds: secondsSinceEpoch * 1_000_000_000n + fractionalNanoseconds };
};

const assertInstant = (name: string, value: unknown): string => parseUtcRfc3339(name, value).text;

const compareInstants = (left: string, right: string): number => {
  const leftNs = parseUtcRfc3339("leftInstant", left).epochNanoseconds;
  const rightNs = parseUtcRfc3339("rightInstant", right).epochNanoseconds;
  return leftNs < rightNs ? -1 : leftNs > rightNs ? 1 : 0;
};

const compareCodeUnits = (left: string, right: string): number => left < right ? -1 : left > right ? 1 : 0;

const assertEnum = <T extends string>(name: string, value: unknown, values: readonly T[]): T => {
  if (typeof value !== "string" || !values.includes(value as T)) fail("invalid_enum", name);
  return value as T;
};

const assertUnicodeScalarString = (value: string, path: string): void => {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail("invalid_unicode_scalar", path);
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      fail("invalid_unicode_scalar", path);
    }
  }
};

/**
 * RFC 8785-style canonical JSON for the supported I-JSON value set.
 *
 * Numbers use ECMAScript JSON number serialization, object keys use UTF-16 code
 * unit ordering, and invalid/non-JSON values, sparse arrays, cycles, and lone
 * surrogates are rejected instead of being silently coerced.
 */
export function canonicalJson(value: unknown): string {
  const ancestors = new WeakSet<object>();

  const encode = (entry: unknown, path: string): string => {
    if (entry === null) return "null";
    if (typeof entry === "boolean") return entry ? "true" : "false";
    if (typeof entry === "string") {
      assertUnicodeScalarString(entry, path);
      const encoded = JSON.stringify(entry);
      if (encoded === undefined) fail("unsupported_json_type", path);
      return encoded;
    }
    if (typeof entry === "number") {
      if (!Number.isFinite(entry)) fail("non_json_number", path);
      const encoded = JSON.stringify(entry);
      if (encoded === undefined) fail("unsupported_json_type", path);
      return encoded;
    }
    if (typeof entry !== "object") fail("unsupported_json_type", path);
    if (ancestors.has(entry)) fail("cyclic_json_value", path);
    ancestors.add(entry);
    try {
      if (Array.isArray(entry)) {
        for (const key of Reflect.ownKeys(entry)) {
          if (typeof key === "symbol") fail("unsupported_json_symbol_key", path);
          if (key !== "length" && !/^(0|[1-9][0-9]*)$/.test(key)) fail("unsupported_json_array_property", `${path}.${key}`);
        }
        for (let index = 0; index < entry.length; index += 1) {
          if (!Object.prototype.hasOwnProperty.call(entry, index)) fail("sparse_json_array", `${path}[${index}]`);
        }
        return `[${entry.map((item, index) => encode(item, `${path}[${index}]`)).join(",")}]`;
      }
      if (!isRecord(entry)) fail("unsupported_json_object", path);
      for (const key of Reflect.ownKeys(entry)) {
        if (typeof key === "symbol") fail("unsupported_json_symbol_key", path);
        const descriptor = Object.getOwnPropertyDescriptor(entry, key);
        if (!descriptor?.enumerable || !("value" in descriptor)) fail("unsupported_json_property", `${path}.${key}`);
      }
      const keys = Object.keys(entry).sort();
      return `{${keys.map((key) => {
        assertUnicodeScalarString(key, `${path}.<key>`);
        const encodedKey = JSON.stringify(key);
        if (encodedKey === undefined) fail("unsupported_json_type", `${path}.<key>`);
        return `${encodedKey}:${encode(entry[key], `${path}.${key}`)}`;
      }).join(",")}}`;
    } finally {
      ancestors.delete(entry);
    }
  };

  return encode(value, "$");
}

export function canonicalSha256(value: unknown): Sha256 {
  return createHash("sha256").update(canonicalJson(value), "utf8").digest("hex");
}

const toSafeNumber = (name: string, value: bigint): number => {
  if (value > BigInt(Number.MAX_SAFE_INTEGER) || value < BigInt(Number.MIN_SAFE_INTEGER)) {
    fail("safe_integer_overflow", name);
  }
  return Number(value);
};

const sumSafe = (name: string, values: readonly number[]): number =>
  toSafeNumber(name, values.reduce((total, value) => total + BigInt(value), 0n));

const ceilDiv = (numerator: bigint, denominator: bigint): bigint => {
  if (denominator <= 0n || numerator < 0n) fail("invalid_division");
  return (numerator + denominator - 1n) / denominator;
};

export interface MoneyAmount {
  amountMinor: number;
  currency: Iso4217;
}

const validateMoney = (name: string, value: unknown): MoneyAmount => {
  const object = assertClosedObject(name, value, ["amountMinor", "currency"]);
  return {
    amountMinor: assertSafeInteger(`${name}.amountMinor`, object.amountMinor, { minimum: 0 }),
    currency: assertCurrency(`${name}.currency`, object.currency),
  };
};

export interface CommerceCandidateV11 {
  candidateId: Uuid;
  subjectRef: StableId;
  exactVersionRef: ExactVersionRef;
  contentSha256: Sha256;
  rightsState: RightsState;
  cieState: GateState;
  channel: string;
  currency: Iso4217;
  requestedEffects: string[];
  providerAliases: Record<string, string>;
}

export function normalizeCandidateV11(input: unknown): CommerceCandidateV11 & { normalizedSha256: Sha256 } {
  const object = assertClosedObject(
    "candidate",
    input,
    ["candidateId", "subjectRef", "exactVersionRef", "contentSha256", "rightsState", "channel", "currency"],
    ["cieState", "requestedEffects", "providerAliases"],
  );
  const aliasesObject = object.providerAliases === undefined
    ? {}
    : assertRecord("candidate.providerAliases", object.providerAliases);
  const providerAliases: Record<string, string> = {};
  for (const key of Object.keys(aliasesObject).sort()) {
    if (!/^[a-z][a-z0-9_.-]{1,63}$/.test(key)) fail("invalid_provider_alias_key", key);
    providerAliases[key] = assertString(`candidate.providerAliases.${key}`, aliasesObject[key]);
  }
  const requestedEffects = object.requestedEffects === undefined
    ? []
    : assertStringArray("candidate.requestedEffects", object.requestedEffects, { unique: true });
  requestedEffects.sort();
  const channel = assertString("candidate.channel", object.channel).trim().toLowerCase();
  if (channel.length === 0) fail("invalid_string", "candidate.channel");
  const candidate: CommerceCandidateV11 = {
    candidateId: assertUuid("candidate.candidateId", object.candidateId),
    subjectRef: assertStableId("candidate.subjectRef", object.subjectRef),
    exactVersionRef: assertExactVersionRef("candidate.exactVersionRef", object.exactVersionRef),
    contentSha256: assertSha256("candidate.contentSha256", object.contentSha256),
    rightsState: assertEnum("candidate.rightsState", object.rightsState, ["PASS", "HOLD", "DENY"] as const),
    cieState: object.cieState === undefined
      ? "NOT_APPLICABLE"
      : assertEnum("candidate.cieState", object.cieState, ["PASS", "HOLD", "DENY", "NOT_APPLICABLE"] as const),
    channel,
    currency: assertCurrency("candidate.currency", object.currency),
    requestedEffects,
    providerAliases,
  };
  return { ...candidate, normalizedSha256: canonicalSha256(candidate) };
}

export interface GateRequirement {
  gateKey: string;
  allowNotApplicable: boolean;
}

export interface GateProfileMaterial {
  registryId: StableId;
  registryVersion: ExactVersionRef;
  registrySnapshotSha256: Sha256;
  profileId: StableId;
  profileVersion: ExactVersionRef;
  exactCandidateVersionRef: ExactVersionRef;
  activeFrom: string;
  activeUntil: string | null;
  gates: GateRequirement[];
}

export interface ExactGateProfile extends GateProfileMaterial {
  profileDigest: Sha256;
}

const validateGateProfileMaterial = (input: unknown): GateProfileMaterial => {
  const object = assertClosedObject(
    "gateProfileMaterial",
    input,
    [
      "registryId",
      "registryVersion",
      "registrySnapshotSha256",
      "profileId",
      "profileVersion",
      "exactCandidateVersionRef",
      "activeFrom",
      "activeUntil",
      "gates",
    ],
  );
  if (!Array.isArray(object.gates) || object.gates.length === 0) fail("empty_gate_profile");
  const gates = object.gates.map((entry, index): GateRequirement => {
    const gate = assertClosedObject(`gateProfileMaterial.gates[${index}]`, entry, ["gateKey", "allowNotApplicable"]);
    const gateKey = assertString(`gateProfileMaterial.gates[${index}].gateKey`, gate.gateKey);
    if (!GATE_KEY_RE.test(gateKey)) fail("invalid_gate_key", gateKey);
    return {
      gateKey,
      allowNotApplicable: assertBoolean(`gateProfileMaterial.gates[${index}].allowNotApplicable`, gate.allowNotApplicable),
    };
  });
  const keys = gates.map((gate) => gate.gateKey);
  if (new Set(keys).size !== keys.length) fail("duplicate_gate_key");
  if (keys.some((key, index) => index > 0 && keys[index - 1]! > key)) fail("gate_profile_not_sorted");
  const activeFrom = assertInstant("gateProfileMaterial.activeFrom", object.activeFrom);
  let activeUntil: string | null = null;
  if (object.activeUntil !== null) activeUntil = assertInstant("gateProfileMaterial.activeUntil", object.activeUntil);
  if (activeUntil !== null && compareInstants(activeUntil, activeFrom) <= 0) fail("invalid_gate_profile_window");
  return {
    registryId: assertStableId("gateProfileMaterial.registryId", object.registryId),
    registryVersion: assertExactVersionRef("gateProfileMaterial.registryVersion", object.registryVersion),
    registrySnapshotSha256: assertSha256(
      "gateProfileMaterial.registrySnapshotSha256",
      object.registrySnapshotSha256,
    ),
    profileId: assertStableId("gateProfileMaterial.profileId", object.profileId),
    profileVersion: assertExactVersionRef("gateProfileMaterial.profileVersion", object.profileVersion),
    exactCandidateVersionRef: assertExactVersionRef(
      "gateProfileMaterial.exactCandidateVersionRef",
      object.exactCandidateVersionRef,
    ),
    activeFrom,
    activeUntil,
    gates,
  };
};

export function createExactGateProfile(input: unknown): ExactGateProfile {
  const material = validateGateProfileMaterial(input);
  return { ...material, profileDigest: canonicalSha256(material) };
}

const validateExactGateProfile = (input: unknown): ExactGateProfile => {
  const object = assertClosedObject(
    "gateProfile",
    input,
    [
      "registryId",
      "registryVersion",
      "registrySnapshotSha256",
      "profileId",
      "profileVersion",
      "exactCandidateVersionRef",
      "activeFrom",
      "activeUntil",
      "gates",
      "profileDigest",
    ],
  );
  const material = validateGateProfileMaterial({
    registryId: object.registryId,
    registryVersion: object.registryVersion,
    registrySnapshotSha256: object.registrySnapshotSha256,
    profileId: object.profileId,
    profileVersion: object.profileVersion,
    exactCandidateVersionRef: object.exactCandidateVersionRef,
    activeFrom: object.activeFrom,
    activeUntil: object.activeUntil,
    gates: object.gates,
  });
  const profileDigest = assertSha256("gateProfile.profileDigest", object.profileDigest);
  if (canonicalSha256(material) !== profileDigest) fail("gate_profile_digest_mismatch");
  return { ...material, profileDigest };
};

export interface ProviderEvidence {
  provider: string;
  providerSuccess: boolean;
  evidenceSha256: Sha256;
  observedAt: string;
}

const validateProviderEvidence = (input: unknown, index: number): ProviderEvidence => {
  const object = assertClosedObject(`providerEvidence[${index}]`, input, ["provider", "providerSuccess", "evidenceSha256", "observedAt"]);
  const provider = assertString(`providerEvidence[${index}].provider`, object.provider);
  if (!PROVIDER_ID_RE.test(provider)) fail("invalid_provider_id", `providerEvidence[${index}].provider`);
  return {
    provider,
    providerSuccess: assertBoolean(`providerEvidence[${index}].providerSuccess`, object.providerSuccess),
    evidenceSha256: assertSha256(`providerEvidence[${index}].evidenceSha256`, object.evidenceSha256),
    observedAt: assertInstant(`providerEvidence[${index}].observedAt`, object.observedAt),
  };
};

export interface ExactEcacEvaluation {
  decision: EcacDecision;
  evaluatorContractVersion: "1.1.0";
  candidateId: Uuid;
  exactCandidateVersionRef: ExactVersionRef;
  candidateSha256: Sha256;
  gateProfileId: StableId;
  gateProfileVersion: ExactVersionRef;
  gateRegistryId: StableId;
  gateRegistryVersion: ExactVersionRef;
  gateRegistrySnapshotSha256: Sha256;
  gateProfileDigest: Sha256;
  gateDigest: Sha256;
  blockers: string[];
  providerEvidenceCount: number;
  providerSuccessEvidenceCount: number;
  providerSuccessTreatedAsEvidenceOnly: true;
  moneyMovementAuthorized: false;
  providerWriteAuthorized: false;
  rightsGrantAuthorized: false;
  pricePublicationAuthorized: false;
  entitlementActivationAuthorized: false;
  selfApproval: false;
  d3HumanReserved: true;
}

export function evaluateExactEcac(input: unknown): ExactEcacEvaluation {
  const object = assertClosedObject(
    "ecacInput",
    input,
    [
      "candidate",
      "gateProfile",
      "expectedRegistrySnapshotSha256",
      "expectedGateProfileDigest",
      "expectedCandidateSha256",
      "expectedCandidateVersionRef",
      "gates",
      "evidenceRefs",
      "providerEvidence",
      "evaluatedAt",
    ],
  );
  const candidate = normalizeCandidateV11(object.candidate);
  const gateProfile = validateExactGateProfile(object.gateProfile);
  const expectedRegistrySnapshotSha256 = assertSha256(
    "ecacInput.expectedRegistrySnapshotSha256",
    object.expectedRegistrySnapshotSha256,
  );
  if (expectedRegistrySnapshotSha256 !== gateProfile.registrySnapshotSha256) {
    fail("expected_registry_snapshot_digest_mismatch");
  }
  const expectedDigest = assertSha256("ecacInput.expectedGateProfileDigest", object.expectedGateProfileDigest);
  if (expectedDigest !== gateProfile.profileDigest) fail("expected_gate_digest_mismatch");
  const expectedCandidateSha256 = assertSha256("ecacInput.expectedCandidateSha256", object.expectedCandidateSha256);
  if (expectedCandidateSha256 !== candidate.normalizedSha256) fail("expected_candidate_digest_mismatch");
  const expectedVersionRef = assertExactVersionRef("ecacInput.expectedCandidateVersionRef", object.expectedCandidateVersionRef);
  if (expectedVersionRef !== candidate.exactVersionRef) fail("stale_expected_version");
  if (gateProfile.exactCandidateVersionRef !== candidate.exactVersionRef) fail("gate_profile_candidate_version_mismatch");
  const evaluatedAt = assertInstant("ecacInput.evaluatedAt", object.evaluatedAt);
  if (compareInstants(evaluatedAt, gateProfile.activeFrom) < 0) fail("gate_profile_not_yet_effective");
  if (gateProfile.activeUntil !== null && compareInstants(evaluatedAt, gateProfile.activeUntil) >= 0) {
    fail("stale_gate_profile");
  }
  const evidenceRefs = assertStringArray("ecacInput.evidenceRefs", object.evidenceRefs, {
    nonempty: true,
    unique: true,
    sorted: true,
  });
  if (!Array.isArray(object.providerEvidence)) fail("invalid_array", "ecacInput.providerEvidence");
  const providerEvidence = object.providerEvidence.map(validateProviderEvidence).sort((left, right) =>
    compareCodeUnits(left.provider, right.provider) || compareCodeUnits(left.evidenceSha256, right.evidenceSha256),
  );
  if (new Set(providerEvidence.map((entry) => `${entry.provider}:${entry.evidenceSha256}`)).size !== providerEvidence.length) {
    fail("duplicate_provider_evidence");
  }
  if (providerEvidence.some((entry) => compareInstants(entry.observedAt, evaluatedAt) > 0)) {
    fail("provider_evidence_from_future");
  }

  const gateObject = assertRecord("ecacInput.gates", object.gates);
  const expectedKeys = gateProfile.gates.map((gate) => gate.gateKey);
  const suppliedKeys = Object.keys(gateObject).sort();
  const missingKeys = expectedKeys.filter((key) => !Object.prototype.hasOwnProperty.call(gateObject, key));
  const unexpectedKeys = suppliedKeys.filter((key) => !expectedKeys.includes(key));
  if (missingKeys.length > 0) fail("missing_gate_keys", missingKeys.join(","));
  if (unexpectedKeys.length > 0) fail("unexpected_gate_keys", unexpectedKeys.join(","));

  const gates: Record<string, GateState> = {};
  const blockers: string[] = [];
  let denied = candidate.rightsState === "DENY" || candidate.cieState === "DENY";
  if (candidate.rightsState !== "PASS") blockers.push(`rights:${candidate.rightsState}`);
  if (candidate.cieState !== "PASS" && candidate.cieState !== "NOT_APPLICABLE") blockers.push(`cie:${candidate.cieState}`);
  for (const requirement of gateProfile.gates) {
    const state = assertEnum(
      `ecacInput.gates.${requirement.gateKey}`,
      gateObject[requirement.gateKey],
      ["PASS", "HOLD", "DENY", "NOT_APPLICABLE"] as const,
    );
    gates[requirement.gateKey] = state;
    if (state === "DENY") {
      denied = true;
      blockers.push(`${requirement.gateKey}:DENY`);
    } else if (state === "HOLD" || (state === "NOT_APPLICABLE" && !requirement.allowNotApplicable)) {
      blockers.push(`${requirement.gateKey}:${state}`);
    }
  }
  blockers.sort();
  const decision: EcacDecision = denied ? "DENY" : blockers.length > 0 ? "HOLD" : "ECAC";
  const gateDigest = canonicalSha256({
    candidateId: candidate.candidateId,
    exactCandidateVersionRef: candidate.exactVersionRef,
    normalizedCandidateSha256: candidate.normalizedSha256,
    gateProfileDigest: gateProfile.profileDigest,
    gates,
    evidenceRefs,
    providerEvidence,
    evaluatedAt,
    decision,
    blockers,
  });
  return {
    decision,
    evaluatorContractVersion: "1.1.0",
    candidateId: candidate.candidateId,
    exactCandidateVersionRef: candidate.exactVersionRef,
    candidateSha256: candidate.normalizedSha256,
    gateProfileId: gateProfile.profileId,
    gateProfileVersion: gateProfile.profileVersion,
    gateRegistryId: gateProfile.registryId,
    gateRegistryVersion: gateProfile.registryVersion,
    gateRegistrySnapshotSha256: gateProfile.registrySnapshotSha256,
    gateProfileDigest: gateProfile.profileDigest,
    gateDigest,
    blockers,
    providerEvidenceCount: providerEvidence.length,
    providerSuccessEvidenceCount: providerEvidence.filter((entry) => entry.providerSuccess).length,
    providerSuccessTreatedAsEvidenceOnly: true,
    moneyMovementAuthorized: false,
    providerWriteAuthorized: false,
    rightsGrantAuthorized: false,
    pricePublicationAuthorized: false,
    entitlementActivationAuthorized: false,
    selfApproval: false,
    d3HumanReserved: true,
  };
}

export interface PriceEnvelopeInput {
  currency: Iso4217;
  costMinor: number;
  providerFeeMinor: number;
  fulfillmentMinor: number;
  supportMinor: number;
  riskMinor: number;
  royaltyMinor: number;
  commissionMinor: number;
  targetMarginBps: number;
  strategicPremiumBps: number;
}

export function computePriceEnvelopeV11(input: unknown) {
  const object = assertClosedObject(
    "priceEnvelope",
    input,
    [
      "currency",
      "costMinor",
      "providerFeeMinor",
      "fulfillmentMinor",
      "supportMinor",
      "riskMinor",
      "royaltyMinor",
      "commissionMinor",
      "targetMarginBps",
      "strategicPremiumBps",
    ],
  );
  const normalized: PriceEnvelopeInput = {
    currency: assertCurrency("priceEnvelope.currency", object.currency),
    costMinor: assertSafeInteger("priceEnvelope.costMinor", object.costMinor, { minimum: 0 }),
    providerFeeMinor: assertSafeInteger("priceEnvelope.providerFeeMinor", object.providerFeeMinor, { minimum: 0 }),
    fulfillmentMinor: assertSafeInteger("priceEnvelope.fulfillmentMinor", object.fulfillmentMinor, { minimum: 0 }),
    supportMinor: assertSafeInteger("priceEnvelope.supportMinor", object.supportMinor, { minimum: 0 }),
    riskMinor: assertSafeInteger("priceEnvelope.riskMinor", object.riskMinor, { minimum: 0 }),
    royaltyMinor: assertSafeInteger("priceEnvelope.royaltyMinor", object.royaltyMinor, { minimum: 0 }),
    commissionMinor: assertSafeInteger("priceEnvelope.commissionMinor", object.commissionMinor, { minimum: 0 }),
    targetMarginBps: assertSafeInteger("priceEnvelope.targetMarginBps", object.targetMarginBps, { minimum: 0, maximum: 9500 }),
    strategicPremiumBps: assertSafeInteger("priceEnvelope.strategicPremiumBps", object.strategicPremiumBps, { minimum: 0, maximum: 100000 }),
  };
  const base = sumSafe("priceEnvelope.base", [
    normalized.costMinor,
    normalized.providerFeeMinor,
    normalized.fulfillmentMinor,
    normalized.supportMinor,
    normalized.riskMinor,
    normalized.royaltyMinor,
    normalized.commissionMinor,
  ]);
  const sustainable = toSafeNumber(
    "priceEnvelope.sustainableMinor",
    ceilDiv(BigInt(base) * 10000n, BigInt(10000 - normalized.targetMarginBps)),
  );
  const premium = toSafeNumber(
    "priceEnvelope.premiumMinor",
    ceilDiv(BigInt(sustainable) * BigInt(10000 + normalized.strategicPremiumBps), 10000n),
  );
  const walkaway = base;
  const promotionFloor = toSafeNumber(
    "priceEnvelope.promotionFloorMinor",
    (BigInt(sustainable) + BigInt(walkaway)) / 2n,
  );
  return {
    currency: normalized.currency,
    floorMinor: base,
    sustainableMinor: sustainable,
    targetMinor: sustainable,
    premiumMinor: premium,
    promotionFloorMinor: promotionFloor,
    walkawayMinor: walkaway,
    inputsSha256: canonicalSha256(normalized),
    authority: "ADVISORY_ENVELOPE" as const,
    effectivePriceAuthorityIssued: false as const,
  };
}

export function reduceProviderReadbackV11(input: unknown) {
  const object = assertClosedObject("providerReadback", input, ["expected", "observed"]);
  const expectedObject = assertClosedObject(
    "providerReadback.expected",
    object.expected,
    ["amount", "state", "exactVersionRef"],
  );
  const observedObject = assertClosedObject(
    "providerReadback.observed",
    object.observed,
    ["amount", "state", "exactVersionRef", "providerSuccess", "providerEvidenceSha256", "observedAt"],
  );
  const expected = {
    amount: validateMoney("providerReadback.expected.amount", expectedObject.amount),
    state: assertString("providerReadback.expected.state", expectedObject.state),
    exactVersionRef: assertExactVersionRef("providerReadback.expected.exactVersionRef", expectedObject.exactVersionRef),
  };
  const observed = {
    amount: validateMoney("providerReadback.observed.amount", observedObject.amount),
    state: assertString("providerReadback.observed.state", observedObject.state),
    exactVersionRef: assertExactVersionRef("providerReadback.observed.exactVersionRef", observedObject.exactVersionRef),
    providerSuccess: assertBoolean("providerReadback.observed.providerSuccess", observedObject.providerSuccess),
    providerEvidenceSha256: assertSha256("providerReadback.observed.providerEvidenceSha256", observedObject.providerEvidenceSha256),
    observedAt: assertInstant("providerReadback.observed.observedAt", observedObject.observedAt),
  };
  const mismatchCodes: string[] = [];
  if (expected.amount.amountMinor !== observed.amount.amountMinor) mismatchCodes.push("AMOUNT_MISMATCH");
  if (expected.amount.currency !== observed.amount.currency) mismatchCodes.push("CURRENCY_MISMATCH");
  if (expected.state !== observed.state) mismatchCodes.push("STATE_MISMATCH");
  if (expected.exactVersionRef !== observed.exactVersionRef) mismatchCodes.push("VERSION_MISMATCH");
  return {
    reconciledState: mismatchCodes.length === 0 ? "PASS" as const : "HOLD" as const,
    mismatchCodes,
    institutionalEffectAllowed: false as const,
    providerSuccessTreatedAsEvidenceOnly: true as const,
    providerSuccess: observed.providerSuccess,
    readbackDigest: canonicalSha256({ expected, observed }),
  };
}

export type EntitlementState =
  | "PENDING"
  | "ACTIVE"
  | "SUSPENDED"
  | "REVOKED"
  | "REFUNDED"
  | "DISPUTED"
  | "EXPIRED";

export const ENTITLEMENT_TRANSITIONS: Readonly<Record<EntitlementState, readonly EntitlementState[]>> = Object.freeze({
  PENDING: Object.freeze(["PENDING", "ACTIVE", "SUSPENDED", "REVOKED", "REFUNDED", "DISPUTED", "EXPIRED"]),
  ACTIVE: Object.freeze(["ACTIVE", "SUSPENDED", "REVOKED", "REFUNDED", "DISPUTED", "EXPIRED"]),
  SUSPENDED: Object.freeze(["SUSPENDED", "ACTIVE", "REVOKED", "REFUNDED", "DISPUTED", "EXPIRED"]),
  DISPUTED: Object.freeze(["DISPUTED", "SUSPENDED", "REVOKED", "REFUNDED", "EXPIRED"]),
  REVOKED: Object.freeze(["REVOKED"]),
  REFUNDED: Object.freeze(["REFUNDED"]),
  EXPIRED: Object.freeze(["EXPIRED"]),
});

const ENTITLEMENT_STATES = ["PENDING", "ACTIVE", "SUSPENDED", "REVOKED", "REFUNDED", "DISPUTED", "EXPIRED"] as const;
const TERMINAL_ENTITLEMENT_STATES = new Set<EntitlementState>(["REVOKED", "REFUNDED", "EXPIRED"]);

export function transitionEntitlementV11(input: unknown) {
  const object = assertClosedObject(
    "entitlementTransition",
    input,
    [
      "entitlementId",
      "priorState",
      "requestedState",
      "priorExactVersionRef",
      "expectedPriorVersionRef",
      "qualifyingEventSha256",
      "qualifyingEventState",
      "licenseState",
      "paymentState",
      "refundState",
      "disputeState",
    ],
  );
  const entitlementId = assertStableId("entitlementTransition.entitlementId", object.entitlementId);
  const priorState = assertEnum("entitlementTransition.priorState", object.priorState, ENTITLEMENT_STATES);
  const requestedState = assertEnum("entitlementTransition.requestedState", object.requestedState, ENTITLEMENT_STATES);
  const priorExactVersionRef = assertExactVersionRef(
    "entitlementTransition.priorExactVersionRef",
    object.priorExactVersionRef,
  );
  const expectedPriorVersionRef = assertExactVersionRef(
    "entitlementTransition.expectedPriorVersionRef",
    object.expectedPriorVersionRef,
  );
  if (priorExactVersionRef !== expectedPriorVersionRef) fail("stale_entitlement_version");
  if (TERMINAL_ENTITLEMENT_STATES.has(priorState) && requestedState !== priorState) {
    fail("terminal_entitlement_reactivation", `${priorState}->${requestedState}`);
  }
  if (!ENTITLEMENT_TRANSITIONS[priorState].includes(requestedState)) {
    fail("invalid_entitlement_transition", `${priorState}->${requestedState}`);
  }
  const licenseState = assertEnum("entitlementTransition.licenseState", object.licenseState, ["PASS", "HOLD", "DENY"] as const);
  const paymentState = assertEnum("entitlementTransition.paymentState", object.paymentState, ["PASS", "HOLD", "DENY"] as const);
  const qualifyingEventState = assertEnum(
    "entitlementTransition.qualifyingEventState",
    object.qualifyingEventState,
    ["PASS", "HOLD", "DENY"] as const,
  );
  const refundState = assertEnum("entitlementTransition.refundState", object.refundState, ["NONE", "PENDING", "REFUNDED"] as const);
  const disputeState = assertEnum("entitlementTransition.disputeState", object.disputeState, ["NONE", "OPEN", "RESOLVED"] as const);
  if (requestedState === "ACTIVE" && (
    licenseState !== "PASS" || paymentState !== "PASS" || qualifyingEventState !== "PASS"
  )) {
    fail("entitlement_activation_gate_not_pass");
  }
  if (refundState === "REFUNDED" && requestedState !== "REFUNDED") fail("refund_state_transition_mismatch");
  if (disputeState === "OPEN" && requestedState !== "DISPUTED") fail("dispute_state_transition_mismatch");
  const reasonCodes = [
    priorState === requestedState ? "STATE_CONFIRMED" : "TRANSITION_VALIDATED",
    requestedState === "ACTIVE" ? "QUALIFYING_EVENT_REQUIRES_EXTERNAL_AUTHORITY" : "NON_ACTIVATING_TRANSITION",
  ];
  const transitionMaterial = {
    entitlementId,
    priorState,
    requestedState,
    priorExactVersionRef,
    qualifyingEventSha256: assertSha256("entitlementTransition.qualifyingEventSha256", object.qualifyingEventSha256),
    qualifyingEventState,
    licenseState,
    paymentState,
    refundState,
    disputeState,
  };
  return {
    priorState,
    nextState: requestedState,
    reasonCodes,
    transitionDigest: canonicalSha256(transitionMaterial),
    entitlementMutationAuthorized: false as const,
    terminalStateCreatesNewEntitlementOnRenewal: true as const,
  };
}

export type SettlementAllocationCategory = "ROYALTY" | "COMMISSION";

export interface SettlementAllocationLine {
  allocationId: Uuid;
  category: SettlementAllocationCategory;
  recipientRef: StableId;
  amountMinor: number;
}

export function reconcileSettlementV11(input: unknown) {
  const object = assertClosedObject(
    "settlement",
    input,
    [
      "orderRef",
      "currency",
      "grossMinor",
      "taxMinor",
      "refundMinor",
      "providerFeeMinor",
      "royaltyMinor",
      "commissionMinor",
      "allocationRules",
      "expectedNetMinor",
    ],
  );
  const currency = assertCurrency("settlement.currency", object.currency);
  const grossMinor = assertSafeInteger("settlement.grossMinor", object.grossMinor, { minimum: 0 });
  const taxMinor = assertSafeInteger("settlement.taxMinor", object.taxMinor, { minimum: 0 });
  const refundMinor = assertSafeInteger("settlement.refundMinor", object.refundMinor, { minimum: 0 });
  const providerFeeMinor = assertSafeInteger("settlement.providerFeeMinor", object.providerFeeMinor, { minimum: 0 });
  const royaltyMinor = assertSafeInteger("settlement.royaltyMinor", object.royaltyMinor, { minimum: 0 });
  const commissionMinor = assertSafeInteger("settlement.commissionMinor", object.commissionMinor, { minimum: 0 });
  const expectedNetMinor = assertSafeInteger("settlement.expectedNetMinor", object.expectedNetMinor, { minimum: 0 });
  if (!Array.isArray(object.allocationRules)) fail("invalid_array", "settlement.allocationRules");
  const allocationLines: SettlementAllocationLine[] = object.allocationRules.map((entry, index) => {
    const line = assertClosedObject(
      `settlement.allocationRules[${index}]`,
      entry,
      ["allocationId", "category", "recipientRef", "amountMinor"],
    );
    return {
      allocationId: assertUuid(`settlement.allocationRules[${index}].allocationId`, line.allocationId),
      category: assertEnum(
        `settlement.allocationRules[${index}].category`,
        line.category,
        ["ROYALTY", "COMMISSION"] as const,
      ),
      recipientRef: assertStableId(`settlement.allocationRules[${index}].recipientRef`, line.recipientRef),
      amountMinor: assertSafeInteger(`settlement.allocationRules[${index}].amountMinor`, line.amountMinor, { minimum: 0 }),
    };
  });
  if (new Set(allocationLines.map((line) => line.allocationId)).size !== allocationLines.length) {
    fail("duplicate_settlement_allocation_id");
  }
  const allocatedRoyalty = sumSafe(
    "settlement.allocatedRoyalty",
    allocationLines.filter((line) => line.category === "ROYALTY").map((line) => line.amountMinor),
  );
  const allocatedCommission = sumSafe(
    "settlement.allocatedCommission",
    allocationLines.filter((line) => line.category === "COMMISSION").map((line) => line.amountMinor),
  );
  if (allocatedRoyalty !== royaltyMinor) fail("royalty_allocation_mismatch");
  if (allocatedCommission !== commissionMinor) fail("commission_allocation_mismatch");
  const deductions = sumSafe("settlement.deductions", [
    taxMinor,
    refundMinor,
    providerFeeMinor,
    royaltyMinor,
    commissionMinor,
  ]);
  if (deductions > grossMinor) fail("settlement_deductions_exceed_gross");
  const netPlatformMinor = grossMinor - deductions;
  const reconciliationDeltaMinor = netPlatformMinor - expectedNetMinor;
  const normalized = {
    orderRef: assertStableId("settlement.orderRef", object.orderRef),
    currency,
    grossMinor,
    taxMinor,
    refundMinor,
    providerFeeMinor,
    royaltyMinor,
    commissionMinor,
    allocationRules: allocationLines,
    expectedNetMinor,
  };
  return {
    currency,
    netPlatformMinor,
    expectedNetMinor,
    reconciliationDeltaMinor,
    allocationLines,
    totals: {
      grossMinor,
      deductionsMinor: deductions,
      taxMinor,
      refundMinor,
      providerFeeMinor,
      royaltyMinor,
      commissionMinor,
    },
    state: reconciliationDeltaMinor === 0 ? "PASS" as const : "HOLD" as const,
    availableRemedies: reconciliationDeltaMinor === 0 ? [] : ["CORRECT", "COMPENSATE"],
    settlementAuthorityIssued: false as const,
    settlementDigest: canonicalSha256(normalized),
  };
}

export function planRollbackCompensationV11(input: unknown) {
  const object = assertClosedObject(
    "rollbackCompensation",
    input,
    [
      "effectRef",
      "effectType",
      "exactVersionRef",
      "providerReversible",
      "institutionalReversible",
      "adverseEvidenceRefs",
      "preReadSha256",
      "postFailureReadSha256",
    ],
  );
  const providerReversible = assertBoolean("rollbackCompensation.providerReversible", object.providerReversible);
  const institutionalReversible = assertBoolean(
    "rollbackCompensation.institutionalReversible",
    object.institutionalReversible,
  );
  const adverseEvidenceRefs = assertStringArray(
    "rollbackCompensation.adverseEvidenceRefs",
    object.adverseEvidenceRefs,
    { nonempty: true, unique: true, sorted: true },
  );
  const action = providerReversible && institutionalReversible ? "ROLLBACK" as const : "COMPENSATE" as const;
  const normalized = {
    effectRef: assertStableId("rollbackCompensation.effectRef", object.effectRef),
    effectType: assertString("rollbackCompensation.effectType", object.effectType),
    exactVersionRef: assertExactVersionRef("rollbackCompensation.exactVersionRef", object.exactVersionRef),
    providerReversible,
    institutionalReversible,
    adverseEvidenceRefs,
    preReadSha256: assertSha256("rollbackCompensation.preReadSha256", object.preReadSha256),
    postFailureReadSha256: assertSha256(
      "rollbackCompensation.postFailureReadSha256",
      object.postFailureReadSha256,
    ),
  };
  const planDigest = canonicalSha256(normalized);
  return {
    action,
    steps: [
      { sequence: 1, operation: "QUARANTINE_EXACT_VERSION", required: true },
      { sequence: 2, operation: "APPEND_ADVERSE_EVIDENCE", required: true },
      {
        sequence: 3,
        operation: action === "ROLLBACK" ? "EXECUTE_GOVERNED_REVERSAL" : "CREATE_GOVERNED_COMPENSATING_ACTION",
        required: true,
      },
      { sequence: 4, operation: "READ_BACK_PROVIDER_AND_INSTITUTIONAL_STATE", required: true },
      { sequence: 5, operation: "APPEND_COMPLETION_RECEIPT", required: true },
    ],
    requiresHuman: true as const,
    appendOnlyReceiptRequired: true as const,
    compensationRequired: action === "COMPENSATE",
    planDigest,
    receiptContract: {
      status: "REQUIRED" as const,
      requiredFields: [
        "receiptId",
        "effectRef",
        "exactVersionRef",
        "action",
        "beforeSha256",
        "afterSha256",
        "providerEvidenceSha256",
        "completedAt",
        "independentVerifierRef",
      ],
    },
    executionAuthorized: false as const,
  };
}

export interface StateReadEvidence {
  subjectRef: StableId;
  exactVersionRef: ExactVersionRef;
  stateSha256: Sha256;
  observedAt: string;
}

const validateStateRead = (name: string, input: unknown): StateReadEvidence => {
  const object = assertClosedObject(name, input, ["subjectRef", "exactVersionRef", "stateSha256", "observedAt"]);
  return {
    subjectRef: assertStableId(`${name}.subjectRef`, object.subjectRef),
    exactVersionRef: assertExactVersionRef(`${name}.exactVersionRef`, object.exactVersionRef),
    stateSha256: assertSha256(`${name}.stateSha256`, object.stateSha256),
    observedAt: assertInstant(`${name}.observedAt`, object.observedAt),
  };
};

export function validateMutationExecutionEnvelopeV11(input: unknown) {
  const object = assertClosedObject(
    "mutationEnvelope",
    input,
    [
      "executionId",
      "idempotencyKey",
      "wrapperId",
      "candidateId",
      "expectedVersionRef",
      "gateDecisionDigest",
      "preRead",
      "secondRead",
      "proposedEffectSha256",
      "postRead",
      "compensation",
    ],
  );
  const executionId = assertUuid("mutationEnvelope.executionId", object.executionId);
  const idempotencyKey = assertString("mutationEnvelope.idempotencyKey", object.idempotencyKey, 8);
  if (!IDEMPOTENCY_KEY_RE.test(idempotencyKey)) fail("invalid_idempotency_key");
  const wrapperId = assertStableId("mutationEnvelope.wrapperId", object.wrapperId);
  const candidateId = assertUuid("mutationEnvelope.candidateId", object.candidateId);
  const expectedVersionRef = assertExactVersionRef("mutationEnvelope.expectedVersionRef", object.expectedVersionRef);
  const gateDecisionDigest = assertSha256("mutationEnvelope.gateDecisionDigest", object.gateDecisionDigest);
  const preRead = validateStateRead("mutationEnvelope.preRead", object.preRead);
  const secondRead = validateStateRead("mutationEnvelope.secondRead", object.secondRead);
  const postRead = validateStateRead("mutationEnvelope.postRead", object.postRead);
  if (preRead.subjectRef !== secondRead.subjectRef || secondRead.subjectRef !== postRead.subjectRef) {
    fail("mutation_subject_mismatch");
  }
  if (preRead.exactVersionRef !== expectedVersionRef || secondRead.exactVersionRef !== expectedVersionRef) {
    fail("stale_expected_version");
  }
  if (preRead.stateSha256 !== secondRead.stateSha256) fail("second_read_drift");
  if (compareInstants(secondRead.observedAt, preRead.observedAt) < 0) fail("second_read_before_pre_read");
  if (compareInstants(postRead.observedAt, secondRead.observedAt) < 0) fail("post_read_before_second_read");
  const compensationObject = assertClosedObject(
    "mutationEnvelope.compensation",
    object.compensation,
    ["planSha256", "receiptRequired", "compensatingActionRef"],
  );
  const receiptRequired = assertBoolean("mutationEnvelope.compensation.receiptRequired", compensationObject.receiptRequired);
  if (!receiptRequired) fail("compensation_receipt_required");
  const normalized = {
    executionId,
    idempotencyKey,
    wrapperId,
    candidateId,
    expectedVersionRef,
    gateDecisionDigest,
    preRead,
    secondRead,
    proposedEffectSha256: assertSha256("mutationEnvelope.proposedEffectSha256", object.proposedEffectSha256),
    postRead,
    compensation: {
      planSha256: assertSha256("mutationEnvelope.compensation.planSha256", compensationObject.planSha256),
      receiptRequired,
      compensatingActionRef: assertStableId(
        "mutationEnvelope.compensation.compensatingActionRef",
        compensationObject.compensatingActionRef,
      ),
    },
  };
  return {
    ...normalized,
    envelopeDigest: canonicalSha256(normalized),
    contractState: "VALIDATED_NOT_AUTHORIZED" as const,
    effectAuthorizationIssued: false as const,
  };
}

export type MlAllowedPurpose = "RANK" | "FORECAST" | "RECOMMEND" | "DETECT_ANOMALY" | "SUGGEST_HOLD_REVIEW";
export type MlProhibitedEffect =
  | "ECAC"
  | "RIGHTS_GRANT"
  | "PRICE_PUBLICATION"
  | "MONEY_MOVEMENT"
  | "PROVIDER_WRITE"
  | "PAYOUT"
  | "ENTITLEMENT_ACTIVATION"
  | "VOTE";

const ML_ALLOWED_PURPOSES = ["RANK", "FORECAST", "RECOMMEND", "DETECT_ANOMALY", "SUGGEST_HOLD_REVIEW"] as const;
const ML_PROHIBITED_EFFECTS = [
  "ECAC",
  "RIGHTS_GRANT",
  "PRICE_PUBLICATION",
  "MONEY_MOVEMENT",
  "PROVIDER_WRITE",
  "PAYOUT",
  "ENTITLEMENT_ACTIVATION",
  "VOTE",
] as const;

const validateMlRequest = (input: unknown) => {
  const object = assertClosedObject(
    "mlRequest",
    input,
    ["purpose", "featureSchemaVersion", "observationWindow", "requestedEffects"],
  );
  const purpose = assertEnum("mlRequest.purpose", object.purpose, ML_ALLOWED_PURPOSES);
  const requestedEffects = assertStringArray("mlRequest.requestedEffects", object.requestedEffects, { unique: true });
  const authorityAttempts = requestedEffects.filter((effect) =>
    (ML_PROHIBITED_EFFECTS as readonly string[]).includes(effect),
  );
  if (authorityAttempts.length > 0) fail("ml_authority_attempt", authorityAttempts.sort().join(","));
  if (requestedEffects.some((effect) => !(ML_ALLOWED_PURPOSES as readonly string[]).includes(effect))) {
    fail("unsupported_ml_effect");
  }
  return {
    purpose,
    featureSchemaVersion: assertExactVersionRef("mlRequest.featureSchemaVersion", object.featureSchemaVersion),
    observationWindow: assertString("mlRequest.observationWindow", object.observationWindow),
    requestedEffects: requestedEffects.sort(),
  };
};

const assertDerivedFinite = (name: string, value: number): number => {
  if (!Number.isFinite(value)) fail("non_finite_ml_output", name);
  return value;
};

const advisoryOutput = (input: {
  modelId: StableId;
  modelVersion: ExactVersionRef;
  modelDigest: Sha256;
  score: number;
  confidence: number;
  explanations: Array<{ code: string; value: number }>;
  featureMaterial: unknown;
  holdRecommended: boolean;
}) => {
  const score = assertDerivedFinite("mlOutput.score", input.score);
  const confidence = assertDerivedFinite("mlOutput.confidence", input.confidence);
  if (confidence < 0 || confidence > 1) fail("ml_confidence_out_of_bounds");
  const explanations = input.explanations.map((explanation, index) => ({
    code: explanation.code,
    value: assertDerivedFinite(`mlOutput.explanations[${index}].value`, explanation.value),
  }));
  return {
    modelId: input.modelId,
    modelVersion: input.modelVersion,
    modelDigest: input.modelDigest,
    score,
    confidence,
    explanations,
    featureDigest: canonicalSha256(input.featureMaterial),
    recommendation: input.holdRecommended ? "SUGGEST_HOLD_REVIEW" as const : "REVIEW" as const,
    authority: "ADVISORY_ONLY" as const,
    institutionalEffectAllowed: false as const,
    prohibitedEffects: [...ML_PROHIBITED_EFFECTS],
  };
};

const sigmoid = (value: number) => 1 / (1 + Math.exp(-value));

export function advisoryDemandScoreV11(input: unknown) {
  const object = assertClosedObject("demandScore", input, ["request", "features", "modelVersion", "modelDigest"]);
  const request = validateMlRequest(object.request);
  const featuresObject = assertClosedObject(
    "demandScore.features",
    object.features,
    ["viewsZ", "conversionZ", "saveZ", "searchZ", "seasonality"],
  );
  const features = {
    viewsZ: assertFiniteNumber("demandScore.features.viewsZ", featuresObject.viewsZ),
    conversionZ: assertFiniteNumber("demandScore.features.conversionZ", featuresObject.conversionZ),
    saveZ: assertFiniteNumber("demandScore.features.saveZ", featuresObject.saveZ),
    searchZ: assertFiniteNumber("demandScore.features.searchZ", featuresObject.searchZ),
    seasonality: assertFiniteNumber("demandScore.features.seasonality", featuresObject.seasonality),
  };
  const raw = 0.28 * features.viewsZ + 0.32 * features.conversionZ + 0.14 * features.saveZ
    + 0.18 * features.searchZ + 0.08 * features.seasonality;
  assertDerivedFinite("demandScore.raw", raw);
  return advisoryOutput({
    modelId: "ct.ml.thriveevergreen.demand-score",
    modelVersion: assertExactVersionRef("demandScore.modelVersion", object.modelVersion),
    modelDigest: assertSha256("demandScore.modelDigest", object.modelDigest),
    score: sigmoid(raw),
    confidence: 0,
    explanations: [
      { code: "WEIGHTED_DEMAND_SIGNAL", value: raw },
      { code: `PURPOSE_${request.purpose}`, value: 1 },
    ],
    featureMaterial: { request, features },
    holdRecommended: false,
  });
}

export function advisoryPriceElasticityV11(input: unknown) {
  const object = assertClosedObject("priceElasticity", input, ["request", "features", "modelVersion", "modelDigest"]);
  const request = validateMlRequest(object.request);
  const featuresObject = assertClosedObject(
    "priceElasticity.features",
    object.features,
    ["priceChangePct", "demandChangePct", "sampleWeight"],
  );
  const features = {
    priceChangePct: assertFiniteNumber("priceElasticity.features.priceChangePct", featuresObject.priceChangePct),
    demandChangePct: assertFiniteNumber("priceElasticity.features.demandChangePct", featuresObject.demandChangePct),
    sampleWeight: assertFiniteNumber("priceElasticity.features.sampleWeight", featuresObject.sampleWeight, { minimum: 0, maximum: 1 }),
  };
  if (Math.abs(features.priceChangePct) < 0.001) fail("insufficient_price_delta");
  const elasticity = (features.demandChangePct / features.priceChangePct) * features.sampleWeight;
  assertDerivedFinite("priceElasticity.elasticity", elasticity);
  return advisoryOutput({
    modelId: "ct.ml.thriveevergreen.price-elasticity-advisor",
    modelVersion: assertExactVersionRef("priceElasticity.modelVersion", object.modelVersion),
    modelDigest: assertSha256("priceElasticity.modelDigest", object.modelDigest),
    score: elasticity,
    confidence: features.sampleWeight,
    explanations: [
      { code: "WEIGHTED_ELASTICITY", value: elasticity },
      { code: `PURPOSE_${request.purpose}`, value: 1 },
    ],
    featureMaterial: { request, features },
    holdRecommended: false,
  });
}

export function advisoryAnomalyRiskV11(input: unknown) {
  const object = assertClosedObject("anomalyRisk", input, ["request", "features", "modelVersion", "modelDigest"]);
  const request = validateMlRequest(object.request);
  const featuresObject = assertClosedObject(
    "anomalyRisk.features",
    object.features,
    ["refundZ", "disputeZ", "priceDriftZ", "providerMismatchZ", "fulfillmentLatencyZ"],
  );
  const features = {
    refundZ: assertFiniteNumber("anomalyRisk.features.refundZ", featuresObject.refundZ),
    disputeZ: assertFiniteNumber("anomalyRisk.features.disputeZ", featuresObject.disputeZ),
    priceDriftZ: assertFiniteNumber("anomalyRisk.features.priceDriftZ", featuresObject.priceDriftZ),
    providerMismatchZ: assertFiniteNumber("anomalyRisk.features.providerMismatchZ", featuresObject.providerMismatchZ),
    fulfillmentLatencyZ: assertFiniteNumber("anomalyRisk.features.fulfillmentLatencyZ", featuresObject.fulfillmentLatencyZ),
  };
  const weighted = 0.25 * Math.abs(features.refundZ) + 0.25 * Math.abs(features.disputeZ)
    + 0.18 * Math.abs(features.priceDriftZ) + 0.20 * Math.abs(features.providerMismatchZ)
    + 0.12 * Math.abs(features.fulfillmentLatencyZ);
  assertDerivedFinite("anomalyRisk.weighted", weighted);
  return advisoryOutput({
    modelId: "ct.ml.thriveevergreen.anomaly-risk",
    modelVersion: assertExactVersionRef("anomalyRisk.modelVersion", object.modelVersion),
    modelDigest: assertSha256("anomalyRisk.modelDigest", object.modelDigest),
    score: Math.min(1, weighted / 5),
    confidence: 0,
    explanations: [
      { code: "WEIGHTED_ANOMALY_SIGNAL", value: weighted },
      { code: `PURPOSE_${request.purpose}`, value: 1 },
    ],
    featureMaterial: { request, features },
    holdRecommended: weighted >= 3.5,
  });
}

export const GENERALIZED_DISPATCH_STATE = Object.freeze({
  toolId: "ct.mcp-tool.thriveevergreen.publish.dispatch",
  contractVersion: "1.1.0",
  decision: "HOLD" as const,
  generalizedDispatchEnabled: false as const,
  wrapperOnly: true as const,
  blocker: "generalized_external_dispatch_not_independently_certified",
});

export function evaluateDispatchV11(input: unknown) {
  const object = assertClosedObject(
    "dispatch",
    input,
    [
      "toolId",
      "mode",
      "wrapperId",
      "requestedEnabled",
      "expectedGateDigest",
      "gateDecisionDigest",
      "idempotencyKey",
    ],
  );
  if (object.toolId !== GENERALIZED_DISPATCH_STATE.toolId) fail("unauthorized_dispatch_tool");
  if (object.mode !== "WRAPPER_ONLY") fail("unauthorized_generalized_dispatch");
  const wrapperId = assertStableId("dispatch.wrapperId", object.wrapperId);
  if (assertBoolean("dispatch.requestedEnabled", object.requestedEnabled)) fail("unauthorized_generalized_dispatch");
  const expectedGateDigest = assertSha256("dispatch.expectedGateDigest", object.expectedGateDigest);
  const gateDecisionDigest = assertSha256("dispatch.gateDecisionDigest", object.gateDecisionDigest);
  if (expectedGateDigest !== gateDecisionDigest) fail("dispatch_gate_digest_mismatch");
  const idempotencyKey = assertString("dispatch.idempotencyKey", object.idempotencyKey, 8);
  if (!IDEMPOTENCY_KEY_RE.test(idempotencyKey)) fail("invalid_idempotency_key");
  return {
    ...GENERALIZED_DISPATCH_STATE,
    wrapperId,
    idempotencyKey,
    wrapperExecutionAuthorized: false as const,
    providerWriteAuthorized: false as const,
    dispatchEvaluationDigest: canonicalSha256({
      toolId: object.toolId,
      mode: object.mode,
      wrapperId,
      requestedEnabled: false,
      expectedGateDigest,
      gateDecisionDigest,
      idempotencyKey,
    }),
  };
}
