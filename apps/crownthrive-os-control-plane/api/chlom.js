import {
  callChlomBridge,
  chlomBridgeState,
  fetchChlomHealth,
  normalizeChlomBridgeError,
  parseBridgeBody,
  requireControlAuthorization,
  validateBridgeOrigin,
} from '../lib/chlom-fabric.js';

function setHeaders(response, payload = null) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  response.setHeader('X-CHLOM-Bridge-State', payload?.bridge?.status || payload?.status || 'UNKNOWN');
  if (payload?.receipt?.bridge_digest) {
    response.setHeader('X-PentaFabric-Receipt', payload.receipt.bridge_digest);
  }
}

function send(response, status, payload) {
  setHeaders(response, payload);
  return response.status(status).json(payload);
}

export default async function handler(request, response) {
  if (request.method === 'GET' || request.method === 'HEAD') {
    try {
      const payload = await fetchChlomHealth();
      if (request.method === 'HEAD') {
        setHeaders(response, payload);
        return response.status(payload.status === 'OPERATIONAL' ? 200 : 503).end();
      }
      return send(response, payload.status === 'OPERATIONAL' ? 200 : 503, payload);
    } catch (error) {
      const normalized = normalizeChlomBridgeError(error);
      const payload = {
        schema: 'ct.penta.chlom.health-bridge.v1',
        status: 'DEGRADED',
        error: {
          code: normalized.code,
          message: normalized.message,
          details: normalized.details,
        },
        bridge: chlomBridgeState(),
        observed_at: new Date().toISOString(),
        pass_manufactured: false,
      };
      if (request.method === 'HEAD') {
        setHeaders(response, payload);
        return response.status(503).end();
      }
      return send(response, 503, payload);
    }
  }

  if (request.method !== 'POST') {
    response.setHeader('Allow', 'GET, HEAD, POST');
    return send(response, 405, {
      schema: 'ct.penta.error.v1',
      status: 'REJECTED',
      error: {
        code: 'METHOD_NOT_ALLOWED',
        message: 'Only GET, HEAD, and POST are supported.',
      },
      pass_manufactured: false,
    });
  }

  try {
    validateBridgeOrigin(request);
    requireControlAuthorization(request);
    const body = parseBridgeBody(request);
    const action = typeof body.action === 'string' ? body.action : '';
    const result = await callChlomBridge(action, body.input || {});
    return send(response, 200, {
      schema: 'ct.penta.chlom.bridge-response.v1',
      status: 'DELIVERED',
      action,
      ...result,
      pass_manufactured: false,
    });
  } catch (error) {
    const normalized = normalizeChlomBridgeError(error);
    return send(response, normalized.status, {
      schema: 'ct.penta.chlom.bridge-response.v1',
      status: 'REJECTED',
      error: {
        code: normalized.code,
        message: normalized.message,
        details: normalized.details,
      },
      bridge: chlomBridgeState(),
      pass_manufactured: false,
    });
  }
}
