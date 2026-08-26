import crypto from 'node:crypto';

export const DISPOSITION_RANK = Object.freeze({ ECAC: 0, HOLD: 1, DENY: 2 });

export function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonicalize(value[k])]));
  }
  return value;
}

export function sha256(value) {
  const body = typeof value === 'string' ? value : JSON.stringify(canonicalize(value));
  return crypto.createHash('sha256').update(body).digest('hex');
}

export function strictest(...states) {
  return states.reduce((a, b) => DISPOSITION_RANK[b] > DISPOSITION_RANK[a] ? b : a, 'ECAC');
}

export function validateBudgetSemantics(value) {
  if (value === null || value === undefined) return { disposition: 'HOLD', meaning: 'UNRESOLVED_FAIL_CLOSED' };
  if (!Number.isInteger(value)) return { disposition: 'DENY', meaning: 'INVALID_NON_INTEGER' };
  if (value === -1) return { disposition: 'ECAC', meaning: 'UNLIMITED_CROWNTHRIVE_LOCAL_MONTHLY_CEILING' };
  if (value === 0) return { disposition: 'ECAC', meaning: 'ZERO_REQUESTS_PERMITTED' };
  if (value > 0) return { disposition: 'ECAC', meaning: `EXACT_${value}_REQUESTS_PER_MONTH` };
  return { disposition: 'DENY', meaning: 'INVALID_NEGATIVE_VALUE' };
}

export function generateFactoryProjection(catalog, domains) {
  if (!catalog || catalog.state !== 'CONTROLLED_TEST') throw new Error('catalog_not_controlled_test');
  const activeDomains = domains.filter(d => d.active !== false).sort((a, b) => a.domain_slug.localeCompare(b.domain_slug));
  const assets = [];
  for (const domain of activeDomains) {
    for (const blueprint of catalog.blueprints) {
      const asset = {
        asset_id: `ct.asset.chlom-wallet.continuity.${domain.domain_slug}.${blueprint.slug}.v1`,
        asset_type: blueprint.type,
        canonical_name: `${domain.domain_name} — ${blueprint.name}`,
        semantic_version: '1.0.0',
        lifecycle_state: 'CONTROLLED_TEST',
        factory_generation_binding: catalog.factory_generation_binding,
        factory_domain_slug: domain.domain_slug,
        public_contract: blueprint.public_contract === true,
        candidate_only: true,
        authority_granted: false,
        production_activation: false,
        provider_write: false,
        money_movement: false,
        rights_grant: false,
        chain_broadcast: false,
        checkout_enabled: false
      };
      asset.asset_sha256 = sha256(asset);
      assets.push(asset);
    }
  }
  return assets;
}

export function evaluateEvidenceExpiry({ now, observed_at, ttl_seconds, explicit_state = 'PASS' }) {
  if (explicit_state === 'DENY') return { disposition: 'DENY', reason: 'explicit_deny' };
  if (!observed_at || !Number.isFinite(ttl_seconds) || ttl_seconds <= 0) return { disposition: 'HOLD', reason: 'missing_freshness_contract' };
  const age = (new Date(now).getTime() - new Date(observed_at).getTime()) / 1000;
  if (!Number.isFinite(age) || age < 0) return { disposition: 'HOLD', reason: 'invalid_or_future_timestamp' };
  if (age > ttl_seconds) return { disposition: 'HOLD', reason: 'stale_evidence', age_seconds: Math.floor(age) };
  if (explicit_state === 'HOLD') return { disposition: 'HOLD', reason: 'explicit_hold' };
  return { disposition: 'ECAC', reason: 'fresh_evidence', age_seconds: Math.floor(age) };
}

export function evaluateHeartbeat({ now, last_heartbeat_at, next_heartbeat_due_at, heartbeat_state }) {
  if (!last_heartbeat_at || !next_heartbeat_due_at) return { disposition: 'HOLD', derived_state: 'MISSING' };
  if (heartbeat_state === 'DENY' || heartbeat_state === 'REVOKED') return { disposition: 'DENY', derived_state: heartbeat_state };
  if (new Date(now).getTime() > new Date(next_heartbeat_due_at).getTime()) return { disposition: 'HOLD', derived_state: 'STALE' };
  return { disposition: heartbeat_state === 'HOLD' ? 'HOLD' : 'ECAC', derived_state: 'FRESH' };
}

export function evaluateOracleObservation({ connection_state, read_only, observed_at, ttl_seconds, payload_digest, now, source_confidence = 1 }) {
  if (read_only !== true) return { disposition: 'DENY', reason: 'oracle_not_read_only' };
  if (connection_state === 'DENY' || connection_state === 'REVOKED') return { disposition: 'DENY', reason: 'oracle_connection_denied' };
  if (!payload_digest || !/^[a-f0-9]{64}$/i.test(payload_digest)) return { disposition: 'HOLD', reason: 'missing_payload_digest' };
  const freshness = evaluateEvidenceExpiry({ now, observed_at, ttl_seconds });
  if (source_confidence < 0 || source_confidence > 1) return { disposition: 'DENY', reason: 'invalid_confidence' };
  if (source_confidence < 0.75) return { disposition: strictest(freshness.disposition, 'HOLD'), reason: 'low_source_confidence' };
  return { disposition: freshness.disposition, reason: freshness.reason };
}

export function deriveContinuityDisposition(input) {
  const states = [
    input.profile_state ?? 'HOLD',
    input.execution_envelope_state ?? 'HOLD',
    input.source_head_match === true ? 'ECAC' : 'HOLD',
    input.identity_pin_match === true ? 'ECAC' : 'HOLD',
    input.heartbeat_state ?? 'HOLD',
    input.dependency_state ?? 'HOLD',
    input.oracle_state ?? 'HOLD',
    input.rollback_verified === true ? 'ECAC' : 'HOLD',
    input.security_state ?? 'HOLD'
  ];
  if (input.forbidden_boundary === true || input.authority_escalation === true || input.secret_exposure === true) states.push('DENY');
  return strictest(...states);
}

export function continuityRiskFeatures(input) {
  return {
    stale_fraction: Number(input.stale_fraction ?? 0),
    dependency_drift: Number(input.dependency_drift ?? 0),
    oracle_disagreement: Number(input.oracle_disagreement ?? 0),
    rollback_gap: Number(input.rollback_gap ?? 0),
    source_head_drift: Number(input.source_head_drift ?? 0),
    heartbeat_miss_rate: Number(input.heartbeat_miss_rate ?? 0),
    security_findings: Number(input.security_findings ?? 0),
    unresolved_handoffs: Number(input.unresolved_handoffs ?? 0)
  };
}

export function mlAdvisoryScore(raw) {
  const f = continuityRiskFeatures(raw);
  const weights = {
    stale_fraction: 1.7,
    dependency_drift: 1.3,
    oracle_disagreement: 1.5,
    rollback_gap: 2.0,
    source_head_drift: 2.2,
    heartbeat_miss_rate: 1.4,
    security_findings: 0.35,
    unresolved_handoffs: 0.25
  };
  let z = -2.4;
  for (const [k, w] of Object.entries(weights)) z += w * f[k];
  const probability = 1 / (1 + Math.exp(-z));
  const band = probability >= 0.8 ? 'CRITICAL' : probability >= 0.55 ? 'HIGH' : probability >= 0.3 ? 'MEDIUM' : 'LOW';
  return {
    model_id: 'ct.ml.chlom-wallet.continuity-risk-advisory.v1',
    probability: Number(probability.toFixed(6)),
    risk_band: band,
    advisory_only: true,
    final_authority: false,
    features: f,
    score_sha256: sha256({ f, weights, probability: Number(probability.toFixed(6)) })
  };
}

export function dueAutomation(definition, now) {
  if (definition.enabled !== true) return false;
  if (definition.next_due_at == null) return true;
  return new Date(now).getTime() >= new Date(definition.next_due_at).getTime();
}

export function planRecovery({ incident_state, rollback_verified, backup_verified, independent_review_state, source_head_match }) {
  const disposition = strictest(
    incident_state === 'DENY' ? 'DENY' : 'ECAC',
    rollback_verified ? 'ECAC' : 'HOLD',
    backup_verified ? 'ECAC' : 'HOLD',
    independent_review_state ?? 'HOLD',
    source_head_match ? 'ECAC' : 'HOLD'
  );
  return {
    disposition,
    mode: disposition === 'ECAC' ? 'RECOVERY_PLAN_ELIGIBLE' : disposition,
    provider_write: false,
    money_movement: false,
    rights_grant: false,
    chain_broadcast: false,
    automatic_destructive_action: false
  };
}
