const CANONICAL_SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const DEFAULT_EVENT_LIMIT = 12;
const MIN_EVENT_LIMIT = 3;
const MAX_EVENT_LIMIT = 25;

function setHeaders(response, payload = null) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
  response.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');
  response.setHeader('X-CrownThrive-Command-State', payload?.status || 'UNKNOWN');
}

function send(response, status, payload, head = false) {
  setHeaders(response, payload);
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

function bindingState() {
  const suppliedUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!suppliedUrl || !serviceRoleKey) {
    return { state: 'UNBOUND', origin: null, serviceRoleKey: null };
  }
  const origin = canonicalSupabaseOrigin(suppliedUrl);
  if (!origin) {
    return { state: 'CONFIGURATION_HOLD', origin: null, serviceRoleKey: null };
  }
  return { state: 'BOUND', origin, serviceRoleKey };
}

function eventLimit(request) {
  const raw = Number(request.query?.limit ?? DEFAULT_EVENT_LIMIT);
  if (!Number.isFinite(raw)) return DEFAULT_EVENT_LIMIT;
  return Math.min(Math.max(Math.trunc(raw), MIN_EVENT_LIMIT), MAX_EVENT_LIMIT);
}

async function readProjection(binding, limit) {
  const target = new URL('/rest/v1/rpc/crownthrive_command_status_v1', binding.origin);
  const upstream = await fetch(target, {
    method: 'POST',
    redirect: 'error',
    cache: 'no-store',
    headers: {
      apikey: binding.serviceRoleKey,
      Authorization: `Bearer ${binding.serviceRoleKey}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ p_event_limit: limit }),
  });

  if (!upstream.ok) {
    const error = new Error('command_projection_readback_failed');
    error.code = 'UPSTREAM_READBACK_FAILED';
    error.status = upstream.status;
    throw error;
  }

  const result = await upstream.json();
  if (Array.isArray(result)) return result[0] || null;
  return result;
}

function unboundPayload(binding, limit) {
  return {
    schema: 'ct.crownthrive.command-api.v1',
    service: 'crownthrive-os-control-plane',
    status: 'PARTIAL',
    source: {
      provider: 'supabase',
      state: binding.state,
      mode: 'SERVER_ONLY_AGGREGATE_RPC',
      secret_material_exposed: false,
    },
    wallet: null,
    dail: {
      assurance: null,
      primary_systems: [],
      supporting_systems: [],
      lanes: [],
      event_limit: limit,
    },
    privacy: {
      public_safe: true,
      wallet_identifiers_exposed: false,
      balances_exposed: false,
      actors_exposed: false,
      payloads_exposed: false,
      raw_private_evidence_public: false,
      hashes_truncated: true,
    },
    controls: {
      read_only_projection: true,
      economic_mutations_exposed: false,
      external_money_movement_exposed: false,
      credential_material_exposed: false,
      authenticated_control_plane_separate: true,
    },
    observed_at: new Date().toISOString(),
    pass_manufactured: false,
  };
}

export default async function handler(request, response) {
  const head = request.method === 'HEAD';
  if (request.method !== 'GET' && !head) {
    response.setHeader('Allow', 'GET, HEAD');
    return send(response, 405, {
      schema: 'ct.crownthrive.command-api.v1',
      status: 'REJECTED',
      error: 'method_not_allowed',
      pass_manufactured: false,
    });
  }

  const limit = eventLimit(request);
  const binding = bindingState();
  if (binding.state === 'UNBOUND') {
    return send(response, 200, unboundPayload(binding, limit), head);
  }
  if (binding.state !== 'BOUND') {
    return send(response, 503, {
      ...unboundPayload(binding, limit),
      status: 'DEGRADED',
      error: 'command_projection_configuration_hold',
    }, head);
  }

  try {
    const projection = await readProjection(binding, limit);
    if (!projection || typeof projection !== 'object') {
      throw new Error('command_projection_invalid_response');
    }

    const status = String(projection.status || 'PARTIAL').toUpperCase();
    const payload = {
      ...projection,
      schema: 'ct.crownthrive.command-api.v1',
      upstream_schema: projection.schema || null,
      source: {
        provider: 'supabase',
        state: 'BOUND',
        mode: 'SERVER_ONLY_AGGREGATE_RPC',
        secret_material_exposed: false,
      },
      event_limit: limit,
      pass_manufactured: false,
    };
    return send(response, status === 'DEGRADED' ? 503 : 200, payload, head);
  } catch {
    return send(response, 503, {
      ...unboundPayload(binding, limit),
      status: 'DEGRADED',
      source: {
        provider: 'supabase',
        state: 'READBACK_FAILED',
        mode: 'SERVER_ONLY_AGGREGATE_RPC',
        secret_material_exposed: false,
      },
      error: 'command_projection_readback_failed',
    }, head);
  }
}
