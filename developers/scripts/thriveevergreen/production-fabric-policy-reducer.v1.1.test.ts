import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  FabricContractViolation,
  advisoryDemandScoreV11,
  advisoryPriceElasticityV11,
  canonicalJson,
  canonicalSha256,
  computePriceEnvelopeV11,
  createExactGateProfile,
  evaluateDispatchV11,
  evaluateExactEcac,
  normalizeCandidateV11,
  reconcileSettlementV11,
  reduceProviderReadbackV11,
  transitionEntitlementV11,
  validateMutationExecutionEnvelopeV11,
} from "./production-fabric-policy-reducer.v1.1.ts";

const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);
const SHA_C = "c".repeat(64);
const CANDIDATE_ID = "018f9f0a-7b2d-7a3a-8b4c-1234567890ab";
const EXECUTION_ID = "018f9f0a-7b2d-7a3a-9b4c-1234567890ab";
const ALLOCATION_ID = "018f9f0a-7b2d-7a3a-ab4c-1234567890ab";
const EXACT_VERSION = "vm-book-test-v1";

const candidate = {
  candidateId: CANDIDATE_ID,
  subjectRef: "ct.product.vm-test-book",
  exactVersionRef: EXACT_VERSION,
  contentSha256: SHA_A,
  rightsState: "PASS",
  cieState: "PASS",
  channel: "virality-music",
  currency: "USD",
  requestedEffects: ["entitlement.prepare"],
  providerAliases: { stripe_product: "provider-object-evidence-only" },
};

const CANDIDATE_SHA = normalizeCandidateV11(candidate).normalizedSha256;

const gateProfileMaterial = () => ({
  registryId: "ct.registry.thriveevergreen-gates",
  registryVersion: "2026-08-24.v1",
  registrySnapshotSha256: SHA_C,
  profileId: "ct.gate-profile.vm-commerce",
  profileVersion: "1.1.0",
  exactCandidateVersionRef: EXACT_VERSION,
  activeFrom: "2026-08-24T00:00:00.123456Z",
  activeUntil: "2026-08-25T00:00:00.123456789Z",
  gates: [
    { gateKey: "rights", allowNotApplicable: false },
    { gateKey: "security", allowNotApplicable: false },
  ],
});

const profile = createExactGateProfile(gateProfileMaterial());

const validEcacInput = () => ({
  candidate,
  gateProfile: profile,
  expectedRegistrySnapshotSha256: SHA_C,
  expectedGateProfileDigest: profile.profileDigest,
  expectedCandidateSha256: CANDIDATE_SHA,
  expectedCandidateVersionRef: EXACT_VERSION,
  gates: { rights: "PASS", security: "PASS" },
  evidenceRefs: ["ct.evidence.vm-test-book-v1"],
  providerEvidence: [
    {
      provider: "stripe",
      providerSuccess: true,
      evidenceSha256: SHA_B,
      observedAt: "2026-08-24T01:00:00.123456Z",
    },
  ],
  evaluatedAt: "2026-08-24T01:00:01.123456789Z",
});

const expectViolation = (code: string, run: () => unknown) => {
  assert.throws(run, (error: unknown) => {
    assert.ok(error instanceof FabricContractViolation);
    assert.equal(error.code, code);
    return true;
  });
};

test("v1.1 contract JSON parses and remains an additive predecessor", () => {
  const contract = JSON.parse(readFileSync(
    new URL("../../contracts/thriveevergreen/production-fabric-policy-reducer.contracts.v1.1.json", import.meta.url),
    "utf8",
  ));
  assert.equal(contract.schemaVersion, "1.1.0");
  assert.equal(contract.compatibility.predecessorMutation, false);
  assert.equal(contract.contracts.exactEcacEvaluation.outputAuthority, "validation_only_not_execution_authority");
  assert.deepEqual(contract.contracts.exactEcacEvaluation.decisionValues, ["ECAC", "HOLD", "DENY"]);
  assert.deepEqual(contract.contracts.settlement.stateValues, ["PASS", "HOLD"]);
  assert.deepEqual(contract.contracts.settlement.remedyValues, ["CORRECT", "COMPENSATE"]);
  assert.equal(contract.contracts.generalizedDispatch.enabled, false);
});

test("all contract references resolve and every object schema is closed or typed", () => {
  const contract = JSON.parse(readFileSync(
    new URL("../../contracts/thriveevergreen/production-fabric-policy-reducer.contracts.v1.1.json", import.meta.url),
    "utf8",
  ));
  const walk = (value: unknown, path: string) => {
    if (Array.isArray(value)) {
      value.forEach((entry, index) => walk(entry, `${path}[${index}]`));
      return;
    }
    if (value === null || typeof value !== "object") return;
    const object = value as Record<string, unknown>;
    if (object.type === "object") {
      assert.ok(Object.prototype.hasOwnProperty.call(object, "additionalProperties"), `${path} is not closed or typed`);
    }
    if (typeof object.$ref === "string" && object.$ref.startsWith("#/$defs/")) {
      const key = object.$ref.slice("#/$defs/".length);
      assert.ok(Object.prototype.hasOwnProperty.call(contract.$defs, key), `${path} has unresolved ${object.$ref}`);
    }
    for (const [key, entry] of Object.entries(object)) walk(entry, `${path}.${key}`);
  };
  walk(contract.$defs, "$.$defs");
  walk(contract.contracts, "$.contracts");
});

test("canonical JSON and SHA are independent of object insertion order", () => {
  const left = { z: [3, { b: true, a: null }], a: "same" };
  const right = { a: "same", z: [3, { a: null, b: true }] };
  assert.equal(canonicalJson(left), canonicalJson(right));
  assert.equal(canonicalSha256(left), canonicalSha256(right));
});

test("exact ECAC uses the exact version and treats provider success as evidence only", () => {
  const result = evaluateExactEcac(validEcacInput());
  assert.equal(result.decision, "ECAC");
  assert.equal(result.exactCandidateVersionRef, EXACT_VERSION);
  assert.equal(result.candidateSha256, CANDIDATE_SHA);
  assert.equal(result.gateRegistrySnapshotSha256, SHA_C);
  assert.equal(result.providerSuccessEvidenceCount, 1);
  assert.equal(result.providerSuccessTreatedAsEvidenceOnly, true);
  assert.equal(result.moneyMovementAuthorized, false);
  assert.equal(result.providerWriteAuthorized, false);
  assert.equal(result.rightsGrantAuthorized, false);
  assert.equal(result.entitlementActivationAuthorized, false);
});

test("valid gate states resolve through exact ECAC, HOLD, or DENY", () => {
  const holdInput = validEcacInput();
  holdInput.gates.security = "HOLD";
  assert.equal(evaluateExactEcac(holdInput).decision, "HOLD");

  const denyInput = validEcacInput();
  denyInput.gates.rights = "DENY";
  assert.equal(evaluateExactEcac(denyInput).decision, "DENY");
});

test("an empty gate profile is rejected", () => {
  expectViolation("empty_gate_profile", () => createExactGateProfile({
    ...gateProfileMaterial(),
    gates: [],
  }));
});

test("missing exact gate keys are rejected", () => {
  const input = validEcacInput();
  input.gates = { rights: "PASS" } as typeof input.gates;
  expectViolation("missing_gate_keys", () => evaluateExactEcac(input));
});

test("unexpected gate keys are rejected", () => {
  const input = validEcacInput();
  Object.assign(input.gates, { finance: "PASS" });
  expectViolation("unexpected_gate_keys", () => evaluateExactEcac(input));
});

test("a stale expected candidate version is rejected", () => {
  const input = validEcacInput();
  input.expectedCandidateVersionRef = "vm-book-test-v0";
  expectViolation("stale_expected_version", () => evaluateExactEcac(input));
});

test("a mismatched registry gate digest is rejected", () => {
  const input = validEcacInput();
  input.expectedGateProfileDigest = SHA_C;
  expectViolation("expected_gate_digest_mismatch", () => evaluateExactEcac(input));
});

test("the trusted registry snapshot expectation is independently required", () => {
  const input = validEcacInput();
  input.expectedRegistrySnapshotSha256 = SHA_A;
  expectViolation("expected_registry_snapshot_digest_mismatch", () => evaluateExactEcac(input));
});

test("trusted registry and candidate digest expectations cannot be omitted", () => {
  const {
    expectedRegistrySnapshotSha256: omittedRegistryDigest,
    ...withoutRegistryDigest
  } = validEcacInput();
  assert.equal(omittedRegistryDigest, SHA_C);
  expectViolation("missing_property", () => evaluateExactEcac(withoutRegistryDigest));

  const {
    expectedCandidateSha256: omittedCandidateDigest,
    ...withoutCandidateDigest
  } = validEcacInput();
  assert.equal(omittedCandidateDigest, CANDIDATE_SHA);
  expectViolation("missing_property", () => evaluateExactEcac(withoutCandidateDigest));
});

test("the trusted candidate digest binds subject, content, and requested effects", () => {
  const mutations = [
    { ...candidate, subjectRef: "ct.product.vm-other-book" },
    { ...candidate, contentSha256: SHA_B },
    { ...candidate, requestedEffects: ["entitlement.prepare", "provider.write"] },
  ];
  for (const mutatedCandidate of mutations) {
    const input = validEcacInput();
    input.candidate = mutatedCandidate;
    expectViolation("expected_candidate_digest_mismatch", () => evaluateExactEcac(input));
  }
});

test("Supabase-style fractional UTC instants are accepted with nanosecond ordering", () => {
  const input = validEcacInput();
  input.providerEvidence[0]!.observedAt = "2026-08-24T01:00:00.123456Z";
  input.evaluatedAt = "2026-08-24T01:00:00.123456001Z";
  assert.equal(evaluateExactEcac(input).decision, "ECAC");
});

test("impossible calendar instants and timezone offsets are rejected", () => {
  expectViolation("invalid_utc_instant", () => createExactGateProfile({
    ...gateProfileMaterial(),
    activeFrom: "2026-02-30T00:00:00Z",
  }));
  expectViolation("invalid_utc_instant", () => createExactGateProfile({
    ...gateProfileMaterial(),
    activeFrom: "2026-08-24T00:00:00-04:00",
  }));
  expectViolation("invalid_utc_instant", () => createExactGateProfile({
    ...gateProfileMaterial(),
    activeFrom: "2026-08-24T00:00:00.1234567890Z",
  }));
});

test("provider IDs are ASCII-constrained and provider evidence order is deterministic", () => {
  const first = validEcacInput();
  first.providerEvidence = [
    {
      provider: "z_provider",
      providerSuccess: true,
      evidenceSha256: SHA_B,
      observedAt: "2026-08-24T01:00:00.123456Z",
    },
    {
      provider: "a-provider",
      providerSuccess: false,
      evidenceSha256: SHA_A,
      observedAt: "2026-08-24T01:00:00.123456Z",
    },
  ];
  const second = validEcacInput();
  second.providerEvidence = [...first.providerEvidence].reverse();
  assert.equal(evaluateExactEcac(first).gateDigest, evaluateExactEcac(second).gateDigest);

  const invalid = validEcacInput();
  invalid.providerEvidence[0]!.provider = "strípe";
  expectViolation("invalid_provider_id", () => evaluateExactEcac(invalid));
});

test("provider amount mismatch returns HOLD even when the provider reports success", () => {
  const result = reduceProviderReadbackV11({
    expected: {
      amount: { amountMinor: 2500, currency: "USD" },
      state: "succeeded",
      exactVersionRef: EXACT_VERSION,
    },
    observed: {
      amount: { amountMinor: 2400, currency: "USD" },
      state: "succeeded",
      exactVersionRef: EXACT_VERSION,
      providerSuccess: true,
      providerEvidenceSha256: SHA_A,
      observedAt: "2026-08-24T02:00:00Z",
    },
  });
  assert.equal(result.reconciledState, "HOLD");
  assert.deepEqual(result.mismatchCodes, ["AMOUNT_MISMATCH"]);
  assert.equal(result.institutionalEffectAllowed, false);
  assert.equal(result.providerSuccessTreatedAsEvidenceOnly, true);
});

test("negative monetary inputs are rejected instead of clamped", () => {
  expectViolation("integer_below_minimum", () => computePriceEnvelopeV11({
    currency: "USD",
    costMinor: -1,
    providerFeeMinor: 0,
    fulfillmentMinor: 0,
    supportMinor: 0,
    riskMinor: 0,
    royaltyMinor: 0,
    commissionMinor: 0,
    targetMarginBps: 2500,
    strategicPremiumBps: 0,
  }));
});

test("terminal entitlement states cannot reactivate", () => {
  expectViolation("terminal_entitlement_reactivation", () => transitionEntitlementV11({
    entitlementId: "ct.entitlement.vm-test-book",
    priorState: "REFUNDED",
    requestedState: "ACTIVE",
    priorExactVersionRef: "entitlement-v2",
    expectedPriorVersionRef: "entitlement-v2",
    qualifyingEventSha256: SHA_A,
    qualifyingEventState: "PASS",
    licenseState: "PASS",
    paymentState: "PASS",
    refundState: "NONE",
    disputeState: "NONE",
  }));
});

test("ML attempts to issue authority are rejected", () => {
  expectViolation("ml_authority_attempt", () => advisoryDemandScoreV11({
    request: {
      purpose: "RANK",
      featureSchemaVersion: "1.0.0",
      observationWindow: "P30D",
      requestedEffects: ["ECAC"],
    },
    features: { viewsZ: 1, conversionZ: 1, saveZ: 1, searchZ: 1, seasonality: 1 },
    modelVersion: "1.0.0",
    modelDigest: SHA_A,
  }));
});

test("price elasticity rejects non-finite derived output from extreme finite inputs", () => {
  expectViolation("non_finite_ml_output", () => advisoryPriceElasticityV11({
    request: {
      purpose: "RECOMMEND",
      featureSchemaVersion: "1.0.0",
      observationWindow: "P30D",
      requestedEffects: ["RECOMMEND"],
    },
    features: {
      priceChangePct: 0.001,
      demandChangePct: Number.MAX_VALUE,
      sampleWeight: 1,
    },
    modelVersion: "1.0.0",
    modelDigest: SHA_A,
  }));
});

test("unauthorized generalized dispatch is rejected", () => {
  expectViolation("unauthorized_generalized_dispatch", () => evaluateDispatchV11({
    toolId: "ct.mcp-tool.thriveevergreen.publish.dispatch",
    mode: "GENERALIZED",
    wrapperId: "ct.wrapper.vm-publisher",
    requestedEnabled: true,
    expectedGateDigest: SHA_A,
    gateDecisionDigest: SHA_A,
    idempotencyKey: "vm-publish-test-0001",
  }));
});

test("even a valid wrapper-only dispatch request remains disabled and HOLD", () => {
  const result = evaluateDispatchV11({
    toolId: "ct.mcp-tool.thriveevergreen.publish.dispatch",
    mode: "WRAPPER_ONLY",
    wrapperId: "ct.wrapper.vm-publisher",
    requestedEnabled: false,
    expectedGateDigest: SHA_A,
    gateDecisionDigest: SHA_A,
    idempotencyKey: "vm-publish-test-0001",
  });
  assert.equal(result.decision, "HOLD");
  assert.equal(result.generalizedDispatchEnabled, false);
  assert.equal(result.wrapperOnly, true);
  assert.equal(result.wrapperExecutionAuthorized, false);
});

test("stale second-read mutation evidence is rejected", () => {
  expectViolation("second_read_drift", () => validateMutationExecutionEnvelopeV11({
    executionId: EXECUTION_ID,
    idempotencyKey: "vm-mutation-test-0001",
    wrapperId: "ct.wrapper.vm-publisher",
    candidateId: CANDIDATE_ID,
    expectedVersionRef: EXACT_VERSION,
    gateDecisionDigest: SHA_A,
    preRead: {
      subjectRef: "ct.product.vm-test-book",
      exactVersionRef: EXACT_VERSION,
      stateSha256: SHA_A,
      observedAt: "2026-08-24T02:00:00Z",
    },
    secondRead: {
      subjectRef: "ct.product.vm-test-book",
      exactVersionRef: EXACT_VERSION,
      stateSha256: SHA_B,
      observedAt: "2026-08-24T02:00:01Z",
    },
    proposedEffectSha256: SHA_C,
    postRead: {
      subjectRef: "ct.product.vm-test-book",
      exactVersionRef: "vm-book-test-v2",
      stateSha256: SHA_C,
      observedAt: "2026-08-24T02:00:02Z",
    },
    compensation: {
      planSha256: SHA_B,
      receiptRequired: true,
      compensatingActionRef: "ct.action.vm-test-compensation",
    },
  }));
});

test("settlement emits allocation, totals, reconciliation, and no authority", () => {
  const result = reconcileSettlementV11({
    orderRef: "ct.order.vm-test-book",
    currency: "USD",
    grossMinor: 10000,
    taxMinor: 500,
    refundMinor: 0,
    providerFeeMinor: 300,
    royaltyMinor: 1000,
    commissionMinor: 200,
    allocationRules: [
      {
        allocationId: ALLOCATION_ID,
        category: "ROYALTY",
        recipientRef: "ct.actor.vm-rights-holder",
        amountMinor: 1000,
      },
      {
        allocationId: "018f9f0a-7b2d-7a3a-bb4c-1234567890ab",
        category: "COMMISSION",
        recipientRef: "ct.actor.vm-partner",
        amountMinor: 200,
      },
    ],
    expectedNetMinor: 8000,
  });
  assert.equal(result.state, "PASS");
  assert.equal(result.netPlatformMinor, 8000);
  assert.equal(result.totals.deductionsMinor, 2000);
  assert.equal(result.allocationLines.length, 2);
  assert.equal(result.settlementAuthorityIssued, false);
});
