# Locticians Brilliant Directories Key Ingest v3

Runtime: `locticians-bd-key-ingest-v3`  
JWT verification: enabled  
Authority: founder/admin only  
DAIL event: `a61bb889-2308-4051-baa8-28a295d91f6e`

This route closes the CrownThrive-side automation gap after Brilliant Directories provider-admin key generation. It does **not** generate a Brilliant Directories key and it never treats a token returned by the provider API-key inventory as a usable credential.

The route accepts only one of the three pre-registered Locticians credential lanes, verifies the submitted key using `GET https://locticians.com/api/v2/token/verify`, verifies the Locticians provider identity, hashes the credential for evidence, writes the raw credential directly into its fixed Supabase Vault alias through `locticians_vault_new_provider_key_v3`, registers the lane through `locticians_register_new_bd_key_v3`, and returns only non-secret evidence.

Allowed lanes:

- `ct.locticians.bd.hot.a.v3` → `locticians_brilliant_directories_hot_a_v3`
- `ct.locticians.bd.hot.b.v3` → `locticians_brilliant_directories_hot_b_v3`
- `ct.locticians.bd.cold.reserve.v3` → `locticians_brilliant_directories_cold_reserve_v3`

The Vault helper is non-overwriting. A lane cannot silently replace an existing vaulted credential. After successful ingestion the next gate is PentaCertify permission/canary reconciliation before broad route assignment.

Unauthenticated requests are rejected by the Edge gateway before function execution; the production negative canary returns HTTP 401 for both `locticians-bd-key-ingest-v3` and `locticians-bd-router-v2` without an Authorization header.

No DELETE is performed by this workflow. Provider records 15 and 16 remain disabled failed-bootstrap evidence until a separately authorized D3 cleanup action exists.
