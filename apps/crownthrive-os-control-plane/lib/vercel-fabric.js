import { createHash } from 'node:crypto';

export const VERCEL_TEAM_ID = 'team_v4xkGtBZSrZXnJtLEJhra5nd';
const SUPABASE_PROJECT_ORIGIN =
  'https://tzajnzshmtzjenqulehq.supabase.co';
const PENTAFABRIC_INGEST_PATH = '/functions/v1/pentafabric-ingest';
const DEFAULT_PENTAFABRIC_INGEST_URL =
  `${SUPABASE_PROJECT_ORIGIN}${PENTAFABRIC_INGEST_PATH}`;

export const PROJECT_BINDINGS = Object.freeze([
  {
    key: 'crownthrive_os',
    service: 'crownthrive-os-control-plane',
    project_id: 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
    repository: 'crownthrive1/CrownThrive-OS',
    health_url: null,
    visibility: 'public',
    required: true,
    lanes: ['public_experience', 'platform_api', 'control_plane'],
  },
  {
    key: 'private_penta_os',
    service: 'private-penta-os',
    project_id: 'prj_bokKbkKjxSq4jKYRtBjxhwEE4xbS',
    repository: 'crownthrive1/PRIVATE-PentaOS',
    health_url: 'https://private-penta-os.vercel.app/health',
    visibility: 'private',
    required: true,
    lanes: ['control_plane'],
  },
  {
    key: 'private_penta_execution',
    service: 'private-penta-execution',
    project_id: 'prj_d1uyuhNZHXfANgZv9zTEiaIlcZer',
    repository: 'crownthrive1/PRIVATE-PentaExecution',
    health_url: 'https://private-penta-execution.vercel.app/health',
    visibility: 'private',
    required: true,
    lanes: ['platform_api', 'control_plane'],
  },
  {
    key: 'chlom_protocol',
    service: 'chlom-protocol',
    project_id: 'prj_HewLgMjUiVBNCl0FADFbSggSp2QN',
    repository: 'crownthrive1/chlom-protocol',
    health_url: 'https://chlom-protocol.vercel.app/health',
    visibility: 'public',
    required: true,
    lanes: ['platform_api', 'control_plane'],
  },
]);

export const FABRIC_LANES = Object.freeze([
  {
    id: 'public_experience',
    name: 'Public Experience',
    function:
      'Production UI, public-safe operating status, and future CrownThrive experience deployments.',
    current_projects: ['prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN'],
  },
  {
    id: 'platform_api',
    name: 'Platform / API',
    function:
      'Health, Penta transport, provider readback, MCP, integration, and bounded execution endpoints.',
    current_projects: [
      'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
      'prj_d1uyuhNZHXfANgZv9zTEiaIlcZer',
      'prj_HewLgMjUiVBNCl0FADFbSggSp2QN',
    ],
  },
  {
    id: 'control_plane',
    name: 'Control Plane',
    function:
      'PentaRG, PentaVercel, PentaOS, PentaExecution, CHLOM authority, release evidence, and recovery.',
    current_projects: PROJECT_BINDINGS.map((project) => project.project_id),
  },
]);

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map((entry) => stableStringify(entry)).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null);
}

function manufacturedPassState(...values) {
  if (values.some((value) => value === true)) return true;
  if (values.some((value) => value === false)) return false;
  return null;
}

function canonicalSupabaseOrigin(value) {
  const raw = String(value || '');
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return false;
  }
  return (
    (raw === SUPABASE_PROJECT_ORIGIN || raw === `${SUPABASE_PROJECT_ORIGIN}/`) &&
    parsed.protocol === 'https:' &&
    parsed.origin === SUPABASE_PROJECT_ORIGIN &&
    !parsed.username &&
    !parsed.password &&
    !parsed.port &&
    parsed.pathname === '/' &&
    !parsed.search &&
    !parsed.hash
  );
}

function canonicalPentafabricIngest(value) {
  const raw = String(value || DEFAULT_PENTAFABRIC_INGEST_URL);
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return false;
  }
  return (
    raw === DEFAULT_PENTAFABRIC_INGEST_URL &&
    parsed.protocol === 'https:' &&
    parsed.origin === SUPABASE_PROJECT_ORIGIN &&
    !parsed.username &&
    !parsed.password &&
    !parsed.port &&
    parsed.pathname === PENTAFABRIC_INGEST_PATH &&
    !parsed.search &&
    !parsed.hash
  );
}

export function supabaseEvidenceBindingState({ oidcTokenPresent = false } = {}) {
  const origin =
    process.env.SUPABASE_URL ||
    process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRolePresent = Boolean(
    origin && process.env.SUPABASE_SERVICE_ROLE_KEY,
  );
  const serviceRoleConfigured = Boolean(
    serviceRolePresent && canonicalSupabaseOrigin(origin),
  );
  const oidcIngestConfigurationValid = canonicalPentafabricIngest(
    process.env.PENTAFABRIC_INGEST_URL,
  );
  return {
    service_role_present: serviceRolePresent,
    service_role_configuration_valid: serviceRoleConfigured,
    service_role_fallback_available: serviceRoleConfigured,
    oidc_token_present: oidcTokenPresent,
    oidc_ingest_configuration_valid: oidcIngestConfigurationValid,
    bound: oidcTokenPresent ? false : serviceRoleConfigured,
    mode: oidcTokenPresent
      ? oidcIngestConfigurationValid
        ? 'VERCEL_OIDC_PRESENT_UNVERIFIED'
        : 'VERCEL_OIDC_INGEST_CONFIGURATION_HOLD'
      : serviceRoleConfigured
        ? 'SERVICE_ROLE'
        : serviceRolePresent
          ? 'SERVICE_ROLE_CONFIGURATION_HOLD'
          : 'UNBOUND',
  };
}

export function safeHealthProjection(payload = {}) {
  return {
    schema: payload.schema || null,
    service: payload.service || null,
    role: payload.role || null,
    status: payload.status || 'UNKNOWN',
    operating_mode:
      firstDefined(payload.operating_mode, payload.operatingMode) || null,
    readiness_status:
      firstDefined(payload.readiness_status, payload.readinessStatus) || null,
    capability_states:
      firstDefined(payload.capability_states, payload.capabilityStates) || null,
    release: payload.release || 'unknown',
    environment: payload.environment || null,
    provider_state:
      firstDefined(
        payload.provider_state,
        payload.providerState,
        payload.vercel_provider_state,
      ) || 'UNKNOWN',
    provider_readback:
      payload.provider_readback === true || payload.providerReadback === true,
    write_state:
      firstDefined(payload.write_state, payload.writeState) || null,
    project_id:
      firstDefined(payload.project_id, payload.projectId) || null,
    repository: payload.repository || null,
    build_sha:
      firstDefined(payload.build_sha, payload.buildSha) || null,
    deployment_id:
      firstDefined(payload.deployment_id, payload.deploymentId) || null,
    capabilities: Array.isArray(payload.capabilities)
      ? payload.capabilities
      : [],
    pass_manufactured: manufacturedPassState(
      payload.pass_manufactured,
      payload.passManufactured,
    ),
  };
}

function localProjectState() {
  const environment = process.env.VERCEL_ENV || 'local';
  const providerReadback = environment !== 'local';
  return {
    schema: 'ct.penta.vercel.health.20260827.v1',
    service: 'crownthrive-os-control-plane',
    role: 'public_control_and_platform_plane',
    status: 'OPERATIONAL',
    release: environment === 'production' ? 'production' : 'candidate',
    environment,
    provider_state: providerReadback
      ? `BOUND_${environment.toUpperCase()}`
      : 'BINDING_REQUIRED',
    provider_readback: providerReadback,
    write_state: process.env.VERCEL_AUTOMATION_TOKEN
      ? 'BOUND_GOVERNED'
      : 'GATED_CREDENTIAL_REQUIRED',
    project_id: 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
    repository: 'crownthrive1/CrownThrive-OS',
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || 'local-candidate',
    deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
    capabilities: [
      'public-control-plane',
      'pentafabric-transport',
      'vercel-provider-readback',
      'stateless-read-only-mcp',
      'release-and-recovery-evidence',
    ],
    pass_manufactured: false,
  };
}

async function probeProject(binding, timeoutMs) {
  const startedAt = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(binding.health_url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'User-Agent': 'CrownThrive-PentaVercel/1.0',
      },
      cache: 'no-store',
      redirect: 'error',
      signal: controller.signal,
    });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await response.json()
      : {
          status: 'INVALID_RESPONSE',
          detail: (await response.text()).slice(0, 160),
        };
    const health = safeHealthProjection(payload);
    const pass =
      response.ok &&
      healthMatchesBinding(binding, health);

    return {
      ...binding,
      state: pass ? 'PASS' : 'HOLD',
      reachable: true,
      http_status: response.status,
      latency_ms: Date.now() - startedAt,
      health,
      error: null,
    };
  } catch (error) {
    return {
      ...binding,
      state: 'HOLD',
      reachable: false,
      http_status: null,
      latency_ms: Date.now() - startedAt,
      health: null,
      error:
        error?.name === 'AbortError'
          ? 'provider_readback_timeout'
          : 'provider_readback_failure',
    };
  } finally {
    clearTimeout(timer);
  }
}

function projectPass(project) {
  return (
    project.state === 'PASS' &&
    healthMatchesBinding(project, project.health)
  );
}

function healthMatchesBinding(binding, health) {
  return Boolean(
    health &&
    health.status === 'OPERATIONAL' &&
    health.release === 'production' &&
    health.provider_readback === true &&
    health.provider_state === 'BOUND_PRODUCTION' &&
    health.project_id === binding.project_id &&
    health.repository === binding.repository &&
    /^[a-f0-9]{40}$/.test(String(health.build_sha || '')) &&
    /^dpl_[A-Za-z0-9]+$/.test(String(health.deployment_id || '')) &&
    typeof health.pass_manufactured === 'boolean' &&
    health.pass_manufactured === false
  );
}

export async function collectVercelFabric({
  timeoutMs = 3500,
  oidcTokenPresent = false,
} = {}) {
  const selfBinding = PROJECT_BINDINGS[0];
  const selfHealth = safeHealthProjection(localProjectState());
  const selfProject = {
    ...selfBinding,
    state: healthMatchesBinding(selfBinding, selfHealth) ? 'PASS' : 'HOLD',
    reachable: true,
    http_status: 200,
    latency_ms: 0,
    health: selfHealth,
    error: null,
  };

  const external = await Promise.all(
    PROJECT_BINDINGS.slice(1).map((binding) =>
      probeProject(binding, timeoutMs),
    ),
  );
  const projects = [selfProject, ...external];
  const requiredProjects = projects.filter((project) => project.required);
  const operationalProjects = requiredProjects.filter(projectPass);
  const operational =
    operationalProjects.length === requiredProjects.length;
  const environment = process.env.VERCEL_ENV || 'local';
  const writeBound = Boolean(process.env.VERCEL_AUTOMATION_TOKEN);
  const serviceRoleState = supabaseEvidenceBindingState({ oidcTokenPresent });
  const evidenceSinkBound = serviceRoleState.bound;
  const evidenceSinkMode = serviceRoleState.mode;

  const receiptSubject = {
    schema: 'ct.penta.vercel.execution-fabric.receipt-subject.v1',
    team_id: VERCEL_TEAM_ID,
    environment,
    fabric_status: operational ? 'OPERATIONAL' : 'DEGRADED',
    projects: projects.map((project) => ({
      project_id: project.project_id,
      state: project.state,
      build_sha: project.health?.build_sha || null,
      deployment_id: project.health?.deployment_id || null,
      provider_state: project.health?.provider_state || null,
    })),
  };
  const digest = createHash('sha256')
    .update(stableStringify(receiptSubject))
    .digest('hex');

  return {
    schema: 'ct.penta.vercel.execution-fabric.20260827.v1',
    version: '1.0.1',
    service: 'crownthrive-vercel-execution-fabric',
    status: operational ? 'OPERATIONAL' : 'DEGRADED',
    release:
      environment === 'production' && operational
        ? 'production'
        : 'candidate',
    environment,
    provider: 'vercel',
    team_id: VERCEL_TEAM_ID,
    required_project_count: requiredProjects.length,
    operational_project_count: operationalProjects.length,
    projects,
    lanes: FABRIC_LANES,
    endpoints: {
      control_plane: '/',
      health: '/api/health',
      fabric: '/api/fabric',
      mcp: '/api/mcp',
      mcp_self_test: '/api/mcp?selftest=1',
      pentafabric: '/api/penta',
      pentafabric_health: '/pentafabric/health',
    },
    mcp: {
      status: 'OPERATIONAL',
      endpoint: '/api/mcp',
      transport: 'streamable_http_stateless',
      protocol_version: '2026-07-28',
      profile: 'read_only_provider_and_fabric_tools',
      write_tools: 0,
    },
    provider_operations: {
      git_triggered_deployments: 'BOUND',
      preview_deployments: 'BOUND',
      production_readback: operational ? 'BOUND' : 'DEGRADED',
      build_and_runtime_logs: 'BOUND_VIA_PROVIDER_CONNECTOR',
      direct_project_mutation: writeBound
        ? 'BOUND_GOVERNED'
        : 'GATED_CREDENTIAL_REQUIRED',
      environment_mutation: writeBound
        ? 'BOUND_GOVERNED'
        : 'GATED_CREDENTIAL_REQUIRED',
      domain_mutation: writeBound
        ? 'BOUND_GOVERNED'
        : 'GATED_CREDENTIAL_REQUIRED',
      promote_and_rollback: writeBound
        ? 'BOUND_GOVERNED'
        : 'GATED_CREDENTIAL_REQUIRED',
    },
    evidence: {
      event_contract: 'crownthrive.penta.event.v1',
      receipt_schema: 'ct.penta.vercel.execution-fabric.receipt.v1',
      algorithm: 'sha256',
      digest,
      provider_readback: operational,
      sink: 'supabase:pentafabric_events',
      sink_bound: evidenceSinkBound,
      sink_mode: evidenceSinkMode,
      service_role_present: serviceRoleState.service_role_present,
      service_role_configuration_valid:
        serviceRoleState.service_role_configuration_valid,
      service_role_fallback_available:
        serviceRoleState.service_role_fallback_available,
      oidc_token_present: oidcTokenPresent,
      oidc_token_verified: false,
      oidc_ingest_configuration_valid:
        serviceRoleState.oidc_ingest_configuration_valid,
      persistence_state: evidenceSinkBound
        ? 'AVAILABLE_THROUGH_PENTAFABRIC'
        : oidcTokenPresent &&
            !serviceRoleState.oidc_ingest_configuration_valid
          ? 'GATED_OIDC_INGEST_CONFIGURATION_REQUIRED'
        : oidcTokenPresent
          ? 'PROVIDER_VALIDATION_REQUIRED_ON_DELIVERY'
        : serviceRoleState.service_role_present
          ? 'GATED_SINK_CONFIGURATION_REQUIRED'
          : 'GATED_SINK_BINDING_REQUIRED',
    },
    governance: {
      authority: 'CHLOM + PentaRG + PentaRelease',
      provider_is_governance_authority: false,
      writes_fail_closed: true,
      secret_material_exposed: false,
      pass_manufactured: false,
    },
    observed_at: new Date().toISOString(),
  };
}
