import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const HERE = dirname(fileURLToPath(import.meta.url));
const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false });
addFormats(ajv);
const receiptSchema = JSON.parse(readFileSync(join(HERE, 'independent-review-receipt.v1.schema.json'), 'utf8'));
const statusSchema = JSON.parse(readFileSync(join(HERE, 'independent-review-status.v1.schema.json'), 'utf8'));
const validateReceipt = ajv.compile(receiptSchema);
const validateStatus = ajv.compile(statusSchema);

const hardBoundaries = {
  originator_self_approval: false,
  profile_promoted: false,
  deployment_authorized: false,
  broadcast_authorized: false,
  custody: false,
  money_movement: false,
  production_rights_grant: false,
  phase_advancement: false,
  merge_authorized: false,
};

const receipt = {
  contract: 'ct.wallet.independent-review-receipt.v1',
  work_id: 'ct.work.chlom-wallet.erc4337-runtime-codehash-review.v1',
  review_role: 'protocol',
  reviewer_agent_id: 'ct.chlom.agent.blockchain-crypto',
  reviewer_did_uri: 'did:chlom:70f6e3c9e8d143299a9d69350093fca4',
  reviewer_public_identity_digest_sha256: '1'.repeat(64),
  reviewer_head_sha: '2'.repeat(40),
  reviewer_heartbeat_at: '2026-08-22T12:00:00.000Z',
  reviewer_heartbeat_ttl_seconds: 3900,
  heartbeat_fresh_at_recording: true,
  exact_head_sha: 'df67672b99839e58d7873dabe49e06de58007820',
  evidence_digest_sha256: 'a11e9c03cfd0ec05d9e4f1171b1d99e124cf2f7fffd697881bb3718f13e4b9fb',
  decision: 'PASS_REVIEW',
  findings: [],
  conditions: [],
  receipt_nonce: 'ct.review.protocol.001',
  receipt_digest_sha256: '3'.repeat(64),
  source_ref: 'github:crownthrive1/CrownThrive-Support:pull/230',
  hard_boundaries: hardBoundaries,
};
assert.equal(validateReceipt(receipt), true, JSON.stringify(validateReceipt.errors));

const wrongReviewer = { ...receipt, reviewer_agent_id: 'ct.chlom.agent.security' };
assert.equal(validateReceipt(wrongReviewer), false);
const originator = { ...receipt, reviewer_agent_id: 'ct.agent.chlom-wallet-settlement' };
assert.equal(validateReceipt(originator), false);
const stale = { ...receipt, heartbeat_fresh_at_recording: false };
assert.equal(validateReceipt(stale), false);
const headDrift = { ...receipt, exact_head_sha: '4'.repeat(40) };
assert.equal(validateReceipt(headDrift), false);
const evidenceDrift = { ...receipt, evidence_digest_sha256: '5'.repeat(64) };
assert.equal(validateReceipt(evidenceDrift), false);
const deployment = structuredClone(receipt);
deployment.hard_boundaries.deployment_authorized = true;
assert.equal(validateReceipt(deployment), false);
const privateLeak = { ...receipt, private_fingerprint_sha256: '6'.repeat(64) };
assert.equal(validateReceipt(privateLeak), false);

const lane = (overrides = {}) => ({
  work_id: 'ct.work.chlom-wallet.erc4337-runtime-codehash-review.v1',
  review_role: 'protocol',
  reviewer_agent_id: 'ct.chlom.agent.blockchain-crypto',
  reviewer_did_uri: 'did:chlom:70f6e3c9e8d143299a9d69350093fca4',
  reviewer_public_identity_digest_sha256: '1'.repeat(64),
  binding_state: 'active',
  authority_ceiling: 'D2',
  vote_eligible: false,
  heartbeat_at: '2026-08-20T18:43:49.368853+00:00',
  heartbeat_ttl_seconds: 3900,
  heartbeat_fresh: false,
  reviewer_ready: false,
  work_state: 'waiting',
  blocker_reason: 'VERIFIER_IDENTITY_OR_HEARTBEAT_NOT_READY',
  receipt_state: 'MISSING',
  receipt_digest_sha256: null,
  receipt_created_at: null,
  ...overrides,
});

const status = {
  contract: 'ct.wallet.independent-review-status.v1',
  state: 'HOLD_REVIEWER_HEARTBEATS_AND_RECEIPTS',
  phase: '2.99',
  originator_agent_id: 'ct.agent.chlom-wallet-settlement',
  originator_is_final_approver: false,
  technical_snapshot: {
    exact_head_sha: 'df67672b99839e58d7873dabe49e06de58007820',
    evidence_digest_sha256: 'a11e9c03cfd0ec05d9e4f1171b1d99e124cf2f7fffd697881bb3718f13e4b9fb',
    chain_id_caip2: 'eip155:11155111',
    entrypoint_address: '0x433709009B8330FDa32311DF1C2AFA402eD8D009',
    runtime_code_bytes: 22425,
    runtime_codehash: '0x280d5c7c0de94b512401eb9c4b0ef0436275ff03627aad0ce1f93ab1627187a0',
  },
  counts: {
    required_reviewers: 5,
    ready_reviewers: 0,
    stale_or_unready_reviewers: 5,
    receipts_recorded: 0,
    pass_receipts: 0,
    hold_receipts: 0,
    deny_receipts: 0,
  },
  review_lanes: [
    lane(),
    lane({ work_id: 'ct.work.chlom-wallet.erc4337-security-review.v1', review_role: 'security', reviewer_agent_id: 'ct.chlom.agent.security' }),
    lane({ work_id: 'ct.work.chlom-wallet.erc4337-quorum-review.v1', review_role: 'quorum', reviewer_agent_id: 'ct.relay.agent-d', vote_eligible: true }),
    lane({ work_id: 'ct.work.chlom-wallet.erc4337-recovery-readback.v1', review_role: 'recovery', reviewer_agent_id: 'ct.chlom.agent.recovery' }),
    lane({ work_id: 'ct.work.chlom-wallet.erc4337-release-synthesis.v1', review_role: 'release', reviewer_agent_id: 'ct.chlom.agent.release-certifier' }),
  ],
  latest_synthesis: { result: 'HOLD_MISSING_INDEPENDENT_RECEIPTS', required_receipt_count: 5, accepted_receipt_count: 0, missing_receipt_count: 5 },
  scheduler_policy: {
    dependency_refresh_job: 'chlom-construction-queue-quarter-hourly',
    fresh_reviewer_heartbeat_required: true,
    scheduler_executes_reviewers: false,
    reviewer_impersonation_allowed: false,
  },
  hard_boundaries: {
    private_fingerprint_exposed: false,
    credential_value_exposed: false,
    fabricated_reviewer_heartbeat: false,
    fabricated_review_receipt: false,
    originator_self_approval: false,
    automatic_profile_promotion: false,
    deployment_authorized: false,
    broadcast_authorized: false,
    custody: false,
    money_movement: false,
    production_rights_grant: false,
    phase_advancement: false,
    merge_authorized: false,
  },
  source_ref: 'github:crownthrive1/CrownThrive-Support:pull/230',
};
assert.equal(validateStatus(status), true, JSON.stringify(validateStatus.errors));

const fabricatedHeartbeat = structuredClone(status);
fabricatedHeartbeat.hard_boundaries.fabricated_reviewer_heartbeat = true;
assert.equal(validateStatus(fabricatedHeartbeat), false);
const statusPrivateLeak = { ...status, credential_value: 'forbidden' };
assert.equal(validateStatus(statusPrivateLeak), false);
const wrongSnapshot = structuredClone(status);
wrongSnapshot.technical_snapshot.exact_head_sha = '7'.repeat(40);
assert.equal(validateStatus(wrongSnapshot), false);
const excessiveLanes = structuredClone(status);
excessiveLanes.review_lanes.push(lane());
assert.equal(validateStatus(excessiveLanes), false);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_INDEPENDENT_REVIEW_CONTRACT_SCHEMAS',
  valid_receipt_roles: 1,
  valid_status_lanes: status.review_lanes.length,
  wrong_reviewer_rejected: true,
  originator_rejected: true,
  stale_heartbeat_rejected: true,
  exact_head_drift_rejected: true,
  evidence_digest_drift_rejected: true,
  deployment_authorization_rejected: true,
  private_material_rejected: true,
  fabricated_heartbeat_rejected: true,
  money_movement: false,
  phase_advancement: false,
}));
