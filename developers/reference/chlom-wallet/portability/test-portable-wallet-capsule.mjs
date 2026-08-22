import assert from 'node:assert/strict';
import {
  buildPortableWalletCapsule,
  planProviderRemap,
  verifyPortableWalletCapsule,
} from './portable-wallet-capsule.mjs';
import { canonicalize, secretShapePresent, sha256Hex } from '../common/canonical-json.mjs';

function appendSynthetic(previous, input) {
  const event_seq = previous ? previous.event_seq + 1 : 1;
  const payload = {
    wallet_id: 'ct.wallet.phase-c.synthetic',
    event_seq,
    event_type: input.event_type,
    asset_code: input.asset_code ?? null,
    amount_minor: input.amount_minor ?? null,
    provider: input.provider ?? null,
    provider_ref: input.provider_ref ?? null,
    schedule_ref: input.schedule_ref ?? null,
    entitlement_ref: input.entitlement_ref ?? null,
    correlation_id: input.correlation_id,
    idempotency_key: input.idempotency_key,
    occurred_at: input.occurred_at,
    metadata: input.metadata ?? {},
  };
  const payload_digest = sha256Hex(JSON.stringify(payload));
  const previous_chain_hash = previous?.chain_hash ?? null;
  const chain_hash = sha256Hex(`${previous_chain_hash ?? 'GENESIS'}|${payload_digest}`);
  return { ...payload, payload_digest, previous_chain_hash, chain_hash };
}

const fullEvents = [];
for (let index = 0; index < 2000; index++) {
  const provider = index % 3 === 0 ? 'stripe' : index % 3 === 1 ? 'chlom_rights' : null;
  fullEvents.push(appendSynthetic(fullEvents.at(-1), {
    event_type: index % 5 === 0 ? 'provider_payment_succeeded' : index % 5 === 1 ? 'entitlement_candidate' : index % 5 === 2 ? 'impact_obligation_calculated' : index % 5 === 3 ? 'reward_candidate' : 'proof_candidate',
    asset_code: index % 3 === 2 ? null : 'USD',
    amount_minor: index % 3 === 2 ? null : index * 17,
    provider,
    provider_ref: provider ? `restricted-provider-ref-${index}` : null,
    schedule_ref: index % 5 === 2 ? 'ct.schedule.synthetic.v1' : null,
    entitlement_ref: index % 5 === 1 ? `ct.entitlement.${index}` : null,
    correlation_id: `ct.correlation.${index}`,
    idempotency_key: `ct.idempotency.${index}`,
    occurred_at: `2026-08-22T${String(Math.floor(index / 3600) % 24).padStart(2, '0')}:${String(Math.floor(index / 60) % 60).padStart(2, '0')}:${String(index % 60).padStart(2, '0')}Z`,
    metadata: { private: 'not exported' },
  }));
}
const projection = fullEvents.map((event) => ({
  event_seq: event.event_seq,
  event_type: event.event_type,
  asset_code: event.asset_code,
  amount_minor: event.amount_minor,
  provider_alias: event.provider === 'stripe' ? 'fiat-primary' : event.provider === 'chlom_rights' ? 'rights-authority' : null,
  schedule_ref: event.schedule_ref,
  entitlement_ref: event.entitlement_ref,
  occurred_at: event.occurred_at,
  payload_digest: event.payload_digest,
  previous_chain_hash: event.previous_chain_hash,
  chain_hash: event.chain_hash,
}));

const input = {
  capsule_id: 'ct.pwc.phase-c.synthetic.001',
  wallet_stable_id: 'ct.wallet.phase-c.synthetic',
  issuer_did: 'did:chlom:phase-c-synthetic-issuer',
  created_at: '2026-08-22T07:15:00Z',
  source_environment: 'controlled_test',
  provider_aliases: [
    { alias_id: 'fiat-primary', provider_class: 'fiat_payment_processor', adapter_contract: 'ct.adapter.fiat.primary.v1', state: 'active' },
    { alias_id: 'rights-authority', provider_class: 'rights_authority', adapter_contract: 'ct.adapter.chlom-rights.v1', state: 'active' },
  ],
  events: projection,
  entitlement_commitments: [
    { entitlement_ref: 'ct.entitlement.1', asset_ref: 'ct.asset.walletkit', terms_digest: sha256Hex('terms-1'), state_commitment: 'active' },
    { entitlement_ref: 'ct.entitlement.6', asset_ref: 'ct.asset.proof-api', terms_digest: sha256Hex('terms-2'), state_commitment: 'held' },
  ],
  proof_capsule_ref: 'ct.harp.phase-c.synthetic.001',
};
const capsule = buildPortableWalletCapsule(input);
const reversed = buildPortableWalletCapsule({
  ...input,
  provider_aliases: [...input.provider_aliases].reverse(),
  events: [...input.events].reverse(),
  entitlement_commitments: [...input.entitlement_commitments].reverse(),
});
assert.equal(capsule.capsule_digest, reversed.capsule_digest);
assert.equal(capsule.chain_head, fullEvents.at(-1).chain_hash);
assert.equal(capsule.event_count, 2000);
assert.equal(capsule.source_payload_body_included, false);
assert.equal(capsule.provider_credentials_included, false);
assert.equal(capsule.provider_write, false);
assert.equal(capsule.money_movement, false);
assert.equal(capsule.rights_granted, false);
assert.equal(secretShapePresent(capsule), false);
assert.equal(canonicalize(capsule).includes('restricted-provider-ref'), false);
assert.equal(canonicalize(capsule).includes('correlation'), false);
assert.equal(canonicalize(capsule).includes('idempotency'), false);
assert.deepEqual(verifyPortableWalletCapsule(capsule), {
  valid: true,
  digest_valid: true,
  chain_valid: true,
  computed_capsule_digest: capsule.capsule_digest,
  computed_chain_head: capsule.chain_head,
  provider_credentials_included: false,
  source_payload_body_included: false,
});

const remap = planProviderRemap(capsule, {
  alias_id: 'fiat-primary',
  new_adapter_ref: 'ct.adapter.fiat.alternate-controlled-test.v1',
  target_environment: 'controlled_test',
});
assert.equal(remap.state, 'REMAP_PLAN_HOLD');
assert.equal(remap.stable_wallet_id_preserved, true);
assert.equal(remap.event_chain_preserved, true);
assert.equal(remap.provider_write, false);
assert.equal(remap.credentials_copied, false);
assert.equal(remap.money_movement, false);

const tamperedDigest = structuredClone(capsule);
tamperedDigest.events[100].payload_digest = sha256Hex('tampered-payload');
assert.throws(() => verifyPortableWalletCapsule(tamperedDigest), /portable_chain_hash_mismatch/);
const tamperedManifest = structuredClone(capsule);
tamperedManifest.entitlement_commitments[0].state_commitment = 'revoked';
assert.equal(verifyPortableWalletCapsule(tamperedManifest).valid, false);
const missingEvent = structuredClone(capsule);
missingEvent.events.splice(100, 1);
assert.throws(() => verifyPortableWalletCapsule(missingEvent), /portable_event_sequence_gap|portable_previous_chain_hash_mismatch/);
const missingAliasInput = structuredClone(input);
missingAliasInput.provider_aliases = [input.provider_aliases[1]];
assert.throws(() => buildPortableWalletCapsule(missingAliasInput), /portable_event_provider_alias_missing/);
const providerRefLeak = structuredClone(input);
providerRefLeak.events[0].provider_ref = 'restricted';
assert.throws(() => buildPortableWalletCapsule(providerRefLeak), /portable_event_key_not_allowed:provider_ref/);
const secretAlias = structuredClone(input);
// Assemble a credential-shaped test value at runtime so source scanners do not confuse this negative fixture with a live credential.
secretAlias.provider_aliases[0].adapter_contract = ['sk_', 'live_', '12345678901234567890'].join('');
assert.throws(() => buildPortableWalletCapsule(secretAlias), /portable_wallet_secret_shape_detected/);
assert.throws(() => planProviderRemap(capsule, {
  alias_id: 'fiat-primary', new_adapter_ref: 'ct.adapter.prod', target_environment: 'production',
}), /portable_target_environment_not_allowed/);

console.log(JSON.stringify({
  result: 'PASS_PORTABLE_WALLET_CAPSULE',
  event_count: capsule.event_count,
  chain_head_preserved: true,
  input_order_independent: true,
  stable_wallet_id_preserved: true,
  provider_alias_remap_planned: true,
  raw_provider_reference_exposed: false,
  provider_credentials_included: false,
  source_payload_body_included: false,
  tamper_rejected: true,
  provider_write: false,
  rights_mutation: false,
  money_movement: false,
}));
