import assert from 'node:assert/strict';
import test from 'node:test';
import healthHandler from '../api/health.js';

function withEnv(values, callback) {
  const previous = new Map();
  for (const [key, value] of Object.entries(values)) {
    previous.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  try {
    return callback();
  } finally {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function response() {
  return {
    headers: {},
    payload: undefined,
    statusCode: null,
    setHeader(name, value) { this.headers[name.toLowerCase()] = value; },
    status(code) { this.statusCode = code; return this; },
    json(payload) { this.payload = payload; return this; },
    end() { return this; },
  };
}

test('health identity is canonical and cannot be replaced by environment input', () => {
  withEnv({
    CROWNTHRIVE_OS_REPOSITORY: 'attacker/substitute',
    VERCEL_DEPLOYMENT_ID: 'dpl_exact',
    VERCEL_ENV: 'production',
    VERCEL_GIT_COMMIT_SHA: 'a'.repeat(40),
  }, () => {
    const result = response();
    healthHandler({ method: 'GET' }, result);
    assert.equal(result.statusCode, 200);
    assert.equal(result.payload.project_id, 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN');
    assert.equal(result.payload.repository, 'crownthrive1/CrownThrive-OS');
    assert.equal(result.payload.build_sha, 'a'.repeat(40));
    assert.equal(result.payload.deployment_id, 'dpl_exact');
    assert.equal(result.payload.vercel_provider_state, 'BOUND_PRODUCTION');
    assert.equal(result.payload.provider_readback, true);
    assert.equal(result.payload.pass_manufactured, false);
  });
});
