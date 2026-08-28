const WINDOW_HOURS = 24;
const SAMPLE_LIMIT = 250;
const RECENT_LIMIT = 30;

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

function countBy(rows, key) {
  const counts = new Map();
  for (const row of rows) {
    const value = typeof row?.[key] === 'string' && row[key].trim()
      ? row[key].trim()
      : 'unknown';
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
}

function parseExactCount(contentRange, fallback) {
  const match = /\/(\d+)$/.exec(String(contentRange || ''));
  return match ? Number(match[1]) : fallback;
}

function publicRow(row) {
  return {
    penta_id: row.penta_id || null,
    trace_id: row.trace_id || null,
    protocol: row.protocol || 'unknown',
    lane: row.lane || 'unknown',
    route: row.route || 'unknown',
    chlom_binding: row.chlom_binding || null,
    build_sha: row.build_sha || null,
    received_at: row.received_at || null,
  };
}

async function readLedger() {
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceRoleKey) {
    return {
      status: 'UNBOUND',
      reason: 'SUPABASE_SERVICE_ROLE_BINDING_REQUIRED',
      rows: [],
      total: 0,
      windowStart: new Date(Date.now() - WINDOW_HOURS * 60 * 60 * 1000).toISOString(),
    };
  }

  const windowStart = new Date(Date.now() - WINDOW_HOURS * 60 * 60 * 1000).toISOString();
  const url = new URL(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/pentafabric_events`);
  url.searchParams.set(
    'select',
    'penta_id,trace_id,protocol,lane,route,chlom_binding,build_sha,received_at',
  );
  url.searchParams.set('received_at', `gte.${windowStart}`);
  url.searchParams.set('order', 'received_at.desc');
  url.searchParams.set('limit', String(SAMPLE_LIMIT));

  const result = await fetch(url, {
    method: 'GET',
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
      Accept: 'application/json',
      Prefer: 'count=exact',
      Range: `0-${SAMPLE_LIMIT - 1}`,
      'Range-Unit': 'items',
    },
    cache: 'no-store',
  });

  if (!result.ok) {
    const detail = await result.text();
    throw new Error(`Pentafabric ledger read failed (${result.status}): ${detail.slice(0, 180)}`);
  }

  const rows = await result.json();
  return {
    status: 'BOUND',
    rows: Array.isArray(rows) ? rows : [],
    total: parseExactCount(result.headers.get('content-range'), Array.isArray(rows) ? rows.length : 0),
    windowStart,
  };
}

export default async function handler(request, response) {
  const head = request.method === 'HEAD';
  if (request.method !== 'GET' && !head) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, {
      schema: 'ct.penta.os.operations.v1',
      status: 'REJECTED',
      error: 'method_not_allowed',
      pass_manufactured: false,
    });
  }

  try {
    const ledger = await readLedger();
    const rows = ledger.rows.map(publicRow);
    const sampled = ledger.total > rows.length;
    const payload = {
      schema: 'ct.penta.os.operations.v1',
      service: 'crownthrive-os-control-plane',
      status: ledger.status === 'BOUND' ? 'OPERATIONAL' : 'PARTIAL',
      window_hours: WINDOW_HOURS,
      source: {
        provider: 'supabase',
        table: 'pentafabric_events',
        state: ledger.status,
        mode: ledger.status === 'BOUND' ? 'SERVER_SIDE_SERVICE_ROLE' : 'UNBOUND',
        secret_material_exposed: false,
      },
      activity: {
        window_start: ledger.windowStart,
        total_events: ledger.total,
        sampled_events: rows.length,
        distribution_scope: sampled ? `latest_${rows.length}` : 'full_window',
        active_protocols: new Set(rows.map((row) => row.protocol)).size,
        active_routes: new Set(rows.map((row) => row.route)).size,
        active_lanes: new Set(rows.map((row) => row.lane)).size,
        protocols: countBy(rows, 'protocol'),
        routes: countBy(rows, 'route'),
        lanes: countBy(rows, 'lane'),
        recent: rows.slice(0, RECENT_LIMIT),
      },
      instrumentation: {
        pentafabric_event_ledger: ledger.status,
        vercel_provider_readback: 'BOUND_VIA_FABRIC',
        vercel_runtime_management: 'PROVIDER_CONNECTOR_ONLY',
        vercel_agent_runs: 'NOT_INSTRUMENTED',
        unobserved_activity_claimed: false,
      },
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    };
    return send(response, 200, payload, head);
  } catch (error) {
    return send(response, 503, {
      schema: 'ct.penta.os.operations.v1',
      service: 'crownthrive-os-control-plane',
      status: 'DEGRADED',
      error: 'operations_readback_failed',
      detail: String(error?.message || error),
      instrumentation: {
        pentafabric_event_ledger: 'READBACK_FAILED',
        unobserved_activity_claimed: false,
      },
      observed_at: new Date().toISOString(),
      pass_manufactured: false,
    }, head);
  }
}
