const PADDLE_UPSTREAM_COMMIT = 'de7fcd3f6cc43bf87a65d6b2e65067611b47353c';

export const PADDLE_MCP_SERVERS = Object.freeze({
  docs: Object.freeze({ id: 'paddle-docs', url: 'https://paddlehq.mcp.kapa.ai' }),
  sandbox: Object.freeze({ id: 'paddle-sandbox', url: 'https://sandbox-mcp.paddle.com/mcp' }),
  live: Object.freeze({ id: 'paddle-live', url: 'https://mcp.paddle.com/mcp' }),
});

export const PADDLE_SKILLS = Object.freeze({
  billing_history: Object.freeze({ skill: 'paddle-billing-history', purpose: 'Authenticated customer transaction history and invoice downloads.' }),
  catalog_setup: Object.freeze({ skill: 'paddle-catalog-setup', purpose: 'Products, prices, tax categories, billing intervals, and catalog seeding.' }),
  checkout_web: Object.freeze({ skill: 'paddle-checkout-web', purpose: 'Paddle Checkout integration for web applications.' }),
  customer_portal: Object.freeze({ skill: 'paddle-customer-portal', purpose: 'Authenticated customer portal sessions and self-service billing.' }),
  pricing_pages: Object.freeze({ skill: 'paddle-pricing-pages', purpose: 'Localized pricing previews, currencies, and billing-frequency presentation.' }),
  sandbox_testing: Object.freeze({ skill: 'paddle-sandbox-testing', purpose: 'End-to-end Paddle sandbox tests and integration canaries.' }),
  subscription_cancel: Object.freeze({ skill: 'paddle-subscription-cancel', purpose: 'Authorized cancellation-at-period-end flows and reconciliation.' }),
  subscription_sync: Object.freeze({ skill: 'paddle-subscription-sync', purpose: 'Webhook-driven customer and subscription state synchronization.' }),
  subscription_update: Object.freeze({ skill: 'paddle-subscription-update', purpose: 'Authorized upgrades, downgrades, item changes, and proration handling.' }),
  webhooks: Object.freeze({ skill: 'paddle-webhooks', purpose: 'Webhook receipt, signature verification, idempotency, retry, and reconciliation.' }),
});

export const PADDLE_OPERATIONS = Object.freeze(Object.keys(PADDLE_SKILLS));
export const PADDLE_ENVIRONMENTS = Object.freeze(['docs', 'sandbox', 'live']);

function requireObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError(`${label} must be an object.`);
  return value;
}

function requireEnum(value, allowed, label) {
  if (!allowed.includes(value)) throw new TypeError(`${label} must be one of: ${allowed.join(', ')}.`);
  return value;
}

export function routePaddleOperation(rawArguments = {}) {
  const args = requireObject(rawArguments, 'arguments');
  const operation = requireEnum(args.operation, PADDLE_OPERATIONS, 'operation');
  const environment = requireEnum(args.environment || 'sandbox', PADDLE_ENVIRONMENTS, 'environment');
  const selected = PADDLE_SKILLS[operation];
  const mcpServer = PADDLE_MCP_SERVERS[environment];
  const state = environment === 'live'
    ? 'HOLD_EXACT_LIVE_OPERATION_AUTHORITY_REQUIRED'
    : environment === 'sandbox'
      ? 'ROUTED_SANDBOX_PROVIDER_AUTH_AND_READBACK_REQUIRED'
      : 'ROUTED_DOCUMENTATION_AUTH_MAY_BE_REQUIRED';
  return {
    schema: 'ct.crownthrive.paddle.route.v1', state, operation, environment,
    task: typeof args.task === 'string' ? args.task.slice(0, 2000) : null,
    required_skill: selected.skill, skill_purpose: selected.purpose, mcp_server: mcpServer,
    upstream_source: { repository: 'PaddleHQ/paddle-agent-skills', commit: PADDLE_UPSTREAM_COMMIT, plugin: 'paddle' },
    use_required: true, provider_contacted: false, side_effect_performed: false,
    next_control: environment === 'live'
      ? 'Resolve eligible-operator OAuth, provider write scope, exact-operation authority, idempotency, rollback or compensation, and provider readback.'
      : environment === 'sandbox'
        ? 'Load the required skill, resolve the sandbox credential in the protected runtime, call paddle-sandbox, and preserve sanitized provider readback.'
        : 'Load the required skill and use paddle-docs to resolve current provider semantics before implementation.',
    truth_boundary: 'Routing selects a pinned skill and MCP lane. It does not authenticate Paddle, grant provider authority, perform a provider action, or certify production.',
  };
}

export function paddleIntegrationStatus() {
  return {
    schema: 'ct.crownthrive.paddle.integration-status.v1',
    state: 'SOURCE_MERGED_AND_SERVING_ROUTE', production_state: 'HOLD_PROVIDER_AUTH_AND_READBACK',
    upstream: { repository: 'PaddleHQ/paddle-agent-skills', commit: PADDLE_UPSTREAM_COMMIT, plugin: 'paddle', skill_count: PADDLE_OPERATIONS.length },
    mcp_servers: PADDLE_MCP_SERVERS,
    skills: PADDLE_OPERATIONS.map((operation) => ({ operation, ...PADDLE_SKILLS[operation] })),
    credential_values_exposed: false, provider_contacted: false, side_effect_performed: false,
    provider_readback: 'NOT_PERFORMED_BY_STATUS_TOOL',
    truth_boundary: 'This status proves the serving gateway loaded the pinned Paddle routing contract. It does not prove Paddle authentication, provider availability, checkout, settlement, entitlement, revenue, or production certification.',
  };
}

export function preflightPaddleOperation(rawArguments = {}) {
  const route = routePaddleOperation(rawArguments);
  const blockers = [];
  if (route.environment === 'sandbox' && !process.env.PADDLE_SANDBOX_API_KEY) blockers.push('PADDLE_SANDBOX_API_KEY_NOT_BOUND');
  if (route.environment === 'live') blockers.push('ELIGIBLE_OPERATOR_OAUTH_NOT_PROVABLE_AT_SERVER', 'EXACT_LIVE_OPERATION_AUTHORITY_REQUIRED', 'PROVIDER_WRITE_SCOPE_AND_READBACK_REQUIRED');
  if (route.environment === 'docs') blockers.push('INTERACTIVE_PROVIDER_AUTH_MAY_BE_REQUIRED');
  return {
    schema: 'ct.crownthrive.paddle.preflight.v1', state: blockers.length === 0 ? 'READY_FOR_BOUNDED_SANDBOX_CALL' : 'HOLD',
    route, blockers,
    sandbox_credential_bound: route.environment === 'sandbox' ? Boolean(process.env.PADDLE_SANDBOX_API_KEY) : null,
    credential_value_exposed: false, provider_contacted: false, side_effect_performed: false,
    checked_at: new Date().toISOString(),
  };
}

export function paddleGatewayDescriptor() {
  return {
    upstream_repository: 'PaddleHQ/paddle-agent-skills', upstream_commit: PADDLE_UPSTREAM_COMMIT,
    plugin: 'paddle', skill_count: PADDLE_OPERATIONS.length,
    mcp_servers: Object.values(PADDLE_MCP_SERVERS).map((server) => server.id),
    default_environment: 'sandbox', production_state: 'HOLD_PROVIDER_AUTH_AND_READBACK', write_authority: 'NONE_AT_GATEWAY',
  };
}
