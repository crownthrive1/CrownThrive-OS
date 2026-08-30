import { collectVercelFabric } from '../lib/vercel-fabric.js';
import { hasVercelOidcToken } from '../lib/vercel-oidc.js';

function send(response, status, payload) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader(
    'Referrer-Policy',
    'strict-origin-when-cross-origin',
  );
  if (payload?.evidence?.digest) {
    response.setHeader(
      'X-PentaFabric-Receipt',
      payload.evidence.digest,
    );
  }
  response.setHeader(
    'X-PentaFabric-State',
    payload?.status || 'UNKNOWN',
  );
  response.setHeader(
    'X-PentaFabric-Evidence-Sink',
    payload?.evidence?.sink_bound ? 'BOUND' : 'GATED',
  );
  return response.status(status).json(payload);
}

export default async function handler(request, response) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, {
      schema: 'ct.penta.error.v1',
      status: 'WRITE_GATED',
      service: 'crownthrive-vercel-execution-fabric',
      pass_manufactured: false,
    });
  }

  try {
    const fabric = await collectVercelFabric({
      oidcTokenPresent: hasVercelOidcToken(request),
    });
    return send(
      response,
      fabric.status === 'OPERATIONAL' ? 200 : 503,
      fabric,
    );
  } catch (error) {
    return send(response, 503, {
      schema: 'ct.penta.vercel.execution-fabric.20260827.v1',
      service: 'crownthrive-vercel-execution-fabric',
      status: 'DEGRADED',
      error: 'fabric_collection_failure',
      detail: String(error?.message || error).slice(0, 240),
      provider_readback: false,
      pass_manufactured: false,
      observed_at: new Date().toISOString(),
    });
  }
}
