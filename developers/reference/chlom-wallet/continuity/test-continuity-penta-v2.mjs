import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  strictest,
  validateBudgetSemantics,
  evaluateEvidenceExpiry,
  evaluateHeartbeat,
  evaluateOracleObservation,
  deriveContinuityDisposition,
  mlAdvisoryScore,
  planRecovery
} from './continuity-core-v1.mjs';

const interfacePack = JSON.parse(fs.readFileSync(new URL('./continuity-penta-interface-pack.v2.json', import.meta.url)));
const live = JSON.parse(fs.readFileSync(new URL('./continuity-live-readback-20260826.v2.json', import.meta.url)));

assert.equal(strictest('ECAC', 'HOLD'), 'HOLD');
assert.equal(strictest('ECAC', 'HOLD', 'DENY'), 'DENY');
assert.equal(validateBudgetSemantics(-1).disposition, 'ECAC');
assert.equal(validateBudgetSemantics(0).disposition, 'ECAC');
assert.equal(validateBudgetSemantics(null).disposition, 'HOLD');
assert.equal(validateBudgetSemantics(-2).disposition, 'DENY');

const now = '2026-08-26T15:17:00Z';
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-26T15:16:30Z', ttl_seconds: 60 }).disposition, 'ECAC');
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-26T15:00:00Z', ttl_seconds: 60 }).disposition, 'HOLD');
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-26T15:18:00Z', ttl_seconds: 60 }).disposition, 'HOLD');

assert.equal(evaluateHeartbeat({ now, last_heartbeat_at: '2026-08-26T15:00:00Z', next_heartbeat_due_at: '2026-08-26T16:00:00Z', heartbeat_state: 'HEALTHY' }).disposition, 'ECAC');
assert.equal(evaluateHeartbeat({ now, last_heartbeat_at: '2026-08-26T14:00:00Z', next_heartbeat_due_at: '2026-08-26T15:00:00Z', heartbeat_state: 'HEALTHY' }).derived_state, 'STALE');

assert.equal(evaluateOracleObservation({ connection_state:'BOUND_CONTROLLED_TEST', read_only:false, observed_at:now, ttl_seconds:60, payload_digest:'a'.repeat(64), now }).disposition, 'DENY');
assert.equal(evaluateOracleObservation({ connection_state:'BOUND_CONTROLLED_TEST', read_only:true, observed_at:now, ttl_seconds:60, payload_digest:'a'.repeat(64), now, source_confidence:0.5 }).disposition, 'HOLD');
assert.equal(evaluateOracleObservation({ connection_state:'BOUND_CONTROLLED_TEST', read_only:true, observed_at:now, ttl_seconds:60, payload_digest:'a'.repeat(64), now, source_confidence:1 }).disposition, 'ECAC');

assert.equal(deriveContinuityDisposition({
  profile_state:'ECAC', execution_envelope_state:'ECAC', source_head_match:true, identity_pin_match:true,
  heartbeat_state:'ECAC', dependency_state:'ECAC', oracle_state:'ECAC', rollback_verified:true, security_state:'ECAC'
}), 'ECAC');
assert.equal(deriveContinuityDisposition({
  profile_state:'ECAC', execution_envelope_state:'ECAC', source_head_match:false, identity_pin_match:true,
  heartbeat_state:'ECAC', dependency_state:'ECAC', oracle_state:'ECAC', rollback_verified:true, security_state:'ECAC'
}), 'HOLD');
assert.equal(deriveContinuityDisposition({ forbidden_boundary:true }), 'DENY');

const advisory = mlAdvisoryScore({ stale_fraction:1, source_head_drift:1, rollback_gap:1 });
assert.equal(advisory.advisory_only, true);
assert.equal(advisory.final_authority, false);

const recovery = planRecovery({ incident_state:'PASS', rollback_verified:true, backup_verified:true, independent_review_state:'ECAC', source_head_match:true });
assert.equal(recovery.disposition, 'ECAC');
assert.equal(recovery.provider_write, false);
assert.equal(recovery.automatic_destructive_action, false);

assert.equal(interfacePack.phase, '3');
assert.equal(interfacePack.ownership.continuity_and_drift, 'PentaNurture');
assert.equal(interfacePack.ownership.current_state, 'PentaStatus');
assert.equal(interfacePack.ownership.credentials_and_server_binding, 'PentaCredentials');
assert.equal(interfacePack.ownership.exact_scope_certification, 'PentaCertify');
assert.equal(interfacePack.mcp_tools.length, 8);
assert.ok(interfacePack.mcp_tools.every(tool => tool.enabled === false));
assert.ok(interfacePack.mcp_tools.every(tool => tool.runtime_binding_state === 'HOLD_UNBOUND_CURRENT_MCP_SERVER'));
assert.equal(interfacePack.api.deployment_state, 'HOLD_CURRENT_SERVER_BINDING_AND_CERTIFICATION_REQUIRED');
assert.ok(Object.values(interfacePack.boundary).every(value => value === false));

assert.equal(live.source_replay_required, false);
assert.equal(live.old_phase_e_sql_replay_allowed, false);
assert.equal(live.cron.active, true);
assert.equal(live.cron.last_observed_status, 'succeeded');
assert.equal(live.historical_wallet_phase_e.is_latest_suite, false);
assert.equal(live.historical_wallet_phase_e.production_activation, false);
assert.equal(live.latest_suite_observed.current_canonical_system_name, 'PentaGreen');
assert.equal(live.latest_suite_observed.production_activation, false);
assert.equal(live.runtime_release.api_activation_claimed, false);
assert.equal(live.runtime_release.mcp_activation_claimed, false);
assert.ok(Object.values(live.hard_boundaries).every(value => value === false));

console.log(JSON.stringify({
  result:'PASS_CHLOM_WALLET_CONTINUITY_PENTA_V2',
  deterministic_core:true,
  mcp_tools:interfacePack.mcp_tools.length,
  mcp_enabled:0,
  old_sql_replay:false,
  cron_observed_healthy:true,
  historical_wallet_suite_is_latest:false,
  current_latest_suite_canonical_name:live.latest_suite_observed.current_canonical_system_name,
  ai_final_authority:false,
  production_activation:false
}, null, 2));
