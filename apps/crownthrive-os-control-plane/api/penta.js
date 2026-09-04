import { timingSafeEqual } from 'node:crypto';
import {
  canonicalPentaJson,
  emitPenta,
  fabricState,
  verifyPenta,
} from '../lib/pentafabric.js';
import {
  requestHeader,
  requestQueryParam,
  resolveVercelOidcToken,
} from '../lib/vercel-oidc.js';

const MAX_BODY_BYTES = 262144;
const SUPABASE_PROJECT_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const PENTAFABRIC_INGEST_PATH = '/functions/v1/pentafabric-ingest';
const DEFAULT_PENTAFABRIC_INGEST_URL = `${SUPABASE_PROJECT_ORIGIN}${PENTAFABRIC_INGEST_PATH}`;
const EXPECTED_OIDC_RECEIPT_AUTHENTICATION = 'VERCEL_OIDC_RS256';
const EXPECTED_OIDC_WORKLOAD = Object.freeze({
  owner_id: 'team_v4xkGtBZSrZXnJtLEJhra5nd',
  project_id: 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
  environment: 'production',
});

class EvidenceSinkError extends Error {
  constructor(message, providerStatus = null) {
    super(message);
    this.name = 'EvidenceSinkError';
    this.providerStatus = providerStatus;
  }
}

function send(response, status, payload) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-PentaFabric-Version', '1.0.1');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  return response.status(status).json(payload);
}

function canonicalSupabaseOrigin(value) {
  const raw = String(value || '');
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new EvidenceSinkError('Supabase Penta sink origin is invalid');
  }
  const exact = raw === SUPABASE_PROJECT_ORIGIN || raw === `${SUPABASE_PROJECT_ORIGIN}/`;
  if (
    !exact || parsed.protocol !== 'https:' || parsed.origin !== SUPABASE_PROJECT_ORIGIN ||
    parsed.username || parsed.password || parsed.port || parsed.pathname !== '/' ||
    parsed.search || parsed.hash
  ) {
    throw new EvidenceSinkError('Supabase Penta sink origin is not the canonical CrownThrive project');
  }
  return SUPABASE_PROJECT_ORIGIN;
}

function canonicalPentafabricIngestUrl(value) {
  const raw = String(value || DEFAULT_PENTAFABRIC_INGEST_URL);
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new EvidenceSinkError('PentaFabric OIDC ingest URL is invalid');
  }
  if (
    raw !== DEFAULT_PENTAFABRIC_INGEST_URL || parsed.protocol !== 'https:' ||
    parsed.origin !== SUPABASE_PROJECT_ORIGIN || parsed.username || parsed.password ||
    parsed.port || parsed.pathname !== PENTAFABRIC_INGEST_PATH || parsed.search || parsed.hash
  ) {
    throw new EvidenceSinkError('PentaFabric OIDC ingest URL is not the canonical CrownThrive edge function');
  }
  return DEFAULT_PENTAFABRIC_INGEST_URL;
}

function evidenceRow(penta) {
  return {
    penta_id: penta.id,
    trace_id: penta.trace.trace_id,
    protocol: penta.mesh.fabric.protocol,
    lane: penta.mesh.fabric.lane,
    route: penta.mesh.fabric.route,
    chlom_intent_id: penta.mesh.chlom.intent_id,
    chlom_binding: penta.mesh.chlom.binding,
    event_contract: penta.mesh.contract,
    fabric_schema: penta.mesh.fabric.schema,
    integrity_algorithm: penta.integrity.algorithm,
    integrity_digest: penta.integrity.digest,
    build_sha: penta.integrity.build_sha,
    event: penta,
  };
}

function sinkConfiguration(oidcToken) {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRolePresent = Boolean(supabaseUrl && process.env.SUPABASE_SERVICE_ROLE_KEY);
  let serviceRoleConfigured = false;
  let oidcIngestConfigured = false;
  try {
    serviceRoleConfigured = Boolean(serviceRolePresent && canonicalSupabaseOrigin(supabaseUrl));
  } catch {
    serviceRoleConfigured = false;
  }
  try {
    oidcIngestConfigured = Boolean(canonicalPentafabricIngestUrl(process.env.PENTAFABRIC_INGEST_URL));
  } catch {
    oidcIngestConfigured = false;
  }
  return {
    oidc_token_present: Boolean(oidcToken),
    oidc_ingest_configuration_valid: oidcIngestConfigured,
    service_role_present: serviceRolePresent,
    service_role_configuration_valid: serviceRoleConfigured,
    configured: Boolean((oidcToken && oidcIngestConfigured) || serviceRoleConfigured),
  };
}

function evidenceSinkState(oidcToken, selfTest = null) {
  const config = sinkConfiguration(oidcToken);
  const verified = Boolean(
    selfTest?.status === 'PASS' &&
    selfTest?.provider_readback_verified === true &&
    selfTest?.persistence?.status === 'PERSISTED_READBACK_VERIFIED',
  );
  const oidcVerified = Boolean(
    verified &&
    selfTest?.persistence?.authentication === EXPECTED_OIDC_RECEIPT_AUTHENTICATION,
  );
  const oidcBound = config.oidc_token_present;
  const serviceRoleConfigured = config.service_role_configuration_valid;

  const configurationBoundary = {
    bound: oidcBound ? false : serviceRoleConfigured,
    primary_route: oidcBound ? 'VERCEL_OIDC' : 'SERVICE_ROLE_FALLBACK',
    service_role_fallback_available: serviceRoleConfigured,
  };
  if (!oidcBound && !serviceRoleConfigured) configurationBoundary.primary_route = 'UNBOUND';

  let mode = 'UNBOUND';
  if (verified) {
    mode = oidcVerified
      ? 'VERCEL_OIDC_EXACT_READBACK'
      : 'SERVICE_ROLE_EXACT_READBACK';
  } else if (oidcBound) {
    mode = config.oidc_ingest_configuration_valid
      ? 'VERCEL_OIDC_PRESENT_UNVERIFIED'
      : 'VERCEL_OIDC_INGEST_CONFIGURATION_HOLD';
  } else if (config.service_role_present) {
    mode = serviceRoleConfigured
      ? 'SERVICE_ROLE_CONFIGURED'
      : 'SERVICE_ROLE_CONFIGURATION_HOLD';
  }

  return {
    provider: 'supabase',
    ...configurationBoundary,
    bound: verified ? true : configurationBoundary.bound,
    verified,
    mode,
    ...config,
    oidc_token_verified: oidcVerified,
    verification_boundary: verified
      ? 'EXACT_PROVIDER_READBACK'
      : config.configured
        ? 'CONFIGURATION_ONLY'
        : 'UNBOUND',
    table: 'pentafabric_events',
    edge_ingest: 'pentafabric-ingest',
  };
}

function writeAuthorizationState(oidcToken, selfTest = null) {
  const writeToken = process.env.PENTAFABRIC_WRITE_TOKEN || '';
  const writeTokenReady = Buffer.byteLength(writeToken, 'utf8') >= 32;
  const workloadVerified = Boolean(
    selfTest?.status === 'PASS' &&
    selfTest?.provider_readback_verified === true,
  );
  return {
    required: true,
    bound: workloadVerified || writeTokenReady,
    mode: workloadVerified
      ? 'WORKLOAD_IDENTITY_EXACT_READBACK'
      : oidcToken
        ? 'WORKLOAD_IDENTITY_PRESENT_UNVERIFIED'
        : writeTokenReady
          ? 'DIRECT_WRITE_TOKEN_BOUND'
          : 'SECURE_DEFAULT_DENY',
    workload_identity: {
      present: Boolean(oidcToken),
      verified: workloadVerified,
      state: workloadVerified ? 'VERIFIED' : oidcToken ? 'PRESENT_UNVERIFIED' : 'UNAVAILABLE',
    },
    direct_external_write: {
      required_for_runtime: false,
      token_bound: writeTokenReady,
      state: writeTokenReady ? 'TOKEN_BOUND' : 'FAIL_CLOSED',
      posture: writeTokenReady ? 'EXPLICIT_CREDENTIAL' : 'SECURE_DEFAULT_DENY',
    },
  };
}

function bearerToken(request) {
  const authorization = requestHeader(request, 'authorization');
  if (!authorization) return null;
  const match = /^Bearer\s+(.+)$/i.exec(authorization.trim());
  return match?.[1] || null;
}

function constantTimeEqual(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string') return false;
  const leftBytes = Buffer.from(left, 'utf8');
  const rightBytes = Buffer.from(right, 'utf8');
  if (leftBytes.length !== rightBytes.length) return false;
  return timingSafeEqual(leftBytes, rightBytes);
}

function authorizeWrite(request) {
  const presented = bearerToken(request);
  const configuredValue = process.env.PENTAFABRIC_WRITE_TOKEN || '';
  const configuredToken = Buffer.byteLength(configuredValue, 'utf8') >= 32 ? configuredValue : null;
  if (!configuredToken) {
    return {
      authorized: false,
      status: 503,
      error: configuredValue ? 'write_authorization_binding_invalid' : 'direct_external_write_fail_closed',
    };
  }
  if (!presented) {
    return { authorized: false, status: 401, error: 'write_authorization_required' };
  }
  if (constantTimeEqual(presented, configuredToken)) {
    return { authorized: true, method: 'PENTAFABRIC_WRITE_TOKEN' };
  }
  return { authorized: false, status: 403, error: 'write_authorization_rejected' };
}

async function persistWithServiceRole(penta, supabaseUrl, serviceRoleKey) {
  const canonicalOrigin = canonicalSupabaseOrigin(supabaseUrl);
  const result = await fetch(`${canonicalOrigin}/rest/v1/pentafabric_events?on_conflict=penta_id`, {
    method: 'POST',
    redirect: 'error',
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
      'Content-Type': 'application/json',
      Prefer: 'resolution=ignore-duplicates,return=minimal',
    },
    body: JSON.stringify(evidenceRow(penta)),
  });
  if (!result.ok) {
    throw new EvidenceSinkError(`Supabase Penta sink rejected delivery (${result.status})`, result.status);
  }
  const readback = await fetch(
    `${canonicalOrigin}/rest/v1/pentafabric_events?penta_id=eq.${encodeURIComponent(penta.id)}&select=penta_id,trace_id,integrity_digest,build_sha,event,received_at&limit=1`,
    {
      method: 'GET',
      redirect: 'error',
      headers: {
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        Accept: 'application/json',
      },
    },
  );
  if (!readback.ok) throw new EvidenceSinkError(`Supabase Penta readback failed (${readback.status})`, readback.status);
  const rows = await readback.json();
  const stored = Array.isArray(rows) && rows.length === 1 ? rows[0] : null;
  const exact =
    stored?.penta_id === penta.id &&
    stored?.trace_id === penta.trace.trace_id &&
    stored?.integrity_digest === penta.integrity.digest &&
    stored?.build_sha === penta.integrity.build_sha &&
    canonicalPentaJson(stored?.event) === canonicalPentaJson(penta);
  if (!exact) throw new EvidenceSinkError('Supabase Penta exact readback mismatch');
  return {
    status: 'PERSISTED_READBACK_VERIFIED',
    sink: 'supabase',
    authentication: 'SERVICE_ROLE',
    idempotent_key: penta.id,
    signing_build_sha: penta.integrity.build_sha,
    exact_readback: true,
    persisted_at: stored?.received_at || null,
    verified_at: new Date().toISOString(),
  };
}

async function persistWithVercelOidc(penta, oidcToken) {
  const ingestUrl = canonicalPentafabricIngestUrl(process.env.PENTAFABRIC_INGEST_URL);
  const result = await fetch(ingestUrl, {
    method: 'POST',
    redirect: 'error',
    headers: {
      Authorization: `Bearer ${oidcToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ penta }),
  });
  const raw = await result.text();
  let receipt = null;
  if (raw) {
    try { receipt = JSON.parse(raw); } catch { receipt = null; }
  }
  if (!result.ok) {
    throw new EvidenceSinkError(`Supabase OIDC Penta sink rejected delivery (${result.status})`, result.status);
  }
  if (
    receipt?.status !== 'PERSISTED_READBACK_VERIFIED' ||
    receipt?.authentication !== EXPECTED_OIDC_RECEIPT_AUTHENTICATION ||
    receipt?.workload?.owner_id !== EXPECTED_OIDC_WORKLOAD.owner_id ||
    receipt?.workload?.project_id !== EXPECTED_OIDC_WORKLOAD.project_id ||
    receipt?.workload?.environment !== EXPECTED_OIDC_WORKLOAD.environment ||
    receipt?.penta_id !== penta.id ||
    receipt?.trace_id !== penta.trace.trace_id ||
    receipt?.integrity_digest !== penta.integrity.digest ||
    receipt?.signing_build_sha !== penta.integrity.build_sha ||
    receipt?.exact_readback !== true
  ) {
    throw new EvidenceSinkError('Supabase OIDC Penta sink did not return exact readback evidence', result.status);
  }
  return {
    status: 'PERSISTED_READBACK_VERIFIED',
    sink: 'supabase-edge',
    authentication: receipt.authentication,
    workload: {
      owner_id: receipt.workload.owner_id,
      project_id: receipt.workload.project_id,
      environment: receipt.workload.environment,
    },
    idempotent_key: penta.id,
    signing_build_sha: penta.integrity.build_sha,
    exact_readback: true,
    persisted_at: receipt.persisted_at || null,
    verified_at: receipt.verified_at || new Date().toISOString(),
    receipt,
  };
}

async function persistPenta(penta, oidcToken) {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (oidcToken) {
    return persistWithVercelOidc(penta, oidcToken);
  }
  if (supabaseUrl && serviceRoleKey) return persistWithServiceRole(penta, supabaseUrl, serviceRoleKey);
  return {
    status: 'SKIPPED_UNBOUND',
    sink: 'supabase',
    required_binding: 'SUPABASE_SERVICE_ROLE_KEY_OR_VERCEL_OIDC_CONTEXT',
  };
}

async function runSelfTest(state, oidcToken) {
  const probe = emitPenta({
    protocol: 'PentaFabricSelfTest',
    payload: { probe: true, build_sha: state.build_sha },
    source: 'urn:crownthrive:pentafabric:self-test',
    subject: 'pentafabric-self-test',
    route: 'vercel-self-test',
    corridor: 'runtime-assurance',
    lane: 'hot',
    ttl_seconds: 60,
    chlom_intent_id: 'chlom-intent-pentafabric-self-test-v1',
    chlom_policy_refs: ['ct.chlom.pentafabric.v1'],
    rights_scope: 'runtime-assurance-only',
  });
  verifyPenta(probe, { requireSignature: true });
  const persistence = await persistPenta(probe, oidcToken);
  if (persistence.status !== 'PERSISTED_READBACK_VERIFIED' || persistence.exact_readback !== true) {
    throw new EvidenceSinkError('PentaFabric provider self-test did not produce exact persisted readback');
  }
  return {
    status: 'PASS',
    penta_id: probe.id,
    trace_id: probe.trace.trace_id,
    assurance: probe.integrity.algorithm,
    chlom_binding: probe.mesh.chlom.binding,
    event_contract: probe.mesh.contract,
    fabric_schema: probe.mesh.fabric.schema,
    provider_readback_verified: true,
    persistence,
    verified_at: persistence.verified_at || new Date().toISOString(),
  };
}

function classifySelfTestFailure(error) {
  const message = String(error?.message || '');
  if (/signing secret is not bound/i.test(message)) {
    return { reason: 'HMAC_BINDING_UNAVAILABLE', detail: 'PentaFabric signing secret is not bound' };
  }
  if (/canonical CrownThrive edge function|ingest URL/i.test(message)) return { reason: 'OIDC_INGEST_CONFIGURATION_HOLD' };
  if (/canonical CrownThrive project|origin/i.test(message)) return { reason: 'SERVICE_ROLE_CONFIGURATION_HOLD' };
  if (/exact readback|persisted readback/i.test(message)) return { reason: 'PROVIDER_READBACK_NOT_VERIFIED' };
  return { reason: 'SELF_TEST_FAILED' };
}

export default async function handler(request, response) {
  const state = fabricState();
  const oidcToken = resolveVercelOidcToken(request);

  if (request.method === 'GET') {
    const selfTestRequested = requestQueryParam(request, 'selftest') === '1';
    if (!selfTestRequested) {
      const selfTest = { status: 'NOT_REQUESTED' };
      return send(response, 200, {
        schema: 'ct.penta.vercel.fabric.20260903.v2',
        service: 'crownthrive-os-control-plane',
        status: 'OPERATIONAL',
        fabric: state,
        accepts: 'crownthrive.penta.event.v1',
        emits: 'crownthrive.penta.event.v1',
        chlom_governed: true,
        evidence_sink: evidenceSinkState(oidcToken, selfTest),
        write_authorization: writeAuthorizationState(oidcToken, selfTest),
        self_test: selfTest,
        provider_readback_claimed: false,
        observed_at: new Date().toISOString(),
        pass_manufactured: false,
      });
    }

    try {
      const selfTest = await runSelfTest(state, oidcToken);
      return send(response, 200, {
        schema: 'ct.penta.vercel.fabric.20260903.v2',
        service: 'crownthrive-os-control-plane',
        status: 'OPERATIONAL',
        fabric: state,
        accepts: 'crownthrive.penta.event.v1',
        emits: 'crownthrive.penta.event.v1',
        chlom_governed: true,
        evidence_sink: evidenceSinkState(oidcToken, selfTest),
        write_authorization: writeAuthorizationState(oidcToken, selfTest),
        self_test: selfTest,
        provider_readback_claimed: true,
        observed_at: new Date().toISOString(),
        pass_manufactured: false,
      });
    } catch (error) {
      const failure = classifySelfTestFailure(error);
      return send(response, 503, {
        schema: 'ct.penta.vercel.fabric.20260903.v2',
        status: 'DEGRADED',
        error: 'pentafabric_self_test_failure',
        reason: failure.reason,
        ...(failure.detail ? { detail: failure.detail } : {}),
        fabric: state,
        evidence_sink: evidenceSinkState(oidcToken),
        write_authorization: writeAuthorizationState(oidcToken),
        self_test: { status: 'FAIL', reason: failure.reason, provider_readback_verified: false },
        provider_readback_claimed: false,
        pass_manufactured: false,
      });
    }
  }

  if (request.method !== 'POST') {
    response.setHeader('Allow', 'GET, POST');
    return send(response, 405, { status: 'REJECTED', error: 'method_not_allowed' });
  }

  const authorization = authorizeWrite(request);
  if (!authorization.authorized) {
    response.setHeader('WWW-Authenticate', 'Bearer realm="CrownThrive PentaFabric"');
    return send(response, authorization.status, {
      schema: 'ct.penta.error.v1',
      status: 'WRITE_GATED',
      error: authorization.error,
      service: 'crownthrive-os-control-plane',
      security_posture: 'FAIL_CLOSED',
      runtime_provider_path_affected: false,
      pass_manufactured: false,
    });
  }

  try {
    const rawLength = Number(request.headers['content-length'] || 0);
    if (rawLength > MAX_BODY_BYTES) return send(response, 413, { status: 'REJECTED', error: 'penta_payload_too_large' });
    const body = request.body && typeof request.body === 'object' ? request.body : {};
    const externallySupplied = Object.hasOwn(body, 'penta');
    const penta = externallySupplied
      ? verifyPenta(body.penta, { requireSignature: true })
      : emitPenta(body);
    verifyPenta(penta, { requireSignature: true });

    let persistence;
    try {
      persistence = await persistPenta(penta, oidcToken);
    } catch (error) {
      return send(response, 503, {
        schema: 'ct.penta.error.v1',
        status: 'DELIVERY_HOLD',
        error: 'pentafabric_evidence_sink_failure',
        service: 'crownthrive-os-control-plane',
        penta_id: penta.id,
        trace_id: penta.trace.trace_id,
        persistence: {
          status: 'FAILED',
          sink: 'supabase',
          upstream_status: error instanceof EvidenceSinkError ? error.providerStatus : null,
        },
        pass_manufactured: false,
      });
    }
    if (persistence.status === 'SKIPPED_UNBOUND') {
      return send(response, 503, {
        schema: 'ct.penta.error.v1',
        status: 'DELIVERY_HOLD',
        error: 'pentafabric_evidence_sink_unbound',
        service: 'crownthrive-os-control-plane',
        penta_id: penta.id,
        trace_id: penta.trace.trace_id,
        persistence,
        pass_manufactured: false,
      });
    }
    const receipt = {
      schema: 'ct.penta.receipt.20260903.v2',
      status: 'DELIVERED',
      penta_id: penta.id,
      trace_id: penta.trace.trace_id,
      protocol: penta.mesh.fabric.protocol,
      lane: penta.mesh.fabric.lane,
      route: penta.mesh.fabric.route,
      provider: 'vercel',
      chlom_binding: penta.mesh.chlom.binding,
      assurance: penta.integrity.algorithm,
      write_authorization: authorization.method,
      transport_assurance: persistence.authentication || 'UNBOUND',
      persistence,
      signing_build_sha: penta.integrity.build_sha,
      persisting_build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
      deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
      delivered_at: new Date().toISOString(),
    };
    return send(response, 202, { penta, receipt });
  } catch (error) {
    return send(response, 400, {
      status: 'REJECTED',
      error: 'pentafabric_contract_failure',
      detail: String(error?.message || error).slice(0, 240),
      fabric: state,
    });
  }
}
