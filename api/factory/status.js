const DRIVE_RECEIPT = {
  state: 'PASS_PROVIDER_READBACK_VERIFIED',
  provider: 'google_drive',
  spreadsheet_id: '1NH2yk1N6qK49zgcBDTbst08Djvh3ypkbHJN_YRyHQPg',
  evidence_id: 'CT-SF-EV-009',
  observed_at: '2026-09-02T22:05:00Z'
};
const FALLBACK = {
  schema_version: '1.0.0', release_version: '1.0.1', factory_id: 'ct.factory.skills.v1',
  status: 'SOURCE_DEPLOYED_RUNTIME_STATE_PENDING',
  hourly_clock: 'GITHUB_ACTIONS_HOURLY',
  registry: { skills: 59, families: 7, bundles: 9 },
  provider_state: {
    github_workflow: 'SOURCE_REGISTERED_AWAITING_WORKFLOW_READBACK',
    vercel_command_center: 'PASS_VERCEL_ROUTE_READBACK',
    drive_master_ledger: DRIVE_RECEIPT.state,
    live_commerce: 'HOLD_PROVIDER_BINDING'
  },
  provider_receipts: { drive_master_ledger: DRIVE_RECEIPT },
  truth_boundary: 'This route proves the Vercel control surface is serving committed source. Runtime-clock and commerce states still require their own provider readback.'
};
const RAW_STATE = 'https://raw.githubusercontent.com/crownthrive1/CrownThrive-OS/automation/skills-factory-state/software-factory-v5/generated/current-status.json';
const withRouteReadback = (state) => ({
  ...state,
  provider_state: { ...(state.provider_state || {}), vercel_command_center: 'PASS_VERCEL_ROUTE_READBACK' },
  provider_receipts: {
    ...(state.provider_receipts || {}),
    drive_master_ledger: state.provider_receipts?.drive_master_ledger || DRIVE_RECEIPT,
    vercel_command_center: {
      state: 'PASS_VERCEL_ROUTE_READBACK',
      commit_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
      deployment_url: process.env.VERCEL_URL || null,
      region: process.env.VERCEL_REGION || null,
      observed_at: new Date().toISOString()
    }
  },
  source: state.source,
  observed_at: new Date().toISOString()
});
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  if (req.method !== 'GET') { res.setHeader('Allow','GET'); return res.status(405).json({error:'METHOD_NOT_ALLOWED'}); }
  try {
    const response = await fetch(RAW_STATE, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(3500) });
    if (!response.ok) throw new Error(`state ${response.status}`);
    const state = await response.json();
    return res.status(200).json(withRouteReadback({ ...state, source: 'automation/skills-factory-state' }));
  } catch (error) {
    return res.status(200).json(withRouteReadback({ ...FALLBACK, source: 'committed-fallback', runtime_state_error: String(error?.message || error) }));
  }
}
