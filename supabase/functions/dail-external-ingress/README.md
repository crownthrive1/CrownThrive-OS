# DAIL Stripe external ingress

This Supabase Edge Function accepts Stripe webhook `POST` requests, verifies the
signature against the exact raw request bytes with a fixed 300-second tolerance,
and projects only provider identifiers plus SHA-256 digests into
`public.dail_ingest_verified_external_event_v2`. Business processing remains
asynchronous. The raw body, raw `Stripe-Signature` header, and endpoint-secret
values are never returned, logged, or sent to Postgres.

This directory is a source implementation. It does not establish that the
function, migration, endpoint-secret binding, or a live Stripe webhook has been
deployed or proven in production.

## Runtime configuration

Required Edge Function secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DAIL_STRIPE_WEBHOOK_SECRETS_JSON`
- `DAIL_INGRESS_ADMISSION_HMAC_KEY`

`DAIL_STRIPE_WEBHOOK_SECRETS_JSON` is a JSON array. Each active rotation entry
contains a non-secret version reference and an endpoint-secret value:

```json
[
  {
    "version_ref": "vault:stripe:endpoint:2026-08",
    "secret": "whsec_REPLACE_WITH_ENDPOINT_SECRET",
    "environment": "live",
    "account_ref": "acct_OPTIONAL",
    "active_from": "2026-08-01T00:00:00Z",
    "active_until": "2026-09-01T00:00:00Z"
  }
]
```

Up to eight entries may overlap during rotation. `active_from`, `active_until`,
and `account_ref` are optional. A value beginning with `sk_live_`, `sk_test_`,
or `rk_` is a Stripe API key, not a webhook endpoint secret, and is rejected.
Only `whsec_...` endpoint secrets belong in this setting. Do not place secret
material in `version_ref` or `account_ref`.

`DAIL_INGRESS_ADMISSION_HMAC_KEY` is a separate, high-entropy secret shared
only with the database-side admission verifier. It must be at least 32 UTF-8
bytes and must not be a Stripe `whsec_`, API, restricted, or publishable key.
Store the identical value in Supabase Vault under the exact secret name
`dail_external_ingress_admission_hmac_key_v2`. The migration does not create
or populate that secret. Until both bindings exist, admission fails closed.
The function MACs a narrow event/digest statement before the service-role RPC;
neither this key nor the resulting MAC is exposed in HTTP responses or logs.
The authenticated UTF-8 statement is exactly
`dail-external-ingress-v2|event_id|raw_body_sha256|signature_timestamp|matched_secret_version_ref`.

## Supabase gateway configuration

Stripe authenticates with `Stripe-Signature`, not a Supabase JWT. JWT checking
must therefore be disabled for this one function in the project-level
`supabase/config.toml`:

```toml
[functions.dail-external-ingress]
verify_jwt = false
```

Do not disable JWT verification globally. The handler is POST-only and fails
closed if its secret set or service-role database configuration is unavailable.

## Local tests

With Node 22 or newer:

```sh
node --test handler.test.ts stripe_signature.test.ts
```

The tests use injected environment/database boundaries and make no network or
live-provider calls.
