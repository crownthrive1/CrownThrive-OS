import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  buildRegistryIndex,
  classifyIntentAdvisory,
  routeSkillHandoffPlan,
  verifyRouteReceipt,
} from './skill-handoff-orchestrator.mjs';

const skills = JSON.parse(await readFile(process.argv[2] ?? 'automation/chlom-wallet-agent-skills-v2.json', 'utf8'));
const crosswalk = JSON.parse(await readFile(process.argv[3] ?? 'automation/chlom-wallet-agent-handoff-crosswalk.v1.json', 'utf8'));
const HEAD = 'a'.repeat(40);
const NOW = '2026-08-23T12:00:00.000Z';
const registry = buildRegistryIndex(skills, crosswalk);

function freshIdentitySnapshot() {
  const snapshot = {};
  for (const row of registry.handoff_index.values()) {
    if (!row.verified || !row.stable_agent_id) continue;
    snapshot[row.stable_agent_id] = {
      did_uri: `did:chlom:${row.stable_agent_id.replace(/[^a-z0-9]/gi, '').slice(-32)}`,
      public_identity_digest_sha256: 'b'.repeat(64),
      head_sha: HEAD,
      heartbeat_state: 'FRESH',
      heartbeat_observed_at: '2026-08-23T11:55:00.000Z',
      authority_ceiling: row.authority_ceiling,
    };
  }
  return snapshot;
}

function request(overrides = {}) {
  return {
    request_id: 'ct.test.wallet-route.001',
    source_head_sha: HEAD,
    requested_mode: 'PLAN_ONLY',
    requested_autonomy_ceiling: 'A1',
    requested_decision_ceiling: 'D1',
    requested_effects: {},
    ...overrides,
  };
}

const results = [];

// 1. A fully verified, active, fresh, exact-head route becomes ready for the downstream policy engine.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_skill_id: 'ct.skill.chlom-wallet.ledger-chain-verification.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'READY_FOR_POLICY_EVALUATION');
  assert.deepEqual(receipt.reason_codes, ['READY_FOR_POLICY_ASSURANCE']);
  assert.equal(receipt.handoff_readiness.ready_count, 3);
  assert.equal(receipt.execution_authorized, false);
  assert.equal(verifyRouteReceipt(receipt).valid, true);
  results.push('ready_verified_route');
}

// 2. Agent H remains a quarantined alias and blocks executable handoff planning.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_skill_id: 'ct.skill.chlom-wallet.provider-event-verification.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'HOLD');
  assert(receipt.reason_codes.includes('HOLD_PENDING_STABLE_ID_CROSSWALK'));
  assert.equal(receipt.execution_authorized, false);
  results.push('agent_h_alias_quarantine');
}

// 3. Agent E remains a quarantined alias and blocks executable handoff planning.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_skill_id: 'ct.skill.chlom-wallet.sdk-api-packaging.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'HOLD');
  assert(receipt.reason_codes.includes('HOLD_PENDING_STABLE_ID_CROSSWALK'));
  results.push('agent_e_alias_quarantine');
}

// 4. Unknown natural-language intent cannot become authority.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_skill_id: undefined, intent_text: 'do something unrelated and unspecified' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'HOLD');
  assert.equal(receipt.advisory.final_authority, false);
  assert(receipt.reason_codes[0].startsWith('HOLD_'));
  results.push('unknown_intent_holds');
}

// 5. D3/A3 is human-reserved and is denied before skill selection.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_decision_ceiling: 'D3', requested_skill_id: 'ct.skill.chlom-wallet.ledger-chain-verification.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'DENY');
  assert.deepEqual(receipt.reason_codes, ['DENY_HUMAN_RESERVED_AUTHORITY']);
  results.push('human_reserved_authority_denied');
}

// 6. Any requested live effect is denied.
{
  const receipt = routeSkillHandoffPlan({
    request: request({
      requested_skill_id: 'ct.skill.chlom-wallet.ledger-chain-verification.v1',
      requested_effects: { provider_write: true, money_movement: true },
    }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'DENY');
  assert.deepEqual(receipt.crossed_effects, ['money_movement', 'provider_write']);
  results.push('live_effects_denied');
}

// 7. The request must bind to the exact source head.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ source_head_sha: 'c'.repeat(40), requested_skill_id: 'ct.skill.chlom-wallet.ledger-chain-verification.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'HOLD');
  assert.deepEqual(receipt.reason_codes, ['HOLD_REQUEST_EXACT_HEAD_MISMATCH']);
  results.push('request_head_mismatch_holds');
}

// 8. A stale specialist heartbeat holds the plan.
{
  const snapshot = freshIdentitySnapshot();
  snapshot['ct.agent.evidence-auditor'].heartbeat_observed_at = '2026-08-23T10:00:00.000Z';
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_skill_id: 'ct.skill.chlom-wallet.ledger-chain-verification.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: snapshot,
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'HOLD');
  assert(receipt.reason_codes.includes('HOLD_HEARTBEAT_STALE_OR_MISSING'));
  results.push('stale_heartbeat_holds');
}

// 9. A prospective binding is not silently treated as an active execution identity.
{
  const receipt = routeSkillHandoffPlan({
    request: request({ requested_skill_id: 'ct.skill.chlom-wallet.customer-projection.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  });
  assert.equal(receipt.disposition, 'HOLD');
  assert(receipt.reason_codes.includes('HOLD_NON_ACTIVE_REGISTRY_BINDING'));
  results.push('prospective_binding_holds');
}

// 10. Same exact input creates the same deterministic receipt digest.
{
  const args = {
    request: request({ request_id: 'ct.test.wallet-route.determinism', requested_skill_id: 'ct.skill.chlom-wallet.contract-verification.v1' }),
    skillSuite: skills,
    handoffCrosswalk: crosswalk,
    identitySnapshot: freshIdentitySnapshot(),
    exactHeadSha: HEAD,
    now: NOW,
  };
  const first = routeSkillHandoffPlan(args);
  const second = routeSkillHandoffPlan(args);
  assert.equal(first.route_digest_sha256, second.route_digest_sha256);
  assert.deepEqual(first, second);
  results.push('deterministic_receipt');
}

// 11. The lexical classifier is explicitly advisory and cannot change the route by itself.
{
  const advisory = classifyIntentAdvisory('Verify the append only ledger chain and event hash linkage');
  assert.equal(advisory.disposition, 'ADVISORY_CANDIDATE');
  assert.equal(advisory.selected_skill_id, 'ct.skill.chlom-wallet.ledger-chain-verification.v1');
  assert.equal(advisory.advisory_only, true);
  assert.equal(advisory.final_authority, false);
  results.push('advisory_classifier_bounded');
}

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_SKILL_HANDOFF_ORCHESTRATION_CONTRACT',
  scenario_count: results.length,
  scenarios: results,
  skill_count: registry.skill_index.size,
  handoff_count: registry.handoff_index.size,
  execution_authorized: false,
  authority_granted: false,
  certification_authority: false,
  credential_access: false,
  provider_write: false,
  money_movement: false,
  rights_grant: false,
  chain_broadcast: false,
  effective_price_publication: false,
  checkout_activation: false,
  phase_advancement: false,
  merge_authorized: false,
  vote_effect: 'none',
  ai_final_authority: false,
}, null, 2));
