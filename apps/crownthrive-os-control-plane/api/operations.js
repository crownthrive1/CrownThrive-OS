const CANONICAL_SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const DEFAULT_WINDOW_HOURS = 24;
const DEFAULT_LIMIT = 200;
const INTERVENTION_LIMIT = 500;

function setHeaders(response) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
}

function send(response, status, payload, head = false) {
  setHeaders(response);
  if (head) return response.status(status).end();
  return response.status(status).json(payload);
}

function canonicalSupabaseOrigin(value) {
  return value === CANONICAL_SUPABASE_ORIGIN || value === `${CANONICAL_SUPABASE_ORIGIN}/`
    ? CANONICAL_SUPABASE_ORIGIN
    : null;
}

function countBy(rows, key) {
  const counts = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    const value = String(row?.[key] || 'unknown').trim() || 'unknown';
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
}

function windowHours(request) {
  const raw = String(request.query?.window || request.query?.hours || DEFAULT_WINDOW_HOURS).toLowerCase();
  if (raw === '1h') return 1;
  if (raw === '7d') return 168;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? Math.min(Math.max(Math.trunc(parsed), 1), 168) : DEFAULT_WINDOW_HOURS;
}

async function rpc(origin, key, functionName, body) {
  const result = await fetch(`${origin}/rest/v1/rpc/${functionName}`, {
    method: 'POST',
    redirect: 'error',
    cache: 'no-store',
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!result.ok) {
    const detail = await result.text();
    const error = new Error(`${functionName} readback failed (${result.status})`);
    error.detail = detail.slice(0, 240);
    throw error;
  }
  return result.json();
}

async function readUnified(request) {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceRoleKey) {
    const error = new Error('SUPABASE_SERVICE_ROLE_BINDING_REQUIRED');
    error.code = 'UNBOUND';
    throw error;
  }
  const origin = canonicalSupabaseOrigin(supabaseUrl);
  if (!origin) throw new Error('SUPABASE_ORIGIN_NOT_CANONICAL');

  const live = await rpc(origin, serviceRoleKey, 'crownthrive_os_live_readback_v1', {
    p_window_hours: windowHours(request),
    p_limit: DEFAULT_LIMIT,
  });

  let interventionHistory = null;
  try {
    interventionHistory = await rpc(origin, serviceRoleKey, 'crownthrive_os_intervention_history_v1', {
      p_limit: INTERVENTION_LIMIT,
    });
  } catch {
    interventionHistory = {
      status: 'PARTIAL',
      rows: Array.isArray(live?.interventions) ? live.interventions : [],
      count: Array.isArray(live?.interventions) ? live.interventions.length : 0,
      fallback: 'window_scoped_live_readback',
    };
  }

  return { live, interventionHistory };
}

export default async function handler(request, response) {
  const head = request.method === 'HEAD';
  if (request.method !== 'GET' && !head) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, {
      schema: 'ct.penta.os.operations.v2',
      status: 'REJECTED',
      error: 'method_not_allowed',
      pass_manufactured: false,
    });
  }

  try {
    const { live, interventionHistory } = await readUnified(request);
    const ledger = Array.isArray(live?.ledger) ? live.ledger : [];
    const providers = Array.isArray(live?.providers) ? live.providers : [];
    const routes = Array.isArray(live?.routes) ? live.routes : [];
    const operations = Array.isArray(live?.operations) ? live.operations : [];
    const dail = Array.isArray(live?.dail) ? live.dail : [];
    const interventions = Array.isArray(interventionHistory?.rows)
      ? interventionHistory.rows
      : [];
    const stats = live?.stats || {};
    const totalObserved =
      Number(stats.penta_events_window || 0) +
      Number(stats.penta_super_runs_window || 0) +
      Number(stats.wake_requests_window || 0) +
      Number(stats.remediation_window || 0) +
      Number(stats.interventions_window || 0);

    const payload = {
      schema: 'ct.penta.os.operations.v2',
      service: 'crownthrive-os-control-plane',
      status: live?.status === 'OPERATIONAL' ? 'OPERATIONAL' : 'PARTIAL',
      window_hours: live?.window_hours || windowHours(request),
      window_start: live?.window_start || null,
      source: {
        provider: 'supabase',
        state: 'BOUND',
        mode: 'SERVER_ONLY_UNIFIED_RPC',
        rpc: 'crownthrive_os_live_readback_v1',
        intervention_rpc: interventionHistory?.status === 'OPERATIONAL'
          ? 'crownthrive_os_intervention_history_v1'
          : 'window_scoped_fallback',
        ledgers: [
          'public.pentafabric_events',
          'penta_runtime.penta_super_runs_v1',
          'pentatime.wake_requests_v1',
          'penta_runtime.remediation_execution_queue_v1',
          'chlom_runtime.dail_system_registry_v1',
          'chlom_runtime.dail_event_lanes_v1',
          'communications_evidence.lifecycle_events_v1',
          'pentamocracy.activation_receipts_v1',
          'public.crownthrive_os_interventions_v1',
        ],
        secret_material_exposed: false,
      },
      activity: {
        total_events: totalObserved,
        persisted_pentas: Number(stats.penta_events_window || 0),
        penta_super_runs: Number(stats.penta_super_runs_window || 0),
        wake_requests: Number(stats.wake_requests_window || 0),
        remediation_events: Number(stats.remediation_window || 0),
        intervention_events: Number(stats.interventions_window || 0),
        distribution_scope: 'unified_live_window',
        active_protocols: new Set(ledger.map((row) => row.protocol)).size,
        active_routes: new Set(ledger.map((row) => row.route)).size,
        active_lanes: new Set(ledger.map((row) => row.lane)).size,
        protocols: countBy(ledger, 'protocol'),
        routes: countBy(ledger, 'route'),
        lanes: countBy(ledger, 'lane'),
        recent: ledger,
      },
      stats,
      providers,
      routes,
      operations,
      interventions,
      intervention_history: {
        status: interventionHistory?.status || 'PARTIAL',
        count: Number(interventionHistory?.count || interventions.length),
        complete_to_limit: interventions.length < INTERVENTION_LIMIT,
        limit: INTERVENTION_LIMIT,
      },
      dail,
      instrumentation: {
        pentafabric_event_ledger: 'BOUND',
        penta_runtime: 'BOUND',
        pentatime: 'BOUND',
        remediation: 'BOUND',
        dail: 'BOUND',
        communications_evidence: 'BOUND',
        pentamocracy: 'BOUND',
        intervention_ledger: 'BOUND',
        provider_registry: 'BOUND',
        route_registry: 'BOUND',
        polling_mode: 'NEAR_REAL_TIME',
        unobserved_activity_claimed: false,
      },
      generated_at: live?.generated_at || null,
      observed_at: new Date().toISOString(),
      public_safe: true,
      pass_manufactured: false,
    };
    return send(response, 200, payload, head);
  } catch (error) {
    return send(response, 503, {
      schema: 'ct.penta.os.operations.v2',
      service: 'crownthrive-os-control-plane',
      status: 'DEGRADED',
      error: error?.code || 'operations_readback_failed',
      detail: String(error?.message || error).slice(0, 240),
      instrumentation: {
        unified_live_readback: 'READBACK_FAILED',
        unobserved_activity_claimed: false,
      },
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }
}
