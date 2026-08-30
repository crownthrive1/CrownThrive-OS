import { chlomBridgeState } from '../lib/chlom-fabric.js';

const CROWNTHRIVE_OS_PROJECT_ID = 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN';
const CROWNTHRIVE_OS_REPOSITORY = 'crownthrive1/CrownThrive-OS';

export default function handler(request, response) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    response.setHeader('Allow', 'GET, HEAD');
    response.setHeader('Cache-Control', 'no-store, max-age=0');
    response.setHeader('Content-Type', 'application/json; charset=utf-8');
    return response.status(405).json({
      schema: 'ct.penta.error.v1',
      service: 'crownthrive-os-control-plane',
      status: 'WRITE_GATED',
      pass_manufactured: false,
    });
  }

  const release =
    process.env.CROWNTHRIVE_OS_RELEASE ||
    (process.env.VERCEL_ENV === 'production' ? 'production' : 'candidate');
  const providerState = process.env.VERCEL_ENV
    ? `BOUND_${process.env.VERCEL_ENV.toUpperCase()}`
    : 'BINDING_REQUIRED';
  const chlomBridge = chlomBridgeState();
  const payload = {
    schema: 'ct.penta.vercel.health.20260827.v2',
    service: 'crownthrive-os-control-plane',
    status: 'OPERATIONAL',
    mode: process.env.PENTA_RG_MODE || 'FULL_AUTONOMOUS_GOVERNED',
    release,
    project_id: CROWNTHRIVE_OS_PROJECT_ID,
    repository: CROWNTHRIVE_OS_REPOSITORY,
    vercel_provider_state: providerState,
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || 'local-candidate',
    deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
    observed_at: new Date().toISOString(),
    provider_readback: Boolean(process.env.VERCEL_ENV),
    integrations: {
      chlom_chain_evidence: {
        status: chlomBridge.status,
        route: '/api/chlom',
        upstream: chlomBridge.base_url,
        upstream_api_token_bound: chlomBridge.upstream_api_token_bound,
        inbound_control_token_bound: chlomBridge.inbound_control_token_bound,
        chain_broadcast_allowed: false,
        private_key_custody: false,
      },
    },
    pass_manufactured: false,
  };
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-CHLOM-Bridge-State', chlomBridge.status);
  if (request.method === 'HEAD') {
    return response.status(200).end();
  }
  return response.status(200).json(payload);
}
