// ThriveEvergreen Production Fabric v1 — deterministic and advisory runtime helpers.
// This module does not grant authority, sign transactions, move money, publish prices,
// write providers, grant rights, or activate entitlements. Exact ECAC remains external.

import { createHash } from "node:crypto";

export type Verdict = "ECAC_CANDIDATE" | "HOLD" | "DENY";
export type EvidenceState = "PASS" | "HOLD" | "DENY" | "NOT_APPLICABLE";

const sha256 = (value: unknown) =>
  createHash("sha256").update(JSON.stringify(value)).digest("hex");

const clean = (v: string) => v.trim().replace(/[^A-Za-z0-9.-]+/g, "-").replace(/^-+|-+$/g, "").toUpperCase();

export interface CommerceCandidate {
  candidateId: string;
  subjectRef: string;
  exactVersionRef: string;
  contentSha256: string;
  rightsState: EvidenceState;
  cieState?: EvidenceState;
  channel: string;
  currency: string;
  requestedEffects?: string[];
  providerAliases?: Record<string, string>;
}

export function normalizeCandidate(input: CommerceCandidate): CommerceCandidate & { normalizedSha256: string } {
  const normalized: CommerceCandidate = {
    candidateId: input.candidateId.trim(),
    subjectRef: input.subjectRef.trim(),
    exactVersionRef: input.exactVersionRef.trim(),
    contentSha256: input.contentSha256.toLowerCase(),
    rightsState: input.rightsState,
    cieState: input.cieState ?? "NOT_APPLICABLE",
    channel: input.channel.trim().toLowerCase(),
    currency: input.currency.trim().toUpperCase(),
    requestedEffects: [...new Set(input.requestedEffects ?? [])].sort(),
    providerAliases: Object.fromEntries(Object.entries(input.providerAliases ?? {}).sort(([a],[b]) => a.localeCompare(b)))
  };
  return { ...normalized, normalizedSha256: sha256(normalized) };
}

export function computeSkuKey(parts: {
  brand: string; className: string; asset: string; variant: string; license: string; version: string;
}) {
  const skuCandidate = ["CT", parts.brand, parts.className, parts.asset, parts.variant, parts.license, parts.version]
    .map(clean).join("-");
  return { skuCandidate, skuKeySha256: sha256(skuCandidate), authority: "PROPOSAL_ONLY" as const };
}

export function evaluateEcac(input: {
  candidate: CommerceCandidate;
  gates: Record<string, EvidenceState>;
  requiredGateKeys: string[];
}) {
  const blockers: string[] = [];
  let denied = false;
  for (const key of input.requiredGateKeys) {
    const state = input.gates[key] ?? "HOLD";
    if (state === "DENY") { denied = true; blockers.push(`${key}:DENY`); }
    else if (state !== "PASS" && state !== "NOT_APPLICABLE") blockers.push(`${key}:HOLD`);
  }
  if (input.candidate.rightsState === "DENY") denied = true;
  if (input.candidate.rightsState !== "PASS") blockers.push(`rights:${input.candidate.rightsState}`);
  const decision: Verdict = denied ? "DENY" : blockers.length ? "HOLD" : "ECAC_CANDIDATE";
  const envelope = { candidateId: input.candidate.candidateId, exactVersionRef: input.candidate.exactVersionRef, gates: input.gates, decision, blockers };
  return {
    decision,
    blockers,
    gateDigest: sha256(envelope),
    moneyMovementAuthorized: false,
    providerWriteAuthorized: false,
    rightsGrantAuthorized: false,
    selfApproval: false
  };
}

export function classifyTopology(input: {
  firstParty: boolean; recurring: boolean; marketplace: boolean; booking: boolean; usageBased: boolean; physical: boolean; licenseBearing: boolean;
}) {
  let topology = "direct_one_time";
  if (input.marketplace) topology = "marketplace";
  else if (input.booking) topology = "booking";
  else if (input.usageBased) topology = "usage_based";
  else if (input.recurring) topology = "subscription";
  else if (input.physical) topology = "physical_direct";
  else if (input.licenseBearing) topology = "license_direct";
  return { topology, merchantOfRecordReviewRequired: input.marketplace || !input.firstParty, topologySha256: sha256({ ...input, topology }) };
}

export function computePriceEnvelope(input: {
  costMinor: number; providerFeeMinor: number; fulfillmentMinor: number; supportMinor: number; riskMinor: number; royaltyMinor: number; commissionMinor: number;
  targetMarginBps: number; strategicPremiumBps?: number;
}) {
  const nonnegative = Object.values(input).every(v => typeof v !== "number" || Number.isFinite(v));
  if (!nonnegative) throw new Error("non_finite_input");
  const base = Math.max(0, input.costMinor) + Math.max(0, input.providerFeeMinor) + Math.max(0, input.fulfillmentMinor) + Math.max(0, input.supportMinor) + Math.max(0, input.riskMinor) + Math.max(0, input.royaltyMinor) + Math.max(0, input.commissionMinor);
  const margin = Math.min(9500, Math.max(0, input.targetMarginBps));
  const sustainable = margin >= 10000 ? base : Math.ceil(base / Math.max(0.05, 1 - margin / 10000));
  const target = sustainable;
  const premium = Math.ceil(target * (1 + Math.max(0, input.strategicPremiumBps ?? 0) / 10000));
  const walkaway = base;
  const promotionFloor = Math.max(walkaway, Math.floor((sustainable + walkaway) / 2));
  return { floorMinor: base, sustainableMinor: sustainable, targetMinor: target, premiumMinor: premium, promotionFloorMinor: promotionFloor, walkawayMinor: walkaway, inputsSha256: sha256(input), authority: "ADVISORY_ENVELOPE" as const };
}

export function guardMargin(input: { priceMinor: number; totalCostMinor: number; minimumMarginBps: number }) {
  const marginMinor = input.priceMinor - input.totalCostMinor;
  const marginBps = input.priceMinor > 0 ? Math.floor((marginMinor / input.priceMinor) * 10000) : -10000;
  return { pass: marginBps >= input.minimumMarginBps, marginMinor, marginBps, state: marginBps >= input.minimumMarginBps ? "PASS" : "HOLD" };
}

export function reduceProviderReadback(input: {
  expected: { amountMinor?: number; currency?: string; state?: string };
  observed: { amountMinor?: number; currency?: string; state?: string; evidenceSha256: string };
}) {
  const mismatches: string[] = [];
  if (input.expected.amountMinor !== undefined && input.expected.amountMinor !== input.observed.amountMinor) mismatches.push("AMOUNT_MISMATCH");
  if (input.expected.currency && input.expected.currency.toUpperCase() !== input.observed.currency?.toUpperCase()) mismatches.push("CURRENCY_MISMATCH");
  if (input.expected.state && input.expected.state !== input.observed.state) mismatches.push("STATE_MISMATCH");
  return { reconciledState: mismatches.length ? "HOLD" : "PASS", mismatchCodes: mismatches, institutionalEffectAllowed: false, readbackDigest: sha256(input) };
}

export type EntitlementState = "PENDING" | "ACTIVE" | "SUSPENDED" | "REVOKED" | "REFUNDED" | "DISPUTED" | "EXPIRED";
export function reduceEntitlementState(input: {
  prior: EntitlementState; qualifyingEvent: boolean; licensePass: boolean; paymentPass: boolean; refunded?: boolean; disputed?: boolean; expired?: boolean;
}) {
  let next: EntitlementState = input.prior;
  const reasons: string[] = [];
  if (input.refunded) { next = "REFUNDED"; reasons.push("REFUNDED"); }
  else if (input.disputed) { next = "DISPUTED"; reasons.push("DISPUTED"); }
  else if (input.expired) { next = "EXPIRED"; reasons.push("EXPIRED"); }
  else if (input.qualifyingEvent && input.licensePass && input.paymentPass) { next = "ACTIVE"; reasons.push("QUALIFYING_EVENT_RECONCILED"); }
  else if (!input.licensePass || !input.paymentPass) { next = "SUSPENDED"; reasons.push("GATE_NOT_PASS"); }
  return { nextState: next, reasonCodes: reasons, entitlementMutationAuthorized: false };
}

export function reconcileSettlement(input: {
  grossMinor: number; taxMinor: number; refundMinor: number; providerFeeMinor: number; royaltyMinor: number; commissionMinor: number; expectedNetMinor?: number;
}) {
  const net = input.grossMinor - input.taxMinor - input.refundMinor - input.providerFeeMinor - input.royaltyMinor - input.commissionMinor;
  const delta = input.expectedNetMinor === undefined ? 0 : net - input.expectedNetMinor;
  return { netPlatformMinor: net, reconciliationDeltaMinor: delta, state: delta === 0 ? "PASS" : "HOLD", settlementAuthority: false, digest: sha256(input) };
}

export function planRollbackCompensation(input: { providerReversible: boolean; institutionalReversible: boolean; adverseEvidenceRefs: string[] }) {
  let action: "ROLLBACK" | "COMPENSATE" | "QUARANTINE" = "QUARANTINE";
  if (input.providerReversible && input.institutionalReversible) action = "ROLLBACK";
  else if (input.adverseEvidenceRefs.length) action = "COMPENSATE";
  return { action, steps: ["freeze affected exact version", "append adverse evidence", action === "ROLLBACK" ? "execute governed reversal" : action === "COMPENSATE" ? "create governed compensating action" : "escalate for review", "read back provider and institutional state"], requiresHuman: true, appendOnlyReceiptRequired: true };
}

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));
export function advisoryDemandScore(f: { viewsZ: number; conversionZ: number; saveZ: number; searchZ: number; seasonality: number }) {
  const raw = 0.28*f.viewsZ + 0.32*f.conversionZ + 0.14*f.saveZ + 0.18*f.searchZ + 0.08*f.seasonality;
  return { score: sigmoid(raw), model: "ct.ml.thriveevergreen.demand-score.v1", authority: "ADVISORY_ONLY" as const, featureDigest: sha256(f) };
}

export function advisoryPriceElasticity(f: { priceChangePct: number; demandChangePct: number; sampleWeight: number }) {
  const denom = Math.abs(f.priceChangePct) < 0.001 ? 0.001 : f.priceChangePct;
  const elasticity = (f.demandChangePct / denom) * Math.max(0, Math.min(1, f.sampleWeight));
  return { elasticity, confidence: Math.max(0, Math.min(1, f.sampleWeight)), model: "ct.ml.thriveevergreen.price-elasticity-advisor.v1", authority: "ADVISORY_ONLY" as const };
}

export function advisoryAnomalyScore(f: { refundZ: number; disputeZ: number; priceDriftZ: number; providerMismatchZ: number; fulfillmentLatencyZ: number }) {
  const weighted = 0.25*Math.abs(f.refundZ) + 0.25*Math.abs(f.disputeZ) + 0.18*Math.abs(f.priceDriftZ) + 0.20*Math.abs(f.providerMismatchZ) + 0.12*Math.abs(f.fulfillmentLatencyZ);
  return { score: Math.min(1, weighted / 5), holdRecommended: weighted >= 3.5, model: "ct.ml.thriveevergreen.anomaly-risk.v1", authority: "ADVISORY_ONLY" as const, featureDigest: sha256(f) };
}
