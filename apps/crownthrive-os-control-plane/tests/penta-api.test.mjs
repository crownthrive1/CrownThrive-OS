import assert from 'node:assert/strict';
import test from 'node:test';
import pentaHandler from '../api/penta.js';
import { emitPenta, verifyPenta } from '../lib/pentafabric.js';

const WRITE_TOKEN =
  'test-pentafabric-write-token-at-least-32-bytes';
const SIGNING_SECRET =
  'test-pentafabric-signing-secret-at-least-32-bytes';
const SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const PENTAFABRIC_INGEST_URL =
  `${SUPABASE_ORIGIN}/functions/v1/pentafabric-ingest`;
const EXPECTED_OIDC_AUTHENTICATION = 'VERCEL_OIDC_RS256';
const EXPECTED_OIDC_WORKLOAD = Object.freeze({
  owner_id: 'team_v4xkGtBZSrZXnJtLEJhra5nd',
  project_id: 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
  environment: 'production',
});

const PENTA_ENV = {
  CHLOM_SIGNING_SECRET: undefined,
  NEXT_PUBLIC_SUPABASE_URL: undefined,
  PENTAFABRIC_INGEST_URL: undefined,
  PENTAFABRIC_SIGNING_SECRET: undefined,
  PENTAFABRIC_WRITE_TOKEN: WRITE_TOKEN,
  PENTA_SIGNING_SECRET: undefined,
  SUPABASE_SERVICE_ROLE_KEY: undefined,
  SUPABASE_URL: undefined,
  VERCEL_GIT_COMMIT_SHA: undefined,
  VERCEL_OIDC_TOKEN: undefined,
};

function withEnv(values, callback) {
  const previous = new Map();
  for (const [key, value] of Object.entries(values)) {
    previous.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  const finish = () => {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  try {
    const result = callback();
    if (result && typeof result.then === 'function') {
      return result.finally(finish);
    }
    finish();
    return result;
  } catch (error) {
    finish();
    throw error;
  }
}

function mockRequest(body) {
  return {
    method: 'POST',
    url: '/api/penta',
    headers: {
      authorization: `Bearer ${WRITE_TOKEN}`,
      host: 'crown-thrive-os.vercel.app',
      'x-forwarded-proto': 'https',
    },
    body,
  };
}

function mockResponse() {
  return {
    headers: {},
    statusCode: null,
    payload: undefined,
    setHeader(name, value) {
      this.headers[name.toLowerCase()] = value;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(payload) {
      this.payload = payload;
      return this;
    },
  };
}

function eventInput() {
  return {
    protocol: 'PentaApiTest',
    payload: { probe: true },
    source: 'urn:crownthrive:test:penta-api',
    subject: 'penta-api-test',
    route: 'penta-api-test',
    corridor: 'runtime-assurance',
    lane: 'hot',
    ttl_seconds: 60,
    chlom_intent_id: 'chlom-intent-penta-api-test-v1',
    chlom_policy_refs: ['ct.chlom.pentafabric.v1'],
    rights_scope: 'runtime-assurance-only',
  };
}

async function withPersistedFetch(callback) {
  const originalFetch = global.fetch;
  let calls = 0;
  let stored = null;
  global.fetch = async (_url, options = {}) => {
    calls += 1;
    if (options.method === 'POST') {
      const row = JSON.parse(options.body);
      stored = {
        penta_id: row.penta_id,
        trace_id: row.trace_id,
        integrity_digest: row.integrity_digest,
        build_sha: row.build_sha,
        event: row.event,
      };
      return new Response('', { status: 201 });
    }
    return new Response(JSON.stringify(stored ? [stored] : []), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await callback(() => calls);
  } finally {
    global.fetch = originalFetch;
  }
}

test('unbound evidence sink returns a hold instead of DELIVERED/202', async () => {
  await withEnv({ ...PENTA_ENV, PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET }, async () => {
    const response = mockResponse();
    await pentaHandler(mockRequest(eventInput()), response);

    assert.equal(response.statusCode, 503);
    assert.equal(response.payload.status, 'DELIVERY_HOLD');
    assert.equal(
      response.payload.error,
      'pentafabric_evidence_sink_unbound',
    );
    assert.equal(
      response.payload.persistence.status,
      'SKIPPED_UNBOUND',
    );
    assert.equal(response.payload.pass_manufactured, false);
    assert.equal(response.payload.receipt, undefined);
  });
});

test('short write token bindings fail closed before persistence', async () => {
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    throw new Error('must not be called');
  };
  try {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        PENTAFABRIC_WRITE_TOKEN: 'short',
      },
      async () => {
        const request = mockRequest(eventInput());
        request.headers.authorization = 'Bearer short';
        const response = mockResponse();
        await pentaHandler(request, response);
        assert.equal(response.statusCode, 503);
        assert.equal(response.payload.status, 'WRITE_GATED');
        assert.equal(
          response.payload.error,
          'write_authorization_binding_invalid',
        );
        assert.equal(calls, 0);
      },
    );
  } finally {
    global.fetch = originalFetch;
  }
});

test('caller-supplied OIDC header is presence-only until provider validation', async () => {
  await withEnv(PENTA_ENV, async () => {
    const response = mockResponse();
    await pentaHandler({
      method: 'GET',
      url: '/api/penta',
      headers: {
        host: 'crown-thrive-os.vercel.app',
        'x-forwarded-proto': 'https',
        'x-vercel-oidc-token': 'not-a-jwt',
      },
    }, response);

    assert.equal(response.statusCode, 200);
    assert.equal(response.payload.evidence_sink.bound, false);
    assert.equal(
      response.payload.evidence_sink.mode,
      'VERCEL_OIDC_PRESENT_UNVERIFIED',
    );
    assert.equal(response.payload.evidence_sink.oidc_token_present, true);
    assert.equal(response.payload.evidence_sink.oidc_token_verified, false);
  });
});

test('service-role credentials are never sent to a noncanonical Supabase URL', async () => {
  const hostileUrls = [
    'http://tzajnzshmtzjenqulehq.supabase.co',
    'https://attacker.example',
    'https://user:password@tzajnzshmtzjenqulehq.supabase.co',
    'https://tzajnzshmtzjenqulehq.supabase.co:8443',
    'https://tzajnzshmtzjenqulehq.supabase.co/rest/v1',
    'https://tzajnzshmtzjenqulehq.supabase.co?redirect=attacker',
    ` ${SUPABASE_ORIGIN}`,
    `${SUPABASE_ORIGIN} `,
  ];
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    throw new Error('credentials must not leave the canonical origin');
  };
  try {
    for (const supabaseUrl of hostileUrls) {
      await withEnv(
        {
          ...PENTA_ENV,
          PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
          SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
          SUPABASE_URL: supabaseUrl,
        },
        async () => {
          const stateResponse = mockResponse();
          await pentaHandler({
            method: 'GET',
            url: '/api/penta',
            headers: {},
          }, stateResponse);
          assert.equal(stateResponse.statusCode, 200);
          assert.equal(
            stateResponse.payload.evidence_sink.mode,
            'SERVICE_ROLE_CONFIGURATION_HOLD',
          );
          assert.equal(
            stateResponse.payload.evidence_sink.service_role_configuration_valid,
            false,
          );
          const response = mockResponse();
          await pentaHandler(mockRequest(eventInput()), response);
          assert.equal(response.statusCode, 503);
          assert.equal(response.payload.status, 'DELIVERY_HOLD');
          assert.equal(
            response.payload.error,
            'pentafabric_evidence_sink_failure',
          );
        },
      );
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('OIDC bearer token is never sent outside the exact ingest function', async () => {
  const hostileUrls = [
    `${SUPABASE_ORIGIN}/functions/v1/other`,
    `${PENTAFABRIC_INGEST_URL}/extra`,
    `${PENTAFABRIC_INGEST_URL}?redirect=attacker`,
    `https://user:password@tzajnzshmtzjenqulehq.supabase.co${PENTAFABRIC_INGEST_URL.slice(SUPABASE_ORIGIN.length)}`,
    'https://attacker.example/functions/v1/pentafabric-ingest',
  ];
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    throw new Error('OIDC token must not leave the canonical ingest URL');
  };
  try {
    for (const ingestUrl of hostileUrls) {
      await withEnv(
        {
          ...PENTA_ENV,
          PENTAFABRIC_INGEST_URL: ingestUrl,
          PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
          VERCEL_OIDC_TOKEN: 'test-vercel-oidc-token',
        },
        async () => {
          const stateResponse = mockResponse();
          await pentaHandler({
            method: 'GET',
            url: '/api/penta',
            headers: {},
          }, stateResponse);
          assert.equal(stateResponse.statusCode, 200);
          assert.equal(
            stateResponse.payload.evidence_sink.mode,
            'VERCEL_OIDC_INGEST_CONFIGURATION_HOLD',
          );
          assert.equal(
            stateResponse.payload.evidence_sink.oidc_ingest_configuration_valid,
            false,
          );
          const response = mockResponse();
          await pentaHandler(mockRequest(eventInput()), response);
          assert.equal(response.statusCode, 503);
          assert.equal(response.payload.status, 'DELIVERY_HOLD');
          assert.equal(
            response.payload.error,
            'pentafabric_evidence_sink_failure',
          );
        },
      );
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('canonical OIDC remains primary over service-role fallback and requires exact readback', async () => {
  const originalFetch = global.fetch;
  const requests = [];
  global.fetch = async (url, options = {}) => {
    requests.push({ url, options });
    const { penta } = JSON.parse(options.body);
    return new Response(JSON.stringify({
      status: 'PERSISTED_READBACK_VERIFIED',
      authentication: EXPECTED_OIDC_AUTHENTICATION,
      workload: EXPECTED_OIDC_WORKLOAD,
      penta_id: penta.id,
      trace_id: penta.trace.trace_id,
      integrity_digest: penta.integrity.digest,
      signing_build_sha: penta.integrity.build_sha,
      exact_readback: true,
    }), {
      status: 202,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_INGEST_URL,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role-fallback',
        SUPABASE_URL: SUPABASE_ORIGIN,
        VERCEL_OIDC_TOKEN: 'test-vercel-oidc-token',
      },
      async () => {
        const stateResponse = mockResponse();
        await pentaHandler({
          method: 'GET',
          url: '/api/penta',
          headers: {},
        }, stateResponse);
        assert.equal(stateResponse.payload.evidence_sink.bound, false);
        assert.equal(
          stateResponse.payload.evidence_sink.mode,
          'VERCEL_OIDC_PRESENT_UNVERIFIED',
        );
        assert.equal(
          stateResponse.payload.evidence_sink.primary_route,
          'VERCEL_OIDC',
        );
        assert.equal(
          stateResponse.payload.evidence_sink.service_role_fallback_available,
          true,
        );
        const response = mockResponse();
        await pentaHandler(mockRequest(eventInput()), response);
        assert.equal(response.statusCode, 202);
        assert.equal(response.payload.receipt.status, 'DELIVERED');
        assert.equal(
          response.payload.receipt.persistence.authentication,
          EXPECTED_OIDC_AUTHENTICATION,
        );
        assert.deepEqual(
          response.payload.receipt.persistence.workload,
          EXPECTED_OIDC_WORKLOAD,
        );
      },
    );
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, PENTAFABRIC_INGEST_URL);
    assert.equal(requests[0].options.redirect, 'error');
    assert.equal(
      requests[0].options.headers.Authorization,
      'Bearer test-vercel-oidc-token',
    );
    assert.equal(requests[0].options.headers.apikey, undefined);
  } finally {
    global.fetch = originalFetch;
  }
});

test('OIDC receipt authentication and workload omissions/substitutions hold delivery', async () => {
  const originalFetch = global.fetch;
  const cases = [
    ['missing-authentication', (receipt) => { delete receipt.authentication; }],
    ['wrong-authentication', (receipt) => { receipt.authentication = 'CALLER_ASSERTED'; }],
    ['missing-workload', (receipt) => { delete receipt.workload; }],
    ['missing-owner', (receipt) => { delete receipt.workload.owner_id; }],
    ['wrong-owner', (receipt) => { receipt.workload.owner_id = 'team_v4x8qxBvnk2dCaD5D0M3KYBN'; }],
    ['missing-project', (receipt) => { delete receipt.workload.project_id; }],
    ['wrong-project', (receipt) => { receipt.workload.project_id = 'prj_x6n4c2Foiz5BKAfwuYLFhaUiNvJd'; }],
    ['missing-environment', (receipt) => { delete receipt.workload.environment; }],
    ['wrong-environment', (receipt) => { receipt.workload.environment = 'preview'; }],
  ];
  try {
    for (const [label, mutate] of cases) {
      let calls = 0;
      global.fetch = async (_url, options = {}) => {
        calls += 1;
        const { penta } = JSON.parse(options.body);
        const receipt = {
          status: 'PERSISTED_READBACK_VERIFIED',
          authentication: EXPECTED_OIDC_AUTHENTICATION,
          workload: { ...EXPECTED_OIDC_WORKLOAD },
          penta_id: penta.id,
          trace_id: penta.trace.trace_id,
          integrity_digest: penta.integrity.digest,
          signing_build_sha: penta.integrity.build_sha,
          exact_readback: true,
        };
        mutate(receipt);
        return new Response(JSON.stringify(receipt), {
          status: 202,
          headers: { 'content-type': 'application/json' },
        });
      };
      await withEnv(
        {
          ...PENTA_ENV,
          PENTAFABRIC_INGEST_URL,
          PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
          VERCEL_OIDC_TOKEN: 'test-vercel-oidc-token',
        },
        async () => {
          const response = mockResponse();
          await pentaHandler(mockRequest(eventInput()), response);
          assert.equal(response.statusCode, 503, label);
          assert.equal(response.payload.status, 'DELIVERY_HOLD', label);
          assert.equal(
            response.payload.error,
            'pentafabric_evidence_sink_failure',
            label,
          );
          assert.equal(response.payload.receipt, undefined, label);
          assert.equal(response.payload.pass_manufactured, false, label);
          assert.equal(calls, 1, label);
        },
      );
    }
  } finally {
    global.fetch = originalFetch;
  }
});

test('PentaFabric self-test holds when the HMAC binding is unavailable', async () => {
  await withEnv(PENTA_ENV, async () => {
    const response = mockResponse();
    await pentaHandler({
      method: 'GET',
      url: '/api/penta?selftest=1',
      headers: {
        host: 'crown-thrive-os.vercel.app',
        'x-forwarded-proto': 'https',
      },
    }, response);

    assert.equal(response.statusCode, 503);
    assert.equal(response.payload.status, 'DEGRADED');
    assert.equal(response.payload.error, 'pentafabric_self_test_failure');
    assert.match(response.payload.detail, /signing secret is not bound/i);
  });
});

test('legacy signing secrets cannot authorize PentaFabric persistence', async () => {
  await withEnv(
    {
      ...PENTA_ENV,
      CHLOM_SIGNING_SECRET: SIGNING_SECRET,
      PENTA_SIGNING_SECRET: SIGNING_SECRET,
    },
    () => {
      const penta = emitPenta(eventInput());
      assert.equal(penta.integrity.algorithm, 'SHA-256');
      assert.equal(penta.integrity.signature, null);
      assert.throws(
        () => verifyPenta(penta, { requireSignature: true }),
        /PentaFabric signing secret is not bound/i,
      );
    },
  );
});

test('externally supplied unsigned Penta is rejected before persistence', async () => {
  let unsignedPenta;
  await withEnv(PENTA_ENV, () => {
    unsignedPenta = emitPenta(eventInput());
  });

  await withPersistedFetch(async (fetchCalls) => {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
        SUPABASE_URL: SUPABASE_ORIGIN,
      },
      async () => {
        const response = mockResponse();
        await pentaHandler(mockRequest({ penta: unsignedPenta }), response);

        assert.equal(response.statusCode, 400);
        assert.equal(response.payload.status, 'REJECTED');
        assert.equal(
          response.payload.error,
          'pentafabric_contract_failure',
        );
        assert.match(response.payload.detail, /signed Penta required/i);
        assert.equal(fetchCalls(), 0);
      },
    );
  });
});

test('externally supplied HMAC Penta persists and returns DELIVERED/202', async () => {
  await withPersistedFetch(async (fetchCalls) => {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
        SUPABASE_URL: SUPABASE_ORIGIN,
      },
      async () => {
        const signedPenta = emitPenta(eventInput());
        const response = mockResponse();
        await pentaHandler(mockRequest({ penta: signedPenta }), response);

        assert.equal(response.statusCode, 202);
        assert.equal(response.payload.receipt.status, 'DELIVERED');
        assert.equal(
          response.payload.receipt.persistence.status,
          'PERSISTED_READBACK_VERIFIED',
        );
        assert.equal(response.payload.receipt.persistence.exact_readback, true);
        assert.equal(response.payload.penta.integrity.algorithm, 'HMAC-SHA256');
        assert.equal(fetchCalls(), 2);
      },
    );
  });
});

test('signed integrity metadata and dangerous object keys cannot be changed', async () => {
  await withEnv(
    { ...PENTA_ENV, PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET },
    () => {
      for (const field of ['algorithm', 'key_id', 'build_sha']) {
        const penta = emitPenta(eventInput());
        penta.integrity[field] = field === 'build_sha' ? '0'.repeat(40) : 'tampered';
        assert.throws(
          () => verifyPenta(penta, { requireSignature: true }),
          /integrity algorithm|key_id|digest mismatch/i,
        );
      }
      for (const key of ['__proto__', 'constructor', 'prototype']) {
        const penta = emitPenta(eventInput());
        Object.defineProperty(penta.data.payload, key, {
          value: 'tampered',
          enumerable: true,
          configurable: true,
        });
        assert.throws(
          () => verifyPenta(penta, { requireSignature: true }),
          /prohibited object key/i,
        );
      }
    },
  );
});

test('digest and HMAC encodings must be exact lowercase 64-character hex', async () => {
  await withEnv(
    { ...PENTA_ENV, PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET },
    () => {
      for (const field of ['digest', 'signature']) {
        const original = emitPenta(eventInput());
        const canonical = original.integrity[field];
        assert.match(canonical, /^[a-f0-9]{64}$/);
        assert.match(canonical, /[a-f]/);
        for (const invalid of [
          `${canonical}f`,
          canonical.slice(0, -1),
          canonical.toUpperCase(),
        ]) {
          const penta = structuredClone(original);
          penta.integrity[field] = invalid;
          assert.throws(
            () => verifyPenta(penta, { requireSignature: true }),
            /digest mismatch|signature mismatch/i,
          );
        }
      }
    },
  );
});

test('signed build lineage must use canonical lowercase Git hex', async () => {
  await withEnv(
    {
      ...PENTA_ENV,
      PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
      VERCEL_GIT_COMMIT_SHA: 'A'.repeat(40),
    },
    () => {
      const penta = emitPenta(eventInput());
      assert.throws(
        () => verifyPenta(penta, { requireSignature: true }),
        /build_sha is invalid/i,
      );
    },
  );
});

test('signed packet build lineage is persisted independently of the persister build', async () => {
  const signingBuildSha = 'a'.repeat(40);
  const persistingBuildSha = 'b'.repeat(40);
  let signedPenta;
  await withEnv(
    {
      ...PENTA_ENV,
      PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
      VERCEL_GIT_COMMIT_SHA: signingBuildSha,
    },
    () => {
      signedPenta = emitPenta(eventInput());
    },
  );

  await withPersistedFetch(async (fetchCalls) => {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
        SUPABASE_URL: SUPABASE_ORIGIN,
        VERCEL_GIT_COMMIT_SHA: persistingBuildSha,
      },
      async () => {
        const response = mockResponse();
        await pentaHandler(mockRequest({ penta: signedPenta }), response);

        assert.equal(response.statusCode, 202);
        assert.equal(response.payload.penta.integrity.build_sha, signingBuildSha);
        assert.equal(response.payload.receipt.signing_build_sha, signingBuildSha);
        assert.equal(response.payload.receipt.persisting_build_sha, persistingBuildSha);
        assert.equal(
          response.payload.receipt.persistence.signing_build_sha,
          signingBuildSha,
        );
        assert.equal(fetchCalls(), 2);
      },
    );
  });
});

test('internally generated Penta is held when the signing key is unbound', async () => {
  await withPersistedFetch(async (fetchCalls) => {
    await withEnv(
      {
        ...PENTA_ENV,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
        SUPABASE_URL: SUPABASE_ORIGIN,
      },
      async () => {
        const response = mockResponse();
        await pentaHandler(mockRequest(eventInput()), response);

        assert.equal(response.statusCode, 400);
        assert.equal(response.payload.status, 'REJECTED');
        assert.match(response.payload.detail, /signing secret is not bound/i);
        assert.equal(fetchCalls(), 0);
      },
    );
  });
});

test('internally generated Penta uses HMAC before persistence', async () => {
  await withPersistedFetch(async (fetchCalls) => {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
        SUPABASE_URL: SUPABASE_ORIGIN,
      },
      async () => {
        const response = mockResponse();
        await pentaHandler(mockRequest(eventInput()), response);

        assert.equal(response.statusCode, 202);
        assert.equal(response.payload.receipt.status, 'DELIVERED');
        assert.equal(response.payload.penta.integrity.algorithm, 'HMAC-SHA256');
        assert.equal(fetchCalls(), 2);
      },
    );
  });
});

for (const failure of [
  {
    name: 'provider rejection',
    fetch: async () => new Response('provider unavailable', { status: 503 }),
    upstreamStatus: 503,
  },
  {
    name: 'network failure',
    fetch: async () => { throw new TypeError('connection reset'); },
    upstreamStatus: null,
  },
]) {
  test(`evidence sink ${failure.name} returns DELIVERY_HOLD/503`, async () => {
    const originalFetch = global.fetch;
    global.fetch = failure.fetch;
    try {
      await withEnv(
        {
          ...PENTA_ENV,
          PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
          SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
          SUPABASE_URL: SUPABASE_ORIGIN,
        },
        async () => {
          const response = mockResponse();
          await pentaHandler(mockRequest(eventInput()), response);

          assert.equal(response.statusCode, 503);
          assert.equal(response.payload.status, 'DELIVERY_HOLD');
          assert.equal(
            response.payload.error,
            'pentafabric_evidence_sink_failure',
          );
          assert.equal(response.payload.persistence.status, 'FAILED');
          assert.equal(
            response.payload.persistence.upstream_status,
            failure.upstreamStatus,
          );
          assert.equal(response.payload.receipt, undefined);
          assert.equal(response.payload.pass_manufactured, false);
        },
      );
    } finally {
      global.fetch = originalFetch;
    }
  });
}

test('conflicting idempotent row cannot produce a delivery receipt', async () => {
  const originalFetch = global.fetch;
  let stored = null;
  global.fetch = async (_url, options = {}) => {
    if (options.method === 'POST') {
      const row = JSON.parse(options.body);
      stored = {
        penta_id: row.penta_id,
        trace_id: row.trace_id,
        integrity_digest: '0'.repeat(64),
        event: row.event,
      };
      return new Response('', { status: 201 });
    }
    return new Response(JSON.stringify([stored]), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv(
      {
        ...PENTA_ENV,
        PENTAFABRIC_SIGNING_SECRET: SIGNING_SECRET,
        SUPABASE_SERVICE_ROLE_KEY: 'test-service-role',
        SUPABASE_URL: SUPABASE_ORIGIN,
      },
      async () => {
        const response = mockResponse();
        await pentaHandler(mockRequest(eventInput()), response);
        assert.equal(response.statusCode, 503);
        assert.equal(response.payload.status, 'DELIVERY_HOLD');
        assert.equal(response.payload.receipt, undefined);
      },
    );
  } finally {
    global.fetch = originalFetch;
  }
});
