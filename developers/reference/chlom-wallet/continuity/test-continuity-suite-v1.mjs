import fs from 'node:fs';
import assert from 'node:assert/strict';
import {
  generateFactoryProjection,
  validateBudgetSemantics,
  evaluateEvidenceExpiry,
  evaluateHeartbeat,
  evaluateOracleObservation,
  deriveContinuityDisposition,
  mlAdvisoryScore,
  planRecovery,
  sha256
} from './continuity-core-v1.mjs';

const catalog = JSON.parse(fs.readFileSync(new URL('./continuity-factory-asset-catalog.v1.json', import.meta.url)));
const promptSuite = JSON.parse(fs.readFileSync(new URL('./continuity-agent-prompt-suite.v1.json', import.meta.url)));
const interfaces = JSON.parse(fs.readFileSync(new URL('./continuity-interface-pack.v1.json', import.meta.url)));
const ip = JSON.parse(fs.readFileSync(new URL('./continuity-metaprotocol-ip.v1.json', import.meta.url)));

const domains = Array.from({ length: 25 }, (_, i) => ({ domain_slug: `domain-${String(i + 1).padStart(2,'0')}`, domain_name: `Domain ${i + 1}`, active: true }));
const assets = generateFactoryProjection(catalog, domains);
assert.equal(assets.length, 600);
assert.equal(new Set(assets.map(a => a.asset_id)).size, 600);
assert.ok(assets.every(a => a.candidate_only && !a.authority_granted && !a.production_activation));
assert.ok(assets.every(a => !a.provider_write && !a.money_movement && !a.rights_grant && !a.chain_broadcast && !a.checkout_enabled));

assert.deepEqual(validateBudgetSemantics(-1), { disposition: 'ECAC', meaning: 'UNLIMITED_CROWNTHRIVE_LOCAL_MONTHLY_CEILING' });
assert.deepEqual(validateBudgetSemantics(0), { disposition: 'ECAC', meaning: 'ZERO_REQUESTS_PERMITTED' });
assert.equal(validateBudgetSemantics(1).meaning, 'EXACT_1_REQUESTS_PER_MONTH');
assert.equal(validateBudgetSemantics(null).disposition, 'HOLD');
assert.equal(validateBudgetSemantics(-2).disposition, 'DENY');

const now = '2026-08-23T05:00:00Z';
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-23T04:59:00Z', ttl_seconds: 120 }).disposition, 'ECAC');
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-23T04:00:00Z', ttl_seconds: 120 }).disposition, 'HOLD');
assert.equal(evaluateHeartbeat({ now, last_heartbeat_at: '2026-08-23T03:00:00Z', next_heartbeat_due_at: '2026-08-23T04:00:00Z', heartbeat_state: 'HEALTHY' }).derived_state, 'STALE');
assert.equal(evaluateHeartbeat({ now, last_heartbeat_at: '2026-08-23T04:30:00Z', next_heartbeat_due_at: '2026-08-23T05:30:00Z', heartbeat_state: 'HEALTHY' }).disposition, 'ECAC');

assert.equal(evaluateOracleObservation({ connection_state: 'BOUND_CONTROLLED_TEST', read_only: false, observed_at: now, ttl_seconds: 60, payload_digest: 'a'.repeat(64), now }).disposition, 'DENY');
assert.equal(evaluateOracleObservation({ connection_state: 'BOUND_CONTROLLED_TEST', read_only: true, observed_at: now, ttl_seconds: 60, payload_digest: 'a'.repeat(64), now, source_confidence: 0.5 }).disposition, 'HOLD');

assert.equal(deriveContinuityDisposition({
  profile_state:'ECAC', execution_envelope_state:'ECAC', source_head_match:true, identity_pin_match:true,
  heartbeat_state:'ECAC', dependency_state:'ECAC', oracle_state:'ECAC', rollback_verified:true, security_state:'ECAC'
}), 'ECAC');
assert.equal(deriveContinuityDisposition({
  profile_state:'ECAC', execution_envelope_state:'ECAC', source_head_match:false, identity_pin_match:true,
  heartbeat_state:'ECAC', dependency_state:'ECAC', oracle_state:'ECAC', rollback_verified:true, security_state:'ECAC'
}), 'HOLD');
assert.equal(deriveContinuityDisposition({ forbidden_boundary:true }), 'DENY');

const advisory = mlAdvisoryScore({ stale_fraction: 1, source_head_drift: 1, rollback_gap: 1 });
assert.equal(advisory.advisory_only, true);
assert.equal(advisory.final_authority, false);
assert.ok(advisory.probability > 0 && advisory.probability < 1);

assert.equal(planRecovery({ incident_state:'PASS', rollback_verified:true, backup_verified:true, independent_review_state:'ECAC', source_head_match:true }).disposition, 'ECAC');
assert.equal(planRecovery({ incident_state:'PASS', rollback_verified:false, backup_verified:true, independent_review_state:'ECAC', source_head_match:true }).disposition, 'HOLD');
assert.equal(planRecovery({ incident_state:'DENY', rollback_verified:true, backup_verified:true, independent_review_state:'ECAC', source_head_match:true }).disposition, 'DENY');

assert.equal(promptSuite.agents.length, 4);
assert.equal(promptSuite.prompts.length, 12);
assert.equal(interfaces.pallets.length, 4);
assert.equal(interfaces.modules.length, 6);
assert.equal(interfaces.plugins.length, 4);
assert.equal(interfaces.mcp_tools.length, 8);
assert.equal(ip.assets.length, 8);
assert.equal(promptSuite.ai_final_authority, false);
assert.equal(interfaces.boundary.production_activation, false);

const runtime = interfaces.runtime_registry_constraints;
for (const plugin of interfaces.plugins) {
  assert.ok(runtime.plugin_kind.includes(plugin.kind), `invalid_plugin_kind:${plugin.plugin_id}:${plugin.kind}`);
  assert.ok(runtime.plugin_archetype.includes(plugin.archetype), `invalid_plugin_archetype:${plugin.plugin_id}:${plugin.archetype}`);
  assert.notEqual(plugin.owner_agent_id, plugin.verifier_agent_id, `plugin_separation_of_duties:${plugin.plugin_id}`);
}
for (const tool of interfaces.mcp_tools) {
  assert.ok(runtime.mcp_risk_class.includes(tool.risk_class), `invalid_mcp_risk:${tool.tool_name}:${tool.risk_class}`);
  assert.equal(tool.contract_registered, true);
  assert.equal(tool.enabled, false);
  assert.equal(tool.runtime_binding_state, 'HOLD_UNBOUND_MCP_SERVER');
}
assert.equal(runtime.service_monthly_request_limit, -1);
assert.equal(interfaces.api.deployment_state, 'CONTRACT_ONLY_HOLD_UNBOUND_SERVER');

const suiteDigest = sha256({
  catalog: catalog.catalog_id,
  prompts: promptSuite.suite_id,
  interfaces: interfaces.pack_id,
  interfaces_version: interfaces.semantic_version,
  ip: ip.registry_id,
  assets: assets.map(a => a.asset_sha256)
});
assert.match(suiteDigest, /^[a-f0-9]{64}$/);

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_CONTINUITY_SUITE_V1',
  generated_assets: assets.length,
  prompt_contracts: promptSuite.prompts.length,
  exact_agent_bindings: promptSuite.agents.length,
  pallets: interfaces.pallets.length,
  modules: interfaces.modules.length,
  plugins: interfaces.plugins.length,
  mcp_tools: interfaces.mcp_tools.length,
  mcp_runtime_binding: 'HOLD_UNBOUND_MCP_SERVER',
  api_runtime_binding: interfaces.api.deployment_state,
  proprietary_metaprotocol_assets: ip.assets.length,
  budget_semantics_correct: true,
  runtime_registry_compatible: true,
  ai_final_authority: false,
  production_activation: false,
  suite_digest_sha256: suiteDigest
}, null, 2));
