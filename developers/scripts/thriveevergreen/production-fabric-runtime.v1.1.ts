// ThriveEvergreen Production Fabric v1.1 — fail-closed deterministic and advisory helpers.
//
// This source supersedes v1 for new integrations only. It does not grant ECAC,
// sign transactions, move money, publish prices, write providers, grant rights,
// activate entitlements, or expose generalized dispatch. Exact ECAC remains external.

import { createHash } from "node:crypto";

export type Verdict = "ECAC_CANDIDATE" | "HOLD" | "DENY";
export type EvidenceState = "PASS" | "HOLD" | "DENY" | "NOT_APPLICABLE";
export type CandidateEvidenceState = Exclude<EvidenceState, "NOT_APPLICABLE">;

export class FabricContractError extends Error {
  readonly code: string;

  constructor(code: string, message = code) {
    super(message);
    this.name = "FabricContractError";
    this.code = code;
  }
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256_RE = /^[0-9a-f]{64}$/i;
const ISO4217_RE = /^[A-Z]{3}$/;
const STABLE_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{1,254}$/;
const EFFECT_RE = /^[a-z][a-z0-9._:-]{1,127}$/;
const SKU_PART_RE = /^[A-Z0-9][A-Z0-9.-]{0,63}$/;

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value) &&
  Object.getPrototypeOf(value) === Object.prototype;

const canonicalize = (value: unknown): string => {
  if (value === null) return "null";
  if (typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new FabricContractError("NON_FINITE_DIGEST_VALUE");
    return JSON.stringify(Object.is(value, -0) ? 0 : value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  if (isPlainObject(value)) {
    const entries = Object.keys(value).sort().map((key) => {
      const member = value[key];
      if (member === undefined) throw new FabricContractError("UNDEFINED_DIGEST_VALUE");
      return `${JSON.stringify(key)}:${canonicalize(member)}`;
    });
    return `{${entries.join(",")}}`;
  }
  throw new FabricContractError("UNSUPPORTED_DIGEST_VALUE");
};

export const canonicalSha256 = (value: unknown) =>
  createHash("sha256").update(canonicalize(value)).digest("hex");

const assertStrictObject = (
  value: unknown,
  contract: string,
  allowed: readonly string[],
  required: readonly string[],
): Record<string, unknown> => {
  if (!isPlainObject(value)) throw new FabricContractError(`${contract}_OBJECT_REQUIRED`);
  const keys = Object.keys(value);
  const unexpected = keys.filter((key) => !allowed.includes(key));
  if (unexpected.length) {
    throw new FabricContractError(`${contract}_ADDITIONAL_PROPERTY`, unexpected.sort().join(","));
  }
  const missing = required.filter((key) => !(key in value));
  if (missing.length) {
    throw new FabricContractError(`${contract}_REQUIRED_PROPERTY`, missing.sort().join(","));
  }
  return value;
};

const requiredString = (value: unknown, field: string, maxLength = 255): string => {
  if (typeof value !== "string") throw new FabricContractError(`${field}_STRING_REQUIRED`);
  const normalized = value.normalize("NFKC").trim();
  if (!normalized) throw new FabricContractError(`${field}_EMPTY`);
  if (normalized.length > maxLength) throw new FabricContractError(`${field}_TOO_LONG`);
  return normalized;
};

const assertSafeInteger = (
  value: unknown,
  field: string,
  minimum = 0,
  maximum = Number.MAX_SAFE_INTEGER,
): number => {
  if (!Number.isSafeInteger(value) || (value as number) < minimum || (value as number) > maximum) {
    throw new FabricContractError(`${field}_SAFE_INTEGER_RANGE`);
  }
  return value as number;
};

const assertBoolean = (value: unknown, field: string): boolean => {
  if (typeof value !== "boolean") throw new FabricContractError(`${field}_BOOLEAN_REQUIRED`);
  return value;
};

const assertEvidenceState = (
  value: unknown,
  field: string,
  allowNotApplicable = true,
): EvidenceState => {
  const allowed = allowNotApplicable
    ? ["PASS", "HOLD", "DENY", "NOT_APPLICABLE"]
    : ["PASS", "HOLD", "DENY"];
  if (typeof value !== "string" || !allowed.includes(value)) {
    throw new FabricContractError(`${field}_EVIDENCE_STATE`);
  }
  return value as EvidenceState;
};

export interface CommerceCandidate {
  candidateId: string;
  subjectRef: string;
  exactVersionRef: string;
  contentSha256: string;
  rightsState: CandidateEvidenceState;
  cieState?: EvidenceState;
  channel: string;
  currency: string;
  requestedEffects?: string[];
  providerAliases?: Record<string, string>;
}

export interface NormalizedCommerceCandidate extends CommerceCandidate {
  cieState: EvidenceState;
  requestedEffects: string[];
  providerAliases: Record<string, string>;
  normalizedSha256: string;
}

export function normalizeCandidate(input: unknown): NormalizedCommerceCandidate {
  const candidate = assertStrictObject(
    input,
    "CANDIDATE",
    [
      "candidateId", "subjectRef", "exactVersionRef", "contentSha256", "rightsState",
      "cieState", "channel", "currency", "requestedEffects", "providerAliases",
    ],
    ["candidateId", "subjectRef", "exactVersionRef", "contentSha256", "rightsState", "channel", "currency"],
  );

  const candidateId = requiredString(candidate.candidateId, "candidateId", 36).toLowerCase();
  if (!UUID_RE.test(candidateId)) throw new FabricContractError("candidateId_UUID");

  const subjectRef = requiredString(candidate.subjectRef, "subjectRef");
  if (!STABLE_ID_RE.test(subjectRef)) throw new FabricContractError("subjectRef_STABLE_ID");

  const exactVersionRef = requiredString(candidate.exactVersionRef, "exactVersionRef");
  const contentSha256 = requiredString(candidate.contentSha256, "contentSha256", 64).toLowerCase();
  if (!SHA256_RE.test(contentSha256)) throw new FabricContractError("contentSha256_SHA256");

  const rightsState = assertEvidenceState(candidate.rightsState, "rightsState", false) as CandidateEvidenceState;
  const cieState = candidate.cieState === undefined
    ? "NOT_APPLICABLE"
    : assertEvidenceState(candidate.cieState, "cieState");
  const channel = requiredString(candidate.channel, "channel", 128).toLowerCase();
  const currency = requiredString(candidate.currency, "currency", 3).toUpperCase();
  if (!ISO4217_RE.test(currency)) throw new FabricContractError("currency_ISO4217");

  const effectsValue = candidate.requestedEffects ?? [];
  if (!Array.isArray(effectsValue)) throw new FabricContractError("requestedEffects_ARRAY_REQUIRED");
  const requestedEffects = [...new Set(effectsValue.map((value, index) => {
    const effect = requiredString(value, `requestedEffects_${index}`, 128).toLowerCase();
    if (!EFFECT_RE.test(effect)) throw new FabricContractError("requestedEffects_EFFECT_ID");
    return effect;
  }))].sort();

  const aliasesValue = candidate.providerAliases ?? {};
  if (!isPlainObject(aliasesValue)) throw new FabricContractError("providerAliases_OBJECT_REQUIRED");
  const providerAliases: Record<string, string> = {};
  for (const key of Object.keys(aliasesValue).sort()) {
    const aliasKey = requiredString(key, "providerAliasKey", 128).toLowerCase();
    if (!EFFECT_RE.test(aliasKey)) throw new FabricContractError("providerAliasKey_STABLE_ID");
    providerAliases[aliasKey] = requiredString(aliasesValue[key], `providerAliases_${aliasKey}`, 255);
  }

  const normalized: Omit<NormalizedCommerceCandidate, "normalizedSha256"> = {
    candidateId,
    subjectRef,
    exactVersionRef,
    contentSha256,
    rightsState,
    cieState,
    channel,
    currency,
    requestedEffects,
    providerAliases,
  };
  return { ...normalized, normalizedSha256: canonicalSha256(normalized) };
}

export function evaluateEcac(input: unknown) {
  const value = assertStrictObject(
    input,
    "ECAC_INPUT",
    ["candidate", "gates", "requiredGateKeys"],
    ["candidate", "gates", "requiredGateKeys"],
  );
  const candidate = normalizeCandidate(value.candidate);
  if (!isPlainObject(value.gates)) throw new FabricContractError("gates_OBJECT_REQUIRED");
  if (!Array.isArray(value.requiredGateKeys)) throw new FabricContractError("requiredGateKeys_ARRAY_REQUIRED");

  const gates: Record<string, EvidenceState> = {};
  for (const key of Object.keys(value.gates).sort()) {
    const gateKey = requiredString(key, "gateKey", 128);
    if (!EFFECT_RE.test(gateKey)) throw new FabricContractError("gateKey_STABLE_ID");
    gates[gateKey] = assertEvidenceState(value.gates[key], `gate_${gateKey}`);
  }
  const requiredGateKeys = [...new Set(value.requiredGateKeys.map((key, index) => {
    const gateKey = requiredString(key, `requiredGateKeys_${index}`, 128);
    if (!EFFECT_RE.test(gateKey)) throw new FabricContractError("requiredGateKeys_STABLE_ID");
    return gateKey;
  }))].sort();

  const blockers: string[] = [];
  let denied = false;
  if (!requiredGateKeys.length) blockers.push("required_gates:EMPTY");

  for (const key of requiredGateKeys) {
    const state = gates[key];
    if (state === "DENY") {
      denied = true;
      blockers.push(`${key}:DENY`);
    } else if (state !== "PASS") {
      blockers.push(`${key}:${state ?? "MISSING"}`);
    }
  }
  for (const [key, state] of Object.entries(gates)) {
    if (!requiredGateKeys.includes(key) && state === "DENY") {
      denied = true;
      blockers.push(`${key}:DENY`);
    }
  }
  if (candidate.rightsState === "DENY") {
    denied = true;
    blockers.push("rights:DENY");
  } else if (candidate.rightsState !== "PASS") {
    blockers.push(`rights:${candidate.rightsState}`);
  }

  const orderedBlockers = [...new Set(blockers)].sort();
  const decision: Verdict = denied ? "DENY" : orderedBlockers.length ? "HOLD" : "ECAC_CANDIDATE";
  const envelope = {
    schemaVersion: "1.1.0",
    candidateId: candidate.candidateId,
    exactVersionRef: candidate.exactVersionRef,
    normalizedCandidateSha256: candidate.normalizedSha256,
    gates,
    requiredGateKeys,
    decision,
    blockers: orderedBlockers,
  };
  return {
    decision,
    blockers: orderedBlockers,
    gateDigest: canonicalSha256(envelope),
    moneyMovementAuthorized: false,
    providerWriteAuthorized: false,
    rightsGrantAuthorized: false,
    pricePublicationAuthorized: false,
    entitlementMutationAuthorized: false,
    publicationAuthorityGranted: false,
    selfApproval: false,
    d3HumanReserved: true,
    authority: "EXTERNAL_EXACT_ECAC_REQUIRED" as const,
  };
}

const cleanSkuPart = (value: string) => value
  .normalize("NFKC")
  .trim()
  .replace(/[^A-Za-z0-9.-]+/g, "-")
  .replace(/^-+|-+$/g, "")
  .toUpperCase();

export function computeSkuKey(input: unknown) {
  const value = assertStrictObject(
    input,
    "SKU_INPUT",
    ["brand", "className", "asset", "variant", "license", "version"],
    ["brand", "className", "asset", "variant", "license", "version"],
  );
  const fieldNames = ["brand", "className", "asset", "variant", "license", "version"] as const;
  const canonicalParts: Record<string, string> = {};
  const displayParts: Record<string, string> = {};
  const lossyFields: string[] = [];
  for (const field of fieldNames) {
    const exact = requiredString(value[field], field, 64).toUpperCase();
    const display = cleanSkuPart(exact);
    if (!display || !SKU_PART_RE.test(display)) throw new FabricContractError(`${field}_SKU_PART`);
    canonicalParts[field] = exact;
    displayParts[field] = display;
    if (display !== exact) lossyFields.push(field);
  }
  const skuCandidate = [
    "CT", displayParts.brand, displayParts.className, displayParts.asset,
    displayParts.variant, displayParts.license, displayParts.version,
  ].join("-");
  const skuKeySha256 = canonicalSha256({ schemaVersion: "1.1.0", canonicalParts });
  return {
    skuCandidate,
    skuCandidateSha256: canonicalSha256(skuCandidate),
    skuKeySha256,
    collisionSensitiveKey: `ct.sku-key.v1.1.${skuKeySha256}`,
    reviewState: lossyFields.length ? "HOLD" as const : "PROPOSAL_ONLY" as const,
    holdReasons: lossyFields.length ? ["LOSSY_SKU_NORMALIZATION"] : [],
    lossyFields,
    authority: "PROPOSAL_ONLY" as const,
  };
}

export function classifyTopology(input: unknown) {
  const value = assertStrictObject(
    input,
    "TOPOLOGY_INPUT",
    ["firstParty", "recurring", "marketplace", "booking", "usageBased", "physical", "licenseBearing"],
    ["firstParty", "recurring", "marketplace", "booking", "usageBased", "physical", "licenseBearing"],
  );
  const normalized = {
    firstParty: assertBoolean(value.firstParty, "firstParty"),
    recurring: assertBoolean(value.recurring, "recurring"),
    marketplace: assertBoolean(value.marketplace, "marketplace"),
    booking: assertBoolean(value.booking, "booking"),
    usageBased: assertBoolean(value.usageBased, "usageBased"),
    physical: assertBoolean(value.physical, "physical"),
    licenseBearing: assertBoolean(value.licenseBearing, "licenseBearing"),
  };
  let topology = "direct_one_time";
  if (normalized.marketplace) topology = "marketplace";
  else if (normalized.booking) topology = "booking";
  else if (normalized.usageBased) topology = "usage_based";
  else if (normalized.recurring) topology = "subscription";
  else if (normalized.physical) topology = "physical_direct";
  else if (normalized.licenseBearing) topology = "license_direct";
  return {
    topology,
    merchantOfRecordReviewRequired: normalized.marketplace || !normalized.firstParty,
    topologySha256: canonicalSha256({ ...normalized, topology }),
    authority: "CLASSIFICATION_ONLY" as const,
  };
}

export function computePriceEnvelope(input: unknown) {
  const value = assertStrictObject(
    input,
    "PRICE_INPUT",
    [
      "costMinor", "providerFeeMinor", "fulfillmentMinor", "supportMinor", "riskMinor",
      "royaltyMinor", "commissionMinor", "targetMarginBps", "strategicPremiumBps",
    ],
    [
      "costMinor", "providerFeeMinor", "fulfillmentMinor", "supportMinor", "riskMinor",
      "royaltyMinor", "commissionMinor", "targetMarginBps",
    ],
  );
  const normalized = {
    costMinor: assertSafeInteger(value.costMinor, "costMinor"),
    providerFeeMinor: assertSafeInteger(value.providerFeeMinor, "providerFeeMinor"),
    fulfillmentMinor: assertSafeInteger(value.fulfillmentMinor, "fulfillmentMinor"),
    supportMinor: assertSafeInteger(value.supportMinor, "supportMinor"),
    riskMinor: assertSafeInteger(value.riskMinor, "riskMinor"),
    royaltyMinor: assertSafeInteger(value.royaltyMinor, "royaltyMinor"),
    commissionMinor: assertSafeInteger(value.commissionMinor, "commissionMinor"),
    targetMarginBps: assertSafeInteger(value.targetMarginBps, "targetMarginBps", 0, 9500),
    strategicPremiumBps: value.strategicPremiumBps === undefined
      ? 0
      : assertSafeInteger(value.strategicPremiumBps, "strategicPremiumBps", 0, 100000),
  };
  const costs = [
    normalized.costMinor, normalized.providerFeeMinor, normalized.fulfillmentMinor,
    normalized.supportMinor, normalized.riskMinor, normalized.royaltyMinor, normalized.commissionMinor,
  ];
  const base = costs.reduce((total, member) => {
    const next = total + member;
    if (!Number.isSafeInteger(next)) throw new FabricContractError("priceBase_SAFE_INTEGER_RANGE");
    return next;
  }, 0);
  const sustainable = Math.ceil(base / (1 - normalized.targetMarginBps / 10000));
  const premium = Math.ceil(sustainable * (1 + normalized.strategicPremiumBps / 10000));
  if (![sustainable, premium].every(Number.isSafeInteger)) {
    throw new FabricContractError("priceEnvelope_SAFE_INTEGER_RANGE");
  }
  const walkaway = base;
  const promotionFloor = Math.max(walkaway, Math.floor((sustainable + walkaway) / 2));
  return {
    floorMinor: base,
    sustainableMinor: sustainable,
    targetMinor: sustainable,
    premiumMinor: premium,
    promotionFloorMinor: promotionFloor,
    walkawayMinor: walkaway,
    inputsSha256: canonicalSha256(normalized),
    authority: "ADVISORY_ENVELOPE" as const,
    effectivePriceAuthorized: false,
  };
}

export function guardMargin(input: unknown) {
  const value = assertStrictObject(
    input,
    "MARGIN_INPUT",
    ["priceMinor", "totalCostMinor", "minimumMarginBps"],
    ["priceMinor", "totalCostMinor", "minimumMarginBps"],
  );
  const priceMinor = assertSafeInteger(value.priceMinor, "priceMinor", 1);
  const totalCostMinor = assertSafeInteger(value.totalCostMinor, "totalCostMinor");
  const minimumMarginBps = assertSafeInteger(value.minimumMarginBps, "minimumMarginBps", 0, 10000);
  const marginMinor = priceMinor - totalCostMinor;
  const marginBps = Math.floor((marginMinor / priceMinor) * 10000);
  const pass = marginBps >= minimumMarginBps;
  return { pass, marginMinor, marginBps, state: pass ? "PASS" as const : "HOLD" as const };
}

export function reduceProviderReadback(input: unknown) {
  const value = assertStrictObject(input, "READBACK_INPUT", ["expected", "observed"], ["expected", "observed"]);
  const expected = assertStrictObject(value.expected, "READBACK_EXPECTED", ["amountMinor", "currency", "state"], []);
  const observed = assertStrictObject(
    value.observed,
    "READBACK_OBSERVED",
    ["amountMinor", "currency", "state", "evidenceSha256"],
    ["evidenceSha256"],
  );
  const mismatches: string[] = [];
  const expectationKeys = ["amountMinor", "currency", "state"].filter((key) => expected[key] !== undefined);
  if (!expectationKeys.length) mismatches.push("EXPECTATION_REQUIRED");

  const evidenceSha256 = typeof observed.evidenceSha256 === "string"
    ? observed.evidenceSha256.trim().toLowerCase()
    : "";
  if (!SHA256_RE.test(evidenceSha256)) mismatches.push("EVIDENCE_DIGEST_INVALID");

  const normalizedExpected: Record<string, number | string> = {};
  const normalizedObserved: Record<string, number | string> = { evidenceSha256 };
  if (expected.amountMinor !== undefined) {
    normalizedExpected.amountMinor = assertSafeInteger(expected.amountMinor, "expected_amountMinor");
    if (observed.amountMinor === undefined) mismatches.push("AMOUNT_MISSING");
    else {
      normalizedObserved.amountMinor = assertSafeInteger(observed.amountMinor, "observed_amountMinor");
      if (normalizedExpected.amountMinor !== normalizedObserved.amountMinor) mismatches.push("AMOUNT_MISMATCH");
    }
  }
  if (expected.currency !== undefined) {
    const currency = requiredString(expected.currency, "expected_currency", 3).toUpperCase();
    if (!ISO4217_RE.test(currency)) throw new FabricContractError("expected_currency_ISO4217");
    normalizedExpected.currency = currency;
    if (observed.currency === undefined) mismatches.push("CURRENCY_MISSING");
    else {
      const observedCurrency = requiredString(observed.currency, "observed_currency", 3).toUpperCase();
      if (!ISO4217_RE.test(observedCurrency)) mismatches.push("OBSERVED_CURRENCY_INVALID");
      normalizedObserved.currency = observedCurrency;
      if (currency !== observedCurrency) mismatches.push("CURRENCY_MISMATCH");
    }
  }
  if (expected.state !== undefined) {
    const state = requiredString(expected.state, "expected_state", 128);
    normalizedExpected.state = state;
    if (observed.state === undefined) mismatches.push("STATE_MISSING");
    else {
      const observedState = requiredString(observed.state, "observed_state", 128);
      normalizedObserved.state = observedState;
      if (state !== observedState) mismatches.push("STATE_MISMATCH");
    }
  }
  const mismatchCodes = [...new Set(mismatches)].sort();
  return {
    reconciledState: mismatchCodes.length ? "HOLD" as const : "PASS" as const,
    mismatchCodes,
    institutionalEffectAllowed: false,
    readbackDigest: canonicalSha256({ expected: normalizedExpected, observed: normalizedObserved }),
  };
}

export type EntitlementState = "PENDING" | "ACTIVE" | "SUSPENDED" | "REVOKED" | "REFUNDED" | "DISPUTED" | "EXPIRED";
const ENTITLEMENT_STATES: EntitlementState[] = ["PENDING", "ACTIVE", "SUSPENDED", "REVOKED", "REFUNDED", "DISPUTED", "EXPIRED"];
const TERMINAL_ENTITLEMENT_STATES = new Set<EntitlementState>(["REVOKED", "REFUNDED", "DISPUTED", "EXPIRED"]);

export function reduceEntitlementState(input: unknown) {
  const value = assertStrictObject(
    input,
    "ENTITLEMENT_INPUT",
    ["prior", "qualifyingEvent", "licensePass", "paymentPass", "refunded", "disputed", "expired"],
    ["prior", "qualifyingEvent", "licensePass", "paymentPass"],
  );
  if (typeof value.prior !== "string" || !ENTITLEMENT_STATES.includes(value.prior as EntitlementState)) {
    throw new FabricContractError("prior_ENTITLEMENT_STATE");
  }
  const prior = value.prior as EntitlementState;
  const normalized = {
    prior,
    qualifyingEvent: assertBoolean(value.qualifyingEvent, "qualifyingEvent"),
    licensePass: assertBoolean(value.licensePass, "licensePass"),
    paymentPass: assertBoolean(value.paymentPass, "paymentPass"),
    refunded: value.refunded === undefined ? false : assertBoolean(value.refunded, "refunded"),
    disputed: value.disputed === undefined ? false : assertBoolean(value.disputed, "disputed"),
    expired: value.expired === undefined ? false : assertBoolean(value.expired, "expired"),
  };
  let next: EntitlementState = prior;
  const reasons: string[] = [];
  if (prior === "REVOKED") reasons.push("TERMINAL_REVOKED");
  else if (normalized.refunded) { next = "REFUNDED"; reasons.push("REFUNDED"); }
  else if (normalized.disputed) { next = "DISPUTED"; reasons.push("DISPUTED"); }
  else if (normalized.expired) { next = "EXPIRED"; reasons.push("EXPIRED"); }
  else if (TERMINAL_ENTITLEMENT_STATES.has(prior)) reasons.push(`TERMINAL_${prior}`);
  else if (normalized.qualifyingEvent && normalized.licensePass && normalized.paymentPass) {
    next = "ACTIVE";
    reasons.push("QUALIFYING_EVENT_RECONCILED");
  } else if (!normalized.licensePass || !normalized.paymentPass) {
    next = "SUSPENDED";
    reasons.push("GATE_NOT_PASS");
  }
  return { nextState: next, reasonCodes: reasons, entitlementMutationAuthorized: false };
}

export function reconcileSettlement(input: unknown) {
  const value = assertStrictObject(
    input,
    "SETTLEMENT_INPUT",
    ["grossMinor", "taxMinor", "refundMinor", "providerFeeMinor", "royaltyMinor", "commissionMinor", "expectedNetMinor"],
    ["grossMinor", "taxMinor", "refundMinor", "providerFeeMinor", "royaltyMinor", "commissionMinor"],
  );
  const expectedNetMinor = value.expectedNetMinor === undefined
    ? null
    : assertSafeInteger(value.expectedNetMinor, "expectedNetMinor", -Number.MAX_SAFE_INTEGER);
  const normalized = {
    grossMinor: assertSafeInteger(value.grossMinor, "grossMinor"),
    taxMinor: assertSafeInteger(value.taxMinor, "taxMinor"),
    refundMinor: assertSafeInteger(value.refundMinor, "refundMinor"),
    providerFeeMinor: assertSafeInteger(value.providerFeeMinor, "providerFeeMinor"),
    royaltyMinor: assertSafeInteger(value.royaltyMinor, "royaltyMinor"),
    commissionMinor: assertSafeInteger(value.commissionMinor, "commissionMinor"),
    expectedNetMinor,
  };
  const netPlatformMinor = normalized.grossMinor - normalized.taxMinor - normalized.refundMinor -
    normalized.providerFeeMinor - normalized.royaltyMinor - normalized.commissionMinor;
  if (!Number.isSafeInteger(netPlatformMinor)) throw new FabricContractError("netPlatformMinor_SAFE_INTEGER_RANGE");

  const reasonCodes: string[] = [];
  if (normalized.expectedNetMinor === null) reasonCodes.push("EXPECTED_NET_REQUIRED");
  if (netPlatformMinor < 0) reasonCodes.push("NEGATIVE_NET");
  const reconciliationDeltaMinor = normalized.expectedNetMinor === null
    ? null
    : netPlatformMinor - normalized.expectedNetMinor;
  if (reconciliationDeltaMinor !== null && reconciliationDeltaMinor !== 0) reasonCodes.push("NET_MISMATCH");
  return {
    netPlatformMinor,
    reconciliationDeltaMinor,
    reasonCodes,
    state: reasonCodes.length ? "HOLD" as const : "PASS" as const,
    settlementAuthority: false,
    digest: canonicalSha256(normalized),
  };
}

export function planRollbackCompensation(input: unknown) {
  const value = assertStrictObject(
    input,
    "ROLLBACK_INPUT",
    ["providerReversible", "institutionalReversible", "adverseEvidenceRefs"],
    ["providerReversible", "institutionalReversible", "adverseEvidenceRefs"],
  );
  const providerReversible = assertBoolean(value.providerReversible, "providerReversible");
  const institutionalReversible = assertBoolean(value.institutionalReversible, "institutionalReversible");
  if (!Array.isArray(value.adverseEvidenceRefs)) throw new FabricContractError("adverseEvidenceRefs_ARRAY_REQUIRED");
  const adverseEvidenceRefs = [...new Set(value.adverseEvidenceRefs.map((ref, index) =>
    requiredString(ref, `adverseEvidenceRefs_${index}`, 255)
  ))].sort();
  let action: "ROLLBACK" | "COMPENSATE" | "QUARANTINE" = "QUARANTINE";
  if (adverseEvidenceRefs.length && providerReversible && institutionalReversible) action = "ROLLBACK";
  else if (adverseEvidenceRefs.length) action = "COMPENSATE";
  const reasonCodes = adverseEvidenceRefs.length ? [] : ["ADVERSE_EVIDENCE_REQUIRED"];
  return {
    action,
    reasonCodes,
    steps: [
      "freeze affected exact version",
      "append adverse evidence",
      action === "ROLLBACK"
        ? "execute governed reversal"
        : action === "COMPENSATE"
          ? "create governed compensating action"
          : "escalate for review",
      "read back provider and institutional state",
    ],
    requiresHuman: true,
    appendOnlyReceiptRequired: true,
  };
}

const assertFiniteFeature = (value: unknown, field: string): number => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new FabricContractError(`${field}_FINITE_NUMBER`);
  }
  return value;
};

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));

export function advisoryDemandScore(input: unknown) {
  const value = assertStrictObject(
    input,
    "DEMAND_INPUT",
    ["viewsZ", "conversionZ", "saveZ", "searchZ", "seasonality"],
    ["viewsZ", "conversionZ", "saveZ", "searchZ", "seasonality"],
  );
  const f = {
    viewsZ: assertFiniteFeature(value.viewsZ, "viewsZ"),
    conversionZ: assertFiniteFeature(value.conversionZ, "conversionZ"),
    saveZ: assertFiniteFeature(value.saveZ, "saveZ"),
    searchZ: assertFiniteFeature(value.searchZ, "searchZ"),
    seasonality: assertFiniteFeature(value.seasonality, "seasonality"),
  };
  const raw = 0.28 * f.viewsZ + 0.32 * f.conversionZ + 0.14 * f.saveZ + 0.18 * f.searchZ + 0.08 * f.seasonality;
  return {
    score: sigmoid(raw),
    model: "ct.ml.thriveevergreen.demand-score.v1",
    authority: "ADVISORY_ONLY" as const,
    featureDigest: canonicalSha256(f),
  };
}

export function advisoryPriceElasticity(input: unknown) {
  const value = assertStrictObject(
    input,
    "ELASTICITY_INPUT",
    ["priceChangePct", "demandChangePct", "sampleWeight"],
    ["priceChangePct", "demandChangePct", "sampleWeight"],
  );
  const f = {
    priceChangePct: assertFiniteFeature(value.priceChangePct, "priceChangePct"),
    demandChangePct: assertFiniteFeature(value.demandChangePct, "demandChangePct"),
    sampleWeight: assertFiniteFeature(value.sampleWeight, "sampleWeight"),
  };
  if (f.sampleWeight < 0 || f.sampleWeight > 1) throw new FabricContractError("sampleWeight_RANGE");
  const denominator = Math.abs(f.priceChangePct) < 0.001 ? 0.001 : f.priceChangePct;
  return {
    elasticity: (f.demandChangePct / denominator) * f.sampleWeight,
    confidence: f.sampleWeight,
    model: "ct.ml.thriveevergreen.price-elasticity-advisor.v1",
    authority: "ADVISORY_ONLY" as const,
    featureDigest: canonicalSha256(f),
  };
}

export function advisoryAnomalyScore(input: unknown) {
  const value = assertStrictObject(
    input,
    "ANOMALY_INPUT",
    ["refundZ", "disputeZ", "priceDriftZ", "providerMismatchZ", "fulfillmentLatencyZ"],
    ["refundZ", "disputeZ", "priceDriftZ", "providerMismatchZ", "fulfillmentLatencyZ"],
  );
  const f = {
    refundZ: assertFiniteFeature(value.refundZ, "refundZ"),
    disputeZ: assertFiniteFeature(value.disputeZ, "disputeZ"),
    priceDriftZ: assertFiniteFeature(value.priceDriftZ, "priceDriftZ"),
    providerMismatchZ: assertFiniteFeature(value.providerMismatchZ, "providerMismatchZ"),
    fulfillmentLatencyZ: assertFiniteFeature(value.fulfillmentLatencyZ, "fulfillmentLatencyZ"),
  };
  const weighted = 0.25 * Math.abs(f.refundZ) + 0.25 * Math.abs(f.disputeZ) +
    0.18 * Math.abs(f.priceDriftZ) + 0.20 * Math.abs(f.providerMismatchZ) +
    0.12 * Math.abs(f.fulfillmentLatencyZ);
  return {
    score: Math.min(1, weighted / 5),
    holdRecommended: weighted >= 3.5,
    model: "ct.ml.thriveevergreen.anomaly-risk.v1",
    authority: "ADVISORY_ONLY" as const,
    featureDigest: canonicalSha256(f),
  };
}
