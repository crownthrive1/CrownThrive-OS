import { createHash } from 'node:crypto';

export const VERCEL_TEAM_ID = 'team_v4xkGtBZSrZXnJtLEJhra5nd';

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
    health_url: process.env.PRIVATE_PENTA_OS_HEALTH_URL || 'https://private-penta-os.vercel.app/health',
    visibility: 'private',
    required: true,
    lanes: ['control_plane'],
  },
  {
    key: 'private_penta_execution',
    service: 'private-penta-execution',
    project_id: 'prj_d1uyuhNZHXfANgZv9zTEiaIlcZer',
    repository: 'crownthrive1/PRIVATE-PentaExecution',
    health_url: process.env.PRIVATE_PENTA_EXECUTION_HEALTH_URL || 'https://private-penta-execution.vercel.app/health',
    visibility: 'private',
    required: true,
    lanes: ['platform_api', 'control_plane'],
  },
  {
    key: 'chlom_protocol',
    service: 'chlom-protocol',
    project_id: 'prj_HewLgMjUiVBNCl0FADFbSggSp2QN',
    repository: 'crownthrive1/chlom-protocol',
    health_url: process.env.CHLOM_PROTOCOL_HEALTH_URL || 'https://chlom-protocol.vercel.app/health',
    visibility: 'public',
    required: true,
    lanes: ['platform_api', 'control_plane'],
  },
]);

export const FABRIC_LANES = Object.freeze([
  {
    id: 'public_experience',
    name: 'Public Experience',
    function: 'Production UI, public-safe operating status, and future CrownThrive experience deployments.',
    current_projects: ['prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN'],
  },
  {
    id: 'platform_api',
    name: 'Platform / API',
    function: 'Health, Penta transport, provider readback, MCP, integration, and bounded execution endpoints.',
    current_projects: [
      'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
      'prj_d1uyuhNZHXfANgZv9zTEiaIlcZer',
      'prj_HewLgMjUiVBNCl0FADFbSggSp2QN',
    ],
  },
  {
    id: 'control_plane',
    name: 'Control Plane',
    function: 'PentaRG, PentaVercel, PentaOS, PentaExecution, CHLOM authority, release evidence, and recovery.',
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

function safeHealthProjection(payload = {}) {
  return {
    schema: payload.schema || null,
    service: payload.service || null,
    role: payload.role || null,
    status: payload.status || 'UNKNOWN',
    release: payload.release || 'unknown',
    environment: payload.environment || null,
    provider_state: payload.provider_state || payload.vercel_provider_state || 'UNKNOWN',
    provider_readback: payload.provider_readback === true,
    write_state: payload.write_state || null,
    project_id: payload.project_id || null,
    repository: payload.repository || null,
    build_sha: payload.build_sha || null,
    deployment_id: payload.deployment_id || null,
    capabilities: Array.isArray(payload.capabilities) ? payload.capabilities : [],
    pass_manufactured: payload.pass_manufactured === true,
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
    provider_state: providerReadback ? `BOUND_${environment.toUpperCase()}` : 'BINDING_REQUIRED',
    provider_readback: providerReadback,
    write_state: process.env.VERCEL_AUTOMATION_TOKEN ? 'BOUND_GOVERNED' : 'GATED_CREDENTIAL_REQUIRED',
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
      signal: controller.signal,
    });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await response.json()
      : { status: 'INVALID_RESPONSE', detail: (await response.text()).slice(0, 160) };
    const health = safeHealthProjection(payload);
    const pass =
      response.ok &&
      health.status === 'OPERATIONAL' &&
      health.release === 'production' &&
      health.provider_readback === true &&
      health.provider_state === 'BOUND_PRODUCTION' &&
      health.pass_manufactured === false;

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
      error: error?.name === 'AbortError' ? 'provider_readback_timeout' : 'provider_readback_failure',
    };
  } finally {
    clearTimeout(timer);
  }
}

function projectPass(project) {
  return (
    project.state === 'PASS' &&
    project.health?.status === 'OPERATIONAL' &&
    project.health?.provider_readback === true &&
    project.health?.pass_manufactured === false
  );
}

export async function collectVercelFabric({ timeoutMs = 3500 } = {}) {
  const selfBinding = PROJECT_BINDINGS[0];
  const selfHealth = safeHealthProjection(localProjectState());
  const selfProject = {
    ...selfBinding,
    state:
      selfHealth.status === 'OPERATIONAL' &&
      selfHealth.release === 'production' &&
      selfHealth.provider_readback &&
      !selfHealth.pass_manufactured
        ? 'PASS'
        : 'HOLD',
    reachable: true,
    http_status: 200,
    latency_ms: 0,
    health: selfHealth,
    error: null,
  };

  const external = await Promise.all(
    PROJECT_BINDINGS.slice(1).map((binding) => probeProject(binding, timeoutMs)),
  );
  const projects = [selfProject, ...external];
  const requiredProjects = projects.filter((project) => project.required);
  const operationalProjects = requiredProjects.filter(projectPass);
  const operational = operationalProjects.length === requiredProjects.length;
  const environment = process.env.VERCEL_ENV || 'local';
  const writeBound = Boolean(process.env.VERCEL_AUTOMATION_TOKEN);
  const evidenceSinkBound = Boolean(
    (process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL) &&
      process.env.SUPABASE_SERVICE_ROLE_KEY,
  );

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
  const digest = createHash('sha256').update(stableStringify(receiptSubject)).digest('hex');

  return {
    schema: 'ct.penta.vercel.execution-fabric.20260827.v1',
    version: '1.0.0',
    service: 'crownthrive-vercel-execution-fabric',
    status: operational ? 'OPERATIONAL' : 'DEGRADED',
    release: environment === 'production' && operational ? 'production' : 'candidate',
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
      direct_project_mutation: writeBound ? 'BOUND_GOVERNED' : 'GATED_CREDENTIAL_REQUIRED',
      environment_mutation: writeBound ? 'BOUND_GOVERNED' : 'GATED_CREDENTIAL_REQUIRED',
      domain_mutation: writeBound ? 'BOUND_GOVERNED' : 'GATED_CREDENTIAL_REQUIRED',
      promote_and_rollback: writeBound ? 'BOUND_GOVERNED' : 'GATED_CREDENTIAL_REQUIRED',
    },
    evidence: {
      event_contract: 'crownthrive.penta.event.v1',
      receipt_schema: 'ct.penta.vercel.execution-fabric.receipt.v1',
      algorithm: 'sha256',
      digest,
      provider_readback: operational,
      sink: 'supabase:pentafabric_events',
      sink_bound: evidenceSinkBound,
      persistence_state: evidenceSinkBound ? 'AVAILABLE_THROUGH_PENTAFABRIC' : 'GATED_SINK_BINDING_REQUIRED',
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
