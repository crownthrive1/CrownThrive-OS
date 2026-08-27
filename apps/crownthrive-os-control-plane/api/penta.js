import { emitPenta, fabricState, verifyPenta } from '../lib/pentafabric.js';

const MAX_BODY_BYTES = 262144;

function send(response, status, payload) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-PentaFabric-Version', '1.0.0');
  return response.status(status).json(payload);
}

async function persistPenta(penta) {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey =
    process.env.SUPABASE_PUBLISHABLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const ingestToken = process.env.PENTAFABRIC_INGEST_TOKEN;
  if (!supabaseUrl || !publishableKey || !ingestToken) {
    return { status: 'SKIPPED_UNBOUND', sink: 'supabase' };
  }

  const result = await fetch(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/rpc/ingest_penta`, {
    method: 'POST',
    headers: {
      apikey: publishableKey,
      Authorization: `Bearer ${publishableKey}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
    },
    body: JSON.stringify({ p_token: ingestToken, p_event: penta }),
  });
  if (!result.ok) {
    const detail = await result.text();
    throw new Error(`Supabase Penta sink rejected delivery (${result.status}): ${detail.slice(0, 240)}`);
  }
  return { status: 'PERSISTED', sink: 'supabase', receipt: await result.json() };
}

export default async function handler(request, response) {
  const state = fabricState();
  if (request.method === 'GET') {
    return send(response, 200, {
      schema: 'ct.penta.vercel.fabric.20260827.v1',
      service: 'crownthrive-os-control-plane',
      status: 'OPERATIONAL',
      fabric: state,
      accepts: 'crownthrive.penta.event.v1',
      emits: 'crownthrive.penta.event.v1',
      chlom_governed: true,
      observed_at: new Date().toISOString(),
    });
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
    const persistence = await persistPenta(penta);
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
