import assert from 'node:assert/strict';
import {
  BROWSER_CANARY_BOUNDARIES,
  assertControlledBrowserEnvironment,
  base64urlToBytes,
  bytesToBase64url,
  decodeAuthenticationOptions,
  decodeRegistrationOptions,
  runControlledBrowserCanary,
  serializeAuthenticationCredential,
  serializeRegistrationCredential,
  validateCanaryEndpoint,
} from './browser-canary.mjs';

Object.defineProperty(globalThis, 'location', {
  configurable: true,
  value: { origin: 'https://wallet.crownthrive.com' },
});
Object.defineProperty(globalThis, 'isSecureContext', {
  configurable: true,
  value: true,
});

const challenge = new Uint8Array([1, 2, 3, 4, 5, 255]);
const encoded = bytesToBase64url(challenge);
assert.deepEqual([...base64urlToBytes(encoded)], [...challenge]);
assert.throws(() => base64urlToBytes('not+base64url'), /base64url_value_invalid/);

const registrationOptions = decodeRegistrationOptions({
  challenge: encoded,
  rp: { id: 'crownthrive.com', name: 'CrownThrive' },
  user: { id: bytesToBase64url(new Uint8Array([9, 8, 7])), name: 'Member', displayName: 'Member' },
  pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
  excludeCredentials: [{ type: 'public-key', id: bytesToBase64url(new Uint8Array([6, 5, 4])) }],
});
assert.ok(registrationOptions.challenge instanceof Uint8Array);
assert.ok(registrationOptions.user.id instanceof Uint8Array);
assert.ok(registrationOptions.excludeCredentials[0].id instanceof Uint8Array);

const authenticationOptions = decodeAuthenticationOptions({
  challenge: encoded,
  rpId: 'crownthrive.com',
  allowCredentials: [{ type: 'public-key', id: bytesToBase64url(new Uint8Array([3, 2, 1])) }],
});
assert.ok(authenticationOptions.challenge instanceof Uint8Array);
assert.ok(authenticationOptions.allowCredentials[0].id instanceof Uint8Array);

const registrationCredential = {
  id: 'credential-registration',
  rawId: new Uint8Array([11, 12, 13]),
  type: 'public-key',
  authenticatorAttachment: 'platform',
  getClientExtensionResults: () => ({ credProps: { rk: true } }),
  response: {
    clientDataJSON: new Uint8Array([21, 22]),
    attestationObject: new Uint8Array([31, 32]),
    getTransports: () => ['internal'],
  },
};
const serializedRegistration = serializeRegistrationCredential(registrationCredential);
assert.equal(serializedRegistration.id, registrationCredential.id);
assert.deepEqual(serializedRegistration.response.transports, ['internal']);
assert.equal(serializedRegistration.response.clientDataJSON, bytesToBase64url(new Uint8Array([21, 22])));

const assertionCredential = {
  id: 'credential-authentication',
  rawId: new Uint8Array([11, 12, 13]),
  type: 'public-key',
  authenticatorAttachment: 'platform',
  getClientExtensionResults: () => ({}),
  response: {
    clientDataJSON: new Uint8Array([41, 42]),
    authenticatorData: new Uint8Array([51, 52]),
    signature: new Uint8Array([61, 62]),
    userHandle: new Uint8Array([71, 72]),
  },
};
const serializedAssertion = serializeAuthenticationCredential(assertionCredential);
assert.equal(serializedAssertion.response.signature, bytesToBase64url(new Uint8Array([61, 62])));
assert.equal(serializedAssertion.response.userHandle, bytesToBase64url(new Uint8Array([71, 72])));

assert.equal(assertControlledBrowserEnvironment({
  origin: 'https://wallet.crownthrive.com',
  secureContext: true,
  credentials: { create() {}, get() {} },
}), true);
assert.throws(() => assertControlledBrowserEnvironment({
  origin: 'https://example.com',
  secureContext: true,
  credentials: { create() {}, get() {} },
}), /wallet_origin_required/);
assert.throws(() => validateCanaryEndpoint('http://example.com/functions/v1/chlom-wallet-passkey-control'), /https_required/);
assert.throws(() => validateCanaryEndpoint('https://example.com/functions/v1/other'), /slug_mismatch/);

const endpoint = 'https://example.supabase.co/functions/v1/chlom-wallet-passkey-control';
assert.equal(validateCanaryEndpoint(endpoint), endpoint);
const actions = [];
const fetchImpl = async (_url, options) => {
  assert.equal(options.credentials, 'omit');
  assert.equal(options.cache, 'no-store');
  assert.equal(options.referrerPolicy, 'no-referrer');
  assert.match(options.headers.authorization, /^Bearer /);
  const body = JSON.parse(options.body);
  actions.push(body.action);
  let payload;
  if (body.action === 'registration-options') {
    payload = {
      ok: true,
      challenge_id: '11111111-1111-4111-8111-111111111111',
      publicKey: {
        challenge: encoded,
        rp: { id: 'crownthrive.com', name: 'CrownThrive' },
        user: { id: bytesToBase64url(new Uint8Array([1, 2, 3])), name: 'Member', displayName: 'Member' },
        pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
      },
    };
  } else if (body.action === 'verify-registration') {
    assert.equal(body.challenge_id, '11111111-1111-4111-8111-111111111111');
    assert.equal(body.response.id, registrationCredential.id);
    payload = {
      ok: true,
      state: 'VERIFIED_REGISTRATION_CONTROLLED_TEST',
      receipt_digest_sha256: 'a'.repeat(64),
    };
  } else if (body.action === 'assertion-options') {
    payload = {
      ok: true,
      challenge_id: '22222222-2222-4222-8222-222222222222',
      publicKey: { challenge: encoded, rpId: 'crownthrive.com', userVerification: 'required' },
    };
  } else if (body.action === 'verify-assertion') {
    assert.equal(body.challenge_id, '22222222-2222-4222-8222-222222222222');
    assert.equal(body.response.id, assertionCredential.id);
    payload = {
      ok: true,
      state: 'VERIFIED_ASSERTION_CONTROLLED_TEST',
      receipt_digest_sha256: 'b'.repeat(64),
    };
  } else {
    payload = { ok: false, error: 'unexpected_action' };
  }
  return new Response(JSON.stringify(payload), {
    status: payload.ok ? 200 : 400,
    headers: { 'content-type': 'application/json' },
  });
};

let createCalls = 0;
let getCalls = 0;
const credentialApi = {
  async create({ publicKey }) {
    createCalls += 1;
    assert.ok(publicKey.challenge instanceof Uint8Array);
    return registrationCredential;
  },
  async get({ publicKey }) {
    getCalls += 1;
    assert.ok(publicKey.challenge instanceof Uint8Array);
    return assertionCredential;
  },
};

const result = await runControlledBrowserCanary({
  endpoint,
  accessToken: 'controlled-test-jwt-placeholder-not-a-real-secret',
  fetchImpl,
  credentialApi,
});
assert.equal(result.result, 'PASS_AUTHENTICATED_BROWSER_WEBAUTHN_CANARY');
assert.equal(result.registration_state, 'VERIFIED_REGISTRATION_CONTROLLED_TEST');
assert.equal(result.assertion_state, 'VERIFIED_ASSERTION_CONTROLLED_TEST');
assert.equal(result.recovery_step_up_state, 'NOT_REQUESTED');
assert.equal(result.access_token_persisted, false);
assert.equal(result.access_token_logged, false);
assert.deepEqual(actions, [
  'registration-options',
  'verify-registration',
  'assertion-options',
  'verify-assertion',
]);
assert.equal(createCalls, 1);
assert.equal(getCalls, 1);
assert.deepEqual(BROWSER_CANARY_BOUNDARIES, {
  production_credential_activation: false,
  smart_account_binding: false,
  smart_account_deployment: false,
  chain_broadcast: false,
  custody: false,
  money_movement: false,
  production_rights_grant: false,
});

console.log(JSON.stringify({
  result: 'PASS_WEBAUTHN_BROWSER_CANARY_CONTRACT',
  base64url_roundtrip: true,
  registration_options_decoded: true,
  assertion_options_decoded: true,
  registration_credential_serialized: true,
  assertion_credential_serialized: true,
  exact_wallet_origin_required: true,
  secure_context_required: true,
  endpoint_https_and_slug_bound: true,
  mocked_action_sequence_verified: true,
  authenticated_browser_ceremony_executed: false,
  production_credential_activation: false,
  smart_account_binding: false,
  smart_account_deployment: false,
  chain_broadcast: false,
  custody: false,
  money_movement: false,
}));
