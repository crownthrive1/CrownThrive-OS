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
const certification = JSON.parse(fs.readFileSync(new URL('./continuity-runtime-certification-20260826.penta.json', import.meta.url)));

assert.equal(strictest('ECAC', 'HOLD'), 'HOLD');
assert.equal(strictest('ECAC', 'HOLD', 'DENY'), 'DENY');
assert.equal(validateBudgetSemantics(-1).disposition, 'ECAC');
assert.equal(validateBudgetSemantics(0).disposition, 'ECAC');
assert.equal(validateBudgetSemantics(null).disposition, 'HOLD');
assert.equal(validateBudgetSemantics(-2).disposition, 'DENY');

const now = '2026-08-26T15:47:46Z';
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-26T15:47:16Z', ttl_seconds: 60 }).disposition, 'ECAC');
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-26T15:00:00Z', ttl_seconds: 60 }).disposition, 'HOLD');
assert.equal(evaluateEvidenceExpiry({ now, observed_at: '2026-08-26T15:48:00Z', ttl_seconds: 60 }).disposition, 'HOLD');
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
assert.equal(interfacePack.state, 'PRODUCTION_PRIVATE_CONTROL_PLANE_CERTIFIED');
assert.equal(interfacePack.service_availability.production, true);
assert.equal(interfacePack.service_availability.exposure, 'PRIVATE_SERVICE_ROLE_ONLY');
assert.equal(interfacePack.ownership.continuity_and_drift, 'PentaNurture');
assert.equal(interfacePack.ownership.current_state, 'PentaStatus');
assert.equal(interfacePack.ownership.credentials_and_server_binding, 'PentaCredentials');
assert.equal(interfacePack.ownership.exact_scope_certification, 'PentaCertify');
assert.equal(interfacePack.mcp_tools.length, 8);
assert.ok(interfacePack.mcp_tools.every(tool => tool.enabled === true));
assert.ok(interfacePack.mcp_tools.every(tool => tool.runtime_binding_state === 'BOUND_PRIVATE_SERVICE_ROLE_ACTIVE'));
assert.equal(interfacePack.api.deployment_state, 'ACTIVE_PRIVATE_SERVICE_ROLE_BOUND');
assert.equal(interfacePack.boundary.service_production_availability, true);
for (const [key, value] of Object.entries(interfacePack.boundary)) {
  if (key !== 'service_production_availability') assert.equal(value, false, key);
}

assert.equal(live.source_replay_required, false);
assert.equal(live.old_phase_e_sql_replay_allowed, false);
assert.equal(live.edge_runtime.provider_status, 'ACTIVE');
assert.equal(live.edge_runtime.verify_jwt, true);
assert.equal(live.edge_runtime.production_private_service_available, true);
assert.equal(live.edge_runtime.public_or_authenticated_client_access, false);
assert.equal(live.rpc_certification.anon_execute, false);
assert.equal(live.rpc_certification.authenticated_execute, false);
assert.equal(live.rpc_certification.service_role_execute, true);
assert.equal(live.rpc_certification.truth_tick_disposition, 'ECAC');
assert.equal(live.rpc_certification.rollback_canary_residue, 0);
assert.equal(live.cron.active, true);
assert.equal(live.cron.last_observed_status, 'succeeded');
assert.equal(live.historical_wallet_phase_e.is_latest_suite, false);
assert.equal(live.latest_suite_observed.current_canonical_system_name, 'PentaGreen');
assert.equal(live.runtime_release.api_private_activation_claimed, true);
assert.equal(live.runtime_release.mcp_private_activation_claimed, true);
assert.equal(live.runtime_release.operation_authority_activation_claimed, false);

assert.equal(certification.disposition, 'PASS_PRODUCTION_PRIVATE_CONTROL_PLANE');
assert.equal(certification.transport.mcp_tool_count, 8);
assert.equal(certification.transport.public_access, false);
assert.equal(certification.transport.authenticated_user_access, false);
assert.equal(certification.transport.service_role_access, true);
assert.equal(certification.canary.rollback_residue, 0);
assert.equal(certification.authority.service_production_availability, true);
for (const [key, value] of Object.entries(certification.authority)) {
  if (key !== 'service_production_availability') assert.equal(value, false, key);
}

console.log(JSON.stringify({
  result:'PASS_CHLOM_WALLET_CONTINUITY_PENTA_V2',
  deterministic_core:true,
  service_availability:'PRODUCTION_PRIVATE',
  private_service_role_only:true,
  mcp_tools:interfacePack.mcp_tools.length,
  mcp_enabled:interfacePack.mcp_tools.filter(tool => tool.enabled).length,
  old_sql_replay:false,
  cron_observed_healthy:true,
  runtime_canary:'PASS',
  rollback_residue:0,
  historical_wallet_suite_is_latest:false,
  current_latest_suite_canonical_name:live.latest_suite_observed.current_canonical_system_name,
  authority_granted:false,
  suite_production_activation:false,
  ai_final_authority:false
}, null, 2));
