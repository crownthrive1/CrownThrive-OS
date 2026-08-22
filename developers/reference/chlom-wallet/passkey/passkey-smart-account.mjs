import { createHash } from 'node:crypto';

// CONTROLLED-TEST INTENT BUILDER.
// This module does not create credentials, signing material, UserOperations, signatures,
// smart accounts, or blockchain transactions. It normalizes public registration intent only.

const sha256 = (value) => createHash('sha256').update(value).digest('hex');

export function normalizeCaip2(namespace, reference) {
  const value = `${String(namespace ?? '')}:${String(reference ?? '')}`;
  if (!/^[-a-z0-9]{3,8}:[-_a-zA-Z0-9]{1,32}$/.test(value)) throw new Error('invalid_caip2');
  return value;
}

export function normalizeCaip10(chainId, accountAddress) {
  if (typeof chainId !== 'string' || !/^[-a-z0-9]{3,8}:[-_a-zA-Z0-9]{1,32}$/.test(chainId)) throw new Error('invalid_caip2');
  if (typeof accountAddress !== 'string' || !/^[-.%a-zA-Z0-9]{1,128}$/.test(accountAddress)) throw new Error('invalid_caip10_account_address');
  return `${chainId}:${accountAddress}`;
}

export function normalizeCredentialDescriptor(input) {
  if (!input || typeof input !== 'object') throw new Error('credential_descriptor_required');
  const credentialId = String(input.credential_id ?? '');
  const rpId = String(input.rp_id ?? '').toLowerCase();
  const origin = String(input.origin ?? '');
  if (!/^[A-Za-z0-9_-]{16,1024}$/.test(credentialId)) throw new Error('credential_id_invalid');
  if (!/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(rpId)) throw new Error('rp_id_invalid');
  let parsedOrigin;
  try { parsedOrigin = new URL(origin); } catch { throw new Error('origin_invalid'); }
  if (parsedOrigin.protocol !== 'https:') throw new Error('https_origin_required');
  if (parsedOrigin.hostname !== rpId && !parsedOrigin.hostname.endsWith(`.${rpId}`)) throw new Error('origin_rp_mismatch');
  const transports = [...new Set((Array.isArray(input.transports) ? input.transports : []).map(String))].sort();
  const algorithm = Number(input.cose_algorithm ?? -7);
  if (!Number.isInteger(algorithm)) throw new Error('cose_algorithm_invalid');
  return {
    credential_id: credentialId,
    rp_id: rpId,
    origin: parsedOrigin.origin,
    transports,
    cose_algorithm: algorithm,
    resident_key: input.resident_key === true,
    user_verification: input.user_verification === true,
  };
}

export function credentialCommitment(input) {
  const normalized = normalizeCredentialDescriptor(input);
  const commitmentPayload = JSON.stringify({
    credential_id: normalized.credential_id,
    rp_id: normalized.rp_id,
    origin: normalized.origin,
    cose_algorithm: normalized.cose_algorithm,
    resident_key: normalized.resident_key,
    user_verification: normalized.user_verification,
    transports: normalized.transports,
  });
  return {
    algorithm: 'sha256',
    commitment: sha256(commitmentPayload),
    public_descriptor: {
      rp_id: normalized.rp_id,
      cose_algorithm: normalized.cose_algorithm,
      resident_key: normalized.resident_key,
      user_verification: normalized.user_verification,
      transports: normalized.transports,
    },
    raw_credential_exported: false,
  };
}

export function buildSmartAccountRegistrationIntent(input) {
  if (!input || typeof input !== 'object') throw new Error('registration_intent_required');
  const chainId = normalizeCaip2(input.chain_namespace ?? 'eip155', input.chain_reference);
  const credential = credentialCommitment(input.credential);
  const walletStableId = String(input.wallet_stable_id ?? '');
  if (!/^ct\.wallet\.[A-Za-z0-9._-]{1,120}$/.test(walletStableId)) throw new Error('wallet_stable_id_invalid');
  const accountStandard = String(input.account_standard ?? 'ERC-4337');
  if (!['ERC-4337', 'ERC-7579'].includes(accountStandard)) throw new Error('unsupported_account_standard');
  const factoryRef = input.factory_ref == null ? null : String(input.factory_ref);
  const entryPointRef = input.entrypoint_ref == null ? null : String(input.entrypoint_ref);
  const intent = {
    version: 1,
    wallet_stable_id: walletStableId,
    chain_id: chainId,
    account_standard: accountStandard,
    credential_commitment: credential.commitment,
    credential_policy: credential.public_descriptor,
    factory_ref: factoryRef,
    entrypoint_ref: entryPointRef,
    session_modules: [],
    paymaster_policy: 'disabled_by_default',
    recovery_policy: 'separate_governed_record_required',
    broadcast: false,
    deploy: false,
    money_movement: false,
  };
  return {
    ...intent,
    intent_digest: sha256(JSON.stringify(intent)),
  };
}

export function bindDeployedAccountCandidate(intent, accountAddress) {
  if (!intent || intent.broadcast !== false || intent.deploy !== false || typeof intent.chain_id !== 'string') {
    throw new Error('controlled_intent_required');
  }
  return {
    wallet_stable_id: intent.wallet_stable_id,
    chain_account_id: normalizeCaip10(intent.chain_id, accountAddress),
    account_standard: intent.account_standard,
    credential_commitment: intent.credential_commitment,
    verification_state: 'candidate_unverified',
    authority_state: 'HOLD_EXTERNAL_DEPLOYMENT_EVIDENCE_REQUIRED',
  };
}
