import assert from 'node:assert/strict';
import test from 'node:test';
import { safeHealthProjection } from '../lib/vercel-fabric.js';

test('CHLOM camelCase health is normalized into the PentaVercel contract', () => {
  const projected = safeHealthProjection({
    schema: 'ct.chlom.chain-evidence-fabric.health.v2',
    service: 'CHLOM Chain Evidence Fabric',
    role: 'rights_rules_roles_revenue_records_remedies_authority',
    status: 'OPERATIONAL',
    operatingMode: 'GOVERNANCE_CONTROL_PLANE_ONLY',
    readinessStatus: 'CONFIGURATION_HOLD',
    capabilityStates: {
      governanceAndRights: 'OPERATIONAL',
      chainBroadcast: 'GATED',
    },
    release: 'production',
    environment: 'production',
    providerState: 'BOUND_PRODUCTION',
    providerReadback: true,
    writeState: 'GATED',
    projectId: 'prj_HewLgMjUiVBNCl0FADFbSggSp2QN',
    repository: 'crownthrive1/chlom-protocol',
    buildSha: 'abc123',
    deploymentId: 'dpl_123',
    passManufactured: false,
  });

  assert.equal(projected.operating_mode, 'GOVERNANCE_CONTROL_PLANE_ONLY');
  assert.equal(projected.readiness_status, 'CONFIGURATION_HOLD');
  assert.deepEqual(projected.capability_states, {
    governanceAndRights: 'OPERATIONAL',
    chainBroadcast: 'GATED',
  });
  assert.equal(projected.provider_state, 'BOUND_PRODUCTION');
  assert.equal(projected.provider_readback, true);
  assert.equal(projected.write_state, 'GATED');
  assert.equal(projected.project_id, 'prj_HewLgMjUiVBNCl0FADFbSggSp2QN');
  assert.equal(projected.build_sha, 'abc123');
  assert.equal(projected.deployment_id, 'dpl_123');
  assert.equal(projected.pass_manufactured, false);
});

test('existing snake_case health remains compatible', () => {
  const projected = safeHealthProjection({
    status: 'OPERATIONAL',
    operating_mode: 'FULL_AUTONOMOUS_GOVERNED',
    readiness_status: 'READY',
    provider_state: 'BOUND_PRODUCTION',
    provider_readback: true,
    write_state: 'GATED_CREDENTIAL_REQUIRED',
    project_id: 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
    build_sha: 'def456',
    deployment_id: 'dpl_456',
    pass_manufactured: false,
  });

  assert.equal(projected.operating_mode, 'FULL_AUTONOMOUS_GOVERNED');
  assert.equal(projected.readiness_status, 'READY');
  assert.equal(projected.provider_state, 'BOUND_PRODUCTION');
  assert.equal(projected.provider_readback, true);
  assert.equal(projected.pass_manufactured, false);
});

test('manufactured-pass evidence is never hidden by casing differences', () => {
  assert.equal(
    safeHealthProjection({ passManufactured: true }).pass_manufactured,
    true,
  );
  assert.equal(
    safeHealthProjection({ pass_manufactured: true }).pass_manufactured,
    true,
  );
});
