import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "postgres";

const ALLOWED_ORIGIN = "https://vm.crownthrive.com";
const MAX_BODY_BYTES = 4_096;
const NATIVE_CATALOG_EVIDENCE = Object.freeze({
  state: "OBSERVED",
  count: 389,
  available: 2,
  hold: 385,
  deny: 2,
  provider_version: 235,
  deployed_source_commit: "59c9f3f1c6ee32cfe1c110194bd15d52f338ef13",
  provider_archive_sha256:
    "93a15558ab1bc40b79b5b74a0ca601462137f4ecf358eb3742a7c4dac62bd71a",
  observed_at: "2026-08-24T05:30:00Z",
  authority: "SITES_D1_READBACK_SNAPSHOT",
});

let sql: ReturnType<typeof postgres> | null = null;

function database() {
  const url = Deno.env.get("SUPABASE_DB_URL") ?? "";
  if (!url) throw new Error("database_unavailable");
  sql ??= postgres(url, { max: 2, idle_timeout: 8, prepare: false });
  return sql;
}

function requestOrigin(request: Request) {
  return request.headers.get("origin")?.trim() ?? "";
}

function originIsAllowed(request: Request) {
  const origin = requestOrigin(request);
  return origin === "" || origin === ALLOWED_ORIGIN;
}

function responseHeaders(request: Request) {
  const headers: Record<string, string> = {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, max-age=0",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "vary": "Origin",
  };
  if (requestOrigin(request) === ALLOWED_ORIGIN) {
    headers["access-control-allow-origin"] = ALLOWED_ORIGIN;
    headers["access-control-allow-methods"] = "GET, POST, OPTIONS";
    headers["access-control-allow-headers"] = "content-type";
    headers["access-control-max-age"] = "600";
  }
  return headers;
}

function reply(request: Request, body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(request),
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
) {
  const actual = Object.keys(value).sort();
  const expected = [...allowed].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

async function readJson(request: Request) {
  const declaredLength = Number(request.headers.get("content-length") ?? 0);
  if (
    !Number.isFinite(declaredLength) ||
    declaredLength < 0 ||
    declaredLength > MAX_BODY_BYTES
  ) {
    throw new Error("payload_too_large");
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > MAX_BODY_BYTES) {
    throw new Error("payload_too_large");
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("invalid_json");
  }
}

async function manifest() {
  const db = database();
  const [
    services,
    denomination,
    creditProgram,
    wallet,
    policy,
    surface,
    stablecoin,
    schedules,
    adapter,
    metamask,
    walletModes,
    dispatch,
    governedProjection,
    stripeGates,
    mcpCounts,
  ] = await Promise.all([
    db`
      select service_id, integration_state, write_gate, credential_state,
             monthly_request_limit, metadata
      from integration_control.services
      where service_id in (
        'virality_commerce', 'crown_credits', 'stripe',
        'trustwallet_agentkit', 'changelly', 'metamask_embedded_wallets'
      )
      order by service_id
    `,
    db`
      select denomination_id, display_name, crown_credits_per_unit,
             nominal_usd_per_unit, state
      from developer_commerce.virality_credit_denominations_v1
      where denomination_id = 'virality_credits_v1'
      limit 1
    `,
    db`
      select program_id, display_name, active, credits_per_usd,
             legal_tax_state, classification_state
      from developer_commerce.credit_programs
      where program_id = 'ct.credit.store.v1'
      limit 1
    `,
    db`
      select stable_id, lifecycle_state, custody_mode
      from chlom_wallet.wallets
      where stable_id = 'ct.wallet.system.chlom-wallet-os'
      limit 1
    `,
    db`
      select public.thriveevergreen_autonomous_publisher_status_v2() as status
    `,
    db`
      select surface_id, canonical_url, health_state,
             provider_connection_state, update_mode, auto_update_enabled,
             metadata
      from integration_control.website_surfaces
      where surface_id = 'ct.surface.virality-music.production'
      limit 1
    `,
    db`
      select founder_attested_enabled, effective_state, last_crypto_offered,
             last_checked_at
      from integration_control.stripe_stablecoin_activation_state_v2
      where state_id = 'stripe_stablecoin_checkout'
      limit 1
    `,
    db`
      select jobname, schedule, active
      from cron.job
      where jobname like 'ct-thriveevergreen-publisher-v2-slot-%'
         or jobname in (
           'ct-crown-credits-reconcile-v1',
           'ct-stripe-stablecoin-reconcile-v2',
           'ct-thriveevergreen-fabric-daily-drift-v1',
           'ct-thriveevergreen-fabric-weekly-ml-v1'
         )
      order by jobname
    `,
    db`
      select adapter_id, read_capability_state, write_canary_state,
             rollback_canary_state, read_after_write_state, state,
             supports_rollback, supports_read_after_write, certified_at,
             updated_at
      from integration_control.site_provider_adapters
      where adapter_id = 'ct.adapter.sites.virality.v1'
      limit 1
    `,
    db`
      select project_key, environment, primary_origin, allowlist_state,
             frontend_state, wallet_services_state, funding_state,
             walletconnect_state, identity_verification_state, updated_at
      from integration_control.metamask_embedded_wallet_state_v1
      where primary_origin = 'https://vm.crownthrive.com'
      limit 1
    `,
    db`
      select mode_id, display_name, provider_service_id, execution_class,
             runtime_state, activation_state, requires_human_approval,
             autonomous_execution_allowed, max_unattended_value_minor,
             custody_mode, authority_ceiling, updated_at
      from integration_control.wallet_execution_modes_v1
      order by mode_id
    `,
    db`
      select tool_name, enabled, risk_class, requires_human_approval, updated_at
      from integration_control.mcp_tools
      where tool_name = 'thriveevergreen.publish.dispatch'
      limit 1
    `,
    db`
      select count(*)::integer as count
      from integration_control.site_catalog_projection
      where surface_id = 'ct.surface.virality-music.production'
    `,
    db`
      select gate_key, state, updated_at
      from integration_control.gates
      where service_id = 'stripe'
        and gate_key in (
          'provider_writes',
          'credit_funding_policy_v2_alignment',
          'additional_enabled_webhook_surface_reconciliation'
        )
      order by gate_key
    `,
    db`
      select enabled, count(*)::integer as count
      from integration_control.mcp_tools
      where service_id in (
        'thriveevergreen',
        'virality_commerce',
        'crown_credits',
        'stripe',
        'trustwallet_agentkit',
        'metamask_embedded_wallets',
        'changelly',
        'chlom_wallet',
        'virality_music',
        'website_surface_control'
      )
      group by enabled
      order by enabled
    `,
  ]);

  const serviceById = Object.fromEntries(
    services.map((service) => [service.service_id, service]),
  );
  const virality = serviceById.virality_commerce ?? null;
  const stripe = serviceById.stripe ?? null;
  const trustWallet = serviceById.trustwallet_agentkit ?? null;
  const changelly = serviceById.changelly ?? null;
  const d = denomination[0] ?? null;
  const credits = creditProgram[0] ?? null;
  const walletRow = wallet[0] ?? null;
  const publisher = policy[0]?.status ?? null;
  const site = surface[0] ?? null;
  const stablecoinRow = stablecoin[0] ?? null;
  const siteAdapter = adapter[0] ?? null;
  const metamaskRow = metamask[0] ?? null;
  const dispatchRow = dispatch[0] ?? null;
  const stripeGateByKey = Object.fromEntries(
    stripeGates.map((gate) => [gate.gate_key, gate]),
  );
  const requiredStripeGateKeys = [
    "provider_writes",
    "credit_funding_policy_v2_alignment",
    "additional_enabled_webhook_surface_reconciliation",
  ] as const;
  const heldStripeGateKeys = requiredStripeGateKeys.filter(
    (gateKey) => stripeGateByKey[gateKey]?.state !== "passed",
  );
  const stripeProviderGatesPassed = heldStripeGateKeys.length === 0;
  const siteMutationHeld =
    siteAdapter?.state !== "certified" ||
    siteAdapter?.read_capability_state !== "passed" ||
    siteAdapter?.write_canary_state !== "passed" ||
    siteAdapter?.rollback_canary_state !== "passed" ||
    siteAdapter?.read_after_write_state !== "passed";
  const internalPublisherActive =
    publisher?.runtime_mode === "production_write" &&
    publisher?.component_runtime_state === "production_publisher_active" &&
    publisher?.publication_activation_state === "ECAC";

  return {
    service: "ct.virality-commerce-control",
    version: "1.1.1",
    environment: "production",
    observed_at: new Date().toISOString(),
    overall_state: "HOLD",
    state_basis: [
      ...heldStripeGateKeys.map(
        (gateKey) => `STRIPE_GATE_NOT_CERTIFIED:${gateKey}`,
      ),
      "EXACT_ECAC_PURCHASE_CHAIN_NOT_CERTIFIED",
      ...(siteMutationHeld ? ["NATIVE_SITES_ADAPTER_NOT_CERTIFIED"] : []),
      ...(stablecoinRow?.effective_state !== "CUSTOMER_EFFECTIVE"
        ? ["STABLECOIN_CUSTOMER_EFFECTIVE_READBACK_PENDING"]
        : []),
      ...(metamaskRow?.frontend_state !== "active"
        ? ["METAMASK_FRONTEND_NOT_ACTIVE"]
        : []),
      ...(dispatchRow?.enabled === false
        ? ["GENERALIZED_DISPATCH_DISABLED_BY_POLICY"]
        : []),
    ],
    site: {
      url: "https://vm.crownthrive.com",
      health_state: site?.health_state ?? null,
      provider_connection_state: site?.provider_connection_state ?? null,
      account_auth: "Sign in with ChatGPT",
      checkout_route: "/api/checkout",
      unauthenticated_checkout_live_readback:
        "400_PROTECTED_PURCHASE_ATTEMPT_KEY_REQUIRED",
      native_wallet_fabric_ui: "NOT_DETECTED",
      native_mutation_state: siteMutationHeld
        ? "HOLD"
        : "PROVIDER_ADAPTER_REPORTED_CERTIFIED_AUTHORITY_STILL_HELD",
      native_mutation_authorized: false,
      adapter: siteAdapter,
      public_catalog: NATIVE_CATALOG_EVIDENCE,
      governed_feed_projection_count:
        Number(governedProjection[0]?.count ?? 0),
      catalog_count_authority:
        "Native Sites D1 and deployed source readback; central projection is separately reported.",
    },
    tender: {
      canonical_program_id: credits?.program_id ?? null,
      canonical_display_name: credits?.display_name ?? "Crown Credits",
      canonical_credits_per_usd: Number(credits?.credits_per_usd ?? 0),
      canonical_active: Boolean(credits?.active),
      virality_display_denomination: d
        ? {
            name: d.display_name,
            crown_credits_per_unit: Number(d.crown_credits_per_unit),
            nominal_usd_per_unit: Number(d.nominal_usd_per_unit),
            state: d.state,
            automatic_historical_balance_rewrite: false,
          }
        : null,
    },
    payments: {
      stripe_direct: {
        provider_account_state: stripe?.integration_state ?? null,
        effective_state: stripeProviderGatesPassed
          ? "HOLD_EXACT_ECAC_PURCHASE_CHAIN"
          : "HOLD_INDEPENDENT_SECURITY",
        provider_gate_states: Object.fromEntries(
          requiredStripeGateKeys.map((gateKey) => [
            gateKey,
            stripeGateByKey[gateKey]?.state ?? "missing",
          ]),
        ),
        provider_gates_passed: stripeProviderGatesPassed,
        checkout_authorized: false,
        crown_credit_topups_authorized: false,
        economic_authority_bound: false,
        authority_state: stripeProviderGatesPassed
          ? "PROVIDER_GATES_ARE_EVIDENCE_ECAC_STILL_REQUIRED"
          : "PROVIDER_GATES_HELD",
        authority_rule: "Provider success is evidence, not economic truth.",
      },
      stripe_connect: {
        effective_state: "HOLD_SECURITY_REVIEW",
        payout_or_earnings_truth_from_provider_event: false,
      },
      stablecoin: {
        founder_attested_dashboard_enabled:
          stablecoinRow?.founder_attested_enabled === true,
        effective_checkout_state:
          stablecoinRow?.effective_state ?? "UNKNOWN",
        last_crypto_offered: stablecoinRow?.last_crypto_offered ?? null,
        last_checked_at: stablecoinRow?.last_checked_at ?? null,
      },
      changelly: {
        widget_state: changelly?.metadata?.widget_state ?? null,
        merchant_mode: changelly?.metadata?.widget_mode ?? null,
        v2_api_state: changelly?.metadata?.v2_api_state ?? null,
        separate_provider_corridor: true,
      },
    },
    wallets: {
      chlom: {
        state: walletRow?.lifecycle_state ?? null,
        custody_mode: walletRow?.custody_mode ?? null,
        money_movement_from_wallet_event: false,
      },
      metamask_embedded: metamaskRow,
      modes: walletModes.map((mode) => ({
        ...mode,
        max_unattended_value_minor:
          Number(mode.max_unattended_value_minor ?? 0),
        effective_economic_execution:
          Number(mode.max_unattended_value_minor ?? 0) === 0
            ? "HOLD_ZERO_UNATTENDED_CEILING"
            : "REQUIRES_EXACT_POLICY_EVALUATION",
      })),
      trustwallet: {
        state: trustWallet?.integration_state ?? null,
        hosted_api: trustWallet?.metadata?.hosted_api_state ?? null,
        signing_state: trustWallet?.metadata?.signing_state ?? null,
        persistent_runner_state:
          trustWallet?.metadata?.persistent_runner_state ?? "PENDING",
        provider_reported_execution_flag:
          trustWallet?.metadata?.provider_execution_authorized === true,
        provider_execution_authorized: false,
        economic_authority_bound: false,
      },
    },
    authority: {
      constitutional_rule:
        "ThriveEvergreen may optimize within authority. It may never manufacture authority.",
      exact_decisions: ["ECAC", "HOLD", "DENY"],
      internal_publisher: {
        engine: "ct.agent.thriveevergreen-autonomous-publisher.v2",
        state: internalPublisherActive
          ? "PRODUCTION_PUBLISHER_ACTIVE"
          : "HOLD",
        policy: publisher,
      },
      generalized_dispatch: {
        state: "HOLD_EXACT_MUTATION_CONTRACT",
        registry_enabled_evidence: dispatchRow?.enabled === true,
        execution_authorized: false,
        registry: dispatchRow,
      },
      d3: "HUMAN_RESERVED",
      advisory_ml_economic_authority: false,
    },
    api_mcp: {
      scope_service_ids: [
        "thriveevergreen",
        "virality_commerce",
        "crown_credits",
        "stripe",
        "trustwallet_agentkit",
        "metamask_embedded_wallets",
        "changelly",
        "chlom_wallet",
        "virality_music",
        "website_surface_control",
      ],
      scope_tool_count: mcpCounts.reduce(
        (total, row) => total + Number(row.count),
        0,
      ),
      relevant_registry_flag_counts: Object.fromEntries(
        mcpCounts.map((row) => [
          row.enabled === true ? "enabled" : "disabled",
          Number(row.count),
        ]),
      ),
      enabled_flag_is_not_execution_authority: true,
    },
    schedules,
    raw_secret_export: false,
  };
}

Deno.serve(async (request: Request) => {
  if (!originIsAllowed(request)) {
    return reply(request, { error: "origin_not_allowed" }, 403);
  }

  if (request.method === "OPTIONS") {
    if (requestOrigin(request) !== ALLOWED_ORIGIN) {
      return reply(request, { error: "origin_required" }, 403);
    }
    return new Response(null, { status: 204, headers: responseHeaders(request) });
  }

  try {
    if (request.method === "GET") {
      return reply(request, await manifest());
    }
    if (request.method !== "POST") {
      return reply(request, { error: "method_not_allowed" }, 405);
    }

    const body = await readJson(request);
    if (!isRecord(body) || typeof body.action !== "string") {
      return reply(request, { error: "invalid_request" }, 400);
    }

    if (body.action === "manifest" || body.action === "health") {
      if (!hasExactKeys(body, ["action"])) {
        return reply(request, { error: "invalid_request_shape" }, 400);
      }
      return reply(request, await manifest());
    }

    if (body.action === "convert_virality_credits") {
      if (!hasExactKeys(body, ["action", "amount"])) {
        return reply(request, { error: "invalid_request_shape" }, 400);
      }
      const amount = body.amount;
      if (
        typeof amount !== "number" ||
        !Number.isSafeInteger(amount) ||
        amount < 0 ||
        amount > Math.floor(Number.MAX_SAFE_INTEGER / 25)
      ) {
        return reply(request, { error: "invalid_amount" }, 400);
      }
      return reply(request, {
        from: "Virality Credits",
        amount,
        to: "Crown Credits",
        canonical_amount: amount * 25,
        ratio: "1 Virality Credit = 25 Crown Credits",
        ledger_mutation: false,
        historical_balance_rewrite: false,
      });
    }

    return reply(request, { error: "unknown_action" }, 400);
  } catch (error) {
    const code = error instanceof Error ? error.message : "operation_failed";
    if (code === "payload_too_large") {
      return reply(request, { error: code, raw_secret_export: false }, 413);
    }
    if (code === "invalid_json") {
      return reply(request, { error: code, raw_secret_export: false }, 400);
    }
    return reply(
      request,
      { error: "control_readback_unavailable", raw_secret_export: false },
      503,
    );
  }
});
