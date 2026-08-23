import { canonicalize, sha256Hex } from './policy-engine.mjs';

export const LIMIT_SEMANTICS_VERSION = 'ct.limit-semantics.founder-override.v1';

function assertSafeNonnegativeInteger(value, code) {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(code);
}

export function evaluateUsageBudget({ limit, used, requested }) {
  assertSafeNonnegativeInteger(used, 'usage_used_invalid');
  assertSafeNonnegativeInteger(requested, 'usage_requested_invalid');
  let disposition;
  let reasonCode;
  let remaining = null;
  if (limit === null || limit === undefined) {
    disposition = 'HOLD';
    reasonCode = 'LIMIT_UNRESOLVED_FAIL_CLOSED';
  } else if (!Number.isSafeInteger(limit)) {
    disposition = 'DENY';
    reasonCode = 'LIMIT_NOT_INTEGER';
  } else if (limit === -1) {
    disposition = 'ALLOW';
    reasonCode = 'UNLIMITED_LOCAL_LIMIT';
  } else if (limit < -1) {
    disposition = 'DENY';
    reasonCode = 'LIMIT_NEGATIVE_INVALID';
  } else if (limit === 0) {
    if (requested === 0) {
      disposition = 'ALLOW';
      reasonCode = 'ZERO_REQUEST_WITH_ZERO_LIMIT';
      remaining = 0;
    } else {
      disposition = 'DENY';
      reasonCode = 'ZERO_LIMIT_DENIES_USAGE';
      remaining = 0;
    }
  } else {
    const projected = used + requested;
    remaining = Math.max(limit - used, 0);
    if (!Number.isSafeInteger(projected)) {
      disposition = 'DENY';
      reasonCode = 'USAGE_INTEGER_OVERFLOW';
    } else if (projected <= limit) {
      disposition = 'ALLOW';
      reasonCode = 'WITHIN_EXACT_LIMIT';
      remaining = limit - projected;
    } else {
      disposition = 'DENY';
      reasonCode = 'EXACT_LIMIT_EXCEEDED';
    }
  }
  const body = {
    contract: 'ct.wallet.usage-budget-decision.v1',
    semantics_version: LIMIT_SEMANTICS_VERSION,
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
  return { ...body, decision_digest_sha256: sha256Hex(canonicalize(body)) };
}

function validateUsageEvent(event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) throw new Error('usage_event_object_required');
  if (typeof event.event_id !== 'string' || !/^ctue_[A-Za-z0-9_-]{12,120}$/.test(event.event_id)) throw new Error('usage_event_id_invalid');
  if (typeof event.idempotency_key !== 'string' || !/^ctik_[A-Za-z0-9_-]{12,160}$/.test(event.idempotency_key)) throw new Error('usage_idempotency_key_invalid');
  if (typeof event.tenant_ref !== 'string' || event.tenant_ref.length < 3 || event.tenant_ref.length > 180) throw new Error('usage_tenant_ref_invalid');
  if (typeof event.wallet_stable_id !== 'string' || event.wallet_stable_id.length < 3 || event.wallet_stable_id.length > 220) throw new Error('usage_wallet_id_invalid');
  if (typeof event.meter_id !== 'string' || !/^ct[.]meter[.][a-z0-9._-]{3,180}$/.test(event.meter_id)) throw new Error('usage_meter_id_invalid');
  assertSafeNonnegativeInteger(event.quantity, 'usage_quantity_invalid');
  const occurredAt = new Date(event.occurred_at);
  if (Number.isNaN(occurredAt.getTime())) throw new Error('usage_occurred_at_invalid');
  if (typeof event.source_ref !== 'string' || event.source_ref.length < 3 || event.source_ref.length > 500) throw new Error('usage_source_ref_invalid');
  const payloadDigest = event.payload_digest_sha256 ?? sha256Hex(canonicalize({
    tenant_ref: event.tenant_ref,
    wallet_stable_id: event.wallet_stable_id,
    meter_id: event.meter_id,
    quantity: event.quantity,
    occurred_at: occurredAt.toISOString(),
    source_ref: event.source_ref,
  }));
  if (!/^[0-9a-f]{64}$/.test(payloadDigest)) throw new Error('usage_payload_digest_invalid');
  return {
    event_id: event.event_id,
    idempotency_key: event.idempotency_key,
    tenant_ref: event.tenant_ref,
    wallet_stable_id: event.wallet_stable_id,
    meter_id: event.meter_id,
    quantity: event.quantity,
    occurred_at: occurredAt.toISOString(),
    source_ref: event.source_ref,
    payload_digest_sha256: payloadDigest,
    metadata: event.metadata && typeof event.metadata === 'object' && !Array.isArray(event.metadata) ? event.metadata : {},
  };
}

export function calendarMonthWindow(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) throw new Error('window_timestamp_invalid');
  const start = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  const end = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1));
  return { window_start: start.toISOString(), window_end: end.toISOString() };
}

export class UsageLedger {
  #eventsByIdempotency = new Map();
  #events = [];

  record(event) {
    const normalized = validateUsageEvent(event);
    const prior = this.#eventsByIdempotency.get(normalized.idempotency_key);
    if (prior) {
      if (prior.payload_digest_sha256 !== normalized.payload_digest_sha256) throw new Error('usage_idempotency_collision');
      return {
        state: 'DUPLICATE',
        event_id: prior.event_id,
        idempotency_key: prior.idempotency_key,
        payload_digest_sha256: prior.payload_digest_sha256,
        provider_write: false,
        billing_charge_created: false,
        money_movement: false,
      };
    }
    this.#eventsByIdempotency.set(normalized.idempotency_key, normalized);
    this.#events.push(normalized);
    return {
      state: 'RECORDED_TEST',
      event_id: normalized.event_id,
      idempotency_key: normalized.idempotency_key,
      payload_digest_sha256: normalized.payload_digest_sha256,
      provider_write: false,
      billing_charge_created: false,
      money_movement: false,
    };
  }

  events() {
    return this.#events.map((event) => structuredClone(event));
  }

  rollup({ tenant_ref, wallet_stable_id, meter_id, window_start, window_end }) {
    const start = new Date(window_start);
    const end = new Date(window_end);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start >= end) throw new Error('usage_rollup_window_invalid');
    const matched = this.#events
      .filter((event) => event.tenant_ref === tenant_ref && event.wallet_stable_id === wallet_stable_id && event.meter_id === meter_id)
      .filter((event) => {
        const timestamp = new Date(event.occurred_at);
        return timestamp >= start && timestamp < end;
      })
      .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at) || a.event_id.localeCompare(b.event_id));
    const quantity = matched.reduce((total, event) => total + event.quantity, 0);
    if (!Number.isSafeInteger(quantity)) throw new Error('usage_rollup_integer_overflow');
    const body = {
      contract: 'ct.wallet.usage-rollup-snapshot.v1',
      tenant_ref,
      wallet_stable_id,
      meter_id,
      window_start: start.toISOString(),
      window_end: end.toISOString(),
      event_count: matched.length,
      quantity,
      event_ids: matched.map((event) => event.event_id),
      event_payload_digests: matched.map((event) => event.payload_digest_sha256),
      out_of_order_event_time_preserved: true,
      hard_boundaries: {
        bill_generated: false,
        price_applied: false,
        stripe_object_created: false,
        provider_write: false,
        money_movement: false,
      },
    };
    return { ...body, rollup_digest_sha256: sha256Hex(canonicalize(body)) };
  }
}

export function validateLicenseCandidate(candidate) {
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) throw new Error('license_candidate_object_required');
  if (typeof candidate.license_id !== 'string' || !/^ct[.]license-candidate[.][a-z0-9._-]{3,180}$/.test(candidate.license_id)) throw new Error('license_candidate_id_invalid');
  if (candidate.state !== 'CONTROLLED_TEST') throw new Error('license_candidate_state_invalid');
  if (!Array.isArray(candidate.pallets) || candidate.pallets.length === 0 || new Set(candidate.pallets).size !== candidate.pallets.length) throw new Error('license_candidate_pallets_invalid');
  if (!candidate.limits || typeof candidate.limits !== 'object' || Array.isArray(candidate.limits)) throw new Error('license_candidate_limits_required');
  for (const [meterId, limit] of Object.entries(candidate.limits)) {
    if (!/^ct[.]meter[.][a-z0-9._-]{3,180}$/.test(meterId)) throw new Error('license_meter_id_invalid');
    if (limit !== null && (!Number.isSafeInteger(limit) || limit < -1)) throw new Error('license_limit_invalid');
  }
  const requiredFalse = ['effective_offer', 'public_price_authorized', 'stripe_objects_created', 'checkout_enabled', 'money_movement', 'rights_grant', 'chain_broadcast'];
  for (const key of requiredFalse) if (candidate[key] !== false) throw new Error(`license_candidate_boundary_must_be_false:${key}`);
  const body = {
    contract: 'ct.wallet.license-package-candidate.v1',
    license_id: candidate.license_id,
    semantic_version: candidate.semantic_version,
    state: candidate.state,
    pallets: [...candidate.pallets].sort(),
    limits: Object.fromEntries(Object.entries(candidate.limits).sort(([a], [b]) => a.localeCompare(b))),
    support_class: candidate.support_class ?? 'UNSPECIFIED',
    effective_offer: false,
    public_price_authorized: false,
    stripe_objects_created: false,
    checkout_enabled: false,
    money_movement: false,
    rights_grant: false,
    chain_broadcast: false,
  };
  return { ...body, license_digest_sha256: sha256Hex(canonicalize(body)) };
}
