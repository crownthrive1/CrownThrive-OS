import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SERVICE_ID = "ct.service.chlom-wallet-policy-lab";
const AGENT_ID = "ct.agent.chlom-wallet-settlement";
const STATE = "CONTROLLED_TEST";
const ORIGIN = "https://wallet.crownthrive.com";
const MAX_BODY_BYTES = 65_536;
const MAX_USAGE_EVENTS = 10_000;
const encoder = new TextEncoder();

type JsonObject = Record<string, unknown>;
type Decision = "ALLOW" | "HOLD" | "DENY";

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function canonicalize(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  if (isObject(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(",")}}`;
  }
  if (typeof value === "number" && !Number.isFinite(value)) throw new Error("non_finite_number_forbidden");
  return JSON.stringify(value);
}

async function sha256Hex(value: string): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
  return [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function responseHeaders(origin: string) {
  return {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, max-age=0",
    "pragma": "no-cache",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "authorization,content-type,x-crownthrive-correlation-id",
    "access-control-max-age": "600",
    "vary": "Origin",
  };
}

function allowedOrigin(req: Request): string | null {
  const origin = req.headers.get("origin");
  if (!origin) return ORIGIN;
  return origin === ORIGIN ? origin : null;
}

function json(req: Request, body: unknown, status = 200): Response {
  const origin = allowedOrigin(req) ?? ORIGIN;
  return new Response(JSON.stringify(body), { status, headers: responseHeaders(origin) });
}

function jwtSubject(req: Request): string {
  const authorization = req.headers.get("authorization") ?? "";
  const match = /^Bearer\s+(.+)$/i.exec(authorization);
  if (!match) throw new Error("authorization_required");
  const parts = match[1].split(".");
  if (parts.length !== 3) throw new Error("jwt_shape_invalid");
  const encoded = parts[1].replaceAll("-", "+").replaceAll("_", "/");
  let payload: JsonObject;
  try {
    payload = JSON.parse(atob(encoded + "===".slice((encoded.length + 3) % 4)));
  } catch {
    throw new Error("jwt_payload_invalid");
  }
  const sub = String(payload.sub ?? "");
  if (!/^[A-Za-z0-9._:@-]{6,200}$/.test(sub)) throw new Error("jwt_subject_invalid");
  const exp = Number(payload.exp ?? 0);
  if (!Number.isFinite(exp) || exp <= Math.floor(Date.now() / 1000)) throw new Error("jwt_expired");
  return sub;
}

function safeInteger(value: unknown, code: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) throw new Error(code);
  return Number(value);
}

async function budgetPreview(input: JsonObject) {
  const used = safeInteger(input.used, "usage_used_invalid");
  const requested = safeInteger(input.requested, "usage_requested_invalid");
  const limit = input.limit;
  let disposition: Decision;
  let reasonCode: string;
  let remaining: number | null = null;

  if (limit === null || limit === undefined) {
    disposition = "HOLD";
    reasonCode = "LIMIT_UNRESOLVED_FAIL_CLOSED";
  } else if (!Number.isSafeInteger(limit)) {
    disposition = "DENY";
    reasonCode = "LIMIT_NOT_INTEGER";
  } else if (Number(limit) === -1) {
    disposition = "ALLOW";
    reasonCode = "UNLIMITED_LOCAL_LIMIT";
  } else if (Number(limit) < -1) {
    disposition = "DENY";
    reasonCode = "LIMIT_NEGATIVE_INVALID";
  } else if (Number(limit) === 0) {
    remaining = 0;
    if (requested === 0) {
      disposition = "ALLOW";
      reasonCode = "ZERO_REQUEST_WITH_ZERO_LIMIT";
    } else {
      disposition = "DENY";
      reasonCode = "ZERO_LIMIT_DENIES_USAGE";
    }
  } else {
    const numericLimit = Number(limit);
    const projected = used + requested;
    if (!Number.isSafeInteger(projected)) {
      disposition = "DENY";
      reasonCode = "USAGE_INTEGER_OVERFLOW";
      remaining = Math.max(numericLimit - used, 0);
    } else if (projected <= numericLimit) {
      disposition = "ALLOW";
      reasonCode = "WITHIN_EXACT_LIMIT";
      remaining = numericLimit - projected;
    } else {
      disposition = "DENY";
      reasonCode = "EXACT_LIMIT_EXCEEDED";
      remaining = Math.max(numericLimit - used, 0);
    }
  }

  const body = {
    contract: "ct.wallet.usage-budget-decision.v1",
    semantics_version: "ct.limit-semantics.founder-override.v1",
    limit: limit ?? null,
    used,
    requested,
    disposition,
    reason_code: reasonCode,
    remaining_after_request: remaining,
    provider_limits_still_authoritative: true,
    hard_boundaries: {
      billing_charge_created: false,
      stripe_object_created: false,
      provider_write: false,
      money_movement: false,
      production_entitlement_grant: false,
    },
  };
  return { ...body, decision_digest_sha256: await sha256Hex(canonicalize(body)) };
}

function actionBoolean(action: JsonObject, key: string): boolean {
  return action[key] === true;
}

async function policyPreview(input: JsonObject) {
  const environment = String(input.environment ?? "");
  const action = isObject(input.action) ? input.action : {};
  const evidence = isObject(input.evidence) ? input.evidence : {};
  const category = String(action.category ?? "");
  let decision: Decision = "HOLD";
  let reasonCode = "DEFAULT_HOLD";
  let decisiveRuleIds: string[] = [];

  const denyRules: Array<[string, string, boolean]> = [
    ["ct.rule.wallet.deny-live-provider-write.v1", "LIVE_PROVIDER_WRITE_NOT_AUTHORIZED", actionBoolean(action, "provider_write")],
    ["ct.rule.wallet.deny-money-movement.v1", "MONEY_MOVEMENT_NOT_AUTHORIZED", actionBoolean(action, "money_movement")],
    ["ct.rule.wallet.deny-production-rights-grant.v1", "PRODUCTION_RIGHTS_GRANT_NOT_AUTHORIZED", actionBoolean(action, "production_rights_grant")],
    ["ct.rule.wallet.deny-chain-broadcast.v1", "CHAIN_BROADCAST_NOT_AUTHORIZED", actionBoolean(action, "chain_broadcast")],
  ];
  const triggeredDeny = denyRules.find(([, , matched]) => matched);
  if (triggeredDeny) {
    decision = "DENY";
    reasonCode = triggeredDeny[1];
    decisiveRuleIds = [triggeredDeny[0]];
  } else if (actionBoolean(action, "effective_offer_change")) {
    decision = "HOLD";
    reasonCode = "INDEPENDENT_PRICE_AND_RELEASE_REVIEW_REQUIRED";
    decisiveRuleIds = ["ct.rule.wallet.hold-effective-offer-change.v1"];
  } else if (category === "provider_translation") {
    if (evidence.provider_signature_verified !== true) {
      decision = "HOLD";
      reasonCode = evidence.provider_signature_verified === undefined
        ? "POLICY_INPUT_UNKNOWN"
        : "PROVIDER_EVIDENCE_NOT_VERIFIED";
      decisiveRuleIds = ["ct.rule.wallet.hold-unverified-provider-evidence.v1"];
    } else if (environment === "CONTROLLED_TEST" && action.provider_write === false) {
      decision = "ALLOW";
      reasonCode = "CONTROLLED_PROVIDER_TRANSLATION_ALLOWED";
      decisiveRuleIds = ["ct.rule.wallet.allow-controlled-provider-translation.v1"];
    }
  } else if (category === "rights_decision") {
    if (evidence.independent_rights_active !== true) {
      decision = "HOLD";
      reasonCode = evidence.independent_rights_active === undefined
        ? "POLICY_INPUT_UNKNOWN"
        : "INDEPENDENT_RIGHTS_EVIDENCE_REQUIRED";
      decisiveRuleIds = ["ct.rule.wallet.hold-rights-without-independent-evidence.v1"];
    } else if (environment === "CONTROLLED_TEST" && action.production_rights_grant === false) {
      decision = "ALLOW";
      reasonCode = "CONTROLLED_RIGHTS_EVALUATION_ALLOWED";
      decisiveRuleIds = ["ct.rule.wallet.allow-controlled-rights-evaluation.v1"];
    }
  } else if (["policy_simulation", "usage_preview", "advisor_preview"].includes(category)) {
    if (
      environment === "CONTROLLED_TEST"
      && action.provider_write === false
      && action.money_movement === false
      && action.chain_broadcast === false
    ) {
      decision = "ALLOW";
      reasonCode = "CONTROLLED_SIMULATION_ALLOWED";
      decisiveRuleIds = ["ct.rule.wallet.allow-controlled-simulation.v1"];
    }
  }

  const body = {
    contract: "ct.wallet.policy-decision-receipt.v1",
    policy_id: "ct.policy.chlom-wallet.walletkit-controlled.v1",
    policy_version: "1.0.0",
    input_digest_sha256: await sha256Hex(canonicalize(input)),
    decision,
    reason_code: reasonCode,
    decisive_rule_ids: decisiveRuleIds,
    hard_boundaries: {
      provider_write: false,
      production_rights_grant: false,
      credential_activation: false,
      chain_broadcast: false,
      custody: false,
      money_movement: false,
      effective_price_publication: false,
      checkout_activation: false,
      phase_advancement: false,
      merge_authorized: false,
    },
  };
  return { ...body, decision_digest_sha256: await sha256Hex(canonicalize(body)) };
}

type UsageEvent = {
  event_id: string;
  idempotency_key: string;
  tenant_ref: string;
  wallet_stable_id: string;
  meter_id: string;
  quantity: number;
  occurred_at: string;
  payload_digest_sha256: string;
};

async function normalizeUsageEvent(value: unknown): Promise<UsageEvent> {
  if (!isObject(value)) throw new Error("usage_event_object_required");
  const eventId = String(value.event_id ?? "");
  const idempotencyKey = String(value.idempotency_key ?? "");
  const tenantRef = String(value.tenant_ref ?? "");
  const walletStableId = String(value.wallet_stable_id ?? "");
  const meterId = String(value.meter_id ?? "");
  const quantity = safeInteger(value.quantity, "usage_quantity_invalid");
  const occurred = new Date(String(value.occurred_at ?? ""));
  if (!/^ctue_[A-Za-z0-9_-]{12,120}$/.test(eventId)) throw new Error("usage_event_id_invalid");
  if (!/^ctik_[A-Za-z0-9_-]{12,160}$/.test(idempotencyKey)) throw new Error("usage_idempotency_key_invalid");
  if (tenantRef.length < 3 || tenantRef.length > 180) throw new Error("usage_tenant_ref_invalid");
  if (walletStableId.length < 3 || walletStableId.length > 220) throw new Error("usage_wallet_id_invalid");
  if (!/^ct[.]meter[.][a-z0-9._-]{3,180}$/.test(meterId)) throw new Error("usage_meter_id_invalid");
  if (Number.isNaN(occurred.getTime())) throw new Error("usage_occurred_at_invalid");
  const digestBody = {
    tenant_ref: tenantRef,
    wallet_stable_id: walletStableId,
    meter_id: meterId,
    quantity,
    occurred_at: occurred.toISOString(),
  };
  const computedDigest = await sha256Hex(canonicalize(digestBody));
  const suppliedDigest = value.payload_digest_sha256;
  if (suppliedDigest !== undefined && (!/^[0-9a-f]{64}$/.test(String(suppliedDigest)) || String(suppliedDigest) !== computedDigest)) {
    throw new Error("usage_payload_digest_mismatch");
  }
  return {
    event_id: eventId,
    idempotency_key: idempotencyKey,
    tenant_ref: tenantRef,
    wallet_stable_id: walletStableId,
    meter_id: meterId,
    quantity,
    occurred_at: occurred.toISOString(),
    payload_digest_sha256: computedDigest,
  };
}

async function usageRollupPreview(input: JsonObject) {
  if (!Array.isArray(input.events) || input.events.length < 1 || input.events.length > MAX_USAGE_EVENTS) {
    throw new Error("usage_event_count_invalid");
  }
  const windowStart = new Date(String(input.window_start ?? ""));
  const windowEnd = new Date(String(input.window_end ?? ""));
  if (Number.isNaN(windowStart.getTime()) || Number.isNaN(windowEnd.getTime()) || windowStart >= windowEnd) {
    throw new Error("usage_rollup_window_invalid");
  }
  const normalized = await Promise.all(input.events.map(normalizeUsageEvent));
  const byIdempotency = new Map<string, UsageEvent>();
  let duplicateCount = 0;
  for (const event of normalized) {
    const prior = byIdempotency.get(event.idempotency_key);
    if (!prior) {
      byIdempotency.set(event.idempotency_key, event);
      continue;
    }
    if (prior.payload_digest_sha256 !== event.payload_digest_sha256) throw new Error("usage_idempotency_collision");
    duplicateCount += 1;
  }
  const unique = [...byIdempotency.values()];
  const tenantRef = String(input.tenant_ref ?? unique[0]?.tenant_ref ?? "");
  const walletStableId = String(input.wallet_stable_id ?? unique[0]?.wallet_stable_id ?? "");
  const meterId = String(input.meter_id ?? unique[0]?.meter_id ?? "");
  const matched = unique
    .filter((event) => event.tenant_ref === tenantRef && event.wallet_stable_id === walletStableId && event.meter_id === meterId)
    .filter((event) => {
      const occurred = new Date(event.occurred_at);
      return occurred >= windowStart && occurred < windowEnd;
    })
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at) || a.event_id.localeCompare(b.event_id));
  const quantity = matched.reduce((total, event) => total + event.quantity, 0);
  if (!Number.isSafeInteger(quantity)) throw new Error("usage_rollup_integer_overflow");
  const body = {
    contract: "ct.wallet.usage-rollup-preview.v1",
    tenant_ref: tenantRef,
    wallet_stable_id: walletStableId,
    meter_id: meterId,
    window_start: windowStart.toISOString(),
    window_end: windowEnd.toISOString(),
    supplied_event_count: normalized.length,
    exact_duplicate_count: duplicateCount,
    unique_event_count: unique.length,
    matched_event_count: matched.length,
    quantity,
    event_ids: matched.map((event) => event.event_id),
    event_payload_digests: matched.map((event) => event.payload_digest_sha256),
    out_of_order_event_time_preserved: true,
    persistence_performed: false,
    hard_boundaries: {
      bill_generated: false,
      price_applied: false,
      stripe_object_created: false,
      provider_write: false,
      money_movement: false,
    },
  };
  return { ...body, rollup_digest_sha256: await sha256Hex(canonicalize(body)) };
}

async function advisorPreview(input: JsonObject) {
  const simulation = isObject(input.simulation_summary) ? input.simulation_summary : {};
  const meters = Array.isArray(input.meter_snapshots) ? input.meter_snapshots : [];
  const risks = Array.isArray(input.risk_signals) ? input.risk_signals : [];
  const proposals: JsonObject[] = [];
  const scenarioCount = Number(simulation.scenario_count ?? 0);
  const reasons = isObject(simulation.reason_counts) ? simulation.reason_counts : {};
  let unknownCount = 0;
  for (const [reason, count] of Object.entries(reasons)) {
    if (reason.includes("UNKNOWN") || reason.includes("UNRESOLVED")) unknownCount += Number(count ?? 0);
  }
  if (scenarioCount > 0 && unknownCount / scenarioCount >= 0.01) {
    proposals.push({
      proposal_type: "RESOLVE_MISSING_POLICY_INPUTS",
      priority_score: Math.min(100, Math.round(55 + (unknownCount / scenarioCount) * 100)),
      rationale_code: "SIMULATION_UNKNOWN_RATIO_ABOVE_THRESHOLD",
      evidence: { unknown_count: unknownCount, scenario_count: scenarioCount },
      auto_apply: false,
    });
  }
  for (const value of meters) {
    if (!isObject(value)) continue;
    const meterId = String(value.meter_id ?? "unknown");
    const limit = value.limit;
    const used = Number(value.used ?? 0);
    if (limit === 0 && used > 0) {
      proposals.push({
        proposal_type: "REVIEW_ZERO_LIMIT",
        priority_score: 95,
        rationale_code: "OBSERVED_USAGE_CONFLICTS_WITH_ZERO_LIMIT",
        evidence: { meter_id: meterId, limit, used },
        auto_apply: false,
      });
    } else if (Number.isSafeInteger(limit) && Number(limit) > 0 && used / Number(limit) >= 0.8) {
      proposals.push({
        proposal_type: "REVIEW_LIMIT_SATURATION",
        priority_score: Math.min(94, Math.round(60 + (used / Number(limit)) * 35)),
        rationale_code: "BOUNDED_LIMIT_SATURATION_ABOVE_80_PERCENT",
        evidence: { meter_id: meterId, limit, used },
        auto_apply: false,
      });
    } else if (limit === null) {
      proposals.push({
        proposal_type: "RESOLVE_MISSING_POLICY_INPUTS",
        priority_score: 90,
        rationale_code: "METER_LIMIT_UNRESOLVED_FAIL_CLOSED",
        evidence: { meter_id: meterId, limit: null, used },
        auto_apply: false,
      });
    }
  }
  for (const value of risks) {
    if (!isObject(value)) continue;
    if (value.signal_type === "UNMAPPED_CONSEQUENTIAL_ACTION") {
      proposals.push({
        proposal_type: "ADD_EXPLICIT_DENY_RULE",
        priority_score: 100,
        rationale_code: "CONSEQUENTIAL_ACTION_LACKS_EXPLICIT_RULE",
        evidence: { action: String(value.action ?? "unknown") },
        auto_apply: false,
      });
    }
    if (value.signal_type === "UNCOVERED_RULE_PATH") {
      proposals.push({
        proposal_type: "ADD_SCENARIO_COVERAGE",
        priority_score: 75,
        rationale_code: "RULE_PATH_HAS_NO_TEST_SCENARIO",
        evidence: { rule_id: String(value.rule_id ?? "unknown") },
        auto_apply: false,
      });
    }
  }
  if (proposals.length === 0) {
    proposals.push({
      proposal_type: "NO_CHANGE_RECOMMENDED",
      priority_score: 1,
      rationale_code: "NO_ACTIONABLE_GAP_IN_SUPPLIED_EVIDENCE",
      evidence: { scenario_count: scenarioCount },
      auto_apply: false,
    });
  }
  proposals.sort((a, b) => Number(b.priority_score) - Number(a.priority_score) || String(a.proposal_type).localeCompare(String(b.proposal_type)));
  const ranked = proposals.map((proposal, index) => ({ rank: index + 1, ...proposal }));
  const body = {
    contract: "ct.wallet.algorithmic-policy-advisor.v1",
    algorithm_id: "ct.algorithm.chlom-wallet.aura.v1",
    proposal_state: "SUGGESTION_ONLY",
    model_provider: null,
    external_model_call_performed: false,
    proposals: ranked,
    authority: {
      auto_apply: false,
      policy_activation: false,
      effective_offer_change: false,
      provider_write: false,
      rights_grant: false,
      chain_broadcast: false,
      money_movement: false,
      phase_advancement: false,
    },
  };
  return { ...body, proposal_digest_sha256: await sha256Hex(canonicalize(body)) };
}

Deno.serve(async (req: Request) => {
  const origin = allowedOrigin(req);
  if (!origin) return new Response(JSON.stringify({ ok: false, error: "origin_not_allowed" }), { status: 403, headers: responseHeaders(ORIGIN) });
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: responseHeaders(origin) });

  let subject: string;
  try {
    subject = jwtSubject(req);
  } catch (error) {
    return json(req, { ok: false, error: error instanceof Error ? error.message : "authorization_failed" }, 401);
  }

  if (req.method === "GET") {
    return json(req, {
      ok: true,
      service_id: SERVICE_ID,
      agent_id: AGENT_ID,
      state: STATE,
      subject_digest_sha256: await sha256Hex(`subject|${subject}`),
      capabilities: ["budget-preview", "policy-preview", "usage-rollup-preview", "advisor-preview"],
      algorithms: ["CWPX", "MARC", "QERA", "SAGE", "AURA"],
      external_model_call: false,
      persistence: false,
      effective_policy: false,
      price_calculation: false,
      billing: false,
      provider_write: false,
      production_rights_grant: false,
      credential_activation: false,
      chain_broadcast: false,
      custody: false,
      token_issuance: false,
      money_movement: false,
      phase_advancement: false,
    });
  }

  if (req.method !== "POST") return json(req, { ok: false, error: "method_not_allowed" }, 405);
  const raw = await req.text();
  if (raw.length > MAX_BODY_BYTES) return json(req, { ok: false, error: "payload_too_large" }, 413);
  let body: JsonObject;
  try {
    body = JSON.parse(raw || "{}");
  } catch {
    return json(req, { ok: false, error: "invalid_json" }, 400);
  }
  const action = String(body.action ?? "");
  const input = isObject(body.input) ? body.input : {};
  try {
    let result: unknown;
    if (action === "budget-preview") result = await budgetPreview(input);
    else if (action === "policy-preview") result = await policyPreview(input);
    else if (action === "usage-rollup-preview") result = await usageRollupPreview(input);
    else if (action === "advisor-preview") result = await advisorPreview(input);
    else return json(req, { ok: false, error: "unsupported_action" }, 400);

    return json(req, {
      ok: true,
      state: STATE,
      action,
      result,
      runtime_boundaries: {
        external_network_call: false,
        external_model_call: false,
        persistence: false,
        effective_policy: false,
        provider_write: false,
        production_rights_grant: false,
        credential_activation: false,
        chain_broadcast: false,
        custody: false,
        token_issuance: false,
        money_movement: false,
        effective_price_publication: false,
        checkout_activation: false,
        phase_advancement: false,
        merge_authorized: false,
      },
    });
  } catch (error) {
    const code = error instanceof Error ? error.message : "policy_lab_failed";
    return json(req, {
      ok: false,
      state: "HOLD",
      error: code,
      runtime_boundaries: {
        external_network_call: false,
        external_model_call: false,
        persistence: false,
        effective_policy: false,
        provider_write: false,
        production_rights_grant: false,
        credential_activation: false,
        chain_broadcast: false,
        custody: false,
        token_issuance: false,
        money_movement: false,
        effective_price_publication: false,
        checkout_activation: false,
        phase_advancement: false,
        merge_authorized: false,
      },
    }, 422);
  }
});
