import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  FabricContractError,
  advisoryAnomalyScore,
  advisoryDemandScore,
  advisoryPriceElasticity,
  canonicalSha256,
  classifyTopology,
  computePriceEnvelope,
  computeSkuKey,
  evaluateEcac,
  guardMargin,
  normalizeCandidate,
  planRollbackCompensation,
  reconcileSettlement,
  reduceEntitlementState,
  reduceProviderReadback,
} from "../../developers/scripts/thriveevergreen/production-fabric-runtime.v1.1.ts";

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const CONTENT_SHA = "a".repeat(64);
const EVIDENCE_SHA = "b".repeat(64);

const validCandidate = (overrides = {}) => ({
  candidateId: "550e8400-e29b-41d4-a716-446655440000",
  subjectRef: "ct.product.vm.test-book",
  exactVersionRef: "ct.asset.vm.test-book@1.0.0",
  contentSha256: CONTENT_SHA,
  rightsState: "PASS",
  cieState: "PASS",
  channel: "virality_music",
  currency: "USD",
  requestedEffects: ["offer.evaluate"],
  providerAliases: { "stripe.product": "prod_evidence_only" },
  ...overrides,
});

test("V1 invalid candidate is rejected at runtime", () => {
  assert.throws(
    () => normalizeCandidate({
      candidateId: "not-a-uuid",
      subjectRef: " ",
      exactVersionRef: "",
      contentSha256: "x",
      rightsState: "PASS",
      channel: " ",
      currency: "US",
    }),
    (error) => error instanceof FabricContractError && error.code === "candidateId_UUID",
  );
});

test("V2 empty gate policy cannot produce an ECAC candidate", () => {
  const result = evaluateEcac({ candidate: validCandidate(), gates: {}, requiredGateKeys: [] });
  assert.equal(result.decision, "HOLD");
  assert.deepEqual(result.blockers, ["required_gates:EMPTY"]);
  assert.equal(result.moneyMovementAuthorized, false);
  assert.equal(result.providerWriteAuthorized, false);
  assert.equal(result.rightsGrantAuthorized, false);
});

test("V3 gate digest is canonical across object insertion order", () => {
  const first = evaluateEcac({
    candidate: validCandidate(),
    gates: { rights: "PASS", pricing: "HOLD" },
    requiredGateKeys: ["rights", "pricing"],
  });
  const second = evaluateEcac({
    candidate: validCandidate(),
    gates: { pricing: "HOLD", rights: "PASS" },
    requiredGateKeys: ["pricing", "rights"],
  });
  assert.equal(first.gateDigest, second.gateDigest);
  assert.equal(first.decision, "HOLD");
});

test("V4 lossy SKU normalization returns collision-sensitive keys and HOLD metadata", () => {
  const shared = { brand: "VM", className: "BOOK", variant: "DIGITAL", license: "PERSONAL", version: "V1" };
  const plus = computeSkuKey({ ...shared, asset: "A+B" });
  const space = computeSkuKey({ ...shared, asset: "A B" });
  assert.equal(plus.skuCandidate, space.skuCandidate);
  assert.notEqual(plus.skuKeySha256, space.skuKeySha256);
  assert.notEqual(plus.collisionSensitiveKey, space.collisionSensitiveKey);
  assert.equal(plus.reviewState, "HOLD");
  assert.equal(space.reviewState, "HOLD");
  assert.deepEqual(plus.holdReasons, ["LOSSY_SKU_NORMALIZATION"]);
});

test("V5 negative cost or provider fee is rejected, never clamped", () => {
  const base = {
    costMinor: 100,
    providerFeeMinor: 25,
    fulfillmentMinor: 0,
    supportMinor: 0,
    riskMinor: 0,
    royaltyMinor: 0,
    commissionMinor: 0,
    targetMarginBps: 2000,
  };
  assert.throws(
    () => computePriceEnvelope({ ...base, costMinor: -1 }),
    (error) => error instanceof FabricContractError && error.code === "costMinor_SAFE_INTEGER_RANGE",
  );
  assert.throws(
    () => computePriceEnvelope({ ...base, providerFeeMinor: -1 }),
    (error) => error instanceof FabricContractError && error.code === "providerFeeMinor_SAFE_INTEGER_RANGE",
  );
});

test("V6 empty expectation and invalid evidence digest holds provider readback", () => {
  const result = reduceProviderReadback({ expected: {}, observed: { evidenceSha256: "x" } });
  assert.equal(result.reconciledState, "HOLD");
  assert.deepEqual(result.mismatchCodes, ["EVIDENCE_DIGEST_INVALID", "EXPECTATION_REQUIRED"]);
  assert.equal(result.institutionalEffectAllowed, false);
});

test("V7 revoked entitlement is terminal for the exact entitlement", () => {
  const result = reduceEntitlementState({
    prior: "REVOKED",
    qualifyingEvent: true,
    licensePass: true,
    paymentPass: true,
  });
  assert.equal(result.nextState, "REVOKED");
  assert.deepEqual(result.reasonCodes, ["TERMINAL_REVOKED"]);
  assert.equal(result.entitlementMutationAuthorized, false);
});

test("V8 missing expected net keeps settlement reconciliation on HOLD", () => {
  const result = reconcileSettlement({
    grossMinor: 1000,
    taxMinor: 100,
    refundMinor: 0,
    providerFeeMinor: 50,
    royaltyMinor: 100,
    commissionMinor: 50,
  });
  assert.equal(result.netPlatformMinor, 700);
  assert.equal(result.reconciliationDeltaMinor, null);
  assert.equal(result.state, "HOLD");
  assert.deepEqual(result.reasonCodes, ["EXPECTED_NET_REQUIRED"]);
  assert.equal(result.settlementAuthority, false);
});

test("P1 valid candidate normalizes deterministically under a closed schema", () => {
  const first = normalizeCandidate(validCandidate({ requestedEffects: ["offer.evaluate", "offer.evaluate"] }));
  const second = normalizeCandidate(validCandidate({ requestedEffects: ["offer.evaluate"] }));
  assert.equal(first.normalizedSha256, second.normalizedSha256);
  assert.deepEqual(first.requestedEffects, ["offer.evaluate"]);
  assert.throws(
    () => normalizeCandidate({ ...validCandidate(), surpriseAuthority: true }),
    (error) => error instanceof FabricContractError && error.code === "CANDIDATE_ADDITIONAL_PROPERTY",
  );
});

test("P2 complete passing gates produce only an external ECAC candidate", () => {
  const result = evaluateEcac({
    candidate: validCandidate(),
    gates: { rights: "PASS", pricing: "PASS", provider: "PASS" },
    requiredGateKeys: ["provider", "rights", "pricing"],
  });
  assert.equal(result.decision, "ECAC_CANDIDATE");
  assert.equal(result.authority, "EXTERNAL_EXACT_ECAC_REQUIRED");
  assert.equal(result.publicationAuthorityGranted, false);
  assert.equal(result.pricePublicationAuthorized, false);
  assert.equal(result.entitlementMutationAuthorized, false);
  assert.equal(result.d3HumanReserved, true);
  assert.equal(result.selfApproval, false);
});

test("P3 non-lossy SKU proposal remains proposal-only", () => {
  const result = computeSkuKey({
    brand: "VM",
    className: "BOOK",
    asset: "ASK-ASHLEY",
    variant: "DIGITAL",
    license: "PERSONAL",
    version: "V2",
  });
  assert.equal(result.skuCandidate, "CT-VM-BOOK-ASK-ASHLEY-DIGITAL-PERSONAL-V2");
  assert.equal(result.reviewState, "PROPOSAL_ONLY");
  assert.equal(result.authority, "PROPOSAL_ONLY");
  assert.match(result.skuKeySha256, /^[0-9a-f]{64}$/);
});

test("P4 price and margin helpers preserve bounded arithmetic and advisory authority", () => {
  const envelope = computePriceEnvelope({
    costMinor: 400,
    providerFeeMinor: 50,
    fulfillmentMinor: 25,
    supportMinor: 25,
    riskMinor: 0,
    royaltyMinor: 100,
    commissionMinor: 0,
    targetMarginBps: 4000,
    strategicPremiumBps: 1000,
  });
  assert.equal(envelope.floorMinor, 600);
  assert.equal(envelope.sustainableMinor, 1000);
  assert.equal(envelope.premiumMinor, 1100);
  assert.equal(envelope.authority, "ADVISORY_ENVELOPE");
  assert.equal(envelope.effectivePriceAuthorized, false);
  assert.equal(guardMargin({ priceMinor: 1000, totalCostMinor: 600, minimumMarginBps: 4000 }).state, "PASS");
});

test("P5 exact provider match is evidence-only", () => {
  const result = reduceProviderReadback({
    expected: { amountMinor: 2500, currency: "USD", state: "paid" },
    observed: { amountMinor: 2500, currency: "USD", state: "paid", evidenceSha256: EVIDENCE_SHA },
  });
  assert.equal(result.reconciledState, "PASS");
  assert.deepEqual(result.mismatchCodes, []);
  assert.equal(result.institutionalEffectAllowed, false);
});

test("P6 entitlement and settlement positive controls remain non-authorizing", () => {
  const entitlement = reduceEntitlementState({
    prior: "PENDING",
    qualifyingEvent: true,
    licensePass: true,
    paymentPass: true,
  });
  assert.equal(entitlement.nextState, "ACTIVE");
  assert.equal(entitlement.entitlementMutationAuthorized, false);

  const settlement = reconcileSettlement({
    grossMinor: 1000,
    taxMinor: 100,
    refundMinor: 0,
    providerFeeMinor: 50,
    royaltyMinor: 100,
    commissionMinor: 50,
    expectedNetMinor: 700,
  });
  assert.equal(settlement.state, "PASS");
  assert.equal(settlement.settlementAuthority, false);
});

test("P7 topology, recovery, and advisory models cannot manufacture authority", () => {
  const topology = classifyTopology({
    firstParty: true,
    recurring: false,
    marketplace: false,
    booking: false,
    usageBased: false,
    physical: false,
    licenseBearing: true,
  });
  assert.equal(topology.topology, "license_direct");
  assert.equal(topology.authority, "CLASSIFICATION_ONLY");

  const recovery = planRollbackCompensation({
    providerReversible: true,
    institutionalReversible: true,
    adverseEvidenceRefs: ["ct.evidence.test.1"],
  });
  assert.equal(recovery.action, "ROLLBACK");
  assert.equal(recovery.requiresHuman, true);

  assert.equal(advisoryDemandScore({ viewsZ: 1, conversionZ: 1, saveZ: 0, searchZ: 0, seasonality: 0 }).authority, "ADVISORY_ONLY");
  assert.equal(advisoryPriceElasticity({ priceChangePct: 0.1, demandChangePct: -0.05, sampleWeight: 0.5 }).authority, "ADVISORY_ONLY");
  assert.equal(advisoryAnomalyScore({ refundZ: 0, disputeZ: 0, priceDriftZ: 0, providerMismatchZ: 0, fulfillmentLatencyZ: 0 }).authority, "ADVISORY_ONLY");
});

test("P8 JSON Schema is parseable, closed, and v1 source anchors remain immutable", async () => {
  const schemaUrl = new URL("../../developers/contracts/thriveevergreen/production-fabric.contracts.v1.1.schema.json", import.meta.url);
  const schema = JSON.parse(await readFile(schemaUrl, "utf8"));
  assert.equal(schema.$schema, "https://json-schema.org/draft/2020-12/schema");
  assert.equal(schema["x-crownthrive-generalized-dispatch"], "DISABLED");
  assert.equal(schema.$defs.candidate.additionalProperties, false);
  assert.equal(schema.$defs.providerExpected.minProperties, 1);

  const runtimeV1 = await readFile(new URL("../../developers/scripts/thriveevergreen/production-fabric-runtime.v1.ts", import.meta.url));
  const contractV1 = await readFile(new URL("../../developers/contracts/thriveevergreen/production-fabric.contracts.v1.json", import.meta.url));
  assert.equal(sha256(runtimeV1), "943b11047f52fbd8c7850aafdba7d6b8411c2d2725283c92a9029d31f16ca085");
  assert.equal(sha256(contractV1), "7e55be37dbc58e75263de45fd2dd74832d642b3d5836e9c5d90dd04206c991fb");
  assert.equal(canonicalSha256({ b: 2, a: 1 }), canonicalSha256({ a: 1, b: 2 }));
});
