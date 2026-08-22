import {
  assertAsciiIdentifier,
  assertHex64,
  assertIsoTimestamp,
  canonicalize,
  frameAscii,
  secretShapePresent,
  sha256Hex,
} from '../common/canonical-json.mjs';

// PWC v1 — CHLOM Portable Wallet Capsule.
// CONTROLLED TEST: exports provider-neutral commitments and import plans only. No credential export, provider mutation, or money movement.

export const PORTABLE_WALLET_SCHEMA_VERSION = '1.0.0';
const CAPSULE_DOMAIN = 'CHLOM:PWC:CAPSULE:v1';
const EVENT_KEYS = new Set([
  'event_seq', 'event_type', 'asset_code', 'amount_minor', 'provider_alias', 'schedule_ref',
  'entitlement_ref', 'occurred_at', 'payload_digest', 'previous_chain_hash', 'chain_hash',
]);
const PROVIDER_ALIAS_KEYS = new Set(['alias_id', 'provider_class', 'adapter_contract', 'state']);
const ENTITLEMENT_KEYS = new Set(['entitlement_ref', 'asset_ref', 'terms_digest', 'state_commitment']);
const PROVIDER_STATES = new Set(['candidate', 'active', 'retired']);
const ENTITLEMENT_STATES = new Set(['candidate', 'active', 'held', 'expired', 'revoked', 'superseded']);

function safeIdentifier(value, code, maxLength = 160) {
  const result = assertAsciiIdentifier(value, code, maxLength);
  if (secretShapePresent(result)) throw new Error('portable_wallet_secret_shape_detected');
  return result;
}

function rejectUnknownKeys(value, allowed, prefix) {
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${prefix}_key_not_allowed:${key}`);
}

function normalizeProviderAlias(alias) {
  if (!alias || typeof alias !== 'object' || Array.isArray(alias)) throw new Error('portable_provider_alias_object_required');
  rejectUnknownKeys(alias, PROVIDER_ALIAS_KEYS, 'portable_provider_alias');
  const alias_id = safeIdentifier(alias.alias_id, 'portable_provider_alias_id_invalid', 96);
  const provider_class = safeIdentifier(alias.provider_class, 'portable_provider_class_invalid', 96);
  const adapter_contract = safeIdentifier(alias.adapter_contract, 'portable_adapter_contract_invalid', 160);
  if (!PROVIDER_STATES.has(alias.state)) throw new Error('portable_provider_alias_state_invalid');
  return { alias_id, provider_class, adapter_contract, state: alias.state };
}

function normalizeEvent(event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) throw new Error('portable_event_object_required');
  rejectUnknownKeys(event, EVENT_KEYS, 'portable_event');
  if (!Number.isSafeInteger(event.event_seq) || event.event_seq < 1) throw new Error('portable_event_seq_invalid');
  const event_type = safeIdentifier(event.event_type, 'portable_event_type_invalid', 128);
  const asset_code = event.asset_code == null ? null : safeIdentifier(event.asset_code, 'portable_asset_code_invalid', 32);
  const amount_minor = event.amount_minor == null ? null : event.amount_minor;
  if (amount_minor !== null && (!Number.isSafeInteger(amount_minor) || amount_minor < 0)) throw new Error('portable_amount_minor_invalid');
  const provider_alias = event.provider_alias == null ? null : safeIdentifier(event.provider_alias, 'portable_provider_alias_invalid', 96);
  const schedule_ref = event.schedule_ref == null ? null : safeIdentifier(event.schedule_ref, 'portable_schedule_ref_invalid', 160);
  const entitlement_ref = event.entitlement_ref == null ? null : safeIdentifier(event.entitlement_ref, 'portable_entitlement_ref_invalid', 160);
  const occurred_at = assertIsoTimestamp(event.occurred_at, 'portable_occurred_at_invalid');
  const payload_digest = assertHex64(event.payload_digest, 'portable_payload_digest_invalid');
  const previous_chain_hash = event.previous_chain_hash == null ? null : assertHex64(event.previous_chain_hash, 'portable_previous_chain_hash_invalid');
  const chain_hash = assertHex64(event.chain_hash, 'portable_chain_hash_invalid');
  return {
    event_seq: event.event_seq,
    event_type,
    asset_code,
    amount_minor,
    provider_alias,
    schedule_ref,
    entitlement_ref,
    occurred_at,
    payload_digest,
    previous_chain_hash,
    chain_hash,
  };
}

function normalizeEntitlement(entitlement) {
  if (!entitlement || typeof entitlement !== 'object' || Array.isArray(entitlement)) throw new Error('portable_entitlement_object_required');
  rejectUnknownKeys(entitlement, ENTITLEMENT_KEYS, 'portable_entitlement');
  const entitlement_ref = safeIdentifier(entitlement.entitlement_ref, 'portable_entitlement_ref_invalid', 160);
  const asset_ref = safeIdentifier(entitlement.asset_ref, 'portable_entitlement_asset_ref_invalid', 160);
  const terms_digest = assertHex64(entitlement.terms_digest, 'portable_entitlement_terms_digest_invalid');
  if (!ENTITLEMENT_STATES.has(entitlement.state_commitment)) throw new Error('portable_entitlement_state_invalid');
  return { entitlement_ref, asset_ref, terms_digest, state_commitment: entitlement.state_commitment };
}

export function verifyPortableEventChain(events) {
  if (!Array.isArray(events) || events.length < 1 || events.length > 100_000) throw new Error('portable_event_count_invalid');
  const normalized = events.map(normalizeEvent).sort((a, b) => a.event_seq - b.event_seq);
  for (let index = 0; index < normalized.length; index++) {
    const event = normalized[index];
    if (event.event_seq !== index + 1) throw new Error('portable_event_sequence_gap');
    const expectedPrevious = index === 0 ? null : normalized[index - 1].chain_hash;
    if (event.previous_chain_hash !== expectedPrevious) throw new Error('portable_previous_chain_hash_mismatch');
    const expectedChainHash = sha256Hex(`${expectedPrevious ?? 'GENESIS'}|${event.payload_digest}`);
    if (event.chain_hash !== expectedChainHash) throw new Error('portable_chain_hash_mismatch');
  }
  return {
    valid: true,
    events: normalized,
    event_count: normalized.length,
    chain_head: normalized.at(-1).chain_hash,
  };
}

export function buildPortableWalletCapsule({
  capsule_id,
  wallet_stable_id,
  issuer_did,
  created_at,
  source_environment,
  provider_aliases,
  events,
  entitlement_commitments = [],
  proof_capsule_ref = null,
}) {
  const normalizedCapsuleId = safeIdentifier(capsule_id, 'portable_capsule_id_invalid', 160);
  const normalizedWalletId = safeIdentifier(wallet_stable_id, 'portable_wallet_stable_id_invalid', 160);
  const normalizedIssuerDid = safeIdentifier(issuer_did, 'portable_issuer_did_invalid', 220);
  const normalizedCreatedAt = assertIsoTimestamp(created_at, 'portable_created_at_invalid');
  const normalizedEnvironment = safeIdentifier(source_environment, 'portable_source_environment_invalid', 96);
  if (!Array.isArray(provider_aliases) || provider_aliases.length > 128) throw new Error('portable_provider_alias_count_invalid');
  const aliases = provider_aliases.map(normalizeProviderAlias).sort((a, b) => a.alias_id.localeCompare(b.alias_id));
  for (let index = 1; index < aliases.length; index++) {
    if (aliases[index - 1].alias_id === aliases[index].alias_id) throw new Error('portable_duplicate_provider_alias');
  }
  const aliasIds = new Set(aliases.map((alias) => alias.alias_id));
  const chain = verifyPortableEventChain(events);
  for (const event of chain.events) {
    if (event.provider_alias && !aliasIds.has(event.provider_alias)) throw new Error('portable_event_provider_alias_missing');
  }
  const entitlements = entitlement_commitments.map(normalizeEntitlement).sort((a, b) => a.entitlement_ref.localeCompare(b.entitlement_ref));
  for (let index = 1; index < entitlements.length; index++) {
    if (entitlements[index - 1].entitlement_ref === entitlements[index].entitlement_ref) throw new Error('portable_duplicate_entitlement_ref');
  }
  const normalizedProofRef = proof_capsule_ref == null ? null : safeIdentifier(proof_capsule_ref, 'portable_proof_capsule_ref_invalid', 160);
  const core = {
    schema_version: PORTABLE_WALLET_SCHEMA_VERSION,
    capsule_id: normalizedCapsuleId,
    wallet_stable_id: normalizedWalletId,
    issuer_did: normalizedIssuerDid,
    created_at: normalizedCreatedAt,
    source_environment: normalizedEnvironment,
    event_count: chain.event_count,
    chain_head: chain.chain_head,
    provider_aliases: aliases,
    events: chain.events,
    entitlement_commitments: entitlements,
    proof_capsule_ref: normalizedProofRef,
    source_payload_body_included: false,
    provider_credentials_included: false,
    import_execution_state: 'HOLD',
    provider_write: false,
    money_movement: false,
    rights_granted: false,
  };
  if (secretShapePresent(core)) throw new Error('portable_wallet_secret_shape_detected');
  const capsule_digest = sha256Hex(frameAscii([CAPSULE_DOMAIN, sha256Hex(canonicalize(core))]));
  return { ...core, capsule_digest };
}

export function verifyPortableWalletCapsule(capsule) {
  if (!capsule || typeof capsule !== 'object' || Array.isArray(capsule)) throw new Error('portable_capsule_required');
  if (capsule.schema_version !== PORTABLE_WALLET_SCHEMA_VERSION) throw new Error('portable_schema_version_unsupported');
  if (capsule.source_payload_body_included !== false || capsule.provider_credentials_included !== false || capsule.import_execution_state !== 'HOLD') {
    throw new Error('portable_controlled_test_boundary_invalid');
  }
  if (capsule.provider_write !== false || capsule.money_movement !== false || capsule.rights_granted !== false) {
    throw new Error('portable_side_effect_boundary_invalid');
  }
  const rebuilt = buildPortableWalletCapsule({
    capsule_id: capsule.capsule_id,
    wallet_stable_id: capsule.wallet_stable_id,
    issuer_did: capsule.issuer_did,
    created_at: capsule.created_at,
    source_environment: capsule.source_environment,
    provider_aliases: capsule.provider_aliases,
    events: capsule.events,
    entitlement_commitments: capsule.entitlement_commitments,
    proof_capsule_ref: capsule.proof_capsule_ref,
  });
  return {
    valid: rebuilt.capsule_digest === capsule.capsule_digest,
    digest_valid: rebuilt.capsule_digest === capsule.capsule_digest,
    chain_valid: rebuilt.chain_head === capsule.chain_head,
    computed_capsule_digest: rebuilt.capsule_digest,
    computed_chain_head: rebuilt.chain_head,
    provider_credentials_included: false,
    source_payload_body_included: false,
  };
}

export function planProviderRemap(capsule, { alias_id, new_adapter_ref, target_environment }) {
  const verification = verifyPortableWalletCapsule(capsule);
  if (!verification.valid) throw new Error('portable_capsule_verification_failed');
  const aliasId = safeIdentifier(alias_id, 'portable_provider_alias_id_invalid', 96);
  const alias = capsule.provider_aliases.find((entry) => entry.alias_id === aliasId);
  if (!alias) throw new Error('portable_provider_alias_not_found');
  const adapter = safeIdentifier(new_adapter_ref, 'portable_new_adapter_ref_invalid', 160);
  const environment = safeIdentifier(target_environment, 'portable_target_environment_invalid', 96);
  if (!['controlled_test', 'staging_candidate'].includes(environment)) throw new Error('portable_target_environment_not_allowed');
  return {
    state: 'REMAP_PLAN_HOLD',
    capsule_id: capsule.capsule_id,
    wallet_stable_id: capsule.wallet_stable_id,
    alias_id: aliasId,
    from_adapter_ref: alias.adapter_contract,
    to_adapter_ref: adapter,
    target_environment: environment,
    stable_wallet_id_preserved: true,
    event_chain_preserved: true,
    provider_write: false,
    credentials_copied: false,
    money_movement: false,
    rights_mutation: false,
  };
}
