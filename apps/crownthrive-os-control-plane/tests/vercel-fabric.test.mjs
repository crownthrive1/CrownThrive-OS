import assert from 'node:assert/strict';
import test from 'node:test';
import {
  collectVercelFabric,
  PROJECT_BINDINGS,
  safeHealthProjection,
  supabaseEvidenceBindingState,
} from '../lib/vercel-fabric.js';

function withEnv(values, callback) {
  const previous = new Map();
  for (const [key, value] of Object.entries(values)) {
    previous.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  const restore = () => {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  try {
    const result = callback();
    if (result && typeof result.then === 'function') return result.finally(restore);
    restore();
    return result;
  } catch (error) {
    restore();
    throw error;
  }
}

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

test('missing manufactured-pass evidence remains unknown', () => {
  assert.equal(safeHealthProjection({}).pass_manufactured, null);
  assert.equal(
    safeHealthProjection({ pass_manufactured: 'false' }).pass_manufactured,
    null,
  );
});

test('evidence sink binding rejects noncanonical Supabase origins', () => {
  const hostileOrigins = [
    'http://tzajnzshmtzjenqulehq.supabase.co',
    'https://attacker.example',
    'https://user:password@tzajnzshmtzjenqulehq.supabase.co',
    'https://tzajnzshmtzjenqulehq.supabase.co:8443',
    'https://tzajnzshmtzjenqulehq.supabase.co/rest/v1',
    'https://tzajnzshmtzjenqulehq.supabase.co?redirect=attacker',
  ];
  for (const origin of hostileOrigins) {
    withEnv({
      NEXT_PUBLIC_SUPABASE_URL: undefined,
      SUPABASE_SERVICE_ROLE_KEY: 'secret-present',
      SUPABASE_URL: origin,
    }, () => {
      assert.deepEqual(supabaseEvidenceBindingState(), {
        service_role_present: true,
        service_role_configuration_valid: false,
        service_role_fallback_available: false,
        oidc_token_present: false,
        oidc_ingest_configuration_valid: true,
        bound: false,
        mode: 'SERVICE_ROLE_CONFIGURATION_HOLD',
      });
    });
  }
});

test('OIDC is the truthful primary route when service-role fallback is also bound', () => {
  withEnv({
    NEXT_PUBLIC_SUPABASE_URL: undefined,
    PENTAFABRIC_INGEST_URL: undefined,
    SUPABASE_SERVICE_ROLE_KEY: 'secret-present',
    SUPABASE_URL: 'https://tzajnzshmtzjenqulehq.supabase.co',
  }, () => {
    const state = supabaseEvidenceBindingState({ oidcTokenPresent: true });
    assert.equal(state.bound, false);
    assert.equal(state.mode, 'VERCEL_OIDC_PRESENT_UNVERIFIED');
    assert.equal(state.oidc_ingest_configuration_valid, true);
    assert.equal(state.service_role_fallback_available, true);
  });
});

test('OIDC primary route holds on a noncanonical ingest URL despite a valid fallback', () => {
  withEnv({
    NEXT_PUBLIC_SUPABASE_URL: undefined,
    PENTAFABRIC_INGEST_URL: 'https://attacker.example/functions/v1/pentafabric-ingest',
    SUPABASE_SERVICE_ROLE_KEY: 'secret-present',
    SUPABASE_URL: 'https://tzajnzshmtzjenqulehq.supabase.co',
  }, () => {
    const state = supabaseEvidenceBindingState({ oidcTokenPresent: true });
    assert.equal(state.bound, false);
    assert.equal(state.mode, 'VERCEL_OIDC_INGEST_CONFIGURATION_HOLD');
    assert.equal(state.oidc_ingest_configuration_valid, false);
    assert.equal(state.service_role_fallback_available, true);
  });
});

test('evidence sink binding accepts only the exact project origin', () => {
  for (const origin of [
    'https://tzajnzshmtzjenqulehq.supabase.co',
    'https://tzajnzshmtzjenqulehq.supabase.co/',
  ]) {
    withEnv({
      NEXT_PUBLIC_SUPABASE_URL: undefined,
      SUPABASE_SERVICE_ROLE_KEY: 'secret-present',
      SUPABASE_URL: origin,
    }, () => {
      assert.equal(supabaseEvidenceBindingState().bound, true);
      assert.equal(supabaseEvidenceBindingState().mode, 'SERVICE_ROLE');
    });
  }
});

test('execution fabric rejects substituted project identities and redirects', async () => {
  const originalFetch = global.fetch;
  const observed = [];
  global.fetch = async (url, options = {}) => {
    observed.push({ url, options });
    return new Response(JSON.stringify({
      status: 'OPERATIONAL',
      release: 'production',
      provider_state: 'BOUND_PRODUCTION',
      provider_readback: true,
      project_id: 'prj_ATTACKER',
      repository: 'attacker/substitute',
      build_sha: 'c'.repeat(40),
      deployment_id: 'dpl_substitute',
      pass_manufactured: false,
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv({
      NEXT_PUBLIC_SUPABASE_URL: undefined,
      PENTAFABRIC_INGEST_URL: undefined,
      SUPABASE_SERVICE_ROLE_KEY: undefined,
      SUPABASE_URL: undefined,
      VERCEL_DEPLOYMENT_ID: 'dpl_self',
      VERCEL_ENV: 'production',
      VERCEL_GIT_COMMIT_SHA: 'a'.repeat(40),
    }, async () => {
      const fabric = await collectVercelFabric({ timeoutMs: 500 });
      assert.equal(fabric.status, 'DEGRADED');
      assert.equal(fabric.operational_project_count, 1);
      for (const project of fabric.projects.slice(1)) {
        assert.equal(project.state, 'HOLD');
        assert.equal(project.health.project_id, 'prj_ATTACKER');
      }
    });
    assert.deepEqual(
      observed.map((item) => item.url),
      PROJECT_BINDINGS.slice(1).map((binding) => binding.health_url),
    );
    for (const { options } of observed) {
      assert.equal(options.redirect, 'error');
    }
  } finally {
    global.fetch = originalFetch;
  }
});

test('execution fabric passes only exact canonical project identities', async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url, options = {}) => {
    const binding = PROJECT_BINDINGS.find((item) => item.health_url === url);
    assert.ok(binding);
    assert.equal(options.redirect, 'error');
    return new Response(JSON.stringify({
      status: 'OPERATIONAL',
      release: 'production',
      provider_state: 'BOUND_PRODUCTION',
      provider_readback: true,
      project_id: binding.project_id,
      repository: binding.repository,
      build_sha: 'c'.repeat(40),
      deployment_id: 'dpl_exact',
      pass_manufactured: false,
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv({
      NEXT_PUBLIC_SUPABASE_URL: undefined,
      PENTAFABRIC_INGEST_URL: undefined,
      SUPABASE_SERVICE_ROLE_KEY: undefined,
      SUPABASE_URL: undefined,
      VERCEL_DEPLOYMENT_ID: 'dpl_self',
      VERCEL_ENV: 'production',
      VERCEL_GIT_COMMIT_SHA: 'a'.repeat(40),
    }, async () => {
      const fabric = await collectVercelFabric({ timeoutMs: 500 });
      assert.equal(fabric.status, 'OPERATIONAL');
      assert.equal(fabric.operational_project_count, 4);
      assert.ok(fabric.projects.every((project) => project.state === 'PASS'));
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test('execution fabric holds when manufactured-pass evidence is omitted', async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url, options = {}) => {
    const binding = PROJECT_BINDINGS.find((item) => item.health_url === url);
    assert.ok(binding);
    assert.equal(options.redirect, 'error');
    return new Response(JSON.stringify({
      status: 'OPERATIONAL',
      release: 'production',
      provider_state: 'BOUND_PRODUCTION',
      provider_readback: true,
      project_id: binding.project_id,
      repository: binding.repository,
      build_sha: 'c'.repeat(40),
      deployment_id: 'dpl_exact',
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv({
      NEXT_PUBLIC_SUPABASE_URL: undefined,
      PENTAFABRIC_INGEST_URL: undefined,
      SUPABASE_SERVICE_ROLE_KEY: undefined,
      SUPABASE_URL: undefined,
      VERCEL_DEPLOYMENT_ID: 'dpl_self',
      VERCEL_ENV: 'production',
      VERCEL_GIT_COMMIT_SHA: 'a'.repeat(40),
    }, async () => {
      const fabric = await collectVercelFabric({ timeoutMs: 500 });
      assert.equal(fabric.status, 'DEGRADED');
      assert.equal(fabric.operational_project_count, 1);
      for (const project of fabric.projects.slice(1)) {
        assert.equal(project.state, 'HOLD');
        assert.equal(project.health.pass_manufactured, null);
      }
    });
  } finally {
    global.fetch = originalFetch;
  }
});
