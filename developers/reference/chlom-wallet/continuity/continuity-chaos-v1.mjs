import assert from 'node:assert/strict';
import { deriveContinuityDisposition, evaluateHeartbeat, evaluateOracleObservation, validateBudgetSemantics } from './continuity-core-v1.mjs';

function rng(seed) {
  let x = seed >>> 0;
  return () => ((x = (x * 1664525 + 1013904223) >>> 0) / 0x100000000);
}

const random = rng(0xC7102026);
let ecac = 0, hold = 0, deny = 0, unsafeEcac = 0, invariantFailures = 0;
const cases = 50000;

for (let i = 0; i < cases; i++) {
  const forbidden = random() < 0.13;
  const secretExposure = random() < 0.08;
  const authorityEscalation = random() < 0.1;
  const sourceHeadMatch = random() >= 0.2;
  const identityPinMatch = random() >= 0.15;
  const rollbackVerified = random() >= 0.25;
  const hbFresh = random() >= 0.28;
  const oracleReadOnly = random() >= 0.12;
  const oracleConfidence = random();

  const heartbeat = evaluateHeartbeat({
    now: '2026-08-23T05:00:00Z',
    last_heartbeat_at: hbFresh ? '2026-08-23T04:30:00Z' : '2026-08-23T02:00:00Z',
    next_heartbeat_due_at: hbFresh ? '2026-08-23T05:30:00Z' : '2026-08-23T03:00:00Z',
    heartbeat_state: 'HEALTHY'
  });
  const oracle = evaluateOracleObservation({
    connection_state: 'BOUND_CONTROLLED_TEST', read_only: oracleReadOnly,
    observed_at: '2026-08-23T04:59:30Z', ttl_seconds: 120,
    payload_digest: 'b'.repeat(64), now: '2026-08-23T05:00:00Z', source_confidence: oracleConfidence
  });
  const d = deriveContinuityDisposition({
    profile_state:'ECAC', execution_envelope_state:'ECAC', source_head_match, identity_pin_match,
    heartbeat_state:heartbeat.disposition, dependency_state: random() < 0.17 ? 'HOLD' : 'ECAC',
    oracle_state:oracle.disposition, rollback_verified, security_state: random() < 0.07 ? 'DENY' : 'ECAC',
    forbidden_boundary:forbidden, authority_escalation:authorityEscalation, secret_exposure:secretExposure
  });
  if (d === 'ECAC') ecac++; else if (d === 'HOLD') hold++; else if (d === 'DENY') deny++; else invariantFailures++;
  const unsafe = forbidden || secretExposure || authorityEscalation || !oracleReadOnly;
  if (unsafe && d === 'ECAC') unsafeEcac++;
}

for (const [value, expected] of [[-1,'ECAC'],[0,'ECAC'],[1,'ECAC'],[100,'ECAC'],[null,'HOLD'],[-2,'DENY']]) {
  assert.equal(validateBudgetSemantics(value).disposition, expected);
}
assert.equal(unsafeEcac, 0);
assert.equal(invariantFailures, 0);
assert.equal(ecac + hold + deny, cases);

console.log(JSON.stringify({
  result:'PASS_CHLOM_WALLET_CONTINUITY_CHAOS_V1',
  cases,
  ecac,
  hold,
  deny,
  unsafe_ecac:unsafeEcac,
  invariant_failures:invariantFailures,
  budget_semantics_correct:true,
  ai_final_authority:false,
  production_activation:false
}, null, 2));
