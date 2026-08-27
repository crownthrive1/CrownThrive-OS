export default function handler(_request, response) {
  const release = process.env.CROWNTHRIVE_OS_RELEASE || (process.env.VERCEL_ENV === 'production' ? 'production' : 'candidate');
  const providerState = process.env.VERCEL_ENV ? 'BOUND_' + process.env.VERCEL_ENV.toUpperCase() : 'BINDING_REQUIRED';
  const payload = {
    schema: 'ct.penta.vercel.health.20260827.v1',
    service: 'crownthrive-os-control-plane',
    status: 'OPERATIONAL',
    mode: process.env.PENTA_RG_MODE || 'FULL_AUTONOMOUS_GOVERNED',
    release,
    repository: process.env.CROWNTHRIVE_OS_REPOSITORY || 'crownthrive1/CrownThrive-OS',
    vercel_provider_state: providerState,
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || 'local-candidate',
    deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
    observed_at: new Date().toISOString(),
    provider_readback: Boolean(process.env.VERCEL_ENV),
    pass_manufactured: false
  };
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.status(200).json(payload);
}
