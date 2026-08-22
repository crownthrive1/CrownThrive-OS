import assert from 'node:assert/strict';
import { adviseInstitutionalizationRuntime } from './chlom-institutionalization-runtime-advisor.mjs';

const healthy = {
  edge_function: { slug: 'chlom-wallet-institutionalize-v2', exists: true, active: true, verify_jwt: false, status: 'ACTIVE' },
  database: {
    package_state: 'RECORDED_CONTROLLED_TEST_EVIDENCE',
    ingest_state: 'RECORDED_CONTROLLED_TEST_EVIDENCE',
    package_canary: 'PASS_CHLOM_INSTITUTIONALIZATION_PACKAGE_V2_CANARY',
    ingest_canary: 'PASS_CHLOM_INSTITUTIONALIZATION_INGEST_V2_CANARY',
    oidc_subject_canary: 'PASS_CHLOM_INSTITUTIONALIZATION_OIDC_SUBJECT_V2_CANARY',
  },
  ci: { package_v2_workflow: 'success', package_v2_run_id: '1' },
  review: { state: 'READY_FOR_PHASE_GATE_REVIEW', ready_reviewers: 5, required_reviewers: 5, receipts_recorded: 5 },
  commercialization: { effective_offer: false, checkout_enabled: false, pricing_state: 'PRICE_REVIEW' },
};

const noGaps = adviseInstitutionalizationRuntime(healthy);
assert.equal(noGaps.state, 'NO_RUNTIME_GAPS');
assert.equal(noGaps.advisory_count, 0);
assert.equal(noGaps.ai_governance.decision_authority, false);
assert.ok(Object.values(noGaps.hard_boundaries).every((value) => value === false));

const failed = structuredClone(healthy);
failed.edge_function.exists = false;
failed.edge_function.active = false;
failed.edge_function.verify_jwt = true;
failed.database.package_state = 'NO_RECORDED_PACKAGE_V2';
failed.database.ingest_state = 'NO_RECORDED_INGEST_V2';
failed.database.oidc_subject_canary = 'FAIL';
failed.ci.package_v2_workflow = 'failure';
failed.review.state = 'HOLD_REVIEWER_HEARTBEATS_AND_RECEIPTS';
failed.review.ready_reviewers = 0;
failed.review.receipts_recorded = 0;
failed.commercialization.pricing_state = 'UNKNOWN';
const advisories = adviseInstitutionalizationRuntime(failed);
assert.equal(advisories.state, 'ADVISORIES_PRESENT');
assert.equal(advisories.highest_priority, 'P0');
const codes = new Set(advisories.advisories.map((item) => item.code));
for (const required of [
  'EDGE_FUNCTION_MISSING',
  'OIDC_SUBJECT_CANARY_NOT_PASS',
  'PACKAGE_V2_WORKFLOW_NOT_GREEN',
  'REAL_PACKAGE_NOT_RECORDED',
  'INGEST_STATUS_NOT_RECORDED',
  'INDEPENDENT_REVIEW_REMAINS_HOLD',
  'PRICING_STATE_UNRESOLVED',
]) assert.ok(codes.has(required), required);
assert.ok(advisories.advisories.every((item) => item.advisory_only && !item.automatic_action && !item.decision_authority && !item.write_authority && !item.release_authority));

const breach = structuredClone(healthy);
breach.commercialization.effective_offer = true;
breach.commercialization.checkout_enabled = true;
const breachResult = adviseInstitutionalizationRuntime(breach);
assert.ok(breachResult.advisories.some((item) => item.code === 'COMMERCIALIZATION_BOUNDARY_BREACH' && item.priority === 'P0'));

assert.throws(() => adviseInstitutionalizationRuntime({}), /runtime_advisor_edge_required/);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_INSTITUTIONALIZATION_RUNTIME_ADVISOR_V1',
  healthy_gap_count: noGaps.advisory_count,
  failure_advisory_count: advisories.advisory_count,
  commercialization_breach_rejected: true,
  advisory_only: true,
  network_access: false,
  write_authority: false,
  decision_authority: false,
  automatic_release: false,
}));
