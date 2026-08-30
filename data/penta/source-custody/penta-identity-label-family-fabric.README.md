# Penta identity/family source custody

The JSON manifest in this directory is generated from the production Supabase migration ledger. It records provider-issued migration versions and SHA-256 hashes while preserving production history. The projector does not replay or rewrite applied migrations and does not export raw secrets.

Canonical implementation files for this wave are the provider-exact SQL files under `supabase/migrations/` and `supabase/functions/penta-identity-source-custody-v1/index.ts`.
