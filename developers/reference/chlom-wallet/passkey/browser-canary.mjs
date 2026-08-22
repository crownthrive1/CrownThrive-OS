const EXPECTED_ORIGIN = 'https://wallet.crownthrive.com';
const EXPECTED_FUNCTION_SLUG = 'chlom-wallet-passkey-control';
const DEFAULT_TIMEOUT_MS = 60_000;

export const BROWSER_CANARY_BOUNDARIES = Object.freeze({
  production_credential_activation: false,
  smart_account_binding: false,
  smart_account_deployment: false,
  chain_broadcast: false,
  custody: false,
  money_movement: false,
  production_rights_grant: false,
});

export function bytesToBase64url(value) {
  const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/g, '');
}

export function base64urlToBytes(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new Error('base64url_value_invalid');
  }
  const base64 = value.replaceAll('-', '+').replaceAll('_', '/');
  const binary = atob(base64 + '==='.slice((base64.length + 3) % 4));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function descriptors(values = []) {
  return values.map((item) => ({ ...item, id: base64urlToBytes(item.id) }));
}

export function decodeRegistrationOptions(publicKey) {
  if (!publicKey || typeof publicKey !== 'object') throw new Error('registration_options_required');
  return {
    ...publicKey,
    challenge: base64urlToBytes(publicKey.challenge),
    user: {
      ...publicKey.user,
      id: base64urlToBytes(publicKey.user?.id),
    },
    excludeCredentials: descriptors(publicKey.excludeCredentials ?? []),
  };
}

export function decodeAuthenticationOptions(publicKey) {
  if (!publicKey || typeof publicKey !== 'object') throw new Error('authentication_options_required');
  return {
    ...publicKey,
    challenge: base64urlToBytes(publicKey.challenge),
    allowCredentials: descriptors(publicKey.allowCredentials ?? []),
  };
}

function commonCredentialFields(credential) {
  if (!credential || typeof credential !== 'object') throw new Error('public_key_credential_required');
  return {
    id: credential.id,
    rawId: bytesToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment ?? null,
    clientExtensionResults: credential.getClientExtensionResults?.() ?? {},
  };
}

export function serializeRegistrationCredential(credential) {
  const common = commonCredentialFields(credential);
  const response = credential.response;
  if (!response?.clientDataJSON || !response?.attestationObject) {
    throw new Error('registration_credential_response_invalid');
  }
  return {
    ...common,
    response: {
      clientDataJSON: bytesToBase64url(response.clientDataJSON),
      attestationObject: bytesToBase64url(response.attestationObject),
      transports: response.getTransports?.() ?? [],
    },
  };
}

export function serializeAuthenticationCredential(credential) {
  const common = commonCredentialFields(credential);
  const response = credential.response;
  if (!response?.clientDataJSON || !response?.authenticatorData || !response?.signature) {
    throw new Error('authentication_credential_response_invalid');
  }
  return {
    ...common,
    response: {
      clientDataJSON: bytesToBase64url(response.clientDataJSON),
      authenticatorData: bytesToBase64url(response.authenticatorData),
      signature: bytesToBase64url(response.signature),
      userHandle: response.userHandle ? bytesToBase64url(response.userHandle) : null,
    },
  };
}

export function validateCanaryEndpoint(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error('canary_endpoint_invalid');
  }
  if (url.protocol !== 'https:') throw new Error('canary_endpoint_https_required');
  if (url.username || url.password || url.hash) throw new Error('canary_endpoint_credentials_or_fragment_forbidden');
  if (!url.pathname.endsWith(`/${EXPECTED_FUNCTION_SLUG}`)) throw new Error('canary_endpoint_slug_mismatch');
  return url.toString();
}

export function assertControlledBrowserEnvironment({
  origin = globalThis.location?.origin,
  secureContext = globalThis.isSecureContext,
  credentials = globalThis.navigator?.credentials,
} = {}) {
  if (origin !== EXPECTED_ORIGIN) throw new Error('wallet_origin_required');
  if (secureContext !== true) throw new Error('secure_context_required');
  if (!credentials || typeof credentials.create !== 'function' || typeof credentials.get !== 'function') {
    throw new Error('webauthn_credentials_api_required');
  }
  return true;
}

async function postAction(endpoint, bearerToken, body, fetchImpl, timeoutMs) {
  const response = await fetchImpl(endpoint, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${bearerToken}`,
      'content-type': 'application/json',
      'x-crownthrive-correlation-id': `ct.wallet.browser-canary.${crypto.randomUUID()}`,
    },
    body: JSON.stringify(body),
    cache: 'no-store',
    credentials: 'omit',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    signal: AbortSignal.timeout(timeoutMs),
  });
  const payload = await response.json().catch(() => ({ ok: false, error: 'non_json_response' }));
  if (!response.ok || payload?.ok !== true) {
    const reason = typeof payload?.error === 'string' ? payload.error : `http_${response.status}`;
    throw new Error(`browser_canary_action_failed:${reason}`);
  }
  return payload;
}

export async function runControlledBrowserCanary({
  endpoint,
  accessToken,
  includeRecoveryStepUp = false,
  fetchImpl = globalThis.fetch,
  credentialApi = globalThis.navigator?.credentials,
  timeoutMs = DEFAULT_TIMEOUT_MS,
} = {}) {
  assertControlledBrowserEnvironment({ credentials: credentialApi });
  const safeEndpoint = validateCanaryEndpoint(endpoint);
  if (typeof accessToken !== 'string' || accessToken.length < 32) throw new Error('authenticated_access_token_required');
  if (typeof fetchImpl !== 'function') throw new Error('fetch_api_required');
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 10_000 || timeoutMs > 180_000) throw new Error('timeout_out_of_range');

  let bearer = accessToken;
  try {
    const registrationOptions = await postAction(
      safeEndpoint,
      bearer,
      { action: 'registration-options' },
      fetchImpl,
      timeoutMs,
    );
    const registrationCredential = await credentialApi.create({
      publicKey: decodeRegistrationOptions(registrationOptions.publicKey),
    });
    const registration = await postAction(
      safeEndpoint,
      bearer,
      {
        action: 'verify-registration',
        challenge_id: registrationOptions.challenge_id,
        response: serializeRegistrationCredential(registrationCredential),
      },
      fetchImpl,
      timeoutMs,
    );

    const assertionOptions = await postAction(
      safeEndpoint,
      bearer,
      { action: 'assertion-options' },
      fetchImpl,
      timeoutMs,
    );
    const assertionCredential = await credentialApi.get({
      publicKey: decodeAuthenticationOptions(assertionOptions.publicKey),
    });
    const assertion = await postAction(
      safeEndpoint,
      bearer,
      {
        action: 'verify-assertion',
        challenge_id: assertionOptions.challenge_id,
        response: serializeAuthenticationCredential(assertionCredential),
      },
      fetchImpl,
      timeoutMs,
    );

    let recovery = null;
    if (includeRecoveryStepUp) {
      const recoveryOptions = await postAction(
        safeEndpoint,
        bearer,
        { action: 'recovery-step-up-options' },
        fetchImpl,
        timeoutMs,
      );
      const recoveryCredential = await credentialApi.get({
        publicKey: decodeAuthenticationOptions(recoveryOptions.publicKey),
      });
      recovery = await postAction(
        safeEndpoint,
        bearer,
        {
          action: 'verify-recovery-step-up',
          challenge_id: recoveryOptions.challenge_id,
          response: serializeAuthenticationCredential(recoveryCredential),
        },
        fetchImpl,
        timeoutMs,
      );
    }

    const result = {
      result: 'PASS_AUTHENTICATED_BROWSER_WEBAUTHN_CANARY',
      origin: EXPECTED_ORIGIN,
      registration_state: registration.state,
      registration_receipt_digest_sha256: registration.receipt_digest_sha256 ?? null,
      assertion_state: assertion.state,
      assertion_receipt_digest_sha256: assertion.receipt_digest_sha256 ?? null,
      recovery_step_up_state: recovery?.state ?? 'NOT_REQUESTED',
      recovery_receipt_digest_sha256: recovery?.receipt_digest_sha256 ?? null,
      access_token_persisted: false,
      access_token_logged: false,
      ...BROWSER_CANARY_BOUNDARIES,
    };
    if (
      result.registration_state !== 'VERIFIED_REGISTRATION_CONTROLLED_TEST'
      || result.assertion_state !== 'VERIFIED_ASSERTION_CONTROLLED_TEST'
      || (includeRecoveryStepUp && result.recovery_step_up_state !== 'VERIFIED_ASSERTION_CONTROLLED_TEST')
    ) {
      throw new Error('browser_canary_controlled_state_mismatch');
    }
    return Object.freeze(result);
  } finally {
    bearer = '';
  }
}
