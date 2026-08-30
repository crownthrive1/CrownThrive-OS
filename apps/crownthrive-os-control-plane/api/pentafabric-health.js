import { emitPenta, fabricState, verifyPenta } from '../lib/pentafabric.js';
import {
  requestQueryParam,
  resolveVercelOidcToken,
} from '../lib/vercel-oidc.js';

function send(response, status, payload) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-PentaFabric-Version', '1.0.0');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  return response.status(status).json(payload);
}

function runSelfTest(state, oidcToken) {
  const signatureBound = state.secret_bound === true;
  const oidcRuntimeBound = Boolean(oidcToken);

  if (!signatureBound && !oidcRuntimeBound) {
    throw new Error('PentaFabric runtime assurance is unbound');
  }

  const probe = emitPenta({
    protocol: 'PentaFabricSelfTest',
    payload: {
      probe: true,
      build_sha: state.build_sha,
      oidc_runtime_bound: oidcRuntimeBound,
    },
    source: 'urn:crownthrive:pentafabric:self-test',
    subject: 'pentafabric-self-test',
    route: 'vercel-self-test',
    corridor: 'runtime-assurance',
    lane: 'hot',
    ttl_seconds: 60,
    chlom_intent_id: 'chlom-intent-pentafabric-self-test-v2',
    chlom_policy_refs: ['ct.chlom.pentafabric.v1'],
    rights_scope: 'runtime-assurance-only',
  });

  verifyPenta(probe, { requireSignature: signatureBound });

  return {
    status: 'PASS',
    penta_id: probe.id,
    trace_id: probe.trace.trace_id,
    assurance: signatureBound
      ? probe.integrity.algorithm
      : 'SHA-256+VERCEL_OIDC_RUNTIME_BOUND',
    static_secret_required: false,
    oidc_runtime_bound: oidcRuntimeBound,
    chlom_binding: probe.mesh.chlom.binding,
    event_contract: probe.mesh.contract,
    fabric_schema: probe.mesh.fabric.schema,
  };
}

export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return send(response, 405, {
      status: 'REJECTED',
      error: 'method_not_allowed',
    });
  }

  const state = fabricState();
  const oidcToken = resolveVercelOidcToken(request);

  try {
    const selfTestRequested = requestQueryParam(request, 'selftest') === '1';
    return send(response, 200, {
      schema: 'ct.penta.vercel.fabric-health.20260830.v2',
      service: 'crownthrive-os-control-plane',
      status: 'OPERATIONAL',
      fabric: state,
      transport_assurance: oidcToken
        ? 'VERCEL_OIDC_RS256'
        : state.secret_bound
          ? 'HMAC_SHA256_BOUND'
          : 'UNBOUND',
      static_secret_required: false,
      oidc_runtime_bound: Boolean(oidcToken),
      self_test: selfTestRequested
        ? runSelfTest(state, oidcToken)
        : { status: 'NOT_REQUESTED' },
      observed_at: new Date().toISOString(),
    });
  } catch (error) {
    return send(response, 503, {
      schema: 'ct.penta.vercel.fabric-health.20260830.v2',
      status: 'DEGRADED',
      error: 'pentafabric_self_test_failure',
      detail: String(error?.message || error),
      fabric: state,
    });
  }
}
