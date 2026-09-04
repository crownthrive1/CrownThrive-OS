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
  const raw = String(value || '');
  const exact = raw === CANONICAL_SUPABASE_ORIGIN || raw === `${CANONICAL_SUPABASE_ORIGIN}/`;
  if (!exact) return null;
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }
  if (
    parsed.protocol !== 'https:' ||
    parsed.origin !== CANONICAL_SUPABASE_ORIGIN ||
    parsed.username ||
    parsed.password ||
    parsed.port ||
    parsed.pathname !== '/' ||
    parsed.search ||
    parsed.hash
  ) return null;
  return CANONICAL_SUPABASE_ORIGIN;
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
  return Number.isFinite(parsed)
    ? Math.min(Math.max(Math.trunc(parsed), 1), 168)
    : DEFAULT_WINDOW_HOURS;
}

function bindingState() {
  const suppliedUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!suppliedUrl || !serviceRoleKey) {
    return {
      state: 'UNBOUND',
      origin: null,
      serviceRoleKey: null,
    };
  }
  const origin = canonicalSupabaseOrigin(suppliedUrl);
  if (!origin) {
    return {
      state: 'CONFIGURATION_HOLD',
      origin: null,
      serviceRoleKey: null,
    };
  }
  return {
    state: 'BOUND',
    origin,
    serviceRoleKey,
  };
}

async function rpc(origin, key, functionName, body) {
  const target = new URL(`/rest/v1/rpc/${functionName}`, origin);
  const result = await fetch(target, {
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
    const error = new Error(`${functionName}_readback_failed`);
    error.code = 'UPSTREAM_READBACK_FAILED';
    throw error;
  }
  return result.json();
}

async function readUnified(request, binding) {
  const live = await rpc(binding.origin, binding.serviceRoleKey, 'crownthrive_os_live_readback_v1', {
    p_window_hours: windowHours(request),
    p_limit: DEFAULT_LIMIT,
  });

  let interventionHistory;
  try {
    interventionHistory = await rpc(
      binding.origin,
      binding.serviceRoleKey,
      'crownthrive_os_intervention_history_v1',
      { p_limit: INTERVENTION_LIMIT },
    );
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

function unboundPayload(request, binding) {
  return {
    schema: 'ct.penta.os.operations.v2',
    service: 'crownthrive-os-control-plane',
    status: 'PARTIAL',
    window_hours: windowHours(request),
    window_start: null,
    source: {
      provider: 'supabase',
      state: binding.state,
      mode: 'SERVER_ONLY_UNIFIED_RPC',
      secret_material_exposed: false,
    },
    activity: {
      total_events: 0,
      persisted_pentas: 0,
      penta_super_runs: 0,
      wake_requests: 0,
      remediation_events: 0,
      intervention_events: 0,
      distribution_scope: 'unobserved_until_server_binding',
      active_protocols: 0,
      active_routes: 0,
      active_lanes: 0,
      protocols: [],
      routes: [],
      lanes: [],
      recent: [],
    },
    stats: {},
    providers: [],
    routes: [],
    operations: [],
    interventions: [],
    intervention_history: {
      status: binding.state,
      count: 0,
      complete_to_limit: false,
      limit: INTERVENTION_LIMIT,
    },
    dail: [],
    instrumentation: {
      unified_live_readback: binding.state,
      vercel_provider_readback: 'UNBOUND',
      pentafabric_event_ledger: 'UNBOUND',
      penta_runtime: 'UNBOUND',
      pentatime: 'UNBOUND',
      remediation: 'UNBOUND',
      dail: 'UNBOUND',
      communications_evidence: 'UNBOUND',
      pentamocracy: 'UNBOUND',
      intervention_ledger: 'UNBOUND',
      provider_registry: 'UNBOUND',
      route_registry: 'UNBOUND',
      polling_mode: 'NEAR_REAL_TIME',
      unobserved_activity_claimed: false,
    },
    generated_at: null,
    observed_at: new Date().toISOString(),
    public_safe: true,
    pass_manufactured: false,
  };
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

  const binding = bindingState();
  if (binding.state === 'UNBOUND') {
    return send(response, 200, unboundPayload(request, binding), head);
  }
  if (binding.state !== 'BOUND') {
    return send(response, 503, {
      schema: 'ct.penta.os.operations.v2',
      service: 'crownthrive-os-control-plane',
      status: 'DEGRADED',
      error: 'operations_readback_failed',
      source: {
        provider: 'supabase',
        state: 'CONFIGURATION_HOLD',
        mode: 'SERVER_ONLY_UNIFIED_RPC',
        secret_material_exposed: false,
      },
      instrumentation: {
        unified_live_readback: 'CONFIGURATION_HOLD',
        vercel_provider_readback: 'UNBOUND',
        unobserved_activity_claimed: false,
      },
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }

  try {
    const { live, interventionHistory } = await readUnified(request, binding);
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
        unified_live_readback: 'BOUND',
        vercel_provider_readback: 'SEPARATE_PROVIDER_ENDPOINT',
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
  } catch {
    return send(response, 503, {
      schema: 'ct.penta.os.operations.v2',
      service: 'crownthrive-os-control-plane',
      status: 'DEGRADED',
      error: 'operations_readback_failed',
      source: {
        provider: 'supabase',
        state: 'BOUND',
        mode: 'SERVER_ONLY_UNIFIED_RPC',
        secret_material_exposed: false,
      },
      instrumentation: {
        unified_live_readback: 'READBACK_FAILED',
        vercel_provider_readback: 'UNOBSERVED',
        unobserved_activity_claimed: false,
      },
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }
}
