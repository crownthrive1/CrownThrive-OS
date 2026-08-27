import { getVercelOidcToken } from '@vercel/oidc';
import { emitPenta, fabricState, verifyPenta } from '../lib/pentafabric.js';

const MAX_BODY_BYTES = 262144;
const VERCEL_TEAM_ID = 'team_v4xkGtBZSrZXnJtLEJhra5nd';
const VERCEL_PROJECT_ID = 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN';
const DEFAULT_PENTAFABRIC_INGEST_URL =
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentafabric-ingest';

function send(response, status, payload) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-PentaFabric-Version', '1.0.0');
  return response.status(status).json(payload);
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
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
    event: penta,
  };
}

async function resolveVercelOidcToken() {
  try {
    const token = await getVercelOidcToken({
      project: VERCEL_PROJECT_ID,
      team: VERCEL_TEAM_ID,
    });
    return typeof token === 'string' && token.length > 0 ? token : null;
  } catch {
    return null;
  }
}

function evidenceSinkState(oidcToken) {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleBound = Boolean(supabaseUrl && process.env.SUPABASE_SERVICE_ROLE_KEY);
  const oidcBound = Boolean(oidcToken);
  return {
    provider: 'supabase',
    bound: serviceRoleBound || oidcBound,
    mode: serviceRoleBound ? 'SERVICE_ROLE' : oidcBound ? 'VERCEL_OIDC_RS256' : 'UNBOUND',
    table: 'pentafabric_events',
    edge_ingest: 'pentafabric-ingest',
  };
}

async function persistWithServiceRole(penta, supabaseUrl, serviceRoleKey) {
  const result = await fetch(
    `${supabaseUrl.replace(/\/$/, '')}/rest/v1/pentafabric_events?on_conflict=penta_id`,
    {
      method: 'POST',
      headers: {
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        'Content-Type': 'application/json',
        Prefer: 'resolution=ignore-duplicates,return=minimal',
      },
      body: JSON.stringify(evidenceRow(penta)),
    },
  );
  if (!result.ok) {
    const detail = await result.text();
    throw new Error(`Supabase Penta sink rejected delivery (${result.status}): ${detail.slice(0, 240)}`);
  }
  return {
    status: 'PERSISTED',
    sink: 'supabase',
    authentication: 'SERVICE_ROLE',
    idempotent_key: penta.id,
  };
}

async function persistWithVercelOidc(penta, oidcToken) {
  const ingestUrl = process.env.PENTAFABRIC_INGEST_URL || DEFAULT_PENTAFABRIC_INGEST_URL;
  const result = await fetch(ingestUrl, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${oidcToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ penta }),
  });
  const raw = await result.text();
  let receipt = null;
  if (raw) {
    try {
      receipt = JSON.parse(raw);
    } catch {
      receipt = { raw: raw.slice(0, 240) };
    }
  }
  if (!result.ok) {
    const detail = receipt?.detail || receipt?.error || raw || 'unknown edge rejection';
    throw new Error(`Supabase OIDC Penta sink rejected delivery (${result.status}): ${String(detail).slice(0, 240)}`);
  }
  return {
    status: 'PERSISTED',
    sink: 'supabase-edge',
    authentication: 'VERCEL_OIDC_RS256',
    idempotent_key: penta.id,
    receipt,
  };
}

async function persistPenta(penta, oidcToken) {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (supabaseUrl && serviceRoleKey) {
    return persistWithServiceRole(penta, supabaseUrl, serviceRoleKey);
  }

  if (oidcToken) {
    return persistWithVercelOidc(penta, oidcToken);
  }

  return {
    status: 'SKIPPED_UNBOUND',
    sink: 'supabase',
    required_binding: 'SUPABASE_SERVICE_ROLE_KEY_OR_VERCEL_OIDC_CONTEXT',
  };
}

function runSelfTest(state) {
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
  verifyPenta(probe);
  return {
    status: 'PASS',
    penta_id: probe.id,
    trace_id: probe.trace.trace_id,
    assurance: probe.integrity.algorithm,
    chlom_binding: probe.mesh.chlom.binding,
    event_contract: probe.mesh.contract,
    fabric_schema: probe.mesh.fabric.schema,
  };
}

export default async function handler(request, response) {
  const state = fabricState();
  const oidcToken = await resolveVercelOidcToken();
  if (request.method === 'GET') {
    try {
      const selfTestRequested = String(request.query?.selftest || '') === '1';
      return send(response, 200, {
        schema: 'ct.penta.vercel.fabric.20260827.v1',
        service: 'crownthrive-os-control-plane',
        status: 'OPERATIONAL',
        fabric: state,
        accepts: 'crownthrive.penta.event.v1',
        emits: 'crownthrive.penta.event.v1',
        chlom_governed: true,
        evidence_sink: evidenceSinkState(oidcToken),
        self_test: selfTestRequested ? runSelfTest(state) : { status: 'NOT_REQUESTED' },
        observed_at: new Date().toISOString(),
      });
    } catch (error) {
      return send(response, 503, {
        schema: 'ct.penta.vercel.fabric.20260827.v1',
        status: 'DEGRADED',
        error: 'pentafabric_self_test_failure',
        detail: String(error?.message || error),
        fabric: state,
      });
    }
  }
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'GET, POST');
    return send(response, 405, { status: 'REJECTED', error: 'method_not_allowed' });
  }

  try {
    const rawLength = Number(request.headers['content-length'] || 0);
    if (rawLength > MAX_BODY_BYTES) {
      return send(response, 413, { status: 'REJECTED', error: 'penta_payload_too_large' });
    }
    const body = request.body && typeof request.body === 'object' ? request.body : {};
    const penta = body.penta ? verifyPenta(body.penta) : emitPenta(body);
    verifyPenta(penta);
    const persistence = await persistPenta(penta, oidcToken);
    const receipt = {
      schema: 'ct.penta.receipt.20260827.v1',
      status: 'DELIVERED',
      penta_id: penta.id,
      trace_id: penta.trace.trace_id,
      protocol: penta.mesh.fabric.protocol,
      lane: penta.mesh.fabric.lane,
      route: penta.mesh.fabric.route,
      provider: 'vercel',
      chlom_binding: penta.mesh.chlom.binding,
      assurance: penta.integrity.algorithm,
      transport_assurance: persistence.authentication || 'UNBOUND',
      persistence,
      build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
      deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
      delivered_at: new Date().toISOString(),
    };
    return send(response, 202, { penta, receipt });
  } catch (error) {
    return send(response, 400, {
      status: 'REJECTED',
      error: 'pentafabric_contract_failure',
      detail: String(error?.message || error),
      fabric: state,
    });
  }
}
